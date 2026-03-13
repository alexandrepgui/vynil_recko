"""Tests for services.collection_sync."""

from unittest.mock import MagicMock, call, patch

import pytest

from repository.models import CollectionItem
from services.collection_sync import sync_full_collection, _backfill_master_covers, _transform_release
from services.discogs_auth import OAuthTokens


TOKENS = OAuthTokens(access_token="a", access_token_secret="b", username="testuser")
USER_ID = "user-123"


# ── _transform_release ──────────────────────────────────────────────────────


def test_transform_release_basic():
    release = {
        "instance_id": 42,
        "date_added": "2024-01-15T10:00:00-08:00",
        "basic_information": {
            "id": 555,
            "title": "Kind of Blue",
            "artists": [{"name": "Miles Davis"}],
            "year": 1959,
            "genres": ["Jazz"],
            "styles": ["Modal"],
            "formats": [{"name": "LP"}],
            "cover_image": "https://img.discogs.com/cover.jpg",
        },
    }
    item = _transform_release(release, USER_ID)
    assert item.user_id == USER_ID
    assert item.instance_id == 42
    assert item.release_id == 555
    assert item.title == "Kind of Blue"
    assert item.artist == "Miles Davis"
    assert item.year == 1959
    assert item.genres == ["Jazz"]
    assert item.styles == ["Modal"]
    assert item.format == "LP"
    assert item.cover_image == "https://img.discogs.com/cover.jpg"
    assert item.date_added == "2024-01-15T10:00:00-08:00"


def test_transform_release_multiple_artists():
    release = {
        "instance_id": 1,
        "basic_information": {
            "id": 10,
            "title": "Collab",
            "artists": [{"name": "A"}, {"name": "B"}],
            "year": 2000,
            "genres": [],
            "styles": [],
            "formats": [],
        },
    }
    item = _transform_release(release, USER_ID)
    assert item.artist == "A, B"
    assert item.format == ""
    assert item.cover_image is None


def test_transform_release_thumb_fallback():
    release = {
        "instance_id": 1,
        "basic_information": {
            "id": 10,
            "title": "X",
            "artists": [],
            "year": 0,
            "genres": [],
            "styles": [],
            "formats": [{"name": "CD"}],
            "thumb": "https://img.discogs.com/thumb.jpg",
        },
    }
    item = _transform_release(release, USER_ID)
    assert item.cover_image == "https://img.discogs.com/thumb.jpg"


# ── sync_full_collection ────────────────────────────────────────────────────


def _make_page(releases, page=1, pages=1, items=None):
    if items is None:
        items = len(releases)
    return {
        "releases": releases,
        "pagination": {"pages": pages, "items": items},
    }


def _simple_release(instance_id):
    return {
        "instance_id": instance_id,
        "basic_information": {
            "id": instance_id * 10,
            "title": f"Title {instance_id}",
            "artists": [{"name": "Artist"}],
            "year": 2020,
            "genres": ["Rock"],
            "styles": [],
            "formats": [{"name": "LP"}],
        },
    }


@patch("services.collection_sync.get_collection")
@patch("services.collection_sync.time.sleep")
def test_sync_single_page(mock_sleep, mock_get_collection):
    mock_get_collection.return_value = _make_page([_simple_release(1), _simple_release(2)])
    repo = MagicMock()
    repo.delete_stale_items.return_value = 0

    result = sync_full_collection(repo, USER_ID, TOKENS)

    assert result["synced"] == 2
    assert result["removed"] == 0
    repo.upsert_collection_items_bulk.assert_called_once()
    repo.delete_stale_items.assert_called_once()
    # Status updated: syncing -> progress -> idle
    assert repo.update_sync_status.call_count >= 2
    mock_sleep.assert_not_called()


@patch("services.collection_sync.get_collection")
@patch("services.collection_sync.time.sleep")
def test_sync_multiple_pages(mock_sleep, mock_get_collection):
    mock_get_collection.side_effect = [
        _make_page([_simple_release(1)], page=1, pages=2, items=2),
        _make_page([_simple_release(2)], page=2, pages=2, items=2),
    ]
    repo = MagicMock()
    repo.delete_stale_items.return_value = 1

    result = sync_full_collection(repo, USER_ID, TOKENS)

    assert result["synced"] == 2
    assert result["removed"] == 1
    assert mock_get_collection.call_count == 2
    mock_sleep.assert_called_once_with(1)


@patch("services.collection_sync.get_collection")
def test_sync_empty_collection(mock_get_collection):
    mock_get_collection.return_value = {"releases": [], "pagination": {}}
    repo = MagicMock()
    repo.delete_stale_items.return_value = 0

    result = sync_full_collection(repo, USER_ID, TOKENS)

    assert result["synced"] == 0
    assert result["removed"] == 0


@patch("services.collection_sync.get_collection")
def test_sync_error_updates_status(mock_get_collection):
    mock_get_collection.side_effect = RuntimeError("API down")
    repo = MagicMock()

    with pytest.raises(RuntimeError, match="API down"):
        sync_full_collection(repo, USER_ID, TOKENS)

    # Should have set status to "syncing" then "error"
    error_call = repo.update_sync_status.call_args_list[-1]
    assert error_call[0][1]["status"] == "error"
    assert "API down" in error_call[0][1]["error"]


# ── _backfill_master_covers ─────────────────────────────────────────────────


def _make_item(cover_image=None, master_id=None):
    return CollectionItem(
        user_id=USER_ID,
        instance_id=1,
        release_id=100,
        title="Test",
        artist="Artist",
        year=2020,
        cover_image=cover_image,
        master_id=master_id,
    )


@patch("services.collection_sync.get_master_cover")
@patch("services.collection_sync.time.sleep")
def test_backfill_fills_missing_cover(mock_sleep, mock_get_master_cover):
    mock_get_master_cover.return_value = "https://img.discogs.com/master.jpg"
    items = [_make_item(cover_image=None, master_id=999)]
    cache: dict[int, str | None] = {}

    _backfill_master_covers(items, TOKENS, cache)

    assert items[0].cover_image == "https://img.discogs.com/master.jpg"
    assert cache[999] == "https://img.discogs.com/master.jpg"
    mock_get_master_cover.assert_called_once_with(999, TOKENS)


@patch("services.collection_sync.get_master_cover")
@patch("services.collection_sync.time.sleep")
def test_backfill_prefers_master_cover_over_existing(mock_sleep, mock_get_master_cover):
    mock_get_master_cover.return_value = "https://img.discogs.com/master.jpg"
    items = [_make_item(cover_image="https://existing.jpg", master_id=999)]
    cache: dict[int, str | None] = {}

    _backfill_master_covers(items, TOKENS, cache)

    assert items[0].cover_image == "https://img.discogs.com/master.jpg"
    mock_get_master_cover.assert_called_once_with(999, TOKENS)


@patch("services.collection_sync.get_master_cover")
@patch("services.collection_sync.time.sleep")
def test_backfill_uses_cache(mock_sleep, mock_get_master_cover):
    items = [
        _make_item(cover_image=None, master_id=999),
        _make_item(cover_image=None, master_id=999),
    ]
    cache: dict[int, str | None] = {}
    mock_get_master_cover.return_value = "https://img.discogs.com/cached.jpg"

    _backfill_master_covers(items, TOKENS, cache)

    # Only fetched once despite two items needing the same master
    mock_get_master_cover.assert_called_once()
    assert items[0].cover_image == "https://img.discogs.com/cached.jpg"
    assert items[1].cover_image == "https://img.discogs.com/cached.jpg"


@patch("services.collection_sync.get_master_cover")
@patch("services.collection_sync.time.sleep")
def test_backfill_skips_items_without_master_id(mock_sleep, mock_get_master_cover):
    items = [_make_item(cover_image=None, master_id=None)]
    cache: dict[int, str | None] = {}

    _backfill_master_covers(items, TOKENS, cache)

    mock_get_master_cover.assert_not_called()
