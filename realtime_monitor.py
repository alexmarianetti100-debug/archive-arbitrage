#!/usr/bin/env python3
"""
Real-Time Listing Monitor — The core competitive advantage.

Continuously polls Grailed and Poshmark for NEW listings every 60 seconds.
First to see = first to buy. This is what makes us unbeatable.

Architecture:
- Polls each platform's "newest" endpoint
- Tracks seen listing IDs to avoid duplicates
- Runs auth + pricing on new items
- Sends qualifying deals to Telegram in <60 seconds from listing

Usage:
    python realtime_monitor.py              # Run forever
    python realtime_monitor.py --once       # Single pass (testing)
    python realtime_monitor.py --brands 10  # Monitor top 10 brands only
"""

import asyncio
import os
import sys
import json
import time
import signal
import logging
from datetime import datetime, timedelta
from typing import List, Set, Dict, Optional
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from scrapers import GrailedScraper, PoshmarkScraper, ScrapedItem
from scrapers.brands import PRIORITY_BRANDS
from api.services.pricing import PricingService
from core.authenticity_v2 import AuthenticityCheckerV2, format_auth_bar, format_auth_grade, MIN_AUTH_SCORE
from core.desirability import check_desirability, get_desirability_emoji
from telegram_bot import send_deal_to_subscribers, init_telegram_db
from db.sqlite_models import init_db, save_item, Item
from core.deal_tracker import DealPrediction, record_prediction

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger("monitor")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

POLL_INTERVAL = int(os.getenv("MONITOR_POLL_INTERVAL", "60"))  # seconds
MIN_PROFIT = float(os.getenv("ALERT_MIN_PROFIT", "50"))
MIN_MARGIN = float(os.getenv("ALERT_MIN_MARGIN", "0.25"))
MAX_BRANDS_PER_CYCLE = int(os.getenv("MONITOR_MAX_BRANDS", "51"))

DEFAULT_SELL_PLATFORM = os.getenv("DEFAULT_SELL_PLATFORM", "grailed")
PLATFORM_FEES = {
    "grailed": 0.142, "poshmark": 0.20, "ebay": 0.13,
    "depop": 0.10, "mercari": 0.10,
}
DEFAULT_SELL_FEE = PLATFORM_FEES.get(DEFAULT_SELL_PLATFORM, 0.142)

# Buy-side costs
BUY_SHIPPING_DOMESTIC = float(os.getenv("BUY_SHIPPING_DOMESTIC", "15.0"))
JAPAN_SOURCES = {"japan_buyee", "rakuma", "mercari_jp", "yahoo_auctions_jp", "buyee"}

# State file to persist seen IDs across restarts
STATE_FILE = os.path.join(os.path.dirname(__file__), "data", "monitor_state.json")

# Priority brand groups — we rotate through these
# Group A: Most hyped, checked every cycle
TIER_A_BRANDS = [
    "rick owens", "chrome hearts", "raf simons", "helmut lang",
    "number nine", "undercover", "jean paul gaultier",
    "vivienne westwood", "maison margiela", "dior homme",
]

# Group B: High demand, checked every 2nd cycle
TIER_B_BRANDS = [
    "enfants riches deprimes", "hysteric glamour",
    "issey miyake", "thierry mugler",
    "balenciaga", "saint laurent", "prada", "gucci",
    "kapital", "julius", "ann demeulemeester",
]

# Group C: Solid brands, checked every 3rd cycle
TIER_C_BRANDS = [
    "boris bidjan saberi", "carol christian poell",
    "vetements", "alexander mcqueen", "hussein chalayan",
    "supreme", "off-white", "gallery dept", "amiri",
    "bape", "human made", "cav empt", "wacko maria",
    "neighborhood", "wtaps", "sacai",
    "dries van noten",
]

# Targeted searches for specific grails (rotated in)
GRAIL_QUERIES = [
    "helmut lang bondage", "raf simons riot", "rick owens geobasket",
    "number nine soloist", "gaultier mesh", "vivienne westwood orb",
    "margiela tabi", "dior homme hedi", "mugler vintage",
    "chrome hearts cross", "undercover scab", "hysteric glamour vintage",
    "raf simons virginia creeper", "rick owens ramones",
    "helmut lang painter", "cdg homme plus",
    # Mistagged / undervalued searches
    "vintage designer jacket", "archive fashion", "japanese designer vintage",
    "vintage avant garde", "made in italy vintage jacket",
    "vintage mesh top", "sterling silver cross pendant",
    "estate sale designer", "vintage leather jacket designer",
]


class RealtimeMonitor:
    """Continuously monitors platforms for new listings."""
    
    def __init__(self):
        self.pricing = PricingService()
        self.auth = AuthenticityCheckerV2()
        self.seen_ids: Set[str] = set()
        self.cycle_count = 0
        self.stats = defaultdict(int)
        self.running = True
        self._load_state()
        
        # Graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)
    
    def _shutdown(self, signum, frame):
        logger.info("Shutting down gracefully...")
        self.running = False
        self._save_state()
    
    def _load_state(self):
        """Load seen IDs from disk."""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE) as f:
                    data = json.load(f)
                    self.seen_ids = set(data.get("seen_ids", []))
                    self.cycle_count = data.get("cycle_count", 0)
                    logger.info(f"Loaded state: {len(self.seen_ids)} seen IDs, cycle {self.cycle_count}")
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
    
    def _save_state(self):
        """Persist seen IDs to disk. Keep last 50K to prevent unbounded growth."""
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            # Only keep most recent 50K IDs
            ids_list = list(self.seen_ids)
            if len(ids_list) > 50000:
                ids_list = ids_list[-50000:]
                self.seen_ids = set(ids_list)
            
            with open(STATE_FILE, "w") as f:
                json.dump({
                    "seen_ids": ids_list,
                    "cycle_count": self.cycle_count,
                    "last_save": datetime.now().isoformat(),
                }, f)
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")
    
    def _get_brands_for_cycle(self) -> List[str]:
        """Get which brands to check this cycle based on rotation."""
        brands = list(TIER_A_BRANDS)  # Always check A
        
        if self.cycle_count % 2 == 0:
            brands.extend(TIER_B_BRANDS)  # Every 2nd cycle
        
        if self.cycle_count % 3 == 0:
            brands.extend(TIER_C_BRANDS)  # Every 3rd cycle
        
        return brands[:MAX_BRANDS_PER_CYCLE]
    
    def _get_queries_for_cycle(self) -> List[str]:
        """Rotate through grail queries — 5 per cycle."""
        start = (self.cycle_count * 5) % len(GRAIL_QUERIES)
        return GRAIL_QUERIES[start:start + 5]
    
    async def scan_platform(self, platform: str, queries: List[str], max_per_query: int = 10) -> List[ScrapedItem]:
        """Scan a platform for new listings across multiple queries."""
        all_items = []
        scraper_class = GrailedScraper if platform == "grailed" else PoshmarkScraper
        
        try:
            async with scraper_class() as scraper:
                for query in queries:
                    try:
                        items = await scraper.search(query, max_results=max_per_query)
                        # Filter to only NEW items we haven't seen
                        new_items = []
                        for item in items:
                            item_key = f"{platform}:{item.source_id or item.url}"
                            if item_key not in self.seen_ids:
                                self.seen_ids.add(item_key)
                                new_items.append(item)
                        
                        all_items.extend(new_items)
                        self.stats[f"{platform}_scanned"] += len(items)
                        self.stats[f"{platform}_new"] += len(new_items)
                        
                    except Exception as e:
                        logger.debug(f"Search failed for '{query}' on {platform}: {e}")
                    
                    await asyncio.sleep(1)  # Rate limiting
                    
        except Exception as e:
            logger.error(f"Platform {platform} scan failed: {e}")
        
        return all_items
    
    async def process_item(self, item: ScrapedItem) -> bool:
        """Process a single item through pricing + auth. Returns True if deal was sent."""
        try:
            brand = self._detect_brand(item.title)
            if not brand:
                return False
            
            category = self._detect_category(item.title)
            
            # ── Product catalog fast-path ──
            _monitor_product_match = None
            try:
                from scrapers.product_fingerprint import parse_title_to_fingerprint
                from db.sqlite_models import get_product_by_fingerprint, get_product_pricing
                from api.services.pricing import PriceRecommendation
                from decimal import Decimal

                _fp = parse_title_to_fingerprint(brand, item.title)
                if _fp.confidence == "high" and _fp.fingerprint_hash:
                    _product = get_product_by_fingerprint(_fp.fingerprint_hash)
                    if _product:
                        _pricing = get_product_pricing(_product.id)
                        if _pricing and _pricing["confidence_tier"] in ("guaranteed", "high"):
                            _monitor_product_match = _pricing
                            sell_fee = PLATFORM_FEES.get(DEFAULT_SELL_PLATFORM, 0.142)
                            _median = _pricing["median_price"]

                            # Apply condition adjustment (same as gap_hunter)
                            try:
                                from core.condition_parser import parse_condition, CONDITION_TIERS
                                _src_cond, _, _ = parse_condition(item.title, brand=brand or "")
                                _src_mult = CONDITION_TIERS.get(_src_cond, 0.70)
                                _comp_assumed = 0.70  # Grailed comp avg
                                if _src_mult < _comp_assumed and _comp_assumed > 0:
                                    _median *= (_src_mult / _comp_assumed)
                            except Exception:
                                pass

                            # Apply seasonal haircut (same as gap_hunter)
                            _month = datetime.now().month
                            _tl = item.title.lower() if item.title else ""
                            _winter = any(k in _tl for k in ("jacket", "coat", "parka", "puffer"))
                            _summer = any(k in _tl for k in ("swim", "tank top", "sandal"))
                            if (_winter and 4 <= _month <= 8) or (_summer and (_month >= 10 or _month <= 2)):
                                _median *= 0.85

                            # Shipping estimate
                            _shipping = 20.0  # Default
                            if any(k in _tl for k in ("jacket", "coat", "hoodie")):
                                _shipping = 32.0
                            elif any(k in _tl for k in ("boot", "shoe", "sneaker", "geobasket")):
                                _shipping = 22.0
                            if _median > 500:
                                _shipping += _median * 0.04  # Insurance

                            _buy_costs = BUY_SHIPPING_DOMESTIC
                            _src = getattr(item, 'source', '').lower()
                            if _src in JAPAN_SOURCES or 'japan' in _src or 'buyee' in _src:
                                _buy_costs = 45.0 + item.price * 0.05  # Japan shipping + service fee

                            _net = _median * (1 - sell_fee) - _shipping
                            _profit = _net - item.price - _buy_costs
                            _margin = _profit / item.price if item.price > 0 else 0

                            # Margin requirement adjusted by tier AND data freshness
                            _min_margin = MIN_MARGIN  # 25% base
                            if _pricing["confidence_tier"] == "high":
                                _min_margin = 0.30  # Higher for price-variable products
                            _freshness = _pricing.get("data_freshness", "unknown")
                            if _freshness == "stale":
                                _min_margin += 0.10  # +10% buffer for stale data
                            elif _freshness in ("aging", "unknown"):
                                _min_margin += 0.05  # +5% buffer for uncertain freshness

                            if _profit < MIN_PROFIT or _margin < _min_margin:
                                _monitor_product_match = None  # Doesn't meet thresholds after adjustments
                            else:
                                price_rec = PriceRecommendation(
                                    source_price=Decimal(str(item.price)),
                                    market_price=Decimal(str(_median)),
                                    recommended_price=Decimal(str(_median)),
                                    margin_percent=float(_margin),
                                    profit_estimate=Decimal(str(_profit)),
                                    confidence="high",
                                    reasoning=f"Product catalog: {_pricing['confidence_tier']} ({_pricing['comp_count']} exact comps)",
                                    comps_count=_pricing["comp_count"],
                                )
                            logger.info(
                                f"    🏷️ Product match: '{_fp.canonical_name}' → "
                                f"{_pricing['confidence_tier'].upper()}, {_pricing['comp_count']} comps "
                                f"({_pricing.get('recent_comp_count', 0)} recent), "
                                f"${_median:.0f} median [{_freshness.upper()}]"
                            )
            except Exception as e:
                logger.debug(f"    Product catalog lookup failed: {e}")

            if not _monitor_product_match:
                # Get pricing (with listing image for pHash comp validation)
                listing_images = getattr(item, 'images', None) or []
                listing_img_url = listing_images[0] if listing_images else None
                price_rec = await self.pricing.calculate_price_async(
                    source_price=item.price,
                    brand=brand,
                    title=item.title,
                    shipping_cost=getattr(item, "shipping_cost", 0) or 0,
                    listing_image_url=listing_img_url,
                )

            if not price_rec or price_rec.confidence == "skip" or price_rec.recommended_price == 0:
                return False
            
            profit = float(price_rec.profit_estimate) if hasattr(price_rec, 'profit_estimate') else 0
            # Deduct buy-side costs (shipping, tax, service fees)
            if not _monitor_product_match:  # Product path already deducted
                _src_lower = getattr(item, 'source', '').lower()
                if _src_lower in JAPAN_SOURCES or 'japan' in _src_lower:
                    profit -= (45.0 + item.price * 0.05)
                else:
                    profit -= BUY_SHIPPING_DOMESTIC
            margin = profit / item.price if item.price > 0 else 0

            if profit < MIN_PROFIT or margin < MIN_MARGIN:
                return False

            # Hard gate: only surface deals with exact product catalog matches
            if not _monitor_product_match:
                return False

            # Desirability check — only alert on items the community actually wants
            is_desirable, desirability_score, desirability_reason = check_desirability(
                title=item.title,
                brand=brand,
                price=item.price,
                profit=profit,
                margin=margin,
                confidence=price_rec.confidence,
                comps_count=price_rec.comps_count,
                demand_level=price_rec.demand_level,
            )
            
            if not is_desirable:
                self.stats["desirability_blocked"] += 1
                logger.debug(f"  ⛔ Not desirable: {item.title[:50]} — {desirability_reason}")
                return False
            
            # Auth check
            auth_result = await asyncio.wait_for(
                self.auth.check(
                    title=item.title,
                    description=item.description or "",
                    price=item.price,
                    brand=brand,
                    category=category or "",
                    seller_name=item.seller or "",
                    seller_sales=getattr(item, "seller_sales", 0),
                    seller_rating=getattr(item, "seller_rating", None),
                    images=item.images,
                    source=item.source,
                ),
                timeout=20.0
            )
            
            if auth_result.action == "block" or auth_result.confidence < MIN_AUTH_SCORE:
                self.stats["auth_blocked"] += 1
                return False
            
            # 🔥 DEAL FOUND — send it
            logger.info(
                f"💰 DEAL: {item.title[:60]} | ${item.price:.0f} → ${price_rec.recommended_price:.0f} "
                f"({margin*100:.0f}%) | {format_auth_grade(auth_result.grade)} | "
                f"{get_desirability_emoji(desirability_score)} {price_rec.confidence} conf"
            )
            
            try:
                await send_deal_to_subscribers(
                    item, price_rec, brand=brand,
                    auth_result=None, auth_v2=auth_result
                )
                self.stats["deals_sent"] += 1
            except Exception as e:
                logger.error(f"Failed to send deal: {e}")
                return False

            # Track deal prediction for accuracy analysis
            try:
                prediction = DealPrediction(
                    timestamp=datetime.now().isoformat(),
                    query=brand or "",
                    item_title=item.title,
                    item_url=item.url,
                    predicted_price=float(price_rec.recommended_price),
                    prediction_method="product_catalog" if _monitor_product_match else "standard",
                    cv=None,
                    confidence_level=price_rec.confidence,
                    num_comps=price_rec.comps_count,
                    buy_price=item.price,
                    buy_platform=item.source,
                    sell_platform=DEFAULT_SELL_PLATFORM,
                    estimated_profit=float(price_rec.profit_estimate),
                    estimated_fees=float(price_rec.recommended_price) * DEFAULT_SELL_FEE,
                )
                record_prediction(prediction)
            except Exception as e:
                logger.debug(f"Failed to track deal prediction: {e}")

            return True
                
        except asyncio.TimeoutError:
            return False
        except Exception as e:
            logger.debug(f"Process item failed: {e}")
            return False
    
    async def run_cycle(self):
        """Run one monitoring cycle."""
        self.cycle_count += 1
        cycle_start = time.time()
        
        brands = self._get_brands_for_cycle()
        grail_queries = self._get_queries_for_cycle()
        all_queries = brands + grail_queries
        
        tier_info = "A"
        if self.cycle_count % 2 == 0:
            tier_info += "+B"
        if self.cycle_count % 3 == 0:
            tier_info += "+C"
        
        logger.info(f"━━━ Cycle {self.cycle_count} | Tiers: {tier_info} | {len(all_queries)} queries ━━━")
        
        # Scan both platforms in parallel
        grailed_task = self.scan_platform("grailed", all_queries, max_per_query=8)
        poshmark_task = self.scan_platform("poshmark", all_queries, max_per_query=8)
        
        grailed_items, poshmark_items = await asyncio.gather(
            grailed_task, poshmark_task, return_exceptions=True
        )
        
        if isinstance(grailed_items, Exception):
            logger.error(f"Grailed scan error: {grailed_items}")
            grailed_items = []
        if isinstance(poshmark_items, Exception):
            logger.error(f"Poshmark scan error: {poshmark_items}")
            poshmark_items = []
        
        all_new = list(grailed_items) + list(poshmark_items)
        
        if all_new:
            logger.info(f"  📦 {len(all_new)} new items (Grailed: {len(grailed_items)}, Poshmark: {len(poshmark_items)})")
            
            # Process all new items concurrently (batches of 10)
            deals_found = 0
            for i in range(0, len(all_new), 10):
                batch = all_new[i:i+10]
                results = await asyncio.gather(
                    *[self.process_item(item) for item in batch],
                    return_exceptions=True
                )
                deals_found += sum(1 for r in results if r is True)
            
            if deals_found:
                logger.info(f"  🔥 {deals_found} deals sent to subscribers!")
        else:
            logger.info(f"  No new items this cycle")
        
        elapsed = time.time() - cycle_start
        logger.info(f"  ⏱ Cycle completed in {elapsed:.1f}s")
        
        # Save state every 5 cycles
        if self.cycle_count % 5 == 0:
            self._save_state()
            self._log_stats()
    
    def _log_stats(self):
        """Log cumulative stats."""
        logger.info(
            f"📊 Stats: cycles={self.cycle_count} | "
            f"grailed_new={self.stats['grailed_new']} | "
            f"poshmark_new={self.stats['poshmark_new']} | "
            f"deals_sent={self.stats['deals_sent']} | "
            f"auth_blocked={self.stats['auth_blocked']} | "
            f"seen_total={len(self.seen_ids)}"
        )
    
    async def run(self, once: bool = False):
        """Main loop — runs forever until killed."""
        init_db()
        init_telegram_db()
        
        logger.info("=" * 60)
        logger.info("🚀 ARCHIVE ARBITRAGE — REAL-TIME MONITOR")
        logger.info(f"   Poll interval: {POLL_INTERVAL}s")
        logger.info(f"   Tier A brands: {len(TIER_A_BRANDS)}")
        logger.info(f"   Tier B brands: {len(TIER_B_BRANDS)}")
        logger.info(f"   Tier C brands: {len(TIER_C_BRANDS)}")
        logger.info(f"   Grail queries: {len(GRAIL_QUERIES)}")
        logger.info(f"   Min profit: ${MIN_PROFIT}")
        logger.info(f"   Min margin: {MIN_MARGIN*100:.0f}%")
        logger.info(f"   Min auth score: {MIN_AUTH_SCORE*100:.0f}%")
        logger.info("=" * 60)
        
        while self.running:
            try:
                await self.run_cycle()
            except Exception as e:
                logger.error(f"Cycle error: {e}")
            
            if once:
                break
            
            # Wait for next cycle
            logger.info(f"  💤 Next cycle in {POLL_INTERVAL}s...")
            for _ in range(POLL_INTERVAL):
                if not self.running:
                    break
                await asyncio.sleep(1)
        
        self._save_state()
        self._log_stats()
        logger.info("Monitor stopped.")
    
    @staticmethod
    def _detect_brand(title: str) -> str:
        title_lower = title.lower()
        brands = [
            "rick owens", "chrome hearts", "raf simons", "helmut lang",
            "number nine", "undercover", "jean paul gaultier", "gaultier",
            "vivienne westwood", "maison margiela", "martin margiela", "margiela",
            "dior homme", "dior", "thierry mugler", "mugler",
            "enfants riches deprimes", "erd", "hysteric glamour",
            "issey miyake", "kapital", "carol christian poell",
            "boris bidjan saberi", "julius", "ann demeulemeester",
            "vetements", "alexander mcqueen",
            "hussein chalayan", "balenciaga", "saint laurent",
            "prada", "gucci", "louis vuitton", "supreme", "off-white",
            "gallery dept", "amiri", "bape", "human made",
            "cav empt", "wacko maria", "neighborhood", "wtaps",
            "sacai", "dries van noten",
        ]
        for brand in brands:
            if brand in title_lower:
                return brand
        return ""
    
    @staticmethod
    def _detect_category(title: str) -> str:
        title_lower = title.lower()
        categories = {
            "jacket": ["jacket", "blazer", "coat", "bomber", "parka"],
            "pants": ["pants", "trousers", "jeans", "cargo"],
            "shirt": ["shirt", "button"],
            "tee": ["t-shirt", "tee"],
            "hoodie": ["hoodie", "pullover"],
            "sweater": ["sweater", "knit", "cardigan"],
            "boots": ["boots", "boot", "geobasket", "ramones"],
            "shoes": ["shoes", "sneakers", "dunks"],
            "bag": ["bag", "backpack", "tote"],
            "jewelry": ["necklace", "ring", "bracelet", "pendant", "cross"],
            "accessories": ["belt", "wallet", "hat", "eyewear"],
            "top": ["mesh", "tank", "corset"],
        }
        for cat, kws in categories.items():
            if any(kw in title_lower for kw in kws):
                return cat
        return ""


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Archive Arbitrage Real-Time Monitor")
    parser.add_argument("--once", action="store_true", help="Run single cycle then exit")
    parser.add_argument("--brands", type=int, default=51, help="Max brands per cycle")
    args = parser.parse_args()
    
    MAX_BRANDS_PER_CYCLE = args.brands
    
    monitor = RealtimeMonitor()
    asyncio.run(monitor.run(once=args.once))
