#!/usr/bin/env python3
"""
Vinted Scraper Diagnostic Tool

Tests various approaches to identify why Vinted is returning 0 items.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

async def test_vinted_api_kit():
    """Test the current vinted-api-kit implementation."""
    print("\n" + "="*60)
    print("TEST 1: Vinted API Kit (Current Implementation)")
    print("="*60)
    
    try:
        from vinted import VintedClient
        from vinted.exceptions import VintedAPIError, VintedNetworkError
        print("✅ vinted-api-kit imported successfully")
    except ImportError as e:
        print(f"❌ vinted-api-kit not available: {e}")
        return False
    
    # Test with just one domain
    domain = "https://www.vinted.com"
    query = "nike"
    proxy = None
    
    # Check proxy config
    proxy_host = os.getenv("PROXY_HOST")
    proxy_port = os.getenv("PROXY_PORT")
    proxy_user = os.getenv("PROXY_USERNAME")
    proxy_pass = os.getenv("PROXY_PASSWORD")
    
    if proxy_user and proxy_pass:
        proxy = f"{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
        print(f"✅ Proxy configured: {proxy_host}:{proxy_port}")
    else:
        print("⚠️  No proxy configured - may be blocked by Cloudflare")
    
    url = f"{domain}/catalog?search_text={query}&order=newest_first"
    
    print(f"\nSearching: {url}")
    
    try:
        async with VintedClient(
            proxy=proxy,
            persist_cookies=False,  # Don't persist for test
        ) as client:
            print("✅ VintedClient created")
            
            print("⏳ Searching items...")
            items = await client.search_items(url=url, per_page=5)
            
            print(f"✅ Search completed - found {len(items)} items")
            
            if items:
                print(f"\nFirst item:")
                item = items[0]
                print(f"  Title: {getattr(item, 'title', 'N/A')}")
                print(f"  Price: {getattr(item, 'price', 'N/A')}")
                print(f"  Brand: {getattr(item, 'brand_title', 'N/A')}")
            else:
                print("⚠️  No items returned - possible API change or blocking")
                
            return len(items) > 0
            
    except VintedAPIError as e:
        print(f"❌ Vinted API Error: {e}")
        return False
    except VintedNetworkError as e:
        print(f"❌ Vinted Network Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_direct_http():
    """Test direct HTTP request to Vinted API."""
    print("\n" + "="*60)
    print("TEST 2: Direct HTTP Request")
    print("="*60)
    
    try:
        import httpx
    except ImportError:
        print("❌ httpx not installed")
        return False
    
    # Vinted's internal API endpoint
    domain = "https://www.vinted.com"
    query = "nike"
    
    # Try to hit their API directly
    api_url = f"{domain}/api/v2/catalog/items"
    params = {
        "search_text": query,
        "per_page": 5,
        "order": "newest_first"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    print(f"Requesting: {api_url}")
    print(f"Params: {params}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(api_url, params=params, headers=headers)
            
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                print(f"✅ Success - found {len(items)} items")
                
                if items:
                    print(f"\nFirst item:")
                    item = items[0]
                    print(f"  Title: {item.get('title', 'N/A')}")
                    print(f"  Price: {item.get('price', 'N/A')}")
                
                return len(items) > 0
            else:
                print(f"❌ HTTP {response.status_code}")
                print(f"Response preview: {response.text[:500]}")
                return False
                
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        return False


async def test_with_playwright():
    """Test using Playwright browser automation."""
    print("\n" + "="*60)
    print("TEST 3: Playwright Browser Automation")
    print("="*60)
    
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ Playwright not installed")
        return False
    
    domain = "https://www.vinted.com"
    query = "nike"
    url = f"{domain}/catalog?search_text={query}&order=newest_first"
    
    print(f"Navigating: {url}")
    
    items_found = []
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            
            page = await context.new_page()
            
            # Listen for API responses
            async def handle_response(response):
                if "catalog/items" in response.url:
                    print(f"📡 API call detected: {response.url}")
                    try:
                        data = await response.json()
                        items = data.get("items", [])
                        print(f"   Found {len(items)} items in API response")
                        items_found.extend(items)
                    except:
                        pass
            
            page.on("response", handle_response)
            
            print("⏳ Loading page...")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            print("⏳ Waiting for content...")
            await asyncio.sleep(3)
            
            # Try to extract items from page
            items = await page.evaluate("""() => {
                const items = [];
                const cards = document.querySelectorAll('[data-testid*="item"], .feed-grid__item, .ItemBox_content');
                cards.forEach(card => {
                    const title = card.querySelector('h2, .ItemBox_title, [data-testid*="title"]')?.textContent?.trim();
                    const price = card.querySelector('.ItemBox_price, [data-testid*="price"]')?.textContent?.trim();
                    if (title) {
                        items.push({title, price});
                    }
                });
                return items;
            }""")
            
            print(f"✅ Page loaded - found {len(items)} items in DOM")
            
            if items:
                print(f"\nFirst item:")
                print(f"  Title: {items[0].get('title', 'N/A')}")
                print(f"  Price: {items[0].get('price', 'N/A')}")
            
            await browser.close()
            
            return len(items) > 0 or len(items_found) > 0
            
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_domain_connectivity():
    """Test basic connectivity to Vinted domains."""
    print("\n" + "="*60)
    print("TEST 4: Domain Connectivity")
    print("="*60)
    
    try:
        import httpx
    except ImportError:
        print("❌ httpx not installed")
        return
    
    domains = [
        "https://www.vinted.com",
        "https://www.vinted.co.uk",
        "https://www.vinted.fr",
        "https://www.vinted.de",
    ]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for domain in domains:
            try:
                response = await client.get(domain)
                status = "✅" if response.status_code == 200 else "⚠️"
                print(f"{status} {domain}: HTTP {response.status_code}")
            except Exception as e:
                print(f"❌ {domain}: {type(e).__name__}")


async def main():
    print("🔍 Vinted Scraper Diagnostic Tool")
    print("Testing various approaches to identify the issue...")
    
    results = {}
    
    # Test 1: Current implementation
    results["vinted_api_kit"] = await test_vinted_api_kit()
    
    # Test 2: Direct HTTP
    results["direct_http"] = await test_direct_http()
    
    # Test 3: Playwright
    results["playwright"] = await test_with_playwright()
    
    # Test 4: Connectivity
    await test_domain_connectivity()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    working = sum(results.values())
    total = len(results)
    
    print(f"\n{working}/{total} tests passed")
    
    if working == 0:
        print("\n🔴 All methods failed - Vinted may be completely blocking automated access")
        print("   Consider temporarily disabling Vinted scraper")
    elif results["vinted_api_kit"]:
        print("\n✅ vinted-api-kit works - issue may be intermittent or proxy-related")
    elif results["playwright"]:
        print("\n✅ Playwright works - consider switching to browser-based scraping")
    elif results["direct_http"]:
        print("\n✅ Direct HTTP works - API endpoint is accessible")


if __name__ == "__main__":
    asyncio.run(main())
