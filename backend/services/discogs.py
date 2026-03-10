import os
import re
import time
from collections.abc import Generator
from difflib import SequenceMatcher

import requests

from config import DISCOGS_BASE_URL, DISCOGS_USER_AGENT
from logger import get_logger
from services.discogs_auth import OAuthTokens, build_oauth_headers
from utils import create_retry_session

log = get_logger("services.discogs")

# Persistent session — reuses TCP/TLS connections across all Discogs API calls
_session = create_retry_session(user_agent=DISCOGS_USER_AGENT)

# Pause when remaining requests drop to this threshold
_RATE_LIMIT_THRESHOLD = 5
_RATE_LIMIT_PAUSE = 5  # seconds


def _headers(tokens: OAuthTokens | None = None) -> dict:
    """Build auth headers: prefer explicit OAuth tokens, fall back to personal token."""
    if tokens:
        return build_oauth_headers(tokens)
    token = os.getenv("DISCOGS_TOKEN")
    return {"Authorization": f"Discogs token={token}"}


def _respect_rate_limit(resp: requests.Response) -> None:
    """Sleep if we're close to the Discogs rate limit, or back off on 429."""
    if resp.status_code == 429:
        log.warning("Discogs rate limit hit (429), pausing %ds", _RATE_LIMIT_PAUSE * 2)
        time.sleep(_RATE_LIMIT_PAUSE * 2)
        return
    remaining = resp.headers.get("X-Discogs-Ratelimit-Remaining")
    if remaining is not None:
        try:
            remaining_int = int(remaining)
        except (ValueError, TypeError):
            return
        if remaining_int <= _RATE_LIMIT_THRESHOLD:
            log.info("Discogs rate limit low (%d remaining), pausing %ds", remaining_int, _RATE_LIMIT_PAUSE)
            time.sleep(_RATE_LIMIT_PAUSE)


def discogs_search(tokens: OAuthTokens | None = None, max_pages: int = 10, **params) -> list[dict]:
    """Search Discogs with arbitrary params, paginating through all results."""
    params.setdefault("type", "release")
    params.setdefault("per_page", 50)
    all_results = []
    page = 1
    log.debug("discogs_search start: params=%s max_pages=%d", params, max_pages)
    while page <= max_pages:
        params["page"] = page
        resp = _session.get(
            f"{DISCOGS_BASE_URL}/database/search",
            headers=_headers(tokens),
            params=params,
        )
        log.debug("Discogs API: page=%d status=%d", page, resp.status_code)
        _respect_rate_limit(resp)
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


def _normalize_catno(raw: str) -> list[str]:
    """Generate search variants for a catalog number.

    1. Original raw value (always first)
    2. Strip trailing side indicator via regex r'[\\s-][AB]$' (case-insensitive)
    3. If the stripped form contains dots, add a variant with dots removed
    """
    variants = [raw]
    stripped = re.sub(r'[\s-][AB]$', '', raw, flags=re.IGNORECASE)
    if stripped != raw:
        variants.append(stripped)
        no_dots = stripped.replace('.', '')
        if no_dots != stripped:
            variants.append(no_dots)
    else:
        no_dots = raw.replace('.', '')
        if no_dots != raw:
            variants.append(no_dots)
    return variants

_SANITY_THRESHOLD = 0.5


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
    """Keep only results where artist OR album have similarity >= threshold."""
    passed = []
    for r in results:
        title = r.get("title", "")
        # Discogs titles are "Artist - Album"
        parts = title.split(" - ", 1)
        r_artist = parts[0] if parts else title
        r_album = parts[1] if len(parts) > 1 else ""

        artist_sim = _best_similarity(candidate_artists, r_artist)
        album_sim = _best_similarity(candidate_albums, r_album)

        if artist_sim >= threshold or album_sim >= threshold:
            passed.append(r)
        else:
            log.debug(
                "Sanity check dropped: '%s' (artist_sim=%.2f, album_sim=%.2f)",
                title, artist_sim, album_sim,
            )
    return passed


def generate_search_candidates(
    candidate_albums: list[str],
    candidate_artists: list[str],
    label_meta: dict,
    media_type: str = "vinyl",
    tried: list[str] | None = None,
    candidate_tracks: list[str] | None = None,
    tokens: OAuthTokens | None = None,
) -> Generator[tuple[list[dict], str], None, None]:
    """Yield (sane_results, strategy_name) for each strategy that produces results.

    Strategies are tried in priority order. The caller decides when to stop.
    The ``tried`` list (if provided) is appended with strategy names for debug/telemetry.
    """
    if tried is None:
        tried = []
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
        catno_variants = _normalize_catno(label_meta["catno"])
        for catno_variant in catno_variants:
            params = {"catno": catno_variant, **fmt}
            if label_meta.get("label"):
                params["label"] = label_meta["label"]
            strategy = f"catno='{catno_variant}'" + (
                f" + label='{label_meta['label']}'" if "label" in params else ""
            )
            log.info("Strategy 1: catno search — %s", params)
            results = discogs_search(tokens, **params)
            if results:
                sane = _try(results, strategy)
                if sane:
                    yield sane, strategy

            if label_meta.get("label"):
                strategy_1b = f"catno='{catno_variant}'"
                log.info("Strategy 1b: catno only (dropping label)")
                results = discogs_search(tokens, catno=catno_variant, **fmt)
                if results:
                    sane = _try(results, strategy_1b)
                    if sane:
                        yield sane, strategy_1b

    # 2. Freeform query (q) with album + artist
    for album in candidate_albums:
        for artist in candidate_artists:
            if artist.strip().lower() == album.strip().lower():
                query = artist
                strategy = f"q='{query}' (self-titled)"
            else:
                query = f"{artist} {album}"
                strategy = f"q='{query}'"
            log.info("Strategy 2: freeform q='%s'", query)
            results = discogs_search(tokens, q=query, **fmt)
            if results:
                sane = _try(results, strategy)
                if sane:
                    yield sane, strategy

    # 3. Strict release_title + artist
    for album in candidate_albums:
        for artist in candidate_artists:
            strategy = f"release_title='{album}' + artist='{artist}'"
            log.info("Strategy 3: release_title='%s' artist='%s'", album, artist)
            results = discogs_search(tokens, artist=artist, release_title=album, **fmt)
            if results:
                sane = _try(results, strategy)
                if sane:
                    yield sane, strategy

    # 4. Artist-only search, fuzzy match titles
    for artist in candidate_artists:
        log.info("Strategy 4: artist-only '%s'", artist)
        artist_results = discogs_search(tokens, artist=artist, **fmt)
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
            yield matched, strategy
            return
        strategy = f"artist='{artist}' (all releases, no title match)"
        tried.append(strategy)
        log.info("Strategy 4 fallback: %d results (no title match)", len(artist_results))
        yield artist_results, strategy
        return

    # 5. Track name search (last resort — no sanity check, relies on LLM ranking)
    if candidate_tracks:
        # Pick up to 3 distinctive track names to form a query
        query_tracks = candidate_tracks[:3]
        query = " ".join(query_tracks)
        strategy = f"q='{query}' (track names)"
        log.info("Strategy 5: track name search q='%s'", query)
        results = discogs_search(tokens, q=query, **fmt)
        if results:
            tried.append(strategy)
            log.info("Strategy 5: %d results for track query", len(results))
            yield results, strategy
        else:
            tried.append(f"{strategy} (no results)")

    log.warning("All search strategies exhausted, no results found")


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


def get_marketplace_stats(release_id: int, tokens: OAuthTokens | None = None) -> dict:
    """Fetch marketplace price stats for a release."""
    resp = _session.get(
        f"{DISCOGS_BASE_URL}/marketplace/stats/{release_id}",
        headers=_headers(tokens),
    )
    _respect_rate_limit(resp)
    resp.raise_for_status()
    return resp.json()


def get_identity(tokens: OAuthTokens | None = None) -> str:
    """Get the authenticated Discogs username via /oauth/identity."""
    resp = _session.get(
        f"{DISCOGS_BASE_URL}/oauth/identity",
        headers=_headers(tokens),
    )
    _respect_rate_limit(resp)
    resp.raise_for_status()
    return resp.json()["username"]


def get_collection(
    tokens: OAuthTokens | None = None,
    page: int = 1,
    per_page: int = 50,
    sort: str = "artist",
    sort_order: str = "asc",
) -> dict:
    """Fetch the authenticated user's Discogs collection (folder 0 = all)."""
    username = tokens.username if tokens and tokens.username else get_identity(tokens)
    log.info("Fetching collection page %d for user '%s'", page, username)
    resp = _session.get(
        f"{DISCOGS_BASE_URL}/users/{username}/collection/folders/0/releases",
        headers=_headers(tokens),
        params={
            "page": page,
            "per_page": per_page,
            "sort": sort,
            "sort_order": sort_order,
        },
    )
    _respect_rate_limit(resp)
    resp.raise_for_status()
    return resp.json()


def add_to_collection(release_id: int, tokens: OAuthTokens | None = None) -> dict:
    """Add a release to the user's Discogs collection (Uncategorized folder)."""
    username = tokens.username if tokens and tokens.username else get_identity(tokens)
    log.info("Adding release %d to collection for user '%s'", release_id, username)
    resp = _session.post(
        f"{DISCOGS_BASE_URL}/users/{username}/collection/folders/1/releases/{release_id}",
        headers=_headers(tokens),
    )
    _respect_rate_limit(resp)
    resp.raise_for_status()
    return resp.json()
