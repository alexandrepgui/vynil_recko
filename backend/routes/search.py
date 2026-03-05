import time

import requests
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile

from config import SINGLE_SEARCH_BATCH_ID
from deps import get_repo
from logger import get_logger
from models import AddToCollectionRequest, MediaType, SearchResponse
from repository import BatchItem, CollectionRecord, SearchRecord
from repository.mongo import MongoRepository
from services.discogs import add_to_collection
from services.search import process_single_image

log = get_logger("routes.search")

router = APIRouter()

# TODO: Re-enable file size limit once we determine the right threshold
# MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _save_record(repo: MongoRepository, record: SearchRecord, start_time: float) -> None:
    """Save telemetry record with duration. Swallows errors."""
    record.total_duration_ms = (time.time() - start_time) * 1000
    try:
        repo.save_search_record(record)
    except Exception as e:
        log.error("Failed to save telemetry record: %s", e, exc_info=True)


@router.post("/api/search", response_model=SearchResponse)
async def search(
    file: UploadFile,
    media_type: MediaType = Form(MediaType.VINYL),
    repo: MongoRepository = Depends(get_repo),
):
    request_start = time.time()
    record = SearchRecord(image_filename=file.filename)

    log.info("Search request: filename=%s content_type=%s", file.filename, file.content_type)

    if file.content_type not in ("image/jpeg", "image/png"):
        log.warning("Rejected: invalid content type %s", file.content_type)
        record.status = "error_validation"
        _save_record(repo, record, request_start)
        raise HTTPException(status_code=400, detail="Only JPEG and PNG images are accepted.")

    image_bytes = await file.read()
    record.image_size_bytes = len(image_bytes)
    log.info("Image size: %d bytes (%.1f KB)", len(image_bytes), len(image_bytes) / 1024)

    # TODO: Re-enable file size limit
    # if len(image_bytes) > MAX_FILE_SIZE:
    #     log.warning("Rejected: file too large (%d bytes)", len(image_bytes))
    #     record.status = "error_validation"
    #     _save_record(repo, record, request_start)
    #     raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB.")

    try:
        response = process_single_image(image_bytes, file.content_type, media_type=media_type)
    except ValueError as e:
        record.status = "error_vision"
        log.error("Search pipeline failed (validation): %s", e)
        _save_record(repo, record, request_start)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        record.status = "error_pipeline"
        log.error("Search pipeline failed: %s", e, exc_info=True)
        _save_record(repo, record, request_start)
        raise HTTPException(status_code=502, detail=f"Search pipeline error: {e}")

    record.status = "success"
    record.total_returned = response.total
    record.top_match_title = response.results[0].title if response.results else None
    log.info("Response: %d results returned", response.total)

    # Persist as a reviewable BatchItem so it appears in the review queue
    try:
        item = BatchItem(
            batch_id=SINGLE_SEARCH_BATCH_ID,
            image_filename=file.filename or "upload",
            status="completed",
            label_data=response.label_data.model_dump(),
            results=[r.model_dump() for r in response.results],
            strategy=response.strategy,
        )
        repo.save_item(item)
        response.item_id = item.item_id
    except Exception as e:
        log.error("Failed to save single-search batch item: %s", e, exc_info=True)

    _save_record(repo, record, request_start)
    return response


@router.post("/api/collection")
async def add_to_collection_endpoint(
    body: AddToCollectionRequest,
    repo: MongoRepository = Depends(get_repo),
):
    request_start = time.time()
    record = CollectionRecord(release_id=body.release_id)

    log.info("Add to collection request: release_id=%d", body.release_id)
    try:
        instance = add_to_collection(body.release_id)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 502
        record.status = "error"
        record.error = str(e)
        record.duration_ms = (time.time() - request_start) * 1000
        try:
            repo.save_collection_record(record)
        except Exception as save_err:
            log.error("Failed to save collection record: %s", save_err, exc_info=True)
        log.error("Discogs collection API failed: %s", e)
        if status == 404:
            raise HTTPException(status_code=404, detail="Release not found on Discogs.")
        raise HTTPException(status_code=502, detail=f"Discogs API error: {e}")
    except Exception as e:
        record.status = "error"
        record.error = str(e)
        record.duration_ms = (time.time() - request_start) * 1000
        try:
            repo.save_collection_record(record)
        except Exception as save_err:
            log.error("Failed to save collection record: %s", save_err, exc_info=True)
        log.error("Unexpected error adding to collection: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=f"Discogs API error: {e}")

    record.status = "success"
    record.discogs_instance_id = instance.get("instance_id")
    resource_url = instance.get("resource_url", "")
    if "/users/" in resource_url:
        record.username = resource_url.split("/users/")[1].split("/")[0]
    record.duration_ms = (time.time() - request_start) * 1000
    try:
        repo.save_collection_record(record)
    except Exception as e:
        log.error("Failed to save collection record: %s", e, exc_info=True)

    log.info("Release %d added to collection: instance_id=%s", body.release_id, instance.get("instance_id"))
    return instance
