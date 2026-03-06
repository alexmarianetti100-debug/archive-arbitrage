"""
Vinted deep diagnostic - single domain, captures:
  - ALL network requests/responses
  - Screenshot of what the page actually looks like
  - Full page title and text snippet
  - Any consent/login walls
"""

import asyncio
import json
import sys
from urllib.parse import quote_plus
from playwright.async_api import async_playwright

QUERY = "balenciaga"
DOMAIN = "https://www.vinted.com"
SEARCH_URL = f"{DOMAIN}/catalog?search_text={quote_plus(QUERY)}&order=newest_first"
SCREENSHOT_PATH = "/tmp/vinted_debug.png"


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--disable-web-security"],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
        """)
        page = await context.new_page()

        all_requests = []
        all_responses = []

        page.on("request", lambda r: all_requests.append(r.url))
        async def on_response(r):
            all_responses.append((r.url, r.status))
        page.on("response", on_response)

        print(f"\n🌐 Loading: {SEARCH_URL}")
        try:
            await page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            print(f"❌ page.goto error: {e}")

        # Wait a bit longer for async JS to fire
        await asyncio.sleep(8)

        final_url = page.url
        title = await page.title()
        print(f"📍 Final URL: {final_url}")
        print(f"📄 Page title: {title}")

        # Screenshot
        await page.screenshot(path=SCREENSHOT_PATH, full_page=False)
        print(f"📸 Screenshot saved: {SCREENSHOT_PATH}")

        # Page text snippet (first 800 chars)
        body_text = await page.evaluate("() => document.body.innerText")
        print(f"\n📝 Page text (first 800 chars):\n{body_text[:800]}\n")

        # All network requests made
        print(f"\n🔗 All requests ({len(all_requests)} total) — filtering for vinted API calls:")
        api_hits = [u for u in all_requests if "/api/" in u]
        for u in api_hits[:30]:
            print(f"   {u}")
        if not api_hits:
            print("   (none — Vinted made NO internal API calls)")

        # Check for consent/cookie wall
        consent_keywords = ["cookie", "consent", "accept", "gdpr", "privacy", "login", "sign in", "log in"]
        text_lower = body_text.lower()
        found = [kw for kw in consent_keywords if kw in text_lower]
        print(f"\n🍪 Consent/auth wall keywords found: {found or 'none'}")

        # DOM: try every possible item selector
        selectors = [
            '[data-testid*="item"]',
            '.feed-grid__item',
            'a[href*="/items/"]',
            '[class*="ItemBox"]',
            '[class*="item-box"]',
            '[class*="ProductCard"]',
            '[class*="CatalogItem"]',
            'article',
        ]
        print(f"\n🔍 DOM element counts:")
        for sel in selectors:
            try:
                els = await page.query_selector_all(sel)
                print(f"   {sel:<40} → {len(els)}")
            except Exception as e:
                print(f"   {sel:<40} → error: {e}")

        # Check cookies set
        cookies = await context.cookies()
        print(f"\n🍪 Cookies set ({len(cookies)}):")
        for c in cookies[:10]:
            print(f"   {c['name']} = {c['value'][:40]}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
