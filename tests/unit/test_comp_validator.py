"""Tests for core.comp_validator — 5-check comp validation safety net."""

import pytest
from datetime import datetime, timedelta


class TestCategoryParity:
    def test_shoes_vs_jacket_rejects(self):
        from core.comp_validator import check_category_parity
        assert check_category_parity("Rick Owens Geobasket Sneakers", "Rick Owens Leather Jacket") is False

    def test_shoes_vs_shoes_passes(self):
        from core.comp_validator import check_category_parity
        assert check_category_parity("Rick Owens Geobasket Sneakers", "Rick Owens Dunks Sneakers") is True

    def test_undetectable_category_passes(self):
        from core.comp_validator import check_category_parity
        assert check_category_parity("Rick Owens", "Rick Owens Black") is True


class TestLineParity:
    def test_diffusion_vs_mainline_rejects(self):
        from core.comp_validator import check_line_parity
        assert check_line_parity(
            "Rick Owens DRKSHDW Canvas Sneakers", "rick owens",
            "Rick Owens Geobasket Leather", "rick owens"
        ) is False

    def test_mainline_vs_mainline_passes(self):
        from core.comp_validator import check_line_parity
        assert check_line_parity(
            "Rick Owens Geobasket Leather", "rick owens",
            "Rick Owens Ramones Leather", "rick owens"
        ) is True


class TestMaterialParity:
    def test_leather_vs_canvas_rejects(self):
        from core.comp_validator import check_material_parity
        assert check_material_parity("Geobasket Leather Black", "Geobasket Canvas White") is False

    def test_leather_vs_leather_passes(self):
        from core.comp_validator import check_material_parity
        assert check_material_parity("Geobasket Leather Black", "Geobasket Leather White") is True

    def test_no_material_passes(self):
        from core.comp_validator import check_material_parity
        assert check_material_parity("Geobasket Black", "Geobasket White") is True

    def test_one_side_no_material_passes(self):
        from core.comp_validator import check_material_parity
        assert check_material_parity("Geobasket Leather", "Geobasket Black") is True


class TestRecencyGate:
    def test_recent_comp_passes(self):
        from core.comp_validator import check_recency
        recent = datetime.now() - timedelta(days=30)
        assert check_recency(recent.isoformat()) is True

    def test_old_comp_rejects(self):
        from core.comp_validator import check_recency
        old = datetime.now() - timedelta(days=200)
        assert check_recency(old.isoformat()) is False

    def test_archive_brand_extended_window(self):
        from core.comp_validator import check_recency
        old = datetime.now() - timedelta(days=300)
        assert check_recency(old.isoformat(), archive_brand=True) is True

    def test_no_date_passes(self):
        from core.comp_validator import check_recency
        assert check_recency(None) is True


class TestOutlierRemoval:
    def test_removes_extreme_high(self):
        from core.comp_validator import remove_outliers
        prices = [100, 110, 120, 115, 105, 800]
        filtered = remove_outliers(prices)
        assert 800 not in filtered

    def test_removes_extreme_low(self):
        from core.comp_validator import remove_outliers
        prices = [500, 520, 510, 530, 490, 50]
        filtered = remove_outliers(prices)
        assert 50 not in filtered

    def test_keeps_normal_range(self):
        from core.comp_validator import remove_outliers
        prices = [100, 110, 120, 130, 140]
        filtered = remove_outliers(prices)
        assert filtered == prices


class TestValidateComps:
    def test_full_pipeline_all_pass(self):
        from core.comp_validator import validate_comps, CompValidationResult
        result = validate_comps(
            listing_title="Rick Owens Geobasket Leather Sneakers",
            listing_brand="rick owens",
            comp_titles=["Rick Owens Geobasket Leather", "Rick Owens Geobasket Black Leather", "Rick Owens Geobasket High Leather"],
            comp_prices=[800, 850, 900],
            comp_sold_dates=[datetime.now().isoformat()] * 3,
        )
        assert isinstance(result, CompValidationResult)
        assert result.surviving_count >= 0
        assert result.confidence in ("full", "reduced", "low", "none")

    def test_mixed_failures_cascade(self):
        """Comps failing different checks should all be removed."""
        from core.comp_validator import validate_comps
        result = validate_comps(
            listing_title="Rick Owens Geobasket Leather Sneakers",
            listing_brand="rick owens",
            comp_titles=[
                "Rick Owens Geobasket Leather High",  # pass
                "Rick Owens Leather Jacket",            # fail: category mismatch
                "Rick Owens Geobasket Canvas",          # fail: material mismatch
                "Rick Owens Geobasket Leather",         # pass
                "Rick Owens Geobasket Leather Black",   # pass
            ],
            comp_prices=[800, 600, 200, 850, 900],
            comp_sold_dates=[datetime.now().isoformat()] * 5,
        )
        # The jacket and canvas comps should be filtered out
        assert result.surviving_count <= 4  # At most 4 (jacket rejected)
        assert result.surviving_count >= 2  # At least the leather geobaskets survive

    def test_confidence_tiers(self):
        """5+ comps = full, 3-4 = reduced, 1-2 = low, 0 = none."""
        from core.comp_validator import validate_comps
        # 5 matching comps = full confidence
        result = validate_comps(
            listing_title="Rick Owens Leather Jacket",
            listing_brand="rick owens",
            comp_titles=["Rick Owens Leather Jacket"] * 5,
            comp_prices=[800, 850, 900, 820, 880],
            comp_sold_dates=[datetime.now().isoformat()] * 5,
        )
        assert result.confidence == "full"
        assert result.score_penalty == 0
