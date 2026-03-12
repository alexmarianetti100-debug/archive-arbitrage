#!/usr/bin/env python3
"""Functional test - verify all scrapers can fetch data."""

import asyncio
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from scrapers.grailed import GrailedScraper
from scrapers.poshmark import PoshmarkScraper
from scrapers.ebay import EbayScraper
from scrapers.vinted_fixed import VintedScraperFixed

async def test_scraper(name, scraper_class, query, max_results=3):
    """Test a single scraper."""
    print(f'\n📦 Testing {name}...')
    print('-' * 50)
    
    try:
        async with scraper_class() as scraper:
            items = await scraper.search(query, max_results=max_results)
            
            if items:
                print(f'  ✅ Found {len(items)} items')
                for i, item in enumerate(items[:2], 1):
                    print(f'     {i}. {item.title[:45]}... - ${item.price}')
                return True
            else:
                print(f'  ❌ No items found')
                return False
                
    except Exception as e:
        print(f'  ❌ Error: {type(e).__name__}: {str(e)[:60]}')
        return False

async def main():
    print('🧪 FUNCTIONAL SCRAPER TESTS')
    print('=' * 60)
    print('Testing each scraper with a live query...')
    
    results = {}
    
    # Test each scraper
    results['grailed'] = await test_scraper('Grailed', GrailedScraper, 'nike')
    results['poshmark'] = await test_scraper('Poshmark', PoshmarkScraper, 'nike')
    results['ebay'] = await test_scraper('eBay', EbayScraper, 'nike')
    results['vinted'] = await test_scraper('Vinted', VintedScraperFixed, 'nike')
    
    # Summary
    print('\n' + '=' * 60)
    print('📊 SUMMARY')
    print('=' * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, success in results.items():
        status = '✅' if success else '❌'
        print(f'  {status} {name.capitalize()}')
    
    print(f'\nPassed: {passed}/{total}')
    
    if passed == total:
        print('\n🎉 ALL SCRAPERS FUNCTIONAL!')
        return True
    else:
        print(f'\n⚠️  {total - passed} scraper(s) failed')
        return False

if __name__ == '__main__':
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
