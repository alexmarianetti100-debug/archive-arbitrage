#!/usr/bin/env python3
"""Quick test of Japan integration fixes"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')

async def test():
    from core.japan_integration import JapanArbitrageMonitor
    
    print("Testing Japan integration with direct Yahoo scraper...")
    monitor = JapanArbitrageMonitor()
    
    # Test just one target
    target = monitor.SEARCH_TARGETS[0]  # First target
    print(f"\nSearching: {target['en']}")
    
    items = await monitor.search_yahoo_direct(target)
    print(f"Found {len(items)} items via direct Yahoo")
    
    if items:
        for item in items[:3]:
            print(f"  - {item['title_jp'][:40]}... ¥{item['price_jpy']:,}")
            
        # Test analysis
        print("\nAnalyzing first item...")
        opp = await monitor.analyze_opportunity(items[0])
        if opp:
            print(f"  ✅ {opp.recommendation}: ${opp.net_profit:.0f} profit ({opp.margin_percent:.1f}%)")
        else:
            print("  ❌ No opportunity (below thresholds)")
    
    print("\n✅ Test complete!")

if __name__ == "__main__":
    asyncio.run(test())
