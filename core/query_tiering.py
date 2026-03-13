"""
Query Tiering — classify search queries as A / B / trap based on telemetry.

Uses the persisted query_performance.json data to sort queries into tiers
that inform rotation weight in TrendEngine.get_cycle_targets().

Tiers:
    A-tier  — Proven deal-finders.  Get a weight boost in rotation.
    B-tier  — New or inconclusive.  Neutral weight (benefit of the doubt).
    Trap    — Many runs, zero deals. Demoted weight (not excluded — that's
              what the dead-query system is for at 50+ runs).

Design constraints:
    - Conservative: requires real evidence before promoting or penalizing.
    - Sparse-data safe: queries with few runs stay B-tier by default.
    - No hard-coded query lists — driven entirely by telemetry.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger("query_tiering")


class QueryTier(str, Enum):
    A = "A"
    B = "B"
    TRAP = "trap"


# ── Thresholds ────────────────────────────────────────────────────────────────
# Minimum runs before we judge a query (below this → always B-tier)
MIN_RUNS_TO_JUDGE = 3

# A-tier: must clear one of these bars
A_TIER_MIN_DEAL_RATE = 0.30       # deals / runs
A_TIER_ALT_MIN_DEALS = 2          # alternative: at least N deals ...
A_TIER_ALT_MIN_GAP = 0.50         # ... with a best gap above this

# Trap-tier: many runs, zero deals
TRAP_MIN_RUNS = 10                # need confidence before penalizing
TRAP_MAX_DEALS = 0                # must have found exactly 0 deals

# ── Weight multipliers (applied in TrendEngine rotation weighting) ────────────
TIER_WEIGHT_MULTIPLIERS = {
    QueryTier.A: 2.5,
    QueryTier.B: 1.0,
    QueryTier.TRAP: 0.2,
}


@dataclass(frozen=True)
class QueryTierResult:
    """Classification result for a single query."""
    query: str
    tier: QueryTier
    reason: str
    total_runs: int
    total_deals: int
    deal_rate: float
    best_gap: float
    weight_multiplier: float


def classify_query(query: str, perf_entry: Optional[dict]) -> QueryTierResult:
    """
    Classify a single query based on its performance telemetry.

    Args:
        query: The search query string.
        perf_entry: Dict from query_performance.json, or None if never seen.

    Returns:
        QueryTierResult with tier, reason, and weight multiplier.
    """
    if not perf_entry:
        return QueryTierResult(
            query=query,
            tier=QueryTier.B,
            reason="no telemetry",
            total_runs=0,
            total_deals=0,
            deal_rate=0.0,
            best_gap=0.0,
            weight_multiplier=TIER_WEIGHT_MULTIPLIERS[QueryTier.B],
        )

    total_runs = perf_entry.get("total_runs", 0)
    total_deals = perf_entry.get("total_deals", 0)
    best_gap = perf_entry.get("best_gap", 0.0)
    deal_rate = total_deals / total_runs if total_runs > 0 else 0.0

    # Not enough data to judge — stay neutral
    if total_runs < MIN_RUNS_TO_JUDGE:
        return QueryTierResult(
            query=query,
            tier=QueryTier.B,
            reason=f"insufficient data ({total_runs} runs)",
            total_runs=total_runs,
            total_deals=total_deals,
            deal_rate=deal_rate,
            best_gap=best_gap,
            weight_multiplier=TIER_WEIGHT_MULTIPLIERS[QueryTier.B],
        )

    # A-tier: proven performer (primary path: high deal rate)
    if deal_rate >= A_TIER_MIN_DEAL_RATE:
        return QueryTierResult(
            query=query,
            tier=QueryTier.A,
            reason=f"high deal rate ({deal_rate:.0%})",
            total_runs=total_runs,
            total_deals=total_deals,
            deal_rate=deal_rate,
            best_gap=best_gap,
            weight_multiplier=TIER_WEIGHT_MULTIPLIERS[QueryTier.A],
        )

    # A-tier: alternative path — found real deals with strong gaps
    if total_deals >= A_TIER_ALT_MIN_DEALS and best_gap >= A_TIER_ALT_MIN_GAP:
        return QueryTierResult(
            query=query,
            tier=QueryTier.A,
            reason=f"strong gaps ({best_gap:.0%}) with {total_deals} deals",
            total_runs=total_runs,
            total_deals=total_deals,
            deal_rate=deal_rate,
            best_gap=best_gap,
            weight_multiplier=TIER_WEIGHT_MULTIPLIERS[QueryTier.A],
        )

    # Trap-tier: many runs, zero results
    if total_runs >= TRAP_MIN_RUNS and total_deals <= TRAP_MAX_DEALS:
        return QueryTierResult(
            query=query,
            tier=QueryTier.TRAP,
            reason=f"0 deals in {total_runs} runs",
            total_runs=total_runs,
            total_deals=total_deals,
            deal_rate=deal_rate,
            best_gap=best_gap,
            weight_multiplier=TIER_WEIGHT_MULTIPLIERS[QueryTier.TRAP],
        )

    # Default: B-tier (some deals but not enough to promote, or moderate runs)
    return QueryTierResult(
        query=query,
        tier=QueryTier.B,
        reason="moderate performance",
        total_runs=total_runs,
        total_deals=total_deals,
        deal_rate=deal_rate,
        best_gap=best_gap,
        weight_multiplier=TIER_WEIGHT_MULTIPLIERS[QueryTier.B],
    )


def classify_all(perf_data: dict) -> dict[str, QueryTierResult]:
    """
    Classify all queries in the performance data.

    Args:
        perf_data: Full query_performance.json dict.

    Returns:
        Dict mapping query string → QueryTierResult.
    """
    return {q: classify_query(q, entry) for q, entry in perf_data.items()}


def get_weight_multiplier(query: str, perf_data: dict) -> float:
    """
    Quick lookup: return the weight multiplier for a query.
    Used directly in TrendEngine's rotation weighting.
    """
    entry = perf_data.get(query) or perf_data.get(query.lower())
    result = classify_query(query, entry)
    return result.weight_multiplier


def get_tier_summary(perf_data: dict) -> dict:
    """
    Return a summary of tier distribution for logging.

    Returns:
        Dict with counts per tier and top A-tier / trap queries.
    """
    results = classify_all(perf_data)
    a_queries = [r for r in results.values() if r.tier == QueryTier.A]
    b_queries = [r for r in results.values() if r.tier == QueryTier.B]
    trap_queries = [r for r in results.values() if r.tier == QueryTier.TRAP]

    # Sort A by deal rate desc, trap by runs desc
    a_queries.sort(key=lambda r: r.deal_rate, reverse=True)
    trap_queries.sort(key=lambda r: r.total_runs, reverse=True)

    return {
        "a_count": len(a_queries),
        "b_count": len(b_queries),
        "trap_count": len(trap_queries),
        "top_a": [f"{r.query} ({r.deal_rate:.0%})" for r in a_queries[:5]],
        "worst_traps": [f"{r.query} ({r.total_runs} runs)" for r in trap_queries[:5]],
    }
