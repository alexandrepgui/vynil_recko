"""Unit tests for MongoRepository using mocked pymongo collections."""

from unittest.mock import MagicMock, patch

import pytest

from repository import Batch, BatchItem, CollectionRecord, SearchRecord
from repository.mongo import MongoRepository


@pytest.fixture()
def repo():
    with patch("repository.mongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_client.return_value.__getitem__ = MagicMock(return_value=mock_db)
        r = MongoRepository(uri="mongodb://fake", database="testdb")
        # Expose internal collections for assertions
        r._search_col = r._search_records
        r._collection_col = r._collection_records
        r._batches_col = r._batches
        r._items_col = r._items
        return r


# ── Search records ───────────────────────────────────────────────────────────


def test_save_search_record(repo):
    record = SearchRecord(request_id="r1", status="success")
    repo.save_search_record(record)
    repo._search_records.replace_one.assert_called_once()
    call_args = repo._search_records.replace_one.call_args
    assert call_args[0][0] == {"request_id": "r1"}
    assert call_args[1]["upsert"] is True


def test_find_search_record_found(repo):
    repo._search_records.find_one.return_value = {
        "request_id": "r1", "status": "success", "timestamp": "2024-01-01",
    }
    result = repo.find_search_record("r1")
    assert result is not None
    assert result.request_id == "r1"


def test_find_search_record_not_found(repo):
    repo._search_records.find_one.return_value = None
    assert repo.find_search_record("nope") is None


def test_find_all_search_records(repo):
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = [
        {"request_id": "r1", "status": "success", "timestamp": "t1"},
    ]
    repo._search_records.find.return_value = cursor
    results = repo.find_all_search_records(limit=10, skip=0)
    assert len(results) == 1


def test_count_search_records(repo):
    repo._search_records.count_documents.return_value = 42
    assert repo.count_search_records() == 42


# ── Collection records ───────────────────────────────────────────────────────


def test_save_collection_record(repo):
    record = CollectionRecord(record_id="c1", release_id=123)
    repo.save_collection_record(record)
    repo._collection_records.replace_one.assert_called_once()


# ── Batches ──────────────────────────────────────────────────────────────────


def test_save_batch(repo):
    batch = Batch(batch_id="b1", total_images=5)
    repo.save_batch(batch)
    repo._batches.replace_one.assert_called_once()


def test_find_batch_found(repo):
    repo._batches.find_one.return_value = {"batch_id": "b1", "status": "processing"}
    result = repo.find_batch("b1")
    assert result is not None
    assert result.batch_id == "b1"


def test_find_batch_not_found(repo):
    repo._batches.find_one.return_value = None
    assert repo.find_batch("nope") is None


def test_update_batch_status(repo):
    repo.update_batch_status("b1", "completed")
    repo._batches.update_one.assert_called_once_with(
        {"batch_id": "b1"}, {"$set": {"status": "completed"}}
    )


def test_increment_batch_processed(repo):
    repo.increment_batch_processed("b1")
    repo._batches.update_one.assert_called_once_with(
        {"batch_id": "b1"}, {"$inc": {"processed": 1}}
    )


def test_increment_batch_failed(repo):
    repo.increment_batch_failed("b1")
    repo._batches.update_one.assert_called_once_with(
        {"batch_id": "b1"}, {"$inc": {"failed": 1}}
    )


# ── Batch items ──────────────────────────────────────────────────────────────


def test_save_item(repo):
    item = BatchItem(item_id="i1", batch_id="b1")
    repo.save_item(item)
    repo._items.replace_one.assert_called_once()


def test_find_item_found(repo):
    repo._items.find_one.return_value = {"item_id": "i1", "batch_id": "b1"}
    result = repo.find_item("i1")
    assert result is not None
    assert result.item_id == "i1"


def test_find_item_not_found(repo):
    repo._items.find_one.return_value = None
    assert repo.find_item("nope") is None


def test_find_items_by_batch(repo):
    cursor = MagicMock()
    cursor.sort.return_value = [{"item_id": "i1", "batch_id": "b1"}]
    repo._items.find.return_value = cursor
    results = repo.find_items_by_batch("b1")
    assert len(results) == 1


def test_find_items_by_batch_with_review_filter(repo):
    cursor = MagicMock()
    cursor.sort.return_value = []
    repo._items.find.return_value = cursor
    repo.find_items_by_batch("b1", review_status="accepted")
    query = repo._items.find.call_args[0][0]
    assert query["review_status"] == "accepted"


def test_find_all_items(repo):
    cursor = MagicMock()
    cursor.sort.return_value = [{"item_id": "i1", "batch_id": "b1"}]
    repo._items.find.return_value = cursor
    results = repo.find_all_items()
    assert len(results) == 1


def test_find_all_items_with_filter(repo):
    cursor = MagicMock()
    cursor.sort.return_value = []
    repo._items.find.return_value = cursor
    repo.find_all_items(review_status="skipped")
    query = repo._items.find.call_args[0][0]
    assert query["review_status"] == "skipped"


def test_update_item_status(repo):
    repo.update_item_status("i1", "processing")
    repo._items.update_one.assert_called_once_with(
        {"item_id": "i1"}, {"$set": {"status": "processing"}}
    )


def test_update_item_completed(repo):
    repo.update_item_completed("i1", label_data={"a": 1}, results=[{"b": 2}], strategy="s1")
    call = repo._items.update_one.call_args
    assert call[0][0] == {"item_id": "i1"}
    update = call[0][1]["$set"]
    assert update["status"] == "completed"
    assert update["label_data"] == {"a": 1}
    assert "debug" not in update


def test_update_item_completed_with_debug(repo):
    repo.update_item_completed("i1", label_data={}, results=[], strategy="s1", debug={"x": 1})
    update = repo._items.update_one.call_args[0][1]["$set"]
    assert update["debug"] == {"x": 1}


def test_update_item_error(repo):
    repo.update_item_error("i1", "something broke")
    call = repo._items.update_one.call_args
    update = call[0][1]["$set"]
    assert update["status"] == "error"
    assert update["error"] == "something broke"


def test_update_item_review(repo):
    repo.update_item_review("i1", "accepted", 456)
    call = repo._items.update_one.call_args
    update = call[0][1]["$set"]
    assert update["review_status"] == "accepted"
    assert update["accepted_release_id"] == 456


# ── Collection items (persisted Discogs collection) ─────────────────────────


def test_upsert_collection_items_bulk_empty(repo):
    assert repo.upsert_collection_items_bulk([]) == 0
    repo._collection_items.bulk_write.assert_not_called()


def test_upsert_collection_items_bulk(repo):
    from repository.models import CollectionItem

    items = [
        CollectionItem(instance_id=1, release_id=10, title="A"),
        CollectionItem(instance_id=2, release_id=20, title="B"),
    ]
    mock_result = MagicMock()
    mock_result.upserted_count = 1
    mock_result.modified_count = 1
    repo._collection_items.bulk_write.return_value = mock_result
    assert repo.upsert_collection_items_bulk(items) == 2
    repo._collection_items.bulk_write.assert_called_once()


def test_find_collection_items_default(repo):
    from repository.models import CollectionItem

    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = [
        {"instance_id": 1, "release_id": 10, "title": "A", "artist": "X"},
    ]
    repo._collection_items.find.return_value = cursor
    results = repo.find_collection_items()
    assert len(results) == 1
    # Default sort is artist asc with secondary year
    cursor.sort.assert_called_once()
    sort_arg = cursor.sort.call_args[0][0]
    assert sort_arg[0] == ("artist", 1)
    assert sort_arg[1] == ("year", 1)


def test_find_collection_items_with_query_and_sort(repo):
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = []
    repo._collection_items.find.return_value = cursor
    repo.find_collection_items(query="miles", sort="year", sort_order="desc", skip=10, limit=25)
    filt = repo._collection_items.find.call_args[0][0]
    assert "$text" in filt
    sort_arg = cursor.sort.call_args[0][0]
    assert sort_arg[0] == ("year", -1)
    # No secondary sort for non-artist
    assert len(sort_arg) == 1


def test_count_collection_items_no_query(repo):
    repo._collection_items.count_documents.return_value = 50
    assert repo.count_collection_items() == 50
    repo._collection_items.count_documents.assert_called_once_with({})


def test_count_collection_items_with_query(repo):
    repo._collection_items.count_documents.return_value = 5
    assert repo.count_collection_items(query="jazz") == 5
    filt = repo._collection_items.count_documents.call_args[0][0]
    assert "$text" in filt


def test_delete_stale_items(repo):
    mock_result = MagicMock()
    mock_result.deleted_count = 3
    repo._collection_items.delete_many.return_value = mock_result
    assert repo.delete_stale_items("2024-01-01T00:00:00Z") == 3


# ── Sync status ─────────────────────────────────────────────────────────────


def test_get_sync_status_exists(repo):
    repo._sync_status.find_one.return_value = {"status": "syncing", "total_items": 10}
    result = repo.get_sync_status()
    assert result["status"] == "syncing"


def test_get_sync_status_missing(repo):
    repo._sync_status.find_one.return_value = None
    assert repo.get_sync_status() == {"status": "idle"}


def test_update_sync_status(repo):
    repo.update_sync_status({"status": "syncing"})
    call = repo._sync_status.update_one.call_args
    assert call[0][0] == {"_id": "collection"}
    assert call[0][1] == {"$set": {"status": "syncing"}}
    assert call[1]["upsert"] is True


# ── find_all_items with status filter ───────────────────────────────────────


def test_find_all_items_with_status_filter(repo):
    cursor = MagicMock()
    cursor.sort.return_value = []
    repo._items.find.return_value = cursor
    repo.find_all_items(status="completed")
    query = repo._items.find.call_args[0][0]
    assert query["status"] == "completed"


# ── LLM usage ───────────────────────────────────────────────────────────────


def test_save_llm_usage(repo):
    from repository.models import LLMUsageRecord

    record = LLMUsageRecord(record_id="u1", operation="vision", model="gpt-4")
    repo.save_llm_usage(record)
    repo._llm_usage.replace_one.assert_called_once()
    call_args = repo._llm_usage.replace_one.call_args
    assert call_args[0][0] == {"record_id": "u1"}


def test_get_usage_summary(repo):
    repo._llm_usage.aggregate.return_value = [{
        "totals": [{"_id": None, "total_calls": 5, "total_tokens": 1000, "total_cost_usd": 0.05}],
        "by_day": [{"_id": "2024-01-01", "requests": 5, "cost_usd": 0.05}],
        "by_model": [{"_id": "gpt-4", "requests": 5, "cost_usd": 0.05}],
        "by_operation": [{"_id": "vision", "requests": 5, "tokens": 1000, "cost_usd": 0.05}],
    }]
    result = repo.get_usage_summary(days=7)
    assert result["period_days"] == 7
    assert result["totals"]["total_calls"] == 5
    assert len(result["by_day"]) == 1
    assert len(result["by_model"]) == 1
    assert len(result["by_operation"]) == 1


def test_get_usage_summary_empty(repo):
    repo._llm_usage.aggregate.return_value = []
    result = repo.get_usage_summary()
    assert result["totals"] == {}
    assert result["by_day"] == []


def test_get_usage_summary_no_totals(repo):
    repo._llm_usage.aggregate.return_value = [{
        "totals": [],
        "by_day": [],
        "by_model": [],
        "by_operation": [],
    }]
    result = repo.get_usage_summary()
    assert result["totals"]["total_calls"] == 0
