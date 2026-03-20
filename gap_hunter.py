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
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from pathlib import Path

# Validate dependencies before importing optional ones
sys.path.insert(0, os.path.dirname(__file__))
from core.dependencies import validate_all

# Run dependency check on startup
if not validate_all(critical_only=True):
    print("\n❌ Cannot start: Missing critical dependencies")
    print("   Install with: pip install -r requirements.txt")
    sys.exit(1)

try:
    import imagehash
    from PIL import Image
    import httpx
    HAS_IMAGE_LIBS = True
except ImportError:
    HAS_IMAGE_LIBS = False

from dotenv import load_dotenv
load_dotenv()

# Validate configuration before starting
from core.config import validate_config
validate_config(exit_on_error=True)

from scrapers import GrailedScraper, PoshmarkScraper, ScrapedItem
from scrapers.multi_platform import EbaySoldScraper
from scrapers.vinted import VintedScraperWrapper as VintedScraper
from scrapers.ebay import EbayScraper
from scrapers.depop import DepopScraper
from scrapers.mercari import MercariScraper
from scrapers.therealreal import TheRealRealScraper
from scrapers.fashionphile import FashionphileScraper
from scrapers.secondstreet import SecondStreetScraper
# ShopGoodwill removed — API consistently returns 500
from core.authenticity_v2 import AuthenticityCheckerV2, format_auth_bar, format_auth_grade, MIN_AUTH_SCORE
from core.desirability import check_desirability, REJECT_PATTERNS
from telegram_bot import send_deal_to_subscribers, send_message, init_telegram_db, get_active_subscribers, TELEGRAM_CHANNEL_ID
from core.discord_alerts import send_discord_alert, DISCORD_ENABLED
from core.tier_policy import classify_discord_tiers
from core.whop_alerts import send_whop_alert, format_whop_deal_content
from core.deal_quality import calculate_deal_quality, format_signal_line, format_quality_header, DealSignals, THRESHOLD_FIRE_1
from core.auth_filter import authenticate_comps, filter_authenticated_comps
from scrapers.product_fingerprint import parse_title_to_fingerprint
from core.japan_integration import find_japan_arbitrage_deals, JapanArbitrageMonitor
from core.deal_validation import validate_deal, track_customer_interaction, ValidationStatus
from core.validation_engine import ValidationEngine
from core.blue_chip_targets import (
    ALL_BLUE_CHIP_TARGETS, 
    get_target_config, 
    get_targets_by_tier,
    get_target_stats
)
from core.pricing_engine import PricingEngine
from core.hyper_pricing import (
    calculate_hyper_price,
    detect_category_from_query,
    extract_days_ago,
    Comp,
)
from core.liquidation_pricing import compute_liquidation_metrics
from core.condition_parser import parse_condition
from core.size_scorer import score_size
from core.deal_tracker import DealPrediction, record_prediction
from db.sqlite_models import save_item as db_save_item, update_item_qualification, Item as DbItem

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
MIN_SOLD_COMPS = int(os.getenv("GAP_MIN_COMPS", "8"))            # Need 8+ sold comps (was 20, too high for niche items)

# Platform fee rates (commission + payment processing)
PLATFORM_FEES = {
    "grailed": 0.142,       # 12% commission + 2.2% payment
    "poshmark": 0.20,       # 20% flat
    "ebay": 0.13,           # ~12.9% FVF + varies
    "depop": 0.10,          # 10% + processor
    "therealreal": 0.15,    # Consignment varies, ~15% avg
    "vinted": 0.05,         # 5% seller fee
    "mercari": 0.10,        # 10% flat
}
DEFAULT_SELL_PLATFORM = os.getenv("DEFAULT_SELL_PLATFORM", "grailed")
DEFAULT_SELL_FEE = PLATFORM_FEES.get(DEFAULT_SELL_PLATFORM, 0.142)

# ── Pricing Engine (centralized cache) ──
_pricing_engine = None

def _get_pricing_engine():
    """Get or initialize PricingEngine singleton."""
    global _pricing_engine
    if _pricing_engine is None:
        try:
            _pricing_engine = PricingEngine()
            logger.info("✅ PricingEngine initialized")
        except Exception as e:
            logger.warning(f"⚠️ PricingEngine initialization failed: {e}")
            _pricing_engine = False
    return _pricing_engine if _pricing_engine else None
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

def estimate_shipping(item: "ScrapedItem", reference_price: float = 0.0) -> float:
    """
    Category-aware shipping estimate for profit calculations.
    Includes insurance for high-value items (>$500).
    """
    title_lower = (item.title or "").lower()
    category_lower = (item.category or "").lower()
    combined = title_lower + " " + category_lower

    # Shipping estimates updated for 2026 rates (USPS +7.8%, UPS/FedEx +6%)
    # Heavy outerwear (2-5 lbs)
    if any(k in combined for k in ("jacket", "coat", "parka", "anorak", "bomber", "leather", "hoodie")):
        base = 32.0
    # Footwear (3-6 lbs with box)
    elif any(k in combined for k in ("boot", "shoe", "sneaker", "geobasket", "ramone", "creeper", "tabi",
                                    "loafer", "sandal", "heel", "pump", "mule", "clog")):
        base = 22.0
    # Small accessories / jewelry (First Class or small Priority)
    elif any(k in combined for k in ("ring", "pendant", "necklace", "bracelet", "earring", "chain",
                                    "charm", "pin", "brooch")):
        base = 8.0
    # Bottoms / pants / denim (1-2 lbs)
    elif any(k in combined for k in ("pant", "jean", "denim", "cargo", "trouser", "short")):
        base = 15.0
    # Eyewear (small but fragile — needs box)
    elif any(k in combined for k in ("sunglasses", "glasses", "eyewear", "frames")):
        base = 12.0
    # Belts (flat, lightweight)
    elif any(k in combined for k in ("belt",)):
        base = 10.0
    # Default (tops, shirts, tees, knitwear — 1-2 lbs)
    else:
        base = 16.0

    # Insurance for high-value items (~$4 per $100 of declared value)
    if reference_price > 500:
        insurance = max(3.0, reference_price * 0.04)
        base += insurance

    return base

STATE_FILE = os.path.join(os.path.dirname(__file__), "data", "gap_state.json")
SOLD_CACHE_FILE = os.path.join(os.path.dirname(__file__), "data", "sold_cache.json")
SOLD_CACHE_TTL = 14400  # 4 hours — must exceed query cooldown (120min) for cache hits
# Archive fashion and luxury items have lower liquidity — use longer windows and lower thresholds
# to ensure we can find comps for rare/archive pieces
ARCHIVE_ITEM_KEYWORDS = ['archive', 'vintage', 'rick owens', 'margiela', 'raf simons',
                         'helmut lang', 'number nine', 'carol christian poell',
                         'boris bidjan saberi', 'undercover',
                         'comme des garcons', 'ann demeulemeester',
                         'chrome hearts', 'julius', 'kapital', 'visvim',
                         'vivienne westwood', 'enfants riches deprimes', 'erd',
                         'jean paul gaultier', 'gaultier', 'guidi',
                         'haider ackermann', 'dries van noten', 'hysteric glamour',
                         'dior homme', 'thierry mugler', 'soloist', 'sacai', 'lemaire']

LUXURY_ITEM_KEYWORDS = ['chanel', 'louis vuitton', 'lv ', 'prada',
                        'gucci', 'balenciaga', 'saint laurent', 'ysl',
                        'dior', 'bottega veneta',
                        'issey miyake', 'thierry mugler', 'mugler', 'jil sander',
                        'maison margiela', 'margiela', 'craig green', 'kiko kostadinov']

def _is_archive_query(query: str) -> bool:
    """Check if query is for archive/vintage items that need relaxed thresholds."""
    query_lower = query.lower()
    return any(kw in query_lower for kw in ARCHIVE_ITEM_KEYWORDS)

def _is_luxury_query(query: str) -> bool:
    """Check if query is for luxury items that need relaxed thresholds."""
    query_lower = query.lower()
    return any(kw in query_lower for kw in LUXURY_ITEM_KEYWORDS)

def _get_comp_thresholds(query: str):
    """Get comp thresholds based on item type."""
    if _is_archive_query(query):
        return {
            'min_comps': 5,
            'max_age_days': 90,  # 90 days — archive markets shift, stale comps = bad pricing
        }
    elif _is_luxury_query(query):
        return {
            'min_comps': 3,
            'max_age_days': 180,  # 6 months for luxury (was 2 years — too stale)
        }
    return {
        'min_comps': MIN_SOLD_COMPS,  # Default 8
        'max_age_days': 365,  # Default 1 year (was 180 days)
    }

MAX_COMP_AGE_DAYS = 180  # Default: only use sold comps from the last 6 months

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
    "therealreal": 0.90,  # TRR prices near Grailed, pre-authenticated
    "fashionphile": 0.95, # Fashionphile premium for luxury accessories
    "2ndstreet": 0.70,    # Japan source, structural discount + JPY weakness
}
# ── Bag filter — ALL bags/wallets/purses rejected from alerts ──
_BAG_KEYWORDS = {"bag", "handbag", "purse", "tote", "clutch", "shoulder bag", "crossbody",
                 "satchel", "backpack", "duffle", "weekender", "briefcase", "messenger bag",
                 "wallet", "card holder", "card case", "coin purse",
                 "flap bag", "bucket bag", "hobo bag", "belt bag", "bum bag", "fanny pack",
                 "keepall", "neverfull", "speedy", "pochette"}

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
        "cross pendant": 350,
        "dagger pendant": 400,
        "floral cross": 400,
        "cross ring": 300,
        "ring": 250,         # minimum for ANY CH ring
        "bracelet": 400,
        "necklace": 300,
        "chain": 350,
        "pendant": 300,
        "leather jacket": 2500,
        "denim jacket": 1000,
        "eyewear": 350,
        "hoodie": 450,
        "cemetery": 600,
        "tee": 250,          # CH tees never sell under $250 authentic
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
        "hoodie": 500,
        "jacket": 1500,
        "leather jacket": 1500,
        "denim jacket": 800,
        "bomber": 1200,
        "tee": 400,
        "t-shirt": 400,
        "long sleeve": 300,
        "jeans": 500,
        "pants": 400,
        "sweater": 600,
        "flannel": 400,
        "shirt": 400,
        "hat": 200,
        "cap": 200,
        "belt": 500,
    },
    "erd": {
        "hoodie": 500,
        "jacket": 1500,
        "leather jacket": 1500,
        "denim jacket": 800,
        "tee": 400,
        "t-shirt": 400,
        "long sleeve": 300,
        "jeans": 500,
        "hat": 200,
        "belt": 500,
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
        "paris sneaker": 200,
    },
    "saint laurent": {
        "wyatt": 200,
        "leather jacket": 300,
        "leather boots": 200,
        "teddy": 300,
        "court classic": 100,
    },
    "prada": {
        "americas cup": 100,
        "cloudbust": 100,
        "linea rossa": 80,
        "chocolate loafers": 300,
        "leather loafers": 200,
    },
    "bottega veneta": {
        "puddle": 100,
        "tire boots": 150,
        "chelsea boots": 200,
    },
    "louis vuitton": {
        "murakami": 500,
        "trainer": 300,
    },
    "chanel": {
        "espadrilles": 300,
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
    # ── New brands ──
    "celine": {
        "leather jacket": 800,
        "teddy jacket": 600,
        "varsity jacket": 700,
        "boots": 200,
        "western boots": 300,
        "belt": 150,
    },
    "haider ackermann": {
        "leather jacket": 400,
        "blazer": 150,
        "silk bomber": 250,
        "coat": 250,
    },
    "dries van noten": {
        "embroidered jacket": 200,
        "velvet blazer": 150,
        "leather jacket": 250,
        "coat": 200,
    },
    "sacai": {
        "leather jacket": 300,
        "bomber": 200,
        "blazer": 150,
    },
    "guidi": {
        "boots": 200,
        "back zip": 250,
        "jacket": 300,
        "horse leather": 250,
    },
    "lemaire": {
        "jacket": 150,
        "leather jacket": 250,
        "coat": 200,
        "boots": 120,
    },
    "acne studios": {
        "leather jacket": 200,
        "velocite": 300,
        "shearling": 250,
        "boots": 100,
    },
    "simone rocha": {
        "dress": 150,
        "jacket": 150,
        "pearl": 100,
    },
    "brunello cucinelli": {
        "cashmere jacket": 250,
        "leather jacket": 400,
        "cashmere sweater": 120,
        "coat": 250,
    },
    "soloist": {
        "jacket": 250,
        "leather jacket": 400,
        "boots": 200,
    },
    "takahiromiyashita": {
        "jacket": 250,
        "leather jacket": 400,
        "boots": 200,
    },
    "hysteric glamour": {
        "leather jacket": 300,
        "denim jacket": 150,
        "jeans": 100,
        "tee": 80,
        "knit": 100,
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
    p25_price: float = 0.0
    auth_p25_price: float = 0.0
    liquidation_anchor: float = 0.0
    downside_anchor: float = 0.0
    pricing_method: str = "median"
    pricing_confidence: str = "medium"
    haircut_pct: float = 0.15
    comp_titles: list = None  # Titles of sold comps (for validation engine)
    comp_sizes: list = None   # Sizes of sold comps (for size parity check)
    comp_prices: list = None  # Individual comp prices (for item_comps persistence)
    comp_urls: list = None    # Individual comp URLs
    comp_confidence_penalty: int = 0  # Points to subtract from quality score (from comp_validator)


@dataclass
class GapDeal:
    item: ScrapedItem
    sold_avg: float
    gap_percent: float
    profit_estimate: float
    sold_count: int
    query: str
    comp_confidence: str = "medium"
    comp_confidence_level: str = "medium"
    comp_cv: float | None = None
    authenticated_comps: int = 0
    comp_auth_confidence: float = 0.0
    hyper_pricing: bool = False
    comp_confidence_penalty: int = 0  # Penalty from comp_validator
    liquidation_anchor: float = 0.0
    downside_anchor: float = 0.0
    expected_net_profit: float = 0.0
    downside_net_profit: float = 0.0
    margin_of_safety_score: float = 0.0
    discovered_at: Optional[datetime] = None
    # Comp snapshot data for frontend persistence
    comp_snapshots: list = None  # List of dicts with title, price, url per comp
    similarity_scores: list = None  # Per-comp similarity scores from compute_weighted_price


def _map_grade(fire_level: int, quality_score: float) -> str:
    """Map gap_hunter quality signals to A/B/C/D grade."""
    if fire_level >= 3 and quality_score >= 80:
        return "A"
    if fire_level >= 2 and quality_score >= 65:
        return "B"
    if fire_level >= 1 and quality_score >= 50:
        return "C"
    return "D"


async def compute_comp_phashes(comps: list, max_concurrent: int = 5) -> dict:
    """Batch compute pHashes for comp images. Returns {index: phash_hex_string}.

    Only hashes comps that have images but no phash yet. Downloads images
    concurrently with a semaphore to limit bandwidth.
    """
    try:
        import imagehash
        from PIL import Image
        import io
        import httpx
    except ImportError:
        return {}

    sem = asyncio.Semaphore(max_concurrent)
    results = {}

    async def _hash_one(idx: int, url: str):
        async with sem:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(url)
                if resp.status_code != 200:
                    return
                img = Image.open(io.BytesIO(resp.content))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                results[idx] = str(imagehash.phash(img))
            except Exception:
                pass

    tasks = []
    for i, comp in enumerate(comps):
        if getattr(comp, 'phash', None):
            continue  # Already has phash
        images = getattr(comp, 'images', None) or []
        url = images[0] if images else getattr(comp, 'image_url', None)
        if url:
            tasks.append(_hash_one(i, url))

    if tasks:
        await asyncio.gather(*tasks)

    return results


def compute_weighted_price(
    item_title: str,
    brand: str,
    sold_items: list,
    sold_data,
    listing_phash: str = None,
) -> Optional[SoldData]:
    """Score each comp against the listing and compute similarity-weighted pricing.

    Returns a new SoldData with recalculated prices, or None if no comps
    are similar enough (hard gate: 0 comps above 0.5 similarity).
    """
    from scrapers.comp_matcher import parse_title, score_comp_similarity, image_similarity_boost, is_exact_match
    from db.sqlite_models import get_comp_quality_scores, get_pair_quality_scores_batch

    if not sold_items:
        return None

    listing_fp = parse_title(brand, item_title)

    # ── Hard gate: is_exact_match() pre-filter ──
    # Reject comps that fail brand/model/type/line/material checks before scoring.
    # This catches mismatches that soft scoring alone might let through at ~0.5.
    filtered_items = []
    for comp in sold_items:
        comp_fp = parse_title(brand, comp.title)
        if is_exact_match(listing_fp, comp_fp):
            filtered_items.append(comp)
        else:
            logger.debug(
                f"    🚫 is_exact_match rejected: '{comp.title[:50]}' "
                f"(model: {comp_fp.model or 'none'}, type: {comp_fp.item_type or 'none'})"
            )
    if not filtered_items:
        logger.info(f"    ❌ All comps rejected by is_exact_match for '{item_title[:50]}'")
        return None
    sold_items = filtered_items
    context_model = listing_fp.model or listing_fp.item_type or "unknown"

    # Look up global quality scores in one batch
    source_pairs = [
        (getattr(c, 'source', 'grailed'), getattr(c, 'source_id', ''))
        for c in sold_items
    ]
    quality_scores = get_comp_quality_scores(source_pairs)

    # Look up per-pair quality scores (Gap 2: scoped to this listing's model context)
    # Also fetch rejection reasons for Gap 3 amplification
    sold_comp_ids = []
    source_to_scid = {}  # map (source, source_id) -> sold_comp_id for pair lookup
    for c in sold_items:
        src = getattr(c, 'source', 'grailed')
        sid = getattr(c, 'source_id', '')
        # sold_comp_id may be available from DB comps
        scid = getattr(c, '_db_sold_comp_id', None)
        if scid:
            sold_comp_ids.append(scid)
            source_to_scid[(src, sid)] = scid

    pair_scores = get_pair_quality_scores_batch(sold_comp_ids, context_model) if sold_comp_ids else {}

    # Batch fetch rejection reasons for Gap 3
    rejection_reasons_map = {}
    try:
        from db.sqlite_models import get_comp_rejection_reasons_batch
        rejection_reasons_map = get_comp_rejection_reasons_batch(source_pairs)
    except ImportError:
        pass

    # Score each comp
    scored = []
    for comp in sold_items:
        if not comp.price or comp.price <= 0:
            continue
        source = getattr(comp, 'source', 'grailed')
        source_id = getattr(comp, 'source_id', '')

        # Per-pair quality takes priority over global quality
        scid = source_to_scid.get((source, source_id))
        if scid and scid in pair_scores:
            q_score = pair_scores[scid]
        else:
            q_score = quality_scores.get((source, source_id), 1.0)

        # Get rejection reasons for this comp (Gap 3)
        comp_reasons = rejection_reasons_map.get((source, source_id))

        similarity = score_comp_similarity(
            listing_fp, comp.title,
            comp_quality_score=q_score,
            rejection_reasons=comp_reasons,
        )

        # Image similarity boost (neutral when either hash is missing)
        comp_phash = getattr(comp, 'phash', None)
        img_boost = image_similarity_boost(listing_phash, comp_phash)
        similarity = similarity * img_boost

        scored.append((comp, similarity))

    if not scored:
        return None

    # Sort by similarity descending for logging
    scored.sort(key=lambda x: x[1], reverse=True)

    above_threshold = [(c, s) for c, s in scored if s >= 0.5]

    # Gate logic
    if len(above_threshold) >= 3:
        # Drop gate: enough good comps, drop the rest
        final = above_threshold
    elif len(above_threshold) == 0:
        # Hard gate: no comps similar enough — skip this item
        logger.info(
            f"    ❌ No comps above 0.5 similarity for '{item_title[:50]}' "
            f"(best: {scored[0][1]:.2f} '{scored[0][0].title[:40]}')"
        )
        return None
    else:
        # Downweight fallback: keep all, weight by similarity
        final = scored

    # Cap at 10 best comps — enough for confidence, few enough that each matters
    # Sort by similarity first to keep the best, then re-sort by price for median
    final.sort(key=lambda x: x[1], reverse=True)
    final = final[:10]

    # Compute weighted median
    final.sort(key=lambda x: x[0].price)
    total_weight = sum(s for _, s in final)
    if total_weight <= 0:
        return None

    # Walk through prices accumulating weight until 50th percentile
    cumulative = 0.0
    weighted_median = final[-1][0].price
    for comp, sim in final:
        cumulative += sim
        if cumulative >= total_weight * 0.5:
            weighted_median = comp.price
            break

    # Weighted average
    weighted_avg = sum(c.price * s for c, s in final) / total_weight

    # Build new SoldData
    surviving_comps = [c for c, _ in final]
    similarity_scores = [s for _, s in final]

    result = SoldData(
        query=getattr(sold_data, 'query', ''),
        avg_price=weighted_avg,
        median_price=weighted_median,
        min_price=min(c.price for c in surviving_comps),
        max_price=max(c.price for c in surviving_comps),
        count=len(final),
        timestamp=getattr(sold_data, 'timestamp', 0),
    )
    # Carry over attributes from original
    result.comp_titles = [c.title for c in surviving_comps]
    result.comp_prices = [c.price for c in surviving_comps]
    result.comp_urls = [getattr(c, 'url', None) for c in surviving_comps]
    result.comp_sizes = [getattr(c, 'size', None) for c in surviving_comps]
    result._similarity_scores = similarity_scores
    # Identity fields for direct persistence (bypass link_item_to_sold_comps)
    result.comp_sources = [getattr(c, 'source', 'grailed') for c in surviving_comps]
    result.comp_source_ids = [getattr(c, 'source_id', '') for c in surviving_comps]
    result.comp_conditions = [getattr(c, 'condition', None) for c in surviving_comps]
    result.comp_sold_dates = [getattr(c, 'sold_date', None) for c in surviving_comps]
    result.comp_phashes = [getattr(c, 'phash', None) for c in surviving_comps]
    result.comp_image_urls = [
        (getattr(c, 'images', None) or [None])[0]
        if hasattr(c, 'images')
        else getattr(c, 'image_url', None)
        for c in surviving_comps
    ]
    result._confidence = getattr(sold_data, '_confidence', 'medium')
    result._cv = getattr(sold_data, '_cv', None)
    result._hyper_pricing = getattr(sold_data, '_hyper_pricing', False)
    result.comp_confidence_penalty = getattr(sold_data, 'comp_confidence_penalty', 0)
    result.pricing_confidence = getattr(sold_data, 'pricing_confidence', 'medium')
    result.liquidation_anchor = getattr(sold_data, 'liquidation_anchor', None)
    result.downside_anchor = getattr(sold_data, 'downside_anchor', None)
    result._authenticated_comps = getattr(sold_data, '_authenticated_comps', 0)
    result._auth_confidence = getattr(sold_data, '_auth_confidence', 0.0)

    logger.info(
        f"    📊 Weighted pricing: {len(final)} comps "
        f"(dropped {len(scored) - len(final)}), "
        f"median ${weighted_median:.0f}, avg ${weighted_avg:.0f}, "
        f"best sim={similarity_scores[0]:.2f}"
    )

    return result


class GapHunter:
    """Find items listed significantly below proven sold prices."""

    def __init__(self):
        self.auth = AuthenticityCheckerV2()
        self.validation = ValidationEngine()
        self.seen_ids: set = set()
        self.sold_cache: Dict[str, SoldData] = {}
        self.cycle_count = 0
        self.stats = defaultdict(int)
        self.running = True
        self.image_hashes: Dict[str, List[Dict]] = {}  # hash -> list of {seller, url, title}
        self._fx_cache: Dict[str, tuple] = {}  # currency -> (rate, timestamp)
        self._last_query_metrics: Dict[str, int] = {}
        self._item_comp_cache: Dict[str, Optional[SoldData]] = {}  # per-item comp cache (cleared each cycle)
        self._raw_items_cache: Dict[str, list] = {}  # raw sold items parallel to sold_cache

        # Initialize seller manager (replaces manual blocklist handling)
        from core.seller_manager import SellerManager
        self.seller_manager = SellerManager()
        
        # Initialize data manager for state persistence
        from core.data_manager import DataManager
        self.data_manager = DataManager()
        
        self._load_state()
        self._load_sold_cache()
        self._load_image_hashes()
        
        # Prune data every 10 cycles
        self.cycles_since_prune = 0

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        logger.info("Shutting down...")
        self.running = False
        # Playwright cleanup happens in run() after the loop exits

    def _load_state(self):
        """Load state using DataManager."""
        try:
            if hasattr(self, 'data_manager'):
                data = self.data_manager.load("gap_state", {})
                self.seen_ids = set(data.get("seen_ids", []))
                self.cycle_count = data.get("cycle_count", 0)
            else:
                # Fallback to direct file I/O
                if os.path.exists(STATE_FILE):
                    with open(STATE_FILE) as f:
                        data = json.load(f)
                        self.seen_ids = set(data.get("seen_ids", []))
                        self.cycle_count = data.get("cycle_count", 0)
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
            self.seen_ids = set()
            self.cycle_count = 0

    def _save_state(self):
        """Save state using DataManager."""
        try:
            # Keep only last 50k IDs to prevent unbounded growth
            ids = list(self.seen_ids)[-50000:]
            data = {"seen_ids": ids, "cycle_count": self.cycle_count}
            
            if hasattr(self, 'data_manager'):
                self.data_manager.save("gap_state", data)
            else:
                # Fallback to direct file I/O
                os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
                with open(STATE_FILE, "w") as f:
                    json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")

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
                    "p25_price": v.p25_price,
                    "auth_p25_price": v.auth_p25_price,
                    "liquidation_anchor": v.liquidation_anchor,
                    "downside_anchor": v.downside_anchor,
                    "pricing_method": v.pricing_method,
                    "pricing_confidence": v.pricing_confidence,
                    "haircut_pct": v.haircut_pct,
                    "comp_titles": v.comp_titles,
                    "comp_prices": v.comp_prices,
                    "comp_urls": v.comp_urls,
                }
            with open(SOLD_CACHE_FILE, "w") as f:
                json.dump(raw, f)
        except Exception:
            pass

    def _load_blocklist(self):
        """Deprecated: Use self.seller_manager instead."""
        pass

    def _save_blocklist(self):
        """Deprecated: Use self.seller_manager.flush() instead."""
        if hasattr(self, 'seller_manager'):
            self.seller_manager.flush()

    def _load_image_hashes(self):
        """Load image hashes using DataManager."""
        try:
            if hasattr(self, 'data_manager'):
                self.image_hashes = self.data_manager.load("image_hashes", {})
            else:
                # Fallback to direct file I/O
                if os.path.exists(IMAGE_HASHES_FILE):
                    with open(IMAGE_HASHES_FILE) as f:
                        self.image_hashes = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load image hashes: {e}")
            self.image_hashes = {}

    def _save_image_hashes(self):
        """Save image hashes using DataManager."""
        try:
            if hasattr(self, 'data_manager'):
                self.data_manager.save("image_hashes", self.image_hashes, compress=True)
            else:
                # Fallback to direct file I/O
                os.makedirs(os.path.dirname(IMAGE_HASHES_FILE), exist_ok=True)
                with open(IMAGE_HASHES_FILE, "w") as f:
                    json.dump(self.image_hashes, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save image hashes: {e}")

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
        if not seller or not hasattr(self, 'seller_manager'):
            return
        
        was_auto_blocked = self.seller_manager.record_auth_failure(seller)
        if was_auto_blocked:
            count = self.seller_manager.get_block_count(seller)
            logger.warning(f"🚫 Auto-blocklisted seller '{seller}' (auth_blocked {count}x)")

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

    async def get_sold_data(self, query: str, return_raw: bool = False) -> Optional[SoldData]:
        """Get sold price data for a query, using PricingEngine cache when available.
        
        Args:
            query: Search query
            return_raw: If True, also return the raw sold items for hyper-pricing
        
        Returns:
            SoldData or tuple(SoldData, list) if return_raw=True
        """
        # ── Try PricingEngine first ──
        # Skip when return_raw=True — PricingEngine has no raw comp data for similarity scoring
        pricing_engine = _get_pricing_engine()
        if pricing_engine and not return_raw:
            cached_entry = pricing_engine.get_price(query)
            if cached_entry and cached_entry.data:
                # Extract price from cached data
                cached_data = cached_entry.data
                if isinstance(cached_data, dict) and 'price' in cached_data:
                    price = cached_data['price']
                    logger.debug(f"  💰 PricingEngine cache hit for '{query}': ${price}")
                    # Convert to SoldData format
                    return SoldData(
                        query=query,
                        avg_price=price,
                        median_price=price,
                        min_price=price * 0.9,
                        max_price=price * 1.1,
                        count=cached_entry.hit_count + 1,
                        timestamp=cached_entry.timestamp,
                    )
        
        # ── Fall back to legacy cache ──
        if query in self.sold_cache:
            cached = self.sold_cache[query]
            if time.time() - cached.timestamp < SOLD_CACHE_TTL:
                if return_raw:
                    raw = self._raw_items_cache.get(query, [])
                    return (cached, raw)
                return cached

        # Get dynamic thresholds based on item type
        thresholds = _get_comp_thresholds(query)
        min_comps = thresholds['min_comps']
        max_age_days = thresholds['max_age_days']

        try:
            async with GrailedScraper() as scraper:
                sold = await scraper.search_sold(query, max_results=40)  # Fetch more to account for filtering

            # ── Temporal filtering: only use comps from last max_age_days ──
            from datetime import datetime as _dt, timedelta, timezone
            now = _dt.now(timezone.utc)
            cutoff = now - timedelta(days=max_age_days)

            def _filter_fresh(items):
                fresh, stale = [], 0
                for s in items:
                    created_str = (s.raw_data or {}).get("created_at") or (s.raw_data or {}).get("sold_at")
                    if created_str:
                        try:
                            comp_date = _dt.fromisoformat(created_str.replace("Z", "+00:00"))
                            if comp_date < cutoff:
                                stale += 1
                                continue
                        except (ValueError, TypeError):
                            pass
                    fresh.append(s)
                return fresh, stale

            fresh_sold, stale_count = _filter_fresh(sold or [])
            if stale_count > 0:
                logger.debug(f"  Filtered out {stale_count} stale comps (>{max_age_days}d) for '{query}'")

            # ── eBay sold fallback: only when Grailed has < 3 comps ──
            # eBay prices run 5-10% below Grailed; mixing freely dilutes accuracy.
            # Only fall back to eBay when Grailed data is truly insufficient.
            ebay_fallback_used = False
            if len(fresh_sold) < 3:
                try:
                    async with EbaySoldScraper() as ebay_scraper:
                        ebay_sold = await ebay_scraper.search_sold(query, max_results=50)
                    ebay_fresh, _ = _filter_fresh(ebay_sold or [])
                    # eBay "Best Offer Accepted" shows listing price, not actual sale price.
                    # Apply 12% haircut to eBay comps to approximate real transaction prices.
                    for eb in ebay_fresh:
                        if eb.price and eb.price > 0:
                            eb.price = eb.price * 0.88
                    combined = fresh_sold + ebay_fresh
                    if len(combined) >= min_comps:
                        logger.info(f"  📦 eBay sold fallback: {len(ebay_fresh)} comps for '{query}' "
                                    f"(Grailed had {len(fresh_sold)})")
                        fresh_sold = combined
                        ebay_fallback_used = True
                    else:
                        logger.debug(f"  eBay fallback insufficient for '{query}' "
                                     f"({len(combined)} combined, need {min_comps})")
                except Exception as e:
                    logger.debug(f"  eBay sold fallback failed for '{query}': {e}")

            if len(fresh_sold) < min_comps:
                logger.info(f"  📊 Insufficient comps for '{query}': {len(fresh_sold)} fresh, need {min_comps} (had {len(sold or [])} total)")
                return (None, []) if return_raw else None

            sold = fresh_sold

            # ── Authentication filtering: prioritize authenticated comps ──
            auth_result = authenticate_comps(sold, item_price=sum(i.price for i in sold) / len(sold))
            if not auth_result['usable']:
                logger.debug(f"  Auth filtering failed for '{query}': {auth_result['reason']}")
                # Still proceed but log the issue

            auth_filtered_sold = filter_authenticated_comps(sold) if auth_result.get('authenticated_comps', 0) >= 3 else []
            auth_prices = sorted([i.price for i in auth_filtered_sold if i.price and i.price > 0])

            # Use authenticated comps if available
            if auth_result['authenticated_comps'] >= 3:
                logger.info(f"  ✅ Using {auth_result['authenticated_comps']} authenticated comps "
                           f"(confidence: {auth_result['confidence']:.1%})")
                sold = auth_filtered_sold
            
            prices = sorted([i.price for i in sold if i.price and i.price > 0])
            if len(prices) < min_comps:
                return (None, []) if return_raw else None

            comp_confidence_penalty = 0  # May be set by comp_validator below
            query_brand = self._detect_brand(query) or ""

            # ── Product fingerprint + item-type filtering ──
            # Two-pass filter:
            #   1. Require exact item-type word in comp title (ring must have "ring")
            #   2. Exact dimension matching via comp_matcher
            try:
                if query_brand:
                    query_fp = parse_title_to_fingerprint(query_brand, query)

                    # Pass 1: Exact item-type keyword filter
                    # If the query fingerprint has a specific item_type, require that
                    # word to appear in the comp title. This prevents ring/pendant mixing.
                    ITEM_TYPE_KEYWORDS = {
                        "rings": ["ring", "band", "signet"],
                        "necklaces": ["necklace", "pendant", "chain"],
                        "bracelets": ["bracelet", "cuff", "bangle"],
                        "earrings": ["earring", "stud", "hoop"],
                        "belts": ["belt"],
                        "hats": ["hat", "cap", "beanie", "trucker"],
                        "eyewear": ["sunglasses", "glasses", "frames", "eyewear"],
                        "wallets": ["wallet", "card holder", "card case"],
                        "bags": ["bag", "handbag", "tote", "clutch", "purse", "crossbody", "satchel"],
                        "footwear": ["shoes", "sneakers", "boots", "boot", "loafers", "derbies", "sandals", "mules"],
                    }
                    type_keywords = ITEM_TYPE_KEYWORDS.get(query_fp.item_type, [])
                    if type_keywords and len(sold) >= 3:
                        type_filtered = []
                        for s in sold:
                            comp_title_lower = (s.title or "").lower()
                            if any(kw in comp_title_lower for kw in type_keywords):
                                type_filtered.append(s)
                        if len(type_filtered) >= min_comps:
                            removed = len(sold) - len(type_filtered)
                            if removed > 0:
                                logger.info(f"  🔍 Item-type filter ({query_fp.item_type}): kept {len(type_filtered)}/{len(sold)} comps (removed {removed} wrong-category comps)")
                            sold = type_filtered
                            prices = sorted([i.price for i in sold if i.price and i.price > 0])
                        elif len(type_filtered) >= 3:
                            logger.info(f"  🔍 Item-type filter: {len(type_filtered)} matches (below {min_comps}, using anyway)")
                            sold = type_filtered
                            prices = sorted([i.price for i in sold if i.price and i.price > 0])

                    # Pass 2: Exact dimension matching (hard gate)
                    from scrapers.comp_matcher import parse_title as cm_parse_title, is_exact_match, match_quality as cm_match_quality
                    listing_parsed = cm_parse_title(query_brand, query)
                    if listing_parsed.brand and len(sold) >= 3:
                        matched_sold = []
                        for s in sold:
                            comp_brand = self._detect_brand(s.title) or query_brand
                            comp_parsed = cm_parse_title(comp_brand, s.title)
                            if is_exact_match(listing_parsed, comp_parsed):
                                s._match_quality = cm_match_quality(listing_parsed, comp_parsed, getattr(s, 'sold_date', ''))
                                matched_sold.append(s)
                        if len(matched_sold) >= min_comps:
                            removed = len(sold) - len(matched_sold)
                            if removed > 0:
                                logger.info(f"  🎯 Exact match filter: {len(matched_sold)}/{len(sold)} comps matched")
                            # Sort by match quality (best comps first for weighted median)
                            matched_sold.sort(key=lambda s: getattr(s, '_match_quality', 0), reverse=True)
                            sold = matched_sold
                            prices = sorted([i.price for i in sold if i.price and i.price > 0])
                        elif len(matched_sold) > 0:
                            logger.info(f"  ⚠️ Exact match: only {len(matched_sold)} comps (below min {min_comps}), keeping original set")
            except Exception as e:
                logger.debug(f"  Fingerprint filtering error: {e}")

            # ── Filter out suspiciously low sold comps (likely reps) ──
            if len(prices) >= 3:
                initial_median = prices[len(prices) // 2]
                threshold = initial_median * 0.20
                filtered_prices = [p for p in prices if p >= threshold]
                if len(filtered_prices) >= min_comps:
                    if len(prices) != len(filtered_prices):
                        logger.debug(f"  Filtered out {len(prices) - len(filtered_prices)} suspiciously low sold comps for '{query}'")
                    prices = filtered_prices

            # ── Remove outliers using IQR method ──
            if len(prices) >= 5:
                q1_idx = len(prices) // 4
                q3_idx = (3 * len(prices)) // 4
                q1 = prices[q1_idx]
                q3 = prices[q3_idx]
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                iqr_filtered = [p for p in prices if lower_bound <= p <= upper_bound]
                if len(iqr_filtered) >= min_comps:
                    removed = len(prices) - len(iqr_filtered)
                    if removed > 0:
                        logger.debug(f"  IQR outlier removal: {removed} comps removed (range ${lower_bound:.0f}-${upper_bound:.0f})")
                    prices = iqr_filtered

            # ── Comp validation safety net ──
            from core.comp_validator import validate_comps
            if len(sold) >= 3:
                validation = validate_comps(
                    listing_title=query,
                    listing_brand=query_brand,
                    comp_titles=[s.title for s in sold],
                    comp_prices=[s.price for s in sold if s.price and s.price > 0],
                    comp_sold_dates=[getattr(s, 'sold_date', None) for s in sold],
                )
                if validation.surviving_count >= 3:
                    sold = [sold[i] for i in validation.surviving_indices]
                    prices = sorted([s.price for s in sold if s.price and s.price > 0])
                    comp_confidence_penalty = validation.score_penalty
                elif validation.surviving_count < 3:
                    logger.info(f"  ❌ Comp validator: only {validation.surviving_count} comps survived for '{query[:50]}' (need 3)")
                    return (None, []) if return_raw else None

            # ── Detect bimodal distribution (p75 > 2.5x p25 = likely mixed products) ──
            if len(prices) >= 5:
                p25 = prices[len(prices) // 4]
                p75 = prices[(3 * len(prices)) // 4]
                if p25 > 0 and p75 > p25 * 2.5:
                    logger.warning(f"  ⚠️ Bimodal price distribution detected for '{query}': p25=${p25:.0f}, p75=${p75:.0f} (ratio {p75/p25:.1f}x)")
                    # Use only lower half — more conservative
                    prices = prices[:len(prices) // 2]
                    comp_confidence_penalty = max(comp_confidence_penalty, 15)
                    logger.info(f"  📉 Using lower half of comps ({len(prices)} items), +{comp_confidence_penalty}pt penalty")

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

            # ── Capture comp data for validation engine + frontend display ──
            # All lists must use the same filter to keep indices aligned
            valid_comps = [s for s in sold if s.title and s.price and s.price > 0]
            comp_titles = [s.title for s in valid_comps]
            comp_sizes = [getattr(s, 'size', None) for s in valid_comps]
            comp_prices = [s.price for s in valid_comps]
            comp_urls = [getattr(s, 'url', None) for s in valid_comps]

            # ── Persist sold comps to DB with embeddings ──
            from scrapers.title_matcher import get_title_embedding, save_comp_with_embedding
            from scrapers.comp_matcher import parse_title as _cm_parse
            for vc in valid_comps[:15]:
                try:
                    emb = get_title_embedding(vc.title)
                    vc_fp = _cm_parse(query_brand, vc.title) if query_brand else None
                    save_comp_with_embedding(
                        search_key=query,
                        title=vc.title,
                        brand=query_brand,
                        sold_price=vc.price,
                        source=getattr(vc, 'source', 'grailed'),
                        source_id=getattr(vc, 'source_id', '') or '',
                        size=getattr(vc, 'size', None) or '',
                        condition=getattr(vc, 'condition', None) or '',
                        sold_url=getattr(vc, 'url', None) or None,
                        sold_date=str((vc.raw_data or {}).get('sold_at', '')),
                        embedding=emb,
                        platform=getattr(vc, 'source', 'grailed'),
                        item_type=vc_fp.item_type if vc_fp else '',
                        model_name=vc_fp.model if vc_fp else '',
                        sub_brand=vc_fp.sub_brand if vc_fp else '',
                        material=vc_fp.material if vc_fp else '',
                        color=vc_fp.color if vc_fp else '',
                        season=vc_fp.season if vc_fp else '',
                    )
                except Exception:
                    pass  # Duplicate or constraint error — skip

            # ── Compute pHashes for comp images (async batch) ──
            try:
                phash_results = await compute_comp_phashes(valid_comps[:15])
                if phash_results:
                    from db.sqlite_models import update_sold_comp_phash
                    for idx, phash_hex in phash_results.items():
                        vc = valid_comps[idx]
                        vc.phash = phash_hex  # Attach to comp object for downstream use
                        source = getattr(vc, 'source', 'grailed')
                        source_id = getattr(vc, 'source_id', '')
                        if source_id:
                            update_sold_comp_phash(source, source_id, phash_hex)
                    logger.debug(f"  📷 Computed {len(phash_results)} pHashes for '{query}' comps")
            except Exception as e:
                logger.debug(f"  ⚠️ pHash computation failed: {e}")

            # ── Comp confidence based on count ──
            comp_confidence = "high" if len(prices) >= 12 else "medium" if len(prices) >= 5 else "low"

            liquidation = compute_liquidation_metrics(
                sold_prices=prices,
                authenticated_prices=auth_prices,
                cv=None,
                comp_count=len(prices),
                auth_comp_count=len(auth_prices),
                avg_days_to_sell=avg_days,
            )

            data = SoldData(
                query=query,
                avg_price=sum(prices) / len(prices),
                median_price=liquidation.median_price,
                min_price=min(prices),
                max_price=max(prices),
                count=len(prices),
                timestamp=time.time(),
                avg_days_to_sell=avg_days,
                p25_price=liquidation.p25_price,
                auth_p25_price=liquidation.auth_p25_price,
                liquidation_anchor=liquidation.liquidation_anchor,
                downside_anchor=liquidation.downside_anchor,
                pricing_method=liquidation.pricing_method,
                pricing_confidence=liquidation.pricing_confidence,
                haircut_pct=liquidation.haircut_pct,
                comp_titles=comp_titles,
                comp_sizes=comp_sizes,
                comp_prices=comp_prices,
                comp_urls=comp_urls,
                comp_confidence_penalty=comp_confidence_penalty,
            )
            # Store confidence and source metadata on SoldData
            data._confidence = comp_confidence
            data._confidence_level = comp_confidence
            data._authenticated_comps = auth_result.get('authenticated_comps', 0)
            data._auth_confidence = auth_result.get('confidence', 0.0)
            data._ebay_fallback = ebay_fallback_used

            # Track eBay fallback activations in stats
            if ebay_fallback_used:
                self.stats["ebay_sold_fallback_used"] = self.stats.get("ebay_sold_fallback_used", 0) + 1

            # ── Store in PricingEngine cache ──
            if pricing_engine:
                try:
                    pricing_engine.set_price(
                        query=query,
                        price=data.avg_price,
                        source="grailed" if not ebay_fallback_used else "grailed+ebay",
                    )
                    logger.debug(f"  💾 Stored in PricingEngine cache: '{query}' = ${data.avg_price:.0f}")
                except Exception as e:
                    logger.warning(f"  ⚠️ Failed to store in PricingEngine: {e}")

            self.sold_cache[query] = data
            self._raw_items_cache[query] = list(valid_comps)
            if return_raw:
                return (data, list(valid_comps))
            return data

        except Exception as e:
            logger.debug(f"Sold data failed for '{query}': {e}")
            if return_raw:
                return (None, [])
            return None

    async def get_hyper_sold_data(self, query: str, item_title: str = "", item_category: str = "") -> Optional[SoldData]:
        """
        Get sold data with hyper-accurate pricing using time decay + condition + size.
        
        This is an enhanced version of get_sold_data that:
        1. Applies exponential time decay to weight recent comps higher
        2. Parses condition from comp titles and weights condition-matched comps higher
        3. Normalizes prices for size differences
        
        Falls back to standard get_sold_data if hyper-pricing fails.
        """
        # First get standard sold data
        base_data = await self.get_sold_data(query)
        if not base_data:
            return None
        
        try:
            # Detect category for time decay settings
            category = detect_category_from_query(query)
            if item_category:
                category = item_category.lower()
            
            # Parse target item attributes
            target_condition, _, _ = parse_condition(item_title, brand=self._detect_brand(item_title))
            target_size, _, _ = score_size(item_title, category=item_category)
            
            # Build Comp objects from sold items
            # We need to re-fetch the sold items to get full details
            async with GrailedScraper() as scraper:
                sold_items = await scraper.search_sold(query, max_results=40)
            
            if not sold_items or len(sold_items) < 3:
                # Not enough comps for hyper-pricing, use standard
                return base_data
            
            comps = []
            for item in sold_items:
                # Parse condition from comp title
                comp_condition, _, _ = parse_condition(item.title, brand=self._detect_brand(item.title))
                
                # Parse size from comp title
                comp_size, _, _ = score_size(item.title, category=item_category)
                
                # Calculate days ago from sold date
                days_ago = 30  # Default
                raw_data = getattr(item, 'raw_data', {}) or {}
                sold_at = raw_data.get('sold_at') or raw_data.get('created_at')
                if sold_at:
                    days_ago = extract_days_ago(sold_at)
                
                # Check if authenticated
                authenticated = getattr(item, 'authenticated', False) or 'authenticated' in item.title.lower()
                
                comps.append(Comp(
                    price=item.price,
                    condition_tier=comp_condition,
                    size=comp_size,
                    days_ago=days_ago,
                    platform=getattr(item, 'source', 'unknown'),
                    authenticated=authenticated,
                ))
            
            # Calculate hyper-accurate price
            hyper_price, metadata = calculate_hyper_price(
                comps=comps,
                target_condition=target_condition,
                target_size=target_size,
                category=category,
                verbose=False,
            )
            
            if hyper_price > 0 and metadata.get('num_comps', 0) >= 3:
                # Check CV (coefficient of variation) for confidence
                cv = metadata.get('cv', 1.0)
                cv_threshold = float(os.getenv('HYPER_CV_THRESHOLD', '1.5'))
                
                if cv > cv_threshold:
                    # High variance = low confidence, use standard pricing
                    logger.warning(f"  ⚠️ Hyper-price CV too high ({cv:.2f} > {cv_threshold}), using standard: ${base_data.avg_price:.0f}")
                    base_data._hyper_pricing = False
                    base_data._cv = cv
                    base_data._cv_rejected = True
                    return base_data
                
                auth_prices = sorted([c.price for c in comps if c.authenticated and c.price > 0])
                liquidation = compute_liquidation_metrics(
                    sold_prices=[c.price for c in comps if c.price > 0],
                    authenticated_prices=auth_prices,
                    hyper_price=hyper_price,
                    cv=cv,
                    comp_count=metadata['num_comps'],
                    auth_comp_count=len(auth_prices),
                    avg_days_to_sell=base_data.avg_days_to_sell,
                )

                # Create enhanced SoldData
                data = SoldData(
                    query=query,
                    avg_price=hyper_price,
                    median_price=liquidation.median_price,
                    min_price=base_data.min_price,
                    max_price=base_data.max_price,
                    count=metadata['num_comps'],
                    timestamp=time.time(),
                    avg_days_to_sell=base_data.avg_days_to_sell,
                    p25_price=liquidation.p25_price,
                    auth_p25_price=liquidation.auth_p25_price,
                    liquidation_anchor=liquidation.liquidation_anchor,
                    downside_anchor=liquidation.downside_anchor,
                    pricing_method=liquidation.pricing_method,
                    pricing_confidence=liquidation.pricing_confidence,
                    haircut_pct=liquidation.haircut_pct,
                )
                # Store hyper-pricing metadata
                data._hyper_pricing = True
                data._hyper_metadata = metadata
                data._target_condition = target_condition
                data._target_size = target_size
                data._cv = cv
                
                # Determine confidence level
                if cv < 0.5:
                    confidence = "high"
                elif cv < 1.0:
                    confidence = "medium"
                else:
                    confidence = "low"
                data._confidence_level = confidence
                
                logger.info(f"  💎 Hyper-price for '{query}': ${hyper_price:.0f} "
                           f"({confidence} confidence, CV={cv:.2f}, {metadata['num_comps']} comps)")
                
                self.sold_cache[query] = data
                return data
            else:
                # Hyper-pricing failed, return standard data
                logger.debug(f"  Hyper-pricing insufficient comps ({metadata.get('num_comps', 0)}), using standard")
                return base_data
                
        except Exception as e:
            logger.debug(f"Hyper-pricing failed for '{query}', using standard: {e}")
            return base_data

    async def get_item_specific_comps(self, item, brand: str, generic_sold: SoldData) -> tuple:
        """Get sold data specific to a listing's actual product, not the generic query.

        Uses comp_matcher to parse the listing title into structured data,
        then searches for sold comps with increasingly specific queries
        (model → sub-brand + item type → brand + item type → fallback).

        Returns:
            (SoldData, query_used: str, is_item_specific: bool)
        """
        from scrapers.comp_matcher import parse_title, build_search_queries

        if not brand:
            return (generic_sold, "", False)

        try:
            fp = parse_title(brand, item.title)
        except Exception as e:
            logger.debug(f"    ⚠️ parse_title failed for '{item.title[:50]}': {e}")
            return (generic_sold, "", False)

        queries = build_search_queries(fp)
        if not queries:
            return (generic_sold, "", False)

        # Sort by word count descending — more words = more specific query.
        # "chrome hearts cemetery cross sterling silver" (6 words) should be tried
        # before "chrome hearts ring" (3 words) because it targets the actual product.
        queries_by_specificity = sorted(queries, key=lambda q: len(q[0].split()), reverse=True)

        # Only try the top 3 most-specific queries to limit API load
        for query_str, expected_quality in queries_by_specificity[:3]:
            cache_key = query_str.strip().lower()

            # Check per-item comp cache first (already weighted)
            if cache_key in self._item_comp_cache:
                cached = self._item_comp_cache[cache_key]
                if cached is not None and cached.count >= 3:
                    logger.info(
                        f"    🎯 Item comps (cached): '{query_str}' → "
                        f"${cached.avg_price:.0f} ({cached.count} comps)"
                    )
                    return (cached, query_str, True)
                # Cached but insufficient — try next query
                continue

            # Also check the existing sold_cache + apply weighted pricing
            if cache_key in self.sold_cache:
                cached = self.sold_cache[cache_key]
                if time.time() - cached.timestamp < SOLD_CACHE_TTL and cached.count >= 3:
                    raw = self._raw_items_cache.get(cache_key, [])
                    if raw:
                        weighted = compute_weighted_price(item.title, brand, raw, cached)
                        if weighted is not None:
                            self._item_comp_cache[cache_key] = weighted
                            logger.info(
                                f"    🎯 Item comps (sold_cache+weighted): '{query_str}' → "
                                f"${weighted.avg_price:.0f} ({weighted.count} comps)"
                            )
                            return (weighted, query_str, True)
                    else:
                        self._item_comp_cache[cache_key] = cached
                        logger.info(
                            f"    🎯 Item comps (sold_cache): '{query_str}' → "
                            f"${cached.avg_price:.0f} ({cached.count} comps)"
                        )
                        return (cached, query_str, True)

            # Fetch fresh sold data with raw items for similarity scoring
            result = await self.get_sold_data(query_str, return_raw=True)
            if isinstance(result, tuple):
                sold, raw_items = result
            else:
                sold, raw_items = result, []

            if sold and sold.count >= 3 and raw_items:
                weighted = compute_weighted_price(item.title, brand, raw_items, sold)
                if weighted is not None:
                    self._item_comp_cache[cache_key] = weighted
                    logger.info(
                        f"    🎯 Item comps (fresh+weighted): '{query_str}' → "
                        f"${weighted.avg_price:.0f} ({weighted.count} comps, "
                        f"quality={expected_quality:.2f})"
                    )
                    return (weighted, query_str, True)
                else:
                    logger.debug(
                        f"    ℹ️ Weighted pricing returned None for '{query_str}' "
                        f"— no comps similar enough"
                    )
                    # Cache None so we don't retry this query
                    self._item_comp_cache[cache_key] = None
            elif sold:
                logger.debug(
                    f"    ℹ️ Specific query '{query_str}' returned only "
                    f"{sold.count if sold else 0} comps (need 3)"
                )

        # ── Historical DB search via embeddings ──
        # Even if live search didn't find specific comps, the DB might have
        # matching comps from previous cycles
        try:
            from scrapers.title_matcher import get_title_embedding, search_comps_by_embedding
            from types import SimpleNamespace
            listing_emb = get_title_embedding(item.title)
            if listing_emb is not None:
                db_comps = search_comps_by_embedding(listing_emb, brand=brand, limit=20)
                db_comps = [c for c in db_comps if c.get("similarity", 0) >= 0.4]
                if db_comps:
                    db_items = []
                    for dc in db_comps:
                        db_items.append(SimpleNamespace(
                            title=dc.get("title", ""),
                            price=dc.get("sold_price", 0),
                            source=dc.get("source", dc.get("platform", "grailed")),
                            source_id=dc.get("source_id", ""),
                            url=dc.get("url", ""),
                            size=dc.get("size"),
                            condition=dc.get("condition"),
                            raw_data={},
                        ))
                    # Deduplicate
                    seen_ids = set()
                    merged = []
                    for c in db_items:
                        key = f"{c.source}:{c.source_id}"
                        if key not in seen_ids and c.price > 0:
                            seen_ids.add(key)
                            merged.append(c)
                    if len(merged) >= 3:
                        weighted = compute_weighted_price(item.title, brand, merged, generic_sold)
                        if weighted is not None:
                            logger.info(
                                f"    🎯 Item comps (DB embeddings): {len(merged)} comps → "
                                f"${weighted.avg_price:.0f} ({weighted.count} used)"
                            )
                            return (weighted, f"[db:{brand}]", True)
        except Exception as e:
            logger.debug(f"    ⚠️ DB embedding search failed: {e}")

        # None of the specific queries returned enough comps
        logger.debug(f"    ℹ️ No item-specific comps for '{item.title[:50]}', using generic")
        return (generic_sold, "", False)

    async def find_gaps(self, query: str, sold_data: SoldData) -> List[GapDeal]:
        """Find active listings priced below sold average."""
        deals = []
        near_misses = []
        debug_near_misses = os.getenv("GAP_DEBUG_NEAR_MISSES", "1") == "1"

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
            # Depop disabled — Playwright consistently crashes on macOS
            # Re-enable only if/when Depop scraper is fixed to use HTTP instead of browser
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

        async def _mercari():
            try:
                if not hasattr(self, '_mercari'):
                    self._mercari = MercariScraper()
                return await asyncio.wait_for(self._mercari.search(query, max_results=10), timeout=45.0)
            except asyncio.TimeoutError:
                logger.warning(f"    ⚠️ Mercari timed out for '{query}'")
                return []
            except Exception as e:
                logger.warning(f"    ⚠️ Mercari search failed for '{query}': {e}")
                return []

        async def _therealreal():
            try:
                async with TheRealRealScraper() as scraper:
                    return await asyncio.wait_for(scraper.search(query, max_results=15), timeout=20.0)
            except asyncio.TimeoutError:
                logger.debug(f"    TheRealReal timed out for '{query}'")
                return []
            except Exception as e:
                logger.debug(f"    TheRealReal search failed: {e}")
                return []

        async def _fashionphile():
            try:
                async with FashionphileScraper() as scraper:
                    return await asyncio.wait_for(scraper.search(query, max_results=15), timeout=20.0)
            except asyncio.TimeoutError:
                logger.debug(f"    Fashionphile timed out for '{query}'")
                return []
            except Exception as e:
                logger.debug(f"    Fashionphile search failed: {e}")
                return []

        async def _secondstreet():
            try:
                async with SecondStreetScraper(use_proxies=False) as scraper:
                    return await asyncio.wait_for(scraper.search(query, max_results=15), timeout=20.0)
            except asyncio.TimeoutError:
                logger.debug(f"    2ndSTREET timed out for '{query}'")
                return []
            except Exception as e:
                logger.debug(f"    2ndSTREET search failed: {e}")
                return []

        # ── Chrome Hearts: Multi-platform with extended window ──
        # CH is luxury, not hype — use 72hr window and seller trust instead of platform-only.
        is_chrome_hearts = "chrome hearts" in query.lower()

        if is_chrome_hearts:
            # Search all platforms for CH (skip Depop/Vinted)
            results_list = await asyncio.gather(
                _grailed(), _poshmark(), _depop(), _vinted(), _ebay(), _mercari(),
                _therealreal(), _fashionphile(), _secondstreet(),
            )
            logger.info(
                f"  [CH] Multi-platform: Grailed={len(results_list[0])}, Poshmark={len(results_list[1])}, "
                f"eBay={len(results_list[4])}, Mercari={len(results_list[5])}, "
                f"TRR={len(results_list[6])}, Fashionphile={len(results_list[7])}, 2ndST={len(results_list[8])}"
            )
        else:
            results_list = await asyncio.gather(
                _grailed(), _poshmark(), _depop(), _vinted(), _ebay(), _mercari(),
                _therealreal(), _fashionphile(), _secondstreet(),
            )

        all_items = [item for sublist in results_list for item in sublist]
        query_metrics = {
            "raw_items_found": len(all_items),
            "post_filter_candidates": 0,
            "brand_mismatch_skips": 0,
            "category_mismatch_skips": 0,
            "stale_skips": 0,
            "rep_ceiling_skips": 0,
            "implausible_gap_skips": 0,
            "low_trust_skips": 0,
        }
        
        # Debug: Log total items found before any filtering
        logger.info(f"    📊 Raw items found: {len(all_items)} total")
        platform_counts = {}
        for item in all_items:
            platform_counts[item.source] = platform_counts.get(item.source, 0) + 1
        for platform, count in sorted(platform_counts.items()):
            logger.info(f"      - {platform}: {count}")

        # Chrome Hearts recency gate: 72 hours (luxury moves much slower than streetwear)
        if is_chrome_hearts:
            from datetime import datetime as _dt, timezone
            now_utc = _dt.now(timezone.utc)
            fresh = []
            for item in all_items:
                if item.listed_at is None:
                    # Keep items without timestamps — better to check them than miss deals
                    fresh.append(item)
                    continue
                age_mins = (now_utc - item.listed_at).total_seconds() / 60
                if age_mins <= 4320:  # 72 hours
                    fresh.append(item)
                else:
                    logger.debug(f"  [CH] Too old ({age_mins:.0f}m), skipping: {item.title[:50]}")
            logger.info(f"  [CH] {len(fresh)}/{len(all_items)} listings within 72 hours")
            all_items = fresh

        for item in all_items:
            item_key = f"{item.source}:{item.source_id or item.url}"
            if item_key in self.seen_ids:
                continue
            self.seen_ids.add(item_key)

            if not item.price or item.price <= 0:
                continue

            # ── Detect brand early (needed for bag filter, Depop filter, etc.) ──
            detected_brand = self._detect_brand(item.title)

            # ── Depop: skip commonly-faked brands (no authentication) ──
            if item.source == "depop":
                _title_lower = (item.title or "").lower()
                _query_lower = query.lower()
                if any(brand in _title_lower or brand in _query_lower for brand in DEPOP_SKIP_BRANDS):
                    logger.debug(f"    🚫 Depop skip (commonly faked brand): {item.title[:60]}")
                    self.stats["depop_fake_brand_skipped"] = self.stats.get("depop_fake_brand_skipped", 0) + 1
                    continue

            # ── Bag filter — ALL bags eliminated ──
            # Bags have high counterfeit risk and inaccurate comp matching.
            # Reject any listing that appears to be a bag/wallet/purse.
            title_lower = (item.title or "").lower()
            if any(kw in title_lower for kw in _BAG_KEYWORDS):
                logger.debug(f"    🚫 Bag listing rejected: {item.title[:60]}")
                self.stats["bag_skipped"] = self.stats.get("bag_skipped", 0) + 1
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
            if item.seller and hasattr(self, 'seller_manager') and self.seller_manager.is_blocked(item.seller):
                logger.debug(f"    Skipped blocklisted seller: {item.seller}")
                self.stats["blocklist_skipped"] += 1
                continue

            # ── Seller trust filter (Fix 1) ──
            seller_sales = getattr(item, "seller_sales", None)
            if item.source == "grailed" and seller_sales is not None:
                min_sales_required = 3
                if item.price >= 1000:
                    min_sales_required = 10
                elif item.price >= 500:
                    min_sales_required = 5
                if seller_sales < min_sales_required:
                    logger.info(f"    ⚠️ Low-trust seller '{item.seller}' ({seller_sales} sales, need {min_sales_required} for ${item.price:.0f}): {item.title[:50]}")
                    self.stats["low_trust_skipped"] += 1
                    query_metrics["low_trust_skips"] += 1
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
            # Skip for Grailed — all items are purchase-verified
            if item.source not in {"grailed", "therealreal", "fashionphile"} and self._check_rep_price_ceiling(query, item.price, item.title):
                logger.info(f"    🚫 Below rep price ceiling — likely fake: ${item.price:.0f} for '{query}' — {item.title[:60]}")
                self.stats["rep_ceiling_skipped"] += 1
                query_metrics["rep_ceiling_skips"] += 1
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
            # Stronger brand phrase and category matching to cut keyword-stuffed junk.
            query_words = query.lower().split()
            title_lower_check = item.title.lower()

            brand_in_title = self._query_brand_in_title(query, title_lower_check)

            # For Japanese Mercari (jp.mercari.com), check for Japanese brand names or Chrome Hearts mention
            is_jp_mercari = "jp.mercari.com" in item.url or (hasattr(item, 'raw_data') and 'jp.mercari.com' in str(item.raw_data))
            if is_jp_mercari and not brand_in_title:
                # Check for Japanese Chrome Hearts name or common CH indicators
                jp_brand_indicators = ['クロムハーツ', 'chrome hearts', 'ｸﾛﾑﾊｰﾂ']
                has_jp_brand = any(ind in title_lower_check for ind in jp_brand_indicators)
                if has_jp_brand:
                    brand_in_title = True
                    logger.debug(f"    Japanese brand match for '{query}': {item.title[:50]}")

            if not brand_in_title:
                logger.debug(f"    Skipped brand mismatch for '{query}': {item.title[:50]}")
                query_metrics["brand_mismatch_skips"] += 1
                continue

            if not is_jp_mercari and not self._query_category_matches_title(query, title_lower_check):
                logger.debug(f"    Skipped category mismatch for '{query}': {item.title[:50]}")
                query_metrics["category_mismatch_skips"] += 1
                continue

            # Require at least 2 query words to appear in the title (not just 1 brand word)
            # For Japanese Mercari, relax this to 1 word since titles are in Japanese
            min_matching_words = 1 if is_jp_mercari else 2
            matching_words = sum(1 for word in query_words if word in title_lower_check)

            # Also check for Japanese category words as valid matches
            if is_jp_mercari:
                jp_category_words = {
                    'ring': ['リング', '指輪'],
                    'necklace': ['ネックレス', 'ペンダント'],
                    'bracelet': ['ブレスレット'],
                    'pendant': ['ペンダント'],
                    'earring': ['ピアス', 'イヤリング'],
                    'chain': ['チェーン'],
                }
                for qw in query_words:
                    if qw in jp_category_words:
                        if any(jp_word in title_lower_check for jp_word in jp_category_words[qw]):
                            matching_words += 1

            if matching_words < min_matching_words:
                logger.debug(f"    Skipped poor match: only {matching_words}/{min_matching_words}+ words match for '{query}' - {item.title[:50]}")
                continue

            # ── Product fingerprint category mismatch check ──
            # Prevent cross-category alerts (e.g., bag listing for a shoe query)
            try:
                if detected_brand:
                    from scrapers.comp_matcher import parse_title as cm_parse_title
                    query_parsed = cm_parse_title(detected_brand, query)
                    item_parsed = cm_parse_title(detected_brand, item.title)
                    if query_parsed.item_type and item_parsed.item_type and query_parsed.item_type != item_parsed.item_type:
                        logger.info(f"    🔍 Category mismatch: query={query_parsed.item_type}, item={item_parsed.item_type} — {item.title[:50]}")
                        query_metrics["category_mismatch_skips"] += 1
                        continue
            except Exception:
                pass

            # Add minimum title similarity check - at least 40% of query words should match
            # For Japanese Mercari, use lower threshold since titles are in Japanese
            min_similarity = 0.25 if is_jp_mercari else 0.40
            similarity_ratio = matching_words / len(query_words)
            if similarity_ratio < min_similarity:
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
                from datetime import timezone
                listing_age_days = (datetime.now(timezone.utc) - item.listed_at).days
                if listing_age_days > 14:
                    logger.debug(f"    Skipped stale listing ({listing_age_days}d old): {item.title[:50]}")
                    self.stats.setdefault("stale_skipped", 0)
                    self.stats["stale_skipped"] += 1
                    query_metrics["stale_skips"] += 1
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
            if photo_count > 0 and photo_count < 2:
                logger.debug(f"    Skipped low photos ({photo_count}): {item.title[:50]}")
                continue

            # ── Gender mismatch filter ──
            # Women's items have different pricing than men's. If listing is
            # explicitly women's but query/comps are men's, skip to avoid inflated profits.
            _WOMENS_KEYWORDS = {"women's", "womens", "woman's", "ladies", "femme", "donna"}
            if any(kw in title_lower for kw in _WOMENS_KEYWORDS):
                query_lower_check = query.lower()
                if not any(kw in query_lower_check for kw in _WOMENS_KEYWORDS):
                    logger.info(f"    🚫 Women's item matched to men's query: {item.title[:50]}")
                    self.stats.setdefault("gender_mismatch_skipped", 0)
                    self.stats["gender_mismatch_skipped"] += 1
                    continue

            # ── Brand whitelist ──
            # Only allow items from brands we actually track. Prevents random
            # Poshmark results (Lululemon, Harley Davidson, etc.) from leaking through.
            # (detected_brand already set above, before bag/depop filters)
            if not detected_brand:
                logger.debug(f"    Skipped unknown brand: {item.title[:50]}")
                continue

            # ── Per-item comp lookup: get sold data specific to THIS listing ──
            effective_sold, item_comp_query, is_item_specific = await self.get_item_specific_comps(
                item, detected_brand, sold_data
            )
            if is_item_specific:
                self.stats["item_specific_comp_hits"] = self.stats.get("item_specific_comp_hits", 0) + 1
            else:
                self.stats["item_specific_comp_misses"] = self.stats.get("item_specific_comp_misses", 0) + 1

            # Calculate gap against Grailed resale value (no platform discount).
            # We buy on any platform and resell on Grailed — the reference is what
            # the item sells for on Grailed, not what it would sell for on the source platform.
            reference_price = effective_sold.liquidation_anchor or (
                getattr(effective_sold, '_hyper_pricing', False) and effective_sold.avg_price or effective_sold.median_price
            )
            downside_reference = effective_sold.downside_anchor or (reference_price * 0.85)

            # ── Condition adjustment: if source is worse condition than comps, haircut reference ──
            source_condition, _, _ = parse_condition(item.title, brand=detected_brand or "")
            from core.condition_parser import CONDITION_TIERS
            source_mult = CONDITION_TIERS.get(source_condition, 0.70)  # Default GENTLY_USED
            # Comps are mostly GENTLY_USED on Grailed; if source is worse, reduce reference
            comp_assumed_mult = 0.70  # Grailed comps average condition
            if source_mult < comp_assumed_mult and comp_assumed_mult > 0:
                condition_ratio = source_mult / comp_assumed_mult
                reference_price *= condition_ratio
                downside_reference *= condition_ratio
                logger.debug(f"    Condition adjustment: {source_condition} ({source_mult}) vs comps ({comp_assumed_mult}) → {condition_ratio:.2f}x")

            # ── Seasonal pricing: haircut for off-season items ──
            current_month = datetime.now().month
            title_lower = item.title.lower() if item.title else ""
            cat_lower = (item.category or "").lower()
            combined_text = title_lower + " " + cat_lower
            # Winter items (outerwear, heavy knits) are off-season April-August
            winter_keywords = ("jacket", "coat", "parka", "anorak", "puffer", "down vest", "heavy knit", "sherpa")
            # Summer items are off-season October-February
            summer_keywords = ("swim", "tank top", "linen short", "sandal")
            is_winter_item = any(k in combined_text for k in winter_keywords)
            is_summer_item = any(k in combined_text for k in summer_keywords)
            off_season = (is_winter_item and 4 <= current_month <= 8) or (is_summer_item and (current_month >= 10 or current_month <= 2))
            if off_season:
                reference_price *= 0.85
                downside_reference *= 0.85
                logger.debug(f"    Seasonal haircut: -15% (off-season {'winter' if is_winter_item else 'summer'} item)")

            gap = reference_price - item.price
            gap_percent = gap / reference_price if reference_price > 0 else 0

            # Profit estimate: resell at reference price minus platform fees + shipping
            sell_fee_rate = DEFAULT_SELL_FEE
            sell_multiplier = 1.0 - sell_fee_rate
            expected_sell_price = reference_price * sell_multiplier
            downside_sell_price = downside_reference * sell_multiplier
            shipping_est = estimate_shipping(item, reference_price=reference_price) * 1.20  # 20% buffer
            profit = expected_sell_price - item.price - shipping_est
            downside_profit = downside_sell_price - item.price - shipping_est
            real_margin = profit / item.price if item.price > 0 else 0

            # ── Implausible gap sanity check ──────────────────────────────────
            # A listing >90% below a $200+ market is virtually never a real deal —
            # it's a wrong match (keyword stuffing, different category entirely).
            # Both the $13 Dr. Martens and extreme Vinted outliers are caught here.
            if gap_percent >= IMPLAUSIBLE_GAP_CAP and effective_sold.median_price >= IMPLAUSIBLE_GAP_MIN_MARKET:
                logger.info(
                    f"    🚫 Implausible gap {gap_percent*100:.0f}% on ${effective_sold.median_price:.0f} market "
                    f"(listed ${item.price:.0f}) — likely wrong match: {item.title[:50]}"
                )
                self.stats.setdefault("implausible_gap_skipped", 0)
                self.stats["implausible_gap_skipped"] += 1
                query_metrics["implausible_gap_skips"] += 1
                continue

            # 3-tier confidence-gated thresholds
            comp_confidence = getattr(effective_sold, '_confidence', 'medium')
            comp_cv = getattr(effective_sold, '_cv', None)
            effective_min_profit = MIN_PROFIT_DOLLARS
            if comp_confidence == "high" and (comp_cv is None or comp_cv < 0.5):
                effective_min_gap = MIN_GAP_PERCENT * 0.83  # ~25% for high confidence
            elif comp_confidence == "low":
                effective_min_gap = MIN_GAP_PERCENT * 1.33  # ~40% for low confidence
            else:
                effective_min_gap = MIN_GAP_PERCENT * 1.07  # ~32% for medium

            # Lower profit threshold for liquid items (high comp count + safe downside)
            if effective_sold.count >= 12 and downside_profit > 30:
                effective_min_profit = 50.0

            if gap_percent >= effective_min_gap and profit >= effective_min_profit:
                pricing_conf = (effective_sold.pricing_confidence or getattr(effective_sold, '_confidence', 'medium')).lower()
                pricing_bonus = {"high": 12.0, "medium": 6.0, "low": 0.0}.get(pricing_conf, 0.0)
                downside_bonus = max(0.0, downside_profit) * 0.10
                mos_score = max(0.0, downside_profit) + pricing_bonus + downside_bonus

                # Build comp snapshots with full identity for direct persistence
                _titles = getattr(effective_sold, 'comp_titles', None) or []
                _prices = getattr(effective_sold, 'comp_prices', None) or []
                _urls = getattr(effective_sold, 'comp_urls', None) or []
                _sources = getattr(effective_sold, 'comp_sources', None) or []
                _source_ids = getattr(effective_sold, 'comp_source_ids', None) or []
                _conditions = getattr(effective_sold, 'comp_conditions', None) or []
                _sold_dates = getattr(effective_sold, 'comp_sold_dates', None) or []
                _phashes = getattr(effective_sold, 'comp_phashes', None) or []
                _image_urls = getattr(effective_sold, 'comp_image_urls', None) or []
                _sim_scores = getattr(effective_sold, '_similarity_scores', None) or []
                _snapshots = []
                for _i, _t in enumerate(_titles[:10]):
                    _snapshots.append({
                        "title": _t,
                        "price": _prices[_i] if _i < len(_prices) else effective_sold.avg_price,
                        "url": _urls[_i] if _i < len(_urls) else None,
                        "source": _sources[_i] if _i < len(_sources) else "grailed",
                        "source_id": _source_ids[_i] if _i < len(_source_ids) else "",
                        "condition": _conditions[_i] if _i < len(_conditions) else None,
                        "sold_date": _sold_dates[_i] if _i < len(_sold_dates) else None,
                        "phash": _phashes[_i] if _i < len(_phashes) else None,
                        "image_url": _image_urls[_i] if _i < len(_image_urls) else None,
                        "similarity_score": _sim_scores[_i] if _i < len(_sim_scores) else None,
                    })

                deals.append(GapDeal(
                    item=item,
                    sold_avg=effective_sold.avg_price,
                    gap_percent=gap_percent,
                    profit_estimate=profit,
                    sold_count=effective_sold.count,
                    query=item_comp_query if is_item_specific else query,
                    comp_confidence=getattr(effective_sold, '_confidence', 'medium'),
                    comp_confidence_level=getattr(effective_sold, '_confidence_level', getattr(effective_sold, '_confidence', 'medium')),
                    comp_cv=getattr(effective_sold, '_cv', None),
                    authenticated_comps=getattr(effective_sold, '_authenticated_comps', 0),
                    comp_auth_confidence=getattr(effective_sold, '_auth_confidence', 0.0),
                    hyper_pricing=getattr(effective_sold, '_hyper_pricing', False),
                    comp_confidence_penalty=getattr(effective_sold, 'comp_confidence_penalty', 0),
                    liquidation_anchor=reference_price,
                    downside_anchor=downside_reference,
                    expected_net_profit=profit,
                    downside_net_profit=downside_profit,
                    margin_of_safety_score=mos_score,
                    discovered_at=datetime.now(),
                    comp_snapshots=_snapshots,
                    similarity_scores=getattr(effective_sold, '_similarity_scores', None),
                ))
            else:
                if debug_near_misses:
                    closeness = max(
                        gap_percent / effective_min_gap if effective_min_gap > 0 else 0.0,
                        profit / effective_min_profit if effective_min_profit > 0 else 0.0,
                        downside_profit / max(1.0, effective_min_profit * 0.35),
                    )
                    if closeness >= 0.65:
                        pricing_conf = (effective_sold.pricing_confidence or getattr(effective_sold, '_confidence', 'medium')).lower()
                        pricing_bonus = {"high": 12.0, "medium": 6.0, "low": 0.0}.get(pricing_conf, 0.0)
                        downside_bonus = max(0.0, downside_profit) * 0.10
                        mos_score = max(0.0, downside_profit) + pricing_bonus + downside_bonus
                        near_misses.append({
                            "source": item.source,
                            "price": item.price,
                            "gap_percent": gap_percent,
                            "profit": profit,
                            "downside_profit": downside_profit,
                            "liquidation_anchor": reference_price,
                            "downside_anchor": downside_reference,
                            "mos": mos_score,
                            "title": item.title[:80],
                        })

                # Debug: Log why item didn't make the cut
                if gap_percent >= 0.20:  # Only log items that were close
                    logger.debug(f"    ⏭ Below threshold: {item.source} ${item.price:.0f} → gap {gap_percent*100:.0f}% (need {effective_min_gap*100:.0f}%), profit ${profit:.0f} (need ${effective_min_profit:.0f}), downside ${downside_profit:.0f} - {item.title[:40]}")

        query_metrics["post_filter_candidates"] = len(deals)
        self._last_query_metrics = dict(query_metrics)

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

        # Debug: Summary of filtering for this query
        if not deals:
            logger.info(f"    📊 Filter summary for '{query}':")
            logger.info(f"      - Items after recency filter: {len(all_items)}")
            logger.info(f"      - Stale skipped: {self.stats.get('stale_skipped', 0)}")
            logger.info(f"      - Price drop skipped: {self.stats.get('price_drop_skipped', 0)}")
            logger.info(f"      - Brand mismatch skipped: {query_metrics.get('brand_mismatch_skips', 0)}")
            logger.info(f"      - Category mismatch skipped: {query_metrics.get('category_mismatch_skips', 0)}")
            logger.info(f"      - Rep ceiling skipped: {self.stats.get('rep_ceiling_skipped', 0)}")
            logger.info(f"      - Low trust skipped: {self.stats.get('low_trust_skipped', 0)}")
            logger.info(f"      - Implausible gap skipped: {self.stats.get('implausible_gap_skipped', 0)}")
            logger.info(f"      - Deals passed all filters: 0")
            if debug_near_misses and near_misses:
                near_misses.sort(key=lambda x: (x['mos'], x['downside_profit'], x['profit']), reverse=True)
                logger.info(f"      - Top near-misses ({min(5, len(near_misses))} shown):")
                for nm in near_misses[:5]:
                    logger.info(
                        f"        · {nm['source']} ${nm['price']:.0f} | gap {nm['gap_percent']*100:.0f}% | "
                        f"profit ${nm['profit']:.0f} | downside ${nm['downside_profit']:.0f} | "
                        f"liq ${nm['liquidation_anchor']:.0f} | down ${nm['downside_anchor']:.0f} | MOS {nm['mos']:.0f} | "
                        f"{nm['title'][:55]}"
                    )
        else:
            logger.info(f"    📊 {len(deals)} deals passed all filters for '{query}'")

        deals.sort(key=lambda d: (d.margin_of_safety_score, d.downside_net_profit, d.profit_estimate), reverse=True)
        query_metrics["post_filter_candidates"] = len(deals)
        self._last_query_metrics = dict(query_metrics)
        return deals

    async def process_deal(self, deal: GapDeal, is_japan_deal: bool = False) -> bool:
        """Auth check, quality score, and send a gap deal."""
        item = deal.item
        brand = self._detect_brand(item.title)
        category = self._detect_category(item.title)
        
        # ── Japan Deal Special Handling ──
        if is_japan_deal and hasattr(item, '_japan_data'):
            japan_data = item._japan_data
            # Handle both dataclass and dict formats
            if isinstance(japan_data, dict):
                brand = japan_data.get('brand', 'Unknown')
                title = japan_data.get('title', '')[:30]
                recommendation = japan_data.get('recommendation', '')
                net_profit = japan_data.get('net_profit', 0)
                margin_percent = japan_data.get('margin_percent', 0)
                item_price_jpy = japan_data.get('item_price_jpy', 0)
                item_price_usd = japan_data.get('item_price_usd', 0)
                total_landed_cost = japan_data.get('total_landed_cost', 0)
                us_market_price = japan_data.get('us_market_price', 0)
                proxy_service = japan_data.get('proxy_service', 'Buyee')
                shipping_method = japan_data.get('shipping_method', 'EMS')
                auction_url = japan_data.get('auction_url', '')
                image_url = japan_data.get('image_url', '')
                category = japan_data.get('category', '')
                bids = japan_data.get('bids', 0)
                end_time = japan_data.get('end_time')
            else:
                # Dataclass format
                brand = japan_data.brand
                title = japan_data.title[:30]
                recommendation = japan_data.recommendation
                net_profit = japan_data.net_profit
                margin_percent = japan_data.margin_percent
                item_price_jpy = japan_data.item_price_jpy
                item_price_usd = japan_data.item_price_usd
                total_landed_cost = japan_data.total_landed_cost
                us_market_price = japan_data.us_market_price
                proxy_service = japan_data.proxy_service
                shipping_method = japan_data.shipping_method
                auction_url = japan_data.auction_url
                image_url = japan_data.image_url
                category = japan_data.category
                bids = japan_data.bids
                end_time = japan_data.end_time
            
            # Apply 5% forex risk buffer to Japan profit estimates
            net_profit = net_profit * 0.95
            margin_percent = margin_percent * 0.95

            logger.info(f"    🗾 Processing Japan deal: {brand} {title}...")

            # Japan deals use pre-authenticated proxy services — set auth confidence to 0.80
            auth_result = None
            auth_conf = 0.80

            # Calculate quality score using the same pipeline as non-Japan deals
            quality_score, signals = calculate_deal_quality(
                item=item,
                brand=brand,
                sold_data=deal,
                gap_percent=margin_percent / 100,
                profit=net_profit,
                auth_confidence=auth_conf,
            )
            # Apply comp confidence penalty from validation
            comp_confidence_penalty = getattr(deal, 'comp_confidence_penalty', 0)
            quality_score = max(0, quality_score - comp_confidence_penalty)
            if comp_confidence_penalty > 0:
                logger.info(f"  📉 Comp confidence penalty: -{comp_confidence_penalty} pts")
            # Override line_name for Japan deals
            signals.line_name = 'Japan Import'

            # Apply the SAME quality gates as non-Japan deals
            min_fire = int(os.getenv("GAP_MIN_FIRE_LEVEL", "2"))
            if signals.fire_level < min_fire:
                logger.info(f"    ⏭ Japan deal below quality threshold (fire={signals.fire_level} < {min_fire}): {title}")
                self.stats["quality_filtered"] += 1
                return False

            public_min_quality = int(os.getenv("DISCORD_MIN_QUALITY_SCORE", "55"))
            if quality_score < public_min_quality:
                logger.info(f"    ⏭ Japan deal below quality score ({quality_score:.0f} < {public_min_quality}): {title}")
                self.stats["public_quality_filtered"] += 1
                return False

            # Build Japan-specific message
            header = format_quality_header(signals)
            if isinstance(japan_data, dict):
                title_jp = japan_data.get('title_jp', '')
            else:
                title_jp = japan_data.title_jp
            message = (
                f"{header}\n🗾 JAPAN ARBITRAGE\n\n"
                f"<b>{title_jp}</b>\n"
                f"{title}\n\n"
                f"💵 <b>Japan Price:</b> ¥{item_price_jpy:,} (${item_price_usd:,.0f})\n"
                f"📦 <b>Landed Cost:</b> ${total_landed_cost:,.0f}\n"
                f"📊 <b>US Market:</b> ${us_market_price:,.0f}\n"
                f"💰 <b>Net Profit:</b> ${net_profit:,.0f}\n"
                f"📈 <b>Margin:</b> {margin_percent:.1f}%\n\n"
                f"🚢 <b>Proxy:</b> {proxy_service}\n"
                f"📮 <b>Shipping:</b> {shipping_method}\n"
                f"⏰ <b>Ends:</b> {end_time.strftime('%Y-%m-%d %H:%M') if hasattr(end_time, 'strftime') else 'Unknown'}\n"
                f"🔥 <b>Bids:</b> {bids}\n\n"
                f"<a href='{auction_url}'>🔗 Bid on Buyee</a>"
            )

        # ── Seller trust re-check (scales with item price) ──
        if not is_japan_deal:
            seller_sales = getattr(item, "seller_sales", None)
            if seller_sales is not None and item.source == "grailed":
                # Higher-value items require more seller history
                min_sales = 3
                if item.price >= 1000:
                    min_sales = 10
                elif item.price >= 500:
                    min_sales = 5
                if seller_sales < min_sales:
                    logger.info(f"    🚫 Low-trust seller ({seller_sales} sales, need {min_sales} for ${item.price:.0f} item): {item.title[:50]}")
                    self.stats["low_trust_skipped"] += 1
                    return False

        # Auth check (skip for Japan deals — already handled above)
        if not is_japan_deal:
            try:
                auth_result = await asyncio.wait_for(
                    self.auth.check(
                        title=item.title,
                        description=item.description or "",
                        price=item.price,
                        brand=brand,
                        category=category,
                        seller_name=item.seller or "",
                        seller_sales=getattr(item, "seller_sales", 0) or 0,
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

        # ── Validation engine — runs for ALL deals (Japan + non-Japan) ──
        sold_data_for_deal = self.sold_cache.get(deal.query)
        v_comp_titles = getattr(sold_data_for_deal, 'comp_titles', None) if sold_data_for_deal else None
        v_comp_sizes = getattr(sold_data_for_deal, 'comp_sizes', None) if sold_data_for_deal else None
        listing_size = getattr(item, 'size', None)

        validation_results = self.validation.validate(
            listing_title=item.title,
            comp_titles=v_comp_titles,
            listing_size=listing_size,
            comp_sizes=v_comp_sizes,
            listing_price=item.price,
            comp_avg_price=deal.sold_avg,
            query=deal.query,
        )
        for vr in validation_results:
            if not vr.passed:
                logger.info(
                    f"    🚫 Validation blocked ({vr.check_name}): {vr.reason} — {item.title[:50]}"
                )
                self.stats["validation_engine_blocked"] = self.stats.get("validation_engine_blocked", 0) + 1
                return False

        # ── Defaults for gate variables (overridden in non-Japan block) ──
        deal_comp_conf = getattr(deal, "comp_confidence_level", None) or getattr(deal, "comp_confidence", "medium")
        deal_comp_cv = getattr(deal, "comp_cv", None)
        deal_auth_comps = getattr(deal, "authenticated_comps", 0)
        deal_auth_conf = getattr(deal, "comp_auth_confidence", 0.0)
        public_min_auth = float(os.getenv("DISCORD_MIN_AUTH_CONFIDENCE", "0.72"))
        public_max_cv = float(os.getenv("DISCORD_MAX_COMP_CV", "0.90"))

        # ── Non-Japan only: quality scoring and remaining gates ──
        # Japan deals already ran quality gates above.
        if not is_japan_deal:
            # Calculate deal quality score
            if auth_result:
                auth_conf = auth_result.confidence
            elif item.source in {"grailed", "therealreal", "fashionphile"}:
                auth_conf = 0.80
            else:
                auth_conf = 0.5
            quality_score, signals = calculate_deal_quality(
                item=item,
                brand=brand,
                sold_data=deal,
                gap_percent=deal.gap_percent,
                profit=deal.profit_estimate,
                auth_confidence=auth_conf,
            )
            # Apply comp confidence penalty from validation
            comp_confidence_penalty = getattr(deal, 'comp_confidence_penalty', 0)
            quality_score = max(0, quality_score - comp_confidence_penalty)
            if comp_confidence_penalty > 0:
                logger.info(f"  📉 Comp confidence penalty: -{comp_confidence_penalty} pts")

            # Fire level gate
            min_fire = int(os.getenv("GAP_MIN_FIRE_LEVEL", "2"))
            if signals.fire_level < min_fire:
                logger.info(
                    f"    ⏭ Below quality threshold ({quality_score:.0f}/100, fire={signals.fire_level} < {min_fire}): {item.title[:50]}"
                )
                self.stats["quality_filtered"] += 1
                return False

            # Quality score gate
            public_min_quality = int(os.getenv("DISCORD_MIN_QUALITY_SCORE", "55"))
            public_min_auth = float(os.getenv("DISCORD_MIN_AUTH_CONFIDENCE", "0.72"))
            public_max_cv = float(os.getenv("DISCORD_MAX_COMP_CV", "0.90"))
            public_min_downside_profit = float(os.getenv("DISCORD_MIN_DOWNSIDE_PROFIT", "25"))
            allow_medium_comp = os.getenv("DISCORD_ALLOW_MEDIUM_COMP_CONFIDENCE", "0") == "1"

            deal_comp_conf = getattr(deal, "comp_confidence_level", None) or getattr(deal, "comp_confidence", "medium")
            deal_comp_cv = getattr(deal, "comp_cv", None)
            deal_auth_comps = getattr(deal, "authenticated_comps", 0)
            deal_auth_conf = getattr(deal, "comp_auth_confidence", 0.0)

            if quality_score < public_min_quality:
                logger.info(f"    ⏭ Public-send gate: score {quality_score:.0f} < {public_min_quality} — {item.title[:50]}")
                self.stats["public_quality_filtered"] += 1
                return False

            if deal.downside_net_profit < public_min_downside_profit:
                logger.info(
                    f"    ⏭ Public-send gate: downside profit ${deal.downside_net_profit:.0f} < ${public_min_downside_profit:.0f} — {item.title[:50]}"
                )
                self.stats["public_quality_filtered"] += 1
                return False

        # Skip auth gate for pre-authenticated platforms (Grailed, TheRealReal, Fashionphile)
        pre_auth_sources = {"grailed", "therealreal", "fashionphile"}
        if auth_result and auth_result.confidence < public_min_auth and item.source not in pre_auth_sources:
            logger.info(
                f"    ⏭ Public-send gate: auth {auth_result.confidence:.0%} < {public_min_auth:.0%} on {item.source} — {item.title[:50]}"
            )
            self.stats["public_auth_filtered"] += 1
            return False

        if deal_comp_conf == "low":
            logger.info(f"    ⏭ Public-send gate: low comp confidence — {item.title[:50]}")
            self.stats["public_comp_filtered"] += 1
            return False

        if deal_comp_conf == "medium" and not allow_medium_comp and signals.fire_level < 3:
            logger.info(
                f"    ⏭ Public-send gate: medium comp confidence requires 🔥🔥🔥 — {item.title[:50]}"
            )
            self.stats["public_comp_filtered"] += 1
            return False

        if deal_comp_cv is not None and deal_comp_cv > public_max_cv:
            logger.info(
                f"    ⏭ Public-send gate: comp CV {deal_comp_cv:.2f} > {public_max_cv:.2f} — {item.title[:50]}"
            )
            self.stats["public_comp_filtered"] += 1
            return False

        if deal_auth_comps < 2 and deal_auth_conf < 0.65 and signals.fire_level < 2:
            logger.info(
                f"    ⏭ Public-send gate: weak sold-comp auth ({deal_auth_comps} authenticated, {deal_auth_conf:.0%} confidence) — {item.title[:50]}"
            )
            self.stats["public_comp_filtered"] += 1
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
            f"🧱 Liquidation: <b>${deal.liquidation_anchor:.0f}</b> · downside <b>${deal.downside_anchor:.0f}</b>",
            f"💰 Est. Profit: <b>${deal.expected_net_profit:.0f}</b> · downside <b>${deal.downside_net_profit:.0f}</b>",
            f"🛡 MOS: <b>{deal.margin_of_safety_score:.0f}</b>",
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

            # Determine subscription tier routing for this deal
            tier_decision = classify_discord_tiers(
                item,
                deal.profit_estimate,
                deal.gap_percent,
                signals=signals,
                auth_result=auth_result,
            )
            logger.info(
                f"    📊 Deal tier decision: {tier_decision.minimum_tier} -> {tier_decision.channel_tiers} "
                f"(profit: ${deal.expected_net_profit:.0f}, downside: ${deal.downside_net_profit:.0f}, MOS: {deal.margin_of_safety_score:.0f}, margin: {deal.gap_percent*100:.0f}%)"
            )
            
            # Post to Discord using nested entitlement routing
            if DISCORD_ENABLED and tier_decision.channel_tiers:
                try:
                    await send_discord_alert(
                        item=item,
                        message=message,
                        fire_level=signals.fire_level,
                        signals=signals,
                        auth_result=auth_result,
                        tier=tier_decision.minimum_tier or "beginner",
                        tiers=tier_decision.channel_tiers,
                    )
                except Exception as e:
                    logger.warning(f"Discord alert failed: {e}")

            # Post to Whop
            try:
                whop_title = f"🔥 Gap Deal: {item.title[:60]} | {deal.gap_percent*100:.0f}% below market"
                signal_lines = [
                    f"- Auth confidence: {auth_result.confidence*100:.0f}%" if auth_result else "- Auth confidence: N/A",
                    f"- Fire level: {'🔥' * signals.fire_level}" if signals.fire_level else "- Fire level: —",
                    f"- Liquidation anchor: ${deal.liquidation_anchor:.0f}",
                    f"- Downside anchor: ${deal.downside_anchor:.0f}",
                    f"- Expected net profit: ${deal.expected_net_profit:.0f}",
                    f"- Downside net profit: ${deal.downside_net_profit:.0f}",
                    f"- Margin of safety: {deal.margin_of_safety_score:.0f}",
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

            # Persist deal to DB for frontend display
            try:
                import hashlib
                url_hash = hashlib.md5(item.url.encode()).hexdigest()[:12] if item.url else ""
                source_id = f"gap_{url_hash}"

                db_item = DbItem(
                    source=item.source,
                    source_id=source_id,
                    source_url=item.url,
                    title=item.title,
                    brand=brand,
                    category=category,
                    size=getattr(item, 'size', None),
                    condition=getattr(item, 'condition', None),
                    source_price=item.price,
                    source_shipping=0.0,
                    market_price=deal.sold_avg,
                    our_price=deal.sold_avg,
                    margin_percent=deal.gap_percent * 100,
                    images=item.images or [],
                    is_auction=getattr(item, 'is_auction', False),
                    status="active",
                )
                persisted_id = db_save_item(db_item)

                grade = _map_grade(signals.fire_level, quality_score)
                grade_reasoning = (
                    f"Gap Hunter: {signals.fire_level} fire, "
                    f"score {quality_score:.0f}/100, "
                    f"{deal.sold_count} comps, "
                    f"${deal.profit_estimate:.0f} profit"
                )

                update_item_qualification(
                    item_id=persisted_id,
                    grade=grade,
                    grade_reasoning=grade_reasoning,
                    demand_score=getattr(signals, 'liquidity_score', 5) / 10,
                    sell_through_days=getattr(signals, 'avg_days_to_sell', 0) or 0,
                    comp_count=deal.sold_count,
                    our_price=deal.sold_avg,
                    margin_percent=deal.gap_percent * 100,
                )

                # Set exact pricing fields
                from db.sqlite_models import _get_conn
                conn = _get_conn()
                try:
                    conn.execute(
                        """UPDATE items SET
                            exact_sell_price=?, exact_profit=?, exact_margin=?,
                            demand_level=?, sold_count=?
                        WHERE id=?""",
                        (
                            deal.sold_avg,
                            deal.expected_net_profit,
                            deal.gap_percent * 100,
                            "hot" if signals.fire_level >= 3 else "warm" if signals.fire_level >= 2 else "cold",
                            deal.sold_count,
                            persisted_id,
                        ),
                    )
                    conn.commit()
                finally:
                    conn.close()

                # Ensure every scored comp has a sold_comps row so persist_scored_comps() can resolve them
                from db.sqlite_models import persist_scored_comps, link_item_to_sold_comps, save_sold_comp
                if deal.comp_snapshots:
                    for snap in deal.comp_snapshots:
                        if snap.get("source_id"):
                            sold_date = snap.get("sold_date")
                            if sold_date is not None and not isinstance(sold_date, str):
                                try:
                                    sold_date = sold_date.isoformat()
                                except (AttributeError, TypeError):
                                    sold_date = str(sold_date) if sold_date else None
                            save_sold_comp(deal.query, {
                                "source": snap.get("source", "grailed"),
                                "source_id": snap.get("source_id"),
                                "title": snap.get("title"),
                                "brand": brand,
                                "sold_price": snap.get("price"),
                                "sold_url": snap.get("url"),
                                "condition": snap.get("condition"),
                                "sold_date": sold_date,
                                "image_url": snap.get("image_url"),
                            })
                    comp_count_saved = persist_scored_comps(persisted_id, deal.comp_snapshots)
                    if comp_count_saved == 0:
                        logger.warning(f"    ⚠️ No scored comps resolved — falling back to DB search")
                        comp_count_saved = link_item_to_sold_comps(persisted_id, deal.query)
                else:
                    comp_count_saved = link_item_to_sold_comps(persisted_id, deal.query)
                    if comp_count_saved == 0:
                        comp_count_saved = link_item_to_sold_comps(persisted_id, brand or "")

                logger.info(f"    💾 Persisted to DB: item #{persisted_id}, grade {grade}, {comp_count_saved} comps [v2-snapshots]")
            except Exception as e:
                logger.warning(f"    ⚠️ DB persist failed: {e}")

            # Track deal prediction for accuracy analysis
            try:
                is_hyper = getattr(deal, '_hyper_pricing', False) or getattr(sold_data, '_hyper_pricing', False)
                cv = getattr(sold_data, '_cv', None)
                confidence = getattr(sold_data, '_confidence_level', None)
                
                prediction = DealPrediction(
                    timestamp=datetime.now().isoformat(),
                    query=deal.query,
                    item_title=item.title,
                    item_url=item.url,
                    predicted_price=deal.sold_avg,
                    prediction_method="hyper" if is_hyper else "standard",
                    cv=cv,
                    confidence_level=confidence,
                    num_comps=deal.sold_count,
                    buy_price=item.price,
                    buy_platform=item.source,
                    sell_platform=DEFAULT_SELL_PLATFORM,
                    estimated_profit=deal.expected_net_profit,
                    estimated_fees=deal.sold_avg * DEFAULT_SELL_FEE,
                )
                record_prediction(prediction)
                logger.debug(f"Tracked deal prediction for accuracy analysis")
            except Exception as e:
                logger.debug(f"Failed to track deal prediction: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Send failed: {e}")
            return False

    async def run_cycle(self, brand_filter=None, custom_queries=None, max_targets=None, source_filter=None, use_blue_chip=False, customer_tier="intermediate", skip_japan: bool = False):
        """Run one hunting cycle.
        
        Args:
            use_blue_chip: If True, prioritize blue-chip luxury targets
            customer_tier: 'beginner', 'intermediate', or 'expert' for target filtering
        """
        self.cycle_count += 1
        self.cycles_since_prune += 1
        self._item_comp_cache.clear()  # Fresh per-item comp cache each cycle
        # Note: _raw_items_cache NOT cleared here — its lifecycle matches sold_cache
        # (TTL-based expiry). Clearing it would break weighted pricing on cached queries.
        cycle_start = time.time()
        
        # ── Periodic data pruning ──
        if self.cycles_since_prune >= 10:
            logger.info("🧹 Running periodic data pruning...")
            try:
                if hasattr(self, 'data_manager'):
                    results = self.data_manager.prune_all()
                    total_removed = sum(r.get('removed', 0) for r in results.values() if isinstance(r.get('removed'), int))
                    if total_removed > 0:
                        logger.info(f"🧹 Pruned {total_removed} old entries from data files")
            except Exception as e:
                logger.warning(f"Data pruning failed: {e}")
            self.cycles_since_prune = 0

        # ── Target Selection ──
        targets = []
        
        # Option 1: Blue-chip targets (high-value luxury focus)
        if use_blue_chip:
            blue_chip_targets = get_targets_by_tier(customer_tier)
            targets = [t.query for t in blue_chip_targets]
            logger.info(f"💎 Using {len(targets)} blue-chip targets ({customer_tier} tier)")
            
            # Log blue-chip stats
            stats = get_target_stats()
            logger.info(f"   📊 Blue-chip stats: {stats['watches']} watches, {stats['bags']} bags, "
                       f"{stats['jewelry']} jewelry, avg margin {stats['avg_margin']:.1%}")
        
        # Option 2: Dynamic targets from TrendEngine
        else:
            from trend_engine import CORE_TARGETS
            targets = CORE_TARGETS  # safety fallback
            trend_engine = _get_trend_engine()
            if trend_engine:
                try:
                    dynamic = await trend_engine.get_cycle_targets(n=25)
                    if dynamic:
                        targets = dynamic
                        logger.info(f"🔥 {len(targets)} targets this cycle (varied rotation)")
                except Exception as e:
                    logger.warning(f"⚠️ TrendEngine failed, running on {len(targets)} core targets: {e}")
        
        # Ensure trend_engine is defined for later use
        if 'trend_engine' not in locals():
            trend_engine = None

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

        # Load query tier info for cycle logging
        _tier_labels = {}
        try:
            from core.query_tiering import classify_query, QueryTier
            te = _get_trend_engine()
            if te:
                _perf = te._load_performance()
                for q in targets:
                    entry = _perf.get(q) or _perf.get(q.lower())
                    result = classify_query(q, entry)
                    _tier_labels[q] = result.tier.value
        except Exception:
            pass

        total_deals = 0

        for i, query in enumerate(targets):
            if not self.running:
                break

            # Get sold data (use hyper-accurate pricing)
            sold = await self.get_hyper_sold_data(query)
            if not sold:
                logger.debug(f"  [{i+1}] {query}: insufficient sold data")
                continue

            # Log whether we're using hyper-pricing or standard
            is_hyper = getattr(sold, '_hyper_pricing', False)
            price_type = "💎 hyper" if is_hyper else "standard"
            tier_tag = _tier_labels.get(query, "B")
            logger.info(f"  [{i+1}/{len(targets)}] [{tier_tag}] {query} - {price_type} avg: ${sold.avg_price:.0f} ({sold.count} comps)")

            # Find gaps
            gaps = await self.find_gaps(query, sold)
            
            # Debug: Log why no gaps were found
            if not gaps:
                logger.info(f"    📊 No gaps found for '{query}' - checking filter stats...")

            query_alerts_sent = 0
            query_validation_failed = 0
            for deal in gaps:
                logger.info(
                    f"    💰 ${deal.item.price:.0f} → ${deal.sold_avg:.0f} "
                    f"(gap {deal.gap_percent*100:.0f}%, +${deal.expected_net_profit:.0f}, downside +${deal.downside_net_profit:.0f}, MOS {deal.margin_of_safety_score:.0f}) "
                    f"- {deal.item.title[:50]}"
                )
                
                # ── Validate deal before alerting ──
                # Skip validation for Grailed items — purchase verification already ensures availability
                if deal.item.source != "grailed":
                    try:
                        validation = await validate_deal(deal, customer_tier="intermediate")
                        if validation.status != ValidationStatus.VALID:
                            logger.info(f"    ⚠️ Deal failed validation: {validation.reason}")
                            self.stats['validation_failed'] = self.stats.get('validation_failed', 0) + 1
                            query_validation_failed += 1
                            continue
                        
                        logger.debug(f"    ✅ Deal validated: {len(validation.checks_passed)} checks passed")
                    except Exception as e:
                        logger.warning(f"    ⚠️ Validation error (proceeding anyway): {e}")
                else:
                    logger.debug(f"    ✅ Grailed item — skipping validation (purchase verified)")
                
                if await self.process_deal(deal):
                    total_deals += 1
                    query_alerts_sent += 1

            # Log query performance for trend feedback loop
            if trend_engine:
                best_gap = max((d.gap_percent for d in gaps), default=0) if gaps else 0
                query_metrics = dict(getattr(self, '_last_query_metrics', {}) or {})
                query_metrics['public_alerts_sent'] = query_alerts_sent
                query_metrics['validation_failed'] = query_validation_failed
                try:
                    trend_engine.log_query_performance(query, len(gaps), best_gap, metrics=query_metrics)
                except Exception:
                    pass

            await asyncio.sleep(1.5)  # Rate limiting

        # ── Japan Arbitrage Scan ──
        # Run every cycle for maximum opportunity capture unless explicitly skipped
        if not skip_japan:
            logger.info("🗾 Running Japan arbitrage scan...")
            try:
                japan_deals = await find_japan_arbitrage_deals(
                    min_margin=25.0,
                    min_profit=200.0,
                )
                
                if japan_deals:
                    logger.info(f"  🎯 Found {len(japan_deals)} Japan arbitrage opportunities")
                    
                    for deal in japan_deals:
                        logger.debug(f"  Processing Japan deal: {deal.brand} {deal.title} - {deal.recommendation}")
                        if deal.recommendation in ['STRONG_BUY', 'BUY']:
                            logger.debug(f"    Deal qualifies for processing (STRONG_BUY or BUY)")
                            # Create mock item for processing
                            class MockItem:
                                def __init__(self, japan_deal):
                                    self.title = f"{japan_deal.brand} {japan_deal.title}"
                                    self.description = getattr(japan_deal, 'description', '') or ''
                                    self.price = japan_deal.total_landed_cost
                                    self.source = 'japan_buyee'
                                    self.url = japan_deal.auction_url
                                    self.images = [japan_deal.image_url] if japan_deal.image_url else []
                                    self.size = getattr(japan_deal, 'size', None)
                                    self.brand = japan_deal.brand
                                    self.category = getattr(japan_deal, 'category', '')
                                    self.seller = None
                                    self.seller_sales = None
                                    self.seller_rating = None
                                    self.raw_data = {}
                                    self._auction_hours_left = None
                                    self._japan_data = japan_deal
                            
                            # Create mock deal signals
                            class MockDeal:
                                def __init__(self, japan_deal, item):
                                    self.item = item
                                    # Use the deal title as query (not brand+title which duplicates brand)
                                    self.query = japan_deal.title.lower().strip()
                                    self.sold_avg = japan_deal.us_market_price
                                    self.gap_percent = japan_deal.margin_percent / 100
                                    self.profit_estimate = japan_deal.net_profit
                                    self.sold_count = 10  # Estimated
                                    self.comp_confidence = "high"
                                    self.comp_confidence_level = "high"
                                    self.comp_cv = None
                                    self.authenticated_comps = 0
                                    self.comp_auth_confidence = 0.0
                                    self.comp_confidence_penalty = 0
                                    self.liquidation_anchor = japan_deal.total_landed_cost
                                    self.downside_anchor = japan_deal.total_landed_cost
                                    self.expected_net_profit = japan_deal.net_profit
                                    self.downside_net_profit = japan_deal.net_profit * 0.7
                                    self.margin_of_safety_score = japan_deal.margin_percent
                                    self._hyper_pricing = False
                                    self.comp_snapshots = None  # No scored comps — use fallback linking
                                    self.similarity_scores = None
                            
                            item = MockItem(deal)
                            mock_deal = MockDeal(deal, item)
                            
                            # Process like a regular deal
                            logger.debug(f"    Calling process_deal for Japan deal...")
                            process_result = await self.process_deal(mock_deal, is_japan_deal=True)
                            logger.debug(f"    process_deal returned: {process_result}")
                            if process_result:
                                total_deals += 1
                                logger.info(f"    🗾 Japan deal sent: {deal.brand} (+${deal.net_profit:.0f})")
                            else:
                                logger.warning(f"    ⚠️ process_deal returned False for Japan deal")
                else:
                    logger.info("  📊 No Japan arbitrage opportunities this scan")
                    
            except Exception as e:
                logger.error(f"  ❌ Japan scan error: {e}")
                import traceback
                logger.debug(f"Japan scan traceback: {traceback.format_exc()}")

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
                f"item_comp_hits={self.stats.get('item_specific_comp_hits', 0)} | "
                f"item_comp_misses={self.stats.get('item_specific_comp_misses', 0)} | "
                f"seen={len(self.seen_ids)}"
            )

    async def run(self, once: bool = False, brand_filter=None, custom_queries=None, max_targets=None, source_filter=None, use_blue_chip=False, skip_japan: bool = False):
        """Main loop."""
        init_telegram_db()

        logger.info("=" * 60)
        logger.info("🎯 ARCHIVE ARBITRAGE - GAP HUNTER")
        if brand_filter:
            logger.info(f"   Brand filter: {', '.join(brand_filter)}")
        if custom_queries:
            logger.info(f"   Custom queries: {len(custom_queries)}")
        elif use_blue_chip:
            logger.info(f"   Targets: BLUE-CHIP LUXURY (High margin, authenticated)")
        else:
            logger.info(f"   Targets: dynamic (Grailed velocity + rotation, varied per cycle)")
        if max_targets:
            logger.info(f"   Max targets: {max_targets}")
        logger.info(f"   Min gap: {MIN_GAP_PERCENT*100:.0f}% below sold avg")
        logger.info(f"   Min profit: ${MIN_PROFIT_DOLLARS}")
        logger.info(f"   Min sold comps: {MIN_SOLD_COMPS}")
        logger.info(f"   Poll interval: {POLL_INTERVAL}s")
        if skip_japan:
            logger.info(f"   🗾 Japan arbitrage: SKIPPED (CLI flag)")
        else:
            logger.info(f"   🗾 Japan arbitrage: ENABLED (every cycle)")
            logger.info(f"     Platforms: Yahoo Auctions, Mercari, Rakuma (via Buyee)")
        logger.info("=" * 60)

        # ── Embedding backfill check ──
        try:
            import sqlite3 as _sq
            _dbpath = os.path.join(os.path.dirname(__file__), "data", "archive.db")
            _c = _sq.connect(_dbpath)
            _missing = _c.execute("SELECT COUNT(*) FROM sold_comps WHERE title_embedding IS NULL").fetchone()[0]
            _c.close()
            if _missing > 100:
                logger.warning(f"  ⚠️ {_missing} comps lack embeddings — run with BACKFILL_EMBEDDINGS=1")
        except Exception:
            pass

        if os.getenv("BACKFILL_EMBEDDINGS", "0") == "1":
            try:
                from scrapers.title_matcher import backfill_embeddings
                count = backfill_embeddings()
                if count > 0:
                    logger.info(f"  📦 Backfilled embeddings for {count} comps")
            except Exception as e:
                logger.warning(f"  ⚠️ Embedding backfill failed: {e}")

        while self.running:
            try:
                await self.run_cycle(
                    brand_filter=brand_filter, 
                    custom_queries=custom_queries, 
                    max_targets=max_targets, 
                    source_filter=source_filter,
                    use_blue_chip=use_blue_chip,
                    skip_japan=skip_japan,
                )
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
        if hasattr(self, '_mercari'):
            try:
                await self._mercari.close()
            except Exception:
                pass

        logger.info("Gap Hunter stopped.")

    @staticmethod
    def _detect_category(title: str) -> str:
        """Detect item category from title for auth scoring and query matching."""
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
            "eyewear": [
                "glasses", "sunglasses", "eyewear", "frames", "frame", "eyeglasses",
                "cox ucker", "box officer", "trypoleagain",
            ],
            "accessories": [
                "necklace", "ring", "bracelet", "pendant", "jewelry",
                "chain",
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
    def _brand_aliases(brand: str) -> list[str]:
        aliases = {
            "number nine": ["number nine", "number (n)ine"],
            "number (n)ine": ["number nine", "number (n)ine"],
            "jean paul gaultier": ["jean paul gaultier", "gaultier", "jpg"],
            "gaultier": ["jean paul gaultier", "gaultier", "jpg"],
            "maison margiela": ["maison margiela", "maison martin margiela", "margiela", "mmm"],
            "margiela": ["maison margiela", "maison martin margiela", "margiela", "mmm"],
            "dior homme": ["dior homme", "dior men", "christian dior"],
            "dior men": ["dior homme", "dior men", "christian dior"],
            "christian dior": ["dior homme", "dior men", "christian dior"],
            "thierry mugler": ["thierry mugler", "mugler"],
            "mugler": ["thierry mugler", "mugler"],
            "comme des garcons": ["comme des garcons", "cdg"],
            "cdg": ["comme des garcons", "cdg"],
            "takahiromiyashita": ["takahiromiyashita", "soloist"],
            "soloist": ["takahiromiyashita", "soloist"],
            "enfants riches deprimes": ["enfants riches deprimes", "erd"],
            "erd": ["enfants riches deprimes", "erd"],
        }
        return aliases.get(brand, [brand] if brand else [])

    @classmethod
    def _query_brand_in_title(cls, query: str, title: str) -> bool:
        query_brand = cls._detect_brand(query)
        if not query_brand:
            query_words = query.lower().split()
            brand_words = query_words[:2] if len(query_words) >= 2 else query_words[:1]
            return any(bw in title for bw in brand_words)
        return any(alias in title for alias in cls._brand_aliases(query_brand))

    @classmethod
    def _query_category_matches_title(cls, query: str, title: str) -> bool:
        query_lower = query.lower()
        title_lower = title.lower()

        query_category = cls._detect_category(query_lower)
        if not query_category:
            if any(token in query_lower for token in ["cox ucker", "box officer", "trypoleagain"]):
                query_category = "eyewear"
            elif "gabardine" in query_lower:
                # Too ambiguous to enforce a category match yet.
                return True

        if not query_category or query_category == "accessories":
            return True

        title_category = cls._detect_category(title_lower)
        if title_category and title_category != query_category:
            return False

        if query_category == "eyewear":
            eyewear_tokens = ["glasses", "sunglasses", "eyewear", "frames", "frame", "eyeglasses", "cox ucker", "box officer", "trypoleagain"]
            return any(tok in title_lower for tok in eyewear_tokens)

        return True

    @staticmethod
    def _detect_brand(title: str) -> str:
        title_lower = title.lower()
        brands = [
            "rick owens", "chrome hearts", "raf simons", "helmut lang",
            "number nine", "number (n)ine", "undercover",
            "jean paul gaultier", "gaultier",
            "vivienne westwood", "maison margiela", "margiela",
            "dior homme", "dior men", "christian dior", "thierry mugler", "mugler",
            "enfants riches deprimes", "erd",
            "hysteric glamour",
            "comme des garcons", "cdg",
            "issey miyake", "kapital", "carol christian poell",
            "boris bidjan saberi", "julius", "ann demeulemeester",
            "alexander mcqueen", "celine",
            "neighborhood", "wtaps", "human made", "sacai",
            "roen", "soloist", "takahiromiyashita", "bape",
            "visvim", "wacko maria",
            "givenchy", "gucci", "versace", "dries van noten",
            "mihara yasuhiro", "burberry", "y-3",
            "balenciaga", "saint laurent", "prada", "bottega veneta",
            "haider ackermann", "guidi", "lemaire", "acne studios",
            "simone rocha", "brunello cucinelli",
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
    parser.add_argument("--skip-japan", action="store_true", help="Skip the Japan arbitrage sweep (useful for fast smoke tests)")
    parser.add_argument("--list-brands", action="store_true", help="List all brands in targets and exit")
    parser.add_argument("--list-targets", action="store_true", help="List all search targets and exit")
    parser.add_argument("--help-config", action="store_true", help="Show configuration help and exit")
    
    # Blocklist management
    parser.add_argument("--blocklist-block", type=str, metavar="SELLER", help="Block a seller")
    parser.add_argument("--blocklist-unblock", type=str, metavar="SELLER", help="Unblock a seller")
    parser.add_argument("--blocklist-list", action="store_true", help="List blocked sellers")
    parser.add_argument("--blocklist-stats", action="store_true", help="Show blocklist statistics")
    parser.add_argument("--blocklist-clear", action="store_true", help="Clear all blocked sellers")
    parser.add_argument("--blocklist-reason", type=str, default="manual", help="Reason for blocking")
    
    # Data management
    parser.add_argument("--data-metrics", action="store_true", help="Show data file metrics")
    parser.add_argument("--data-prune", action="store_true", help="Prune old data files")
    parser.add_argument("--data-prune-force", action="store_true", help="Force pruning even if under threshold")
    
    # Cache management
    parser.add_argument("--cache-stats", action="store_true", help="Show pricing cache statistics")
    parser.add_argument("--cache-flush", action="store_true", help="Flush expired cache entries")
    parser.add_argument("--cache-clear", action="store_true", help="Clear all cache entries")
    
    args = parser.parse_args()

    # Config help mode
    if args.help_config:
        from core.config import print_config_help
        print_config_help()
        exit(0)

    # List modes
    if args.list_brands:
        seen = []
        for t in TARGETS:
            for brand in ["rick owens", "chrome hearts", "raf simons", "helmut lang",
                          "number nine", "undercover", "jean paul gaultier", "gaultier",
                          "vivienne westwood", "maison margiela", "margiela", "dior",
                          "thierry mugler", "enfants riches deprimes", "hysteric glamour",
                          "comme des garcons", "cdg", "issey miyake",
                          "kapital", "carol christian poell", "boris bidjan saberi", "julius",
                          "ann demeulemeester", "celine",
                          "balenciaga", "saint laurent", "prada", "bottega veneta",
                          "givenchy", "gucci", "versace", "dries van noten",
                          "stone island", "needles", "visvim", "mihara yasuhiro",
                          "neighborhood", "wtaps", "human made", "sacai", "roen",
                          "soloist", "bape", "wacko maria", "burberry",
                          "haider ackermann", "guidi", "lemaire", "acne studios",
                          "simone rocha", "brunello cucinelli"]:
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

    # Blocklist management commands
    if args.blocklist_block:
        from core.seller_manager import block_seller_cli
        block_seller_cli(args.blocklist_block, args.blocklist_reason or "manual")
        exit(0)

    if args.blocklist_unblock:
        from core.seller_manager import unblock_seller_cli
        unblock_seller_cli(args.blocklist_unblock)
        exit(0)

    if args.blocklist_list:
        from core.seller_manager import list_blocked_cli
        list_blocked_cli()
        exit(0)

    if args.blocklist_stats:
        from core.seller_manager import SellerManager
        manager = SellerManager()
        stats = manager.get_stats()
        print("\nBlocklist Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        exit(0)

    if args.blocklist_clear:
        from core.seller_manager import clear_blocklist_cli
        clear_blocklist_cli()
        exit(0)

    # Data management commands
    if args.data_metrics:
        from core.data_manager import data_metrics_cli
        data_metrics_cli()
        exit(0)

    if args.data_prune:
        from core.data_manager import prune_data_cli
        prune_data_cli(force=args.data_prune_force)
        exit(0)

    # Cache management commands
    if args.cache_stats:
        from core.pricing_engine import show_cache_stats
        show_cache_stats()
        exit(0)

    if args.cache_flush:
        from core.pricing_engine import flush_cache
        flush_cache()
        exit(0)

    if args.cache_clear:
        from core.pricing_engine import clear_cache
        clear_cache()
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
        skip_japan=args.skip_japan,
    ))
