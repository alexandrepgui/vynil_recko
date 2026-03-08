import time
from datetime import datetime, timezone

from logger import get_logger
from repository.models import CollectionItem
from repository.mongo import MongoRepository
from services.discogs import get_collection

log = get_logger("services.collection_sync")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sync_full_collection(repo: MongoRepository) -> dict:
    """Fetch every page from Discogs and upsert into MongoDB.

    Returns a summary with counts of synced/removed items.
    """
    sync_started_at = _now_iso()
    repo.update_sync_status({
        "status": "syncing",
        "started_at": sync_started_at,
        "error": None,
        "total_items": 0,
        "items_synced": 0,
    })

    page = 1
    total_synced = 0

    try:
        while True:
            data = get_collection(page=page, per_page=100, sort="added", sort_order="desc")
            releases = data.get("releases", [])
            if not releases:
                break

            items = [_transform_release(r) for r in releases]
            repo.upsert_collection_items_bulk(items)
            total_synced += len(items)

            pagination = data.get("pagination", {})
            repo.update_sync_status({
                "total_items": pagination.get("items", 0),
                "items_synced": total_synced,
            })

            if page >= pagination.get("pages", 1):
                break
            page += 1
            time.sleep(1)  # respect Discogs rate limit (60 req/min)

        # Items not touched during this sync are no longer in the collection
        removed = repo.delete_stale_items(sync_started_at)

        repo.update_sync_status({
            "status": "idle",
            "completed_at": _now_iso(),
            "total_items": total_synced,
            "items_synced": total_synced,
            "items_removed": removed,
        })
        log.info("Collection sync complete: %d synced, %d removed", total_synced, removed)
        return {"synced": total_synced, "removed": removed}

    except Exception as e:
        log.error("Collection sync failed: %s", e, exc_info=True)
        repo.update_sync_status({"status": "error", "error": str(e)})
        raise


def _transform_release(r: dict) -> CollectionItem:
    """Transform a Discogs API release dict into a CollectionItem."""
    info = r.get("basic_information", {})
    artists = ", ".join(a.get("name", "") for a in info.get("artists", []))
    formats = info.get("formats", [])
    format_name = formats[0].get("name", "") if formats else ""
    cover = info.get("cover_image") or info.get("thumb") or None
    return CollectionItem(
        instance_id=r.get("instance_id", 0),
        release_id=info.get("id", 0),
        title=info.get("title", ""),
        artist=artists,
        year=info.get("year", 0),
        genres=info.get("genres", []),
        styles=info.get("styles", []),
        format=format_name,
        cover_image=cover,
        date_added=r.get("date_added"),
    )
