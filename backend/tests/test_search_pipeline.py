"""Tests for services/search.py: self-titled logic, tiebreaker, strategy fallthrough, _build_debug."""

from unittest.mock import patch, MagicMock

import pytest

from conftest import FAKE_RANKING, make_discogs_response, make_mock_llm_client
from services.discogs_auth import OAuthTokens
from config import DISCOGS_SPACER_GIF
from services.search import _build_debug, process_single_image

_SPACER_GIF = DISCOGS_SPACER_GIF  # For backward compatibility with existing test assertions

_FAKE_TOKENS = OAuthTokens(access_token="t", access_token_secret="s", username="testuser")

# Default release used by tests that don't need custom releases.
_DEFAULT_RELEASE = {
    "id": 1,
    "title": "Test Artist - Test Album",
    "year": "2000",
    "country": "US",
    "format": ["Vinyl"],
    "label": ["TestLabel"],
    "catno": "T001",
    "uri": "/release/1",
    "cover_image": "https://example.com/cover.jpg",
}


def _run_pipeline(label_data, discogs_results=None, ranking=None):
    """Run the search pipeline with mocked external calls."""
    if discogs_results is None:
        discogs_results = [_DEFAULT_RELEASE]
    if ranking is None:
        ranking = FAKE_RANKING

    mock_client = make_mock_llm_client([label_data, ranking])
    discogs_resp = make_discogs_response(discogs_results)
    mock_repo = MagicMock()

    with (
        patch("services.vision._get_client", return_value=mock_client),
        patch("services.discogs._session.get", return_value=discogs_resp),
        patch("services.vision._read_cache", return_value=None),
        patch("services.vision._write_cache"),
        patch("services.search.get_repo", return_value=mock_repo),
    ):
        return process_single_image(b"fake-image", "image/jpeg", tokens=_FAKE_TOKENS)


_UNSET = object()


def _make_label(albums=_UNSET, artists=_UNSET, tracks=None):
    """Build a minimal label_data dict."""
    return {
        "albums": ["Kind of Blue"] if albums is _UNSET else albums,
        "artists": ["Miles Davis"] if artists is _UNSET else artists,
        "tracks": tracks,
        "country": None, "format": None, "label": None, "catno": None, "year": None,
    }


# ── _build_debug ──────────────────────────────────────────────────────────────


class TestBuildDebug:
    def test_basic_fields(self):
        result = _build_debug(
            cache_hit=True,
            strategies_tried=["s1", "s2"],
            timing_ms={"vision": 100.0},
            label_data={"albums": ["A"]},
        )
        assert result["cache_hit"] is True
        assert result["strategies_tried"] == ["s1", "s2"]
        assert result["timing_ms"] == {"vision": 100.0}
        assert result["llm_label_response"] == {"albums": ["A"]}

    def test_extras_merged(self):
        result = _build_debug(
            cache_hit=False,
            strategies_tried=[],
            timing_ms={},
            label_data={},
            prefilter={"before": 10, "after": 5},
        )
        assert result["prefilter"] == {"before": 10, "after": 5}


# ── Self-titled logic ─────────────────────────────────────────────────────────


class TestSelfTitledLogic:
    def test_album_missing_uses_artist_as_album(self):
        resp = _run_pipeline(_make_label(albums=None, artists=["Miles Davis"]))
        assert resp.label_data.albums == ["Miles Davis"]

    def test_artist_missing_uses_album_as_artist(self):
        resp = _run_pipeline(_make_label(albums=["Kind of Blue"], artists=None))
        assert resp.label_data.artists == ["Kind of Blue"]

    def test_both_missing_raises(self):
        with pytest.raises(ValueError, match="Could not extract"):
            _run_pipeline(_make_label(albums=None, artists=None))

    def test_empty_albums_and_artists_raises(self):
        with pytest.raises(ValueError, match="Could not extract"):
            _run_pipeline(_make_label(albums=[], artists=[]))


# ── Cover image tiebreaker ────────────────────────────────────────────────────


class TestCoverImageTiebreaker:
    def test_promotes_result_with_cover_same_catno(self):
        """Same catno: result with cover should be promoted above one without."""
        releases = [
            {"id": 1, "title": "Miles Davis - Kind of Blue", "year": "1959",
             "country": "US", "format": ["Vinyl"], "label": ["Columbia"],
             "catno": "CS 8163", "uri": "/release/1", "cover_image": None},
            {"id": 2, "title": "Miles Davis - Kind of Blue", "year": "1959",
             "country": "US", "format": ["Vinyl"], "label": ["Columbia"],
             "catno": "CS 8163", "uri": "/release/2", "cover_image": "https://example.com/cover.jpg"},
        ]
        resp = _run_pipeline(_make_label(), releases, {"likeliness": [0, 1], "discarded": []})
        assert resp.results[0].cover_image == "https://example.com/cover.jpg"
        assert resp.results[1].cover_image is None

    def test_no_swap_when_first_has_cover(self):
        releases = [
            {"id": 1, "title": "Miles Davis - Kind of Blue", "year": "1959",
             "country": "US", "format": ["Vinyl"], "label": ["Columbia"],
             "catno": "CS 8163", "uri": "/release/1", "cover_image": "https://example.com/cover1.jpg"},
            {"id": 2, "title": "Miles Davis - Kind of Blue", "year": "1959",
             "country": "US", "format": ["Vinyl"], "label": ["Columbia"],
             "catno": "CS 8163", "uri": "/release/2", "cover_image": "https://example.com/cover2.jpg"},
        ]
        resp = _run_pipeline(_make_label(), releases, {"likeliness": [0, 1], "discarded": []})
        assert resp.results[0].discogs_id == 1

    def test_no_swap_when_different_catno_and_title(self):
        """Different albums (different catno + title) should not be reordered."""
        releases = [
            {"id": 1, "title": "Miles Davis - Kind of Blue", "year": "1959",
             "country": "US", "format": ["Vinyl"], "label": ["Columbia"],
             "catno": "CS 8163", "uri": "/release/1", "cover_image": None},
            {"id": 2, "title": "Miles Davis - Bitches Brew", "year": "1970",
             "country": "US", "format": ["Vinyl"], "label": ["Columbia"],
             "catno": "GP 26", "uri": "/release/2", "cover_image": "https://example.com/cover.jpg"},
        ]
        resp = _run_pipeline(_make_label(), releases, {"likeliness": [0, 1], "discarded": []})
        assert resp.results[0].discogs_id == 1

    def test_spacer_gif_treated_as_no_image(self):
        """Discogs spacer.gif placeholder should be treated as no cover image."""
        spacer = f"https://st.discogs.com/abc123/images/{_SPACER_GIF}"
        releases = [
            {"id": 1, "title": "Miles Davis - Kind of Blue", "year": "1959",
             "country": "US", "format": ["Vinyl"], "label": ["Columbia"],
             "catno": "CS 8163", "uri": "/release/1", "cover_image": spacer},
            {"id": 2, "title": "Miles Davis - Kind of Blue", "year": "1959",
             "country": "US", "format": ["Vinyl"], "label": ["Columbia"],
             "catno": "CS 8163", "uri": "/release/2", "cover_image": "https://i.discogs.com/real-cover.jpg"},
        ]
        resp = _run_pipeline(_make_label(), releases, {"likeliness": [0, 1], "discarded": []})
        assert resp.results[0].discogs_id == 2
        assert resp.results[0].cover_image == "https://i.discogs.com/real-cover.jpg"
        assert resp.results[1].discogs_id == 1
        assert resp.results[1].cover_image is None

    def test_promotes_image_across_multiple_same_catno(self):
        """Image results bubble up even when more than two share the same catno."""
        releases = [
            {"id": 1, "title": "Miles Davis - Kind of Blue", "year": "1959",
             "country": "US", "format": ["Vinyl"], "label": ["Columbia"],
             "catno": "CS 8163", "uri": "/release/1", "cover_image": None},
            {"id": 2, "title": "Miles Davis - Kind of Blue", "year": "1959",
             "country": "US", "format": ["Vinyl"], "label": ["Columbia"],
             "catno": "CS 8163", "uri": "/release/2", "cover_image": None},
            {"id": 3, "title": "Miles Davis - Kind of Blue", "year": "1959",
             "country": "US", "format": ["Vinyl"], "label": ["Columbia"],
             "catno": "CS 8163", "uri": "/release/3", "cover_image": "https://example.com/cover.jpg"},
        ]
        resp = _run_pipeline(_make_label(), releases, {"likeliness": [0, 1, 2], "discarded": []})
        assert resp.results[0].discogs_id == 3
        assert resp.results[0].cover_image == "https://example.com/cover.jpg"

    def test_title_fallback_grouping(self):
        """When catno differs, fall back to normalized title for grouping."""
        releases = [
            {"id": 1, "title": "Miles Davis - Kind of Blue (1959)", "year": "1959",
             "country": "US", "format": ["Vinyl"], "label": ["Columbia"],
             "catno": "C1", "uri": "/release/1", "cover_image": None},
            {"id": 2, "title": "Miles Davis - Kind of Blue", "year": "1959",
             "country": "US", "format": ["Vinyl"], "label": ["Columbia"],
             "catno": "C2", "uri": "/release/2", "cover_image": "https://example.com/cover.jpg"},
        ]
        resp = _run_pipeline(_make_label(), releases, {"likeliness": [0, 1], "discarded": []})
        # Different catnos, different titles → no swap
        assert resp.results[0].discogs_id == 1


# ── Strategy fallthrough ──────────────────────────────────────────────────────


class TestStrategyFallthrough:
    def test_falls_through_when_llm_rejects_all(self):
        """When LLM discards all results from strategy 1, pipeline tries strategy 2."""
        strategy1_releases = [
            {"id": 1, "title": "Miles Davis - Wrong Album", "year": "1959",
             "country": "US", "format": ["Vinyl"], "label": ["Columbia"],
             "catno": "C1", "uri": "/release/1", "cover_image": None},
        ]
        strategy2_releases = [
            {"id": 2, "title": "Miles Davis - Kind of Blue", "year": "1959",
             "country": "US", "format": ["Vinyl"], "label": ["Columbia"],
             "catno": "C2", "uri": "/release/2", "cover_image": "https://example.com/cover.jpg"},
        ]

        label_data = _make_label()
        # Vision response, then ranking for strategy 1 (discard all), then ranking for strategy 2 (accept)
        mock_client = make_mock_llm_client([
            label_data,
            {"likeliness": [0], "discarded": [0]},
            {"likeliness": [0], "discarded": []},
        ])
        mock_repo = MagicMock()

        def fake_generator(*args, **kwargs):
            yield strategy1_releases, "strategy_1"
            yield strategy2_releases, "strategy_2"

        with (
            patch("services.vision._get_client", return_value=mock_client),
            patch("services.vision._read_cache", return_value=None),
            patch("services.vision._write_cache"),
            patch("services.search.get_repo", return_value=mock_repo),
            patch("services.search.generate_search_candidates", side_effect=fake_generator),
        ):
            resp = process_single_image(b"fake-image", "image/jpeg", tokens=_FAKE_TOKENS)

        assert resp.total == 1
        assert resp.results[0].discogs_id == 2
        assert resp.strategy == "strategy_2"

    def test_empty_results_when_all_strategies_exhausted(self):
        """When LLM discards everything from the only strategy, return empty results."""
        releases = [
            {"id": 1, "title": "Miles Davis - Kind of Blue", "year": "1959",
             "country": "US", "format": ["Vinyl"], "label": ["Columbia"],
             "catno": "C1", "uri": "/release/1", "cover_image": "https://example.com/cover.jpg"},
        ]

        label_data = _make_label()
        mock_client = make_mock_llm_client([
            label_data,
            {"likeliness": [0], "discarded": [0]},
        ])
        mock_repo = MagicMock()

        def fake_generator(*args, **kwargs):
            yield releases, "only_strategy"

        with (
            patch("services.vision._get_client", return_value=mock_client),
            patch("services.vision._read_cache", return_value=None),
            patch("services.vision._write_cache"),
            patch("services.search.get_repo", return_value=mock_repo),
            patch("services.search.generate_search_candidates", side_effect=fake_generator),
        ):
            resp = process_single_image(b"fake-image", "image/jpeg", tokens=_FAKE_TOKENS)

        assert resp.total == 0
        assert resp.results == []


# ── No results from Discogs ──────────────────────────────────────────────────


class TestNoResults:
    def test_empty_discogs_returns_empty(self):
        label = _make_label()
        mock_client = make_mock_llm_client([label])
        discogs_resp = make_discogs_response([])
        mock_repo = MagicMock()

        with (
            patch("services.vision._get_client", return_value=mock_client),
            patch("services.discogs._session.get", return_value=discogs_resp),
            patch("services.vision._read_cache", return_value=None),
            patch("services.vision._write_cache"),
            patch("services.search.get_repo", return_value=mock_repo),
        ):
            resp = process_single_image(b"fake-image", "image/jpeg", tokens=_FAKE_TOKENS)

        assert resp.total == 0
        assert resp.results == []
