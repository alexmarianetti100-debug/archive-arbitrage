#!/usr/bin/env python3
"""
Detailed debug of get_sold_data
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

print("🔍 DETAILED DEBUG OF GET_SOLD_DATA")
print("=" * 70)

async def test_detailed():
    from gap_hunter import GapHunter, _get_comp_thresholds
    from scrapers.grailed import GrailedScraper
    from scrapers.multi_platform import EbaySoldScraper
    from datetime import datetime, timedelta, timezone
    
    query = "rolex datejust"
    
    print(f"\nQuery: {query}\n")
    
    thresholds = _get_comp_thresholds(query)
    min_comps = thresholds['min_comps']
    max_age_days = thresholds['max_age_days']
    
    print(f"Thresholds: min_comps={min_comps}, max_age_days={max_age_days}")
    
    # Step 1: Fetch from Grailed
    print("\n1. Fetching from Grailed...")
    async with GrailedScraper() as scraper:
        sold = await scraper.search_sold(query, max_results=30)
        print(f"   Grailed returned: {len(sold) if sold else 0} items")
    
    if not sold:
        print("   ❌ No items from Grailed - ABORTING")
        return
    
    # Step 2: Filter by date
    print("\n2. Filtering by date...")
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)
    
    fresh_sold = []
    for s in sold:
        created_str = (s.raw_data or {}).get("created_at") or (s.raw_data or {}).get("sold_at")
        if created_str:
            try:
                comp_date = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                if comp_date >= cutoff:
                    fresh_sold.append(s)
            except:
                fresh_sold.append(s)  # Include if can't parse
        else:
            fresh_sold.append(s)  # Include if no date
    
    print(f"   Fresh items: {len(fresh_sold)} (cutoff: {max_age_days} days)")
    
    if len(fresh_sold) >= min_comps:
        print(f"   ✅ ENOUGH COMPS! Using {len(fresh_sold)} fresh comps")
        return
    
    # Step 3: Try eBay fallback
    print(f"\n3. Trying eBay fallback (need {min_comps}, have {len(fresh_sold)})...")
    try:
        async with EbaySoldScraper() as ebay_scraper:
            ebay_sold = await ebay_scraper.search_sold(query, max_results=50)
            print(f"   eBay returned: {len(ebay_sold) if ebay_sold else 0} items")
        
        if ebay_sold:
            ebay_fresh = []
            for s in ebay_sold:
                created_str = (s.raw_data or {}).get("created_at") or (s.raw_data or {}).get("sold_at")
                if created_str:
                    try:
                        comp_date = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        if comp_date >= cutoff:
                            ebay_fresh.append(s)
                    except:
                        ebay_fresh.append(s)
                else:
                    ebay_fresh.append(s)
            
            print(f"   eBay fresh items: {len(ebay_fresh)}")
            
            combined = fresh_sold + ebay_fresh
            print(f"   Combined total: {len(combined)}")
            
            if len(combined) >= min_comps:
                print(f"   ✅ ENOUGH WITH EBAY! Using {len(combined)} comps")
                return
            else:
                print(f"   ❌ Still not enough ({len(combined)} < {min_comps})")
    
    except Exception as e:
        print(f"   ❌ eBay failed: {e}")
    
    print("\n❌ FINAL RESULT: No sold data (insufficient comps)")

asyncio.run(test_detailed())

print("\n" + "=" * 70)
print("Debug complete")
