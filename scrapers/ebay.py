"""
eBay scraper — HTML search scraping, no API key required.

Fetches eBay search results page and extracts active BIN + auction listings.
Archive pieces are frequently mis-listed by sellers unaware of brand value.
"""

import logging
import os
import re
from typing import List, Optional
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from .base import BaseScraper, ScrapedItem

logger = logging.getLogger("scraper.ebay")

SEARCH_URL = "https://www.ebay.com/sch/i.html"


def _proxy_url() -> Optional[str]:
    host = os.getenv("PROXY_HOST", "p.webshare.io")
    port = os.getenv("PROXY_PORT", "10000")
    user = os.getenv("PROXY_USERNAME", "")
    pwd  = os.getenv("PROXY_PASSWORD", "")
    if user and pwd:
        return f"http://{user}:{pwd}@{host}:{port}"
    return None


class EbayScraper(BaseScraper):
    """
    Scrape eBay active listings via HTML search.
    Uses curl_cffi Chrome impersonation + Webshare proxy to bypass eBay bot detection.
    """

    SOURCE_NAME = "ebay"
    BASE_URL = "https://www.ebay.com"

    def __init__(self, proxy_manager=None):
        super().__init__(proxy_manager)
        self._proxy = _proxy_url()

    async def _fetch(self, params: dict) -> Optional[BeautifulSoup]:
        proxies = {"https": self._proxy} if self._proxy else None
        try:
            async with AsyncSession(impersonate="chrome124") as session:
                url = SEARCH_URL + "?" + urlencode(params)
                resp = await session.get(url, proxies=proxies, timeout=15)
                if resp.status_code != 200 or "splashui/challenge" in str(resp.url):
                    logger.debug(f"eBay bot challenge or non-200: {resp.status_code}")
                    return None
                return BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            logger.debug(f"eBay fetch error: {e}")
            return None

    async def search(self, query: str, max_results: int = 20) -> List[ScrapedItem]:
        params = {
            "_nkw": query,
            "_sacat": "11450",  # Clothing, Shoes & Accessories
            "LH_BIN": "1",      # Buy It Now only
            "_sop": "10",       # Sort: newly listed
            "_ipg": "60",
        }
        soup = await self._fetch(params)
        if soup is None:
            return []
        items = []

        for card in soup.select("li.s-card, li.s-item")[1:max_results + 6]:  # [1:] skips first ad card
            try:
                title_el = card.select_one("[class*='title'], h3")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if "shop on ebay" in title.lower():
                    continue

                # URL
                link_el = card.select_one("a[href*='/itm/'], a[href*='ebay.com/itm']")
                url = link_el["href"].split("?")[0] if link_el else ""
                item_id_match = re.search(r"/itm/(\d+)", url)
                item_id = item_id_match.group(1) if item_id_match else url
                if not item_id or not url:
                    continue

                # Price — use specific eBay price class to avoid grabbing discount/
                # strikethrough elements that appear first with [class*='price'].
                # Fallback chain: s-item__price → itemprop=price → any *price class
                price_el = (
                    card.select_one(".s-item__price")
                    or card.select_one("[itemprop='price']")
                    or card.select_one("[class*='price']")
                )
                price_text = price_el.get_text(strip=True) if price_el else ""
                # Strip currency symbols and commas, grab the largest number found
                # (guards against "Was $1,500 → $1,125" grabbing the "1" fragment)
                price_matches = [float(n.replace(",", "")) for n in re.findall(r"[\d,]+\.?\d*", price_text) if float(n.replace(",", "")) >= 5.0]
                price = max(price_matches) if price_matches else 0.0
                if price <= 0:
                    continue

                # Image
                img_el = card.select_one("img[src*='ebayimg'], img[src*='i.ebayimg']")
                image = ""
                if img_el:
                    image = img_el.get("src") or img_el.get("data-src") or ""
                    # Upgrade thumbnail to larger image
                    image = re.sub(r"s-l\d+", "s-l500", image)

                # Condition
                cond_el = card.select_one(".SECONDARY_INFO, [class*='subtitle'], [class*='condition']")
                condition = cond_el.get_text(strip=True) if cond_el else None

                if not title or not url:
                    continue

                items.append(ScrapedItem(
                    source=self.SOURCE_NAME,
                    source_id=item_id,
                    url=url,
                    title=title[:200],
                    price=price,
                    currency="USD",
                    condition=condition,
                    images=[image] if image else [],
                    raw_data={"ebay_id": item_id},
                ))

                if len(items) >= max_results:
                    break

            except Exception as e:
                logger.debug(f"eBay card parse error: {e}")
                continue

        logger.info(f"  eBay: {len(items)} results for '{query}'")
        return items

    async def search_sold(self, query: str, max_results: int = 20) -> List[ScrapedItem]:
        """Scrape eBay sold/completed listings for price comps."""
        params = {
            "_nkw": query,
            "_sacat": "11450",
            "LH_Sold": "1",
            "LH_Complete": "1",
            "_sop": "13",
            "_ipg": "60",
        }
        soup = await self._fetch(params)
        if soup is None:
            return []
        items = []
        for card in soup.select("li.s-card, li.s-item")[1:max_results + 6]:
            try:
                title_el = card.select_one("[class*='title'], h3")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if "shop on ebay" in title.lower():
                    continue
                price_el = (
                    card.select_one(".s-item__price")
                    or card.select_one("[itemprop='price']")
                    or card.select_one("[class*='price']")
                )
                price_text = price_el.get_text(strip=True) if price_el else ""
                price_m = [float(n.replace(",", "")) for n in re.findall(r"[\d,]+\.?\d*", price_text) if float(n.replace(",", "")) >= 5.0]
                price = max(price_m) if price_m else 0.0
                if price <= 0:
                    continue
                link_el = card.select_one("a[href*='/itm/'], a[href*='ebay.com/itm']")
                url = link_el["href"].split("?")[0] if link_el else ""
                items.append(ScrapedItem(
                    source=self.SOURCE_NAME,
                    source_id=url,
                    url=url,
                    title=title[:200],
                    price=price,
                    currency="USD",
                ))
                if len(items) >= max_results:
                    break
            except Exception:
                continue
        return items

    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        return None

    async def check_availability(self, item_id: str) -> bool:
        return True

    async def close(self):
        pass  # curl_cffi AsyncSession is context-managed per request
