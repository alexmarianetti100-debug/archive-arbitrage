#!/usr/bin/env python3
"""Test the fix for archive item thresholds."""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

print('🔍 TESTING ARCHIVE ITEM THRESHOLD FIX')
print('=' * 60)

# Test the helper functions
from gap_hunter import _is_archive_query, _get_comp_thresholds

print('\n1. Testing _is_archive_query...')
test_queries = [
    ('chrome hearts cross pendant', True),
    ('nike air max', False),
    ('rick owens dunks', True),
    ('vintage levis', True),
    ('adidas ultraboost', False),
]

for query, expected in test_queries:
    result = _is_archive_query(query)
    status = '✅' if result == expected else '❌'
    print(f'   {status} "{query}": {result} (expected {expected})')

print('\n2. Testing _get_comp_thresholds...')
for query, expected_archive in test_queries:
    thresholds = _get_comp_thresholds(query)
    is_archive = thresholds['min_comps'] == 10
    status = '✅' if is_archive == expected_archive else '❌'
    print(f'   {status} "{query}": min_comps={thresholds["min_comps"]}, max_age={thresholds["max_age_days"]}d')

print('\n3. Testing get_sold_data with archive items...')
async def test_sold_data():
    import gap_hunter
    hunter = gap_hunter.GapHunter()
    
    queries = [
        'chrome hearts cross pendant',  # archive
        'nike air max',  # non-archive
    ]
    
    for query in queries:
        print(f'\n   Query: {query}')
        thresholds = _get_comp_thresholds(query)
        print(f'   Thresholds: {thresholds}')
        
        try:
            sold = await hunter.get_sold_data(query)
            if sold:
                print(f'   ✅ Got sold data: avg=${sold.avg_price:.0f}, count={sold.count}')
            else:
                print(f'   ❌ No sold data (insufficient comps)')
        except Exception as e:
            print(f'   ❌ Error: {e}')

asyncio.run(test_sold_data())

print('\n' + '=' * 60)
print('Test complete')
