"""
Query management service — reads telemetry, classifies tiers, exposes Japan targets.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import asdict

logger = logging.getLogger("query_service")

PERF_FILE = Path(__file__).parent.parent.parent / "data" / "trends" / "query_performance.json"
JAPAN_PERF_FILE = Path(__file__).parent.parent.parent / "data" / "trends" / "japan_query_performance.json"


def _load_perf_data() -> Dict[str, Any]:
    if PERF_FILE.exists():
        try:
            with open(PERF_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _load_japan_perf_data() -> Dict[str, Any]:
    if JAPAN_PERF_FILE.exists():
        try:
            with open(JAPAN_PERF_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def get_all_queries() -> List[Dict[str, Any]]:
    """Get all English queries with tier classification and performance data."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from core.query_tiering import classify_all
    from core.query_normalization import is_promoted_query, is_demoted_query

    perf_data = _load_perf_data()
    classified = classify_all(perf_data)

    results = []
    for query, result in classified.items():
        entry = perf_data.get(query, {})
        results.append({
            "query": result.query,
            "tier": result.tier.value,
            "reason": result.reason,
            "total_runs": result.total_runs,
            "total_deals": result.total_deals,
            "deal_rate": round(result.deal_rate, 4),
            "best_gap": round(result.best_gap, 4),
            "weight_multiplier": result.weight_multiplier,
            "promoted": is_promoted_query(query),
            "demoted": is_demoted_query(query),
            "junk_ratio": entry.get("junk_ratio", 0),
            "last_run": entry.get("last_run"),
            "raw_items_found": entry.get("raw_items_found", 0),
            "post_filter_candidates": entry.get("post_filter_candidates", 0),
        })

    # Sort: A first, then B, then trap; within tier by deal_rate desc
    tier_order = {"A": 0, "B": 1, "trap": 2}
    results.sort(key=lambda r: (tier_order.get(r["tier"], 9), -r["deal_rate"]))

    return results


def get_tier_summary() -> Dict[str, Any]:
    """Get tier distribution summary."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from core.query_tiering import get_tier_summary as _get_summary
    from core.query_normalization import PROMOTED_LIQUIDITY_QUERIES, DEMOTED_QUERY_FAMILIES

    perf_data = _load_perf_data()
    summary = _get_summary(perf_data)
    summary["total_queries"] = len(perf_data)
    summary["promoted_count"] = len(PROMOTED_LIQUIDITY_QUERIES)
    summary["demoted_count"] = len(DEMOTED_QUERY_FAMILIES)

    return summary


def get_japan_targets() -> List[Dict[str, Any]]:
    """Get Japanese search targets with EN mapping and performance data."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from core.japan_integration import JapanArbitrageMonitor

    monitor = JapanArbitrageMonitor.__new__(JapanArbitrageMonitor)
    targets = JapanArbitrageMonitor.SEARCH_TARGETS

    # Load Japan performance data
    jp_perf = _load_japan_perf_data()

    # Load English perf to show inherited tier
    en_perf = _load_perf_data()

    from core.query_tiering import classify_query

    results = []
    for target in targets:
        en_query = target.get("en", "")
        jp_query = target.get("jp", "")

        # Get performance for this JP query
        jp_entry = jp_perf.get(jp_query, jp_perf.get(en_query, {}))

        # Get inherited English tier
        en_entry = en_perf.get(en_query)
        en_tier_result = classify_query(en_query, en_entry)

        results.append({
            "jp": jp_query,
            "en": en_query,
            "category": target.get("category", ""),
            "brand": target.get("brand", ""),
            "weight": target.get("weight", 1.0),
            "en_tier": en_tier_result.tier.value,
            "en_deal_rate": round(en_tier_result.deal_rate, 4),
            "jp_total_runs": jp_entry.get("total_runs", 0),
            "jp_total_deals": jp_entry.get("total_deals", 0),
            "jp_last_run": jp_entry.get("last_run"),
        })

    return results


def update_query_tier(query: str, action: str) -> Dict[str, Any]:
    """
    Manually promote or demote a query by updating its telemetry.

    action: 'promote' or 'demote'

    This works by adjusting the performance data to push the query
    into A-tier or trap-tier classification.
    """
    perf_data = _load_perf_data()

    entry = perf_data.get(query, {
        "total_runs": 0,
        "total_deals": 0,
        "best_gap": 0,
        "last_run": None,
        "raw_items_found": 0,
        "post_filter_candidates": 0,
    })

    if action == "promote":
        # Give enough signal for A-tier classification
        entry["total_runs"] = max(entry.get("total_runs", 0), 5)
        entry["total_deals"] = max(entry.get("total_deals", 0), 3)
        entry["best_gap"] = max(entry.get("best_gap", 0), 0.55)
        entry["manual_override"] = "promoted"
    elif action == "demote":
        # Push toward trap tier
        entry["total_runs"] = max(entry.get("total_runs", 0), 15)
        entry["total_deals"] = 0
        entry["best_gap"] = 0
        entry["manual_override"] = "demoted"
    else:
        return {"error": f"Unknown action: {action}"}

    perf_data[query] = entry

    try:
        PERF_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PERF_FILE, "w") as f:
            json.dump(perf_data, f, indent=2)
    except Exception as e:
        return {"error": f"Failed to save: {e}"}

    # Re-classify to return new tier
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from core.query_tiering import classify_query

    result = classify_query(query, entry)

    return {
        "query": query,
        "action": action,
        "new_tier": result.tier.value,
        "reason": result.reason,
    }
