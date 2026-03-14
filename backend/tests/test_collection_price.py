"""Tests for GET /api/collection, POST /api/collection, GET /api/price/{release_id}, and sync endpoints."""

from unittest.mock import MagicMock, patch

import pytest
import requests
from fastapi.testclient import TestClient

from auth import User, get_current_user
from conftest import TEST_USER_ID
from repository.models import CollectionItem


@pytest.fixture()
def mock_repo():
    repo = MagicMock()
    repo.saved_records = []
    repo.save_collection_record.side_effect = lambda r: repo.saved_records.append(r)
    # Default: no duplicates, never synced
    repo.has_release.return_value = False
    repo.get_sync_status.return_value = {"status": "idle"}
    repo.load_oauth_tokens.return_value = {
        "access_token": "test-token",
        "access_token_secret": "test-secret",
        "username": "testuser",
    }
    return repo


@pytest.fixture()
def client(mock_repo, mock_jwt_user):
    from deps import get_repo
    from main import app

    app.dependency_overrides[get_repo] = lambda: mock_repo
    yield TestClient(app)
    app.dependency_overrides.pop(get_repo, None)


# ── GET /api/collection (reads from MongoDB) ──────────────────────────────

SAMPLE_ITEM = CollectionItem(
    user_id=TEST_USER_ID,
    instance_id=100,
    release_id=555,
    title="Kind of Blue",
    artist="Miles Davis",
    year=1959,
    genres=["Jazz"],
    styles=["Modal"],
    format="LP",
    cover_image="https://img.discogs.com/cover.jpg",
    date_added="2024-01-15T10:00:00-08:00",
)


def test_get_collection_success(client, mock_repo):
    mock_repo.find_collection_items.return_value = [SAMPLE_ITEM]
    mock_repo.count_collection_items.return_value = 120
    resp = client.get("/api/collection")
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["pages"] == 3  # ceil(120/50)
    assert body["total_items"] == 120
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["release_id"] == 555
    assert item["title"] == "Kind of Blue"
    assert item["artist"] == "Miles Davis"
    assert item["year"] == 1959
    assert item["genres"] == ["Jazz"]
    assert item["format"] == "LP"
    assert item["cover_image"] == "https://img.discogs.com/cover.jpg"


def test_get_collection_with_params(client, mock_repo):
    mock_repo.find_collection_items.return_value = []
    mock_repo.count_collection_items.return_value = 0
    resp = client.get("/api/collection?page=2&per_page=25&sort=year&sort_order=desc")
    assert resp.status_code == 200
    mock_repo.find_collection_items.assert_called_once_with(
        TEST_USER_ID, query=None, sort="year", sort_order="desc", skip=25, limit=25,
    )


def test_get_collection_with_search(client, mock_repo):
    mock_repo.find_collection_items.return_value = []
    mock_repo.count_collection_items.return_value = 0
    resp = client.get("/api/collection?q=miles")
    assert resp.status_code == 200
    mock_repo.find_collection_items.assert_called_once_with(
        TEST_USER_ID, query="miles", sort="artist", sort_order="asc", skip=0, limit=50,
    )


def test_get_collection_empty(client, mock_repo):
    mock_repo.find_collection_items.return_value = []
    mock_repo.count_collection_items.return_value = 0
    resp = client.get("/api/collection")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total_items"] == 0


# ── Sync endpoints ────────────────────────────────────────────────────────


def test_trigger_sync_no_discogs(client, mock_repo):
    """Cannot sync without Discogs OAuth tokens."""
    mock_repo.get_sync_status.return_value = {"status": "idle"}
    mock_repo.load_oauth_tokens.return_value = None
    resp = client.post("/api/collection/sync")
    assert resp.status_code == 400
    assert "not connected" in resp.json()["detail"].lower()


def test_trigger_sync(client, mock_repo):
    mock_repo.get_sync_status.return_value = {"status": "idle"}
    mock_repo.load_oauth_tokens.return_value = {
        "access_token": "a", "access_token_secret": "b", "username": "u",
    }
    with patch("routes.collection.sync_full_collection"):
        resp = client.post("/api/collection/sync")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Sync started."


def test_trigger_sync_already_running(client, mock_repo):
    mock_repo.get_sync_status.return_value = {"status": "syncing"}
    resp = client.post("/api/collection/sync")
    assert resp.status_code == 409


def test_get_sync_status(client, mock_repo):
    mock_repo.get_sync_status.return_value = {
        "status": "idle",
        "completed_at": "2024-01-15T10:00:00Z",
        "total_items": 120,
    }
    resp = client.get("/api/collection/sync")
    assert resp.status_code == 200
    assert resp.json()["status"] == "idle"
    assert resp.json()["total_items"] == 120


# ── POST /api/collection ────────────────────────────────────────────────────


def test_add_to_collection_success(client, mock_repo):
    instance = {
        "instance_id": 42,
        "resource_url": "https://api.discogs.com/users/testuser/collection/folders/1/releases/123/instances/42",
    }
    with patch("routes.search.add_to_collection", return_value=instance):
        resp = client.post("/api/collection", json={"release_id": 123})
    assert resp.status_code == 200
    assert resp.json()["instance_id"] == 42
    assert mock_repo.save_collection_record.call_count == 1


def test_add_to_collection_duplicate_blocked(client, mock_repo):
    mock_repo.has_release.return_value = True
    resp = client.post("/api/collection", json={"release_id": 123})
    assert resp.status_code == 409
    assert "already in your collection" in resp.json()["detail"]


def test_add_to_collection_duplicate_forced(client, mock_repo):
    mock_repo.has_release.return_value = True
    instance = {
        "instance_id": 99,
        "resource_url": "https://api.discogs.com/users/testuser/collection/folders/1/releases/123/instances/99",
    }
    with patch("routes.search.add_to_collection", return_value=instance):
        resp = client.post("/api/collection", json={"release_id": 123, "force": True})
    assert resp.status_code == 200
    assert resp.json()["instance_id"] == 99


def test_add_to_collection_http_404(client, mock_repo):
    http_err = requests.HTTPError(response=MagicMock(status_code=404))
    with patch("routes.search.add_to_collection", side_effect=http_err):
        resp = client.post("/api/collection", json={"release_id": 999})
    assert resp.status_code == 404


def test_add_to_collection_http_502(client, mock_repo):
    http_err = requests.HTTPError(response=MagicMock(status_code=500))
    with patch("routes.search.add_to_collection", side_effect=http_err):
        resp = client.post("/api/collection", json={"release_id": 999})
    assert resp.status_code == 502


def test_add_to_collection_unexpected_error(client, mock_repo):
    with patch("routes.search.add_to_collection", side_effect=RuntimeError("boom")):
        resp = client.post("/api/collection", json={"release_id": 123})
    assert resp.status_code == 502
    assert mock_repo.save_collection_record.call_count == 1


# ── GET /api/price/{release_id} ─────────────────────────────────────────────


def test_get_price_success(client):
    stats = {"lowest_price": {"value": 12.50, "currency": "USD"}, "num_for_sale": 5}
    with patch("routes.search.get_marketplace_stats", return_value=stats):
        resp = client.get("/api/price/123")
    assert resp.status_code == 200
    assert resp.json() == {"lowest_price": 12.50, "num_for_sale": 5, "currency": "USD"}


def test_get_price_scalar_lowest(client):
    stats = {"lowest_price": 9.99, "num_for_sale": 2}
    with patch("routes.search.get_marketplace_stats", return_value=stats):
        resp = client.get("/api/price/456")
    assert resp.status_code == 200
    assert resp.json()["lowest_price"] == 9.99
    assert resp.json()["currency"] is None


def test_get_price_not_found(client):
    http_err = requests.HTTPError(response=MagicMock(status_code=404))
    with patch("routes.search.get_marketplace_stats", side_effect=http_err):
        resp = client.get("/api/price/999")
    assert resp.status_code == 404


def test_get_price_discogs_error(client):
    http_err = requests.HTTPError(response=MagicMock(status_code=500))
    with patch("routes.search.get_marketplace_stats", side_effect=http_err):
        resp = client.get("/api/price/123")
    assert resp.status_code == 502


def test_get_price_unexpected_error(client):
    with patch("routes.search.get_marketplace_stats", side_effect=RuntimeError("fail")):
        resp = client.get("/api/price/123")
    assert resp.status_code == 502


# ── DELETE /api/collection ─────────────────────────────────────────────────


def test_delete_collection_no_instance_ids(client, mock_repo):
    resp = client.request("DELETE", "/api/collection", json={"instance_ids": []})
    assert resp.status_code == 422  # Pydantic min_length=1 validation


def test_delete_collection_no_discogs_connected(client, mock_repo):
    mock_repo.load_oauth_tokens.return_value = None
    resp = client.request("DELETE", "/api/collection", json={"instance_ids": [1]})
    assert resp.status_code == 400
    assert "not connected" in resp.json()["detail"].lower()


def test_delete_collection_success(client, mock_repo):
    mock_repo.load_oauth_tokens.return_value = {
        "access_token": "a", "access_token_secret": "b", "username": "u",
    }
    mock_repo.find_collection_items_by_instance_ids.return_value = [
        CollectionItem(user_id=TEST_USER_ID, instance_id=100, release_id=555, title="Test"),
    ]
    mock_repo.delete_collection_items.return_value = 1

    with patch("routes.collection.remove_from_collection") as mock_remove:
        resp = client.request("DELETE", "/api/collection", json={"instance_ids": [100]})

    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] == 1
    assert body["errors"] == []
    mock_remove.assert_called_once_with(555, 100, mock_remove.call_args[0][2])
    mock_repo.delete_collection_items.assert_called_once()


def test_delete_collection_partial_failure(client, mock_repo):
    mock_repo.load_oauth_tokens.return_value = {
        "access_token": "a", "access_token_secret": "b", "username": "u",
    }
    mock_repo.find_collection_items_by_instance_ids.return_value = [
        CollectionItem(user_id=TEST_USER_ID, instance_id=100, release_id=555, title="A"),
        CollectionItem(user_id=TEST_USER_ID, instance_id=200, release_id=666, title="B"),
    ]
    mock_repo.delete_collection_items.return_value = 1

    def mock_remove_side_effect(release_id, instance_id, tokens):
        if instance_id == 200:
            raise RuntimeError("Discogs error")

    with patch("routes.collection.remove_from_collection", side_effect=mock_remove_side_effect):
        resp = client.request(
            "DELETE", "/api/collection", json={"instance_ids": [100, 200]},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["instance_id"] == 200


def test_delete_collection_not_found_in_db(client, mock_repo):
    mock_repo.load_oauth_tokens.return_value = {
        "access_token": "a", "access_token_secret": "b", "username": "u",
    }
    mock_repo.find_collection_items_by_instance_ids.return_value = []
    mock_repo.delete_collection_items.return_value = 0

    resp = client.request("DELETE", "/api/collection", json={"instance_ids": [999]})

    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] == 0
    assert len(body["errors"]) == 1
    assert body["errors"][0]["instance_id"] == 999


# ── GET /api/collection/{username} (public) ──────────────────────────────


def test_public_collection_user_not_found(client, mock_repo):
    mock_repo.find_user_id_by_username.return_value = None
    resp = client.get("/api/collection/nonexistent_user")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_public_collection_private(client, mock_repo):
    mock_repo.find_user_id_by_username.return_value = "other-user-id"
    mock_repo.get_user_settings.return_value = {"collection_public": False}
    resp = client.get("/api/collection/some_user")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_public_collection_success(client, mock_repo):
    mock_repo.find_user_id_by_username.return_value = "other-user-id"
    mock_repo.get_user_settings.return_value = {"collection_public": True}
    mock_repo.find_collection_items.return_value = [SAMPLE_ITEM]
    mock_repo.count_collection_items.return_value = 1

    resp = client.get("/api/collection/dj_public")
    assert resp.status_code == 200
    body = resp.json()
    assert body["owner"]["username"] == "dj_public"
    assert len(body["items"]) == 1
    assert body["total_items"] == 1
