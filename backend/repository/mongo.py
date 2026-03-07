from __future__ import annotations

from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.collection import Collection

from logger import get_logger
from .models import Batch, BatchItem, CollectionRecord, LLMUsageRecord, SearchRecord

log = get_logger("repository.mongo")


class MongoRepository:
    """Unified repository for all MongoDB operations."""

    def __init__(self, uri: str, database: str):
        self._client = MongoClient(uri)
        self._db = self._client[database]
        self._search_records: Collection = self._db["search_records"]
        self._collection_records: Collection = self._db["collection_records"]
        self._batches: Collection = self._db["batches"]
        self._items: Collection = self._db["batch_items"]
        self._llm_usage: Collection = self._db["llm_usage"]
        log.info("MongoDB repository: db=%s", database)

    # ── Search telemetry ──────────────────────────────────────────────────

    def save_search_record(self, record: SearchRecord) -> None:
        doc = record.to_dict()
        self._search_records.replace_one(
            {"request_id": record.request_id},
            doc,
            upsert=True,
        )
        log.info("Saved record %s (status=%s)", record.request_id, record.status)

    def find_search_record(self, request_id: str) -> SearchRecord | None:
        doc = self._search_records.find_one({"request_id": request_id}, {"_id": 0})
        if doc is None:
            return None
        return SearchRecord.from_dict(doc)

    def find_all_search_records(self, limit: int = 100, skip: int = 0) -> list[SearchRecord]:
        cursor = (
            self._search_records.find({}, {"_id": 0})
            .sort("timestamp", -1)
            .skip(skip)
            .limit(limit)
        )
        return [SearchRecord.from_dict(doc) for doc in cursor]

    def count_search_records(self) -> int:
        return self._search_records.count_documents({})

    # ── Collection telemetry ──────────────────────────────────────────────

    def save_collection_record(self, record: CollectionRecord) -> None:
        doc = record.to_dict()
        self._collection_records.replace_one(
            {"record_id": record.record_id},
            doc,
            upsert=True,
        )
        log.info("Saved collection record %s (status=%s)", record.record_id, record.status)

    # ── Batches ───────────────────────────────────────────────────────────

    def save_batch(self, batch: Batch) -> None:
        self._batches.replace_one(
            {"batch_id": batch.batch_id}, batch.to_dict(), upsert=True,
        )
        log.info("Saved batch %s (status=%s)", batch.batch_id, batch.status)

    def find_batch(self, batch_id: str) -> Batch | None:
        doc = self._batches.find_one({"batch_id": batch_id}, {"_id": 0})
        return Batch.from_dict(doc) if doc else None

    def update_batch_status(self, batch_id: str, status: str) -> None:
        self._batches.update_one({"batch_id": batch_id}, {"$set": {"status": status}})

    def increment_batch_processed(self, batch_id: str) -> None:
        self._batches.update_one({"batch_id": batch_id}, {"$inc": {"processed": 1}})

    def increment_batch_failed(self, batch_id: str) -> None:
        self._batches.update_one({"batch_id": batch_id}, {"$inc": {"failed": 1}})

    # ── Batch items ───────────────────────────────────────────────────────

    def save_item(self, item: BatchItem) -> None:
        self._items.replace_one(
            {"item_id": item.item_id}, item.to_dict(), upsert=True,
        )

    def find_item(self, item_id: str) -> BatchItem | None:
        doc = self._items.find_one({"item_id": item_id}, {"_id": 0})
        return BatchItem.from_dict(doc) if doc else None

    def find_items_by_batch(
        self, batch_id: str, review_status: str | None = None,
    ) -> list[BatchItem]:
        query: dict = {"batch_id": batch_id}
        if review_status is not None:
            query["review_status"] = review_status
        cursor = self._items.find(query, {"_id": 0}).sort("created_at", 1)
        return [BatchItem.from_dict(doc) for doc in cursor]

    def find_all_items(
        self, review_status: str | None = None, status: str | None = None,
    ) -> list[BatchItem]:
        """Query across all batches, optionally filtered by review_status and/or status."""
        query: dict = {}
        if review_status is not None:
            query["review_status"] = review_status
        if status is not None:
            query["status"] = status
        cursor = self._items.find(query, {"_id": 0}).sort("created_at", 1)
        return [BatchItem.from_dict(doc) for doc in cursor]

    def update_item_status(self, item_id: str, status: str) -> None:
        self._items.update_one({"item_id": item_id}, {"$set": {"status": status}})

    def update_item_completed(
        self,
        item_id: str,
        label_data: dict,
        results: list[dict],
        strategy: str,
        debug: dict | None = None,
    ) -> None:
        update: dict = {
            "status": "completed",
            "label_data": label_data,
            "results": results,
            "strategy": strategy,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        if debug is not None:
            update["debug"] = debug
        self._items.update_one({"item_id": item_id}, {"$set": update})

    def update_item_error(self, item_id: str, error: str) -> None:
        self._items.update_one(
            {"item_id": item_id},
            {"$set": {
                "status": "error",
                "error": error,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

    def update_item_review(
        self, item_id: str, review_status: str, accepted_release_id: int | None,
    ) -> None:
        self._items.update_one(
            {"item_id": item_id},
            {"$set": {
                "review_status": review_status,
                "accepted_release_id": accepted_release_id,
            }},
        )

    # ── LLM usage tracking ────────────────────────────────────────────────

    def save_llm_usage(self, record: LLMUsageRecord) -> None:
        doc = record.to_dict()
        self._llm_usage.replace_one(
            {"record_id": record.record_id}, doc, upsert=True,
        )
        log.debug("Saved LLM usage %s (op=%s cost=$%.6f)", record.record_id, record.operation, record.cost_usd)

    def get_usage_summary(self, days: int = 30) -> dict:
        """Aggregate LLM usage stats over the last N days."""
        cutoff = datetime.now(timezone.utc)
        cutoff = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        cutoff_str = (cutoff - timedelta(days=days)).isoformat()

        match_stage = {"$match": {"timestamp": {"$gte": cutoff_str}, "cache_hit": False}}

        pipeline = [
            match_stage,
            {"$facet": {
                "totals": [{"$group": {
                    "_id": None,
                    "total_calls": {"$sum": 1},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "total_cost_usd": {"$sum": "$cost_usd"},
                }}],
                "by_day": [{"$group": {
                    "_id": {"$substr": ["$timestamp", 0, 10]},
                    "requests": {"$sum": 1},
                    "cost_usd": {"$sum": "$cost_usd"},
                }}, {"$sort": {"_id": 1}}],
                "by_model": [{"$group": {
                    "_id": "$model",
                    "requests": {"$sum": 1},
                    "cost_usd": {"$sum": "$cost_usd"},
                }}],
                "by_operation": [{"$group": {
                    "_id": "$operation",
                    "requests": {"$sum": 1},
                    "tokens": {"$sum": "$total_tokens"},
                    "cost_usd": {"$sum": "$cost_usd"},
                }}],
            }},
        ]

        result = list(self._llm_usage.aggregate(pipeline))
        if not result:
            return {"period_days": days, "totals": {}, "by_day": [], "by_model": [], "by_operation": []}

        facets = result[0]
        totals_raw = facets["totals"][0] if facets["totals"] else {}
        totals_raw.pop("_id", None)

        return {
            "period_days": days,
            "totals": totals_raw or {"total_calls": 0, "total_tokens": 0, "total_cost_usd": 0.0},
            "by_day": [{"date": d["_id"], "requests": d["requests"], "cost_usd": d["cost_usd"]} for d in facets["by_day"]],
            "by_model": [{"model": d["_id"], "requests": d["requests"], "cost_usd": d["cost_usd"]} for d in facets["by_model"]],
            "by_operation": [{"operation": d["_id"], "requests": d["requests"], "tokens": d["tokens"], "cost_usd": d["cost_usd"]} for d in facets["by_operation"]],
        }
