"""Tests for model-mismatch penalty and rejection reason amplification in score_comp_similarity."""

from scrapers.comp_matcher import parse_title, score_comp_similarity


class TestModelMismatchPenalty:
    def test_different_models_penalized(self):
        """Spacer Ring comp should score very low for Cemetery Cross listing."""
        parsed = parse_title("chrome hearts", "Chrome Hearts Cemetery Cross Ring Sterling Silver")
        score = score_comp_similarity(parsed, "Chrome Hearts Spacer Ring Silver")
        assert score < 0.2  # Well below 0.5 threshold

    def test_same_model_not_penalized(self):
        """Cemetery Cross comp should score high for Cemetery Cross listing."""
        parsed = parse_title("chrome hearts", "Chrome Hearts Cemetery Cross Ring Sterling Silver")
        score = score_comp_similarity(parsed, "Chrome Hearts Cemetery Cross Ring 925")
        assert score > 0.6

    def test_no_model_on_comp_not_penalized(self):
        """If comp has no detectable model, don't penalize — it might just be sparse."""
        parsed = parse_title("rick owens", "Rick Owens Geobasket Leather Sneakers")
        score = score_comp_similarity(parsed, "Rick Owens Leather High Top Sneakers Black")
        assert score > 0.3  # Not penalized, just missing model bonus

    def test_no_model_on_listing_not_penalized(self):
        """If listing has no detectable model, don't penalize comps that do."""
        parsed = parse_title("rick owens", "Rick Owens Leather Jacket FW08")
        score = score_comp_similarity(parsed, "Rick Owens Stooges Leather Jacket")
        assert score > 0.3

    def test_penalty_stacks_with_quality_score(self):
        """Model mismatch + low quality_score should produce very low similarity."""
        parsed = parse_title("chrome hearts", "Chrome Hearts Cemetery Cross Ring")
        score = score_comp_similarity(parsed, "Chrome Hearts Spacer Ring", comp_quality_score=0.4)
        assert score < 0.1


class TestRejectionReasonAmplification:
    def test_wrong_model_reason_strengthens_model_penalty(self):
        """A comp frequently rejected for wrong_model should score even lower on model mismatch."""
        parsed = parse_title("chrome hearts", "Chrome Hearts Cemetery Cross Ring")

        # Without rejection reasons
        score_base = score_comp_similarity(parsed, "Chrome Hearts Spacer Ring")

        # With wrong_model rejection history
        score_with_reasons = score_comp_similarity(
            parsed, "Chrome Hearts Spacer Ring",
            rejection_reasons={"wrong_model": 5}
        )
        assert score_with_reasons < score_base

    def test_outlier_reason_does_not_affect_model_score(self):
        """Outlier rejections should not amplify model-mismatch penalty."""
        parsed = parse_title("chrome hearts", "Chrome Hearts Cemetery Cross Ring")

        score_base = score_comp_similarity(parsed, "Chrome Hearts Spacer Ring")
        score_outlier = score_comp_similarity(
            parsed, "Chrome Hearts Spacer Ring",
            rejection_reasons={"outlier": 5}
        )
        # Outlier reasons don't change model scoring — these should be close
        assert abs(score_outlier - score_base) < 0.05

    def test_wrong_condition_reduces_score(self):
        """Frequent wrong_condition rejections should reduce score."""
        parsed = parse_title("rick owens", "Rick Owens Geobasket Leather Sneakers")
        comp = "Rick Owens Geobasket High Top Sneakers"

        score_base = score_comp_similarity(parsed, comp)
        score_condition = score_comp_similarity(
            parsed, comp,
            rejection_reasons={"wrong_condition": 5}
        )
        assert score_condition < score_base
