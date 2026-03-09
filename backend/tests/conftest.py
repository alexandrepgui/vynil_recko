"""Shared fixtures for the backend test suite."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.llm.base import LLMResponse


@pytest.fixture(autouse=True, scope="session")
def _mock_lifespan_repo():
    """Prevent the app lifespan from connecting to a real MongoDB."""
    with patch("main.get_repo", return_value=MagicMock()):
        yield

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
