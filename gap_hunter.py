#!/usr/bin/env python3
"""
Gap Hunter - Find items listed significantly below their proven sold price.

Strategy:
1. For each target search, fetch recent SOLD prices from Grailed
2. Then find ACTIVE listings for the same item
3. Alert when active price is 30%+ below average sold price
4. This is PROVEN arbitrage - we know what it sells for because it already sold

This is fundamentally different from the old approach:
- Old: "Is this item cheap for its brand?" (guessing)
- New: "This exact item sells for $X, and it's listed for $Y" (proven)
"""

import asyncio
import os
import sys
import json
import time
import signal
import logging
import hashlib
import io
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from pathlib import Path

try:
    import imagehash
    from PIL import Image
    import httpx
    HAS_IMAGE_LIBS = True
except ImportError:
    HAS_IMAGE_LIBS = False

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from scrapers import GrailedScraper, PoshmarkScraper, ScrapedItem
from scrapers.vinted import VintedScraperWrapper as VintedScraper
from scrapers.ebay import EbayScraper
from scrapers.depop import DepopScraper
# Mercari removed — Cloudflare Enterprise tier blocks all proxies
# ShopGoodwill removed — API consistently returns 500
from core.authenticity_v2 import AuthenticityCheckerV2, format_auth_bar, format_auth_grade, MIN_AUTH_SCORE
from core.desirability import check_desirability, REJECT_PATTERNS
from telegram_bot import send_deal_to_subscribers, send_message, init_telegram_db, get_active_subscribers, TELEGRAM_CHANNEL_ID
from core.discord_alerts import send_discord_alert, DISCORD_ENABLED
from core.whop_alerts import send_whop_alert, format_whop_deal_content
from core.deal_quality import calculate_deal_quality, format_signal_line, format_quality_header, DealSignals, THRESHOLD_FIRE_1

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logging.getLogger("vinted").setLevel(logging.CRITICAL)         # suppress proxy 403/502 noise
logging.getLogger("vinted.client").setLevel(logging.CRITICAL)  # suppress "Exception in context" tracebacks
logger = logging.getLogger("gap_hunter")

# ── Trend Engine (always on) ──
_trend_engine = None

def _get_trend_engine():
    global _trend_engine
    if _trend_engine is None:
        try:
            from trend_engine import TrendEngine
            _trend_engine = TrendEngine()
        except ImportError:
            logger.warning("trend_engine not available")
            _trend_engine = False  # sentinel: don't retry
    return _trend_engine if _trend_engine else None

# Config
MIN_GAP_PERCENT = float(os.getenv("GAP_MIN_PERCENT", "0.30"))  # 30% below sold avg
MIN_PROFIT_DOLLARS = float(os.getenv("GAP_MIN_PROFIT", "75"))   # At least $75 profit
MIN_SOLD_COMPS = int(os.getenv("GAP_MIN_COMPS", "20"))           # Need 20+ sold comps for reliable median
POLL_INTERVAL = int(os.getenv("GAP_POLL_INTERVAL", "120"))      # 2 min between cycles

# ── Collab listing filters ────────────────────────────────────────────────────
# Queries containing a secondary brand (e.g. "rick owens dr. martens") are
# collab pairs. Sellers on Vinted/Poshmark keyword-stuff luxury names into plain
# listings (e.g. regular Dr. Martens titled "Rick Owens x Dr. Martens").
# Guards: (1) price floor — listing must be ≥ 30% of market avg to be credible,
#          (2) model word check — at least one collab-specific model word must
#             appear in the title on non-Grailed platforms.
COLLAB_SECONDARY_BRANDS = {
    "dr. martens", "dr martens", "martens", "adidas", "new balance",
    "converse", "vans", "clarks", "nike", "reebok", "birkenstock",
}
COLLAB_FLOOR_RATIO = 0.30  # listing must be ≥ 30% of market avg

# Known model identifiers for each collab partner — at least one must appear
# in the title on non-Grailed platforms, or the listing is rejected.
COLLAB_MODEL_WORDS: dict[str, set[str]] = {
    "martens": {"turbowpn", "bogun", "sawcut", "1918", "rubs", "tractor", "1460 ro"},
    "adidas":  {"ozweego", "response trail", "stan smith", "samba", "response"},
    "vans":    {"sk8", "authentic", "era"},
    "new balance": {"1906", "2002", "rc_elite"},
}

# ── Implausible gap hard cap ──────────────────────────────────────────────────
# A listing >90% below a $200+ market price is almost certainly a wrong match
# (keyword stuffing, different item entirely) rather than a real arbitrage deal.
IMPLAUSIBLE_GAP_CAP = 0.90          # reject if gap exceeds this
IMPLAUSIBLE_GAP_MIN_MARKET = 200.0  # only apply when market median is meaningful

STATE_FILE = os.path.join(os.path.dirname(__file__), "data", "gap_state.json")
SOLD_CACHE_FILE = os.path.join(os.path.dirname(__file__), "data", "sold_cache.json")
SOLD_CACHE_TTL = 1800  # 30 min — balances freshness vs Grailed rate limits
MAX_COMP_AGE_DAYS = 180  # Only use sold comps from the last 6 months

# ── Platform price discount factors ──
# Grailed buyers pay a premium. Items on other platforms naturally sell for less.
# We adjust the "market price" baseline when the SOURCE item comes from a cheaper platform.
PLATFORM_PRICE_DISCOUNT = {
    "grailed": 1.0,       # Baseline — comps come from here
    "ebay": 0.85,         # eBay items sell ~15% below Grailed
    "poshmark": 0.75,     # Poshmark ~25% below
    "mercari": 0.70,      # Mercari ~30% below
    "depop": 0.80,        # Depop ~20% below
    "vinted": 0.65,       # Vinted ~35% below (buyer pays fees)
    # shopgoodwill removed
}
BLOCKLIST_FILE = os.path.join(os.path.dirname(__file__), "data", "seller_blocklist.json")
IMAGE_HASHES_FILE = os.path.join(os.path.dirname(__file__), "data", "image_hashes.json")

# ── Commonly-faked brands: skip Depop results for these ──
# Depop does not verify items and is a high-risk platform for replicas of these brands.
DEPOP_SKIP_BRANDS: set[str] = {
    "chrome hearts",
    "rick owens",
    "raf simons",
    "enfants riches deprimes",
    "erd",
    "dior",
    "dior homme",
    "vivienne westwood",
    "number nine",
    "undercover",
    "helmut lang",
    "maison margiela",
    "gaultier",
    "jean paul gaultier",
    "balenciaga",
    "saint laurent",
    "prada",
    "bottega veneta",
    "supreme",
    "bape",
    "amiri",
    "stone island",
    "vetements",
    "gallery dept",
    "acronym",
    "needles",
    "alyx",
    "gucci",
    "versace",
    "givenchy",
    "burberry",
}

# ── Minimum believable authentic prices per brand+category ──
REP_PRICE_CEILINGS = {
    "chrome hearts": {
        "trucker hat": 350,
        "cross pendant": 300,
        "dagger pendant": 300,
        "floral cross": 350,
        "cross ring": 250,
        "ring": 200,
        "bracelet": 400,
        "necklace": 250,
        "chain": 300,
        "leather jacket": 2500,
        "denim jacket": 1000,
        "eyewear": 300,
        "hoodie": 400,
        "cemetery": 500,
    },
    "rick owens": {
        "geobasket": 300,
        "ramones": 250,
        "dunks": 300,
        "leather jacket": 600,
        "stooges": 700,
        "kiss boots": 350,
        "intarsia": 200,
        "bauhaus": 150,
        "vans": 230,           # RO x Vans heavily repped — authentic resale floor ~$150-180
    },
    "raf simons": {
        "bomber jacket": 400,
        "riot": 800,
        "ozweego": 100,
        "virginia creeper": 300,
        "peter saville": 250,
    },
    "enfants riches deprimes": {
        "hoodie": 450,
        "jacket": 500,
        "tee": 200,
        "t-shirt": 200,
        "jeans": 300,
        "pants": 300,
        "sweater": 350,
        "hat": 150,
        "cap": 150,
    },
    "erd": {
        "hoodie": 450,
        "jacket": 500,
        "tee": 200,
        "t-shirt": 200,
    },
    "dior": {
        "boots": 200,
        "leather jacket": 500,
        "sneakers": 200,
        "derby": 200,
        "shoes": 200,
        "navigate": 300,
    },
    "dior homme": {
        "boots": 200,
        "leather jacket": 500,
        "sneakers": 200,
        "derby": 200,
        "shoes": 200,
        "navigate": 300,
    },
    "vivienne westwood": {
        "orb necklace": 80,
        "pearl necklace": 100,
        "pearl choker": 100,
        "necklace": 60,
        "armor ring": 60,
        "ring": 50,
        "pendant": 50,
        "earring": 40,
        "bracelet": 60,
        "choker": 80,
        "bag": 100,
        "wallet": 80,
    },
    "number nine": {
        "skull": 300,
        "leather jacket": 400,
    },
    "undercover": {
        "scab": 400,
        "bomber": 250,
        "leather jacket": 350,
    },
    "helmut lang": {
        "bondage": 150,
        "astro": 200,
        "leather jacket": 150,
        "flak jacket": 300,
    },
    "maison margiela": {
        "tabi": 200,
        "artisanal": 300,
    },
    "dior homme": {
        "leather jacket": 500,
        "navigate": 300,
    },
    "gaultier": {
        "mesh": 80,
        "corset": 200,
        "cyberbaba": 150,
    },
    # ── New brands ──
    "balenciaga": {
        "triple s": 200,
        "track": 150,
        "speed": 100,
        "cargo": 100,
        "leather jacket": 400,
    },
    "saint laurent": {
        "wyatt": 200,
        "leather jacket": 300,
        "teddy": 300,
        "court classic": 100,
    },
    "prada": {
        "americas cup": 100,
        "cloudbust": 100,
        "nylon bag": 80,
        "linea rossa": 80,
    },
    "bottega veneta": {
        "puddle": 100,
        "tire boots": 150,
        "cassette": 150,
    },
    "supreme": {
        "box logo": 200,      # Heavily repped
        "north face": 150,
        "leather jacket": 300,
    },
    "bape": {
        "shark hoodie": 100,   # Extremely heavily repped
        "bape sta": 80,
    },
    "amiri": {
        "mx1": 150,
        "leather jacket": 300,
        "bones": 80,
    },
    "stone island": {
        "shadow project": 100,
        "ghost": 80,
        "ice jacket": 150,
    },
    "vetements": {
        "hoodie": 150,
        "bomber": 200,
    },
    "gallery dept": {
        "flared": 100,
        "painted": 80,
    },
    "acronym": {
        "j1a": 300,
        "p10": 150,
    },
    "needles": {
        "track pants": 50,
        "rebuild": 40,
    },
    "alyx": {
        "chest rig": 40,
        "rollercoaster belt": 30,
    },
}


@dataclass
class SoldData:
    query: str
    avg_price: float
    median_price: float
    min_price: float
    max_price: float
    count: int
    timestamp: float
    avg_days_to_sell: float = 0.0  # Average days from listed to sold (lower = more liquid)


@dataclass
class GapDeal:
    item: ScrapedItem
    sold_avg: float
    gap_percent: float
    profit_estimate: float
    sold_count: int
    query: str


class GapHunter:
    """Find items listed significantly below proven sold prices."""

    def __init__(self):
        self.auth = AuthenticityCheckerV2()
        self.seen_ids: set = set()
        self.sold_cache: Dict[str, SoldData] = {}
        self.cycle_count = 0
        self.stats = defaultdict(int)
        self.running = True
        self.seller_blocklist: set = set()
        self.seller_block_counts: Dict[str, int] = {}  # seller -> auth_block count
        self.image_hashes: Dict[str, List[Dict]] = {}  # hash -> list of {seller, url, title}
        self._fx_cache: Dict[str, tuple] = {}  # currency -> (rate, timestamp)
        self._load_state()
        self._load_sold_cache()
        self._load_blocklist()
        self._load_image_hashes()

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        logger.info("Shutting down...")
        self.running = False
        # Playwright cleanup happens in run() after the loop exits

    def _load_state(self):
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE) as f:
                    data = json.load(f)
                    self.seen_ids = set(data.get("seen_ids", []))
                    self.cycle_count = data.get("cycle_count", 0)
        except Exception:
            pass

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            ids = list(self.seen_ids)[-50000:]
            with open(STATE_FILE, "w") as f:
                json.dump({"seen_ids": ids, "cycle_count": self.cycle_count}, f)
        except Exception:
            pass

    def _get_fx_rate(self, currency: str) -> Optional[float]:
        """Return live USD conversion rate for the given currency. Cached 1h."""
        import urllib.request
        FX_TTL = 3600
        cached = self._fx_cache.get(currency)
        if cached and time.time() - cached[1] < FX_TTL:
            return cached[0]
        # Hardcoded fallbacks in case the API is unreachable
        fallbacks = {"EUR": 1.08, "GBP": 1.27, "JPY": 0.0067, "CAD": 0.74,
                     "AUD": 0.63, "CHF": 1.11, "SEK": 0.094, "DKK": 0.144,
                     "NOK": 0.091, "PLN": 0.25, "CZK": 0.044, "HUF": 0.0027,
                     "RON": 0.22, "BGN": 0.55, "TWD": 0.031, "HKD": 0.13}
        try:
            url = f"https://open.er-api.com/v6/latest/USD"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = __import__("json").loads(resp.read())
            rates = data.get("rates", {})
            # rates are X per 1 USD — invert to get USD per X
            if currency in rates and rates[currency]:
                rate = 1.0 / rates[currency]
                self._fx_cache[currency] = (rate, time.time())
                logger.debug(f"FX rate {currency}→USD: {rate:.4f}")
                return rate
        except Exception as e:
            logger.debug(f"FX rate fetch failed ({currency}): {e} — using fallback")
        rate = fallbacks.get(currency)
        if rate:
            self._fx_cache[currency] = (rate, time.time())
        return rate

    def _load_sold_cache(self):
        try:
            if os.path.exists(SOLD_CACHE_FILE):
                with open(SOLD_CACHE_FILE) as f:
                    raw = json.load(f)
                    for k, v in raw.items():
                        if time.time() - v.get("timestamp", 0) < SOLD_CACHE_TTL:
                            self.sold_cache[k] = SoldData(**v)
        except Exception:
            pass

    def _save_sold_cache(self):
        try:
            os.makedirs(os.path.dirname(SOLD_CACHE_FILE), exist_ok=True)
            raw = {}
            for k, v in self.sold_cache.items():
                raw[k] = {
                    "query": v.query, "avg_price": v.avg_price,
                    "median_price": v.median_price, "min_price": v.min_price,
                    "max_price": v.max_price, "count": v.count,
                    "timestamp": v.timestamp,
                    "avg_days_to_sell": v.avg_days_to_sell,
                }
            with open(SOLD_CACHE_FILE, "w") as f:
                json.dump(raw, f)
        except Exception:
            pass

    def _load_blocklist(self):
        try:
            if os.path.exists(BLOCKLIST_FILE):
                with open(BLOCKLIST_FILE) as f:
                    data = json.load(f)
                    self.seller_blocklist = set(data.get("blocklist", []))
                    self.seller_block_counts = data.get("block_counts", {})
        except Exception:
            pass

    def _save_blocklist(self):
        try:
            os.makedirs(os.path.dirname(BLOCKLIST_FILE), exist_ok=True)
            with open(BLOCKLIST_FILE, "w") as f:
                json.dump({
                    "blocklist": list(self.seller_blocklist),
                    "block_counts": self.seller_block_counts,
                }, f, indent=2)
        except Exception:
            pass

    def _load_image_hashes(self):
        try:
            if os.path.exists(IMAGE_HASHES_FILE):
                with open(IMAGE_HASHES_FILE) as f:
                    self.image_hashes = json.load(f)
        except Exception:
            pass

    def _save_image_hashes(self):
        try:
            os.makedirs(os.path.dirname(IMAGE_HASHES_FILE), exist_ok=True)
            with open(IMAGE_HASHES_FILE, "w") as f:
                json.dump(self.image_hashes, f, indent=2)
        except Exception:
            pass

    async def _get_image_hash(self, image_url: str) -> Optional[str]:
        """Get perceptual hash of first image. Returns hash string or None."""
        if not HAS_IMAGE_LIBS or not image_url:
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(image_url)
                if response.status_code != 200:
                    return None

                # Create PIL Image from bytes
                image = Image.open(io.BytesIO(response.content))
                # Convert to RGB if needed (handles RGBA, etc)
                if image.mode != 'RGB':
                    image = image.convert('RGB')

                # Get perceptual hash (8x8 default, good balance of speed/accuracy)
                phash = imagehash.phash(image)
                return str(phash)
        except Exception as e:
            logger.debug(f"Image hash failed for {image_url}: {e}")
            return None

    def _check_image_duplicates(self, image_hash: str, seller: str, item_url: str, title: str) -> bool:
        """Check if image appears across multiple sellers. Return True if likely rep."""
        if not image_hash:
            return False

        # Add this listing to the hash registry
        if image_hash not in self.image_hashes:
            self.image_hashes[image_hash] = []

        # Check if we already have this seller for this hash (avoid double counting)
        existing_sellers = {entry.get("seller", "").lower() for entry in self.image_hashes[image_hash]}
        current_seller_lower = seller.lower() if seller else ""

        if current_seller_lower not in existing_sellers:
            self.image_hashes[image_hash].append({
                "seller": seller or "unknown",
                "url": item_url,
                "title": title[:100],  # Truncate for storage
            })

        # Count unique sellers for this hash
        unique_sellers = len({entry.get("seller", "").lower() for entry in self.image_hashes[image_hash]})

        # Flag as rep if same image appears across 3+ different sellers
        if unique_sellers >= 3:
            logger.warning(f"🔴 Image duplicate detected: hash {image_hash[:8]}... appears across {unique_sellers} sellers")
            return True

        return False

    def _record_auth_block(self, seller: str):
        """Track auth blocks per seller; auto-blocklist after 3."""
        if not seller:
            return
        key = seller.lower().strip()
        self.seller_block_counts[key] = self.seller_block_counts.get(key, 0) + 1
        if self.seller_block_counts[key] >= 3 and key not in self.seller_blocklist:
            self.seller_blocklist.add(key)
            logger.warning(f"🚫 Auto-blocklisted seller '{seller}' (auth_blocked {self.seller_block_counts[key]}x)")
            self._save_blocklist()

    # ── Women's / non-menswear keywords ──
    WOMENS_KEYWORDS = [
        "women's", "womens", "women ", "woman's",
        "ladies", "lady's",
        " her ", " she ",
        "maternity",
        "women's size", "womens size",
    ]
    # Explicit women's sizing patterns (won't match "Size M" etc.)
    WOMENS_SIZE_PATTERNS = [
        "size 0 ", "size 00 ", "size 2 ", "size 4 ", "size 6 ", "size 8 ",
        " 0p ", " 2p ", " 4p ", " 6p ", " 8p ",
        "size 0,", "size 2,", "size 4,", "size 6,",
    ]
    # Women's specific categories/garment types
    WOMENS_CATEGORIES = [
        "bralette", "sports bra", "bikini", "tankini",
        "midi dress", "maxi dress", "wrap dress", "bodycon",
        "women's jacket", "womens jacket",
        "women's coat", "womens coat",
        "women's blazer", "womens blazer",
        "women's pants", "womens pants",
        "women's shoe", "womens shoe",
        "women's boot", "womens boot",
        "women's sneaker", "womens sneaker",
        "pump", "stiletto", "kitten heel",
        "pencil skirt", "a-line skirt",
    ]
    # Items that look women's but are actually unisex/men's archive
    # Use \b word boundary via regex to avoid "womens" matching "mens"
    WOMENS_EXCEPTIONS_EXACT = [
        "homme", "pour homme",
        "gaultier",  # JPG mesh tops are unisex
        "play comme",  # CDG Play is unisex
    ]

    def _is_womens_item(self, item) -> bool:
        """Return True if item appears to be women's clothing (not menswear)."""
        import re
        title = (item.title or "").lower()
        desc = (getattr(item, "description", "") or "").lower()
        text = f"{title} {desc}"
        # Normalize curly quotes/apostrophes to straight
        text = text.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')

        # Check exceptions first — these are NOT women's even if keywords match
        for exc in self.WOMENS_EXCEPTIONS_EXACT:
            if exc in text:
                return False
        # Word-boundary check for "men's" / "mens" (avoid matching inside "womens")
        if re.search(r"\bmen'?s\b", text) and not re.search(r"\bwomen", text):
            return False
        # "tabi" is unisex — only skip if it's clearly a tabi item
        if "tabi" in text and "women" not in text:
            return False

        # Check explicit women's keywords
        for kw in self.WOMENS_KEYWORDS:
            if kw in text:
                return True

        # Check women's categories
        for cat in self.WOMENS_CATEGORIES:
            if cat in text:
                return True

        # Check women's sizing (be careful — "Size 8" could be shoe size)
        # Only flag if it also says "women" nearby or is a non-shoe item
        for pat in self.WOMENS_SIZE_PATTERNS:
            if pat in text and "shoe" not in text and "sneaker" not in text and "boot" not in text:
                return True

        return False

    # Items we never alert on regardless of brand or gap
    EXCLUDED_CATEGORY_KEYWORDS = [
        # Fragrances
        "fragrance", "cologne", "perfume", "eau de toilette", "eau de parfum",
        "edt", "edp", "aftershave", "deodorant", "body spray", "mist",
        # Ties & neckwear
        "bow tie", "bowtie", "bow-tie", "necktie", "tie clip", "bolo tie",
        # Ties (word boundary check handled separately to avoid "tie-dye", "katie", etc.)
        # Bags — common, low-margin
        "drawstring backpack", "drawstring bag",
        "tote bag",
    ]

    # These contain "tie" but are NOT neckwear — don't exclude them
    TIE_EXCEPTIONS = [
        "tie-dye", "tie dye", "tiedye", "bootie", "hoodie", "beanie",
        "tee", "katie", "tie waist",  # tie-waist trousers are clothing
        "ankle tie", "lace tie", "string tie",  # drawstrings on clothing
    ]

    def _is_excluded_category(self, item) -> bool:
        """Return True if item is a fragrance, tie, or other excluded category."""
        title = (item.title or "").lower()
        desc = (getattr(item, "description", "") or "").lower()
        text = f"{title} {desc}"

        # Check hard-excluded keywords
        for kw in self.EXCLUDED_CATEGORY_KEYWORDS:
            if kw in text:
                return True

        # "tie" check with exceptions — standalone tie/ties = neckwear
        import re
        if re.search(r'\btie[s]?\b', text):
            # Allow if any exception phrase is present
            if not any(exc in text for exc in self.TIE_EXCEPTIONS):
                return True

        return False

    def _check_rep_price_ceiling(self, query: str, price: float, title: str = "") -> bool:
        """Return True if price is below rep ceiling (likely fake).
        Brand must appear in the item TITLE (not just query) to avoid false positives
        on irrelevant Poshmark results. Category can match query or title."""
        import unicodedata
        def _normalize(s):
            """Strip accents and lowercase for matching."""
            return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')

        query_lower = _normalize(query)
        title_lower = _normalize(title) if title else ""
        for brand, categories in REP_PRICE_CEILINGS.items():
            # Brand MUST be in the title to confirm the item is actually this brand
            if _normalize(brand) not in title_lower:
                continue
            # Category can match in either query or title
            search_text = f"{query_lower} {title_lower}"
            for category, ceiling in categories.items():
                if category in search_text:
                    if price < ceiling:
                        return True
        return False

    async def get_sold_data(self, query: str) -> Optional[SoldData]:
        """Get sold price data for a query, using cache when available."""
        if query in self.sold_cache:
            cached = self.sold_cache[query]
            if time.time() - cached.timestamp < SOLD_CACHE_TTL:
                return cached

        try:
            async with GrailedScraper() as scraper:
                sold = await scraper.search_sold(query, max_results=30)  # Fetch more to account for filtering

            if not sold:
                return None

            # ── Temporal filtering: only use comps from last MAX_COMP_AGE_DAYS ──
            from datetime import datetime as _dt, timedelta, timezone
            now = _dt.now(timezone.utc)
            cutoff = now - timedelta(days=MAX_COMP_AGE_DAYS)
            fresh_sold = []
            stale_count = 0
            for s in sold:
                created_str = (s.raw_data or {}).get("created_at") or (s.raw_data or {}).get("sold_at")
                if created_str:
                    try:
                        comp_date = _dt.fromisoformat(created_str.replace("Z", "+00:00"))
                        if comp_date < cutoff:
                            stale_count += 1
                            continue
                    except (ValueError, TypeError):
                        pass  # Keep items with unparseable dates
                fresh_sold.append(s)

            if stale_count > 0:
                logger.debug(f"  Filtered out {stale_count} stale comps (>{MAX_COMP_AGE_DAYS}d) for '{query}'")

            # Require minimum fresh comps; stale fallback removed — no niche exceptions
            if len(fresh_sold) >= MIN_SOLD_COMPS:
                sold = fresh_sold
            else:
                # Not enough fresh comps — skip this query entirely
                return None

            if len(sold) < MIN_SOLD_COMPS:
                return None

            prices = sorted([i.price for i in sold if i.price and i.price > 0])
            if len(prices) < MIN_SOLD_COMPS:
                return None

            # ── Filter out suspiciously low sold comps (likely reps) ──
            if len(prices) >= 3:
                initial_median = prices[len(prices) // 2]
                threshold = initial_median * 0.20
                filtered_prices = [p for p in prices if p >= threshold]
                if len(filtered_prices) >= MIN_SOLD_COMPS:
                    if len(prices) != len(filtered_prices):
                        logger.debug(f"  Filtered out {len(prices) - len(filtered_prices)} suspiciously low sold comps for '{query}'")
                    prices = filtered_prices

            # ── Remove outliers (top/bottom 10%) ──
            if len(prices) > 5:
                trim = max(1, len(prices) // 10)
                prices = prices[trim:-trim]

            # ── Calculate average days-to-sell from sold comps ──
            days_to_sell_list = []
            for s in sold:
                rd = s.raw_data or {}
                created_str = rd.get("created_at")
                sold_str = rd.get("sold_at")
                if created_str and sold_str:
                    try:
                        created = _dt.fromisoformat(created_str.replace("Z", "+00:00"))
                        sold_dt = _dt.fromisoformat(sold_str.replace("Z", "+00:00"))
                        days = max(0, (sold_dt - created).total_seconds() / 86400)
                        if days < 365:
                            days_to_sell_list.append(days)
                    except (ValueError, TypeError):
                        pass
            avg_days = sum(days_to_sell_list) / len(days_to_sell_list) if days_to_sell_list else 0.0

            # ── Comp confidence based on count (minimum is now 20, so low tier is gone) ──
            comp_confidence = "high" if len(prices) >= 20 else "medium"

            data = SoldData(
                query=query,
                avg_price=sum(prices) / len(prices),
                median_price=prices[len(prices) // 2],
                min_price=min(prices),
                max_price=max(prices),
                count=len(prices),
                timestamp=time.time(),
                avg_days_to_sell=avg_days,
            )
            # Store confidence on the SoldData (not in dataclass but accessible)
            data._confidence = comp_confidence

            self.sold_cache[query] = data
            return data

        except Exception as e:
            logger.debug(f"Sold data failed for '{query}': {e}")
            return None

    async def find_gaps(self, query: str, sold_data: SoldData) -> List[GapDeal]:
        """Find active listings priced below sold average."""
        deals = []

        # ── Parallel scraping across all platforms ──
        async def _grailed():
            try:
                async with GrailedScraper() as scraper:
                    return await scraper.search(query, max_results=15)
            except Exception:
                return []

        async def _poshmark():
            try:
                async with PoshmarkScraper() as scraper:
                    return await scraper.search(query, max_results=15)
            except Exception:
                return []

        async def _depop():
            try:
                if not hasattr(self, '_depop_scraper'):
                    self._depop_scraper = DepopScraper()
                return await asyncio.wait_for(self._depop_scraper.search(query, max_results=15), timeout=30.0)
            except asyncio.TimeoutError:
                logger.debug(f"    Depop timed out for '{query}'")
                return []
            except Exception as e:
                logger.debug(f"    Depop search failed: {e}")
                return []

        async def _vinted():
            try:
                if not hasattr(self, '_vinted'):
                    self._vinted = VintedScraper()
                return await self._vinted.search(query, max_results=10)
            except Exception as e:
                logger.debug(f"    Vinted search failed: {e}")
                return []

        async def _ebay():
            try:
                if not hasattr(self, '_ebay'):
                    self._ebay = EbayScraper()
                return await asyncio.wait_for(self._ebay.search(query, max_results=15), timeout=15.0)
            except asyncio.TimeoutError:
                logger.debug(f"    eBay timed out for '{query}'")
                return []
            except Exception as e:
                logger.debug(f"    eBay search failed: {e}")
                return []

        # ── Chrome Hearts: Grailed-only, new listings only ──
        # CH fakes flood Poshmark/Mercari/Vinted; Grailed has purchase verification.
        # Only surface listings posted in the last 30 minutes to catch fresh drops.
        is_chrome_hearts = "chrome hearts" in query.lower()

        if is_chrome_hearts:
            grailed_items = await _grailed()
            results_list = [grailed_items, [], [], [], []]
            logger.info(f"  [CH] Grailed-only mode: {len(grailed_items)} raw results")
        else:
            results_list = await asyncio.gather(_grailed(), _poshmark(), _depop(), _vinted(), _ebay())

        all_items = [item for sublist in results_list for item in sublist]

        # Chrome Hearts recency gate: skip anything listed > 30 minutes ago
        if is_chrome_hearts:
            from datetime import datetime as _dt, timezone
            now_utc = _dt.now(timezone.utc)
            fresh = []
            for item in all_items:
                if item.listed_at is None:
                    logger.debug(f"  [CH] No listing timestamp, skipping: {item.title[:50]}")
                    continue
                age_mins = (now_utc - item.listed_at).total_seconds() / 60
                if age_mins <= 30:
                    fresh.append(item)
                else:
                    logger.debug(f"  [CH] Too old ({age_mins:.0f}m), skipping: {item.title[:50]}")
            logger.info(f"  [CH] {len(fresh)}/{len(all_items)} listings within 30 minutes")
            all_items = fresh

        for item in all_items:
            item_key = f"{item.source}:{item.source_id or item.url}"
            if item_key in self.seen_ids:
                continue
            self.seen_ids.add(item_key)

            if not item.price or item.price <= 0:
                continue

            # ── Depop: skip commonly-faked brands (no authentication) ──
            if item.source == "depop":
                _title_lower = (item.title or "").lower()
                _query_lower = query.lower()
                if any(brand in _title_lower or brand in _query_lower for brand in DEPOP_SKIP_BRANDS):
                    logger.debug(f"    🚫 Depop skip (commonly faked brand): {item.title[:60]}")
                    self.stats["depop_fake_brand_skipped"] = self.stats.get("depop_fake_brand_skipped", 0) + 1
                    continue

            # ── Currency conversion → USD (live rates, cached 1h) ──
            item_currency = getattr(item, 'currency', 'USD')
            if item_currency != 'USD':
                rate = self._get_fx_rate(item_currency)
                if rate:
                    item.price = round(item.price * rate, 2)
                item.currency = 'USD'


            # ── Women's / non-menswear filter ──
            if self._is_womens_item(item):
                logger.debug(f"    Skipped women's item: {item.title[:50]}")
                self.stats["womens_skipped"] += 1
                continue

            if self._is_excluded_category(item):
                logger.debug(f"    Skipped excluded category (fragrance/tie): {item.title[:50]}")
                self.stats.setdefault("category_filtered", 0)
                self.stats["category_filtered"] += 1
                continue

            # ── Seller blocklist check ──
            if item.seller and item.seller.lower().strip() in self.seller_blocklist:
                logger.debug(f"    Skipped blocklisted seller: {item.seller}")
                self.stats["blocklist_skipped"] += 1
                continue

            # ── Seller trust filter (Fix 1) ──
            seller_sales = getattr(item, "seller_sales", None)
            if item.source == "grailed" and seller_sales is not None and seller_sales < 5:
                logger.info(f"    ⚠️ Low-trust seller '{item.seller}' ({seller_sales} sales) - skipping: {item.title[:50]}")
                self.stats["low_trust_skipped"] += 1
                continue
            # Penalty for unknown seller_sales handled in process_deal auth scoring

            # ── High-rep collab filter: Rick Owens x Vans ──
            # These are so heavily repped that we require stricter seller trust
            title_lower = (item.title or "").lower()
            if "rick owens" in title_lower and "vans" in title_lower:
                # Require minimum seller history for RO Vans
                min_sales = 10 if item.source == "grailed" else 5
                if seller_sales is not None and seller_sales < min_sales:
                    logger.info(f"    🚫 RO x Vans from low-trust seller '{item.seller}' ({seller_sales} sales) - high rep risk: {item.title[:50]}")
                    self.stats["ro_vans_rep_skipped"] = self.stats.get("ro_vans_rep_skipped", 0) + 1
                    continue
                # Also flag if price is suspiciously in the "too good to be true" zone
                # Authentic RO Vans resale: median $245, rarely below $150
                if item.price < 150:
                    logger.info(f"    🚫 RO x Vans at ${item.price:.0f} — below authentic floor ($150): {item.title[:50]}")
                    self.stats["ro_vans_rep_skipped"] = self.stats.get("ro_vans_rep_skipped", 0) + 1
                    continue

            # ── Rep price ceiling check (Fix 3) ──
            if self._check_rep_price_ceiling(query, item.price, item.title):
                logger.info(f"    🚫 Below rep price ceiling — likely fake: ${item.price:.0f} for '{query}' — {item.title[:60]}")
                self.stats["rep_ceiling_skipped"] += 1
                continue

            # ── Collab listing credibility floor ─────────────────────────────
            # For queries containing a secondary brand (e.g. "rick owens dr. martens"),
            # require listing price ≥ 30% of market median. Keyword-stuffed plain
            # Dr. Martens / Adidas / etc. are almost always priced far below the
            # real collab market, so this catches them cleanly.
            query_lower_collab = query.lower()
            collab_secondary = next(
                (s for s in COLLAB_SECONDARY_BRANDS if s in query_lower_collab), None
            )
            if collab_secondary:
                collab_floor = sold_data.median_price * COLLAB_FLOOR_RATIO
                if item.price < collab_floor:
                    logger.info(
                        f"    🚫 Collab floor: ${item.price:.0f} < ${collab_floor:.0f} "
                        f"(30% of ${sold_data.median_price:.0f} market) — likely keyword-stuffed "
                        f"'{collab_secondary}': {item.title[:50]}"
                    )
                    self.stats.setdefault("collab_floor_skipped", 0)
                    self.stats["collab_floor_skipped"] += 1
                    continue

                # Fix 3 — model word check on non-Grailed platforms:
                # At least one collab-specific model word must appear in the title.
                # Grailed is exempt (purchase verification makes fakes less likely).
                collab_key = next(
                    (k for k in COLLAB_MODEL_WORDS if k in query_lower_collab), None
                )
                if collab_key and item.source != "grailed":
                    model_words = COLLAB_MODEL_WORDS[collab_key]
                    title_lower_collab = item.title.lower()
                    has_model = any(mw in title_lower_collab for mw in model_words)
                    if not has_model:
                        logger.info(
                            f"    🚫 Collab model word missing for '{collab_key}' "
                            f"on {item.source} — likely generic: {item.title[:50]}"
                        )
                        self.stats.setdefault("collab_model_skipped", 0)
                        self.stats["collab_model_skipped"] += 1
                        continue

            # ── Image fingerprint deduplication (Day 2 Fix 1) ──
            if item.images:
                image_hash = await self._get_image_hash(item.images[0])
                if image_hash and self._check_image_duplicates(image_hash, item.seller, item.url, item.title):
                    logger.info(f"    🔴 Image duplicate detected - likely rep: {item.title[:50]}")
                    self.stats["image_dup_skipped"] += 1
                    continue

            # CRITICAL: Verify the item actually matches the brand/query
            # Day 2 Fix 4: Strengthen brand matching for Poshmark relevance
            query_words = query.lower().split()
            title_lower_check = item.title.lower()

            # Brand name must appear in title (first 1-2 words of query = brand)
            # e.g., "rick owens" from "rick owens geobasket", "gaultier" from "gaultier mesh top"
            brand_words = query_words[:2] if len(query_words) >= 2 else query_words[:1]
            brand_in_title = any(bw in title_lower_check for bw in brand_words)
            if not brand_in_title:
                continue

            # Require at least 2 query words to appear in the title (not just 1 brand word)
            matching_words = sum(1 for word in query_words if word in title_lower_check)
            if matching_words < 2:
                logger.debug(f"    Skipped poor match: only {matching_words}/2+ words match for '{query}' - {item.title[:50]}")
                continue

            # Add minimum title similarity check - at least 40% of query words should match
            similarity_ratio = matching_words / len(query_words)
            if similarity_ratio < 0.40:
                logger.debug(f"    Skipped low similarity: {similarity_ratio:.0%} for '{query}' - {item.title[:50]}")
                continue

            # ── Qualifier word check ──
            # For searches with specific qualifiers (hedi, archive, homme, slimane, etc.),
            # at least one qualifier must appear in the title. This prevents
            # "dior homme hedi jacket" matching a generic "Dior suit jacket".
            QUALIFIER_WORDS = {
                "hedi", "slimane", "homme", "archive", "vintage", "artisanal",
                "bondage", "navigate", "riot", "consumed", "scab", "cyberbaba",
                "tabi", "gat", "replica", "stooges", "geobasket", "ramones",
                "dustulator", "astro", "flak", "painter", "skull", "soloist",
                "mesh", "tattoo", "orb", "plisse", "plissé", "pour homme",
                "homme plus", "junya", "martin",
            }
            query_qualifiers = [w for w in query_words if w in QUALIFIER_WORDS]
            if query_qualifiers:
                has_qualifier = any(q in title_lower_check for q in query_qualifiers)
                if not has_qualifier:
                    logger.debug(f"    Skipped missing qualifier: need one of {query_qualifiers} in title - {item.title[:50]}")
                    continue

            # Check instant reject
            title_lower = item.title.lower()
            rejected = False
            for pattern in REJECT_PATTERNS:
                if pattern.search(title_lower):
                    rejected = True
                    break
            if rejected:
                continue

            # ── Listing age check ──
            # Stale listings (>30 days old) indicate the item isn't liquid
            if item.listed_at:
                from datetime import datetime, timezone
                listing_age_days = (datetime.now(timezone.utc) - item.listed_at).days
                if listing_age_days > 10:
                    logger.debug(f"    Skipped stale listing ({listing_age_days}d old): {item.title[:50]}")
                    self.stats.setdefault("stale_skipped", 0)
                    self.stats["stale_skipped"] += 1
                    continue

            # ── Price drop check (Grailed only) ──
            # Multiple price drops = seller struggling to sell = not liquid
            price_drops = (item.raw_data or {}).get("price_drops", [])
            if len(price_drops) >= 3:
                logger.debug(f"    Skipped {len(price_drops)} price drops (struggling to sell): {item.title[:50]}")
                self.stats.setdefault("price_drop_skipped", 0)
                self.stats["price_drop_skipped"] += 1
                continue

            # ── Low photo count check ──
            # Legitimate sellers of real archive pieces take detailed photos
            photo_count = (item.raw_data or {}).get("photo_count", 0)
            if photo_count > 0 and photo_count < 4:
                logger.debug(f"    Skipped low photos ({photo_count}): {item.title[:50]}")
                continue

            # ── Brand whitelist ──
            # Only allow items from brands we actually track. Prevents random
            # Poshmark results (Lululemon, Harley Davidson, etc.) from leaking through.
            detected_brand = self._detect_brand(item.title)
            if not detected_brand:
                logger.debug(f"    Skipped unknown brand: {item.title[:50]}")
                continue

            # Calculate gap with platform price adjustment
            # Grailed sold median is our baseline, but items on cheaper platforms
            # naturally sell for less. Adjust the reference to avoid phantom profit.
            platform_discount = PLATFORM_PRICE_DISCOUNT.get(item.source, 0.80)
            adjusted_reference = sold_data.median_price * platform_discount
            gap = adjusted_reference - item.price
            gap_percent = gap / adjusted_reference if adjusted_reference > 0 else 0

            # Profit estimate: assume selling on Grailed (~12% total fees) + shipping
            sell_price = sold_data.median_price * 0.88  # After Grailed fees + PayPal
            profit = sell_price - item.price - 15  # $15 estimated shipping
            real_margin = profit / item.price if item.price > 0 else 0

            # ── Implausible gap sanity check ──────────────────────────────────
            # A listing >90% below a $200+ market is virtually never a real deal —
            # it's a wrong match (keyword stuffing, different category entirely).
            # Both the $13 Dr. Martens and extreme Vinted outliers are caught here.
            if gap_percent >= IMPLAUSIBLE_GAP_CAP and sold_data.median_price >= IMPLAUSIBLE_GAP_MIN_MARKET:
                logger.info(
                    f"    🚫 Implausible gap {gap_percent*100:.0f}% on ${sold_data.median_price:.0f} market "
                    f"(listed ${item.price:.0f}) — likely wrong match: {item.title[:50]}"
                )
                self.stats.setdefault("implausible_gap_skipped", 0)
                self.stats["implausible_gap_skipped"] += 1
                continue

            # Confidence-gated thresholds: medium (20-19 comps) slightly stricter than high (20+)
            comp_confidence = getattr(sold_data, '_confidence', 'medium')
            effective_min_gap = MIN_GAP_PERCENT
            effective_min_profit = MIN_PROFIT_DOLLARS
            if comp_confidence == "medium":
                effective_min_gap = MIN_GAP_PERCENT * 1.17  # ~35% instead of 30%

            if gap_percent >= effective_min_gap and profit >= effective_min_profit:
                deals.append(GapDeal(
                    item=item,
                    sold_avg=sold_data.avg_price,
                    gap_percent=gap_percent,
                    profit_estimate=profit,
                    sold_count=sold_data.count,
                    query=query,
                ))

        # ── Price clustering detection (Fix 2) ──
        # If 3+ listings priced within $30 of each other AND all below 40% of sold median → rep batch
        if len(deals) >= 3:
            prices = sorted([d.item.price for d in deals])
            threshold_price = sold_data.median_price * 0.40
            cheap_deals = [d for d in deals if d.item.price < threshold_price]
            if len(cheap_deals) >= 3:
                cheap_prices = sorted([d.item.price for d in cheap_deals])
                # Check if they cluster within $30
                for i in range(len(cheap_prices) - 2):
                    window = cheap_prices[i:i+3]
                    if window[-1] - window[0] <= 30:
                        logger.warning(
                            f"    🔴 Rep batch detected for '{query}': {len(cheap_deals)} listings "
                            f"clustered at ${cheap_prices[0]:.0f}-${cheap_prices[-1]:.0f} "
                            f"(median sold: ${sold_data.median_price:.0f}) - skipping all"
                        )
                        self.stats["rep_batch_skipped"] += len(deals)
                        return []

        return deals

    async def process_deal(self, deal: GapDeal) -> bool:
        """Auth check, quality score, and send a gap deal."""
        item = deal.item
        brand = self._detect_brand(item.title)
        category = self._detect_category(item.title)

        # Auth check
        try:
            auth_result = await asyncio.wait_for(
                self.auth.check(
                    title=item.title,
                    description=item.description or "",
                    price=item.price,
                    brand=brand,
                    category=category,
                    seller_name=item.seller or "",
                    seller_sales=getattr(item, "seller_sales", 0),
                    seller_rating=getattr(item, "seller_rating", None),
                    images=item.images,
                    source=item.source,
                ),
                timeout=20.0,
            )

            if auth_result.action == "block" or auth_result.confidence < MIN_AUTH_SCORE:
                self.stats["auth_blocked"] += 1
                self._record_auth_block(item.seller)
                return False
        except Exception:
            auth_result = None

        # ── Calculate deal quality score ──
        auth_conf = auth_result.confidence if auth_result else 0.5
        quality_score, signals = calculate_deal_quality(
            item=item,
            brand=brand,
            sold_data=deal,
            gap_percent=deal.gap_percent,
            profit=deal.profit_estimate,
            auth_confidence=auth_conf,
        )

        # Quality gate: only send 🔥🔥+ deals (score >= 50)
        min_fire = int(os.getenv("GAP_MIN_FIRE_LEVEL", "2"))
        if signals.fire_level < min_fire:
            logger.info(
                f"    ⏭ Below quality threshold ({quality_score:.0f}/100, fire={signals.fire_level} < {min_fire}): {item.title[:50]}"
            )
            self.stats["quality_filtered"] += 1
            return False

        # Build the alert message with signal breakdown
        header = format_quality_header(signals)
        grade_str = format_auth_grade(auth_result.grade) if auth_result else ""

        # Build title line with season/line info
        title_line = f"<b>{item.title[:80]}</b>"
        subtitle_parts = []
        if signals.line_name and signals.line_name not in ("Unknown", "Mainline"):
            subtitle_parts.append(signals.line_name)
        elif signals.line_name == "Mainline":
            subtitle_parts.append("Mainline")
        if signals.condition_tier != "GENTLY_USED":
            condition_display = signals.condition_tier.replace("_", " ").title()
            subtitle_parts.append(condition_display)
        if signals.detected_size:
            subtitle_parts.append(signals.detected_size)

        msg_lines = [
            header,
            "",
            title_line,
        ]

        if subtitle_parts:
            msg_lines.append(" | ".join(subtitle_parts))

        if signals.season_name and signals.season_multiplier > 1.0:
            msg_lines.append(f"✨ <b>{signals.season_name}</b>")

        msg_lines.extend([
            "",
            f"💵 Listed: <b>${item.price:.0f}</b> on {item.source.title()}"
            + (f" ⏰ auction ends in {getattr(item, '_auction_hours_left', 0):.0f}h" if getattr(item, '_auction_hours_left', None) is not None else ""),
            f"📊 Market: <b>${deal.sold_avg:.0f}</b> ({deal.sold_count} comps, Grailed sold)",
            f"💰 Est. Profit: <b>${deal.profit_estimate:.0f}</b> (after fees + shipping)",
            f"📈 <b>{deal.gap_percent*100:.0f}% below market</b>",
        ])

        # Signal breakdown line
        signal_line = format_signal_line(signals)
        if signal_line:
            msg_lines.append(f"\n{signal_line}")

        if auth_result:
            filled = round(auth_result.confidence * 5)
            bar = "●" * filled + "○" * (5 - filled)
            msg_lines.append(f"🔐 Auth: {bar} {auth_result.confidence*100:.0f}% {grade_str}")

        if item.url:
            msg_lines.append(f"")
            msg_lines.append(f"<a href=\"{item.url}\">🔗 Buy Now</a>")

        message = "\n".join(msg_lines)

        # Send to subscribers + channel
        try:
            subscribers = get_active_subscribers()
            for user in subscribers:
                try:
                    if item.images:
                        from telegram_bot import send_photo
                        await send_photo(user["telegram_id"], item.images[0], message)
                    else:
                        await send_message(user["telegram_id"], message)
                except Exception:
                    pass
                await asyncio.sleep(0.1)

            # Post to channel
            if TELEGRAM_CHANNEL_ID:
                try:
                    if item.images:
                        from telegram_bot import send_photo
                        await send_photo(TELEGRAM_CHANNEL_ID, item.images[0], message)
                    else:
                        await send_message(TELEGRAM_CHANNEL_ID, message)
                except Exception:
                    pass

            # Post to Discord
            if DISCORD_ENABLED:
                try:
                    await send_discord_alert(
                        item=item,
                        message=message,
                        fire_level=signals.fire_level,
                        signals=signals,
                        auth_result=auth_result,
                    )
                except Exception as e:
                    logger.warning(f"Discord alert failed: {e}")

            # Post to Whop
            try:
                whop_title = f"🔥 Gap Deal: {item.title[:60]} | {deal.gap_percent*100:.0f}% below market"
                signal_lines = [
                    f"- Auth confidence: {auth_result.confidence*100:.0f}%" if auth_result else "- Auth confidence: N/A",
                    f"- Fire level: {'🔥' * signals.fire_level}" if signals.fire_level else "- Fire level: —",
                ]
                if signals.season_name:
                    signal_lines.append(f"- Season: {signals.season_name}")
                if signals.line_name and signals.line_name not in ("Unknown",):
                    signal_lines.append(f"- Line: {signals.line_name}")

                whop_content = "\n".join([
                    f"## {item.title}",
                    "",
                    "**💰 The Opportunity**",
                    f"- Listed: **${item.price:.0f}** on {item.source.title()}",
                    f"- Proven sold: **${deal.sold_avg:.0f}** ({deal.sold_count} Grailed comps)",
                    f"- Gap: **{deal.gap_percent*100:.0f}% below market**",
                    f"- Est. profit: **${deal.profit_estimate:.0f}** (after fees + shipping)",
                    "",
                    "**📊 Signals**",
                    *signal_lines,
                    "",
                    f"[View Listing]({item.url})",
                ])
                await asyncio.wait_for(send_whop_alert(whop_title, whop_content), timeout=10.0)
            except Exception as e:
                logger.error(f"Whop alert failed: {e}")

            self.stats["deals_sent"] += 1
            return True
        except Exception as e:
            logger.error(f"Send failed: {e}")
            return False

    async def run_cycle(self, brand_filter=None, custom_queries=None, max_targets=None, source_filter=None):
        """Run one hunting cycle."""
        self.cycle_count += 1
        cycle_start = time.time()

        # ── Dynamic targets: per-cycle varied subset from TrendEngine ──
        # get_cycle_targets() returns a fresh randomised mix each call:
        #   - ALWAYS_RUN anchors (top broad performers, every cycle)
        #   - Random draw from velocity pool + EXTENDED_TARGETS
        #   - Dead queries (50+ runs, 0 deals) are auto-excluded
        # Falls back to CORE_TARGETS if TrendEngine fails entirely.
        from trend_engine import CORE_TARGETS
        targets = CORE_TARGETS  # safety fallback
        trend_engine = _get_trend_engine()
        if trend_engine:
            try:
                dynamic = await trend_engine.get_cycle_targets(n=60)
                if dynamic:
                    targets = dynamic
                    logger.info(f"🔥 {len(targets)} targets this cycle (varied rotation)")
            except Exception as e:
                logger.warning(f"⚠️ TrendEngine failed, running on {len(targets)} core targets: {e}")

        # Apply custom queries override
        if custom_queries:
            targets = custom_queries

        # Apply brand filter
        if brand_filter:
            filters = [b.strip().lower() for b in brand_filter]
            targets = [t for t in targets if any(f in t.lower() for f in filters)]
            if not targets:
                logger.warning(f"⚠️ No targets matched brand filter: {brand_filter}")
                return

        # Apply max targets limit
        if max_targets:
            targets = targets[:max_targets]

        logger.info(f"━━━ Cycle {self.cycle_count} | {len(targets)} targets ━━━")

        total_deals = 0

        for i, query in enumerate(targets):
            if not self.running:
                break

            # Get sold data
            sold = await self.get_sold_data(query)
            if not sold:
                logger.debug(f"  [{i+1}] {query}: insufficient sold data")
                continue

            logger.info(f"  [{i+1}/{len(targets)}] {query} - sold avg: ${sold.avg_price:.0f} ({sold.count} comps)")

            # Find gaps
            gaps = await self.find_gaps(query, sold)

            for deal in gaps:
                logger.info(
                    f"    💰 ${deal.item.price:.0f} → ${deal.sold_avg:.0f} "
                    f"(gap {deal.gap_percent*100:.0f}%, +${deal.profit_estimate:.0f}) "
                    f"- {deal.item.title[:50]}"
                )
                if await self.process_deal(deal):
                    total_deals += 1

            # Log query performance for trend feedback loop
            if trend_engine:
                best_gap = max((d.gap_percent for d in gaps), default=0) if gaps else 0
                try:
                    trend_engine.log_query_performance(query, len(gaps), best_gap)
                except Exception:
                    pass

            await asyncio.sleep(1.5)  # Rate limiting

        elapsed = time.time() - cycle_start

        if total_deals:
            logger.info(f"  🔥 {total_deals} gap deals sent!")

        logger.info(f"  ⏱ Cycle completed in {elapsed:.0f}s")

        if self.cycle_count % 3 == 0:
            self._save_state()
            self._save_sold_cache()
            self._save_blocklist()
            self._save_image_hashes()
            logger.info(
                f"📊 Stats: cycles={self.cycle_count} | "
                f"deals_sent={self.stats['deals_sent']} | "
                f"auth_blocked={self.stats['auth_blocked']} | "
                f"quality_filtered={self.stats['quality_filtered']} | "
                f"rep_ceiling={self.stats['rep_ceiling_skipped']} | "
                f"low_trust={self.stats['low_trust_skipped']} | "
                f"rep_batch={self.stats['rep_batch_skipped']} | "
                f"image_dup={self.stats['image_dup_skipped']} | "
                f"blocklist={self.stats['blocklist_skipped']} | "
                f"stale={self.stats.get('stale_skipped', 0)} | "
                f"collab_floor={self.stats.get('collab_floor_skipped', 0)} | "
                f"collab_model={self.stats.get('collab_model_skipped', 0)} | "
                f"implausible={self.stats.get('implausible_gap_skipped', 0)} | "
                f"seen={len(self.seen_ids)}"
            )

    async def run(self, once: bool = False, brand_filter=None, custom_queries=None, max_targets=None, source_filter=None):
        """Main loop."""
        init_telegram_db()

        logger.info("=" * 60)
        logger.info("🎯 ARCHIVE ARBITRAGE - GAP HUNTER")
        if brand_filter:
            logger.info(f"   Brand filter: {', '.join(brand_filter)}")
        if custom_queries:
            logger.info(f"   Custom queries: {len(custom_queries)}")
        else:
            logger.info(f"   Targets: dynamic (Grailed velocity + rotation, varied per cycle)")
        if max_targets:
            logger.info(f"   Max targets: {max_targets}")
        logger.info(f"   Min gap: {MIN_GAP_PERCENT*100:.0f}% below sold avg")
        logger.info(f"   Min profit: ${MIN_PROFIT_DOLLARS}")
        logger.info(f"   Min sold comps: {MIN_SOLD_COMPS}")
        logger.info(f"   Poll interval: {POLL_INTERVAL}s")
        logger.info("=" * 60)

        while self.running:
            try:
                await self.run_cycle(brand_filter=brand_filter, custom_queries=custom_queries, max_targets=max_targets, source_filter=source_filter)
            except Exception as e:
                logger.error(f"Cycle error: {e}")

            if once:
                break

            logger.info(f"  💤 Next cycle in {POLL_INTERVAL}s...")
            for _ in range(POLL_INTERVAL):
                if not self.running:
                    break
                await asyncio.sleep(1)

        self._save_state()
        self._save_sold_cache()
        self._save_blocklist()
        self._save_image_hashes()

        # Clean up Playwright browsers
        if hasattr(self, '_ebay'):
            try:
                await self._ebay.close()
            except Exception:
                pass
        if hasattr(self, '_depop_scraper'):
            try:
                await self._depop_scraper.close()
            except Exception:
                pass
        if hasattr(self, '_vinted'):
            try:
                await self._vinted.close()
            except Exception:
                pass

        logger.info("Gap Hunter stopped.")

    @staticmethod
    def _detect_category(title: str) -> str:
        """Detect item category from title for auth scoring."""
        title_lower = title.lower()
        categories = {
            "shoes": [
                "geobasket", "ramones", "dunks", "kiss boots", "larry boots",
                "sickle boots", "banana dunks", "blakey", "peterson", "wayne",
                "shoes", "sneakers", "runners", "trainers", "loafers",
                "court classic", "triple s", "track", "speed trainer",
                "ozweego", "response trail", "stan smith", "virgilboot",
                "virgil boots", "tabi boots", "tabi ankle", "puddle boots",
                "tire boots", "wyatt boots", "chain boots",
            ],
            "boots": [
                "boots", "boot", "combat boot", "cylon",
            ],
            "jacket": [
                "jacket", "blazer", "coat", "bomber", "parka", "varsity",
                "stooges", "dustulator", "memphis", "flak jacket", "astro biker",
                "riot bomber", "tape bomber",
            ],
            "pants": [
                "pants", "trousers", "jeans", "denim", "cargos", "cargo",
                "bauhaus cargo", "creatch cargo", "painter jeans", "bondage pants",
                "track pants", "leather pants",
            ],
            "hoodie": [
                "hoodie", "hooded sweatshirt", "zip up hoodie", "pullover",
                "horseshoe hoodie", "pentagram hoodie", "matty boy hoodie",
            ],
            "tee": [
                "t-shirt", "tshirt", "tee ", " tee", "level tee", "long sleeve tee",
                "scoop neck tee", "atelier tee",
            ],
            "sweater": [
                "sweater", "knit", "cardigan", "jumper", "intarsia", "mohair",
            ],
            "shirt": [
                "shirt", "button up", "button down", "flannel", "hawaiian shirt",
                "leopard shirt", "printed shirt", "silk shirt", "bowling shirt",
            ],
            "bag": [
                "bag", "messenger", "duffle", "handbag", "purse",
                "glam slam", "cassette bag", "saddle bag", "luggage",
                "box bag", "bao bao", "chest rig",
            ],
            "hat": [
                "hat", "cap", "beanie", "trucker hat", "new era",
            ],
            "accessories": [
                "necklace", "ring", "bracelet", "pendant", "jewelry",
                "chain", "glasses", "sunglasses", "eyewear",
                "cross pendant", "dagger pendant", "floral cross",
                "scroll bracelet", "paper chain", "orb necklace",
                "pearl choker", "armor ring", "pearl necklace",
                "rollercoaster belt", "belt", "wallet",
            ],
        }
        for cat, keywords in categories.items():
            if any(kw in title_lower for kw in keywords):
                return cat
        return ""

    @staticmethod
    def _detect_brand(title: str) -> str:
        title_lower = title.lower()
        brands = [
            "rick owens", "chrome hearts", "raf simons", "helmut lang",
            "number nine", "number (n)ine", "undercover",
            "jean paul gaultier", "gaultier",
            "vivienne westwood", "maison margiela", "margiela",
            "dior homme", "dior men", "christian dior", "thierry mugler", "mugler",
            "enfants riches deprimes", "erd", "hysteric glamour",
            "yohji yamamoto", "comme des garcons", "cdg",
            "issey miyake", "kapital", "carol christian poell",
            "boris bidjan saberi", "julius", "ann demeulemeester",
            "haider ackermann", "alexander mcqueen", "celine",
            "neighborhood", "wtaps", "human made", "sacai",
            "roen", "soloist", "takahiromiyashita", "bape",
            "visvim", "junya watanabe", "wacko maria",
            "givenchy", "gucci", "versace", "dries van noten",
            "mihara yasuhiro", "burberry", "y-3",
            "balenciaga", "saint laurent", "prada", "bottega veneta",
        ]
        for brand in brands:
            if brand in title_lower:
                return brand
        return ""


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Archive Arbitrage Gap Hunter — find underpriced archive pieces")
    parser.add_argument("--once", action="store_true", help="Run one cycle then exit")
    parser.add_argument("--brand", type=str, help="Filter by brand (e.g. 'rick owens'). Comma-separated for multiple.")
    parser.add_argument("--query", type=str, help="Custom search queries, comma-separated (e.g. 'rick owens dunks,raf simons bomber')")
    parser.add_argument("--max-targets", type=int, help="Max number of targets per cycle")
    parser.add_argument("--list-brands", action="store_true", help="List all brands in targets and exit")
    parser.add_argument("--list-targets", action="store_true", help="List all search targets and exit")
    args = parser.parse_args()

    # List modes
    if args.list_brands:
        seen = []
        for t in TARGETS:
            for brand in ["rick owens", "chrome hearts", "raf simons", "helmut lang",
                          "number nine", "undercover", "jean paul gaultier", "gaultier",
                          "vivienne westwood", "maison margiela", "margiela", "dior",
                          "thierry mugler", "enfants riches deprimes", "hysteric glamour",
                          "yohji yamamoto", "y-3", "comme des garcons", "cdg", "issey miyake",
                          "kapital", "carol christian poell", "boris bidjan saberi", "julius",
                          "ann demeulemeester", "haider ackermann", "celine",
                          "balenciaga", "saint laurent", "prada", "bottega veneta",
                          "givenchy", "gucci", "versace", "dries van noten",
                          "stone island", "needles", "visvim", "mihara yasuhiro",
                          "neighborhood", "wtaps", "human made", "sacai", "roen",
                          "soloist", "bape", "junya watanabe", "wacko maria", "burberry"]:
                if brand in t.lower() and brand not in seen:
                    seen.append(brand)
        for b in seen:
            count = sum(1 for t in TARGETS if b in t.lower())
            print(f"  {b} ({count} targets)")
        print(f"\nTotal: {len(seen)} brands, {len(TARGETS)} targets")
        exit(0)

    if args.list_targets:
        for i, t in enumerate(TARGETS, 1):
            print(f"  {i:3d}. {t}")
        print(f"\nTotal: {len(TARGETS)} targets")
        exit(0)

    # Parse filters
    brand_filter = [b.strip() for b in args.brand.split(",")] if args.brand else None
    custom_queries = [q.strip() for q in args.query.split(",")] if args.query else None

    hunter = GapHunter()
    asyncio.run(hunter.run(
        once=args.once,
        brand_filter=brand_filter,
        custom_queries=custom_queries,
        max_targets=args.max_targets,
    ))
