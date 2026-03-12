#!/usr/bin/env python3
"""Debug gap_hunter cycle execution."""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

print('🔍 DEBUGGING GAP HUNTER CYCLE EXECUTION')
print('=' * 60)

import gap_hunter

async def debug_cycle():
    print('\n1. Creating GapHunter instance...')
    hunter = gap_hunter.GapHunter()
    print('   ✅ GapHunter created')
    
    print('\n2. Getting targets...')
    from trend_engine import CORE_TARGETS
    from gap_hunter import _get_trend_engine
    
    trend_engine = _get_trend_engine()
    targets = CORE_TARGETS  # fallback
    
    if trend_engine:
        try:
            dynamic = await trend_engine.get_cycle_targets(n=5)  # Just 5 for testing
            if dynamic:
                targets = dynamic
                print(f'   ✅ Got {len(targets)} dynamic targets')
        except Exception as e:
            print(f'   ⚠️  Using fallback: {e}')
    
    print(f'   Targets: {targets[:3]}...')
    
    print('\n3. Testing get_sold_data for first target...')
    target = targets[0]
    print(f'   Target: {target}')
    
    try:
        sold = await hunter.get_sold_data(target)
        if sold:
            print(f'   ✅ Sold data: avg=${sold.avg_price:.0f}, count={sold.count}')
        else:
            print(f'   ❌ No sold data returned')
            print('   This is likely why no items are found!')
    except Exception as e:
        print(f'   ❌ Error: {e}')
        import traceback
        traceback.print_exc()
    
    print('\n4. Testing find_gaps...')
    if sold:
        try:
            gaps = await hunter.find_gaps(target, sold)
            print(f'   ✅ Found {len(gaps)} gaps')
            if gaps:
                print(f'   First gap: ${gaps[0].item.price:.0f} → ${gaps[0].sold_avg:.0f}')
        except Exception as e:
            print(f'   ❌ Error: {e}')
            import traceback
            traceback.print_exc()
    else:
        print('   ⚠️  Skipping (no sold data)')
    
    print('\n5. Testing full process_deal...')
    if gaps:
        try:
            result = await hunter.process_deal(gaps[0])
            print(f'   ✅ process_deal returned: {result}')
        except Exception as e:
            print(f'   ❌ Error: {e}')
            import traceback
            traceback.print_exc()

asyncio.run(debug_cycle())

print('\n' + '=' * 60)
print('Debug complete')
