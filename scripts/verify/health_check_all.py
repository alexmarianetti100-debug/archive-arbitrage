#!/usr/bin/env python3
"""Comprehensive health check for all scrapers."""

import asyncio
import sys
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from scrapers.grailed import GrailedScraper
from scrapers.poshmark import PoshmarkScraper
from scrapers.ebay import EbayScraper
from scrapers.vinted_fixed import VintedScraperFixed

async def health_check():
    print('🔍 COMPREHENSIVE SCRAPER HEALTH CHECK')
    print('=' * 70)
    
    results = {}
    
    # 1. Grailed
    print('\n📦 Grailed Scraper')
    print('-' * 40)
    try:
        health = GrailedScraper.get_health_status()
        print(f"  Status: {'✅ Healthy' if health['healthy'] else '❌ Unhealthy'}")
        print(f"  Failures: {health.get('failures', health.get('failure_count', 0))}")
        print(f"  Using fallback: {health.get('using_fallback', False)}")
        results['grailed'] = health['healthy']
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['grailed'] = False
    
    # 2. Poshmark
    print('\n👗 Poshmark Scraper')
    print('-' * 40)
    try:
        health = PoshmarkScraper.get_health_status()
        print(f"  Status: {'✅ Healthy' if health['healthy'] else '❌ Unhealthy'}")
        print(f"  Success rate: {health['success_rate']:.1%}")
        print(f"  Failures: {health['failure_count']}")
        print(f"  Selector version: {health.get('selector_version', 'N/A')}")
        results['poshmark'] = health['healthy']
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['poshmark'] = False
    
    # 3. eBay
    print('\n🛒 eBay Scraper')
    print('-' * 40)
    try:
        health = EbayScraper.get_health_status()
        print(f"  Status: {'✅ Healthy' if health['healthy'] else '❌ Unhealthy'}")
        print(f"  Success rate: {health['success_rate']:.1%}")
        print(f"  Failures: {health['failure_count']}")
        print(f"  Rate limit hits: {health['rate_limit_hits']}")
        print(f"  Timeout: {health['timeout_seconds']}s")
        results['ebay'] = health['healthy']
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['ebay'] = False
    
    # 4. Vinted
    print('\n🏷️  Vinted Scraper (Fixed)')
    print('-' * 40)
    try:
        # Create instance to call method
        vinted = VintedScraperFixed()
        health = vinted.get_health_status()
        print(f"  Status: {'✅ Healthy' if health['healthy'] else '❌ Unhealthy'}")
        print(f"  Total failures: {health.get('total_failures', 0)}")
        print(f"  Consecutive failures: {health.get('consecutive_failures', 0)}")
        print(f"  Disabled: {health.get('disabled', False)}")
        results['vinted'] = health['healthy']
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['vinted'] = False
    
    # Summary
    print('\n' + '=' * 70)
    print('📊 SUMMARY')
    print('=' * 70)
    
    healthy_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    for name, healthy in results.items():
        status = '✅' if healthy else '❌'
        print(f"  {status} {name.capitalize()}")
    
    print(f"\nTotal: {healthy_count}/{total_count} scrapers healthy")
    
    if healthy_count == total_count:
        print("\n🎉 ALL SCRAPERS HEALTHY!")
        return True
    else:
        print(f"\n⚠️  {total_count - healthy_count} scraper(s) need attention")
        return False

if __name__ == '__main__':
    result = asyncio.run(health_check())
    sys.exit(0 if result else 1)
