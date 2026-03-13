"""Tests for the Discogs OAuth 1.0a authentication service."""

from unittest.mock import MagicMock, patch

import pytest

from services.discogs_auth import (
    OAuthTokens,
    PendingOAuth,
    _build_auth_params,
    _parse_form_body,
    _pending,
    _plaintext_signature,
    _purge_stale_pending,
    build_oauth_headers,
    exchange_verifier,
    get_request_token,
    is_configured,
)

USER_ID = "user-123"


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset module-level state between tests."""
    import services.discogs_auth as mod

    mod._pending.clear()
    yield
    mod._pending.clear()


@pytest.fixture
def _env(monkeypatch):
    monkeypatch.setenv("DISCOGS_CONSUMER_KEY", "test_key")
    monkeypatch.setenv("DISCOGS_CONSUMER_SECRET", "test_secret")


class TestIsConfigured:
    def test_not_configured_when_missing(self, monkeypatch):
        monkeypatch.delenv("DISCOGS_CONSUMER_KEY", raising=False)
        monkeypatch.delenv("DISCOGS_CONSUMER_SECRET", raising=False)
        assert is_configured() is False

    def test_configured_when_set(self, _env):
        assert is_configured() is True


class TestPlaintextSignature:
    def test_without_token_secret(self):
        assert _plaintext_signature("consumer_sec") == "consumer_sec&"

    def test_with_token_secret(self):
        assert _plaintext_signature("consumer_sec", "token_sec") == "consumer_sec&token_sec"


class TestGetRequestToken:
    @patch("services.discogs_auth._auth_session.get")
    def test_success(self, mock_get, _env):
        mock_resp = MagicMock()
        mock_resp.text = "oauth_token=req_tok&oauth_token_secret=req_sec&oauth_callback_confirmed=true"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        token, url = get_request_token(USER_ID, "http://localhost/callback")

        assert token == "req_tok"
        assert "oauth_token=req_tok" in url
        assert "req_tok" in _pending
        assert _pending["req_tok"].request_token_secret == "req_sec"
        assert _pending["req_tok"].user_id == USER_ID

    @patch("services.discogs_auth._auth_session.get")
    def test_propagates_http_error(self, mock_get, _env):
        mock_get.return_value.raise_for_status.side_effect = Exception("401")
        with pytest.raises(Exception, match="401"):
            get_request_token(USER_ID, "http://localhost/callback")


class TestExchangeVerifier:
    @patch("services.discogs_auth._auth_session.post")
    def test_success(self, mock_post, _env):
        # Seed pending state
        _pending["req_tok"] = PendingOAuth(
            user_id=USER_ID,
            request_token="req_tok", request_token_secret="req_sec",
        )

        mock_resp = MagicMock()
        mock_resp.text = "oauth_token=access_tok&oauth_token_secret=access_sec"
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        tokens, returned_user_id = exchange_verifier("req_tok", "verifier_123")

        assert tokens.access_token == "access_tok"
        assert tokens.access_token_secret == "access_sec"
        assert returned_user_id == USER_ID
        assert "req_tok" not in _pending

    def test_missing_pending_raises(self, _env):
        with pytest.raises(ValueError, match="No pending OAuth flow"):
            exchange_verifier("unknown_tok", "verifier")


class TestBuildOAuthHeaders:
    def test_headers_contain_oauth(self, _env):
        tokens = OAuthTokens(access_token="at", access_token_secret="ats")
        headers = build_oauth_headers(tokens)

        assert "Authorization" in headers
        assert "OAuth" in headers["Authorization"]
        assert "at" in headers["Authorization"]


class TestParseFormBody:
    def test_simple(self):
        assert _parse_form_body("a=1&b=2") == {"a": "1", "b": "2"}

    def test_value_with_equals(self):
        assert _parse_form_body("token=abc%3Ddef&secret=xyz") == {
            "token": "abc=def",
            "secret": "xyz",
        }


class TestBuildAuthParams:
    def test_contains_required_keys(self, _env):
        params = _build_auth_params()
        assert "oauth_consumer_key" in params
        assert "oauth_nonce" in params
        assert "oauth_signature" in params
        assert "oauth_signature_method" in params
        assert "oauth_timestamp" in params

    def test_extra_params_included(self, _env):
        params = _build_auth_params(oauth_callback="http://test")
        assert params["oauth_callback"] == "http://test"


class TestPurgeStalePending:
    def test_purges_old_entries(self):
        _pending["old"] = PendingOAuth(
            user_id="u1",
            request_token="old", request_token_secret="s", created_at=0.0,
        )
        _pending["fresh"] = PendingOAuth(
            user_id="u2",
            request_token="fresh", request_token_secret="s",
        )
        _purge_stale_pending()
        assert "old" not in _pending
        assert "fresh" in _pending
