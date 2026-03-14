"""Tests for cover art endpoints: POST/PUT/DELETE /api/collection/{instance_id}/cover."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from conftest import TEST_USER_ID
from repository.models import CollectionItem


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
    master_id=999,
)

SAMPLE_ITEM_NO_MASTER = CollectionItem(
    user_id=TEST_USER_ID,
    instance_id=200,
    release_id=666,
    title="No Master",
    artist="Test",
    year=2020,
    master_id=None,
)


@pytest.fixture()
def mock_repo():
    repo = MagicMock()
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


# ── GET /api/collection/{instance_id}/cover/master (preview) ─────────────────


@patch("routes.collection.get_master_cover")
def test_preview_master_cover_success(mock_get_master_cover, client, mock_repo):
    mock_repo.find_collection_item.return_value = SAMPLE_ITEM
    mock_get_master_cover.return_value = "https://img.discogs.com/master.jpg"

    resp = client.get("/api/collection/100/cover/master")
    assert resp.status_code == 200
    assert resp.json()["cover_url"] == "https://img.discogs.com/master.jpg"
    # Preview should NOT persist anything
    mock_repo.update_collection_item_cover.assert_not_called()


def test_preview_master_cover_item_not_found(client, mock_repo):
    mock_repo.find_collection_item.return_value = None
    resp = client.get("/api/collection/999/cover/master")
    assert resp.status_code == 404


def test_preview_master_cover_no_master_id(client, mock_repo):
    mock_repo.find_collection_item.return_value = SAMPLE_ITEM_NO_MASTER
    resp = client.get("/api/collection/200/cover/master")
    assert resp.status_code == 400


@patch("routes.collection.get_master_cover")
def test_preview_master_cover_no_cover_found(mock_get_master_cover, client, mock_repo):
    mock_repo.find_collection_item.return_value = SAMPLE_ITEM
    mock_get_master_cover.return_value = None
    resp = client.get("/api/collection/100/cover/master")
    assert resp.status_code == 404


# ── POST /api/collection/{instance_id}/cover/master (confirm) ────────────────


@patch("routes.collection.get_master_cover")
def test_use_master_cover_success(mock_get_master_cover, client, mock_repo):
    mock_repo.find_collection_item.return_value = SAMPLE_ITEM
    mock_get_master_cover.return_value = "https://img.discogs.com/master.jpg"
    mock_repo.update_collection_item_cover.return_value = True

    resp = client.post("/api/collection/100/cover/master")
    assert resp.status_code == 200
    data = resp.json()
    assert data["custom_cover_image"] == "https://img.discogs.com/master.jpg"
    mock_get_master_cover.assert_called_once_with(999, mock_get_master_cover.call_args[0][1])
    mock_repo.update_collection_item_cover.assert_called_once_with(
        TEST_USER_ID, 100, "https://img.discogs.com/master.jpg",
    )


def test_use_master_cover_item_not_found(client, mock_repo):
    mock_repo.find_collection_item.return_value = None
    resp = client.post("/api/collection/999/cover/master")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_use_master_cover_no_master_id(client, mock_repo):
    mock_repo.find_collection_item.return_value = SAMPLE_ITEM_NO_MASTER
    resp = client.post("/api/collection/200/cover/master")
    assert resp.status_code == 400
    assert "no master" in resp.json()["detail"].lower()


@patch("routes.collection.get_master_cover")
def test_use_master_cover_no_cover_found(mock_get_master_cover, client, mock_repo):
    mock_repo.find_collection_item.return_value = SAMPLE_ITEM
    mock_get_master_cover.return_value = None

    resp = client.post("/api/collection/100/cover/master")
    assert resp.status_code == 404
    assert "no cover" in resp.json()["detail"].lower()


# ── PUT /api/collection/{instance_id}/cover ──────────────────────────────────


def _supabase_cover_url(path="custom.jpg"):
    """Build a valid Supabase Storage cover URL for tests."""
    import os
    base = os.getenv("SUPABASE_URL", os.getenv("VITE_SUPABASE_URL", "http://127.0.0.1:54321"))
    return f"{base.rstrip('/')}/storage/v1/object/public/covers/{path}"


def test_set_custom_cover_success(client, mock_repo):
    mock_repo.find_collection_item.return_value = SAMPLE_ITEM
    mock_repo.update_collection_item_cover.return_value = True

    url = _supabase_cover_url("user1/100.jpg")
    resp = client.put("/api/collection/100/cover", json={"url": url})
    assert resp.status_code == 200
    assert resp.json()["custom_cover_image"] == url
    mock_repo.update_collection_item_cover.assert_called_once_with(
        TEST_USER_ID, 100, url,
    )


def test_set_custom_cover_item_not_found(client, mock_repo):
    mock_repo.find_collection_item.return_value = None
    url = _supabase_cover_url("user1/999.jpg")
    resp = client.put("/api/collection/999/cover", json={"url": url})
    assert resp.status_code == 404


def test_set_custom_cover_empty_url(client, mock_repo):
    resp = client.put("/api/collection/100/cover", json={"url": ""})
    assert resp.status_code == 422  # validation error


def test_set_custom_cover_rejects_external_url(client, mock_repo):
    """Cover URL must point to Supabase Storage covers bucket (SSRF prevention)."""
    mock_repo.find_collection_item.return_value = SAMPLE_ITEM
    resp = client.put(
        "/api/collection/100/cover",
        json={"url": "http://169.254.169.254/latest/meta-data/"},
    )
    assert resp.status_code == 400
    assert "Supabase Storage" in resp.json()["detail"]


# ── DELETE /api/collection/{instance_id}/cover ───────────────────────────────


def test_reset_cover_success(client, mock_repo):
    mock_repo.find_collection_item.return_value = SAMPLE_ITEM
    mock_repo.update_collection_item_cover.return_value = True

    resp = client.delete("/api/collection/100/cover")
    assert resp.status_code == 200
    assert resp.json()["custom_cover_image"] is None
    mock_repo.update_collection_item_cover.assert_called_once_with(
        TEST_USER_ID, 100, None,
    )


def test_reset_cover_item_not_found(client, mock_repo):
    mock_repo.find_collection_item.return_value = None
    resp = client.delete("/api/collection/999/cover")
    assert resp.status_code == 404
