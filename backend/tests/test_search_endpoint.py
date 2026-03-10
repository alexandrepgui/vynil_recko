"""Integration tests for POST /api/search with telemetry recording.

Every test mocks:
  - Supabase JWT via get_current_user dependency override
  - LLM API via services.vision._get_client (provider abstraction layer)
  - Discogs API via services.discogs._session.get
  - MongoDB repository via FastAPI dependency override

We verify both the HTTP response AND the SearchRecord saved to the repository.
"""

import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth import User, get_current_user
from conftest import (
    FAKE_DISCOGS_RESULT,
    FAKE_LABEL_DATA,
    FAKE_RANKING,
    TEST_USER_ID,
    make_discogs_response,
    make_mock_llm_client,
)
from models import SearchStatus
from repository.models import SearchRecord


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def client(mock_repo, mock_jwt_user):
    """FastAPI test client with mocked repository and JWT user."""
    from deps import get_repo
    from main import app

    app.dependency_overrides[get_repo] = lambda: mock_repo
    with patch("services.search.get_repo", return_value=mock_repo):
        yield TestClient(app)
    app.dependency_overrides.pop(get_repo, None)


def _upload_file(client, content=b"fake-jpeg-data", content_type="image/jpeg", filename="label.jpg"):
    return client.post(
        "/api/search",
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


# ── Success path ─────────────────────────────────────────────────────────────


def test_success_full_pipeline(client, mock_repo):
    """Happy path: vision → discogs → ranking → success record saved."""
    mock_client = make_mock_llm_client([FAKE_LABEL_DATA, FAKE_RANKING])
    discogs_resp = make_discogs_response([FAKE_DISCOGS_RESULT])

    with (
        patch("services.vision._get_client", return_value=mock_client),
        patch("services.discogs._session.get", return_value=discogs_resp),
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
    assert record.status == SearchStatus.SUCCESS
    assert record.user_id == TEST_USER_ID
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
    assert record.status == SearchStatus.ERROR_VALIDATION
    assert record.total_duration_ms is not None


def test_pipeline_error_on_llm_failure(client, mock_repo):
    """When the LLM is unreachable, pipeline returns 502 and records error."""
    huge_content = b"x" * 1024
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_client.chat.side_effect = ConnectionError("LLM is down")

    with (
        patch("services.vision._get_client", return_value=mock_client),
        patch("services.vision._read_cache", return_value=None),
    ):
        response = _upload_file(client, content=huge_content)

    assert response.status_code == 502
    assert mock_repo.save_search_record.call_count == 1
    record: SearchRecord = mock_repo.saved_records[0]
    assert record.status == SearchStatus.ERROR_PIPELINE
    assert record.image_size_bytes == len(huge_content)


# ── Vision failure ───────────────────────────────────────────────────────────


def test_vision_api_error(client, mock_repo):
    """Vision API failure should save error record."""
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_client.chat.side_effect = ConnectionError("LLM is down")

    with (
        patch("services.vision._get_client", return_value=mock_client),
        patch("services.vision._read_cache", return_value=None),
    ):
        response = _upload_file(client)

    assert response.status_code == 502
    record: SearchRecord = mock_repo.saved_records[0]
    assert record.status == SearchStatus.ERROR_PIPELINE


def test_vision_returns_empty_albums_triggers_self_titled(client, mock_repo):
    """Vision succeeds with empty albums — self-titled logic kicks in, uses artist as album."""
    empty_label = {**FAKE_LABEL_DATA, "albums": [], "artists": ["Miles Davis"]}
    mock_client = make_mock_llm_client([empty_label, FAKE_RANKING])
    discogs_resp = make_discogs_response([FAKE_DISCOGS_RESULT])

    with (
        patch("services.vision._get_client", return_value=mock_client),
        patch("services.discogs._session.get", return_value=discogs_resp),
        patch("services.vision._read_cache", return_value=None),
        patch("services.vision._write_cache"),
    ):
        response = _upload_file(client)

    # Self-titled logic uses artist name as album, so pipeline succeeds
    assert response.status_code == 200
    data = response.json()
    assert data["label_data"]["albums"] == ["Miles Davis"]


def test_vision_returns_both_empty_raises(client, mock_repo):
    """Vision returns both empty albums and artists — should raise error_vision."""
    empty_label = {**FAKE_LABEL_DATA, "albums": [], "artists": []}
    mock_client = make_mock_llm_client([empty_label])

    with (
        patch("services.vision._get_client", return_value=mock_client),
        patch("services.vision._read_cache", return_value=None),
        patch("services.vision._write_cache"),
    ):
        response = _upload_file(client)

    assert response.status_code == 422

    record: SearchRecord = mock_repo.saved_records[0]
    assert record.status == SearchStatus.ERROR_VISION


# ── Discogs failure ──────────────────────────────────────────────────────────


def test_discogs_api_error(client, mock_repo):
    """Discogs failure should save error record."""
    mock_client = make_mock_llm_client([FAKE_LABEL_DATA])

    def mock_discogs_fail(*args, **kwargs):
        raise ConnectionError("Discogs is down")

    with (
        patch("services.vision._get_client", return_value=mock_client),
        patch("services.discogs._session.get", side_effect=mock_discogs_fail),
        patch("services.vision._read_cache", return_value=None),
        patch("services.vision._write_cache"),
    ):
        response = _upload_file(client)

    assert response.status_code == 502

    record: SearchRecord = mock_repo.saved_records[0]
    assert record.status == SearchStatus.ERROR_PIPELINE


# ── Ranking failure ──────────────────────────────────────────────────────────


def test_ranking_api_error(client, mock_repo):
    """Ranking failure should save error record."""
    from services.llm.base import LLMResponse
    from unittest.mock import MagicMock
    import json

    call_count = 0

    def mock_chat(messages, model=""):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return LLMResponse(
                content=json.dumps(FAKE_LABEL_DATA),
                prompt_tokens=100, completion_tokens=50, total_tokens=150,
                model=model, provider="openrouter",
            )
        # Second call (ranking) fails
        raise ConnectionError("Ranking LLM is down")

    mock_client = MagicMock()
    mock_client.chat = mock_chat

    discogs_resp = make_discogs_response([FAKE_DISCOGS_RESULT])

    with (
        patch("services.vision._get_client", return_value=mock_client),
        patch("services.discogs._session.get", return_value=discogs_resp),
        patch("services.vision._read_cache", return_value=None),
        patch("services.vision._write_cache"),
    ):
        response = _upload_file(client)

    assert response.status_code == 502

    record: SearchRecord = mock_repo.saved_records[0]
    assert record.status == SearchStatus.ERROR_PIPELINE


# ── Repo failure doesn't break the API ──────────────────────────────────────


def test_repo_save_failure_still_returns_response(client, mock_repo):
    """If MongoDB is down, the API should still return results."""
    mock_repo.save_search_record.side_effect = Exception("MongoDB connection refused")

    mock_client = make_mock_llm_client([FAKE_LABEL_DATA, FAKE_RANKING])
    discogs_resp = make_discogs_response([FAKE_DISCOGS_RESULT])

    with (
        patch("services.vision._get_client", return_value=mock_client),
        patch("services.discogs._session.get", return_value=discogs_resp),
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
    mock_client = make_mock_llm_client([FAKE_LABEL_DATA])
    empty_discogs = make_discogs_response([])

    with (
        patch("services.vision._get_client", return_value=mock_client),
        patch("services.discogs._session.get", return_value=empty_discogs),
        patch("services.vision._read_cache", return_value=None),
        patch("services.vision._write_cache"),
    ):
        response = _upload_file(client)

    assert response.status_code == 200
    assert response.json()["total"] == 0

    record: SearchRecord = mock_repo.saved_records[0]
    assert record.status == SearchStatus.SUCCESS
    assert record.total_returned == 0
