#!/usr/bin/env python3
"""Test process_deal with a real Japan deal from the opportunities file"""
import asyncio
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger("test_process_deal")

async def test_process_deal():
    """Test process_deal with a real Japan deal."""
    
    print("="*60)
    print("Testing process_deal with Real Japan Deal")
    print("="*60)
    
    # Load a real Japan deal from the opportunities file
    deal_data = None
    try:
        with open('data/japan_opportunities.jsonl', 'r') as f:
            lines = f.readlines()
            for line in reversed(lines):  # Get most recent
                data = json.loads(line)
                if data.get('recommendation') in ['STRONG_BUY', 'BUY']:
                    deal_data = data
                    break
    except Exception as e:
        print(f"❌ Could not load Japan deal: {e}")
        return False
    
    if not deal_data:
        print("❌ No STRONG_BUY or BUY deals found in japan_opportunities.jsonl")
        return False
    
    print(f"\n✅ Loaded Japan deal:")
    print(f"   Brand: {deal_data['brand']}")
    print(f"   Title: {deal_data['title'][:40]}...")
    print(f"   Profit: ${deal_data['net_profit']:.0f}")
    print(f"   Margin: {deal_data['margin_percent']:.1f}%")
    print(f"   Recommendation: {deal_data['recommendation']}")
    
    # Create mock classes
    class MockItem:
        def __init__(self, data):
            self.title = f"{data['brand']} {data['title']}"
            self.price = data['total_landed_cost']
            self.source = 'japan_buyee'
            self.url = data['auction_url']
            self.images = [data['image_url']] if data['image_url'] else []
            self._japan_data = data
    
    class MockDeal:
        def __init__(self, data, item):
            self.item = item
            self.sold_avg = data['us_market_price']
            self.gap_percent = data['margin_percent'] / 100
            self.profit_estimate = data['net_profit']
            self.sold_count = 10
    
    # Import gap_hunter
    print("\n2. Importing GapHunter...")
    from gap_hunter import GapHunter
    
    gh = GapHunter()
    
    item = MockItem(deal_data)
    mock_deal = MockDeal(deal_data, item)
    
    print("\n3. Calling process_deal...")
    try:
        result = await gh.process_deal(mock_deal, is_japan_deal=True)
        print(f"\n✅ process_deal returned: {result}")
        return result
    except Exception as e:
        print(f"\n❌ process_deal failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = asyncio.run(test_process_deal())
    print("\n" + "="*60)
    if success:
        print("✅ SUCCESS - Japan deal alerts are working!")
    else:
        print("❌ FAILED - Check errors above")
    print("="*60)
    exit(0 if success else 1)
