import requests
from fastapi import APIRouter, HTTPException, Query

from logger import get_logger
from services.discogs import get_collection

log = get_logger("routes.collection")

router = APIRouter()


@router.get("/api/collection")
async def collection(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("artist"),
    sort_order: str = Query("asc"),
):
    """Return the authenticated user's Discogs collection."""
    log.info("Collection request: page=%d per_page=%d sort=%s sort_order=%s", page, per_page, sort, sort_order)
    try:
        data = get_collection(page=page, per_page=per_page, sort=sort, sort_order=sort_order)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 502
        log.error("Discogs collection API failed: %s", e)
        if status == 401:
            raise HTTPException(status_code=401, detail="Not authenticated with Discogs.")
        raise HTTPException(status_code=502, detail=f"Discogs API error: {e}")
    except Exception as e:
        log.error("Unexpected error fetching collection: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=f"Discogs API error: {e}")

    releases = data.get("releases", [])
    pagination = data.get("pagination", {})

    items = []
    for r in releases:
        info = r.get("basic_information", {})
        artists = ", ".join(a.get("name", "") for a in info.get("artists", []))
        genres = info.get("genres", [])
        styles = info.get("styles", [])
        formats = info.get("formats", [])
        format_name = formats[0].get("name", "") if formats else ""
        cover = info.get("cover_image") or info.get("thumb") or None
        items.append({
            "id": info.get("id"),
            "instance_id": r.get("instance_id"),
            "title": info.get("title", ""),
            "artist": artists,
            "year": info.get("year", 0),
            "genres": genres,
            "styles": styles,
            "format": format_name,
            "cover_image": cover,
            "date_added": r.get("date_added"),
        })

    return {
        "items": items,
        "page": pagination.get("page", page),
        "pages": pagination.get("pages", 1),
        "per_page": pagination.get("per_page", per_page),
        "total_items": pagination.get("items", len(items)),
    }
