import time

import requests
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile

from auth import User, get_current_user
from config import SINGLE_SEARCH_BATCH_ID
from deps import get_repo
from logger import get_logger
from models import AddToCollectionRequest, MediaType, SearchResponse
from repository import BatchItem, CollectionRecord, SearchRecord
from repository.mongo import MongoRepository
from services.discogs import add_to_collection, get_marketplace_stats
from services.discogs_auth import load_tokens_for_user
from services.search import process_single_image
from utils import save_upload_image

log = get_logger("routes.search")

router = APIRouter()


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
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    request_start = time.time()
    record = SearchRecord(image_filename=file.filename, user_id=user.id)

    log.info("Search request: user_id=%s filename=%s content_type=%s", user.id, file.filename, file.content_type)

    if file.content_type not in ("image/jpeg", "image/png"):
        log.warning("Rejected: invalid content type %s", file.content_type)
        record.status = "error_validation"
        _save_record(repo, record, request_start)
        raise HTTPException(status_code=400, detail="Only JPEG and PNG images are accepted.")

    image_bytes = await file.read()
    record.image_size_bytes = len(image_bytes)
    log.info("Image size: %d bytes (%.1f KB)", len(image_bytes), len(image_bytes) / 1024)

    tokens = load_tokens_for_user(repo, user.id)

    try:
        response = process_single_image(
            image_bytes, file.content_type, media_type=media_type,
            user_id=user.id, tokens=tokens,
        )
    except ValueError as e:
        record.status = "error_vision"
        log.error("Search pipeline failed (validation): %s", e)
        _save_record(repo, record, request_start)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        record.status = "error_pipeline"
        log.error("Search pipeline failed: %s", e, exc_info=True)
        _save_record(repo, record, request_start)
        raise HTTPException(status_code=502, detail="Search pipeline error. Please try again.")

    record.status = "success"
    record.total_returned = response.total
    record.top_match_title = response.results[0].title if response.results else None
    log.info("Response: %d results returned", response.total)

    # Persist as a reviewable BatchItem so it appears in the review queue
    try:
        item = BatchItem(
            batch_id=SINGLE_SEARCH_BATCH_ID,
            user_id=user.id,
            image_filename=file.filename or "upload",
            status="completed",
            label_data=response.label_data.model_dump(),
            results=[r.model_dump() for r in response.results],
            strategy=response.strategy,
            debug=response.debug,
        )
        item.image_url = save_upload_image(item.item_id, file.filename or "upload.jpg", image_bytes, user_id=user.id)
        repo.save_item(item)
        response.item_id = item.item_id
    except Exception as e:
        log.error("Failed to save single-search batch item: %s", e, exc_info=True)

    _save_record(repo, record, request_start)
    return response


@router.post("/api/collection")
async def add_to_collection_endpoint(
    body: AddToCollectionRequest,
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    request_start = time.time()
    record = CollectionRecord(release_id=body.release_id, user_id=user.id)

    log.info("Add to collection request: user_id=%s release_id=%d", user.id, body.release_id)

    tokens = load_tokens_for_user(repo, user.id)

    try:
        instance = add_to_collection(body.release_id, tokens=tokens)
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
        raise HTTPException(status_code=502, detail="Failed to add to Discogs collection. Please try again.")
    except Exception as e:
        record.status = "error"
        record.error = str(e)
        record.duration_ms = (time.time() - request_start) * 1000
        try:
            repo.save_collection_record(record)
        except Exception as save_err:
            log.error("Failed to save collection record: %s", save_err, exc_info=True)
        log.error("Unexpected error adding to collection: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail="Failed to add to Discogs collection. Please try again.")

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


@router.get("/api/price/{release_id}")
async def get_price(
    release_id: int,
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Fetch marketplace price stats for a Discogs release."""
    tokens = load_tokens_for_user(repo, user.id)
    try:
        stats = get_marketplace_stats(release_id, tokens=tokens)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 502
        if status == 404:
            raise HTTPException(status_code=404, detail="Release not found")
        raise HTTPException(status_code=502, detail="Failed to fetch price data. Please try again.")
    except Exception as e:
        log.error("Failed to fetch marketplace stats for %d: %s", release_id, e)
        raise HTTPException(status_code=502, detail="Failed to fetch price data. Please try again.")

    lowest = stats.get("lowest_price")
    if isinstance(lowest, dict):
        price_value = lowest.get("value")
        currency = lowest.get("currency")
    else:
        price_value = lowest
        currency = None

    return {
        "lowest_price": price_value,
        "num_for_sale": stats.get("num_for_sale", 0),
        "currency": currency,
    }
