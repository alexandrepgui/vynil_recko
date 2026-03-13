"""Tests for services/discogs.py: prefilter, score_by_metadata, _sanity_check, _best_similarity, _normalize_catno, remove_from_collection, get_master_cover, get_master_versions, _normalize_version."""

from unittest.mock import MagicMock, patch

from services.discogs import (
    _best_similarity,
    _contains_any,
    _extract_tracklist,
    _normalize_catno,
    _normalize_version,
    _sanity_check,
    _track_overlap,
    get_master_cover,
    get_master_versions,
    prefilter,
    remove_from_collection,
    score_by_metadata,
    generate_search_candidates,
)
from services.discogs_auth import OAuthTokens


# ── prefilter ─────────────────────────────────────────────────────────────────


class TestPrefilter:
    def test_keeps_matching_releases(self):
        releases = [
            {"title": "Miles Davis - Kind of Blue"},
            {"title": "John Coltrane - Blue Train"},
        ]
        result = prefilter(releases, ["Miles Davis"])
        assert len(result) == 1
        assert result[0]["title"] == "Miles Davis - Kind of Blue"

    def test_case_insensitive(self):
        releases = [{"title": "MILES DAVIS - Kind of Blue"}]
        result = prefilter(releases, ["miles davis"])
        assert len(result) == 1

    def test_returns_originals_when_all_filtered(self):
        """When prefilter drops everything, return originals as fallback."""
        releases = [
            {"title": "John Coltrane - Blue Train"},
            {"title": "Thelonious Monk - Brilliant Corners"},
        ]
        result = prefilter(releases, ["Miles Davis"])
        assert result == releases

    def test_empty_releases_returns_empty(self):
        result = prefilter([], ["Miles Davis"])
        assert result == []

    def test_multiple_artists(self):
        releases = [
            {"title": "Miles Davis - Kind of Blue"},
            {"title": "John Coltrane - Blue Train"},
            {"title": "Oscar Peterson - Night Train"},
        ]
        result = prefilter(releases, ["Miles Davis", "John Coltrane"])
        assert len(result) == 2

    def test_partial_match_in_title(self):
        """Artist substring appearing in the title should match."""
        releases = [{"title": "Miles Davis Quintet - Relaxin'"}]
        result = prefilter(releases, ["Miles Davis"])
        assert len(result) == 1

    def test_missing_title_key(self):
        releases = [{"id": 1}, {"title": "Miles Davis - Kind of Blue"}]
        result = prefilter(releases, ["Miles Davis"])
        assert len(result) == 1


# ── _best_similarity ─────────────────────────────────────────────────────────


class TestBestSimilarity:
    def test_exact_match(self):
        assert _best_similarity(["Miles Davis"], "Miles Davis") == 1.0

    def test_case_insensitive(self):
        assert _best_similarity(["miles davis"], "MILES DAVIS") == 1.0

    def test_partial_match(self):
        sim = _best_similarity(["Miles Davis"], "Miles Davis Quintet")
        assert 0.5 < sim < 1.0

    def test_no_candidates(self):
        assert _best_similarity([], "anything") == 0.0

    def test_picks_best_from_multiple(self):
        sim = _best_similarity(["John Coltrane", "Miles Davis"], "Miles Davis")
        assert sim == 1.0

    def test_completely_different(self):
        sim = _best_similarity(["zzzzzzzzzzz"], "Miles Davis")
        assert sim < 0.3


# ── _sanity_check ─────────────────────────────────────────────────────────────


class TestSanityCheck:
    def test_passes_good_match(self):
        results = [{"title": "Miles Davis - Kind of Blue"}]
        passed = _sanity_check(results, ["Kind of Blue"], ["Miles Davis"])
        assert len(passed) == 1

    def test_drops_bad_match(self):
        results = [{"title": "ZZZXXX - QQQWWW"}]
        passed = _sanity_check(results, ["Kind of Blue"], ["Miles Davis"])
        assert len(passed) == 0

    def test_mixed_results(self):
        results = [
            {"title": "Miles Davis - Kind of Blue"},
            {"title": "ZZZXXX - QQQWWW"},
        ]
        passed = _sanity_check(results, ["Kind of Blue"], ["Miles Davis"])
        assert len(passed) == 1
        assert passed[0]["title"] == "Miles Davis - Kind of Blue"

    def test_custom_threshold(self):
        results = [{"title": "Miles Davis - Kind of Blue"}]
        # Very high threshold should reject even good matches
        passed = _sanity_check(results, ["Kind of Blue"], ["Miles Davis"], threshold=0.99)
        assert len(passed) == 1  # exact match should still pass

    def test_empty_results(self):
        assert _sanity_check([], ["Blue"], ["Miles"]) == []

    def test_title_without_dash(self):
        """Titles without ' - ' put everything in artist, album is empty."""
        results = [{"title": "Some Compilation"}]
        # Artist candidate "Various" not in "Some Compilation" → fails
        passed = _sanity_check(results, ["Other Album"], ["Various"])
        assert len(passed) == 0
        # Artist candidate "Some Compilation" IS contained in artist part → passes
        passed = _sanity_check(results, ["X"], ["Some Compilation"])
        assert len(passed) == 1

    def test_artist_contained_in_discogs_artist(self):
        """Artist contained in longer Discogs string should pass (e.g. collabs)."""
        results = [{"title": "Rita Lee & Roberto De Carvalho* - Rita Lee"}]
        passed = _sanity_check(results, ["Rita Lee"], ["Rita Lee"])
        assert len(passed) == 1

    def test_contains_any_basic(self):
        assert _contains_any(["Rita Lee"], "Rita Lee & Roberto De Carvalho*") is True
        assert _contains_any(["Rita Lee"], "ZZZXXX") is False

    def test_contains_any_reverse(self):
        """Short Discogs text contained in longer candidate also passes."""
        assert _contains_any(["Rita Lee & Roberto"], "Rita Lee") is True


# ── score_by_metadata ─────────────────────────────────────────────────────────


class TestScoreByMetadata:
    def test_returns_unchanged_when_no_metadata(self):
        releases = [{"title": "R1"}, {"title": "R2"}]
        result = score_by_metadata(releases, {})
        assert result == releases

    def test_filters_by_year(self):
        releases = [
            {"title": "R1", "year": "1959"},
            {"title": "R2", "year": "2001"},
        ]
        result = score_by_metadata(releases, {"year": "1959"})
        assert len(result) == 1
        assert result[0]["title"] == "R1"

    def test_filters_by_country(self):
        releases = [
            {"title": "R1", "country": "US"},
            {"title": "R2", "country": "UK"},
        ]
        result = score_by_metadata(releases, {"country": "US"})
        assert len(result) == 1
        assert result[0]["title"] == "R1"

    def test_filters_by_label(self):
        releases = [
            {"title": "R1", "label": ["Columbia"]},
            {"title": "R2", "label": ["RCA"]},
        ]
        result = score_by_metadata(releases, {"label": "Columbia"})
        assert len(result) == 1
        assert result[0]["title"] == "R1"

    def test_highest_score_wins(self):
        """Release matching both year and country should beat one matching only year."""
        releases = [
            {"title": "R1", "year": "1959", "country": "UK"},
            {"title": "R2", "year": "1959", "country": "US"},
        ]
        result = score_by_metadata(releases, {"year": "1959", "country": "US"})
        assert len(result) == 1
        assert result[0]["title"] == "R2"

    def test_keeps_all_when_no_matches(self):
        """When no release matches any metadata, keep them all."""
        releases = [
            {"title": "R1", "year": "2000"},
            {"title": "R2", "year": "2001"},
        ]
        result = score_by_metadata(releases, {"year": "1959"})
        assert result == releases

    def test_case_insensitive_country(self):
        releases = [
            {"title": "R1", "country": "us"},
            {"title": "R2", "country": "UK"},
        ]
        result = score_by_metadata(releases, {"country": "US"})
        assert len(result) == 1
        assert result[0]["title"] == "R1"

    def test_empty_meta_values_skipped(self):
        """Empty string metadata values should be treated as absent."""
        releases = [{"title": "R1"}, {"title": "R2"}]
        result = score_by_metadata(releases, {"year": "", "country": ""})
        assert result == releases

    def test_multiple_labels_in_release(self):
        releases = [
            {"title": "R1", "label": ["Columbia", "Legacy"]},
            {"title": "R2", "label": ["RCA"]},
        ]
        result = score_by_metadata(releases, {"label": "Columbia"})
        assert len(result) == 1
        assert result[0]["title"] == "R1"

    def test_tie_keeps_all_with_same_score(self):
        releases = [
            {"title": "R1", "year": "1959", "country": "US"},
            {"title": "R2", "year": "1959", "country": "US"},
            {"title": "R3", "year": "2000", "country": "UK"},
        ]
        result = score_by_metadata(releases, {"year": "1959", "country": "US"})
        assert len(result) == 2

    def test_album_match_promotes_correct_release(self):
        """Release with matching album title should beat ones with wrong album."""
        releases = [
            {"title": "Nektar - ...Sounds Like This", "year": "1973"},
            {"title": "Nektar - ...Sounds Like This", "year": "1975"},
            {"title": "Nektar - Journey To The Centre Of The Eye", "year": "1971"},
        ]
        result = score_by_metadata(
            releases, {},
            candidate_albums=["Journey To The Centre Of The Eye"],
            candidate_artists=["Nektar"],
        )
        assert len(result) == 1
        assert "Journey To The Centre Of The Eye" in result[0]["title"]

    def test_artist_match_scores(self):
        """Releases with matching artist score higher than non-matching."""
        releases = [
            {"title": "Nektar - Some Album"},
            {"title": "Various - Some Compilation"},
        ]
        result = score_by_metadata(
            releases, {},
            candidate_artists=["Nektar"],
        )
        assert len(result) == 1
        assert result[0]["title"] == "Nektar - Some Album"

    def test_title_scoring_combined_with_metadata(self):
        """Artist+album+year should beat artist+album alone."""
        releases = [
            {"title": "Nektar - Journey To The Centre Of The Eye", "year": "1971"},
            {"title": "Nektar - Journey To The Centre Of The Eye", "year": "2024"},
        ]
        result = score_by_metadata(
            releases, {"year": "1971"},
            candidate_albums=["Journey To The Centre Of The Eye"],
            candidate_artists=["Nektar"],
        )
        assert len(result) == 1
        assert result[0]["year"] == "1971"

    def test_no_candidates_falls_back_to_meta_only(self):
        """When no candidate albums/artists provided, behaves like before."""
        releases = [
            {"title": "Nektar - Journey To The Centre Of The Eye", "year": "1971"},
            {"title": "Nektar - ...Sounds Like This", "year": "1973"},
        ]
        result = score_by_metadata(releases, {"year": "1971"})
        assert len(result) == 1
        assert result[0]["year"] == "1971"


# ── _normalize_catno ─────────────────────────────────────────────────────────


class TestCatnoNormalization:
    def test_strip_side_a(self):
        assert _normalize_catno("BR 36.149-A") == ["BR 36.149-A", "BR 36.149", "BR 36149"]

    def test_strip_side_b(self):
        assert _normalize_catno("31C 052 422805 B") == ["31C 052 422805 B", "31C 052 422805"]

    def test_dots_removal_without_side(self):
        assert _normalize_catno("201.404.007") == ["201.404.007", "201404007"]

    def test_side_suffix_with_dots(self):
        assert _normalize_catno("201.404.007-A") == ["201.404.007-A", "201.404.007", "201404007"]

    def test_no_change(self):
        assert _normalize_catno("F0019") == ["F0019"]

    def test_numeric_suffix_preserved(self):
        """'-2' is NOT a side indicator, should not be stripped."""
        assert _normalize_catno("510 022-2") == ["510 022-2"]

    def test_case_insensitive_side(self):
        assert _normalize_catno("ABC-a") == ["ABC-a", "ABC"]

    def test_side_with_space(self):
        assert _normalize_catno("XYZ 123 A") == ["XYZ 123 A", "XYZ 123"]


# ── self-titled dedup ────────────────────────────────────────────────────────


class TestSelfTitledDedup:
    @patch("services.discogs.discogs_search")
    def test_self_titled_no_duplicate(self, mock_search):
        """When album == artist, freeform q should not duplicate the name."""
        def search_side_effect(tokens, **params):
            if params.get("type") == "master":
                return []
            if "release_title" in params:
                return []
            if "q" in params:
                return [{"title": "Di Melo - Di Melo"}]
            return []
        mock_search.side_effect = search_side_effect
        results, strategy = next(generate_search_candidates(
            candidate_albums=["Di Melo"],
            candidate_artists=["Di Melo"],
            label_meta={},
            media_type="vinyl",
        ))
        calls = mock_search.call_args_list
        q_calls = [c for c in calls if "q" in c.kwargs]
        assert any(c.kwargs["q"] == "Di Melo" for c in q_calls)
        assert "self-titled" in strategy

    @patch("services.discogs._get_master_detail")
    @patch("services.discogs.get_master_versions")
    @patch("services.discogs.discogs_search")
    def test_self_titled_with_tracks_sorts_by_overlap(self, mock_search, mock_versions, mock_detail):
        """Self-titled + tracks: masters sorted by track overlap, best match first."""
        MASTER_WRONG = {"id": 100, "title": "Rita Lee - Grandes Sucessos", "cover_image": "c1"}
        MASTER_RIGHT = {"id": 200, "title": "Rita Lee - Rita Lee", "cover_image": "c2"}

        def search_side_effect(tokens, **params):
            if params.get("type") == "master":
                return [MASTER_WRONG, MASTER_RIGHT]
            return []
        mock_search.side_effect = search_side_effect
        mock_detail.side_effect = lambda mid, tokens: {
            100: {"tracklist": [{"title": "Lança Perfume"}, {"title": "Caso Sério"}]},
            200: {"tracklist": [{"title": "Flagra"}, {"title": "Barriga Da Mamãe"}, {"title": "Barata Tonta"}]},
        }.get(mid)
        mock_versions.return_value = [{"id": 999, "title": "Rita Lee", "released": "1982"}]

        results, strategy = next(generate_search_candidates(
            candidate_albums=["Rita Lee"],
            candidate_artists=["Rita Lee"],
            label_meta={},
            media_type="vinyl",
            candidate_tracks=["Flagra", "Barriga da Mamãe", "Barata Tonta"],
        ))
        # Master 200 (right album) should be processed first due to higher track overlap
        assert "id=200" in strategy

    @patch("services.discogs.discogs_search")
    def test_different_artist_album_not_deduped(self, mock_search):
        """When album != artist, query should contain both."""
        def search_side_effect(tokens, **params):
            if params.get("type") == "master":
                return []
            if "release_title" in params:
                return []
            if "q" in params:
                return [{"title": "Miles Davis - Kind of Blue"}]
            return []
        mock_search.side_effect = search_side_effect
        results, strategy = next(generate_search_candidates(
            candidate_albums=["Kind of Blue"],
            candidate_artists=["Miles Davis"],
            label_meta={},
            media_type="vinyl",
        ))
        calls = mock_search.call_args_list
        for call in calls:
            if "q" in call.kwargs:
                assert call.kwargs["q"] == "Miles Davis Kind of Blue"
                break
        assert "self-titled" not in strategy


# ── sanity check: short-string false positives ───────────────────────────────


class TestSanityCheckThreshold:
    def test_metallica_vs_jim_trahan_blocked(self):
        """Short-string false positive should be blocked at threshold 0.5."""
        results = [{"title": "Jim Trahan - Some Album"}]
        passed = _sanity_check(results, ["Metallica"], ["Metallica"])
        assert len(passed) == 0

    def test_miles_davis_quintet_passes(self):
        """Legitimate partial match should still pass."""
        results = [{"title": "Miles Davis Quintet - Relaxin'"}]
        passed = _sanity_check(results, ["Relaxin'"], ["Miles Davis"])
        assert len(passed) == 1


# ── remove_from_collection ──────────────────────────────────────────────────


class TestRemoveFromCollection:
    @patch("services.discogs._session")
    def test_remove_from_collection_success(self, mock_session):
        tokens = OAuthTokens(access_token="a", access_token_secret="b", username="testuser")
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.headers = {"X-Discogs-Ratelimit-Remaining": "50"}
        mock_resp.raise_for_status = MagicMock()
        mock_session.delete.return_value = mock_resp

        remove_from_collection(release_id=555, instance_id=100, tokens=tokens)

        mock_session.delete.assert_called_once()
        url = mock_session.delete.call_args[0][0]
        assert "/users/testuser/collection/folders/0/releases/555/instances/100" in url

    @patch("services.discogs._session")
    def test_remove_from_collection_raises_on_error(self, mock_session):
        import requests
        tokens = OAuthTokens(access_token="a", access_token_secret="b", username="testuser")
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.headers = {"X-Discogs-Ratelimit-Remaining": "50"}
        mock_resp.raise_for_status.side_effect = requests.HTTPError("Not Found")
        mock_session.delete.return_value = mock_resp

        try:
            remove_from_collection(release_id=555, instance_id=100, tokens=tokens)
            assert False, "Should have raised"
        except requests.HTTPError:
            pass


# ── get_master_cover ──────────────────────────────────────────────────────


class TestGetMasterCover:
    @patch("services.discogs._session")
    def test_returns_primary_image(self, mock_session):
        tokens = OAuthTokens(access_token="a", access_token_secret="b", username="u")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"X-Discogs-Ratelimit-Remaining": "50"}
        mock_resp.json.return_value = {
            "images": [
                {"type": "secondary", "uri": "https://i.discogs.com/secondary.jpg"},
                {"type": "primary", "uri": "https://i.discogs.com/primary.jpg"},
            ]
        }
        mock_session.get.return_value = mock_resp

        result = get_master_cover(12345, tokens)
        assert result == "https://i.discogs.com/primary.jpg"

    @patch("services.discogs._session")
    def test_falls_back_to_first_image(self, mock_session):
        tokens = OAuthTokens(access_token="a", access_token_secret="b", username="u")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"X-Discogs-Ratelimit-Remaining": "50"}
        mock_resp.json.return_value = {
            "images": [
                {"type": "secondary", "uri": "https://i.discogs.com/only.jpg"},
            ]
        }
        mock_session.get.return_value = mock_resp

        result = get_master_cover(12345, tokens)
        assert result == "https://i.discogs.com/only.jpg"

    @patch("services.discogs._session")
    def test_returns_none_on_empty_images(self, mock_session):
        tokens = OAuthTokens(access_token="a", access_token_secret="b", username="u")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"X-Discogs-Ratelimit-Remaining": "50"}
        mock_resp.json.return_value = {"images": []}
        mock_session.get.return_value = mock_resp

        result = get_master_cover(12345, tokens)
        assert result is None

    @patch("services.discogs._session")
    def test_returns_none_on_error(self, mock_session):
        import requests
        tokens = OAuthTokens(access_token="a", access_token_secret="b", username="u")
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.headers = {"X-Discogs-Ratelimit-Remaining": "50"}
        mock_resp.raise_for_status.side_effect = requests.HTTPError("Not Found")
        mock_session.get.return_value = mock_resp

        result = get_master_cover(12345, tokens)
        assert result is None


# ── get_master_versions ─────────────────────────────────────────────────────


class TestGetMasterVersions:
    @patch("services.discogs._session")
    def test_single_page(self, mock_session):
        tokens = OAuthTokens(access_token="a", access_token_secret="b", username="u")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"X-Discogs-Ratelimit-Remaining": "50"}
        mock_resp.json.return_value = {
            "versions": [{"id": 1}, {"id": 2}],
            "pagination": {"pages": 1},
        }
        mock_session.get.return_value = mock_resp

        result = get_master_versions(26002, tokens)
        assert len(result) == 2
        assert result[0]["id"] == 1

    @patch("services.discogs._session")
    def test_pagination(self, mock_session):
        tokens = OAuthTokens(access_token="a", access_token_secret="b", username="u")
        page1 = MagicMock()
        page1.status_code = 200
        page1.headers = {"X-Discogs-Ratelimit-Remaining": "50"}
        page1.json.return_value = {
            "versions": [{"id": 1}],
            "pagination": {"pages": 2},
        }
        page2 = MagicMock()
        page2.status_code = 200
        page2.headers = {"X-Discogs-Ratelimit-Remaining": "50"}
        page2.json.return_value = {
            "versions": [{"id": 2}],
            "pagination": {"pages": 2},
        }
        mock_session.get.side_effect = [page1, page2]

        result = get_master_versions(26002, tokens)
        assert len(result) == 2

    @patch("services.discogs._session")
    def test_format_filter_passed(self, mock_session):
        tokens = OAuthTokens(access_token="a", access_token_secret="b", username="u")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"X-Discogs-Ratelimit-Remaining": "50"}
        mock_resp.json.return_value = {"versions": [], "pagination": {"pages": 1}}
        mock_session.get.return_value = mock_resp

        get_master_versions(26002, tokens, format_filter="Vinyl")
        call_params = mock_session.get.call_args[1]["params"]
        assert call_params["format"] == "Vinyl"

    @patch("services.discogs._session")
    def test_empty_versions(self, mock_session):
        tokens = OAuthTokens(access_token="a", access_token_secret="b", username="u")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"X-Discogs-Ratelimit-Remaining": "50"}
        mock_resp.json.return_value = {"versions": [], "pagination": {"pages": 1}}
        mock_session.get.return_value = mock_resp

        result = get_master_versions(26002, tokens)
        assert result == []


# ── _normalize_version ──────────────────────────────────────────────────────


class TestNormalizeVersion:
    def test_basic_mapping(self):
        version = {
            "id": 999,
            "title": "Journey To The Centre Of The Eye",
            "released": "1971",
            "country": "Germany",
            "label": "Bellaphon",
            "catno": "BLPS 19117",
            "format": ["Vinyl", "LP", "Album"],
        }
        result = _normalize_version(version, "Nektar", cover_image="https://img.jpg", master_id=26002)

        assert result["id"] == 999
        assert result["title"] == "Nektar - Journey To The Centre Of The Eye"
        assert result["year"] == 1971
        assert result["country"] == "Germany"
        assert result["label"] == ["Bellaphon"]
        assert result["catno"] == "BLPS 19117"
        assert result["format"] == ["Vinyl", "LP", "Album"]
        assert result["uri"] == "/release/999"
        assert result["cover_image"] == "https://img.jpg"
        assert result["master_id"] == 26002

    def test_year_extraction_from_full_date(self):
        version = {"id": 1, "released": "1971-06-15", "title": "X"}
        result = _normalize_version(version, "Artist")
        assert result["year"] == 1971

    def test_missing_year(self):
        version = {"id": 1, "title": "X"}
        result = _normalize_version(version, "Artist")
        assert result["year"] is None

    def test_label_wrapping(self):
        version = {"id": 1, "title": "X", "label": "Columbia"}
        result = _normalize_version(version, "Artist")
        assert result["label"] == ["Columbia"]

    def test_label_already_list(self):
        version = {"id": 1, "title": "X", "label": ["A", "B"]}
        result = _normalize_version(version, "Artist")
        assert result["label"] == ["A", "B"]

    def test_missing_label(self):
        version = {"id": 1, "title": "X"}
        result = _normalize_version(version, "Artist")
        assert result["label"] == []

    def test_cover_and_master_id_defaults(self):
        version = {"id": 1, "title": "X"}
        result = _normalize_version(version, "Artist")
        assert result["cover_image"] is None
        assert result["master_id"] is None


# ── track overlap ────────────────────────────────────────────────────────────


class TestTrackOverlap:
    def test_exact_match(self):
        assert _track_overlap(["Flagra", "Barata Tonta"], ["Flagra", "Barata Tonta", "Vote Em Mim"]) == 2

    def test_fuzzy_match(self):
        """Slight differences (accents, casing) should still match."""
        assert _track_overlap(["Barriga da Mamãe"], ["Barriga Da Mamãe"]) == 1

    def test_no_match(self):
        assert _track_overlap(["Flagra", "Barata Tonta"], ["Lança Perfume", "Caso Sério"]) == 0

    def test_empty_inputs(self):
        assert _track_overlap([], ["Flagra"]) == 0
        assert _track_overlap(["Flagra"], []) == 0

    def test_extract_tracklist(self):
        data = {"tracklist": [
            {"position": "A1", "title": "Flagra"},
            {"position": "A2", "title": ""},
            {"position": "A3", "title": "Barata Tonta"},
        ]}
        assert _extract_tracklist(data) == ["Flagra", "Barata Tonta"]

    def test_extract_tracklist_missing(self):
        assert _extract_tracklist({}) == []


# ── master search strategy ──────────────────────────────────────────────────


class TestMasterSearchStrategy:
    MASTER_TITLE = "Nektar - Journey To The Centre Of The Eye"

    @patch("services.discogs.get_master_versions")
    @patch("services.discogs.discogs_search")
    def test_master_search_yields_normalized_versions(self, mock_search, mock_versions):
        """Strategy 2 should find masters and yield normalized versions."""
        mock_search.return_value = [
            {"id": 26002, "cover_image": "https://cover.jpg", "title": self.MASTER_TITLE},
        ]
        mock_versions.return_value = [
            {"id": 100, "title": "Journey To The Centre Of The Eye", "released": "1971",
             "country": "Germany", "label": "Bellaphon", "catno": "BLPS 19117",
             "format": ["Vinyl", "LP"]},
        ]
        results, strategy = next(generate_search_candidates(
            candidate_albums=["Journey To The Centre Of The Eye"],
            candidate_artists=["Nektar"],
            label_meta={},
            media_type="vinyl",
        ))
        assert "master" in strategy
        assert strategy != "master fallback"
        assert len(results) >= 1
        assert results[0]["master_id"] == 26002
        assert results[0]["cover_image"] == "https://cover.jpg"
        mock_versions.assert_called_once_with(26002, None, format_filter="Vinyl")

    @patch("services.discogs.get_master_versions")
    @patch("services.discogs.discogs_search")
    def test_master_dedup(self, mock_search, mock_versions):
        """Same master found via different album/artist combos should only be fetched once."""
        mock_search.return_value = [
            {"id": 26002, "cover_image": "https://cover.jpg", "title": self.MASTER_TITLE},
        ]
        mock_versions.return_value = [
            {"id": 100, "title": "Journey To The Centre Of The Eye", "released": "1971",
             "label": "Bellaphon", "format": ["Vinyl"]},
        ]
        gen = generate_search_candidates(
            candidate_albums=["Journey To The Centre Of The Eye", "Journey"],
            candidate_artists=["Nektar"],
            label_meta={},
            media_type="vinyl",
        )
        # Consume first yield (master 26002 from first album variant)
        first_results, _ = next(gen)
        assert first_results[0]["master_id"] == 26002
        # get_master_versions should be called only once for master 26002
        assert mock_versions.call_count == 1

    @patch("services.discogs.get_master_versions")
    @patch("services.discogs.discogs_search")
    def test_master_fallthrough_when_no_masters_found(self, mock_search, mock_versions):
        """When no masters are found at all, fall through to strategy 3."""
        def search_side_effect(tokens, **params):
            if params.get("type") == "master":
                return []
            return [{"title": "Nektar - Journey To The Centre Of The Eye"}]
        mock_search.side_effect = search_side_effect
        results, strategy = next(generate_search_candidates(
            candidate_albums=["Journey To The Centre Of The Eye"],
            candidate_artists=["Nektar"],
            label_meta={},
            media_type="vinyl",
        ))
        assert "master" not in strategy
        assert "release_title" in strategy or "q=" in strategy

    @patch("services.discogs.get_master_versions")
    @patch("services.discogs.discogs_search")
    def test_perfect_master_no_versions_yields_master_fallback(self, mock_search, mock_versions):
        """When a perfect master has no versions, yield the master itself as fallback."""
        mock_search.return_value = [
            {"id": 26002, "cover_image": "https://cover.jpg", "title": self.MASTER_TITLE,
             "uri": "/master/26002"},
        ]
        mock_versions.return_value = []  # No versions
        results, strategy = next(generate_search_candidates(
            candidate_albums=["Journey To The Centre Of The Eye"],
            candidate_artists=["Nektar"],
            label_meta={},
            media_type="vinyl",
        ))
        assert strategy == "master fallback"
        assert len(results) == 1
        assert results[0]["master_id"] == 26002

    @patch("services.discogs.get_master_versions")
    @patch("services.discogs.discogs_search")
    def test_perfect_master_blocks_fallthrough(self, mock_search, mock_versions):
        """When a perfect master exists, generator must not yield strategies 3–6."""
        mock_search.return_value = [
            {"id": 26002, "cover_image": "https://cover.jpg", "title": self.MASTER_TITLE},
        ]
        mock_versions.return_value = [
            {"id": 100, "title": "Journey To The Centre Of The Eye", "released": "1971",
             "label": "Bellaphon", "format": ["Vinyl"]},
        ]
        gen = generate_search_candidates(
            candidate_albums=["Journey To The Centre Of The Eye"],
            candidate_artists=["Nektar"],
            label_meta={},
            media_type="vinyl",
        )
        strategies = [strategy for _, strategy in gen]
        # Should only have master strategies + master fallback, never strict/freeform/artist-only
        for s in strategies:
            assert "master" in s, f"Unexpected non-master strategy: {s}"

    @patch("services.discogs.get_master_versions")
    @patch("services.discogs.discogs_search")
    def test_master_sanity_fail_falls_through(self, mock_search, mock_versions):
        """Masters that fail sanity check should not block fallthrough."""
        def search_side_effect(tokens, **params):
            if params.get("type") == "master":
                return [{"id": 999, "title": "ZZZXXX - QQQWWW"}]  # fails sanity
            return [{"title": "Nektar - Journey To The Centre Of The Eye"}]
        mock_search.side_effect = search_side_effect
        results, strategy = next(generate_search_candidates(
            candidate_albums=["Journey To The Centre Of The Eye"],
            candidate_artists=["Nektar"],
            label_meta={},
            media_type="vinyl",
        ))
        assert "master" not in strategy
