import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import User, get_current_user
from deps import get_repo
from logger import get_logger
from repository.mongo import MongoRepository
from services.collection_sync import sync_full_collection
from services.discogs_auth import load_tokens_for_user

log = get_logger("routes.collection")

router = APIRouter()


@router.get("/api/collection")
async def collection(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("artist"),
    sort_order: str = Query("asc"),
    q: str = Query(""),
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Return the user's collection from the local MongoDB store."""
    skip = (page - 1) * per_page
    query = q.strip() or None
    items = repo.find_collection_items(
        user.id, query=query, sort=sort, sort_order=sort_order,
        skip=skip, limit=per_page,
    )
    total = repo.count_collection_items(user.id, query=query)
    pages = max(1, (total + per_page - 1) // per_page)

    return {
        "items": [item.to_dict() for item in items],
        "page": page,
        "pages": pages,
        "per_page": per_page,
        "total_items": total,
    }


@router.post("/api/collection/sync")
async def trigger_sync(
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Trigger a full collection sync from Discogs."""
    status = repo.get_sync_status(user.id)
    if status.get("status") == "syncing":
        raise HTTPException(status_code=409, detail="Sync already in progress.")

    tokens = load_tokens_for_user(repo, user.id)
    if not tokens:
        raise HTTPException(status_code=400, detail="Discogs account not connected. Link your Discogs account first.")

    asyncio.create_task(_run_sync(repo, user.id, tokens))
    return {"message": "Sync started."}


@router.get("/api/collection/sync")
async def sync_status(
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Return current sync status."""
    return repo.get_sync_status(user.id)


async def _run_sync(repo: MongoRepository, user_id: str, tokens) -> None:
    try:
        await asyncio.to_thread(sync_full_collection, repo, user_id, tokens)
    except Exception as e:
        log.error("Background sync failed for user_id=%s: %s", user_id, e, exc_info=True)
