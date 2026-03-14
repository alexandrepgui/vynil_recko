"""Collection export endpoint: CSV, Excel, PDF."""

from __future__ import annotations

import asyncio
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from auth import User, get_current_user
from deps import get_repo
from logger import get_logger
from repository.mongo import MongoRepository
from services.export import generate_csv, generate_pdf, generate_xlsx

log = get_logger("routes.export")

router = APIRouter()

_MEDIA_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}

_FILENAMES = {
    "csv": "groove-log-collection.csv",
    "xlsx": "groove-log-collection.xlsx",
    "pdf": "groove-log-collection.pdf",
}

_GENERATORS = {
    "csv": generate_csv,
    "xlsx": generate_xlsx,
    "pdf": generate_pdf,
}


@router.get("/api/collection/export")
async def export_collection(
    format: str = Query(..., pattern="^(csv|xlsx|pdf)$"),
    sort: str = Query("artist"),
    sort_order: str = Query("asc"),
    q: str = Query(""),
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
) -> StreamingResponse:
    query = q.strip() or None

    items = await asyncio.to_thread(
        repo.find_collection_items,
        user.id,
        query=query,
        sort=sort,
        sort_order=sort_order,
        skip=0,
        limit=0,
    )

    generator = _GENERATORS[format]
    if format == "pdf":
        # Get Discogs username for the PDF title page
        tokens = repo.load_oauth_tokens(user.id)
        display_name = (tokens or {}).get("username") or user.name or user.email or "collector"
        content = await asyncio.to_thread(generator, items, display_name)
    else:
        content = await asyncio.to_thread(generator, items)

    log.info("Exported %d items as %s for user_id=%s", len(items), format, user.id)

    return StreamingResponse(
        io.BytesIO(content),
        media_type=_MEDIA_TYPES[format],
        headers={
            "Content-Disposition": f'attachment; filename="{_FILENAMES[format]}"',
        },
    )
