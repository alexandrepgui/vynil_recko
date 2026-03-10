"""Shared fixtures for the backend test suite."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest

from auth import User, get_current_user
from services.llm.base import LLMResponse

# JWT test constants
JWT_SECRET = "test-secret-key"
TEST_USER_ID = "test-user-123"
TEST_USER_EMAIL = "test@example.com"


@pytest.fixture(autouse=True, scope="session")
def _mock_lifespan_repo():
    """Prevent the app lifespan from connecting to a real MongoDB."""
    # No-op: lifespan no longer restores OAuth tokens
    yield


@pytest.fixture()
def mock_jwt_user():
    """Override get_current_user to return a test user (no real JWT needed)."""
    from main import app

    test_user = User(id=TEST_USER_ID, email=TEST_USER_EMAIL)
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield test_user
    app.dependency_overrides.pop(get_current_user, None)


def make_jwt_token(user_id=TEST_USER_ID, email=TEST_USER_EMAIL, secret=JWT_SECRET):
    """Create a valid JWT token for testing."""
    payload = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


def jwt_headers(user_id=TEST_USER_ID, email=TEST_USER_EMAIL, secret=JWT_SECRET):
    """Return Authorization headers with a valid JWT for testing."""
    token = make_jwt_token(user_id, email, secret)
    return {"Authorization": f"Bearer {token}"}


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ── Common test data ──────────────────────────────────────────────────────────

FAKE_LABEL_DATA = {
    "albums": ["Kind of Blue"],
    "artists": ["Miles Davis"],
    "country": "US",
    "format": "LP",
    "label": "Columbia",
    "catno": "CS 8163",
    "year": "1959",
}

FAKE_DISCOGS_RESULT = {
    "id": 123,
    "title": "Miles Davis - Kind of Blue",
    "year": "1959",
    "country": "US",
    "format": ["Vinyl", "LP"],
    "label": ["Columbia"],
    "catno": "CS 8163",
    "uri": "/release/123",
    "cover_image": "https://example.com/cover.jpg",
}

FAKE_RANKING = {"likeliness": [0], "discarded": []}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def sample_image_bytes():
    """Load the sample label JPEG fixture."""
    return (FIXTURES_DIR / "sample_label.jpg").read_bytes()


@pytest.fixture()
def fake_label_data():
    """Return a copy of the standard fake label data."""
    return dict(FAKE_LABEL_DATA)


@pytest.fixture()
def fake_discogs_result():
    """Return a copy of the standard fake Discogs result."""
    return dict(FAKE_DISCOGS_RESULT)


@pytest.fixture()
def mock_repo():
    """Mock repository that captures saved records."""
    repo = MagicMock()
    repo.saved_records = []

    def capture_save(record):
        repo.saved_records.append(record)

    repo.save_search_record.side_effect = capture_save
    # Return valid OAuth tokens by default (Discogs connected)
    repo.load_oauth_tokens.return_value = {
        "access_token": "test-token",
        "access_token_secret": "test-secret",
        "username": "testuser",
    }
    return repo


def make_llm_response(data):
    """Create a mock LLM HTTP response (legacy format for backward compat)."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps(data)}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }
    resp.raise_for_status = MagicMock()
    return resp


def make_llm_client_response(data):
    """Create an LLMResponse from the abstraction layer."""
    return LLMResponse(
        content=json.dumps(data),
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        model="google/gemini-2.5-flash",
        provider="openrouter",
    )


def make_mock_llm_client(responses):
    """Create a mock LLM client that returns LLMResponse objects in sequence.

    Args:
        responses: list of dicts to serialize as JSON responses.
    """
    client = MagicMock()
    client.provider_name = "openrouter"
    call_idx = 0

    def mock_chat(messages, model=""):
        nonlocal call_idx
        data = responses[call_idx]
        call_idx += 1
        return LLMResponse(
            content=json.dumps(data),
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            model=model or "google/gemini-2.5-flash",
            provider="openrouter",
        )

    client.chat = mock_chat
    return client


def make_discogs_response(results, pages=1):
    """Create a mock Discogs HTTP response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"X-Discogs-Ratelimit-Remaining": "50"}
    resp.json.return_value = {
        "results": results,
        "pagination": {"pages": pages},
    }
    resp.raise_for_status = MagicMock()
    return resp
