"""
Comp Feedback Service — rejection processing and re-grading.

When a user rejects a comp, this service:
1. Updates the item_comp feedback status
2. Updates the sold_comp rejection counters
3. Re-grades the item from remaining comps (or flags for review)
"""

import logging
import statistics
from datetime import datetime
from typing import Any, Dict, List, Optional

from db.sqlite_models import (
    _get_conn,
    get_active_item_comps,
    get_item_by_id,
    insert_regrade_log,
    set_item_needs_review,
    update_item_comp_feedback,
    update_sold_comp_rejection,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_COMPS_FOR_REGRADE = 3
MIN_MARGIN_FLOOR = 0.35  # Enforce minimum 35% margin on re-grade


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def process_comp_feedback(
    item_id: int,
    item_comp_id: int,
    status: str,
    reason: Optional[str] = None,
) -> dict:
    """Process comp feedback (accept or reject) and optionally re-grade.

    Uses BEGIN IMMEDIATE to prevent concurrent feedback from producing
    inconsistent re-grades.

    Returns a result dict describing what happened.  See module docstring
    for response shapes.
    """
    # Acquire exclusive lock to prevent concurrent feedback races
    lock_conn = _get_conn()
    try:
        lock_conn.execute("BEGIN IMMEDIATE")
    except Exception:
        lock_conn.close()
        raise

    try:
        # ------------------------------------------------------------------
        # 1. Validate item and item_comp exist
        # ------------------------------------------------------------------
        item = get_item_by_id(item_id)
        if item is None:
            lock_conn.rollback()
            lock_conn.close()
            return {"error": "Item not found"}

        # Update the item_comp feedback row — validates it exists AND belongs to this item.
        updated_comp = update_item_comp_feedback(item_comp_id, status, reason, expected_item_id=item_id)
        if updated_comp is None:
            lock_conn.rollback()
            lock_conn.close()
            return {"error": "Item comp not found or does not belong to this item"}

        # ------------------------------------------------------------------
        # 2. If rejected, propagate to sold_comp rejection counters
        # ------------------------------------------------------------------
        if status == "rejected" and reason:
            sold_comp_id = updated_comp.get("sold_comp_id")
            if sold_comp_id:
                try:
                    update_sold_comp_rejection(sold_comp_id, reason)
                except Exception:
                    logger.exception(
                        "Failed to update sold_comp rejection for sold_comp_id=%s",
                        sold_comp_id,
                    )

        # ------------------------------------------------------------------
        # 3. Count remaining (non-rejected) comps
        # ------------------------------------------------------------------
        active_comps = get_active_item_comps(item_id)
        comps_remaining = len(active_comps)

        # ------------------------------------------------------------------
        # 4. If acceptance — nothing more to do
        # ------------------------------------------------------------------
        if status == "accepted":
            lock_conn.commit()
            lock_conn.close()
            return {
                "updated": True,
                "regrade": {
                    "triggered": False,
                    "comps_remaining": comps_remaining,
                    "reason": "acceptance_only",
                },
            }

        # ------------------------------------------------------------------
        # 5. Capture "before" snapshot for the regrade log
        # ------------------------------------------------------------------
        grade_before = item.grade
        price_before = item.exact_sell_price
        margin_before = item.exact_margin

        # ------------------------------------------------------------------
        # 6. Enough comps to re-grade?
        # ------------------------------------------------------------------
        if comps_remaining >= MIN_COMPS_FOR_REGRADE:
            regrade = _regrade_from_comps(item, active_comps)

            # Write regrade_log
            pool_health = _calc_pool_health(active_comps)
            insert_regrade_log({
                "item_id": item_id,
                "trigger": "comp_rejection",
                "comps_before": comps_remaining + 1,
                "comps_after": comps_remaining,
                "grade_before": grade_before,
                "grade_after": regrade["grade"],
                "price_before": price_before,
                "price_after": regrade["sell_price"],
                "margin_before": margin_before,
                "margin_after": regrade["margin"],
                "comp_pool_health": pool_health,
                "rejected_comp_id": item_comp_id,
            })

            # Clear needs_review since we successfully re-graded
            set_item_needs_review(item_id, 0)

            lock_conn.commit()
            lock_conn.close()
            return {
                "updated": True,
                "regrade": {
                    "triggered": True,
                    "comps_remaining": comps_remaining,
                    "grade_before": grade_before,
                    "grade_after": regrade["grade"],
                    "price_before": price_before,
                    "price_after": regrade["sell_price"],
                    "margin_before": margin_before,
                    "margin_after": regrade["margin"],
                },
            }

        # ------------------------------------------------------------------
        # 7. Below threshold — flag for manual review
        # ------------------------------------------------------------------
        set_item_needs_review(item_id, 1)

        pool_health = _calc_pool_health(active_comps) if active_comps else 0.0
        insert_regrade_log({
            "item_id": item_id,
            "trigger": "comp_rejection",
            "comps_before": comps_remaining + 1,
            "comps_after": comps_remaining,
            "grade_before": grade_before,
            "grade_after": grade_before,
            "price_before": price_before,
            "price_after": price_before,
            "margin_before": margin_before,
            "margin_after": margin_before,
            "comp_pool_health": pool_health,
            "rejected_comp_id": item_comp_id,
        })

        lock_conn.commit()
        lock_conn.close()
        return {
            "updated": True,
            "regrade": {
                "triggered": False,
                "comps_remaining": comps_remaining,
                "reason": "below_minimum_threshold",
                "flagged_for_review": True,
            },
        }

    except Exception:
        lock_conn.rollback()
        lock_conn.close()
        raise


# ---------------------------------------------------------------------------
# Re-grade pricing logic
# ---------------------------------------------------------------------------


def _regrade_from_comps(item, active_comps: List[Dict[str, Any]]) -> dict:
    """Re-calculate grade + price from the remaining active comps.

    Writes the new values directly to the item row and returns a summary
    dict with keys: grade, sell_price, profit, margin, market_price,
    price_low, price_high, comp_count.
    """
    # Extract snapshot prices, filtering out None / zero
    prices = [
        c["snapshot_price"]
        for c in active_comps
        if c.get("snapshot_price") and c["snapshot_price"] > 0
    ]

    if not prices:
        # Shouldn't happen (we checked count >= 3), but be safe
        return {
            "grade": item.grade,
            "sell_price": item.exact_sell_price,
            "profit": item.exact_profit,
            "margin": item.exact_margin,
        }

    # ----- Core pricing math -----
    median_price = statistics.median(prices)
    price_low = min(prices)
    price_high = max(prices)
    count = len(prices)

    # Conservative quick-sale pricing: 90% of the low end
    sell_price = price_low * 0.90

    # Total cost (source_price + shipping)
    source_shipping = item.source_shipping if item.source_shipping else 0.0
    total_cost = item.source_price + source_shipping

    # Enforce minimum 35% margin
    min_sell_price = total_cost * (1.0 + MIN_MARGIN_FLOOR)  # total_cost * 1.35
    if sell_price < min_sell_price:
        sell_price = min_sell_price

    profit = sell_price - total_cost
    margin = profit / sell_price if sell_price > 0 else 0.0

    # ----- Price confidence -----
    spread = (price_high - price_low) / median_price if median_price > 0 else 1.0
    high_price_confidence = count >= 8 and spread <= 0.30

    # ----- Grade determination -----
    if count >= 8 and high_price_confidence and profit >= 150 and margin >= 0.40:
        grade = "A"
    elif count >= 4 and profit >= 150 and margin >= 0.30:
        grade = "B"
    elif count >= 4:
        grade = "C"
    else:
        grade = "D"

    # ----- Persist to DB -----
    now = datetime.utcnow().isoformat()
    market_price = median_price  # use median as market_price proxy

    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        """
        UPDATE items SET
            grade = ?,
            exact_sell_price = ?,
            exact_profit = ?,
            exact_margin = ?,
            our_price = ?,
            market_price = ?,
            margin_percent = ?,
            comp_count = ?,
            price_low = ?,
            price_high = ?,
            qualified_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            grade,
            round(sell_price, 2),
            round(profit, 2),
            round(margin, 4),
            round(sell_price, 2),
            round(market_price, 2),
            round(margin, 4),
            count,
            round(price_low, 2),
            round(price_high, 2),
            now,
            now,
            item.id,
        ),
    )
    conn.commit()
    conn.close()

    return {
        "grade": grade,
        "sell_price": round(sell_price, 2),
        "profit": round(profit, 2),
        "margin": round(margin, 4),
        "market_price": round(market_price, 2),
        "price_low": round(price_low, 2),
        "price_high": round(price_high, 2),
        "comp_count": count,
    }


# ---------------------------------------------------------------------------
# Pool health helper
# ---------------------------------------------------------------------------


def _calc_pool_health(comps: List[Dict[str, Any]]) -> float:
    """Average similarity_score of remaining comps.

    Returns 0.0 when there are no comps or no similarity scores.
    """
    scores = [
        c["similarity_score"]
        for c in comps
        if c.get("similarity_score") is not None
    ]
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 4)
