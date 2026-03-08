import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from deps import get_repo
from logger import get_logger
from repository.mongo import MongoRepository
from services.collection_sync import sync_full_collection

log = get_logger("routes.collection")

router = APIRouter()


@router.get("/api/collection")
async def collection(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("artist"),
    sort_order: str = Query("asc"),
    q: str = Query(""),
    repo: MongoRepository = Depends(get_repo),
):
    """Return the user's collection from the local MongoDB store."""
    skip = (page - 1) * per_page
    query = q.strip() or None
    items = repo.find_collection_items(
        query=query, sort=sort, sort_order=sort_order,
        skip=skip, limit=per_page,
    )
    total = repo.count_collection_items(query=query)
    pages = max(1, (total + per_page - 1) // per_page)

    return {
        "items": [item.to_dict() for item in items],
        "page": page,
        "pages": pages,
        "per_page": per_page,
        "total_items": total,
    }


@router.post("/api/collection/sync")
async def trigger_sync(repo: MongoRepository = Depends(get_repo)):
    """Trigger a full collection sync from Discogs."""
    status = repo.get_sync_status()
    if status.get("status") == "syncing":
        raise HTTPException(status_code=409, detail="Sync already in progress.")
    asyncio.create_task(_run_sync(repo))
    return {"message": "Sync started."}


@router.get("/api/collection/sync")
async def sync_status(repo: MongoRepository = Depends(get_repo)):
    """Return current sync status."""
    return repo.get_sync_status()


async def _run_sync(repo: MongoRepository) -> None:
    try:
        await asyncio.to_thread(sync_full_collection, repo)
    except Exception as e:
        log.error("Background sync failed: %s", e, exc_info=True)
