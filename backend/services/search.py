from __future__ import annotations

import re
import time

from config import DEV_MODE, DISCOGS_SPACER_GIF, LLM_PRICING, MAX_RANKING_RESULTS
from deps import get_repo
from models import DiscogsResult, LabelData, SearchResponse
from repository import LLMUsageRecord
from services.discogs import generate_search_candidates, get_master_cover, prefilter, score_by_metadata
from services.discogs_auth import OAuthTokens
from services.llm import LLMResponse
from services.vision import rank_results, read_label_image
from logger import get_logger

log = get_logger("services.search")


def _dedup_case_insensitive(items: list[str]) -> list[str]:
    """Remove case-only duplicates, keeping the first occurrence."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _has_cover_image(release: dict) -> bool:
    """Return True if the release has a real cover image (not a Discogs spacer placeholder)."""
    url = release.get("cover_image")
    return bool(url) and DISCOGS_SPACER_GIF not in url


def _calculate_cost(llm_response: LLMResponse) -> float:
    """Estimate cost in USD from token usage and known pricing."""
    pricing = LLM_PRICING.get(llm_response.model)
    if not pricing:
        return 0.0
    input_cost = llm_response.prompt_tokens * pricing["input"] / 1_000_000
    output_cost = llm_response.completion_tokens * pricing["output"] / 1_000_000
    return input_cost + output_cost


def _log_llm_usage(
    operation: str,
    llm_response: LLMResponse | None,
    cache_hit: bool = False,
    batch_id: str | None = None,
    item_id: str | None = None,
    user_id: str = "",
) -> None:
    """Persist an LLM usage record. Skip on cache hits or missing response."""
    if cache_hit or llm_response is None:
        return
    try:
        repo = get_repo()
        record = LLMUsageRecord(
            user_id=user_id,
            provider=llm_response.provider,
            model=llm_response.model,
            operation=operation,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            total_tokens=llm_response.total_tokens,
            cost_usd=_calculate_cost(llm_response),
            batch_id=batch_id,
            item_id=item_id,
            cache_hit=False,
        )
        repo.save_llm_usage(record)
    except Exception as e:
        log.warning("Failed to log LLM usage: %s", e)


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


def _build_ordered(releases: list[dict], likeliness: list[int], discarded: list[int]) -> list[dict]:
    """Build an ordered result list from LLM ranking output.

    Includes releases in likeliness order (excluding discarded), then any
    remaining releases not mentioned in either list.
    """
    discarded_set = {d for d in discarded if isinstance(d, int)}
    likeliness = [i for i in likeliness if isinstance(i, int)]
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
    return ordered


def _group_key(r: dict) -> str:
    """Group key for tiebreaker: catno (most reliable), then normalized title."""
    catno = (r.get("catno") or "").strip()
    if catno:
        return catno.lower()
    # Fallback: normalized title (strip year suffix, lowercase)
    title = r.get("title") or ""
    return re.sub(r'\s*\(\d{4}\)\s*$', '', title).strip().lower()


def _apply_cover_image_tiebreaker(ordered: list[dict]) -> list[dict]:
    """Within groups of same-release results, promote entries with a real cover image.

    Groups by catno (most reliable) or normalized title. Stable sort preserves
    the LLM's original ordering within each subgroup.
    """
    result = list(ordered)
    i = 0
    while i < len(result):
        key_i = _group_key(result[i])
        j = i + 1
        while j < len(result) and _group_key(result[j]) == key_i:
            j += 1
        if j - i > 1:
            result[i:j] = sorted(result[i:j], key=lambda r: not _has_cover_image(r))
        i = j
    return result


def _to_discogs_results(ordered: list[dict], *, is_master_fallback: bool = False) -> list[DiscogsResult]:
    """Convert raw Discogs dicts to DiscogsResult models."""
    return [
        DiscogsResult(
            discogs_id=r.get("id"),
            title=r.get("title"),
            year=int(r["year"]) if r.get("year") else None,
            country=r.get("country"),
            format=", ".join(r.get("format", [])),
            label=", ".join(r.get("label", [])),
            catno=r.get("catno"),
            discogs_url=f"https://www.discogs.com{r['uri']}" if r.get("uri") else None,
            cover_image=r.get("cover_image") if _has_cover_image(r) else None,
            master_id=r.get("master_id") or None,
            is_master_fallback=is_master_fallback,
        )
        for r in ordered
    ]


def process_single_image(
    image_bytes: bytes,
    content_type: str,
    tokens: OAuthTokens,
    media_type: str = "vinyl",
    batch_id: str | None = None,
    item_id: str | None = None,
    user_id: str = "",
) -> SearchResponse:
    """Run the full search pipeline for a single image.

    Raises on failure (callers handle errors).
    """
    # ── Step 1: Vision ──
    t0 = time.time()
    label_data, conversation, cache_hit, vision_usage = read_label_image(image_bytes, content_type, media_type)
    vision_ms = (time.time() - t0) * 1000

    _log_llm_usage("label_reading", vision_usage, cache_hit=cache_hit, batch_id=batch_id, item_id=item_id, user_id=user_id)

    candidate_albums = _dedup_case_insensitive([a for a in (label_data.get("albums") or []) if a])
    candidate_artists = _dedup_case_insensitive([a for a in (label_data.get("artists") or []) if a])
    candidate_tracks = [t for t in (label_data.get("tracks") or []) if t]
    label_data["albums"] = candidate_albums or label_data.get("albums")
    label_data["artists"] = candidate_artists or label_data.get("artists")

    # Handle null / empty — treat as self-titled album
    albums_missing = candidate_albums is None or len(candidate_albums) == 0
    artists_missing = candidate_artists is None or len(candidate_artists) == 0

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
        "Label extracted: albums=%s artists=%s tracks=%s meta=%s",
        candidate_albums, candidate_artists, candidate_tracks, label_meta,
    )

    has_artist_album = candidate_albums and candidate_artists and not (albums_missing and artists_missing)
    if not has_artist_album and not candidate_tracks:
        raise ValueError("Could not extract album, artist, or track names from the label image.")

    # Ensure albums/artists are lists (not None) for downstream code
    if not candidate_albums:
        candidate_albums = []
        label_data["albums"] = []
    if not candidate_artists:
        candidate_artists = []
        label_data["artists"] = []

    # ── Step 2: Search + Evaluate ──
    t1 = time.time()
    strategies_tried: list[str] = []
    ordered: list[dict] = []
    winning_strategy = "exhausted all strategies"
    ranking_ms = 0.0

    for candidates, strategy in generate_search_candidates(
        candidate_albums or [], candidate_artists or [], label_meta,
        media_type=media_type, tried=strategies_tried,
        candidate_tracks=candidate_tracks,
        tokens=tokens,
    ):
        # Master fallback: guaranteed result — skip filtering and LLM ranking
        if strategy == "master fallback":
            ordered = candidates
            winning_strategy = strategy
            break

        # Skip artist prefilter for track-name strategies (no artist to filter on)
        if candidate_artists and "track names" not in strategy:
            filtered = prefilter(candidates, candidate_artists)
        else:
            filtered = candidates
        scored = score_by_metadata(filtered, label_meta, candidate_albums, candidate_artists)

        # Rank in batches of MAX_RANKING_RESULTS — if the LLM rejects a batch,
        # send the next batch before falling through to the next strategy.
        for batch_start in range(0, len(scored), MAX_RANKING_RESULTS):
            batch = scored[batch_start:batch_start + MAX_RANKING_RESULTS]

            t2 = time.time()
            likeliness, discarded, ranking_usage = rank_results(
                batch, list(conversation), media_type,
            )
            ranking_ms = (time.time() - t2) * 1000

            _log_llm_usage("ranking", ranking_usage, batch_id=batch_id, item_id=item_id, user_id=user_id)

            ordered = _build_ordered(batch, likeliness, discarded)
            if ordered:
                winning_strategy = strategy
                break
            log.info("Strategy '%s': LLM rejected batch %d–%d (%d candidates)",
                     strategy, batch_start, batch_start + len(batch), len(batch))

        if ordered:
            break
        strategies_tried.append(f"{strategy} (LLM rejected all {len(scored)})")
        log.info("Strategy '%s': LLM rejected all %d, trying next", strategy, len(scored))

    search_ms = (time.time() - t1) * 1000

    # ── Step 2b: Prefer master covers ──
    # Always use the master cover when available — release covers are often
    # low-quality label photos, while the master has the canonical artwork.
    master_cover_cache: dict[int, str | None] = {}
    for r in ordered:
        mid = r.get("master_id")
        if mid:
            if mid not in master_cover_cache:
                master_cover_cache[mid] = get_master_cover(mid, tokens)
            cover = master_cover_cache[mid]
            if cover:
                r["cover_image"] = cover

    # ── Step 3: Tiebreaker ──
    ordered = _apply_cover_image_tiebreaker(ordered)

    # ── Step 4: Response ──
    results = _to_discogs_results(ordered, is_master_fallback=winning_strategy == "master fallback")

    resp = SearchResponse(
        label_data=LabelData(**label_data),
        strategy=winning_strategy,
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
        )

    return resp
