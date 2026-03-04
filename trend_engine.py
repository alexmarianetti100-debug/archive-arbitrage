"""
TrendEngine — Dynamic search target generation for Archive Arbitrage.

Replaces the static TARGETS list in gap_hunter.py with daily trend-driven queries.
Discovers what's hot in archive fashion using multiple signal sources, then generates
prioritized search queries for deal hunting.

Usage:
    engine = TrendEngine()
    targets = await engine.get_today_targets()
"""

import asyncio
import json
import logging
import os
import random
from collections import defaultdict
from datetime import datetime, date
from typing import Optional

from trend_sources.base import TrendSignal, TrendSource
from trend_sources.grailed_velocity import GrailedVelocitySource
from trend_sources.social_signals import RedditSignalSource
from trend_sources.google_trends import GoogleTrendsSource
from trend_sources.editorial import EditorialSource

logger = logging.getLogger("trend_engine")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "trends")
DAILY_DIR = os.path.join(DATA_DIR, "daily")
PERFORMANCE_FILE = os.path.join(DATA_DIR, "query_performance.json")

# ═══════════════════════════════════════════════════════════════════
# CORE TARGETS — Always searched regardless of trends.
# These are the most liquid archive items that consistently have deals.
# ═══════════════════════════════════════════════════════════════════
CORE_TARGETS = [
    "rick owens geobasket",
    "rick owens ramones high",
    "rick owens dunks",
    "rick owens stooges leather jacket",
    "rick owens kiss boots",
    "margiela tabi boots",
    "chrome hearts cross pendant silver",
    "chrome hearts cross ring",
    "raf simons peter saville joy division",
    "raf simons ozweego",
    "helmut lang bondage jacket",
    "balenciaga triple s",
    "balenciaga track",
    "saint laurent wyatt boots",
    "prada americas cup",
    "bottega veneta puddle boots",
    "number nine leather jacket",
    "undercover scab",
    "dior homme hedi slimane jacket",
    "maison martin margiela replica GAT",
]

# Full brand universe for random rotation (discover new opportunities)
ROTATION_BRANDS = [
    "rick owens", "raf simons", "chrome hearts", "helmut lang",
    "maison margiela", "comme des garcons", "undercover", "number nine",
    "yohji yamamoto", "balenciaga", "saint laurent", "prada",
    "dior homme", "vivienne westwood", "jean paul gaultier", "issey miyake",
    "julius", "bottega veneta", "celine", "junya watanabe",
    "kapital", "visvim", "hysteric glamour", "needles",
    "sacai", "bape", "wtaps", "neighborhood",
]

ROTATION_CATEGORIES = [
    "leather jacket", "cargo pants", "boots", "sneakers",
    "hoodie", "knit sweater", "bomber jacket", "bag",
    "denim jacket", "ring", "pendant", "coat",
]


class TrendEngine:
    """
    Orchestrates trend discovery and search query generation.
    
    Query allocation (default 60 total):
    - 20: Today's hottest trends
    - 15: Core targets (always-liquid items, rotated)
    - 15: Emerging/rising signals
    - 10: Random rotation from brand universe
    """

    def __init__(self, max_queries: int = 60):
        self.max_queries = max_queries
        self.sources: list[TrendSource] = [
            GrailedVelocitySource(),
            RedditSignalSource(),
            GoogleTrendsSource(),
            EditorialSource(),
        ]
        os.makedirs(DAILY_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)

    async def get_today_targets(self) -> list[str]:
        """
        Main entry point. Returns today's search queries.
        Uses daily cache to avoid re-analyzing every cycle.
        """
        today = date.today().isoformat()
        cache_file = os.path.join(DAILY_DIR, f"{today}.json")

        # Check cache
        if os.path.exists(cache_file):
            try:
                with open(cache_file) as f:
                    cached = json.load(f)
                queries = cached.get("queries", [])
                if queries:
                    logger.info(f"📋 Using cached trend targets for {today} ({len(queries)} queries)")
                    return queries
            except (json.JSONDecodeError, IOError):
                pass

        # Discover trends and generate queries
        try:
            trends = await self.discover_trends()
            queries = self.generate_searches(trends)
        except Exception as e:
            logger.error(f"❌ Trend discovery failed: {e}. Falling back to core targets.")
            queries = list(CORE_TARGETS)

        # Cache today's results
        self._save_daily_cache(today, queries, trends if 'trends' in dir() else [])

        return queries

    async def discover_trends(self) -> list[TrendSignal]:
        """
        Run all signal sources concurrently, merge and deduplicate signals.
        """
        logger.info("🔥 Discovering today's trends...")

        all_signals: list[TrendSignal] = []

        # Run sources concurrently
        tasks = []
        for source in self.sources:
            tasks.append(self._safe_fetch(source))

        results = await asyncio.gather(*tasks)

        for source, signals in zip(self.sources, results):
            if signals:
                # Apply source weight to scores
                for sig in signals:
                    sig.trend_score *= source.weight
                all_signals.extend(signals)
                logger.info(f"  {source.name}: {len(signals)} signals")

        # Merge signals about the same items from different sources
        merged = self._merge_signals(all_signals)

        # Boost signals confirmed by multiple sources
        for sig in merged:
            if len(sig.signal_sources) > 1:
                sig.trend_score = min(1.0, sig.trend_score * 1.3)

        # Sort by score
        merged.sort(key=lambda s: s.trend_score, reverse=True)

        logger.info(f"  Total merged signals: {len(merged)}")
        return merged

    def generate_searches(self, trends: list[TrendSignal]) -> list[str]:
        """
        Convert trend signals into search query strings.
        
        Allocation:
        - Hot (20): trend_score > 0.5, direction rising/stable
        - Core (15): from CORE_TARGETS, rotated
        - Emerging (15): direction == "rising", lower scores
        - Random (10): brand+category combos for discovery
        
        Feedback loop: boosts scores for queries that historically find deals,
        and deprioritizes queries that never find anything.
        """
        # Apply feedback loop: boost/penalize trends based on past performance
        trends = self._apply_feedback(trends)

        queries: list[str] = []
        used: set[str] = set()

        def _add(q: str):
            q_lower = q.lower().strip()
            if q_lower and q_lower not in used:
                used.add(q_lower)
                queries.append(q)

        # ── HOT: Today's top trends ──
        hot_count = 0
        for sig in trends:
            if hot_count >= 20:
                break
            if sig.trend_score >= 0.3:
                _add(sig.specific_query)
                hot_count += 1

        # ── CORE: Always-liquid items (rotate through the list) ──
        day_of_year = datetime.utcnow().timetuple().tm_yday
        core_rotated = CORE_TARGETS[day_of_year % len(CORE_TARGETS):] + CORE_TARGETS[:day_of_year % len(CORE_TARGETS)]
        core_count = 0
        for q in core_rotated:
            if core_count >= 15:
                break
            _add(q)
            core_count += 1

        # ── EMERGING: Rising signals with lower scores ──
        emerging_count = 0
        for sig in trends:
            if emerging_count >= 15:
                break
            if sig.trend_direction == "rising" and sig.specific_query.lower() not in used:
                _add(sig.specific_query)
                emerging_count += 1

        # ── RANDOM: Discovery rotation ──
        random.seed(day_of_year)
        random_combos = []
        for _ in range(30):
            brand = random.choice(ROTATION_BRANDS)
            cat = random.choice(ROTATION_CATEGORIES)
            random_combos.append(f"{brand} {cat}")
        random.shuffle(random_combos)

        random_count = 0
        for q in random_combos:
            if random_count >= 10:
                break
            _add(q)
            random_count += 1

        # Fill remaining slots with more trends if available
        remaining = self.max_queries - len(queries)
        if remaining > 0:
            for sig in trends:
                if remaining <= 0:
                    break
                _add(sig.specific_query)
                remaining = self.max_queries - len(queries)

        logger.info(
            f"  Generated {len(queries)} queries: "
            f"{hot_count} hot, {core_count} core, {emerging_count} emerging, {random_count} random"
        )
        return queries

    def log_query_performance(self, query: str, found_deals: int, best_gap_pct: float = 0.0):
        """Track which queries actually found deals (feedback loop)."""
        perf = self._load_performance()

        if query not in perf:
            perf[query] = {"total_runs": 0, "total_deals": 0, "best_gap": 0, "last_run": None}

        perf[query]["total_runs"] += 1
        perf[query]["total_deals"] += found_deals
        perf[query]["best_gap"] = max(perf[query]["best_gap"], best_gap_pct)
        perf[query]["last_run"] = datetime.utcnow().isoformat()

        self._save_performance(perf)

    def _apply_feedback(self, trends: list[TrendSignal]) -> list[TrendSignal]:
        """
        Boost/penalize trend signals based on historical query performance.
        
        - Queries that found deals in the past get a score boost
        - Queries that ran 10+ times with zero deals get penalized
        - New queries are left unchanged (neutral)
        """
        perf = self._load_performance()
        if not perf:
            return trends

        for sig in trends:
            query_lower = sig.specific_query.lower()
            # Check exact match and partial matches
            best_match = None
            for q, data in perf.items():
                if q.lower() == query_lower or q.lower() in query_lower or query_lower in q.lower():
                    if best_match is None or data.get("total_deals", 0) > best_match.get("total_deals", 0):
                        best_match = data

            if best_match:
                runs = best_match.get("total_runs", 0)
                deals = best_match.get("total_deals", 0)

                if runs > 0:
                    hit_rate = deals / runs

                    if hit_rate > 0.1:
                        # Great performer — boost up to 30%
                        boost = min(0.3, hit_rate)
                        sig.trend_score = min(1.0, sig.trend_score + boost)
                        logger.debug(f"  📈 Boosted '{sig.specific_query}' by {boost:.0%} (hit rate {hit_rate:.0%})")
                    elif runs >= 10 and deals == 0:
                        # Dead query — penalize
                        sig.trend_score *= 0.5
                        logger.debug(f"  📉 Penalized '{sig.specific_query}' (0 deals in {runs} runs)")

        # Re-sort after adjustments
        trends.sort(key=lambda s: s.trend_score, reverse=True)
        return trends

    # ── Private helpers ──

    async def _safe_fetch(self, source: TrendSource) -> list[TrendSignal]:
        """Fetch signals from a source, returning [] on error."""
        try:
            return await source.fetch_signals()
        except Exception as e:
            logger.error(f"  ❌ {source.name} failed: {e}")
            return []

    def _merge_signals(self, signals: list[TrendSignal]) -> list[TrendSignal]:
        """Merge signals about the same item from different sources."""
        merged: dict[str, TrendSignal] = {}

        for sig in signals:
            key = sig.merge_key
            if key in merged:
                merged[key] = merged[key].merge(sig)
            else:
                merged[key] = sig

        return list(merged.values())

    def _save_daily_cache(self, today: str, queries: list[str], trends: list[TrendSignal]):
        """Save today's queries and trends to cache."""
        cache = {
            "date": today,
            "generated_at": datetime.utcnow().isoformat(),
            "queries": queries,
            "trend_count": len(trends),
            "top_trends": [
                {
                    "query": t.specific_query,
                    "brand": t.brand,
                    "score": round(t.trend_score, 3),
                    "direction": t.trend_direction,
                    "sources": t.signal_sources,
                    "velocity_change": round(t.velocity_change, 2),
                    "price_change": round(t.price_change, 2),
                }
                for t in trends[:20]
            ],
        }
        path = os.path.join(DAILY_DIR, f"{today}.json")
        with open(path, "w") as f:
            json.dump(cache, f, indent=2)
        logger.info(f"  💾 Cached {len(queries)} queries to {path}")

    def _load_performance(self) -> dict:
        if os.path.exists(PERFORMANCE_FILE):
            try:
                with open(PERFORMANCE_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save_performance(self, perf: dict):
        with open(PERFORMANCE_FILE, "w") as f:
            json.dump(perf, f, indent=2)


# ── CLI test ──
if __name__ == "__main__":
    async def main():
        engine = TrendEngine()
        targets = await engine.get_today_targets()
        print(f"\n🎯 Today's {len(targets)} search targets:\n")
        for i, q in enumerate(targets, 1):
            print(f"  {i:2}. {q}")

    asyncio.run(main())
