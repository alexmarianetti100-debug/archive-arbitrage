"""Tests for exact comp matching — hard dimension gates."""

import pytest
from scrapers.comp_matcher import parse_title, is_exact_match, match_quality


class TestIsExactMatch:
    """Hard dimension gate: brand, model, item_type, line, material."""

    def test_identical_items_match(self):
        listing = parse_title("rick owens", "Rick Owens Geobasket Leather Sneakers Black")
        comp = parse_title("rick owens", "Rick Owens Geobasket Leather High Top Black")
        assert is_exact_match(listing, comp) is True

    def test_different_model_rejects(self):
        listing = parse_title("rick owens", "Rick Owens Geobasket Leather")
        comp = parse_title("rick owens", "Rick Owens Ramones Low Canvas")
        assert is_exact_match(listing, comp) is False

    def test_different_line_rejects(self):
        """DRKSHDW listing must NOT match mainline comps."""
        listing = parse_title("rick owens", "Rick Owens DRKSHDW Canvas Low Sneakers")
        comp = parse_title("rick owens", "Rick Owens Geobasket Leather Sneakers")
        assert is_exact_match(listing, comp) is False

    def test_different_material_rejects(self):
        """Canvas listing must NOT match leather comps."""
        listing = parse_title("rick owens", "Rick Owens Geobasket Canvas")
        comp = parse_title("rick owens", "Rick Owens Geobasket Leather")
        assert is_exact_match(listing, comp) is False

    def test_material_skip_when_undetectable(self):
        """If neither title mentions material, skip material check."""
        listing = parse_title("rick owens", "Rick Owens Geobasket Black")
        comp = parse_title("rick owens", "Rick Owens Geobasket Size 43")
        assert is_exact_match(listing, comp) is True

    def test_material_skip_when_one_undetectable(self):
        """If only one title mentions material, skip material check."""
        listing = parse_title("rick owens", "Rick Owens Geobasket Leather Black")
        comp = parse_title("rick owens", "Rick Owens Geobasket Size 43")
        assert is_exact_match(listing, comp) is True

    def test_different_brand_rejects(self):
        listing = parse_title("rick owens", "Rick Owens Geobasket")
        comp = parse_title("balenciaga", "Balenciaga Triple S")
        assert is_exact_match(listing, comp) is False

    def test_different_item_type_rejects(self):
        """Sneakers must NOT match jackets."""
        listing = parse_title("rick owens", "Rick Owens Geobasket Sneakers")
        comp = parse_title("rick owens", "Rick Owens Leather Jacket")
        assert is_exact_match(listing, comp) is False

    def test_no_model_both_sides_passes(self):
        """When neither has a detected model, pass (don't over-filter)."""
        listing = parse_title("rick owens", "Rick Owens Leather Jacket FW08")
        comp = parse_title("rick owens", "Rick Owens Leather Jacket SS09")
        assert is_exact_match(listing, comp) is True

    def test_model_detected_one_side_only_passes(self):
        """If only one side has a model, pass (comp titles are often sparse)."""
        listing = parse_title("rick owens", "Rick Owens Stooges Leather Jacket")
        comp = parse_title("rick owens", "Rick Owens Leather Jacket Black")
        assert is_exact_match(listing, comp) is True

    def test_same_line_both_diffusion_passes(self):
        """Two DRKSHDW items should match."""
        listing = parse_title("rick owens", "Rick Owens DRKSHDW Pods Sneakers Canvas")
        comp = parse_title("rick owens", "Rick Owens DRKSHDW Pods Low Canvas")
        assert is_exact_match(listing, comp) is True

    def test_type_alias_geobasket_boots_vs_sneakers(self):
        """Geobasket classified as boots should match Geobasket classified as sneakers via TYPE_ALIASES."""
        listing = parse_title("rick owens", "Rick Owens Geobasket High Top Sneakers")
        comp = parse_title("rick owens", "Rick Owens Geobasket Boots Leather")
        assert is_exact_match(listing, comp) is True

    def test_type_alias_tabi_boots_vs_loafers(self):
        """Tabi boots should match Tabi loafers via TYPE_ALIASES."""
        listing = parse_title("maison margiela", "Maison Margiela Tabi Boots")
        comp = parse_title("maison margiela", "Maison Margiela Tabi Loafers")
        assert is_exact_match(listing, comp) is True


class TestMatchQuality:
    """Soft ranking: season, size, condition, recency."""

    def test_identical_item_scores_high(self):
        listing = parse_title("rick owens", "Rick Owens Geobasket Leather Black SS24")
        comp = parse_title("rick owens", "Rick Owens Geobasket Leather Black SS24")
        score = match_quality(listing, comp)
        # Identical titles without explicit size/condition keywords get neutral credit
        # for those dimensions, so score is ~0.65-0.75 (not 1.0)
        assert score >= 0.6

    def test_different_season_scores_lower(self):
        listing = parse_title("rick owens", "Rick Owens Geobasket Leather SS24")
        comp_same = parse_title("rick owens", "Rick Owens Geobasket Leather SS24")
        comp_diff = parse_title("rick owens", "Rick Owens Geobasket Leather FW18")
        assert match_quality(listing, comp_same) > match_quality(listing, comp_diff)

    def test_returns_0_to_1_range(self):
        listing = parse_title("rick owens", "Rick Owens Geobasket Leather")
        comp = parse_title("rick owens", "Rick Owens Geobasket Leather")
        score = match_quality(listing, comp)
        assert 0.0 <= score <= 1.0

    def test_no_shared_soft_dimensions_still_returns_positive(self):
        """Even with no soft dimension overlap, score should be > 0."""
        listing = parse_title("rick owens", "Rick Owens Geobasket")
        comp = parse_title("rick owens", "Rick Owens Geobasket")
        score = match_quality(listing, comp)
        assert score > 0.0


class TestFootwearSubTypes:
    """Sneakers and boots should be separate item types."""

    def test_sneakers_vs_boots_rejects(self):
        listing = parse_title("balenciaga", "Balenciaga Triple S Sneakers White")
        comp = parse_title("balenciaga", "Balenciaga Santiago Leather Boots Black")
        assert is_exact_match(listing, comp) is False

    def test_sneakers_vs_sneakers_passes(self):
        listing = parse_title("balenciaga", "Balenciaga Triple S Sneakers")
        comp = parse_title("balenciaga", "Balenciaga Triple S Trainers White")
        assert is_exact_match(listing, comp) is True

    def test_loafers_vs_sneakers_rejects(self):
        listing = parse_title("prada", "Prada Leather Loafers")
        comp = parse_title("prada", "Prada Americas Cup Sneakers")
        assert is_exact_match(listing, comp) is False

    def test_boots_vs_boots_passes(self):
        listing = parse_title("ann demeulemeester", "Ann Demeulemeester Leather Boots")
        comp = parse_title("ann demeulemeester", "Ann Demeulemeester Lace Up Boots Black")
        assert is_exact_match(listing, comp) is True
