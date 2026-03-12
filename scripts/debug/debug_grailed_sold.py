#!/usr/bin/env python3
"""
Debug Grailed sold search directly
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

print("🔍 DEBUGGING GRAILED SOLD SEARCH")
print("=" * 70)

async def test_grailed_sold():
    from scrapers.grailed import GrailedScraper
    from datetime import datetime, timedelta, timezone
    
    query = "rolex datejust"
    
    print(f"\nQuery: {query}\n")
    
    async with GrailedScraper() as scraper:
        print("Fetching sold items from Grailed...")
        sold = await scraper.search_sold(query, max_results=30)
        
        print(f"\n📊 Results:")
        print(f"  Total items returned: {len(sold) if sold else 0}")
        
        if not sold:
            print("  ❌ No items returned from Grailed")
            return
        
        # Check dates
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=180)
        
        fresh_count = 0
        stale_count = 0
        no_date_count = 0
        
        print(f"\n  Checking {len(sold)} items:")
        for i, item in enumerate(sold[:10], 1):  # Check first 10
            raw = item.raw_data or {}
            created_str = raw.get("created_at") or raw.get("sold_at")
            
            if created_str:
                try:
                    comp_date = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    age_days = (now - comp_date).days
                    is_fresh = comp_date >= cutoff
                    
                    if is_fresh:
                        fresh_count += 1
                        status = "✅ FRESH"
                    else:
                        stale_count += 1
                        status = "❌ STALE"
                    
                    print(f"    {i}. ${item.price:.0f} - {status} ({age_days} days old)")
                    
                except Exception as e:
                    print(f"    {i}. ${item.price:.0f} - ⚠️ Date parse error: {e}")
                    no_date_count += 1
            else:
                no_date_count += 1
                print(f"    {i}. ${item.price:.0f} - ⚠️ No date")
        
        print(f"\n  Summary:")
        print(f"    Fresh (≤180 days): {fresh_count}")
        print(f"    Stale (>180 days): {stale_count}")
        print(f"    No date: {no_date_count}")
        print(f"    Need 12 fresh for threshold")

asyncio.run(test_grailed_sold())

print("\n" + "=" * 70)
print("Debug complete")
