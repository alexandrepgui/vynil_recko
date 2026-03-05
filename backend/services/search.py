from __future__ import annotations

from models import DiscogsResult, LabelData, SearchResponse
from services.discogs import prefilter, search_with_strategy
from services.vision import rank_results, read_label_image
from logger import get_logger

log = get_logger("services.search")


def process_single_image(image_bytes: bytes, content_type: str, media_type: str = "vinyl") -> SearchResponse:
    """Run the full search pipeline for a single image.

    Raises on failure (callers handle errors).
    """
    # 1. Vision — extract label data
    label_data, conversation, cache_hit = read_label_image(image_bytes, content_type, media_type)

    candidate_albums = label_data.get("albums", [])
    candidate_artists = label_data.get("artists", [])
    label_meta = {
        k: label_data[k]
        for k in ("country", "format", "label", "catno", "year")
        if label_data.get(k)
    }

    log.info(
        "Label extracted: albums=%s artists=%s meta=%s",
        candidate_albums, candidate_artists, label_meta,
    )

    if not candidate_albums or not candidate_artists:
        raise ValueError("Could not extract album or artist from the label image.")

    # 2. Discogs search
    releases, strategy, strategies_tried = search_with_strategy(
        candidate_albums, candidate_artists, label_meta, media_type=media_type,
    )

    log.info("Discogs search: strategy='%s' results=%d", strategy, len(releases))

    if not releases:
        return SearchResponse(
            label_data=LabelData(**label_data),
            strategy=strategy,
            results=[],
            total=0,
        )

    # 3. Pre-filter
    before_count = len(releases)
    releases = prefilter(releases, candidate_artists)
    log.info("Prefilter: %d → %d releases", before_count, len(releases))

    # 4. LLM ranking
    likeliness, discarded = rank_results(releases, conversation, media_type)
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

    return SearchResponse(
        label_data=LabelData(**label_data),
        strategy=strategy,
        results=results,
        total=len(results),
    )
