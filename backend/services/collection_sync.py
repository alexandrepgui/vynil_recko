import time
from datetime import datetime, timezone

from logger import get_logger
from repository.models import CollectionItem
from repository.mongo import MongoRepository
from services.discogs import get_collection, get_master_cover
from services.discogs_auth import OAuthTokens

log = get_logger("services.collection_sync")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sync_full_collection(repo: MongoRepository, user_id: str, tokens: OAuthTokens) -> dict:
    """Fetch every page from Discogs and upsert into MongoDB.

    Returns a summary with counts of synced/removed items.
    """
    sync_started_at = _now_iso()
    repo.update_sync_status(user_id, {
        "status": "syncing",
        "started_at": sync_started_at,
        "error": None,
        "total_items": 0,
        "items_synced": 0,
    })

    page = 1
    total_synced = 0
    # Cache master covers across pages so we only fetch each master once
    master_cover_cache: dict[int, str | None] = {}

    try:
        while True:
            data = get_collection(tokens=tokens, page=page, per_page=100, sort="added", sort_order="desc")
            releases = data.get("releases", [])
            if not releases:
                break

            items = [_transform_release(r, user_id) for r in releases]

            # Backfill missing covers from master releases
            _backfill_master_covers(items, tokens, master_cover_cache)

            repo.upsert_collection_items_bulk(items)
            total_synced += len(items)

            pagination = data.get("pagination", {})
            repo.update_sync_status(user_id, {
                "total_items": pagination.get("items", 0),
                "items_synced": total_synced,
            })

            if page >= pagination.get("pages", 1):
                break
            page += 1
            time.sleep(1)  # respect Discogs rate limit (60 req/min)

        # Items not touched during this sync are no longer in the collection
        removed = repo.delete_stale_items(user_id, sync_started_at)

        repo.update_sync_status(user_id, {
            "status": "idle",
            "completed_at": _now_iso(),
            "total_items": total_synced,
            "items_synced": total_synced,
            "items_removed": removed,
        })
        log.info("Collection sync complete for user_id=%s: %d synced, %d removed", user_id, total_synced, removed)
        return {"synced": total_synced, "removed": removed}

    except Exception as e:
        log.error("Collection sync failed for user_id=%s: %s", user_id, e, exc_info=True)
        repo.update_sync_status(user_id, {"status": "error", "error": str(e)})
        raise


def _backfill_master_covers(
    items: list[CollectionItem],
    tokens: OAuthTokens,
    cache: dict[int, str | None],
) -> None:
    """Prefer master cover over release cover — master has canonical artwork."""
    has_master: dict[int, int] = {}  # index → master_id
    for i, item in enumerate(items):
        if item.master_id:
            has_master[i] = item.master_id

    if not has_master:
        return

    # Fetch unique master covers not already cached
    unique_masters = set(has_master.values()) - set(cache.keys())
    for master_id in unique_masters:
        cache[master_id] = get_master_cover(master_id, tokens)
        time.sleep(1)  # respect rate limit

    # Apply cached covers
    filled = 0
    for i, master_id in has_master.items():
        cover = cache.get(master_id)
        if cover:
            items[i].cover_image = cover
            filled += 1

    if filled:
        log.info("Applied %d master covers from %d master release(s)",
                 filled, len(unique_masters))


def _transform_release(r: dict, user_id: str = "") -> CollectionItem:
    """Transform a Discogs API release dict into a CollectionItem."""
    info = r.get("basic_information", {})
    artists = ", ".join(a.get("name", "") for a in info.get("artists", []))
    formats = info.get("formats", [])
    format_name = formats[0].get("name", "") if formats else ""
    cover = info.get("cover_image") or info.get("thumb") or None
    return CollectionItem(
        user_id=user_id,
        instance_id=r.get("instance_id", 0),
        release_id=info.get("id", 0),
        title=info.get("title", ""),
        artist=artists,
        year=info.get("year", 0),
        genres=info.get("genres", []),
        styles=info.get("styles", []),
        format=format_name,
        cover_image=cover,
        master_id=info.get("master_id"),
        date_added=r.get("date_added"),
    )
