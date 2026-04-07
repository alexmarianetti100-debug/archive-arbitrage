"""
eBay scraper — HTML search scraping, no API key required.

Fetches eBay search results page and extracts active BIN + auction listings.
Archive pieces are frequently mis-listed by sellers unaware of brand value.

Hardened implementation with rate limiting and timeouts.
"""

import asyncio
import logging
import os
import re
import time
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from .base import BaseScraper, ScrapedItem

logger = logging.getLogger("scraper.ebay")

SEARCH_URL = "https://www.ebay.com/sch/i.html"

# Timeouts (increased for eBay's slow responses)
REQUEST_TIMEOUT = 45.0  # Was 15s
CONNECT_TIMEOUT = 30.0  # Was implicit

# Rate limiting
MIN_REQUEST_INTERVAL = 1.0  # Max 1 request per second


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
    Includes rate limiting and health tracking.
    """

    SOURCE_NAME = "ebay"
    BASE_URL = "https://www.ebay.com"
    
    # Health tracking
    _success_count = 0
    _failure_count = 0
    _last_request_time = 0
    _last_failure = None
    _rate_limit_hits = 0

    def __init__(self, proxy_manager=None):
        super().__init__(proxy_manager)
        self._proxy = _proxy_url()
        self._session: Optional[AsyncSession] = None
        self._session_request_count = 0
        self._session_max_requests = 50  # Recycle session every N requests

    async def _get_session(self) -> AsyncSession:
        """Get or create a reusable curl_cffi session."""
        if (self._session is None or
            self._session_request_count >= self._session_max_requests):
            # Close old session if exists
            if self._session is not None:
                try:
                    await self._session.close()
                except Exception:
                    pass
            self._session = AsyncSession(impersonate="chrome120")
            self._session_request_count = 0
        self._session_request_count += 1
        return self._session

    async def close(self):
        """Close the reusable session."""
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None

    async def _enforce_rate_limit(self):
        """Enforce minimum time between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - elapsed
            logger.debug(f"eBay rate limit: sleeping {sleep_time:.2f}s")
            await asyncio.sleep(sleep_time)
        self._last_request_time = time.time()

    async def _fetch(self, params: dict) -> Optional[BeautifulSoup]:
        """Fetch eBay page with rate limiting and timeouts."""
        await self._enforce_rate_limit()
        
        proxies = {"https": self._proxy} if self._proxy else None
        try:
            session = await self._get_session()
            url = SEARCH_URL + "?" + urlencode(params)

            # Use longer timeout for eBay
            resp = await session.get(
                url,
                proxies=proxies,
                timeout=REQUEST_TIMEOUT
            )

            # Check for rate limiting
            if resp.status_code == 429:
                self._rate_limit_hits += 1
                logger.warning(f"eBay rate limited (429)")
                return None

            if resp.status_code != 200 or "splashui/challenge" in str(resp.url):
                logger.debug(f"eBay bot challenge or non-200: {resp.status_code}")
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            return soup

        except asyncio.TimeoutError:
            logger.warning(f"eBay request timed out after {REQUEST_TIMEOUT}s")
            return None
        except Exception as e:
            logger.debug(f"eBay fetch error: {e}")
            # Recycle session on error
            try:
                await self.close()
            except Exception:
                pass
            return None

    # Minimum credible price for archive fashion on eBay.
    # Auction starting bids ($1, $4, $13) and international placeholder prices
    # are almost always noise. Anything below this floor is skipped.
    MIN_PRICE = 30.0

    async def search(self, query: str, max_results: int = 20) -> List[ScrapedItem]:
        """Search eBay with error handling and health tracking."""
        params = {
            "_nkw": query,
            "_sacat": "11450",  # Clothing, Shoes & Accessories
            "LH_BIN": "1",      # Buy It Now only
            "LH_Auction": "0",  # Explicitly exclude auction-only listings
            "_sop": "10",       # Sort: newly listed
            "_ipg": "60",
        }
        
        soup = await self._fetch(params)
        if soup is None:
            self._record_failure("fetch_failed")
            return []
            
        items = self._parse_items(soup, max_results)
        
        if items:
            self._record_success()
            logger.info(f"  eBay: {len(items)} results for '{query}'")
        else:
            self._record_failure("parse_failed")
            
        return items
    
    def _parse_items(self, soup: BeautifulSoup, max_results: int) -> List[ScrapedItem]:
        """Parse items from eBay HTML."""
        items = []

        for card in soup.select("li.s-card, li.s-item")[1:max_results + 6]:  # [1:] skips first ad card
            try:
                title_el = card.select_one("[class*='title'], h3")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if "shop on ebay" in title.lower():
                    continue

                # Skip auction cards — they slip through LH_BIN=1 when the listing
                # has both an auction bid AND a BIN price. Bids/time-left elements
                # are present on auction cards but absent on pure BIN listings.
                card_text = card.get_text(" ", strip=True).lower()
                if any(kw in card_text for kw in ("place bid", "bid now", "bids", "time left", "se abre en")):
                    logger.debug(f"eBay skipped auction card: {title[:50]}")
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
                # (guards against "Was $1,500 → $1,125" grabbing the "1" fragment,
                #  and filters auction starting bids / placeholder prices below MIN_PRICE)
                price_matches = [float(n.replace(",", "")) for n in re.findall(r"[\d,]+\.?\d*", price_text) if float(n.replace(",", "")) >= self.MIN_PRICE]
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

        return items

    def _record_success(self):
        """Record successful scrape."""
        self.__class__._success_count += 1

    def _record_failure(self, reason: str):
        """Record failed scrape."""
        self.__class__._failure_count += 1
        self.__class__._last_failure = datetime.now()
        logger.debug(f"eBay failure: {reason}")

    @classmethod
    def get_health_status(cls) -> dict:
        """Get scraper health status."""
        total = cls._success_count + cls._failure_count
        success_rate = cls._success_count / total if total > 0 else 1.0

        return {
            "success_count": cls._success_count,
            "failure_count": cls._failure_count,
            "success_rate": success_rate,
            "last_failure": cls._last_failure.isoformat() if cls._last_failure else None,
            "rate_limit_hits": cls._rate_limit_hits,
            "healthy": success_rate > 0.8 and cls._failure_count < 10,
            "timeout_seconds": REQUEST_TIMEOUT,
        }

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

    # close() defined in __init__ section — reuses shared session
