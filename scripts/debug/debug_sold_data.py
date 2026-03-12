#!/usr/bin/env python3
"""
Debug sold data retrieval to see why most queries fail
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

print("🔍 DEBUGGING SOLD DATA RETRIEVAL")
print("=" * 70)

async def test_sold_data():
    from gap_hunter import GapHunter, _get_comp_thresholds
    from trend_engine import CORE_TARGETS
    
    hunter = GapHunter()
    
    # Test a few targets
    test_targets = [
        'rolex datejust',
        'chanel classic flap', 
        'chrome hearts ring',
        'prada america\'s cup sneakers',
        'nike air max',
    ]
    
    print(f"\nTesting {len(test_targets)} targets:\n")
    
    for query in test_targets:
        print(f"Query: {query}")
        
        # Get thresholds
        thresholds = _get_comp_thresholds(query)
        print(f"  Thresholds: min_comps={thresholds['min_comps']}, max_age={thresholds['max_age_days']}d")
        
        # Try to get sold data
        try:
            sold = await hunter.get_sold_data(query)
            
            if sold:
                print(f"  ✅ SUCCESS: {sold.count} comps, avg=${sold.avg_price:.0f}")
            else:
                print(f"  ❌ FAILED: No sold data returned")
                
        except Exception as e:
            print(f"  ❌ ERROR: {type(e).__name__}: {str(e)[:60]}")
        
        print()
        await asyncio.sleep(1)  # Rate limiting

asyncio.run(test_sold_data())

print("=" * 70)
print("Debug complete")
