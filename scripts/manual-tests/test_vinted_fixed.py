#!/usr/bin/env python3
"""
Test the fixed Vinted scraper implementation.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path BEFORE any imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

async def test_fixed_vinted():
    """Test the fixed Vinted scraper."""
    print("🔧 Testing Fixed Vinted Scraper")
    print("=" * 60)
    
    # Import directly from file to avoid circular imports
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scrapers"))
    from vinted_fixed import VintedScraperFixed
    
    scraper = VintedScraperFixed()
    
    # Check health status
    health = scraper.get_health_status()
    print(f"\nHealth Status:")
    print(f"  Disabled: {health['disabled']}")
    print(f"  Consecutive Failures: {health['consecutive_failures']}")
    print(f"  Last Success: {health['last_success'] or 'Never'}")
    
    if health['disabled']:
        print(f"\n⚠️  Vinted is disabled until {health['disabled_until']}")
        print("   Skipping test")
        return
    
    # Test search
    query = "nike"
    print(f"\n🔍 Searching for: '{query}'")
    print("-" * 60)
    
    try:
        items = await scraper.search(query, max_results=10)
        
        print(f"\n✅ Search completed!")
        print(f"   Found {len(items)} items")
        
        if items:
            print(f"\nFirst 3 items:")
            for i, item in enumerate(items[:3], 1):
                print(f"\n  {i}. {item.title[:50]}...")
                print(f"     Price: ${item.price} {item.currency}")
                print(f"     Brand: {item.brand or 'N/A'}")
                print(f"     URL: {item.url[:60]}...")
        
        # Check health after search
        health = scraper.get_health_status()
        print(f"\n📊 Health after search:")
        print(f"   Healthy: {health['healthy']}")
        print(f"   Consecutive Failures: {health['consecutive_failures']}")
        
        return len(items) > 0
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_cookie_factory():
    """Test the cookie factory independently."""
    print("\n" + "=" * 60)
    print("🍪 Testing Cookie Factory")
    print("=" * 60)
    
    # Import directly from file to avoid circular imports
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scrapers"))
    from vinted_fixed import VintedCookieFactory
    
    factory = VintedCookieFactory("https://www.vinted.com")
    
    print("\nFetching cookies...")
    cookies = await factory.get_cookies()
    
    if cookies.get("access_token_web"):
        print("✅ Got access_token_web cookie")
        print(f"   Token: {cookies['access_token_web'][:20]}...")
        return True
    else:
        print("❌ No access_token_web in cookies")
        print(f"   Available cookies: {list(cookies.keys())}")
        return False


async def main():
    print("🧪 Vinted Scraper Fix Test Suite")
    
    # Test 1: Cookie factory
    cookie_ok = await test_cookie_factory()
    
    # Test 2: Full scraper
    scraper_ok = await test_fixed_vinted()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    print(f"Cookie Factory: {'✅ PASS' if cookie_ok else '❌ FAIL'}")
    print(f"Scraper: {'✅ PASS' if scraper_ok else '❌ FAIL'}")
    
    if scraper_ok:
        print("\n🎉 Vinted scraper is working!")
    elif cookie_ok:
        print("\n⚠️  Cookies work but scraper failed - may need proxy")
    else:
        print("\n🔴 Vinted is blocking requests - may need proxy or different approach")


if __name__ == "__main__":
    asyncio.run(main())
