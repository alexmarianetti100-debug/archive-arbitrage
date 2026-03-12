"""
Mercari scraper using Playwright Chromium + Webshare rotating proxy.

Supports two markets:
  - US: mercari.com (USD, requires proxy to bypass CF)
  - JP: jp.mercari.com (JPY, no proxy needed)

CF is bypassed using the proxy IP — headless Chromium passes with a fresh residential IP.
"""

import asyncio
import os
import logging
from typing import List
from urllib.parse import quote_plus

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .base import BaseScraper, ScrapedItem

logger = logging.getLogger("scraper.mercari")


def _build_proxy_cfg() -> dict | None:
    """Build Playwright proxy config from env vars (same Webshare creds as Vinted)."""
    host = os.getenv("PROXY_HOST", "")
    port = os.getenv("PROXY_PORT", "")
    user = os.getenv("PROXY_USERNAME", "")
    pwd = os.getenv("PROXY_PASSWORD", "")
    if host and port and user and pwd:
        return {"server": f"http://{host}:{port}", "username": user, "password": pwd}
    return None


DOMAINS = [
    {
        "base": "https://www.mercari.com",
        "search_url": "https://www.mercari.com/search/?keyword={query}",
        "item_selector": 'a[href*="/item/m"]',
        "currency": "USD",
        "locale": "en-US",
        "use_proxy": True,
        "price_pattern": r"\$([0-9,.]+)",
    },
    {
        "base": "https://jp.mercari.com",
        "search_url": "https://jp.mercari.com/search?keyword={query}&order=desc&sort=created_time",
        "item_selector": 'li[data-testid] a[href]',
        "currency": "JPY",
        "locale": "ja-JP",
        "use_proxy": False,
        "price_pattern": r"¥\s*([0-9,]+)",
    },
    {
        "base": "https://www.mercari.com",
        "search_url": "https://www.mercari.com/tw/search/?keyword={query}",
        "item_selector": 'a[href*="/item/m"]',
        "currency": "TWD",
        "locale": "zh-TW",
        "use_proxy": True,
        "price_pattern": r"NT\$\s*([0-9,.]+)|([0-9,]+)\s*元",
    },
]


class MercariScraper(BaseScraper):
    """Scrape Mercari US and JP using Playwright Chromium with DOM extraction."""

    SOURCE_NAME = "mercari"

    def __init__(self, proxy_manager=None):
        super().__init__(proxy_manager)
        self._proxy_cfg = _build_proxy_cfg()

    async def _search_domain(
        self,
        domain: dict,
        query: str,
        max_results: int,
    ) -> List[ScrapedItem]:
        """Search a single Mercari domain and return ScrapedItems."""
        import re

        url = domain["search_url"].format(query=quote_plus(query))
        sel = domain["item_selector"]
        currency = domain["currency"]
        proxy = self._proxy_cfg if domain["use_proxy"] else None

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                    proxy=proxy,
                )
                ctx = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    locale=domain["locale"],
                )
                await ctx.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.chrome = { runtime: {} };
                """)
                page = await ctx.new_page()

                await page.goto(url, wait_until="domcontentloaded", timeout=25000)

                # Wait up to 8s for item links to appear
                try:
                    await page.wait_for_selector(sel, timeout=8000)
                except Exception:
                    pass

                # Scroll once to load lazy images
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)

                raw_items = await page.evaluate(f"""() => {{
                    const results = [];
                    const seen = new Set();
                    const links = document.querySelectorAll('{sel}');
                    for (const a of links) {{
                        const href = a.getAttribute('href') || '';
                        const m = href.match(/\\/item\\/(m[a-zA-Z0-9]+)/);
                        if (!m) continue;
                        const itemId = m[1];
                        if (seen.has(itemId)) continue;
                        seen.add(itemId);

                        let container = a;
                        for (let i = 0; i < 6; i++) {{
                            if (container.parentElement) container = container.parentElement;
                        }}

                        const text = a.innerText || container.innerText || '';
                        const img = a.querySelector('img') || container.querySelector('img');
                        const imgSrc = img ? (img.getAttribute('src') || img.getAttribute('data-src') || '') : '';

                        results.push({{
                            id: itemId,
                            text: text.substring(0, 300),
                            image: imgSrc,
                            href: a.href || href,
                        }});
                        if (results.length >= {max_results}) break;
                    }}
                    return results;
                }}""")

                await browser.close()

        except Exception as e:
            logger.debug(f"Mercari ({domain['base']}): {type(e).__name__}: {e}")
            return []

        items = []
        price_re = re.compile(domain["price_pattern"])

        for raw in raw_items:
            text = raw.get("text", "")
            item_id = raw.get("id", "")
            href = raw.get("href", "")

            # Price
            pm = price_re.search(text)
            price = float(pm.group(1).replace(",", "")) if pm else 0.0

            # Title: first meaningful non-price line (skip price/number-only lines)
            lines = [
                l.strip() for l in text.split("\n")
                if l.strip() and len(l.strip()) > 3
                and not l.strip().startswith("$")
                and not re.match(r"^[¥\s\d,]+$", l.strip())  # skip yen price lines
                and not re.match(r"^[\d,]+$", l.strip())
                and not re.match(r"^現在\s*¥", l.strip())     # skip "現在 ¥XXXXX"
            ]
            title = lines[0] if lines else f"Mercari {item_id}"

            if not title and not price:
                continue

            # Build canonical URL
            if href.startswith("http"):
                item_url = href
            else:
                item_url = f"{domain['base']}/item/{item_id}/"

            items.append(ScrapedItem(
                source=self.SOURCE_NAME,
                source_id=item_id,
                url=item_url,
                title=title[:200],
                price=price,
                currency=currency,
                images=[raw["image"]] if raw.get("image") else [],
                raw_data={"mercari_id": item_id, "market": domain["base"]},
            ))

        logger.info(f"  Mercari ({domain['base']}): {len(items)} results for '{query}'")
        return items

    async def search(self, query: str, max_results: int = 20) -> List[ScrapedItem]:
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not installed — Mercari disabled.")
            return []

        per_domain = max(5, max_results // len(DOMAINS))

        # Run sequentially — concurrent Playwright browsers compete for resources
        # and cause items to never load. Sequential is slower but reliable.
        items = []
        for domain in DOMAINS:
            try:
                batch = await self._search_domain(domain, query, per_domain)
                items.extend(batch)
            except Exception as e:
                logger.debug(f"Mercari domain error: {e}")

        return items[:max_results]

    async def get_item_details(self, item_id: str):
        return None

    async def check_availability(self, item_id: str) -> bool:
        return True

    async def close(self):
        pass  # Each search spawns+closes its own browser instance
