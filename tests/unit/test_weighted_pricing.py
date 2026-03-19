"""Tests for similarity-weighted median pricing."""

from types import SimpleNamespace
from unittest.mock import patch


def _make_comp(title, price, source="grailed", source_id=""):
    """Create a mock sold comp object."""
    return SimpleNamespace(
        title=title, price=price, source=source,
        source_id=source_id or f"id_{price}",
        raw_data={}, url="", size=None, condition=None,
    )


class TestComputeWeightedPrice:
    def _import(self):
        from gap_hunter import compute_weighted_price
        return compute_weighted_price

    def test_drop_gate_removes_low_similarity(self):
        """With 3+ comps above 0.5, comps below 0.5 are dropped."""
        fn = self._import()
        comps = [
            _make_comp("Chrome Hearts Cemetery Cross Ring Silver", 2500),
            _make_comp("Chrome Hearts Cemetery Cross Ring", 2200),
            _make_comp("Chrome Hearts Cemetery Cross Pendant", 2400),
            _make_comp("Chrome Hearts Spacer Ring", 200),
            _make_comp("Chrome Hearts Ring Silver", 400),
        ]
        sold_data = SimpleNamespace(
            query="chrome hearts ring", avg_price=1500, median_price=1500, count=5,
            liquidation_anchor=None, downside_anchor=None,
            _confidence="medium", _cv=0.3, _hyper_pricing=False,
            comp_confidence_penalty=0, pricing_confidence="medium",
            comp_titles=[c.title for c in comps],
            comp_prices=[c.price for c in comps],
            comp_urls=[""] * 5,
            timestamp=0,
        )
        with patch("db.sqlite_models.get_comp_quality_scores", return_value={}):
            result = fn("Chrome Hearts Cemetery Cross Ring Sterling Silver Size 9", "chrome hearts", comps, sold_data)

        assert result is not None
        assert result.median_price > 1500
        assert result.count <= 4

    def test_hard_gate_returns_none_when_no_match(self):
        """If no comps have similarity >= 0.5, return None."""
        fn = self._import()
        comps = [
            _make_comp("Chrome Hearts Trucker Hat", 800),
            _make_comp("Chrome Hearts Hoodie", 600),
        ]
        sold_data = SimpleNamespace(
            query="chrome hearts ring", avg_price=700, median_price=700, count=2,
            liquidation_anchor=None, downside_anchor=None,
            _confidence="medium", _cv=0.3, _hyper_pricing=False,
            comp_confidence_penalty=0, pricing_confidence="medium",
            comp_titles=[c.title for c in comps],
            comp_prices=[c.price for c in comps],
            comp_urls=[""] * 2,
            timestamp=0,
        )
        with patch("db.sqlite_models.get_comp_quality_scores", return_value={}):
            result = fn("Chrome Hearts Cemetery Cross Ring Silver", "chrome hearts", comps, sold_data)

        assert result is None

    def test_downweight_fallback_when_few_above_threshold(self):
        """If 1-2 above 0.5, keep all but weight by similarity."""
        fn = self._import()
        comps = [
            _make_comp("Rick Owens Geobasket Leather", 900),
            _make_comp("Rick Owens Sneakers Black", 500),
            _make_comp("Rick Owens Pants Cargo", 300),
        ]
        sold_data = SimpleNamespace(
            query="rick owens geobasket", avg_price=550, median_price=500, count=3,
            liquidation_anchor=None, downside_anchor=None,
            _confidence="medium", _cv=0.3, _hyper_pricing=False,
            comp_confidence_penalty=0, pricing_confidence="medium",
            comp_titles=[c.title for c in comps],
            comp_prices=[c.price for c in comps],
            comp_urls=[""] * 3,
            timestamp=0,
        )
        with patch("db.sqlite_models.get_comp_quality_scores", return_value={}):
            result = fn("Rick Owens Geobasket Black Leather EU 43", "rick owens", comps, sold_data)

        assert result is not None
        assert result.avg_price > 500

    def test_quality_score_reduces_effective_similarity(self):
        """A comp with low quality_score gets its similarity reduced."""
        fn = self._import()
        comps = [
            _make_comp("Chrome Hearts Forever Ring Silver", 400, source_id="good1"),
            _make_comp("Chrome Hearts Forever Ring", 380, source_id="good2"),
            _make_comp("Chrome Hearts Forever Ring 925", 420, source_id="good3"),
            _make_comp("Chrome Hearts Forever Ring Sterling", 350, source_id="bad1"),
        ]
        sold_data = SimpleNamespace(
            query="chrome hearts forever ring", avg_price=390, median_price=390, count=4,
            liquidation_anchor=None, downside_anchor=None,
            _confidence="medium", _cv=0.1, _hyper_pricing=False,
            comp_confidence_penalty=0, pricing_confidence="medium",
            comp_titles=[c.title for c in comps],
            comp_prices=[c.price for c in comps],
            comp_urls=[""] * 4,
            timestamp=0,
        )
        quality_scores = {("grailed", "bad1"): 0.2}
        with patch("db.sqlite_models.get_comp_quality_scores", return_value=quality_scores):
            result = fn("Chrome Hearts Forever Ring Sterling Silver", "chrome hearts", comps, sold_data)

        assert result is not None
