import os
from difflib import SequenceMatcher

import requests

from config import DISCOGS_BASE_URL, DISCOGS_USER_AGENT
from logger import get_logger
from services.discogs_auth import build_oauth_headers, get_current_tokens

log = get_logger("services.discogs")


def _headers() -> dict:
    """Build auth headers: prefer OAuth tokens, fall back to personal token."""
    tokens = get_current_tokens()
    if tokens:
        return build_oauth_headers(tokens)
    token = os.getenv("DISCOGS_TOKEN")
    return {
        "User-Agent": DISCOGS_USER_AGENT,
        "Authorization": f"Discogs token={token}",
    }


def discogs_search(max_pages: int = 10, **params) -> list[dict]:
    """Search Discogs with arbitrary params, paginating through all results."""
    params.setdefault("type", "release")
    params.setdefault("per_page", 50)
    all_results = []
    page = 1
    log.debug("discogs_search start: params=%s max_pages=%d", params, max_pages)
    while page <= max_pages:
        params["page"] = page
        resp = requests.get(
            f"{DISCOGS_BASE_URL}/database/search",
            headers=_headers(),
            params=params,
        )
        log.debug("Discogs API: page=%d status=%d", page, resp.status_code)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            log.debug("No results on page %d, stopping", page)
            break
        all_results.extend(results)
        log.debug("Page %d: %d results (total so far: %d)", page, len(results), len(all_results))
        if page >= data.get("pagination", {}).get("pages", 1):
            break
        page += 1
    log.info("discogs_search complete: %d total results", len(all_results))
    return all_results


def prefilter(releases: list[dict], candidate_artists: list[str]) -> list[dict]:
    """Drop results where none of the candidate artist names appear in the title."""
    artists_lower = {a.lower() for a in candidate_artists}
    filtered = [
        r for r in releases
        if any(a in r.get("title", "").lower() for a in artists_lower)
    ]
    if filtered:
        log.info("Prefilter: %d → %d (dropped %d)", len(releases), len(filtered), len(releases) - len(filtered))
    else:
        log.warning("Prefilter dropped ALL %d results, keeping originals", len(releases))
    # If filtering removes everything, keep the originals (better than nothing)
    return filtered if filtered else releases


_MEDIA_TYPE_TO_FORMAT = {"vinyl": "Vinyl", "cd": "CD"}

_SANITY_THRESHOLD = 0.4


def _best_similarity(candidates: list[str], text: str) -> float:
    """Return the highest SequenceMatcher ratio between any candidate and text."""
    text_lower = text.lower()
    return max(
        (SequenceMatcher(None, c.lower(), text_lower).ratio() for c in candidates),
        default=0.0,
    )


def _sanity_check(
    results: list[dict],
    candidate_albums: list[str],
    candidate_artists: list[str],
    threshold: float = _SANITY_THRESHOLD,
) -> list[dict]:
    """Keep only results where artist AND album have similarity >= threshold."""
    passed = []
    for r in results:
        title = r.get("title", "")
        # Discogs titles are "Artist - Album"
        parts = title.split(" - ", 1)
        r_artist = parts[0] if parts else title
        r_album = parts[1] if len(parts) > 1 else ""

        artist_sim = _best_similarity(candidate_artists, r_artist)
        album_sim = _best_similarity(candidate_albums, r_album)

        if artist_sim >= threshold and album_sim >= threshold:
            passed.append(r)
        else:
            log.debug(
                "Sanity check dropped: '%s' (artist_sim=%.2f, album_sim=%.2f)",
                title, artist_sim, album_sim,
            )
    return passed


def search_with_strategy(
    candidate_albums: list[str],
    candidate_artists: list[str],
    label_meta: dict,
    media_type: str = "vinyl",
) -> tuple[list[dict], str, list[str]]:
    """Try progressively looser search strategies. Returns (releases, strategy_used, strategies_tried)."""
    tried: list[str] = []
    fmt = {"format": _MEDIA_TYPE_TO_FORMAT[media_type]}

    def _try(results: list[dict], strategy: str) -> list[dict] | None:
        """Apply sanity check; return sane results or None to fall through."""
        sane = _sanity_check(results, candidate_albums, candidate_artists)
        if sane:
            log.info("Sanity check passed: %d/%d kept for '%s'", len(sane), len(results), strategy)
            return sane
        log.warning("Sanity check failed for '%s' (%d results all dropped), falling through", strategy, len(results))
        tried.append(f"{strategy} (sanity fail)")
        return None

    # 1. Catalog number + label (most precise)
    if label_meta.get("catno"):
        params = {"catno": label_meta["catno"], **fmt}
        if label_meta.get("label"):
            params["label"] = label_meta["label"]
        strategy = f"catno='{label_meta['catno']}'" + (
            f" + label='{label_meta['label']}'" if "label" in params else ""
        )
        log.info("Strategy 1: catno search — %s", params)
        results = discogs_search(**params)
        if results:
            sane = _try(results, strategy)
            if sane:
                return sane, strategy, tried

        if label_meta.get("label"):
            strategy_1b = f"catno='{label_meta['catno']}'"
            log.info("Strategy 1b: catno only (dropping label)")
            results = discogs_search(catno=label_meta["catno"], **fmt)
            if results:
                sane = _try(results, strategy_1b)
                if sane:
                    return sane, strategy_1b, tried

    # 2. Freeform query (q) with album + artist
    for album in candidate_albums:
        for artist in candidate_artists:
            query = f"{artist} {album}"
            strategy = f"q='{query}'"
            log.info("Strategy 2: freeform q='%s'", query)
            results = discogs_search(q=query, **fmt)
            if results:
                sane = _try(results, strategy)
                if sane:
                    return sane, strategy, tried

    # 3. Strict release_title + artist
    for album in candidate_albums:
        for artist in candidate_artists:
            strategy = f"release_title='{album}' + artist='{artist}'"
            log.info("Strategy 3: release_title='%s' artist='%s'", album, artist)
            results = discogs_search(artist=artist, release_title=album, **fmt)
            if results:
                sane = _try(results, strategy)
                if sane:
                    return sane, strategy, tried

    # 4. Artist-only search, fuzzy match titles
    for artist in candidate_artists:
        log.info("Strategy 4: artist-only '%s'", artist)
        artist_results = discogs_search(artist=artist, **fmt)
        if not artist_results:
            tried.append(f"artist='{artist}' (no results)")
            continue
        album_names_lower = {a.lower() for a in candidate_albums}
        matched = [
            r
            for r in artist_results
            if any(a in r.get("title", "").lower() for a in album_names_lower)
        ]
        if matched:
            strategy = f"artist='{artist}' + fuzzy title match"
            tried.append(strategy)
            log.info("Strategy 4 hit: %d fuzzy-matched from %d", len(matched), len(artist_results))
            return matched, strategy, tried
        strategy = f"artist='{artist}' (all releases, no title match)"
        tried.append(strategy)
        log.info("Strategy 4 fallback: %d results (no title match)", len(artist_results))
        return artist_results, strategy, tried

    log.warning("All search strategies exhausted, no results found")
    tried.append("exhausted all strategies")
    return [], "exhausted all strategies", tried


def score_by_metadata(releases: list[dict], label_meta: dict) -> list[dict]:
    """Filter releases by deterministic year/country/label scoring.

    Each release scores 0-3 points (1 per matching field).
    Only the highest-scoring tier is kept.
    If LLM provided no scorable fields, returns releases unchanged.
    """
    llm_year = (label_meta.get("year") or "").strip().lower()
    llm_country = (label_meta.get("country") or "").strip().lower()
    llm_label = (label_meta.get("label") or "").strip().lower()

    if not llm_year and not llm_country and not llm_label:
        log.debug("score_by_metadata: no year/country/label from LLM, skipping")
        return releases

    def _score(r: dict) -> int:
        score = 0
        if llm_year:
            r_year = str(r.get("year", "")).strip().lower()
            if r_year == llm_year:
                score += 1
        if llm_country:
            r_country = (r.get("country") or "").strip().lower()
            if r_country == llm_country:
                score += 1
        if llm_label:
            r_labels = [lbl.strip().lower() for lbl in r.get("label", [])]
            if llm_label in r_labels:
                score += 1
        return score

    scored = [(r, _score(r)) for r in releases]
    max_score = max(s for _, s in scored)

    if max_score == 0:
        log.info("score_by_metadata: no matches (year=%r, country=%r, label=%r), keeping all %d",
                 llm_year, llm_country, llm_label, len(releases))
        return releases

    filtered = [r for r, s in scored if s == max_score]
    log.info("score_by_metadata: %d → %d (kept score=%d, year=%r, country=%r, label=%r)",
             len(releases), len(filtered), max_score, llm_year, llm_country, llm_label)
    return filtered


def get_marketplace_stats(release_id: int) -> dict:
    """Fetch marketplace price stats for a release."""
    resp = requests.get(
        f"{DISCOGS_BASE_URL}/marketplace/stats/{release_id}",
        headers=_headers(),
    )
    resp.raise_for_status()
    return resp.json()


def get_identity() -> str:
    """Get the authenticated Discogs username via /oauth/identity."""
    resp = requests.get(
        f"{DISCOGS_BASE_URL}/oauth/identity",
        headers=_headers(),
    )
    resp.raise_for_status()
    return resp.json()["username"]


def add_to_collection(release_id: int) -> dict:
    """Add a release to the user's Discogs collection (Uncategorized folder)."""
    tokens = get_current_tokens()
    username = tokens.username if tokens and tokens.username else get_identity()
    log.info("Adding release %d to collection for user '%s'", release_id, username)
    resp = requests.post(
        f"{DISCOGS_BASE_URL}/users/{username}/collection/folders/1/releases/{release_id}",
        headers=_headers(),
    )
    resp.raise_for_status()
    return resp.json()
