"""Tests for services/discogs.py: prefilter, score_by_metadata, _sanity_check, _best_similarity."""

from services.discogs import (
    _best_similarity,
    _sanity_check,
    prefilter,
    score_by_metadata,
)


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
        """Titles without ' - ' should still be handled (artist = full title, album = '')."""
        results = [{"title": "Some Compilation"}]
        passed = _sanity_check(results, ["Some Compilation"], ["Various"])
        # artist part won't match "Various", album part is empty
        assert len(passed) == 0


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
