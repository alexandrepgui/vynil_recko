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


def _headers(tokens: OAuthTokens) -> dict:
    """Build auth headers from OAuth tokens."""
    return build_oauth_headers(tokens)


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


_MAX_SEARCH_PAGES = 20  # Safety cap — broad queries can return 100+ pages


def discogs_search(tokens: OAuthTokens, **params) -> list[dict]:
    """Search Discogs with arbitrary params, paginating up to _MAX_SEARCH_PAGES."""
    params.setdefault("type", "release")
    params.setdefault("per_page", 100)
    all_results = []
    page = 1
    log.debug("discogs_search start: params=%s", params)
    while page <= _MAX_SEARCH_PAGES:
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


def _contains_any(candidates: list[str], text: str) -> bool:
    """Return True if any candidate is a substring of text or vice versa."""
    if not text:
        return False
    text_lower = text.lower()
    return any(c.lower() in text_lower or text_lower in c.lower() for c in candidates if c)


def _sanity_check(
    results: list[dict],
    candidate_albums: list[str],
    candidate_artists: list[str],
    threshold: float = _SANITY_THRESHOLD,
) -> list[dict]:
    """Keep only results where artist OR album match via similarity or containment."""
    passed = []
    for r in results:
        title = r.get("title", "")
        # Discogs titles are "Artist - Album"
        parts = title.split(" - ", 1)
        r_artist = parts[0] if parts else title
        r_album = parts[1] if len(parts) > 1 else ""

        artist_sim = _best_similarity(candidate_artists, r_artist)
        album_sim = _best_similarity(candidate_albums, r_album)
        artist_contained = _contains_any(candidate_artists, r_artist)
        album_contained = _contains_any(candidate_albums, r_album)

        if artist_sim >= threshold or album_sim >= threshold or artist_contained or album_contained:
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

    # Detect self-titled: artist == album (or album was copied from artist)
    is_self_titled = any(
        a.strip().lower() == b.strip().lower()
        for a in candidate_artists
        for b in candidate_albums
    ) if candidate_artists and candidate_albums else False

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

    # 2. Master search → versions
    format_filter = _MEDIA_TYPE_TO_FORMAT.get(media_type)
    seen_master_ids: set[int] = set()
    perfect_masters: list[dict] = []
    # Collect all sane masters first, then sort by track overlap for self-titled
    sane_masters: list[tuple[dict, str, int]] = []  # (master, artist, track_overlap)
    for album in candidate_albums:
        for artist in candidate_artists:
            strategy = f"master: artist='{artist}' release_title='{album}'"
            log.info("Strategy 2: master search — artist='%s' release_title='%s'", artist, album)
            masters = discogs_search(tokens, type="master", artist=artist, release_title=album)
            for master in masters:
                mid = master.get("id")
                if not mid or mid in seen_master_ids:
                    continue
                seen_master_ids.add(mid)
                if not _sanity_check([master], candidate_albums, candidate_artists):
                    continue
                sane_masters.append((master, artist, mid))

    # For self-titled with tracks: fetch tracklists and sort by track overlap
    if is_self_titled and candidate_tracks and len(sane_masters) > 1:
        scored: list[tuple[dict, str, int, int]] = []
        for master, artist, mid in sane_masters:
            detail = _get_master_detail(mid, tokens)
            overlap = 0
            if detail:
                master_tracks = _extract_tracklist(detail)
                overlap = _track_overlap(candidate_tracks, master_tracks)
                log.info("Master %d track overlap: %d/%d (tracks: %s)",
                         mid, overlap, len(candidate_tracks), master_tracks[:5])
            scored.append((master, artist, mid, overlap))
        # Sort by overlap descending — best matching album first
        scored.sort(key=lambda x: x[3], reverse=True)
        sane_masters = [(m, a, mid) for m, a, mid, _ in scored]

    # Process masters: fetch versions and yield
    for master, artist, mid in sane_masters:
        master_result = dict(master)
        master_result["master_id"] = mid
        perfect_masters.append(master_result)
        master_cover = master.get("cover_image")
        versions = get_master_versions(mid, tokens, format_filter=format_filter)
        if not versions:
            log.info("Master %d has no %s versions", mid, format_filter or "any")
            continue
        normalized = [
            _normalize_version(v, artist, cover_image=master_cover, master_id=mid)
            for v in versions
        ]
        strategy = f"master: artist='{artist}' id={mid}"
        sane = _try(normalized, strategy)
        if sane:
            yield sane, strategy

    if perfect_masters:
        # Perfect master found — yield masters as guaranteed fallback, then stop.
        # The caller uses these directly if the LLM rejected all versions.
        log.info("Yielding %d perfect master(s) as fallback, skipping remaining strategies", len(perfect_masters))
        yield perfect_masters, "master fallback"
        return

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

    # 4. Freeform query (q) with album + artist
    for album in candidate_albums:
        for artist in candidate_artists:
            if artist.strip().lower() == album.strip().lower():
                query = artist
                strategy = f"q='{query}' (self-titled)"
            else:
                query = f"{artist} {album}"
                strategy = f"q='{query}'"
            log.info("Strategy 4: freeform q='%s'", query)
            results = discogs_search(tokens, q=query, **fmt)
            if results:
                sane = _try(results, strategy)
                if sane:
                    yield sane, strategy

    # 5. Artist-only search, fuzzy match titles
    for artist in candidate_artists:
        log.info("Strategy 5: artist-only '%s'", artist)
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
            log.info("Strategy 5 hit: %d fuzzy-matched from %d", len(matched), len(artist_results))
            yield matched, strategy
            return
        strategy = f"artist='{artist}' (all releases, no title match)"
        tried.append(strategy)
        log.info("Strategy 5 fallback: %d results (no title match)", len(artist_results))
        yield artist_results, strategy
        return

    # 6. Track name search (last resort — no sanity check, relies on LLM ranking)
    if candidate_tracks:
        # Pick up to 3 distinctive track names to form a query
        query_tracks = candidate_tracks[:3]
        query = " ".join(query_tracks)
        strategy = f"q='{query}' (track names)"
        log.info("Strategy 6: track name search q='%s'", query)
        results = discogs_search(tokens, q=query, **fmt)
        if results:
            tried.append(strategy)
            log.info("Strategy 6: %d results for track query", len(results))
            yield results, strategy
        else:
            tried.append(f"{strategy} (no results)")

    log.warning("All search strategies exhausted, no results found")


def score_by_metadata(
    releases: list[dict],
    label_meta: dict,
    candidate_albums: list[str] | None = None,
    candidate_artists: list[str] | None = None,
) -> list[dict]:
    """Filter releases by deterministic metadata scoring.

    Each release scores 0-5 points:
      +1 artist title similarity >= 0.5
      +1 album title similarity >= 0.5
      +1 year exact match
      +1 country exact match
      +1 label exact match
    Only the highest-scoring tier is kept.
    If no scorable fields are available, returns releases unchanged.
    """
    llm_year = (label_meta.get("year") or "").strip().lower()
    llm_country = (label_meta.get("country") or "").strip().lower()
    llm_label = (label_meta.get("label") or "").strip().lower()
    albums = candidate_albums or []
    artists = candidate_artists or []

    has_meta = llm_year or llm_country or llm_label
    has_title = bool(albums or artists)

    if not has_meta and not has_title:
        log.debug("score_by_metadata: no scorable fields, skipping")
        return releases

    def _score(r: dict) -> int:
        score = 0
        title = r.get("title", "")
        parts = title.split(" - ", 1)
        r_artist = parts[0] if parts else title
        r_album = parts[1] if len(parts) > 1 else ""

        if artists and _best_similarity(artists, r_artist) >= _SANITY_THRESHOLD:
            score += 1
        if albums and _best_similarity(albums, r_album) >= _SANITY_THRESHOLD:
            score += 1
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
        log.info("score_by_metadata: no matches, keeping all %d", len(releases))
        return releases

    filtered = [r for r, s in scored if s == max_score]
    log.info("score_by_metadata: %d → %d (kept score=%d/%d)",
             len(releases), len(filtered), max_score, 5)
    return filtered


_MAX_VERSIONS_PAGES = 10  # Safety cap for master version pagination


def get_master_versions(
    master_id: int,
    tokens: OAuthTokens,
    format_filter: str | None = None,
) -> list[dict]:
    """Fetch versions of a master release, optionally filtered by format."""
    all_versions: list[dict] = []
    page = 1
    params: dict = {"per_page": 100}
    if format_filter:
        params["format"] = format_filter
    log.debug("get_master_versions: master_id=%d params=%s", master_id, params)
    while page <= _MAX_VERSIONS_PAGES:
        params["page"] = page
        resp = _session.get(
            f"{DISCOGS_BASE_URL}/masters/{master_id}/versions",
            headers=_headers(tokens),
            params=params,
        )
        log.debug("Master versions page=%d status=%d", page, resp.status_code)
        _respect_rate_limit(resp)
        resp.raise_for_status()
        data = resp.json()
        versions = data.get("versions", [])
        if not versions:
            break
        all_versions.extend(versions)
        if page >= data.get("pagination", {}).get("pages", 1):
            break
        page += 1
    log.info("get_master_versions: master_id=%d → %d versions", master_id, len(all_versions))
    return all_versions


def _normalize_version(
    version: dict,
    artist_name: str,
    cover_image: str | None = None,
    master_id: int | None = None,
) -> dict:
    """Convert a master version dict to the same shape as a release search result."""
    year_raw = str(version.get("released", ""))[:4]
    try:
        year = int(year_raw) if year_raw else None
    except ValueError:
        year = None
    label = version.get("label")
    return {
        "id": version.get("id"),
        "title": f"{artist_name} - {version.get('title', '')}",
        "year": year,
        "country": version.get("country"),
        "label": [label] if isinstance(label, str) else (label or []),
        "catno": version.get("catno"),
        "format": version.get("format") if isinstance(version.get("format"), list) else [],
        "uri": f"/release/{version.get('id')}",
        "cover_image": cover_image,
        "master_id": master_id,
    }


def _get_master_detail(master_id: int, tokens: OAuthTokens) -> dict | None:
    """Fetch full master detail (cover, tracklist, etc.). Returns raw dict or None."""
    try:
        resp = _session.get(
            f"{DISCOGS_BASE_URL}/masters/{master_id}",
            headers=_headers(tokens),
        )
        _respect_rate_limit(resp)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.warning("Failed to fetch master %d: %s", master_id, e)
        return None


def _extract_cover(data: dict) -> str | None:
    """Extract primary cover image URL from a master detail dict."""
    images = data.get("images", [])
    for img in images:
        if img.get("type") == "primary":
            return img.get("uri") or img.get("resource_url")
    if images:
        return images[0].get("uri") or images[0].get("resource_url")
    return None


def get_master_cover(master_id: int, tokens: OAuthTokens) -> str | None:
    """Fetch the primary cover image for a master release. Returns URL or None."""
    data = _get_master_detail(master_id, tokens)
    return _extract_cover(data) if data else None


def _extract_tracklist(data: dict) -> list[str]:
    """Extract track titles from a master detail dict."""
    return [t.get("title", "") for t in data.get("tracklist", []) if t.get("title")]


def _track_overlap(extracted_tracks: list[str], master_tracks: list[str]) -> int:
    """Count how many extracted track names fuzzy-match the master tracklist."""
    if not extracted_tracks or not master_tracks:
        return 0
    master_lower = [t.lower() for t in master_tracks]
    matches = 0
    for et in extracted_tracks:
        et_lower = et.lower()
        if any(SequenceMatcher(None, et_lower, mt).ratio() >= 0.7 for mt in master_lower):
            matches += 1
    return matches


def get_marketplace_stats(release_id: int, tokens: OAuthTokens) -> dict:
    """Fetch marketplace price stats for a release."""
    resp = _session.get(
        f"{DISCOGS_BASE_URL}/marketplace/stats/{release_id}",
        headers=_headers(tokens),
    )
    _respect_rate_limit(resp)
    resp.raise_for_status()
    return resp.json()


def get_identity(tokens: OAuthTokens) -> str:
    """Get the authenticated Discogs username via /oauth/identity."""
    resp = _session.get(
        f"{DISCOGS_BASE_URL}/oauth/identity",
        headers=_headers(tokens),
    )
    _respect_rate_limit(resp)
    resp.raise_for_status()
    return resp.json()["username"]


def get_release(release_id: int, tokens: OAuthTokens) -> dict:
    """Fetch full details for a single Discogs release."""
    resp = _session.get(
        f"{DISCOGS_BASE_URL}/releases/{release_id}",
        headers=_headers(tokens),
    )
    _respect_rate_limit(resp)
    resp.raise_for_status()
    return resp.json()


def get_collection(
    tokens: OAuthTokens,
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


def add_to_collection(release_id: int, tokens: OAuthTokens) -> dict:
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


def remove_from_collection(
    release_id: int, instance_id: int, tokens: OAuthTokens,
) -> None:
    """Remove a specific instance of a release from the user's Discogs collection."""
    username = tokens.username if tokens and tokens.username else get_identity(tokens)
    log.info(
        "Removing release %d instance %d from collection for user '%s'",
        release_id, instance_id, username,
    )
    resp = _session.delete(
        f"{DISCOGS_BASE_URL}/users/{username}/collection/folders/0/releases/{release_id}/instances/{instance_id}",
        headers=_headers(tokens),
    )
    _respect_rate_limit(resp)
    resp.raise_for_status()
