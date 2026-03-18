"""Tests for the quality_weight function in comp_matcher."""

from scrapers.comp_matcher import quality_weight


class TestQualityWeight:
    def test_none_returns_one(self):
        assert quality_weight(None) == 1.0

    def test_perfect_score(self):
        assert quality_weight(1.0) == 1.0

    def test_zero_score(self):
        assert quality_weight(0.0) == 0.5

    def test_half_score(self):
        assert quality_weight(0.5) == 0.75

    def test_clamps_above_one(self):
        assert quality_weight(1.5) == 1.0

    def test_clamps_below_zero(self):
        assert quality_weight(-0.5) == 0.5

    def test_score_integrated_in_similarity(self):
        """quality_score should reduce the final similarity score."""
        from scrapers.comp_matcher import parse_title, score_comp_similarity
        parsed = parse_title("rick owens", "Rick Owens Geobasket Leather Sneakers")
        comp_title = "Rick Owens Geobasket High Top Sneakers"

        score_good = score_comp_similarity(parsed, comp_title, comp_quality_score=1.0)
        score_bad = score_comp_similarity(parsed, comp_title, comp_quality_score=0.0)

        assert score_good > score_bad
        assert score_bad >= score_good * 0.5  # floor is 50%
