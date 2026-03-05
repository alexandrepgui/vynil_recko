import io
import os
import time
import zipfile

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, UploadFile

from deps import get_repo
from logger import get_logger
from models import MediaType, ReviewAction, ReviewStatus
from repository import Batch, BatchItem, SearchRecord
from repository.mongo import MongoRepository
from services.search import process_single_image

log = get_logger("routes.batch")

router = APIRouter()

VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
_EXT_TO_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
MAX_ZIP_SIZE = 100 * 1024 * 1024  # 100 MB


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
) -> None:
    """Background task: process each image sequentially."""
    repo = get_repo()
    for item_id, image_bytes, content_type in items:
        record = SearchRecord(
            image_filename=filenames.get(item_id, "unknown"),
            image_size_bytes=len(image_bytes),
            batch_id=batch_id,
        )
        request_start = time.time()
        try:
            repo.update_item_status(item_id, "processing")
            response = process_single_image(image_bytes, content_type, media_type=media_type)
            repo.update_item_completed(
                item_id,
                label_data=response.label_data.model_dump(),
                results=[r.model_dump() for r in response.results],
                strategy=response.strategy,
            )
            repo.increment_batch_processed(batch_id)
            record.status = "success"
            record.total_returned = response.total
            record.top_match_title = response.results[0].title if response.results else None
        except Exception as e:
            log.error("Batch item %s failed: %s", item_id, e, exc_info=True)
            repo.update_item_error(item_id, str(e))
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

    repo.update_batch_status(batch_id, "completed")
    log.info("Batch %s completed", batch_id)


@router.post("/api/batch")
async def create_batch(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    media_type: MediaType = Form(MediaType.VINYL),
    repo: MongoRepository = Depends(get_repo),
):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(400, "Only .zip files are accepted.")

    zip_bytes = await file.read()
    if len(zip_bytes) > MAX_ZIP_SIZE:
        raise HTTPException(413, "Zip file too large. Maximum 100MB.")

    image_files = _extract_images_from_zip(zip_bytes)
    if not image_files:
        raise HTTPException(422, "No JPEG or PNG images found in the zip.")

    batch = Batch(
        total_images=len(image_files),
        original_filename=file.filename,
    )
    repo.save_batch(batch)

    task_items: list[tuple[str, bytes, str]] = []
    filenames: dict[str, str] = {}
    for filename, img_bytes, content_type in image_files:
        item = BatchItem(batch_id=batch.batch_id, image_filename=filename)
        repo.save_item(item)
        task_items.append((item.item_id, img_bytes, content_type))
        filenames[item.item_id] = filename

    background_tasks.add_task(_process_batch, batch.batch_id, task_items, filenames, media_type)
    log.info("Batch %s created: %d images", batch.batch_id, len(image_files))

    return {"batch_id": batch.batch_id, "total_images": len(image_files)}


@router.get("/api/batch/{batch_id}")
async def get_batch(batch_id: str, repo: MongoRepository = Depends(get_repo)):
    batch = repo.find_batch(batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found.")
    return batch.to_dict()


@router.get("/api/batch/{batch_id}/items")
async def get_batch_items(
    batch_id: str,
    review_status: ReviewStatus | None = Query(None),
    repo: MongoRepository = Depends(get_repo),
):
    items = repo.find_items_by_batch(batch_id, review_status=review_status)
    return [item.to_dict() for item in items]


@router.patch("/api/batch/{batch_id}/items/{item_id}")
async def review_batch_item(
    batch_id: str,
    item_id: str,
    body: ReviewAction,
    repo: MongoRepository = Depends(get_repo),
):
    item = repo.find_item(item_id)
    if not item or item.batch_id != batch_id:
        raise HTTPException(404, "Item not found.")
    repo.update_item_review(item_id, body.review_status, body.accepted_release_id)
    return {"ok": True}


# ── Global review (across all batches + single searches) ────────────────────


@router.get("/api/review/items")
async def get_all_review_items(
    review_status: ReviewStatus | None = Query(None),
    repo: MongoRepository = Depends(get_repo),
):
    items = repo.find_all_items(review_status=review_status)
    return [item.to_dict() for item in items]


@router.patch("/api/review/items/{item_id}")
async def review_item(
    item_id: str,
    body: ReviewAction,
    repo: MongoRepository = Depends(get_repo),
):
    item = repo.find_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found.")
    repo.update_item_review(item_id, body.review_status, body.accepted_release_id)
    return {"ok": True}


@router.post("/api/review/items/{item_id}/undo")
async def undo_review_item(item_id: str, repo: MongoRepository = Depends(get_repo)):
    item = repo.find_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found.")
    repo.update_item_review(item_id, ReviewStatus.UNREVIEWED, None)
    return {"ok": True}
