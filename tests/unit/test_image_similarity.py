"""Tests for image similarity boost and image data storage."""

from types import SimpleNamespace
from unittest.mock import patch


class TestImageSimilarityBoost:
    def test_strong_match_boosts(self):
        """Identical pHashes should boost score."""
        from scrapers.comp_matcher import image_similarity_boost
        assert image_similarity_boost("a0b0c0d0e0f01020", "a0b0c0d0e0f01020") == 1.2

    def test_moderate_distance_neutral(self):
        """Moderate hamming distance (~10 bits) should return 1.0."""
        from scrapers.comp_matcher import image_similarity_boost
        # These differ by 10 bits — in the neutral 6-15 range
        boost = image_similarity_boost("a0b0c0d0e0f01020", "a0b0c0d0e0f013df")
        assert boost == 1.0

    def test_strong_mismatch_dampens(self):
        """Very different pHashes should dampen score."""
        from scrapers.comp_matcher import image_similarity_boost
        boost = image_similarity_boost("0000000000000000", "ffffffffffffffff")
        assert boost == 0.5

    def test_missing_listing_hash_neutral(self):
        from scrapers.comp_matcher import image_similarity_boost
        assert image_similarity_boost(None, "a0b0c0d0e0f01020") == 1.0

    def test_missing_comp_hash_neutral(self):
        from scrapers.comp_matcher import image_similarity_boost
        assert image_similarity_boost("a0b0c0d0e0f01020", None) == 1.0

    def test_both_missing_neutral(self):
        from scrapers.comp_matcher import image_similarity_boost
        assert image_similarity_boost(None, None) == 1.0

    def test_mismatched_lengths_neutral(self):
        from scrapers.comp_matcher import image_similarity_boost
        assert image_similarity_boost("a0b0", "a0b0c0d0e0f01020") == 1.0


class TestImageBoostIntegration:
    def test_image_match_raises_effective_similarity(self):
        from scrapers.comp_matcher import (
            parse_title, score_comp_similarity, image_similarity_boost,
        )
        parsed = parse_title("chrome hearts", "Chrome Hearts Forever Ring Silver")
        title_sim = score_comp_similarity(parsed, "Chrome Hearts Forever Ring Sterling")
        boosted = title_sim * image_similarity_boost("a0b0c0d0e0f01020", "a0b0c0d0e0f01020")
        assert boosted > title_sim

    def test_image_mismatch_lowers_effective_similarity(self):
        from scrapers.comp_matcher import (
            parse_title, score_comp_similarity, image_similarity_boost,
        )
        parsed = parse_title("chrome hearts", "Chrome Hearts Forever Ring Silver")
        title_sim = score_comp_similarity(parsed, "Chrome Hearts Forever Ring Sterling")
        dampened = title_sim * image_similarity_boost("0000000000000000", "ffffffffffffffff")
        assert dampened < title_sim

    def test_weighted_price_accepts_listing_phash(self):
        """compute_weighted_price should accept and use listing_phash param."""
        def _make_comp(title, price, source_id="", phash=None):
            return SimpleNamespace(
                title=title, price=price, source="grailed",
                source_id=source_id or f"id_{price}",
                raw_data={}, url="", size=None, condition=None,
                phash=phash,
            )

        from gap_hunter import compute_weighted_price
        comps = [
            _make_comp("Chrome Hearts Forever Ring", 400, "c1", phash="a0b0c0d0e0f01020"),
            _make_comp("Chrome Hearts Forever Ring 925", 420, "c2", phash="a0b0c0d0e0f01020"),
            _make_comp("Chrome Hearts Forever Ring Silver", 380, "c3", phash="a0b0c0d0e0f01020"),
        ]
        sold_data = SimpleNamespace(
            query="chrome hearts forever ring", avg_price=400,
            median_price=400, count=3,
            liquidation_anchor=None, downside_anchor=None,
            _confidence="medium", _cv=0.1, _hyper_pricing=False,
            comp_confidence_penalty=0, pricing_confidence="medium",
            comp_titles=[c.title for c in comps],
            comp_prices=[c.price for c in comps],
            comp_urls=[""] * 3,
            timestamp=0,
        )
        with patch("db.sqlite_models.get_comp_quality_scores", return_value={}):
            result = compute_weighted_price(
                "Chrome Hearts Forever Ring Sterling Silver",
                "chrome hearts", comps, sold_data,
                listing_phash="a0b0c0d0e0f01020",
            )
        assert result is not None
