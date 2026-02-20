"""
Re-qualify all items using exact product matching.

This script runs Phase 2A/2B qualification on all unqualified items
or re-qualifies existing items with the new exact product system.

Usage:
    python requalify_exact.py              # Qualify items without product matches
    python requalify_exact.py --all        # Re-qualify all items
    python requalify_exact.py --grade A    # Show A-grade items
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from db.sqlite_models import (
    init_db, get_unqualified_items, get_item_by_id,
    update_item_qualification, get_qualified_items,
    get_product_by_fingerprint, Item
)
from api.services.exact_qualification import qualify_item_exact, ExactProductQualification


async def requalify_item(item: Item, dry_run: bool = False) -> dict:
    """Re-qualify a single item with exact product matching."""
    
    try:
        result = await qualify_item_exact(item)
        
        if not dry_run and result.product_id:
            # Create a qualification object for the database
            class QualProxy:
                pass
            
            qual = QualProxy()
            qual.grade = result.grade
            qual.grade_reasoning = result.grade_reasoning
            qual.comp_count = result.exact_comp_count
            qual.high_quality_comps = result.exact_comp_count
            qual.comp_median_price = result.price_median
            qual.price_band_width = result.price_band_high - result.price_band_low
            qual.demand_score = 0.5 if result.is_high_velocity else 0.3
            qual.demand_level = "hot" if result.is_high_velocity else "warm"
            qual.sold_count = result.sales_30d
            qual.active_count = 0
            qual.exact_market_price = result.market_price
            qual.exact_sell_price = result.sell_price
            qual.exact_profit = result.profit
            qual.exact_margin = result.margin_percent
            qual.demand_reasoning = f"Velocity: {result.sales_30d}/30d, trend: {result.velocity_trend}"
            qual.sell_through_rate = 0.5 if result.is_high_velocity else 0.2
            qual.est_days_to_sell = 7 if result.is_high_velocity else 21
            qual.qualified_at = result.qualified_at
            qual.weighted_volume = float(result.sales_30d * 10)
            qual.sales_per_day = result.sales_30d / 30.0
            qual.volume_trend = result.velocity_trend
            qual.same_size_sold = 0
            qual.price_trend_percent = 0.0
            qual.exact_season = None
            qual.exact_year = None
            qual.season_confidence = None
            
            update_item_qualification(item.id, qual)
        
        return {
            "id": item.id,
            "title": item.title[:60],
            "old_grade": item.deal_grade,
            "new_grade": result.grade,
            "product": result.fingerprint.canonical_name[:50] if result.fingerprint else None,
            "exact_comps": result.exact_comp_count,
            "velocity": result.sales_30d,
            "profit": result.profit,
            "risk": result.risk_level,
        }
        
    except Exception as e:
        return {
            "id": item.id,
            "title": item.title[:60],
            "error": str(e),
        }


async def requalify_all(dry_run: bool = False, only_unmatched: bool = True, limit: int = None):
    """Re-qualify all items."""
    
    init_db()
    
    # Get items to process
    if only_unmatched:
        # Only items without product matches
        import sqlite3
        conn = sqlite3.connect('data/archive.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM items 
            WHERE status = 'active' AND (product_id IS NULL OR product_match_confidence IS NULL)
            ORDER BY margin_percent DESC
        ''')
        from db.sqlite_models import _row_to_item
        items = [_row_to_item(row) for row in cursor.fetchall()]
        conn.close()
        print(f"Found {len(items)} items without product matches")
    else:
        items = get_unqualified_items(limit=limit or 500)
    
    if limit:
        items = items[:limit]
    
    print(f"\n🔄 Re-qualifying {len(items)} items with exact product matching...")
    print("=" * 80)
    
    results = []
    upgraded = {"A": 0, "B": 0}
    
    for i, item in enumerate(items):
        if i % 50 == 0 and i > 0:
            print(f"  ...processed {i}/{len(items)}")
        
        result = await requalify_item(item, dry_run=dry_run)
        results.append(result)
        
        if result.get("new_grade") in ("A", "B"):
            upgraded[result["new_grade"]] += 1
            print(f"\n  ⭐ {result['new_grade']}: {result['title'][:55]}")
            if result.get("product"):
                print(f"     Product: {result['product']}")
            print(f"     Comps: {result.get('exact_comps', 0)} | Velocity: {result.get('velocity', 0)}/30d | Profit: ${result.get('profit', 0):.0f}")
    
    print("\n" + "=" * 80)
    print(f"✅ Done! Upgraded to A: {upgraded['A']}, B: {upgraded['B']}")
    
    return results


def show_by_grade(grade: str, limit: int = 20):
    """Show items by grade."""
    items = get_qualified_items(grade=grade, limit=limit)
    
    print(f"\n📦 {grade}-Grade Items:")
    print("=" * 80)
    
    for item in items:
        print(f"\n{item['title'][:70]}")
        print(f"  Grade: {item['deal_grade']} | Profit: ${item['exact_profit']:.0f} | Margin: {item['exact_margin']*100:.0f}%")
        if item.get('demand_reasoning'):
            print(f"  {item['demand_reasoning']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-qualify items with exact product matching")
    parser.add_argument("--all", action="store_true", help="Re-qualify all items (not just unmatched)")
    parser.add_argument("--dry-run", action="store_true", help="Don't save changes")
    parser.add_argument("--limit", type=int, help="Limit items to process")
    parser.add_argument("--grade", type=str, choices=["A", "B", "C", "D"], help="Show items by grade")
    
    args = parser.parse_args()
    
    if args.grade:
        show_by_grade(args.grade)
    else:
        asyncio.run(requalify_all(
            dry_run=args.dry_run,
            only_unmatched=not args.all,
            limit=args.limit
        ))
