#!/usr/bin/env python3
"""Test regular (American) deal flow"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')

async def test_regular_deals():
    """Test that regular American deals are being found and processed."""
    
    print("="*60)
    print("Testing Regular (American) Deal Flow")
    print("="*60)
    
    # Import gap_hunter
    print("\n1. Initializing GapHunter...")
    from gap_hunter import GapHunter
    
    gh = GapHunter()
    
    # Test a single query
    test_query = 'chrome hearts necklace'
    print(f"\n2. Testing query: '{test_query}'")
    
    # Get sold data
    print("   Fetching sold data...")
    sold_data = await gh.get_sold_data(test_query)
    
    if sold_data:
        print(f"   ✅ Sold data found:")
        print(f"      Count: {sold_data.count}")
        print(f"      Avg: ${sold_data.avg_price:.0f}")
        print(f"      Median: ${sold_data.median_price:.0f}")
    else:
        print(f"   ❌ No sold data found")
        print("\n⚠️ Cannot test without sold data")
        return False
    
    # Check if we can find live listings
    print("\n3. Searching for live listings...")
    try:
        from scrapers.grailed import GrailedScraper
        async with GrailedScraper() as scraper:
            listings = await scraper.search(test_query, max_results=10)
            print(f"   Found {len(listings)} live listings on Grailed")
            
            if listings:
                for i, item in enumerate(listings[:3]):
                    print(f"   {i+1}. {item.title[:50]}... - ${item.price}")
            
            # Check for gaps
            if sold_data and listings:
                print("\n4. Checking for gaps...")
                gaps_found = 0
                for item in listings:
                    gap_percent = (sold_data.avg_price - item.price) / sold_data.avg_price
                    profit = sold_data.avg_price - item.price
                    if gap_percent >= 0.30 and profit >= 75:  # 30% gap, $75 profit
                        gaps_found += 1
                        print(f"   🎯 GAP: {item.title[:40]}...")
                        print(f"      Listed: ${item.price} | Market: ${sold_data.avg_price:.0f}")
                        print(f"      Gap: {gap_percent*100:.0f}% | Profit: ${profit:.0f}")
                
                if gaps_found == 0:
                    print(f"   No gaps found (checked {len(listings)} items)")
    except Exception as e:
        print(f"   ❌ Error searching: {e}")
        import traceback
        print(traceback.format_exc())
    
    print("\n" + "="*60)
    print("Regular deal flow test complete")
    print("="*60)
    return True

if __name__ == "__main__":
    asyncio.run(test_regular_deals())
