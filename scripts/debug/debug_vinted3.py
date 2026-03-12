"""
Deep dive: single domain with Camoufox.
Captures ALL network requests, all API URLs, DOM card count with various selectors,
and a screenshot of the final rendered page.
"""
import asyncio, re, sys
from urllib.parse import quote_plus
from camoufox.async_api import AsyncCamoufox

QUERY = "balenciaga"
DOMAIN = "https://www.vinted.com"
SEARCH_URL = f"{DOMAIN}/catalog?search_text={quote_plus(QUERY)}&order=newest_first"

async def main():
    print(f"\n🔬 Deep Vinted diagnostic — {DOMAIN}\n")
    async with AsyncCamoufox(headless=True, geoip=True) as browser:
        ctx = await browser.new_context()
        page = await ctx.new_page()

        api_urls = []
        api_data = []

        async def on_response(resp):
            if "vinted" in resp.url and "/api/" in resp.url:
                api_urls.append(resp.url)
            if "/api/v2/catalog/items" in resp.url:
                try:
                    api_data.append(await resp.json())
                except Exception:
                    pass

        page.on("response", on_response)

        print(f"Navigating to: {SEARCH_URL}")
        await page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=30000)
        print(f"Page title: {await page.title()}")
        print(f"Final URL:  {page.url}")

        # Wait extra time for lazy-loaded API calls
        print("Waiting 12s for API calls...")
        await asyncio.sleep(12)

        print(f"\n📡 API URLs seen ({len(api_urls)}):")
        for u in sorted(set(api_urls)):
            print(f"  {u}")

        print(f"\n🎯 /api/v2/catalog/items hits: {len(api_data)}")
        for d in api_data:
            items = d.get("items", [])
            print(f"  → {len(items)} items in response")
            if items:
                first = items[0]
                print(f"     sample: {first.get('title','?')} — {first.get('price',{})}")

        # Try all selectors
        print(f"\n🔍 DOM selectors:")
        selectors = {
            "a[href*='/items/']": "all item links (too broad)",
            '[data-testid="item-box"]': "item boxes by testid",
            '[data-testid*="item-box"]': "item boxes partial testid",
            '.feed-grid__item': "feed grid items",
            '[class*="ItemBox"]': "ItemBox classes",
            '[class*="item-box"]': "item-box classes",
            '[class*="CatalogItem"]': "CatalogItem classes",
            '[class*="ProductCard"]': "ProductCard classes",
            'article': "article tags",
        }
        for sel, desc in selectors.items():
            els = await page.query_selector_all(sel)
            print(f"  {sel:<45} → {len(els):>5}  ({desc})")

        # Try to find price elements inside item links
        item_links = await page.query_selector_all("a[href*='/items/']")
        items_with_price = 0
        for link in item_links[:50]:
            price_el = await link.query_selector('[class*="price"], [class*="Price"], [data-testid*="price"]')
            if price_el:
                items_with_price += 1
        print(f"\n  Item links with price child: {items_with_price} / {min(50, len(item_links))} sampled")

        # Screenshot
        await page.screenshot(path="/tmp/vinted_camoufox.png")
        print(f"\n📸 Screenshot: /tmp/vinted_camoufox.png")

        # Check if there's a cookie/consent banner
        body_text = await page.evaluate("() => document.body.innerText")
        print(f"\n📝 Body text preview:\n{body_text[:500]}")

        await ctx.close()

if __name__ == "__main__":
    asyncio.run(main())
