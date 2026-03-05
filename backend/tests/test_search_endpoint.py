"""Integration tests for POST /api/search with telemetry recording.

Every test mocks:
  - LLM API (OpenRouter) via services.vision.requests.post
  - Discogs API via services.discogs.requests.get
  - MongoDB repository via FastAPI dependency override

We verify both the HTTP response AND the SearchRecord saved to the repository.
"""

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repository.models import SearchRecord

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


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def mock_repo():
    """Mock repository that captures saved records."""
    repo = MagicMock()
    repo.saved_records = []

    def capture_save(record):
        repo.saved_records.append(record)

    repo.save_search_record.side_effect = capture_save
    return repo


@pytest.fixture()
def client(mock_repo):
    """FastAPI test client with mocked repository."""
    from deps import get_repo
    from main import app

    app.dependency_overrides[get_repo] = lambda: mock_repo
    yield TestClient(app)
    app.dependency_overrides.clear()


def _make_llm_response(data):
    """Create a mock LLM HTTP response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps(data)}}]
    }
    resp.raise_for_status = MagicMock()
    return resp


def _make_discogs_response(results, pages=1):
    """Create a mock Discogs HTTP response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "results": results,
        "pagination": {"pages": pages},
    }
    resp.raise_for_status = MagicMock()
    return resp


def _upload_file(client, content=b"fake-jpeg-data", content_type="image/jpeg", filename="label.jpg"):
    return client.post(
        "/api/search",
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


# ── Success path ─────────────────────────────────────────────────────────────


def test_success_full_pipeline(client, mock_repo):
    """Happy path: vision → discogs → ranking → success record saved."""
    llm_responses = [
        _make_llm_response(FAKE_LABEL_DATA),
        _make_llm_response(FAKE_RANKING),
    ]
    llm_call_count = 0

    def mock_llm_post(*args, **kwargs):
        nonlocal llm_call_count
        resp = llm_responses[llm_call_count]
        llm_call_count += 1
        return resp

    discogs_resp = _make_discogs_response([FAKE_DISCOGS_RESULT])

    with (
        patch("services.vision.requests.post", side_effect=mock_llm_post),
        patch("services.discogs.requests.get", return_value=discogs_resp),
        patch("services.vision._read_cache", return_value=None),
        patch("services.vision._write_cache"),
    ):
        response = _upload_file(client)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["title"] == "Miles Davis - Kind of Blue"

    # Verify record was saved
    assert mock_repo.save_search_record.call_count == 1
    record: SearchRecord = mock_repo.saved_records[0]
    assert record.status == "success"
    assert record.total_returned == 1
    assert record.top_match_title == "Miles Davis - Kind of Blue"
    assert record.total_duration_ms is not None


# ── Validation errors ────────────────────────────────────────────────────────


def test_invalid_content_type(client, mock_repo):
    """Non-image upload should save error_validation record."""
    response = _upload_file(client, content_type="text/plain", filename="notes.txt")

    assert response.status_code == 400
    assert mock_repo.save_search_record.call_count == 1
    record: SearchRecord = mock_repo.saved_records[0]
    assert record.status == "error_validation"
    assert record.total_duration_ms is not None


def test_file_too_large(client, mock_repo):
    """Oversized file should save error_validation record."""
    huge_content = b"x" * (10 * 1024 * 1024 + 1)  # Just over 10MB
    response = _upload_file(client, content=huge_content)

    assert response.status_code == 413
    assert mock_repo.save_search_record.call_count == 1
    record: SearchRecord = mock_repo.saved_records[0]
    assert record.status == "error_validation"
    assert record.image_size_bytes == len(huge_content)


# ── Vision failure ───────────────────────────────────────────────────────────


def test_vision_api_error(client, mock_repo):
    """Vision API failure should save error record."""
    def mock_llm_fail(*args, **kwargs):
        raise ConnectionError("LLM is down")

    with (
        patch("services.vision.requests.post", side_effect=mock_llm_fail),
        patch("services.vision._read_cache", return_value=None),
    ):
        response = _upload_file(client)

    assert response.status_code == 502
    record: SearchRecord = mock_repo.saved_records[0]
    assert record.status == "error_pipeline"


def test_vision_returns_empty_albums(client, mock_repo):
    """Vision succeeds but returns no albums — should save error_vision."""
    empty_label = {**FAKE_LABEL_DATA, "albums": [], "artists": ["Miles Davis"]}
    llm_resp = _make_llm_response(empty_label)

    with (
        patch("services.vision.requests.post", return_value=llm_resp),
        patch("services.vision._read_cache", return_value=None),
        patch("services.vision._write_cache"),
    ):
        response = _upload_file(client)

    assert response.status_code == 422

    record: SearchRecord = mock_repo.saved_records[0]
    assert record.status == "error_vision"


# ── Discogs failure ──────────────────────────────────────────────────────────


def test_discogs_api_error(client, mock_repo):
    """Discogs failure should save error record."""
    llm_resp = _make_llm_response(FAKE_LABEL_DATA)

    def mock_discogs_fail(*args, **kwargs):
        raise ConnectionError("Discogs is down")

    with (
        patch("services.vision.requests.post", return_value=llm_resp),
        patch("services.discogs.requests.get", side_effect=mock_discogs_fail),
        patch("services.vision._read_cache", return_value=None),
        patch("services.vision._write_cache"),
    ):
        response = _upload_file(client)

    assert response.status_code == 502

    record: SearchRecord = mock_repo.saved_records[0]
    assert record.status == "error_pipeline"


# ── Ranking failure ──────────────────────────────────────────────────────────


def test_ranking_api_error(client, mock_repo):
    """Ranking failure should save error record."""
    llm_call_count = 0

    def mock_llm(*args, **kwargs):
        nonlocal llm_call_count
        llm_call_count += 1
        if llm_call_count == 1:
            return _make_llm_response(FAKE_LABEL_DATA)
        # Second call (ranking) fails
        raise ConnectionError("Ranking LLM is down")

    discogs_resp = _make_discogs_response([FAKE_DISCOGS_RESULT])

    with (
        patch("services.vision.requests.post", side_effect=mock_llm),
        patch("services.discogs.requests.get", return_value=discogs_resp),
        patch("services.vision._read_cache", return_value=None),
        patch("services.vision._write_cache"),
    ):
        response = _upload_file(client)

    assert response.status_code == 502

    record: SearchRecord = mock_repo.saved_records[0]
    assert record.status == "error_pipeline"


# ── Repo failure doesn't break the API ──────────────────────────────────────


def test_repo_save_failure_still_returns_response(client, mock_repo):
    """If MongoDB is down, the API should still return results."""
    mock_repo.save_search_record.side_effect = Exception("MongoDB connection refused")

    llm_responses = [
        _make_llm_response(FAKE_LABEL_DATA),
        _make_llm_response(FAKE_RANKING),
    ]
    llm_call_count = 0

    def mock_llm_post(*args, **kwargs):
        nonlocal llm_call_count
        resp = llm_responses[llm_call_count]
        llm_call_count += 1
        return resp

    discogs_resp = _make_discogs_response([FAKE_DISCOGS_RESULT])

    with (
        patch("services.vision.requests.post", side_effect=mock_llm_post),
        patch("services.discogs.requests.get", return_value=discogs_resp),
        patch("services.vision._read_cache", return_value=None),
        patch("services.vision._write_cache"),
    ):
        response = _upload_file(client)

    # API should still work even if repo fails
    assert response.status_code == 200
    assert response.json()["total"] == 1


# ── No results from Discogs ─────────────────────────────────────────────────


def test_no_discogs_results(client, mock_repo):
    """When Discogs returns empty results, record should reflect that."""
    llm_resp = _make_llm_response(FAKE_LABEL_DATA)
    empty_discogs = _make_discogs_response([])

    with (
        patch("services.vision.requests.post", return_value=llm_resp),
        patch("services.discogs.requests.get", return_value=empty_discogs),
        patch("services.vision._read_cache", return_value=None),
        patch("services.vision._write_cache"),
    ):
        response = _upload_file(client)

    assert response.status_code == 200
    assert response.json()["total"] == 0

    record: SearchRecord = mock_repo.saved_records[0]
    assert record.status == "success"
    assert record.total_returned == 0
