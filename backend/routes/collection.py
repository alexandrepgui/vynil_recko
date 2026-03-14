import asyncio
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth import User, get_current_user
from deps import get_repo
from logger import get_logger
from repository.mongo import MongoRepository
from services.collection_sync import sync_full_collection
from services.discogs import get_master_cover, remove_from_collection
from services.discogs_auth import require_discogs_tokens

log = get_logger("routes.collection")

router = APIRouter()


def _paginated_collection(
    repo: MongoRepository,
    user_id: str,
    page: int,
    per_page: int,
    sort: str,
    sort_order: str,
    q: str,
) -> dict:
    """Shared pagination logic for collection endpoints."""
    skip = (page - 1) * per_page
    query = q.strip() or None
    items = repo.find_collection_items(
        user_id, query=query, sort=sort, sort_order=sort_order,
        skip=skip, limit=per_page,
    )
    total = repo.count_collection_items(user_id, query=query)
    pages = max(1, (total + per_page - 1) // per_page)
    return {
        "items": [item.to_dict() for item in items],
        "page": page,
        "pages": pages,
        "per_page": per_page,
        "total_items": total,
    }


@router.get("/api/collection")
async def collection(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=250),
    sort: str = Query("artist"),
    sort_order: str = Query("asc"),
    q: str = Query(""),
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Return the user's collection from the local MongoDB store."""
    return _paginated_collection(repo, user.id, page, per_page, sort, sort_order, q)


@router.post("/api/collection/sync")
async def trigger_sync(
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Trigger a full collection sync from Discogs."""
    status = repo.get_sync_status(user.id)
    if status.get("status") == "syncing":
        raise HTTPException(status_code=409, detail="Sync already in progress.")

    tokens = require_discogs_tokens(repo, user.id)

    asyncio.create_task(_run_sync(repo, user.id, tokens))
    return {"message": "Sync started."}


@router.get("/api/collection/sync")
async def sync_status(
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Return current sync status."""
    return repo.get_sync_status(user.id)


class DeleteCollectionRequest(BaseModel):
    instance_ids: list[int] = Field(..., min_length=1, max_length=250)


@router.delete("/api/collection")
async def delete_collection_items(
    body: DeleteCollectionRequest,
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Remove items from the user's collection (both Discogs and local DB)."""
    tokens = require_discogs_tokens(repo, user.id)

    # Look up release_ids for each instance_id
    items = repo.find_collection_items_by_instance_ids(user.id, body.instance_ids)
    item_map = {item.instance_id: item.release_id for item in items}

    errors: list[dict] = []
    deleted = 0

    for instance_id in body.instance_ids:
        release_id = item_map.get(instance_id)
        if release_id is None:
            errors.append({"instance_id": instance_id, "error": "Not found in local collection"})
            continue
        try:
            await asyncio.to_thread(
                remove_from_collection, release_id, instance_id, tokens,
            )
            deleted += 1
        except Exception as exc:
            log.warning(
                "Failed to remove instance %d (release %d) from Discogs: %s",
                instance_id, release_id, exc,
            )
            errors.append({"instance_id": instance_id, "error": str(exc)})

    # Remove successfully-deleted items from local DB
    successfully_deleted_ids = [
        iid for iid in body.instance_ids
        if iid not in {e["instance_id"] for e in errors}
    ]
    if successfully_deleted_ids:
        repo.delete_collection_items(user.id, successfully_deleted_ids)

    return {"deleted": deleted, "errors": errors}


async def _run_sync(repo: MongoRepository, user_id: str, tokens) -> None:
    try:
        await asyncio.to_thread(sync_full_collection, repo, user_id, tokens)
    except Exception as e:
        log.error("Background sync failed for user_id=%s: %s", user_id, e, exc_info=True)


# ── Cover art endpoints ──────────────────────────────────────────────────────


@router.get("/api/collection/{instance_id}/cover/master")
async def preview_master_cover(
    instance_id: int,
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Fetch master cover URL from Discogs for preview (does not persist)."""
    item = repo.find_collection_item(user.id, instance_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")
    if not item.master_id:
        raise HTTPException(status_code=400, detail="This release has no master release.")

    tokens = require_discogs_tokens(repo, user.id)
    cover = await asyncio.to_thread(get_master_cover, item.master_id, tokens)
    if not cover:
        raise HTTPException(status_code=404, detail="No cover found for this master release.")

    return {"cover_url": cover}


@router.post("/api/collection/{instance_id}/cover/master")
async def use_master_cover(
    instance_id: int,
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Fetch master cover from Discogs and set it as custom cover."""
    item = repo.find_collection_item(user.id, instance_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")
    if not item.master_id:
        raise HTTPException(status_code=400, detail="This release has no master release.")

    tokens = require_discogs_tokens(repo, user.id)
    cover = await asyncio.to_thread(get_master_cover, item.master_id, tokens)
    if not cover:
        raise HTTPException(status_code=404, detail="No cover found for this master release.")

    repo.update_collection_item_cover(user.id, instance_id, cover)
    return {"custom_cover_image": cover}


class SetCoverRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)


def _get_allowed_cover_prefix() -> str:
    """Return the Supabase Storage public URL prefix for the covers bucket."""
    supabase_url = os.getenv("SUPABASE_URL", os.getenv("VITE_SUPABASE_URL", "http://127.0.0.1:54321"))
    return f"{supabase_url.rstrip('/')}/storage/v1/object/public/covers/"


@router.put("/api/collection/{instance_id}/cover")
async def set_custom_cover(
    instance_id: int,
    body: SetCoverRequest,
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Set a custom cover image URL."""
    allowed_prefix = _get_allowed_cover_prefix()
    # Strip cache-bust query params before checking prefix
    url_without_query = body.url.split("?")[0]
    if not url_without_query.startswith(allowed_prefix):
        raise HTTPException(
            status_code=400,
            detail="Cover URL must point to Supabase Storage covers bucket.",
        )

    item = repo.find_collection_item(user.id, instance_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")

    repo.update_collection_item_cover(user.id, instance_id, body.url)
    return {"custom_cover_image": body.url}


@router.delete("/api/collection/{instance_id}/cover")
async def reset_cover(
    instance_id: int,
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Reset cover to default (clear custom_cover_image)."""
    item = repo.find_collection_item(user.id, instance_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")

    repo.update_collection_item_cover(user.id, instance_id, None)
    return {"custom_cover_image": None}


# Public collection endpoint — placed last so /api/collection/sync is matched first.
@router.get("/api/collection/{username}")
async def public_collection(
    username: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=250),
    sort: str = Query("artist"),
    sort_order: str = Query("asc"),
    q: str = Query(""),
    repo: MongoRepository = Depends(get_repo),
):
    """Return a public collection by username. No auth required."""
    user_id = repo.find_user_id_by_username(username)
    if not user_id:
        raise HTTPException(status_code=404, detail="Collection not found.")

    settings = repo.get_user_settings(user_id)
    if not settings.get("collection_public"):
        raise HTTPException(status_code=404, detail="Collection not found.")

    result = _paginated_collection(repo, user_id, page, per_page, sort, sort_order, q)
    result["owner"] = {
        "username": username,
        "avatar_url": settings.get("avatar_url"),
    }
    return result
