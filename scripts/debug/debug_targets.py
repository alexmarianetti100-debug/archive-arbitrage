#!/usr/bin/env python3
"""Debug trend engine and targets."""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

print('🔍 DEBUGGING TREND ENGINE & TARGETS')
print('=' * 60)

# 1. Check direct import
print('\n1. Checking trend_engine import...')
try:
    from trend_engine import CORE_TARGETS, EXTENDED_TARGETS
    print(f'   ✅ CORE_TARGETS: {len(CORE_TARGETS)} targets')
    print(f'   ✅ EXTENDED_TARGETS: {len(EXTENDED_TARGETS)} targets')
    print(f'   First 3 CORE_TARGETS: {CORE_TARGETS[:3]}')
except Exception as e:
    print(f'   ❌ Error: {e}')
    import traceback
    traceback.print_exc()

# 2. Check TrendEngine class
print('\n2. Checking TrendEngine...')
try:
    from trend_engine import TrendEngine
    engine = TrendEngine()
    print(f'   ✅ TrendEngine initialized')
    
    # Check get_cycle_targets
    print('\n3. Testing get_cycle_targets...')
    async def test_cycle_targets():
        targets = await engine.get_cycle_targets(n=20)
        print(f'   ✅ Got {len(targets)} cycle targets')
        if targets:
            print(f'   First 3: {targets[:3]}')
        return targets
    
    targets = asyncio.run(test_cycle_targets())
    
except Exception as e:
    print(f'   ❌ Error: {e}')
    import traceback
    traceback.print_exc()

# 3. Check gap_hunter TARGETS
print('\n4. Checking gap_hunter TARGETS...')
try:
    import gap_hunter
    # Check if TARGETS is defined in gap_hunter module
    if hasattr(gap_hunter, 'TARGETS'):
        print(f'   gap_hunter.TARGETS: {len(gap_hunter.TARGETS)} targets')
    else:
        print('   ⚠️  gap_hunter.TARGETS not defined (uses dynamic from trend_engine)')
except Exception as e:
    print(f'   ❌ Error: {e}')

print('\n' + '=' * 60)
print('Debug complete')
