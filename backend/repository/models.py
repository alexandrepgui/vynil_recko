from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class SearchRecord:
    request_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    user_id: str = ""
    status: str = "pending"
    image_filename: str | None = None
    image_size_bytes: int | None = None
    batch_id: str | None = None
    total_returned: int = 0
    top_match_title: str | None = None
    total_duration_ms: float | None = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SearchRecord:
        return cls(
            request_id=data.get("request_id", str(uuid4())),
            timestamp=data.get("timestamp", ""),
            user_id=data.get("user_id", ""),
            status=data.get("status", "pending"),
            image_filename=data.get("image_filename"),
            image_size_bytes=data.get("image_size_bytes"),
            batch_id=data.get("batch_id"),
            total_returned=data.get("total_returned", 0),
            top_match_title=data.get("top_match_title"),
            total_duration_ms=data.get("total_duration_ms"),
        )


@dataclass
class Batch:
    batch_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    status: str = "processing"  # processing | completed | failed
    total_images: int = 0
    processed: int = 0
    failed: int = 0
    original_filename: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Batch:
        return cls(
            batch_id=data.get("batch_id", str(uuid4())),
            user_id=data.get("user_id", ""),
            status=data.get("status", "processing"),
            total_images=data.get("total_images", 0),
            processed=data.get("processed", 0),
            failed=data.get("failed", 0),
            original_filename=data.get("original_filename"),
            created_at=data.get("created_at", ""),
        )


@dataclass
class BatchItem:
    item_id: str = field(default_factory=lambda: str(uuid4()))
    batch_id: str = ""
    user_id: str = ""
    image_filename: str = ""
    status: str = "pending"  # pending | processing | completed | error
    error: str | None = None
    label_data: dict | None = None
    results: list[dict] | None = None
    strategy: str | None = None
    review_status: str = "unreviewed"  # unreviewed | accepted | skipped
    accepted_release_id: int | None = None
    image_url: str | None = None
    debug: dict | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processed_at: str | None = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> BatchItem:
        return cls(
            item_id=data.get("item_id", str(uuid4())),
            batch_id=data.get("batch_id", ""),
            user_id=data.get("user_id", ""),
            image_filename=data.get("image_filename", ""),
            status=data.get("status", "pending"),
            error=data.get("error"),
            label_data=data.get("label_data"),
            results=data.get("results"),
            strategy=data.get("strategy"),
            review_status=data.get("review_status", "unreviewed"),
            accepted_release_id=data.get("accepted_release_id"),
            image_url=data.get("image_url"),
            debug=data.get("debug"),
            created_at=data.get("created_at", ""),
            processed_at=data.get("processed_at"),
        )


@dataclass
class LLMUsageRecord:
    record_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    user_id: str = ""
    provider: str = ""  # openrouter | google
    model: str = ""  # e.g. "google/gemini-2.5-flash"
    operation: str = ""  # label_reading | ranking
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    batch_id: str | None = None
    item_id: str | None = None
    cache_hit: bool = False

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> LLMUsageRecord:
        return cls(
            record_id=data.get("record_id", str(uuid4())),
            timestamp=data.get("timestamp", ""),
            user_id=data.get("user_id", ""),
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            operation=data.get("operation", ""),
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            cost_usd=data.get("cost_usd", 0.0),
            batch_id=data.get("batch_id"),
            item_id=data.get("item_id"),
            cache_hit=data.get("cache_hit", False),
        )


@dataclass
class CollectionItem:
    """A single release in the user's Discogs collection (persisted locally)."""
    user_id: str = ""
    instance_id: int = 0
    release_id: int = 0
    title: str = ""
    artist: str = ""
    year: int = 0
    genres: list[str] = field(default_factory=list)
    styles: list[str] = field(default_factory=list)
    format: str = ""
    cover_image: str | None = None
    master_id: int | None = None
    date_added: str | None = None
    synced_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> CollectionItem:
        return cls(
            user_id=data.get("user_id", ""),
            instance_id=data.get("instance_id", 0),
            release_id=data.get("release_id", 0),
            title=data.get("title", ""),
            artist=data.get("artist", ""),
            year=data.get("year", 0),
            genres=data.get("genres", []),
            styles=data.get("styles", []),
            format=data.get("format", ""),
            cover_image=data.get("cover_image"),
            master_id=data.get("master_id"),
            date_added=data.get("date_added"),
            synced_at=data.get("synced_at", ""),
        )


@dataclass
class CollectionRecord:
    record_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    user_id: str = ""
    status: str = "pending"
    release_id: int | None = None
    username: str | None = None
    discogs_instance_id: int | None = None
    duration_ms: float | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> CollectionRecord:
        return cls(
            record_id=data.get("record_id", str(uuid4())),
            timestamp=data.get("timestamp", ""),
            user_id=data.get("user_id", ""),
            status=data.get("status", "pending"),
            release_id=data.get("release_id"),
            username=data.get("username"),
            discogs_instance_id=data.get("discogs_instance_id"),
            duration_ms=data.get("duration_ms"),
            error=data.get("error"),
        )
