from enum import StrEnum

from pydantic import BaseModel


class MediaType(StrEnum):
    VINYL = "vinyl"
    CD = "cd"


class SearchStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    ERROR_VALIDATION = "error_validation"
    ERROR_VISION = "error_vision"
    ERROR_PIPELINE = "error_pipeline"


class ItemStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    SKIPPED = "skipped"
    WRONG = "wrong"


class LabelData(BaseModel):
    albums: list[str]
    artists: list[str]
    tracks: list[str] | None = None
    country: str | None = None
    format: str | None = None
    label: str | None = None
    catno: str | None = None
    year: str | None = None


class DiscogsResult(BaseModel):
    discogs_id: int | None = None
    title: str | None = None
    year: int | None = None
    country: str | None = None
    format: str | None = None
    label: str | None = None
    catno: str | None = None
    discogs_url: str | None = None
    cover_image: str | None = None
    master_id: int | None = None
    is_master_fallback: bool = False


class AddToCollectionRequest(BaseModel):
    release_id: int
    force: bool = False


class SearchResponse(BaseModel):
    label_data: LabelData
    strategy: str
    results: list[DiscogsResult]
    total: int
    item_id: str | None = None  # batch_item ID for review tracking
    debug: dict | None = None


class ReviewAction(BaseModel):
    review_status: ReviewStatus
    accepted_release_id: int | None = None
