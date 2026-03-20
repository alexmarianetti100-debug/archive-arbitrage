"""Tests for core.query_tiering — A/B/trap query classification."""

import pytest
from core.query_tiering import (
    classify_query,
    classify_all,
    get_weight_multiplier,
    get_tier_summary,
    QueryTier,
    TIER_WEIGHT_MULTIPLIERS,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _entry(runs=0, deals=0, gap=0.0):
    """Shorthand for a query_performance entry."""
    return {
        "total_runs": runs,
        "total_deals": deals,
        "best_gap": gap,
        "last_run": "2026-03-10T00:00:00",
    }


# ── classify_query ────────────────────────────────────────────────────────────

class TestClassifyQuery:
    def test_no_telemetry_returns_b(self):
        r = classify_query("unknown query", None)
        assert r.tier == QueryTier.B
        assert r.reason == "no telemetry"
        assert r.weight_multiplier == 1.0

    def test_insufficient_runs_returns_b(self):
        r = classify_query("new query", _entry(runs=2, deals=2, gap=0.9))
        assert r.tier == QueryTier.B
        assert "insufficient data" in r.reason

    def test_high_deal_rate_returns_a(self):
        r = classify_query("rick owens boots", _entry(runs=10, deals=5, gap=0.8))
        assert r.tier == QueryTier.A
        assert "deal rate" in r.reason
        assert r.weight_multiplier == TIER_WEIGHT_MULTIPLIERS[QueryTier.A]

    def test_strong_gap_with_deals_returns_a(self):
        """Alternative A-tier path: deals below deal-rate threshold but strong gaps."""
        r = classify_query("jpj jacket", _entry(runs=10, deals=2, gap=0.75))
        assert r.tier == QueryTier.A
        assert "strong gaps" in r.reason

    def test_strong_gap_but_one_deal_stays_b(self):
        """Need at least 2 deals for the alt A-tier path."""
        r = classify_query("rare query", _entry(runs=5, deals=1, gap=0.9))
        assert r.tier == QueryTier.B

    def test_many_runs_zero_deals_is_trap(self):
        r = classify_query("kapital jacket", _entry(runs=35, deals=0, gap=0.0))
        assert r.tier == QueryTier.TRAP
        assert "0 deals" in r.reason
        assert r.weight_multiplier == TIER_WEIGHT_MULTIPLIERS[QueryTier.TRAP]

    def test_trap_needs_minimum_runs(self):
        """9 runs with 0 deals is still B — not enough confidence."""
        r = classify_query("new brand pants", _entry(runs=9, deals=0))
        assert r.tier == QueryTier.B

    def test_moderate_performance_is_b(self):
        """Some deals but below A-tier thresholds."""
        r = classify_query("moderate query", _entry(runs=20, deals=3, gap=0.4))
        assert r.tier == QueryTier.B
        assert r.reason == "moderate performance"

    def test_exact_threshold_a_tier(self):
        """Boundary: exactly 30% deal rate with 3 runs."""
        r = classify_query("boundary", _entry(runs=10, deals=3, gap=0.3))
        assert r.tier == QueryTier.A

    def test_exact_threshold_trap(self):
        """Boundary: exactly 10 runs, 0 deals."""
        r = classify_query("boundary trap", _entry(runs=10, deals=0))
        assert r.tier == QueryTier.TRAP


# ── classify_all ──────────────────────────────────────────────────────────────

class TestClassifyAll:
    def test_classifies_all_entries(self):
        perf = {
            "good query": _entry(runs=10, deals=5),
            "bad query": _entry(runs=20, deals=0),
            "new query": _entry(runs=1, deals=0),
        }
        results = classify_all(perf)
        assert len(results) == 3
        assert results["good query"].tier == QueryTier.A
        assert results["bad query"].tier == QueryTier.TRAP
        assert results["new query"].tier == QueryTier.B


# ── get_weight_multiplier ────────────────────────────────────────────────────

class TestGetWeightMultiplier:
    def test_a_tier_boost(self):
        perf = {"q": _entry(runs=10, deals=5)}
        assert get_weight_multiplier("q", perf) == 3.5

    def test_trap_demotion(self):
        perf = {"q": _entry(runs=30, deals=0)}
        assert get_weight_multiplier("q", perf) == 0.15

    def test_unknown_query_neutral(self):
        assert get_weight_multiplier("never seen", {}) == 1.0

    def test_case_insensitive_lookup(self):
        """get_weight_multiplier falls back to lowercase key match."""
        perf = {"rick owens boots": _entry(runs=10, deals=5)}
        # Exact key miss but lowercase fallback finds it
        assert get_weight_multiplier("Rick Owens Boots", perf) == 3.5
        # Direct match also works
        assert get_weight_multiplier("rick owens boots", perf) == 3.5


# ── get_tier_summary ─────────────────────────────────────────────────────────

class TestGetTierSummary:
    def test_summary_structure(self):
        perf = {
            "a1": _entry(runs=10, deals=5),
            "a2": _entry(runs=5, deals=3, gap=0.7),
            "b1": _entry(runs=2, deals=0),
            "trap1": _entry(runs=15, deals=0),
            "trap2": _entry(runs=50, deals=0),
        }
        summary = get_tier_summary(perf)
        assert summary["a_count"] == 2
        assert summary["b_count"] == 1
        assert summary["trap_count"] == 2
        assert len(summary["top_a"]) == 2
        assert len(summary["worst_traps"]) == 2

    def test_empty_perf(self):
        summary = get_tier_summary({})
        assert summary["a_count"] == 0
        assert summary["trap_count"] == 0
