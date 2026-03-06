"""
Vinted scraper — Camoufox (anti-detection Firefox fork).

Root cause of zero results (diagnosed 2026-03-06):
  Vinted uses Cloudflare Bot Management. Standard headless Playwright/Chromium
  gets served a JS challenge page ("Just a moment…"). Camoufox bypasses this
  by spoofing a realistic Firefox fingerprint.

Architecture:
  - One shared Camoufox browser instance per process (lazy-started)
  - All 20 domains fetched concurrently, capped at MAX_CONCURRENT contexts
  - Per-domain: up to MAX_RETRIES attempts with exponential backoff
  - Cloudflare challenge detection aborts immediately (no point retrying sans proxy)
  - DOM extraction via `.feed-grid__item` cards + title-attribute parser
    (Camoufox/Firefox renders Vinted server-side; no /api/v2/catalog/items calls)
"""

import asyncio
import logging
import re
from typing import List, Optional, Tuple
from urllib.parse import quote_plus

from .base import BaseScraper, ScrapedItem

try:
    from camoufox.async_api import AsyncCamoufox
    CAMOUFOX_AVAILABLE = True
except ImportError:
    CAMOUFOX_AVAILABLE = False

logger = logging.getLogger("scraper.vinted")

# ── Tuning ────────────────────────────────────────────────────────────────────
MAX_CONCURRENT = 2    # max simultaneous Camoufox browser contexts (3+ causes timeouts)
MAX_RETRIES    = 2    # per-domain retry attempts on timeout/error
PAGE_TIMEOUT   = 30000  # ms — page.goto hard timeout
SETTLE_SLEEP   = 2    # seconds after domcontentloaded before scraping

# ── Domain list ───────────────────────────────────────────────────────────────
DEFAULT_DOMAINS = [
    "https://www.vinted.com",       # US / global
    "https://www.vinted.co.uk",     # UK
    "https://www.vinted.fr",        # France
    "https://www.vinted.de",        # Germany
    "https://www.vinted.es",        # Spain
    "https://www.vinted.it",        # Italy
    "https://www.vinted.pl",        # Poland
    "https://www.vinted.be",        # Belgium
    "https://www.vinted.nl",        # Netherlands
    "https://www.vinted.at",        # Austria
    "https://www.vinted.lu",        # Luxembourg
    "https://www.vinted.cz",        # Czech Republic
    "https://www.vinted.sk",        # Slovakia
    "https://www.vinted.hu",        # Hungary
    "https://www.vinted.ro",        # Romania
    "https://www.vinted.pt",        # Portugal
    "https://www.vinted.se",        # Sweden
    "https://www.vinted.dk",        # Denmark
    "https://www.vinted.fi",        # Finland
    "https://www.vinted.lt",        # Lithuania
]

# ── Locale / currency maps ────────────────────────────────────────────────────
_LOCALE_MAP = {
    ".co.uk": "en-GB", ".fr": "fr-FR", ".de": "de-DE", ".es": "es-ES",
    ".it":    "it-IT", ".pl": "pl-PL", ".be": "fr-BE", ".nl": "nl-NL",
    ".at":    "de-AT", ".lu": "fr-LU", ".cz": "cs-CZ", ".sk": "sk-SK",
    ".hu":    "hu-HU", ".ro": "ro-RO", ".pt": "pt-PT", ".se": "sv-SE",
    ".dk":    "da-DK", ".fi": "fi-FI", ".lt": "lt-LT",
}
_EUR_TLDS = {".fr", ".de", ".it", ".es", ".be", ".nl", ".at", ".lu",
             ".pt", ".fi", ".lt", ".sk"}
_LOCAL_CURRENCY = {
    ".co.uk": "GBP", ".pl": "PLN", ".cz": "CZK",
    ".hu": "HUF", ".ro": "RON", ".se": "SEK", ".dk": "DKK",
}

# Price symbols per currency (for title-attr parsing)
_CURRENCY_SYMBOLS = {
    "GBP": "£", "EUR": "€", "PLN": "zł", "CZK": "Kč",
    "HUF": "Ft", "RON": "lei", "SEK": "kr", "DKK": "kr",
}


def _domain_locale(domain: str) -> str:
    for tld, loc in _LOCALE_MAP.items():
        if tld in domain:
            return loc
    return "en-US"


def _domain_currency(domain: str) -> str:
    if any(tld in domain for tld in _EUR_TLDS):
        return "EUR"
    return next((c for tld, c in _LOCAL_CURRENCY.items() if tld in domain), "USD")


# ── Title-attribute parser ────────────────────────────────────────────────────
def _parse_title_attr(title_attr: str) -> Tuple[str, str, str, float]:
    """
    Parse Vinted card title attribute.

    Format (confirmed via DOM inspection 2026-03-06):
      "Kids Balenciaga hoodie, brand: Balenciaga, condition: Very good,
       size: 3T/3, $40.59, $43.32 includes Buyer Protection"

    Returns (title, brand, size, price).
    """
    if not title_attr:
        return "", "", "", 0.0

    # Brand — localized field name varies by domain
    _brand_keys = r"brand|marque|marke|merk|marca|marka|varumärke|tuotemerkki|prekių ženklas|značka|brand"
    brand = ""
    m = re.search(rf"(?:{_brand_keys}):\s*([^,]+)", title_attr, re.I)
    if m:
        brand = m.group(1).strip()

    # Size — localized field name varies by domain
    _size_keys = r"size|taille|größe|maat|talla|taglia|rozmiar|storlek|koko|dydis|veľkosť|velikost|méret|dimensiune"
    size = ""
    m = re.search(rf"(?:{_size_keys}):\s*([^,]+)", title_attr, re.I)
    if m:
        size = m.group(1).strip()

    # First price token — handles prefix symbols ($€£) and suffix units (zł, lei, kr, Ft, Kč)
    prices = re.findall(
        r"[\$€£]\s*[\d\s,.]+\d"                                          # €200 / £175 / $40.59 / € 5,00
        r"|[\d][\d\s,.]*\s*(?:zł|lei|kr|Ft|Kč|SEK|DKK|PLN|CZK|HUF|RON)",  # 900,00 zł / 2 283,18 kr
        title_attr
    )
    price = 0.0
    if prices:
        price = _parse_localized_price(prices[0])

    # Item title = everything before the first metadata comma
    cut = len(title_attr)
    for pattern in [r",\s*brand:", r",\s*condition:", r",\s*size:",
                    r",\s*[\$€£]", r",\s*\d"]:
        m = re.search(pattern, title_attr, re.I)
        if m:
            cut = min(cut, m.start())
    title = title_attr[:cut].strip().rstrip(",")

    return title, brand, size, price


def _parse_localized_price(price_str: str) -> float:
    """
    Parse a price string with locale-aware decimal handling.

    Handles:
      $40.59        → 40.59   (dot decimal)
      € 5,00        → 5.00    (comma decimal, EU)
      900,00 zł     → 900.00  (comma decimal, PL)
      2,283.18 kr   → 2283.18 (comma thousands, dot decimal, SE)
      2 283,18 kr   → 2283.18 (space thousands, comma decimal)
      1.234,56      → 1234.56 (dot thousands, comma decimal)
    """
    # Strip currency symbols and unit suffixes
    s = re.sub(r"[^\d,.\s]", "", price_str).strip()
    # Remove spaces (used as thousands separator in some locales)
    s = s.replace(" ", "")

    if not s:
        return 0.0

    has_comma = "," in s
    has_dot   = "." in s

    if has_comma and has_dot:
        last_comma = s.rfind(",")
        last_dot   = s.rfind(".")
        if last_dot > last_comma:
            # dot is decimal: 2,283.18
            s = s.replace(",", "")
        else:
            # comma is decimal: 1.234,56
            s = s.replace(".", "").replace(",", ".")
    elif has_comma:
        # Comma only — decimal if ≤2 digits follow, else thousands
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = s.replace(",", ".")   # 900,00 → 900.00
        else:
            s = s.replace(",", "")    # 1,234 → 1234

    try:
        return float(s)
    except ValueError:
        return 0.0


# ── Cloudflare detection ──────────────────────────────────────────────────────
async def _is_cf_blocked(page) -> bool:
    """Return True if Cloudflare is serving a bot-challenge page."""
    try:
        title = (await page.title()).lower()
        if "just a moment" in title:
            return True
        body = await page.evaluate("() => document.body?.innerText || ''")
        return "verifying you are human" in body.lower()
    except Exception:
        return False


# ── Shared browser singleton ──────────────────────────────────────────────────
_camoufox_ctx = None
_browser      = None
_browser_lock = asyncio.Lock()


async def _ensure_browser():
    global _camoufox_ctx, _browser
    async with _browser_lock:
        if _browser:
            return _browser
        if not CAMOUFOX_AVAILABLE:
            raise ImportError(
                "camoufox not installed.\n"
                "  pip install 'camoufox[geoip]' && python -m camoufox fetch"
            )
        _camoufox_ctx = AsyncCamoufox(headless=True, geoip=True)
        _browser = await _camoufox_ctx.__aenter__()
        logger.debug("Camoufox browser started")
        return _browser


async def _close_browser():
    global _camoufox_ctx, _browser
    if _camoufox_ctx:
        try:
            await _camoufox_ctx.__aexit__(None, None, None)
        except Exception:
            pass
    _browser = None
    _camoufox_ctx = None


# ── Scraper class ─────────────────────────────────────────────────────────────
class VintedScraperWrapper(BaseScraper):
    """Search Vinted across all international domains using Camoufox."""

    SOURCE_NAME = "vinted"

    def __init__(self, domains: Optional[List[str]] = None, proxy_manager=None):
        super().__init__(proxy_manager)
        self.domains = domains or DEFAULT_DOMAINS

    # ── Single-domain search (with retries) ───────────────────────────────────
    async def _search_domain(
        self, browser, domain: str, query: str, max_results: int
    ) -> List[ScrapedItem]:
        """
        Fetch one Vinted domain with up to MAX_RETRIES attempts.
        Returns empty list and logs a warning on persistent failure.
        """
        currency   = _domain_currency(domain)
        search_url = f"{domain}/catalog?search_text={quote_plus(query)}&order=newest_first"
        last_error = ""

        for attempt in range(1, MAX_RETRIES + 1):
            ctx = None
            try:
                ctx = await browser.new_context(locale=_domain_locale(domain))
                page = await ctx.new_page()

                try:
                    await page.goto(search_url, wait_until="domcontentloaded",
                                    timeout=PAGE_TIMEOUT)
                except Exception as e:
                    last_error = f"goto timeout/error: {e}"
                    await ctx.close()
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(2 ** attempt)  # 2s, 4s backoff
                    continue

                # Abort immediately if Cloudflare is blocking
                if await _is_cf_blocked(page):
                    logger.debug(f"Vinted ({domain}): Cloudflare blocked — skipping")
                    await ctx.close()
                    return []

                # Wait for JS-rendered product grid — poll until cards appear or timeout
                for _ in range(12):
                    cards = await page.query_selector_all(".feed-grid__item")
                    if cards:
                        break
                    await asyncio.sleep(1)

                items = await self._extract_from_dom(page, domain, currency, max_results)
                await ctx.close()

                if items:
                    return items

                # Zero results — retry in case of transient render miss
                last_error = "0 items from DOM"
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)

            except Exception as e:
                last_error = str(e)
                if ctx:
                    try:
                        await ctx.close()
                    except Exception:
                        pass
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)

        logger.debug(f"Vinted ({domain}): gave up after {MAX_RETRIES} attempts — {last_error}")
        return []

    # ── DOM extraction ────────────────────────────────────────────────────────
    async def _extract_from_dom(
        self, page, domain: str, currency: str, max_results: int
    ) -> List[ScrapedItem]:
        """
        Extract listings from a rendered Vinted catalog page.

        Confirmed DOM structure (2026-03-06 inspection on vinted.com + vinted.it):

          .feed-grid__item
            ├─ a.new-item-box__overlay          ← href + title attr with all metadata
            │    title="Item name, brand: X, condition: Y, size: Z, $price, $fee incl."
            └─ img.web_ui__Image__content       ← item photo src
               data-testid="product-item-id-{ID}--image--img"

        Fallback selectors tried in order if primary fails.
        """
        items: List[ScrapedItem] = []

        # Selector priority list — most specific first
        card_selectors = [
            ".feed-grid__item",
            '[data-testid*="product-item-id"]',
            ".new-item-box__container",
            'a[href*="/items/"]',
        ]

        cards = []
        for sel in card_selectors:
            try:
                cards = await page.query_selector_all(sel)
                if cards:
                    break
            except Exception:
                continue

        if not cards:
            logger.debug(f"Vinted ({domain}): no cards found in DOM")
            return []

        for card in cards[:max_results]:
            try:
                # ── URL + metadata from overlay anchor ──
                link = await card.query_selector(
                    "a.new-item-box__overlay, a[href*='/items/']"
                )
                if not link:
                    continue

                href = (await link.get_attribute("href") or "").strip()
                if not href:
                    continue
                if not href.startswith("http"):
                    href = f"{domain}{href}"

                title_attr = await link.get_attribute("title") or ""
                title, brand, size, price = _parse_title_attr(title_attr)

                # ── Item ID from URL ──
                id_match = re.search(r"/items/(\d+)", href)
                item_id = id_match.group(1) if id_match else ""

                # ── Title fallback: URL slug ──
                if not title:
                    slug_match = re.search(r"/items/\d+-?([\w-]+)", href)
                    if slug_match:
                        title = slug_match.group(1).replace("-", " ").title()

                # ── Price fallback: look for price element in DOM ──
                if price == 0.0:
                    price_el = await card.query_selector(
                        '[data-testid*="price"], [class*="price"], [class*="Price"]'
                    )
                    if price_el:
                        price_text = await price_el.inner_text()
                        try:
                            price = float(re.sub(r"[^\d.]", "",
                                                  price_text.replace(",", ".")))
                        except ValueError:
                            pass

                # ── Image ──
                img_el = await card.query_selector("img")
                img_src = (await img_el.get_attribute("src") or "") if img_el else ""

                if href and price > 0:
                    items.append(ScrapedItem(
                        source=self.SOURCE_NAME,
                        source_id=item_id,
                        url=href,
                        title=(title or "Vinted item").strip(),
                        price=price,
                        currency=currency,
                        brand=brand or None,
                        size=size or None,
                        images=[img_src] if img_src else [],
                    ))

            except Exception as e:
                logger.debug(f"Vinted ({domain}): card parse error: {e}")
                continue

        return items

    # ── Public search ─────────────────────────────────────────────────────────
    async def search(self, query: str, max_results: int = 20) -> List[ScrapedItem]:
        if not CAMOUFOX_AVAILABLE:
            logger.warning(
                "Camoufox not available — Vinted disabled. "
                "Run: pip install 'camoufox[geoip]' && python -m camoufox fetch"
            )
            return []

        try:
            browser = await _ensure_browser()
        except Exception as e:
            logger.warning(f"Vinted: browser start failed: {e}")
            return []

        per_domain = max(3, max_results // max(len(self.domains), 1))
        sem = asyncio.Semaphore(MAX_CONCURRENT)

        async def _fetch(domain: str) -> List[ScrapedItem]:
            async with sem:
                result = await self._search_domain(browser, domain, query, per_domain)
                if result:
                    logger.info(
                        f"  Vinted ({domain.replace('https://www.', '')}): "
                        f"{len(result)} results for '{query}'"
                    )
                return result

        results = await asyncio.gather(*[_fetch(d) for d in self.domains])
        all_items = [item for batch in results for item in batch]

        # Deduplicate by (title prefix + price) to keep regional variants
        seen: set = set()
        unique: List[ScrapedItem] = []
        for item in all_items:
            key = f"{item.title.lower().strip()[:40]}|{item.price}"
            if key not in seen:
                seen.add(key)
                unique.append(item)

        return unique[:max_results]

    async def search_sold(self, query: str, max_results: int = 20) -> List[ScrapedItem]:
        return []

    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        return None

    async def check_availability(self, item_id: str) -> bool:
        return True

    async def close(self):
        await _close_browser()
