#!/usr/bin/env python3
"""Test full gap hunter cycle with fix."""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

print('🔍 TESTING FULL GAP HUNTER CYCLE')
print('=' * 60)

async def test_cycle():
    import gap_hunter
    
    print('\n1. Creating GapHunter...')
    hunter = gap_hunter.GapHunter()
    print('   ✅ Created')
    
    print('\n2. Running single cycle with 3 targets...')
    
    # Use a mix of archive and non-archive
    test_targets = [
        'chrome hearts cross pendant',
        'nike air max',
        'rick owens dunks',
    ]
    
    total_gaps = 0
    
    for target in test_targets:
        print(f'\n   Target: {target}')
        
        # Get sold data
        sold = await hunter.get_sold_data(target)
        if not sold:
            print(f'   ❌ No sold data')
            continue
        
        print(f'   ✅ Sold: avg=${sold.avg_price:.0f}, count={sold.count}')
        
        # Find gaps
        gaps = await hunter.find_gaps(target, sold)
        print(f'   ✅ Found {len(gaps)} gaps')
        
        if gaps:
            total_gaps += len(gaps)
            for gap in gaps[:2]:  # Show first 2
                print(f'      💰 ${gap.item.price:.0f} → ${gap.sold_avg:.0f} ({gap.gap_percent*100:.0f}% gap)')
                print(f'         {gap.item.title[:50]}...')
    
    print(f'\n3. Summary:')
    print(f'   Total gaps found: {total_gaps}')
    
    if total_gaps > 0:
        print(f'   ✅ SUCCESS! Gaps are being found.')
    else:
        print(f'   ⚠️  No gaps found (may need to check active listings)')

asyncio.run(test_cycle())

print('\n' + '=' * 60)
print('Test complete')
