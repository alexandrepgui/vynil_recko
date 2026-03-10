"""Tests for the profile routes (/api/me)."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from conftest import TEST_USER_ID, TEST_USER_EMAIL


@pytest.fixture()
def client(mock_jwt_user):
    from deps import get_repo
    from main import app

    mock_repo = MagicMock()
    mock_repo.load_oauth_tokens.return_value = None
    app.dependency_overrides[get_repo] = lambda: mock_repo
    yield TestClient(app), mock_repo
    app.dependency_overrides.pop(get_repo, None)


class TestGetProfile:
    def test_returns_user_info(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.delenv("DISCOGS_CONSUMER_KEY", raising=False)
        monkeypatch.delenv("DISCOGS_CONSUMER_SECRET", raising=False)
        resp = test_client.get("/api/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == TEST_USER_ID
        assert data["email"] == TEST_USER_EMAIL
        assert data["discogs"]["connected"] is False

    def test_discogs_connected(self, client, monkeypatch):
        test_client, mock_repo = client
        monkeypatch.setenv("DISCOGS_CONSUMER_KEY", "k")
        monkeypatch.setenv("DISCOGS_CONSUMER_SECRET", "s")
        mock_repo.load_oauth_tokens.return_value = {
            "access_token": "a", "access_token_secret": "b", "username": "dj_test",
        }
        resp = test_client.get("/api/me")
        data = resp.json()
        assert data["discogs"]["connected"] is True
        assert data["discogs"]["username"] == "dj_test"
        assert data["discogs"]["oauth_configured"] is True


class TestGetSettings:
    def test_returns_defaults(self, client):
        test_client, mock_repo = client
        mock_repo.get_user_settings.return_value = {"collection_public": False}
        resp = test_client.get("/api/me/settings")
        assert resp.status_code == 200
        assert resp.json()["collection_public"] is False
        mock_repo.get_user_settings.assert_called_once_with(TEST_USER_ID)

    def test_returns_stored_settings(self, client):
        test_client, mock_repo = client
        mock_repo.get_user_settings.return_value = {"collection_public": True}
        resp = test_client.get("/api/me/settings")
        assert resp.status_code == 200
        assert resp.json()["collection_public"] is True


class TestUpdateSettings:
    def test_update_collection_public(self, client):
        test_client, mock_repo = client
        mock_repo.get_user_settings.return_value = {"collection_public": True}
        resp = test_client.put("/api/me/settings", json={"collection_public": True})
        assert resp.status_code == 200
        assert resp.json()["collection_public"] is True
        mock_repo.update_user_settings.assert_called_once_with(
            TEST_USER_ID, {"collection_public": True},
        )

    def test_update_empty_body(self, client):
        test_client, mock_repo = client
        mock_repo.get_user_settings.return_value = {"collection_public": False}
        resp = test_client.put("/api/me/settings", json={})
        assert resp.status_code == 200
        mock_repo.update_user_settings.assert_not_called()
