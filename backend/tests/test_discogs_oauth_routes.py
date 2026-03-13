"""Tests for the Discogs OAuth routes (/api/discogs/*)."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from conftest import TEST_USER_ID
from routes.discogs_oauth import validate_redirect_url


@pytest.fixture(autouse=True)
def _clean_pending():
    import services.discogs_auth as mod

    mod._pending.clear()
    yield
    mod._pending.clear()


@pytest.fixture()
def client(mock_jwt_user):
    from deps import get_repo
    from main import app

    mock_repo = MagicMock()
    mock_repo.load_oauth_tokens.return_value = None
    app.dependency_overrides[get_repo] = lambda: mock_repo
    yield TestClient(app), mock_repo
    app.dependency_overrides.pop(get_repo, None)


class TestDiscogsStatus:
    def test_not_configured(self, client, monkeypatch):
        test_client, mock_repo = client
        monkeypatch.delenv("DISCOGS_CONSUMER_KEY", raising=False)
        monkeypatch.delenv("DISCOGS_CONSUMER_SECRET", raising=False)
        resp = test_client.get("/api/discogs/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["oauth_configured"] is False
        assert data["authenticated"] is False

    def test_configured_not_authenticated(self, client, monkeypatch):
        test_client, mock_repo = client
        monkeypatch.setenv("DISCOGS_CONSUMER_KEY", "k")
        monkeypatch.setenv("DISCOGS_CONSUMER_SECRET", "s")
        resp = test_client.get("/api/discogs/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["oauth_configured"] is True
        assert data["authenticated"] is False

    def test_authenticated(self, client, monkeypatch):
        test_client, mock_repo = client
        monkeypatch.setenv("DISCOGS_CONSUMER_KEY", "k")
        monkeypatch.setenv("DISCOGS_CONSUMER_SECRET", "s")
        mock_repo.load_oauth_tokens.return_value = {
            "access_token": "a", "access_token_secret": "b", "username": "dj_test",
        }
        resp = test_client.get("/api/discogs/status")
        data = resp.json()
        assert data["authenticated"] is True
        assert data["username"] == "dj_test"


class TestDiscogsLogin:
    def test_not_configured_returns_503(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.delenv("DISCOGS_CONSUMER_KEY", raising=False)
        monkeypatch.delenv("DISCOGS_CONSUMER_SECRET", raising=False)
        resp = test_client.get("/api/discogs/login")
        assert resp.status_code == 503

    @patch("services.discogs_auth._auth_session.get")
    def test_returns_authorize_url(self, mock_get, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setenv("DISCOGS_CONSUMER_KEY", "k")
        monkeypatch.setenv("DISCOGS_CONSUMER_SECRET", "s")
        mock_get.return_value.text = "oauth_token=tok&oauth_token_secret=sec&oauth_callback_confirmed=true"
        mock_get.return_value.raise_for_status.return_value = None

        resp = test_client.get("/api/discogs/login")
        assert resp.status_code == 200
        assert "authorize_url" in resp.json()
        assert "oauth_token=tok" in resp.json()["authorize_url"]


class TestDiscogsCallback:
    @patch("services.discogs_auth._auth_session.post")
    @patch("services.discogs._session.get")
    def test_successful_callback(self, mock_identity, mock_post, client, monkeypatch):
        test_client, mock_repo = client
        monkeypatch.setenv("DISCOGS_CONSUMER_KEY", "k")
        monkeypatch.setenv("DISCOGS_CONSUMER_SECRET", "s")

        # Seed pending state with user_id
        import services.discogs_auth as mod
        from services.discogs_auth import PendingOAuth

        mod._pending["tok"] = PendingOAuth(
            user_id=TEST_USER_ID,
            request_token="tok", request_token_secret="sec",
        )

        mock_post.return_value.text = "oauth_token=access&oauth_token_secret=access_sec"
        mock_post.return_value.raise_for_status.return_value = None

        mock_identity.return_value.json.return_value = {"username": "dj_vinyl"}
        mock_identity.return_value.raise_for_status.return_value = None

        resp = test_client.get("/api/discogs/callback", params={"oauth_token": "tok", "oauth_verifier": "ver"}, follow_redirects=False)
        assert resp.status_code == 307
        assert "localhost:5173" in resp.headers["location"]
        mock_repo.save_oauth_tokens.assert_called_once_with(TEST_USER_ID, "access", "access_sec", "dj_vinyl")

    def test_invalid_token_returns_400(self, client):
        test_client, _ = client
        resp = test_client.get("/api/discogs/callback", params={"oauth_token": "bad", "oauth_verifier": "v"})
        assert resp.status_code == 400


class TestDiscogsLogout:
    def test_logout_deletes_tokens(self, client):
        test_client, mock_repo = client
        resp = test_client.post("/api/discogs/logout")
        assert resp.status_code == 200
        mock_repo.delete_oauth_tokens.assert_called_once_with(TEST_USER_ID)


# ── validate_redirect_url unit tests ────────────────────────────────────────


class TestValidateRedirectUrl:
    """Tests for the redirect URL validation helper."""

    HOSTS = {"localhost", "127.0.0.1"}

    def test_https_allowed_host(self):
        assert validate_redirect_url("https://localhost/path", self.HOSTS) is True

    def test_https_disallowed_host(self):
        assert validate_redirect_url("https://evil.com/path", self.HOSTS) is False

    def test_http_rejected_by_default(self):
        assert validate_redirect_url("http://localhost:5173", self.HOSTS) is False

    def test_http_allowed_when_flag_set(self):
        assert validate_redirect_url("http://localhost:5173", self.HOSTS, allow_http=True) is True

    def test_http_disallowed_host_even_with_flag(self):
        assert validate_redirect_url("http://evil.com", self.HOSTS, allow_http=True) is False

    def test_ftp_scheme_rejected(self):
        assert validate_redirect_url("ftp://localhost/file", self.HOSTS, allow_http=True) is False

    def test_empty_string(self):
        assert validate_redirect_url("", self.HOSTS, allow_http=True) is False

    def test_no_scheme(self):
        assert validate_redirect_url("localhost:5173", self.HOSTS, allow_http=True) is False

    def test_javascript_scheme(self):
        assert validate_redirect_url("javascript:alert(1)", self.HOSTS, allow_http=True) is False

    def test_ip_address_allowed(self):
        assert validate_redirect_url("http://127.0.0.1:5173", self.HOSTS, allow_http=True) is True


# ── Redirect validation integration tests ───────────────────────────────────


class TestCallbackRedirectValidation:
    """The /callback endpoint should fall back to the default URL when FRONTEND_URL is invalid."""

    @patch("services.discogs_auth._auth_session.post")
    @patch("services.discogs._session.get")
    def test_invalid_frontend_url_falls_back(self, mock_identity, mock_post, client, monkeypatch):
        test_client, mock_repo = client
        monkeypatch.setenv("DISCOGS_CONSUMER_KEY", "k")
        monkeypatch.setenv("DISCOGS_CONSUMER_SECRET", "s")
        monkeypatch.setenv("FRONTEND_URL", "ftp://evil.com")

        import services.discogs_auth as mod
        from services.discogs_auth import PendingOAuth

        mod._pending["tok"] = PendingOAuth(
            user_id=TEST_USER_ID,
            request_token="tok", request_token_secret="sec",
        )

        mock_post.return_value.text = "oauth_token=access&oauth_token_secret=access_sec"
        mock_post.return_value.raise_for_status.return_value = None

        mock_identity.return_value.json.return_value = {"username": "dj_vinyl"}
        mock_identity.return_value.raise_for_status.return_value = None

        resp = test_client.get(
            "/api/discogs/callback",
            params={"oauth_token": "tok", "oauth_verifier": "ver"},
            follow_redirects=False,
        )
        assert resp.status_code == 307
        # Should fall back to default localhost URL
        assert "localhost:5173" in resp.headers["location"]

    @patch("services.discogs_auth._auth_session.post")
    @patch("services.discogs._session.get")
    def test_valid_frontend_url_used(self, mock_identity, mock_post, client, monkeypatch):
        test_client, mock_repo = client
        monkeypatch.setenv("DISCOGS_CONSUMER_KEY", "k")
        monkeypatch.setenv("DISCOGS_CONSUMER_SECRET", "s")
        monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")

        import services.discogs_auth as mod
        from services.discogs_auth import PendingOAuth

        mod._pending["tok"] = PendingOAuth(
            user_id=TEST_USER_ID,
            request_token="tok", request_token_secret="sec",
        )

        mock_post.return_value.text = "oauth_token=access&oauth_token_secret=access_sec"
        mock_post.return_value.raise_for_status.return_value = None

        mock_identity.return_value.json.return_value = {"username": "dj_vinyl"}
        mock_identity.return_value.raise_for_status.return_value = None

        resp = test_client.get(
            "/api/discogs/callback",
            params={"oauth_token": "tok", "oauth_verifier": "ver"},
            follow_redirects=False,
        )
        assert resp.status_code == 307
        assert "localhost:3000" in resp.headers["location"]


class TestLoginCallbackUrlValidation:
    """The /login endpoint should fall back when OAUTH_CALLBACK_URL is invalid."""

    @patch("services.discogs_auth._auth_session.get")
    def test_invalid_callback_url_falls_back_to_auto(self, mock_get, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setenv("DISCOGS_CONSUMER_KEY", "k")
        monkeypatch.setenv("DISCOGS_CONSUMER_SECRET", "s")
        monkeypatch.setenv("OAUTH_CALLBACK_URL", "javascript:alert(1)")

        mock_get.return_value.text = "oauth_token=tok&oauth_token_secret=sec&oauth_callback_confirmed=true"
        mock_get.return_value.raise_for_status.return_value = None

        resp = test_client.get("/api/discogs/login")
        assert resp.status_code == 200
        assert "authorize_url" in resp.json()

    @patch("services.discogs_auth._auth_session.get")
    def test_valid_callback_url_used(self, mock_get, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setenv("DISCOGS_CONSUMER_KEY", "k")
        monkeypatch.setenv("DISCOGS_CONSUMER_SECRET", "s")
        monkeypatch.setenv("OAUTH_CALLBACK_URL", "http://localhost:8000/api/discogs/callback")

        mock_get.return_value.text = "oauth_token=tok&oauth_token_secret=sec&oauth_callback_confirmed=true"
        mock_get.return_value.raise_for_status.return_value = None

        resp = test_client.get("/api/discogs/login")
        assert resp.status_code == 200
        assert "authorize_url" in resp.json()
