#!/usr/bin/env python3
"""Debug gap hunter cycles."""

import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

print('🔍 DEBUGGING GAP HUNTER CYCLES')
print('=' * 60)

# Check if we can import gap_hunter
print('\n1. Checking gap_hunter import...')
try:
    import gap_hunter
    print('   ✅ gap_hunter imported successfully')
except Exception as e:
    print(f'   ❌ Failed to import gap_hunter: {e}')
    sys.exit(1)

# Check targets
print('\n2. Checking targets...')
try:
    targets = gap_hunter.TARGETS if hasattr(gap_hunter, 'TARGETS') else []
    print(f'   Found {len(targets)} targets')
    if targets:
        print(f'   First target: {targets[0]}')
except Exception as e:
    print(f'   ❌ Error: {e}')

# Check ALWAYS_RUN
print('\n3. Checking ALWAYS_RUN...')
try:
    always_run = gap_hunter.ALWAYS_RUN if hasattr(gap_hunter, 'ALWAYS_RUN') else []
    print(f'   Found {len(always_run)} ALWAYS_RUN targets')
    if always_run:
        print(f'   Targets: {always_run}')
except Exception as e:
    print(f'   ❌ Error: {e}')

# Test a single scraper
print('\n4. Testing individual scrapers...')

async def test_scrapers():
    from scrapers.ebay import EbayScraper
    from scrapers.poshmark import PoshmarkScraper
    from scrapers.grailed import GrailedScraper
    
    scrapers = [
        ('eBay', EbayScraper),
        ('Poshmark', PoshmarkScraper),
        ('Grailed', GrailedScraper),
    ]
    
    for name, ScraperClass in scrapers:
        try:
            print(f'\n   Testing {name}...')
            async with ScraperClass() as scraper:
                items = await scraper.search('nike', max_results=3)
                print(f'   ✅ {name}: Found {len(items)} items')
                if items:
                    print(f'      First item: {items[0].title[:50]}...')
        except Exception as e:
            print(f'   ❌ {name}: {type(e).__name__}: {str(e)[:60]}')

asyncio.run(test_scrapers())

# Check gap hunter cycle
print('\n5. Testing gap_hunter run_cycle...')
async def test_cycle():
    try:
        # Mock a single cycle
        print('   Attempting to run one cycle...')
        
        # Check if there's a run_once or similar function
        if hasattr(gap_hunter, 'run_once'):
            await gap_hunter.run_once()
            print('   ✅ Cycle completed')
        elif hasattr(gap_hunter, 'run_cycle'):
            await gap_hunter.run_cycle()
            print('   ✅ Cycle completed')
        else:
            print('   ⚠️  No run_once or run_cycle function found')
            
    except Exception as e:
        print(f'   ❌ Cycle failed: {type(e).__name__}: {str(e)[:100]}')
        import traceback
        traceback.print_exc()

asyncio.run(test_cycle())

print('\n' + '=' * 60)
print('Debug complete')
