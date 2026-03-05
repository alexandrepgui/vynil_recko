"""Tests for the disk-based LRU cache in services.vision."""

import hashlib
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend/ is on sys.path so bare imports (config, services.vision) resolve.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.vision import (
    _cache_path,
    _evict_if_needed,
    _read_cache,
    _write_cache,
    read_label_image,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE_LABEL = FIXTURES / "sample_label.jpg"

FAKE_LABEL_DATA = {
    "albums": ["Kind of Blue"],
    "artists": ["Miles Davis"],
    "country": "US",
    "format": "LP",
    "label": "Columbia",
    "catno": "CS 8163",
    "year": "1959",
}


@pytest.fixture()
def image_bytes():
    return SAMPLE_LABEL.read_bytes()


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Redirect CACHE_DIR and CACHE_MAX_ENTRIES to a temp dir for every test."""
    monkeypatch.setattr("services.vision.CACHE_DIR", str(tmp_path))
    monkeypatch.setattr("services.vision.CACHE_MAX_ENTRIES", 200)
    return tmp_path


# ── _cache_path ──────────────────────────────────────────────────────────────


def test_cache_path_deterministic(image_bytes, isolated_cache):
    p1 = _cache_path(image_bytes)
    p2 = _cache_path(image_bytes)
    assert p1 == p2


def test_cache_path_uses_sha256(image_bytes, isolated_cache):
    expected = hashlib.sha256(image_bytes).hexdigest() + ".json"
    assert _cache_path(image_bytes).name == expected


def test_cache_path_different_for_different_images(isolated_cache):
    assert _cache_path(b"image_a") != _cache_path(b"image_b")


# ── _read_cache / _write_cache ───────────────────────────────────────────────


def test_cache_miss_returns_none(image_bytes):
    assert _read_cache(image_bytes) is None


def test_write_then_read(image_bytes):
    _write_cache(image_bytes, FAKE_LABEL_DATA)
    result = _read_cache(image_bytes)
    assert result == FAKE_LABEL_DATA


def test_read_bumps_mtime(image_bytes):
    _write_cache(image_bytes, FAKE_LABEL_DATA)
    path = _cache_path(image_bytes)
    old_mtime = path.stat().st_mtime
    time.sleep(0.05)
    _read_cache(image_bytes)
    assert path.stat().st_mtime >= old_mtime


def test_corrupted_cache_returns_none(image_bytes):
    _write_cache(image_bytes, FAKE_LABEL_DATA)
    path = _cache_path(image_bytes)
    path.write_text("NOT VALID JSON {{{")
    assert _read_cache(image_bytes) is None


# ── _evict_if_needed ─────────────────────────────────────────────────────────


def test_eviction_removes_oldest(isolated_cache, monkeypatch):
    monkeypatch.setattr("services.vision.CACHE_MAX_ENTRIES", 3)

    # Write 3 entries with staggered mtimes
    for i in range(3):
        data = {"albums": [f"album_{i}"], "artists": [f"artist_{i}"]}
        _write_cache(f"img_{i}".encode(), data)
        time.sleep(0.05)

    # Cache is full (3 entries). Writing a 4th should evict the oldest.
    _write_cache(b"img_3", {"albums": ["album_3"], "artists": ["artist_3"]})

    remaining = list(isolated_cache.glob("*.json"))
    assert len(remaining) == 3  # max 3, oldest evicted

    # The oldest (img_0) should be gone
    assert _read_cache(b"img_0") is None
    # Newest should exist
    assert _read_cache(b"img_3") is not None


# ── read_label_image integration ─────────────────────────────────────────────


def test_read_label_image_calls_llm_on_miss(image_bytes):
    """First call should hit the LLM and write to cache."""
    llm_response = json.dumps(FAKE_LABEL_DATA)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": llm_response}}]
    }

    with patch("services.vision.requests.post", return_value=mock_resp) as mock_post:
        label_data, messages, cache_hit = read_label_image(image_bytes, "image/jpeg")

    assert label_data == FAKE_LABEL_DATA
    assert cache_hit is False
    assert mock_post.call_count == 1
    # Should now be cached
    assert _read_cache(image_bytes) == FAKE_LABEL_DATA


def test_read_label_image_uses_cache_on_hit(image_bytes):
    """Second call with same image should skip the LLM entirely."""
    _write_cache(image_bytes, FAKE_LABEL_DATA)

    with patch("services.vision.requests.post") as mock_post:
        label_data, messages, cache_hit = read_label_image(image_bytes, "image/jpeg")

    assert label_data == FAKE_LABEL_DATA
    assert cache_hit is True
    mock_post.assert_not_called()


def test_cached_response_has_valid_conversation(image_bytes):
    """Cached path should still return a 2-message conversation for rank_results."""
    _write_cache(image_bytes, FAKE_LABEL_DATA)

    with patch("services.vision.requests.post") as mock_post:
        _, messages, cache_hit = read_label_image(image_bytes, "image/jpeg")

    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    # Assistant content should be parseable back to label data
    assert json.loads(messages[1]["content"]) == FAKE_LABEL_DATA
