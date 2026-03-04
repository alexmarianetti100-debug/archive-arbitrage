#!/usr/bin/env python3
"""
Batch update all items with advanced volume metrics.

Usage:
    python update_volume_metrics.py           # Update all items
    python update_volume_metrics.py --limit 100   # Update first 100 items
    python update_volume_metrics.py --brand "helmut lang"  # Update specific brand
    python update_volume_metrics.py --dry-run  # Preview without saving
"""

import asyncio
import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from db.sqlite_models import init_db, get_items, update_item_qualification
from scrapers.volume_tracker import get_volume_tracker, VolumeMetrics
from scrapers.comp_matcher import find_best_comps, CompResult
from scrapers.demand_scorer import score_demand, DemandResult


async def update_single_item(item, tracker, dry_run=False):
    """Update a single item with advanced volume metrics."""
    brand = item.brand or ""
    title = item.title or ""
    size = item.size
    
    # Get advanced volume metrics
    try:
        volume = await asyncio.wait_for(
            tracker.get_volume_metrics(brand, title, size),
            timeout=30,
        )
    except Exception as e:
        print(f"  ⚠️ Volume tracking failed: {e}")
        volume = VolumeMetrics(
            total_sold=item.sold_count or 0,
            grailed_sold=item.sold_count or 0,
            ebay_sold=0,
            poshmark_sold=0,
            weighted_volume=0.0,
            sales_per_day_7d=0.0,
            sales_per_day_30d=0.0,
            trend_direction="unknown",
            trend_score=0.0,
            same_size_sold=0,
            size_match_rate=0.0,
            avg_price_7d=0.0,
            avg_price_30d=0.0,
            price_trend=0.0,
            confidence="low",
            data_freshness_hours=999.0,
            summary="No data",
        )
    
    # Create a simple qualification result with just volume data
    class VolumeUpdate:
        pass
    
    update = VolumeUpdate()
    update.grade = item.deal_grade or "D"
    update.grade_reasoning = item.deal_grade_reasoning or ""
    update.comp_count = item.comp_count or 0
    update.high_quality_comps = item.high_quality_comps or 0
    update.comp_median_price = item.comp_median_price or 0.0
    update.price_band_width = item.price_band_width or 0.0
    update.demand_score = item.demand_score or 0.0
    update.demand_level = item.demand_level or "unknown"
    update.sold_count = item.sold_count or 0
    update.active_count = item.active_count or 0
    update.exact_market_price = item.exact_market_price or 0.0
    update.exact_sell_price = item.exact_sell_price or 0.0
    update.exact_profit = item.exact_profit or 0.0
    update.exact_margin = item.exact_margin or 0.0
    update.demand_reasoning = item.demand_reasoning or ""
    update.sell_through_rate = item.sell_through_rate or 0.0
    update.est_days_to_sell = item.est_days_to_sell or 999.0
    update.qualified_at = item.qualified_at or datetime.utcnow().isoformat()
    
    # New volume fields
    update.weighted_volume = volume.weighted_volume
    update.sales_per_day = volume.sales_per_day_7d
    update.volume_trend = volume.trend_direction
    update.same_size_sold = volume.same_size_sold
    update.price_trend_percent = volume.price_trend
    
    if not dry_run:
        update_item_qualification(item.id, update)
    
    return {
        "id": item.id,
        "brand": brand[:20],
        "title": title[:40],
        "weighted_volume": volume.weighted_volume,
        "sales_per_day": volume.sales_per_day_7d,
        "trend": volume.trend_direction,
        "same_size": volume.same_size_sold,
        "price_trend": volume.price_trend,
        "confidence": volume.confidence,
    }


async def main():
    parser = argparse.ArgumentParser(description="Update all items with advanced volume metrics")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of items to update (0 = all)")
    parser.add_argument("--brand", type=str, help="Filter by brand")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--batch-size", type=int, default=10, help="Items to process in parallel")
    args = parser.parse_args()
    
    init_db()
    tracker = get_volume_tracker()
    
    print(f"\n🔥 Volume Metrics Updater")
    print(f"{'='*60}")
    print(f"Dry run: {args.dry_run}")
    print(f"Batch size: {args.batch_size}")
    
    # Get items
    items = get_items(
        status="active",
        brand=args.brand,
        sort="grade_asc",
        limit=args.limit if args.limit > 0 else 10000
    )
    
    print(f"Items to update: {len(items)}")
    if args.brand:
        print(f"Brand filter: {args.brand}")
    print()
    
    if not items:
        print("No items found.")
        return
    
    # Process in batches
    updated = 0
    errors = 0
    
    for i in range(0, len(items), args.batch_size):
        batch = items[i:i + args.batch_size]
        print(f"Processing batch {i//args.batch_size + 1}/{(len(items)-1)//args.batch_size + 1} ({i+1}-{min(i+len(batch), len(items))})...")
        
        tasks = [update_single_item(item, tracker, args.dry_run) for item in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                errors += 1
                print(f"  ❌ Error: {result}")
                continue
            
            updated += 1
            trend_emoji = {"accelerating": "📈", "steady": "➡️", "decelerating": "📉", "unknown": "❓"}
            emoji = trend_emoji.get(result["trend"], "❓")
            
            print(f"  {emoji} {result['brand']}: {result['title']}...")
            print(f"     Volume: {result['weighted_volume']:.0f} | {result['sales_per_day']:.1f}/day | {result['trend']}")
            print(f"     Same size: {result['same_size']} | Price trend: {result['price_trend']:+.1f}% | {result['confidence']}")
        
        print()
    
    print(f"{'='*60}")
    print(f"✅ Updated: {updated}")
    if errors > 0:
        print(f"❌ Errors: {errors}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
