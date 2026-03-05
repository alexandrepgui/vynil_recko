"""Tests for repository models and MongoDB repository."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repository.models import SearchRecord


# ── SearchRecord serialization ───────────────────────────────────────────────


def _make_record(**overrides) -> SearchRecord:
    defaults = dict(
        request_id="test-uuid-123",
        timestamp="2026-03-02T12:00:00+00:00",
        status="success",
        image_filename="label.jpg",
        image_size_bytes=50_000,
        total_returned=7,
        top_match_title="Miles Davis - Kind of Blue",
        total_duration_ms=4200.0,
    )
    defaults.update(overrides)
    return SearchRecord(**defaults)


def test_to_dict_roundtrip():
    record = _make_record()

    d = record.to_dict()
    restored = SearchRecord.from_dict(d)

    assert restored.request_id == record.request_id
    assert restored.status == "success"
    assert restored.total_returned == 7
    assert restored.top_match_title == "Miles Davis - Kind of Blue"
    assert restored.total_duration_ms == 4200.0


def test_default_values():
    record = SearchRecord()
    assert record.status == "pending"
    assert record.total_returned == 0
    assert record.top_match_title is None
    assert record.request_id  # should be auto-generated


def test_error_record_serializes():
    record = _make_record(status="error_vision")

    d = record.to_dict()
    assert d["status"] == "error_vision"
    assert d["total_returned"] == 7


def test_from_dict_with_partial_data():
    """Simulates loading a record where some steps didn't execute."""
    data = {
        "request_id": "abc",
        "timestamp": "2026-03-02T00:00:00+00:00",
        "status": "error_pipeline",
        "image_filename": "test.png",
        "image_size_bytes": 1000,
        "total_returned": 0,
        "top_match_title": None,
        "total_duration_ms": 700.0,
    }
    record = SearchRecord.from_dict(data)
    assert record.status == "error_pipeline"
    assert record.total_returned == 0
    assert record.total_duration_ms == 700.0


# ── MongoRepository ──────────────────────────────────────────────────────────


def _make_mock_repo():
    """Create a MongoRepository with mocked MongoClient."""
    with patch("repository.mongo.MongoClient") as MockClient:
        mock_db = MagicMock()
        MockClient.return_value.__getitem__.return_value = mock_db
        collections = {}

        def getitem(name):
            if name not in collections:
                collections[name] = MagicMock()
            return collections[name]

        mock_db.__getitem__.side_effect = getitem

        from repository.mongo import MongoRepository

        repo = MongoRepository(uri="mongodb://fake:27017", database="test_db")
        return repo, collections


def test_mongo_save_calls_replace_one():
    repo, cols = _make_mock_repo()
    record = _make_record()
    repo.save_search_record(record)

    mock_col = cols["search_records"]
    mock_col.replace_one.assert_called_once()
    call_args = mock_col.replace_one.call_args
    assert call_args[0][0] == {"request_id": "test-uuid-123"}
    assert call_args[0][1]["status"] == "success"
    assert call_args[1]["upsert"] is True


def test_mongo_find_by_id_returns_record():
    repo, cols = _make_mock_repo()
    mock_col = cols["search_records"]
    record = _make_record()
    mock_col.find_one.return_value = record.to_dict()

    result = repo.find_search_record("test-uuid-123")
    assert result is not None
    assert result.request_id == "test-uuid-123"
    mock_col.find_one.assert_called_once_with({"request_id": "test-uuid-123"}, {"_id": 0})


def test_mongo_find_by_id_returns_none():
    repo, cols = _make_mock_repo()
    mock_col = cols["search_records"]
    mock_col.find_one.return_value = None

    assert repo.find_search_record("nonexistent") is None


def test_mongo_count():
    repo, cols = _make_mock_repo()
    mock_col = cols["search_records"]
    mock_col.count_documents.return_value = 42

    assert repo.count_search_records() == 42
    mock_col.count_documents.assert_called_once_with({})
