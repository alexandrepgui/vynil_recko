import io
import os
import time
import zipfile

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, UploadFile

from auth import User, get_current_user
from config import UPLOADS_DIR
from deps import get_repo
from logger import get_logger
from models import ItemStatus, MediaType, ReviewAction, ReviewStatus
from repository import Batch, BatchItem, SearchRecord
from repository.mongo import MongoRepository
from services.discogs_auth import OAuthTokens, require_discogs_tokens
from services.search import process_single_image
from services.vision import invalidate_cache
from utils import save_upload_image

log = get_logger("routes.batch")

router = APIRouter()

VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
_EXT_TO_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def _extract_images_from_zip(zip_bytes: bytes) -> list[tuple[str, bytes, str]]:
    """Return [(filename, image_bytes, content_type)] from a zip archive."""
    images: list[tuple[str, bytes, str]] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith("/") or "__MACOSX" in name:
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in VALID_IMAGE_EXTENSIONS:
                images.append((name, zf.read(name), _EXT_TO_MIME[ext]))
    return images


def _process_batch(
    batch_id: str,
    items: list[tuple[str, bytes, str]],
    filenames: dict[str, str],
    media_type: str = "vinyl",
    user_id: str = "",
    tokens: OAuthTokens | None = None,
) -> None:
    """Background task: process each image sequentially."""
    repo = get_repo()
    for item_id, image_bytes, content_type in items:
        record = SearchRecord(
            user_id=user_id,
            image_filename=filenames.get(item_id, "unknown"),
            image_size_bytes=len(image_bytes),
            batch_id=batch_id,
        )
        request_start = time.time()
        try:
            repo.update_item_status(item_id, ItemStatus.PROCESSING)
            response = process_single_image(
                image_bytes, content_type, media_type=media_type,
                batch_id=batch_id, item_id=item_id,
                user_id=user_id, tokens=tokens,
            )
            repo.update_item_completed(
                item_id,
                label_data=response.label_data.model_dump(),
                results=[r.model_dump() for r in response.results],
                strategy=response.strategy,
                debug=response.debug,
            )
            repo.increment_batch_processed(batch_id)
            record.status = "success"
            record.total_returned = response.total
            record.top_match_title = response.results[0].title if response.results else None
        except ValueError as e:
            log.error("Batch item %s failed (validation): %s", item_id, e)
            repo.update_item_error(item_id, str(e))
            repo.increment_batch_failed(batch_id)
        except Exception as e:
            log.error("Batch item %s failed: %s", item_id, e, exc_info=True)
            repo.update_item_error(item_id, "Search pipeline error. Check server logs for details.")
            repo.increment_batch_failed(batch_id)
            record.status = "error_pipeline"
        finally:
            record.total_duration_ms = (time.time() - request_start) * 1000
            try:
                repo.save_search_record(record)
            except Exception as e:
                log.error("Failed to save batch telemetry record: %s", e, exc_info=True)

        # Respect Discogs rate limits (~60 req/min)
        time.sleep(1)

    repo.update_batch_status(batch_id, "completed")  # Batch status not yet typed as enum
    log.info("Batch %s completed", batch_id)


@router.post("/api/batch")
async def create_batch(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    media_type: MediaType = Form(MediaType.VINYL),
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(400, "Only .zip files are accepted.")

    zip_bytes = await file.read()

    image_files = _extract_images_from_zip(zip_bytes)
    if not image_files:
        raise HTTPException(422, "No JPEG or PNG images found in the zip.")

    batch = Batch(
        user_id=user.id,
        total_images=len(image_files),
        original_filename=file.filename,
    )
    repo.save_batch(batch)

    task_items: list[tuple[str, bytes, str]] = []
    filenames: dict[str, str] = {}
    for filename, img_bytes, content_type in image_files:
        item = BatchItem(batch_id=batch.batch_id, user_id=user.id, image_filename=filename)
        item.image_url = save_upload_image(item.item_id, filename, img_bytes, user_id=user.id)
        repo.save_item(item)
        task_items.append((item.item_id, img_bytes, content_type))
        filenames[item.item_id] = filename

    tokens = require_discogs_tokens(repo, user.id)
    background_tasks.add_task(
        _process_batch, batch.batch_id, task_items, filenames, media_type,
        user_id=user.id, tokens=tokens,
    )
    log.info("Batch %s created: %d images (user_id=%s)", batch.batch_id, len(image_files), user.id)

    return {"batch_id": batch.batch_id, "total_images": len(image_files)}


@router.get("/api/batch/{batch_id}")
async def get_batch(
    batch_id: str,
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    batch = repo.find_batch(batch_id, user.id)
    if not batch:
        raise HTTPException(404, "Batch not found.")
    return batch.to_dict()


@router.get("/api/batch/{batch_id}/items")
async def get_batch_items(
    batch_id: str,
    review_status: ReviewStatus | None = Query(None),
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    items = repo.find_items_by_batch(batch_id, user.id, review_status=review_status)
    return [item.to_dict() for item in items]


@router.patch("/api/batch/{batch_id}/items/{item_id}")
async def review_batch_item(
    batch_id: str,
    item_id: str,
    body: ReviewAction,
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    item = repo.find_item(item_id, user.id)
    if not item or item.batch_id != batch_id:
        raise HTTPException(404, "Item not found.")
    repo.update_item_review(item_id, body.review_status, body.accepted_release_id)
    return {"ok": True}


# ── Global review (across all batches + single searches) ────────────────────


@router.get("/api/review/items")
async def get_all_review_items(
    review_status: ReviewStatus | None = Query(None),
    status: ItemStatus | None = Query(None),
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    items = repo.find_all_items(user.id, review_status=review_status, status=status)
    return [item.to_dict() for item in items]


@router.patch("/api/review/items/{item_id}")
async def review_item(
    item_id: str,
    body: ReviewAction,
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    item = repo.find_item(item_id, user.id)
    if not item:
        raise HTTPException(404, "Item not found.")
    repo.update_item_review(item_id, body.review_status, body.accepted_release_id)
    return {"ok": True}


@router.post("/api/review/items/{item_id}/undo")
async def undo_review_item(
    item_id: str,
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    item = repo.find_item(item_id, user.id)
    if not item:
        raise HTTPException(404, "Item not found.")
    repo.update_item_review(item_id, ReviewStatus.UNREVIEWED, None)
    return {"ok": True}


def _reprocess_item(
    item_id: str, image_bytes: bytes, content_type: str,
    batch_id: str | None = None, user_id: str = "",
    tokens: OAuthTokens | None = None,
) -> None:
    """Background task: re-run the processing pipeline for a single item."""
    repo = get_repo()
    try:
        repo.update_item_status(item_id, ItemStatus.PROCESSING)
        response = process_single_image(
            image_bytes, content_type, media_type="vinyl",
            batch_id=batch_id, item_id=item_id,
            user_id=user_id, tokens=tokens,
        )
        repo.update_item_completed(
            item_id,
            label_data=response.label_data.model_dump(),
            results=[r.model_dump() for r in response.results],
            strategy=response.strategy,
            debug=response.debug,
        )
    except ValueError as e:
        log.error("Retry item %s failed (validation): %s", item_id, e)
        repo.update_item_error(item_id, str(e))
    except Exception as e:
        log.error("Retry item %s failed: %s", item_id, e, exc_info=True)
        repo.update_item_error(item_id, "Search pipeline error. Check server logs for details.")


@router.post("/api/review/items/{item_id}/retry")
async def retry_item(
    item_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    item = repo.find_item(item_id, user.id)
    if not item:
        raise HTTPException(404, "Item not found.")
    if not item.image_url:
        raise HTTPException(422, "No saved image to reprocess.")

    # Resolve image path from URL (e.g. /api/uploads/uid/abc.jpg → .uploads/uid/abc.jpg)
    url_path = item.image_url.replace("/api/uploads/", "")
    image_path = (UPLOADS_DIR / url_path).resolve()
    if not image_path.is_relative_to(UPLOADS_DIR.resolve()):
        raise HTTPException(403, "Invalid image path.")

    try:
        image_bytes = image_path.read_bytes()
    except FileNotFoundError:
        raise HTTPException(422, "Image file not found on disk.")
    ext = image_path.suffix.lower()
    content_type = _EXT_TO_MIME.get(ext, "image/jpeg")

    # Invalidate LLM cache so the image is re-analysed from scratch
    invalidate_cache(image_bytes)

    # Reset item state
    repo.update_item_status(item_id, ItemStatus.PENDING)
    repo.update_item_review(item_id, ReviewStatus.UNREVIEWED, None)

    tokens = require_discogs_tokens(repo, user.id)
    background_tasks.add_task(
        _reprocess_item, item_id, image_bytes, content_type,
        item.batch_id, user_id=user.id, tokens=tokens,
    )
    return {"ok": True}
