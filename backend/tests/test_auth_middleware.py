"""Tests for JWT authentication middleware."""

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from auth import User, get_current_user, _jwks_client

USER_ID = "123e4567-e89b-12d3-a456-426614174000"
USER_EMAIL = "test@example.com"

# Generate a test EC key pair for ES256
_private_key = ec.generate_private_key(ec.SECP256R1())
_public_key = _private_key.public_key()


def _make_jwt(payload=None, key=_private_key, algorithm="ES256"):
    """Create a JWT token for testing."""
    default = {
        "sub": USER_ID,
        "email": USER_EMAIL,
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    if payload:
        default.update(payload)
    return jwt.encode(default, key, algorithm=algorithm, headers={"kid": "test-key-id"})


@pytest.fixture(autouse=True)
def _mock_jwks(monkeypatch):
    """Mock the JWKS client to return our test public key."""
    import auth
    mock_signing_key = MagicMock()
    mock_signing_key.key = _public_key
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
    monkeypatch.setattr(auth, "_jwks_client", mock_client)
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")


@pytest.fixture()
def app():
    test_app = FastAPI()

    @test_app.get("/test")
    async def test_endpoint(user: User = Depends(get_current_user)):
        return {"id": user.id, "email": user.email}

    return test_app


@pytest.fixture()
def client(app):
    return TestClient(app)


class TestGetCurrentUser:
    def test_valid_token(self, client):
        token = _make_jwt()
        resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["id"] == USER_ID
        assert resp.json()["email"] == USER_EMAIL

    def test_missing_token(self, client):
        resp = client.get("/test")
        assert resp.status_code in (401, 403)

    def test_expired_token(self, client):
        token = _make_jwt({"exp": int(time.time()) - 100})
        resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
        assert "expired" in resp.json()["detail"].lower()

    def test_invalid_signature(self, client):
        """Token signed with a different key should fail."""
        other_key = ec.generate_private_key(ec.SECP256R1())
        token = _make_jwt(key=other_key)
        resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_missing_supabase_url(self, client, monkeypatch):
        """When no SUPABASE_URL is set and JWKS client isn't cached, return 500."""
        import auth
        monkeypatch.setattr(auth, "_jwks_client", None)
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("VITE_SUPABASE_URL", raising=False)
        token = _make_jwt()
        resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 500

    def test_wrong_audience(self, client):
        token = _make_jwt({"aud": "anon"})
        resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_missing_sub_claim(self, client):
        payload = {
            "email": USER_EMAIL,
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, _private_key, algorithm="ES256", headers={"kid": "test-key-id"})
        resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
