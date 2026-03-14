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

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger("monitor")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

POLL_INTERVAL = int(os.getenv("MONITOR_POLL_INTERVAL", "60"))  # seconds
MIN_PROFIT = float(os.getenv("ALERT_MIN_PROFIT", "50"))
MIN_MARGIN = float(os.getenv("ALERT_MIN_MARGIN", "0.25"))
MAX_BRANDS_PER_CYCLE = int(os.getenv("MONITOR_MAX_BRANDS", "51"))

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
    "enfants riches deprimes", "hysteric glamour", "yohji yamamoto",
    "comme des garcons", "issey miyake", "thierry mugler",
    "balenciaga", "saint laurent", "prada", "gucci",
    "kapital", "julius", "ann demeulemeester",
]

# Group C: Solid brands, checked every 3rd cycle
TIER_C_BRANDS = [
    "boris bidjan saberi", "carol christian poell",
    "vetements", "alexander mcqueen", "hussein chalayan",
    "supreme", "off-white", "gallery dept", "amiri",
    "bape", "human made", "cav empt", "wacko maria",
    "neighborhood", "wtaps", "visvim", "sacai",
    "junya watanabe", "dries van noten",
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
            
            # Get pricing
            price_rec = await self.pricing.calculate_price_async(
                source_price=item.price,
                brand=brand,
                title=item.title,
                shipping_cost=getattr(item, "shipping_cost", 0) or 0,
            )
            
            if not price_rec or price_rec.confidence == "skip" or price_rec.recommended_price == 0:
                return False
            
            profit = float(price_rec.profit_estimate) if hasattr(price_rec, 'profit_estimate') else 0
            margin = float(price_rec.margin_percent) if hasattr(price_rec, 'margin_percent') else 0
            
            if profit < MIN_PROFIT or margin < MIN_MARGIN:
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
                return True
            except Exception as e:
                logger.error(f"Failed to send deal: {e}")
                return False
                
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
            "yohji yamamoto", "comme des garcons", "cdg",
            "issey miyake", "kapital", "carol christian poell",
            "boris bidjan saberi", "julius", "ann demeulemeester",
            "vetements", "alexander mcqueen",
            "hussein chalayan", "balenciaga", "saint laurent",
            "prada", "gucci", "louis vuitton", "supreme", "off-white",
            "gallery dept", "amiri", "bape", "human made",
            "cav empt", "wacko maria", "neighborhood", "wtaps",
            "visvim", "sacai", "junya watanabe", "dries van noten",
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
