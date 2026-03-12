#!/usr/bin/env python3
"""Quick test of American market sources"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')

async def test_american_markets():
    """Test American market sources (Grailed, eBay, Poshmark)."""
    
    print("="*60)
    print("Testing American Market Sources")
    print("="*60)
    
    # Test Grailed
    print("\n1. Testing Grailed...")
    try:
        from scrapers.grailed import GrailedScraper
        async with GrailedScraper() as scraper:
            # Test sold data
            sold = await scraper.search_sold("chrome hearts ring", max_results=5)
            print(f"   ✅ Grailed sold: {len(sold)} items")
            if sold:
                avg_price = sum(s.price for s in sold) / len(sold)
                print(f"   Avg sold price: ${avg_price:.0f}")
            
            # Test live listings
            live = await scraper.search("chrome hearts ring", max_results=5)
            print(f"   ✅ Grailed live: {len(live)} items")
            if live:
                for item in live[:2]:
                    print(f"   - ${item.price:.0f}: {item.title[:40]}...")
    except Exception as e:
        print(f"   ❌ Grailed error: {e}")
    
    # Test eBay
    print("\n2. Testing eBay...")
    try:
        from scrapers.ebay import EbayScraper
        async with EbayScraper() as scraper:
            # Test live listings
            items = await scraper.search("chrome hearts ring", max_results=5)
            print(f"   ✅ eBay live: {len(items)} items")
            if items:
                for item in items[:2]:
                    print(f"   - ${item.price:.0f}: {item.title[:40]}...")
    except Exception as e:
        print(f"   ❌ eBay error: {e}")
    
    # Test Poshmark
    print("\n3. Testing Poshmark...")
    try:
        from scrapers.poshmark import PoshmarkScraper
        async with PoshmarkScraper() as scraper:
            items = await scraper.search("chrome hearts ring", max_results=5)
            print(f"   ✅ Poshmark: {len(items)} items")
            if items:
                for item in items[:2]:
                    print(f"   - ${item.price:.0f}: {item.title[:40]}...")
    except Exception as e:
        print(f"   ❌ Poshmark error: {e}")
    
    # Check for gaps
    print("\n4. Checking for arbitrage opportunities...")
    try:
        from gap_hunter import GapHunter
        gh = GapHunter()
        
        sold_data = await gh.get_sold_data("chrome hearts ring")
        if sold_data:
            print(f"   Sold data: {sold_data.count} comps, avg ${sold_data.avg_price:.0f}")
            
            # Get live listings from all sources
            from scrapers.grailed import GrailedScraper
            from scrapers.ebay import EbayScraper
            from scrapers.poshmark import PoshmarkScraper
            
            all_items = []
            async with GrailedScraper() as scraper:
                all_items.extend(await scraper.search("chrome hearts ring", max_results=10))
            async with EbayScraper() as scraper:
                all_items.extend(await scraper.search("chrome hearts ring", max_results=10))
            async with PoshmarkScraper() as scraper:
                all_items.extend(await scraper.search("chrome hearts ring", max_results=10))
            
            print(f"   Live items: {len(all_items)} total")
            
            gaps_found = 0
            for item in all_items:
                if item.price < sold_data.avg_price:
                    gap = (sold_data.avg_price - item.price) / sold_data.avg_price
                    profit = sold_data.avg_price - item.price
                    if gap >= 0.25 and profit >= 100:
                        gaps_found += 1
                        print(f"   🎯 GAP: ${item.price:.0f} → ${sold_data.avg_price:.0f} ({gap*100:.0f}% gap, ${profit:.0f} profit)")
                        print(f"      {item.title[:50]}...")
            
            if gaps_found == 0:
                print(f"   No gaps found (market is efficient)")
    except Exception as e:
        print(f"   ❌ Gap check error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("American market test complete")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_american_markets())
