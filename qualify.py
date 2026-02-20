#!/usr/bin/env python3
"""
Deal Qualifier — Pass 2 of the scraping pipeline.

Pass 1 (scrape) finds everything that looks profitable using cached comps.
Pass 2 (this) deep-scores ONLY the candidates that passed Pass 1.

For each candidate:
1. Smart comp matching — find exact product comps, not generic brand comps
2. Demand scoring — sold velocity + active supply
3. Sell-through estimation — how fast does this exact product move
4. Deal grading — A (guaranteed flip) through D (skip)

Only A and B grade deals get Discord alerts.

Usage:
    # Qualify all ungraded items
    python qualify.py

    # Qualify items from a specific brand
    python qualify.py --brand "helmut lang"

    # Qualify items with minimum margin
    python qualify.py --min-margin 0.30

    # Dry run (don't update DB, just show grades)
    python qualify.py --dry-run

    # Qualify and send alerts for A/B deals
    python qualify.py --alert
"""

import asyncio
import argparse
import os
import sys
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from db.sqlite_models import (
    init_db, get_items, get_item_by_id, Item,
    get_unqualified_items, update_item_qualification,
)
from scrapers.comp_matcher import find_best_comps, parse_title, CompResult
from scrapers.demand_scorer import score_demand, DemandResult
from scrapers.volume_tracker import get_volume_tracker, VolumeMetrics
from scrapers.seasons import detect_season
from alerts import AlertService, AlertItem


# --- Deal Grade Thresholds ---

# Grade A: Guaranteed flip — high volume, tight price band, proven demand
GRADE_A_MIN_COMPS = 8          # Need 8+ exact comps
GRADE_A_MIN_VELOCITY = 0.60    # Demand score >= 0.60
GRADE_A_MIN_MARGIN = 0.25      # At least 25% margin after repricing
GRADE_A_MIN_PROFIT = 40        # At least $40 profit
GRADE_A_MAX_BAND_WIDTH = 0.40  # Price band width < 40% of median (tight)

# Grade B: Likely flip — good data, decent demand
GRADE_B_MIN_COMPS = 5
GRADE_B_MIN_VELOCITY = 0.45
GRADE_B_MIN_MARGIN = 0.25
GRADE_B_MIN_PROFIT = 30
GRADE_B_MAX_BAND_WIDTH = 0.60

# Grade C: Speculative — some data, uncertain demand
GRADE_C_MIN_COMPS = 3
GRADE_C_MIN_VELOCITY = 0.30
GRADE_C_MIN_MARGIN = 0.20
GRADE_C_MIN_PROFIT = 20

# Below C = Grade D (skip)


@dataclass
class QualificationResult:
    """Full qualification data for an item."""
    item_id: int
    grade: str  # A, B, C, D
    grade_reasoning: str

    # Comp data
    comp_count: int = 0
    high_quality_comps: int = 0
    comp_median_price: float = 0.0
    comp_min_price: float = 0.0
    comp_max_price: float = 0.0
    price_band_width: float = 0.0  # (max-min)/median — tighter = better
    comp_confidence: str = "none"
    comp_query: str = ""

    # Demand data
    demand_score: float = 0.0
    demand_level: str = "unknown"  # hot, warm, cold, dead
    sold_count: int = 0
    active_count: int = 0
    supply_demand_ratio: float = 0.0
    avg_sold_price: float = 0.0
    avg_active_price: float = 0.0
    sell_through_rate: float = 0.0   # sold / (sold + active)
    est_days_to_sell: float = 999.0  # Estimated days based on velocity
    demand_reasoning: str = ""

    # Recalculated pricing based on exact comps
    exact_market_price: float = 0.0
    exact_sell_price: float = 0.0
    exact_profit: float = 0.0
    exact_margin: float = 0.0

    # Season
    season_name: Optional[str] = None
    season_multiplier: float = 1.0
    
    # Exact season/year from comps (Quick Win)
    exact_season: Optional[str] = None      # "FW", "SS", etc.
    exact_year: Optional[int] = None        # 2018, 2005, etc.
    season_confidence: str = "unknown"      # "confirmed", "inferred", "unknown"

    # Advanced volume metrics (new)
    weighted_volume: float = 0.0
    sales_per_day: float = 0.0
    volume_trend: str = "unknown"
    same_size_sold: int = 0
    price_trend_percent: float = 0.0

    qualified_at: str = ""


def calculate_deal_grade(
    source_price: float,
    comp_result: CompResult,
    demand: DemandResult,
    volume: VolumeMetrics,
    season_multiplier: float = 1.0,
) -> QualificationResult:
    """
    Grade a deal based on comp quality, demand, and margin.

    Returns a QualificationResult with the grade and all supporting data.
    """
    result = QualificationResult(
        item_id=0,
        grade="D",
        grade_reasoning="",
        qualified_at=datetime.utcnow().isoformat(),
    )

    # --- Fill comp data ---
    result.comp_count = comp_result.comps_count
    result.high_quality_comps = comp_result.high_quality_count
    result.comp_median_price = comp_result.weighted_price
    result.comp_confidence = comp_result.confidence
    result.comp_query = comp_result.query_used

    if comp_result.top_comps:
        prices = [c.price for c in comp_result.top_comps]
        result.comp_min_price = min(prices)
        result.comp_max_price = max(prices)
        if result.comp_median_price > 0:
            result.price_band_width = (result.comp_max_price - result.comp_min_price) / result.comp_median_price

    # --- Fill demand data ---
    result.demand_score = demand.score
    result.demand_level = demand.level
    result.sold_count = demand.sold_count
    result.active_count = demand.active_count
    result.supply_demand_ratio = demand.supply_demand_ratio
    result.avg_sold_price = demand.avg_sold_price
    result.avg_active_price = demand.avg_active_price
    result.sell_through_rate = demand.sell_through_rate
    result.est_days_to_sell = demand.est_days_to_sell
    result.demand_reasoning = demand.reasoning

    # --- Fill advanced volume data ---
    result.weighted_volume = volume.weighted_volume
    result.sales_per_day = volume.sales_per_day_7d
    result.volume_trend = volume.trend_direction
    result.same_size_sold = volume.same_size_sold
    result.price_trend_percent = volume.price_trend

    # --- Recalculate pricing from exact comps ---
    # Use the comp-matched price (already similarity-weighted)
    # Only apply season multiplier if comps are generic (low quality)
    if comp_result.weighted_price > 0:
        market = comp_result.weighted_price
        if comp_result.high_quality_count < 3 and season_multiplier > 1.0:
            # Comps are generic, apply season boost
            market *= season_multiplier
            result.season_multiplier = season_multiplier
        result.exact_market_price = market
        # Price 10% below market for quick sale
        result.exact_sell_price = market * 0.90
        result.exact_profit = result.exact_sell_price - source_price
        if result.exact_sell_price > 0:
            result.exact_margin = result.exact_profit / result.exact_sell_price
    else:
        # No comp data at all
        result.grade = "D"
        result.grade_reasoning = "No comparable sales data found"
        return result

    # --- Not profitable ---
    if result.exact_profit <= 0:
        result.grade = "D"
        result.grade_reasoning = f"Not profitable: buy ${source_price:.0f}, market ${result.exact_market_price:.0f}"
        return result

    # --- Dead demand = always D ---
    if demand.level == "dead":
        result.grade = "D"
        result.grade_reasoning = f"Dead demand ({demand.reasoning})"
        return result

    # --- Grade A check ---
    reasons = []
    
    # NEW: Use weighted volume for A-grade (must be hot item)
    is_high_volume = result.weighted_volume >= 40 or result.sales_per_day >= 1.5
    is_accelerating = result.volume_trend == "accelerating"
    
    if (
        result.high_quality_comps >= GRADE_A_MIN_COMPS
        and result.demand_score >= GRADE_A_MIN_VELOCITY
        and result.exact_margin >= GRADE_A_MIN_MARGIN
        and result.exact_profit >= GRADE_A_MIN_PROFIT
        and result.price_band_width <= GRADE_A_MAX_BAND_WIDTH
        and is_high_volume  # NEW: Must have proven volume
    ):
        result.grade = "A"
        reasons.append(f"{result.high_quality_comps} exact comps")
        reasons.append(f"demand {result.demand_score:.0%}")
        reasons.append(f"${result.exact_profit:.0f} profit ({result.exact_margin:.0%})")
        reasons.append(f"tight band ({result.price_band_width:.0%})")
        reasons.append(f"{result.sell_through_rate:.0%} sell-through")
        if result.weighted_volume > 0:
            reasons.append(f"🔥 volume score {result.weighted_volume:.0f}")
        if is_accelerating:
            reasons.append(f"📈 trending up")
        if result.est_days_to_sell < 999:
            reasons.append(f"~{result.est_days_to_sell:.0f}d to sell")
        result.grade_reasoning = "Guaranteed flip: " + " · ".join(reasons)
        return result

    # --- Grade B check ---
    has_good_volume = result.weighted_volume >= 20 or result.sales_per_day >= 0.5
    
    if (
        result.comp_count >= GRADE_B_MIN_COMPS
        and result.demand_score >= GRADE_B_MIN_VELOCITY
        and result.exact_margin >= GRADE_B_MIN_MARGIN
        and result.exact_profit >= GRADE_B_MIN_PROFIT
        and result.price_band_width <= GRADE_B_MAX_BAND_WIDTH
    ):
        result.grade = "B"
        reasons.append(f"{result.comp_count} comps ({result.high_quality_comps} exact)")
        reasons.append(f"demand {result.demand_score:.0%}")
        reasons.append(f"${result.exact_profit:.0f} profit ({result.exact_margin:.0%})")
        reasons.append(f"{result.sell_through_rate:.0%} sell-through")
        if result.weighted_volume > 0:
            reasons.append(f"volume score {result.weighted_volume:.0f}")
        if result.volume_trend != "steady":
            reasons.append(f"trend: {result.volume_trend}")
        if result.est_days_to_sell < 999:
            reasons.append(f"~{result.est_days_to_sell:.0f}d to sell")
        result.grade_reasoning = "Likely flip: " + " · ".join(reasons)
        return result

    # --- Grade C check ---
    if (
        result.comp_count >= GRADE_C_MIN_COMPS
        and result.demand_score >= GRADE_C_MIN_VELOCITY
        and result.exact_margin >= GRADE_C_MIN_MARGIN
        and result.exact_profit >= GRADE_C_MIN_PROFIT
    ):
        result.grade = "C"
        reasons.append(f"{result.comp_count} comps")
        reasons.append(f"demand {result.demand_score:.0%}")
        reasons.append(f"${result.exact_profit:.0f} profit")
        if result.price_band_width > GRADE_B_MAX_BAND_WIDTH:
            reasons.append(f"wide band ({result.price_band_width:.0%})")
        reasons.append(f"{result.sell_through_rate:.0%} sell-through")
        if result.weighted_volume > 0:
            reasons.append(f"volume: {result.weighted_volume:.0f}")
        if result.est_days_to_sell < 999:
            reasons.append(f"~{result.est_days_to_sell:.0f}d to sell")
        result.grade_reasoning = "Speculative: " + " · ".join(reasons)
        return result

    # --- Grade D ---
    result.grade = "D"
    fail_reasons = []
    if result.comp_count < GRADE_C_MIN_COMPS:
        fail_reasons.append(f"only {result.comp_count} comps")
    if result.demand_score < GRADE_C_MIN_VELOCITY:
        fail_reasons.append(f"low demand ({result.demand_score:.0%})")
    if result.exact_profit < GRADE_C_MIN_PROFIT:
        fail_reasons.append(f"thin profit (${result.exact_profit:.0f})")
    if result.exact_margin < GRADE_C_MIN_MARGIN:
        fail_reasons.append(f"low margin ({result.exact_margin:.0%})")
    if result.weighted_volume < 10 and result.sold_count > 0:
        fail_reasons.append(f"low volume ({result.weighted_volume:.0f})")
    result.grade_reasoning = "Skip: " + " · ".join(fail_reasons) if fail_reasons else "Does not meet minimum thresholds"
    return result


async def qualify_item(
    item: Item,
    timeout_comps: int = 30,
    timeout_demand: int = 20,
    timeout_volume: int = 25,
) -> QualificationResult:
    """
    Deep-qualify a single item with smart comps + demand scoring + advanced volume.
    """
    brand = item.brand or ""
    title = item.title or ""
    size = item.size

    # Smart comp matching
    try:
        comp_result = await asyncio.wait_for(
            find_best_comps(brand, title),
            timeout=timeout_comps,
        )
    except (asyncio.TimeoutError, Exception):
        comp_result = CompResult(
            weighted_price=0, simple_median=0, comps_count=0,
            high_quality_count=0, confidence="none", query_used="",
        )

    # Demand scoring
    try:
        demand = await asyncio.wait_for(
            score_demand(brand, title),
            timeout=timeout_demand,
        )
    except (asyncio.TimeoutError, Exception):
        demand = DemandResult(
            score=0, level="unknown", sold_count=0, active_count=0,
            supply_demand_ratio=0, avg_sold_price=0, avg_active_price=0,
            undercut_pct=0, query_used="", reasoning="Scoring failed/timed out",
        )

    # Advanced volume tracking
    try:
        tracker = get_volume_tracker()
        volume = await asyncio.wait_for(
            tracker.get_volume_metrics(brand, title, size),
            timeout=timeout_volume,
        )
    except (asyncio.TimeoutError, Exception) as e:
        print(f"Volume tracking failed for {brand} {title}: {e}")
        volume = VolumeMetrics(
            total_sold=0, grailed_sold=0, ebay_sold=0, poshmark_sold=0,
            weighted_volume=0.0, sales_per_day_7d=0.0, sales_per_day_30d=0.0,
            trend_direction="unknown", trend_score=0.0, same_size_sold=0,
            size_match_rate=0.0, avg_sold_price=0.0, avg_active_price=0.0,
            undercut_pct=0.0, sell_through_rate=0.0, est_days_to_sell=999.0,
            query_used="", reasoning="Volume tracking failed", summary="No data",
            confidence="low", data_freshness_hours=999.0,
        )

    # Season detection
    season_result = detect_season(brand, title)
    season_mult = season_result[0] if season_result else 1.0
    season_name = season_result[1] if season_result else None

    # Grade the deal
    result = calculate_deal_grade(
        source_price=item.source_price,
        comp_result=comp_result,
        demand=demand,
        volume=volume,
        season_multiplier=season_mult,
    )

    result.item_id = item.id
    result.season_name = season_name
    result.season_multiplier = season_mult
    
    # Add exact season/year from comp analysis (Quick Win)
    result.exact_season = comp_result.exact_season
    result.exact_year = comp_result.exact_year
    result.season_confidence = comp_result.season_confidence

    return result


async def enhance_with_reverse_image(item: Item, result: QualificationResult, timeout: int = 30) -> QualificationResult:
    """
    Enhance qualification with reverse image search data.
    
    This runs as an optional enhancement when:
    - Item has images
    - SERPAPI_KEY is configured
    - Product identification confidence is low from text alone
    """
    import os
    
    serpapi_key = os.getenv('SERPAPI_KEY')
    if not serpapi_key:
        return result  # Skip if no API key
    
    if not item.images or len(item.images) == 0:
        return result  # Skip if no images
    
    try:
        from scrapers.reverse_image import ProductIdentifier
        
        identifier = ProductIdentifier(serpapi_key=serpapi_key)
        
        product_info = await asyncio.wait_for(
            identifier.identify_product(
                image_url=item.images[0],
                title=item.title,
                brand=item.brand or ''
            ),
            timeout=timeout
        )
        
        # Update result with enhanced data if confidence is good
        if product_info['confidence'] >= 0.6:
            # If we didn't have season data from comps, use from image search
            if not result.exact_season and product_info.get('season'):
                result.exact_season = product_info['season']
                result.season_confidence = 'image_inferred'
            
            if not result.exact_year and product_info.get('year'):
                result.exact_year = product_info['year']
                if result.season_confidence == 'unknown':
                    result.season_confidence = 'image_inferred'
            
            # Add product identification to reasoning
            if product_info.get('product_name'):
                result.grade_reasoning += f" | ID: {product_info['product_name']}"
        
    except Exception as e:
        # Don't fail qualification if reverse image search fails
        pass
    
    return result


async def run_qualification(
    brand_filter: Optional[str] = None,
    min_margin: float = 0.0,
    min_profit: float = 0.0,
    dry_run: bool = False,
    send_alerts: bool = False,
    limit: int = 200,
    requalify: bool = False,
):
    """
    Run the qualification pass on scrape candidates.
    """
    print(f"\n⚡ Deal Qualifier starting at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    init_db()

    # Get candidates
    if requalify:
        items = get_items(status="active", brand=brand_filter, limit=limit)
        print(f"📋 Re-qualifying {len(items)} items (all active)")
    else:
        items = get_unqualified_items(
            brand=brand_filter,
            min_margin=min_margin,
            min_profit=min_profit,
            limit=limit,
        )
        print(f"📋 Qualifying {len(items)} ungraded candidates")

    if not items:
        print("   No candidates to qualify.")
        return

    if brand_filter:
        print(f"   Brand filter: {brand_filter}")
    print()

    alerts = AlertService() if send_alerts else None
    grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    alert_count = 0

    for i, item in enumerate(items):
        brand_str = (item.brand or "Unknown")[:20]
        title_str = item.title[:40]

        # Qualify
        result = await qualify_item(item)
        grade_counts[result.grade] = grade_counts.get(result.grade, 0) + 1

        # Print result
        grade_emoji = {"A": "🅰️", "B": "🅱️", "C": "🔵", "D": "⬜"}[result.grade]
        price_str = f"${item.source_price:.0f}→${result.exact_sell_price:.0f}" if result.exact_sell_price > 0 else f"${item.source_price:.0f}"
        demand_str = f"[{result.demand_level}]" if result.demand_level != "unknown" else ""

        days_str = f"~{result.est_days_to_sell:.0f}d" if result.est_days_to_sell < 999 else "n/a"

        if result.grade in ("A", "B"):
            print(f"  {grade_emoji} {result.grade} {brand_str}: {title_str}...")
            print(f"     {price_str} | ${result.exact_profit:.0f} profit ({result.exact_margin:.0%}) | {result.comp_count} comps {demand_str}")
            print(f"     Sell-through: {result.sell_through_rate:.0%} | Est. time: {days_str}")
            print(f"     {result.grade_reasoning}")
        elif result.grade == "C":
            print(f"  {grade_emoji} C {brand_str}: {title_str}... | {price_str} {demand_str} | {result.sell_through_rate:.0%} sell-through, {days_str}")
        # D grades are silent

        # Save to DB
        if not dry_run:
            update_item_qualification(item.id, result)

        # Send alert for A/B deals
        if send_alerts and alerts and result.grade in ("A", "B"):
            try:
                alert_item = AlertItem(
                    title=item.title,
                    brand=item.brand or "Unknown",
                    source=item.source,
                    source_url=item.source_url,
                    source_price=item.source_price,
                    market_price=result.exact_market_price,
                    recommended_price=result.exact_sell_price,
                    profit=result.exact_profit,
                    margin_percent=result.exact_margin,
                    image_url=item.images[0] if item.images else None,
                    size=item.size,
                    season_name=result.season_name,
                    season_multiplier=result.season_multiplier,
                    comps_count=result.comp_count,
                    demand_level=result.demand_level,
                    demand_score=result.demand_score,
                )
                sent = await alerts.send_item_alert(alert_item)
                if sent:
                    alert_count += 1
            except Exception:
                pass

        # Rate limit — don't hammer APIs
        await asyncio.sleep(0.5)

    # Summary
    print()
    print("=" * 60)
    print(f"📊 Qualification Results:")
    print(f"   🅰️  Grade A (guaranteed): {grade_counts['A']}")
    print(f"   🅱️  Grade B (likely):     {grade_counts['B']}")
    print(f"   🔵 Grade C (speculative): {grade_counts['C']}")
    print(f"   ⬜ Grade D (skip):        {grade_counts['D']}")
    print(f"   Total qualified: {sum(grade_counts.values())}")
    if send_alerts:
        print(f"   Discord alerts: {alert_count}")
    if dry_run:
        print(f"   ⚠️  Dry run — no DB updates")
    print()


def main():
    parser = argparse.ArgumentParser(description="Archive Arbitrage Deal Qualifier")
    parser.add_argument("--brand", help="Filter by brand")
    parser.add_argument("--min-margin", type=float, default=0.20, help="Minimum margin to qualify (default 0.20)")
    parser.add_argument("--min-profit", type=float, default=20, help="Minimum profit to qualify (default $20)")
    parser.add_argument("--limit", type=int, default=200, help="Max items to qualify per run")
    parser.add_argument("--dry-run", action="store_true", help="Don't update DB")
    parser.add_argument("--alert", action="store_true", help="Send Discord alerts for A/B deals")
    parser.add_argument("--requalify", action="store_true", help="Re-qualify all items (not just ungraded)")
    args = parser.parse_args()

    asyncio.run(run_qualification(
        brand_filter=args.brand,
        min_margin=args.min_margin,
        min_profit=args.min_profit,
        dry_run=args.dry_run,
        send_alerts=args.alert,
        limit=args.limit,
        requalify=args.requalify,
    ))


if __name__ == "__main__":
    main()
