"""Tests for the Discogs OAuth routes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from deps import get_repo
from main import app

mock_repo = MagicMock()
app.dependency_overrides[get_repo] = lambda: mock_repo

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_state():
    import services.discogs_auth as mod

    mod._current_tokens = None
    mod._pending.clear()
    mock_repo.reset_mock()
    yield
    mod._current_tokens = None
    mod._pending.clear()


class TestAuthStatus:
    def test_not_configured(self, monkeypatch):
        monkeypatch.delenv("DISCOGS_CONSUMER_KEY", raising=False)
        monkeypatch.delenv("DISCOGS_CONSUMER_SECRET", raising=False)
        resp = client.get("/api/auth/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["oauth_configured"] is False
        assert data["authenticated"] is False

    def test_configured_not_authenticated(self, monkeypatch):
        monkeypatch.setenv("DISCOGS_CONSUMER_KEY", "k")
        monkeypatch.setenv("DISCOGS_CONSUMER_SECRET", "s")
        resp = client.get("/api/auth/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["oauth_configured"] is True
        assert data["authenticated"] is False

    def test_authenticated(self, monkeypatch):
        monkeypatch.setenv("DISCOGS_CONSUMER_KEY", "k")
        monkeypatch.setenv("DISCOGS_CONSUMER_SECRET", "s")
        import services.discogs_auth as mod
        from services.discogs_auth import OAuthTokens

        mod._current_tokens = OAuthTokens(
            access_token="a", access_token_secret="b", username="dj_test"
        )
        resp = client.get("/api/auth/status")
        data = resp.json()
        assert data["authenticated"] is True
        assert data["username"] == "dj_test"


class TestLogin:
    def test_not_configured_returns_503(self, monkeypatch):
        monkeypatch.delenv("DISCOGS_CONSUMER_KEY", raising=False)
        monkeypatch.delenv("DISCOGS_CONSUMER_SECRET", raising=False)
        resp = client.get("/api/auth/login")
        assert resp.status_code == 503

    @patch("services.discogs_auth.requests.get")
    def test_returns_authorize_url(self, mock_get, monkeypatch):
        monkeypatch.setenv("DISCOGS_CONSUMER_KEY", "k")
        monkeypatch.setenv("DISCOGS_CONSUMER_SECRET", "s")
        mock_get.return_value.text = "oauth_token=tok&oauth_token_secret=sec&oauth_callback_confirmed=true"
        mock_get.return_value.raise_for_status.return_value = None

        resp = client.get("/api/auth/login")
        assert resp.status_code == 200
        assert "authorize_url" in resp.json()
        assert "oauth_token=tok" in resp.json()["authorize_url"]


class TestCallback:
    @patch("services.discogs_auth.requests.post")
    @patch("services.discogs.requests.get")
    def test_successful_callback(self, mock_identity, mock_post, monkeypatch):
        monkeypatch.setenv("DISCOGS_CONSUMER_KEY", "k")
        monkeypatch.setenv("DISCOGS_CONSUMER_SECRET", "s")

        # Seed pending state
        import services.discogs_auth as mod
        from services.discogs_auth import PendingOAuth

        mod._pending["tok"] = PendingOAuth(
            request_token="tok", request_token_secret="sec"
        )

        mock_post.return_value.text = "oauth_token=access&oauth_token_secret=access_sec"
        mock_post.return_value.raise_for_status.return_value = None

        mock_identity.return_value.json.return_value = {"username": "dj_vinyl"}
        mock_identity.return_value.raise_for_status.return_value = None

        resp = client.get("/api/auth/callback", params={"oauth_token": "tok", "oauth_verifier": "ver"}, follow_redirects=False)
        assert resp.status_code == 307
        assert "localhost:5173" in resp.headers["location"]
        mock_repo.save_oauth_tokens.assert_called_once_with("access", "access_sec", "dj_vinyl")

    def test_invalid_token_returns_400(self):
        resp = client.get("/api/auth/callback", params={"oauth_token": "bad", "oauth_verifier": "v"})
        assert resp.status_code == 400


class TestLogout:
    def test_logout_clears_tokens(self, monkeypatch):
        monkeypatch.setenv("DISCOGS_CONSUMER_KEY", "k")
        monkeypatch.setenv("DISCOGS_CONSUMER_SECRET", "s")
        import services.discogs_auth as mod
        from services.discogs_auth import OAuthTokens

        mod._current_tokens = OAuthTokens(access_token="a", access_token_secret="b")

        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert mod._current_tokens is None
        mock_repo.delete_oauth_tokens.assert_called_once()
