from __future__ import annotations

import time

from config import DEV_MODE
from models import DiscogsResult, LabelData, SearchResponse
from services.discogs import prefilter, score_by_metadata, search_with_strategy
from services.vision import rank_results, read_label_image
from logger import get_logger

log = get_logger("services.search")


def _build_debug(
    cache_hit: bool,
    strategies_tried: list[str],
    timing_ms: dict,
    label_data: dict,
    **extras: object,
) -> dict:
    debug = {
        "cache_hit": cache_hit,
        "strategies_tried": strategies_tried,
        "timing_ms": timing_ms,
        "llm_label_response": label_data,
    }
    debug.update(extras)
    return debug


def process_single_image(image_bytes: bytes, content_type: str, media_type: str = "vinyl") -> SearchResponse:
    """Run the full search pipeline for a single image.

    Raises on failure (callers handle errors).
    """
    # 1. Vision — extract label data
    t0 = time.time()
    label_data, conversation, cache_hit = read_label_image(image_bytes, content_type, media_type)
    vision_ms = (time.time() - t0) * 1000

    candidate_albums = label_data.get("albums", [])
    candidate_artists = label_data.get("artists", [])

    # Handle "Not present in label" — treat as self-titled album
    _sentinel = "Not present in label"
    albums_missing = all(a.strip().lower() == _sentinel.lower() for a in candidate_albums) if candidate_albums else True
    artists_missing = all(a.strip().lower() == _sentinel.lower() for a in candidate_artists) if candidate_artists else True

    if albums_missing and not artists_missing:
        candidate_albums = list(candidate_artists)
        label_data["albums"] = candidate_albums
        log.info("Album not present on label — assuming self-titled: %s", candidate_albums)
    elif artists_missing and not albums_missing:
        candidate_artists = list(candidate_albums)
        label_data["artists"] = candidate_artists
        log.info("Artist not present on label — assuming self-titled: %s", candidate_artists)

    label_meta = {
        k: label_data[k]
        for k in ("country", "format", "label", "catno", "year")
        if label_data.get(k)
    }

    log.info(
        "Label extracted: albums=%s artists=%s meta=%s",
        candidate_albums, candidate_artists, label_meta,
    )

    if not candidate_albums or not candidate_artists or (albums_missing and artists_missing):
        raise ValueError("Could not extract album or artist from the label image.")

    # 2. Discogs search
    t1 = time.time()
    releases, strategy, strategies_tried = search_with_strategy(
        candidate_albums, candidate_artists, label_meta, media_type=media_type,
    )
    search_ms = (time.time() - t1) * 1000

    log.info("Discogs search: strategy='%s' results=%d", strategy, len(releases))

    if not releases:
        resp = SearchResponse(
            label_data=LabelData(**label_data),
            strategy=strategy,
            results=[],
            total=0,
        )
        if DEV_MODE:
            resp.debug = _build_debug(
                cache_hit, strategies_tried,
                {"vision": round(vision_ms, 1), "search": round(search_ms, 1)},
                label_data,
            )
        return resp

    # 3. Pre-filter
    before_count = len(releases)
    releases = prefilter(releases, candidate_artists)
    after_count = len(releases)
    log.info("Prefilter: %d → %d releases", before_count, after_count)

    # 3b. Metadata scoring (year/country)
    before_meta = len(releases)
    releases = score_by_metadata(releases, label_meta)
    after_meta = len(releases)
    log.info("Metadata filter: %d → %d releases", before_meta, after_meta)

    # 4. LLM ranking
    t2 = time.time()
    likeliness, discarded = rank_results(releases, conversation, media_type)
    ranking_ms = (time.time() - t2) * 1000
    log.info("Ranking: %d ordered, %d discarded", len(likeliness), len(discarded))

    # 5. Build ordered results
    discarded_set = set(discarded)
    seen: set[int] = set()
    ordered = []
    for idx in likeliness:
        if idx not in discarded_set and 0 <= idx < len(releases) and idx not in seen:
            ordered.append(releases[idx])
            seen.add(idx)
    for idx, r in enumerate(releases):
        if idx not in seen and idx not in discarded_set:
            ordered.append(r)
            seen.add(idx)

    # 5b. Tiebreaker: when two results share the same title but one has a cover image
    # and the other doesn't, promote the one with the image.
    for i in range(len(ordered) - 1):
        a, b = ordered[i], ordered[i + 1]
        if a.get("title") == b.get("title") and not a.get("cover_image") and b.get("cover_image"):
            ordered[i], ordered[i + 1] = b, a

    # Safety net: if ranking discarded everything, keep results in likeliness order
    if not ordered and releases:
        log.warning("Ranking discarded all %d results, keeping them in likeliness order", len(releases))
        seen.clear()
        for idx in likeliness:
            if 0 <= idx < len(releases) and idx not in seen:
                ordered.append(releases[idx])
                seen.add(idx)
        for idx, r in enumerate(releases):
            if idx not in seen:
                ordered.append(r)
                seen.add(idx)

    results = [
        DiscogsResult(
            discogs_id=r.get("id"),
            title=r.get("title"),
            year=int(r["year"]) if r.get("year") else None,
            country=r.get("country"),
            format=", ".join(r.get("format", [])),
            label=", ".join(r.get("label", [])),
            catno=r.get("catno"),
            discogs_url=f"https://www.discogs.com{r['uri']}" if r.get("uri") else None,
            cover_image=r.get("cover_image"),
        )
        for r in ordered
    ]

    resp = SearchResponse(
        label_data=LabelData(**label_data),
        strategy=strategy,
        results=results,
        total=len(results),
    )

    if DEV_MODE:
        resp.debug = _build_debug(
            cache_hit, strategies_tried,
            {
                "vision": round(vision_ms, 1),
                "search": round(search_ms, 1),
                "ranking": round(ranking_ms, 1),
            },
            label_data,
            prefilter={"before": before_count, "after": after_count},
            metadata_filter={"before": before_meta, "after": after_meta},
            ranking={"likeliness": likeliness, "discarded": discarded},
        )

    return resp
