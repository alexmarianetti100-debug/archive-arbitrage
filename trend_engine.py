"""
TrendEngine — Dynamic search target generation for Archive Arbitrage.

Strategy: hunt items that combine HIGH resale price with CONSISTENT sales volume.
Not trending items — consistently liquid, high-value items with real deal room.

Scoring:
    opportunity_score = avg_sold_price × monthly_sold_volume
    e.g. $600 jacket × 10 sales/mo = 6000  (better than $50 tee × 100 sales/mo = 5000)

Tier thresholds (applied to Grailed-derived opportunity scores):
    Tier 1 — always run every cycle:  avg ≥ $400 AND monthly_vol ≥ 6
    Tier 2 — most cycles (~70%):      avg ≥ $250 AND monthly_vol ≥ 4
    Tier 3 — rotation (~30%):         avg ≥ $150 AND monthly_vol ≥ 2

Golden Catalog:
    Persisted to data/trends/golden_catalog.json, refreshed weekly.
    Inspectable — shows exactly why each item is being hunted.

Usage:
    engine = TrendEngine()
    targets = await engine.get_cycle_targets(n=60)   # varied per-cycle subset
    targets = await engine.get_today_targets()        # full daily pool (legacy)
"""

import asyncio
import json
import logging
import os
import random
from collections import defaultdict
from datetime import datetime, date, timedelta
from typing import Optional

from trend_sources.base import TrendSignal, TrendSource
from trend_sources.grailed_velocity import GrailedVelocitySource

logger = logging.getLogger("trend_engine")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "trends")
DAILY_DIR = os.path.join(DATA_DIR, "daily")
PERFORMANCE_FILE = os.path.join(DATA_DIR, "query_performance.json")
GOLDEN_CATALOG_FILE = os.path.join(DATA_DIR, "golden_catalog.json")

# ── Catalog refresh schedule ──────────────────────────────────────────────────
CATALOG_REFRESH_DAYS = 7    # Rebuild golden catalog once a week

# ── Tier thresholds ───────────────────────────────────────────────────────────
# Items must clear BOTH price AND volume floors to enter a tier.
TIER1_MIN_PRICE  = 400.0    # High-value: leather jackets, rare boots, bags
TIER1_MIN_VOLUME = 6        # Sells 6+ times per month (liquid)

TIER2_MIN_PRICE  = 250.0    # Mid-high: knitwear, accessories, common boots
TIER2_MIN_VOLUME = 4        # Sells 4+ times per month

TIER3_MIN_PRICE  = 150.0    # Entry: lower-priced but consistent items
TIER3_MIN_VOLUME = 2        # Sells 2+ times per month

# ── Dead query exclusion ──────────────────────────────────────────────────────
DEAD_QUERY_MIN_RUNS  = 50   # After this many runs…
DEAD_QUERY_MAX_DEALS = 0    # …with zero deals → excluded from rotation

# ── Fallback targets (used only when catalog is empty / velocity fetch fails) ─
CORE_TARGETS = [
    "rick owens dunks",
    "rick owens leather jacket",
    "rick owens cargo pants",
    "rick owens boots",
    "margiela tabi boots",
    "margiela tabi heels",
    "saint laurent wyatt boots",
    "saint laurent leather jacket",
    "dior homme hedi slimane jacket",
    "dior homme leather jacket",
    "maison martin margiela replica GAT",
    "helmut lang jacket",
    "helmut lang leather jacket",
    "helmut lang astro biker",
    "number nine leather jacket",
    "number nine skull cashmere",
    "jean paul gaultier mesh top",
    "jean paul gaultier leather jacket",
    "raf simons riot bomber",
    "raf simons leather jacket",
    "chrome hearts hoodie",
    "chrome hearts leather jacket",
    "chrome hearts ring",
    "bottega veneta puddle boots",
    "bottega veneta cassette bag",
    "ann demeulemeester leather jacket",
    "ann demeulemeester boots",
    "comme des garcons homme plus jacket",
    "junya watanabe jacket",
    "yohji yamamoto jacket",
    "julius leather jacket",
    "undercover jacket",
    "vivienne westwood leather jacket",
    "issey miyake homme plisse jacket",
    "carol christian poell jacket",
    "haider ackermann leather jacket",
    "boris bidjan saberi jacket",
]

EXTENDED_TARGETS = [
    "rick owens coat", "rick owens knit", "rick owens hoodie", "rick owens geobasket",
    "rick owens bomber", "rick owens drkshdw", "rick owens bauhaus", "rick owens level tee",
    "rick owens intarsia", "rick owens dustulator",
    "chrome hearts hoodie", "chrome hearts ring", "chrome hearts necklace",
    "chrome hearts bracelet", "chrome hearts t shirt", "chrome hearts matty boy",
    "chrome hearts horseshoe", "chrome hearts dagger", "chrome hearts floral cross ring",
    "chrome hearts scroll bracelet", "chrome hearts cemetery cross",
    "margiela paint splatter", "margiela deconstructed blazer", "margiela numbers tee",
    "margiela replica sneakers", "margiela glam slam", "margiela artisanal jacket",
    "helmut lang archive", "helmut lang leather", "helmut lang painter jeans",
    "helmut lang nylon bomber", "helmut lang flak jacket", "helmut lang bondage pants",
    "raf simons consumed hoodie", "raf simons tape bomber", "raf simons sterling ruby",
    "raf simons leather jacket", "raf simons denim jacket", "raf simons knit sweater",
    "jean paul gaultier mesh top", "jean paul gaultier tattoo top", "jean paul gaultier corset",
    "jean paul gaultier sailor", "jean paul gaultier tuxedo jacket", "jean paul gaultier denim",
    "dior homme boots", "dior homme jeans", "dior homme bomber", "dior homme tuxedo",
    "balenciaga speed trainer", "balenciaga defender", "balenciaga leather jacket",
    "balenciaga political campaign", "saint laurent chain boots", "saint laurent teddy jacket",
    "bottega veneta intrecciato", "bottega veneta jodie bag", "bottega veneta orbit sneaker",
    "number nine skull cashmere", "number nine kurt cobain", "number nine heart skull",
    "undercover bomber jacket", "undercover 85 bomber", "undercover arts and crafts",
    "undercover leather jacket", "yohji yamamoto coat", "yohji yamamoto boots",
    "yohji yamamoto blazer", "yohji yamamoto y-3", "yohji yamamoto pour homme",
    "comme des garcons jacket", "comme des garcons coat", "junya watanabe coat",
    "ann demeulemeester coat", "ann demeulemeester shirt", "ann demeulemeester blazer",
    "carol christian poell leather", "carol christian poell boots", "carol christian poell coat",
    "haider ackermann coat", "haider ackermann blazer", "haider ackermann silk shirt",
    "vivienne westwood orb necklace", "vivienne westwood armor ring",
    "vivienne westwood corset", "vivienne westwood anglomania jacket",
    "julius cargo pants", "julius boots", "julius bomber jacket", "julius gas mask",
    "boris bidjan saberi leather", "boris bidjan saberi coat",
    "thierry mugler jacket", "thierry mugler coat", "thierry mugler leather",
    "alexander mcqueen bumster", "alexander mcqueen skull scarf", "alexander mcqueen leather jacket",
    "kapital boro jacket", "kapital kountry", "kapital denim", "kapital knit",
    "visvim fbt", "visvim virgil boots", "visvim jacket", "visvim lhamo coat",
    "needles track pants", "needles butterfly jacket", "needles rebuild jacket",
    "sacai leather jacket", "sacai bomber", "sacai blazer",
    "prada nylon jacket", "prada leather jacket", "prada re-nylon", "prada americas cup",
    "enfants riches deprimes", "wacko maria jacket", "gallery dept jeans", "gallery dept hoodie",
    "dries van noten jacket", "dries van noten coat", "mihara yasuhiro sneakers",
    "kiko kostadinov", "a-cold-wall jacket", "craig green jacket", "stone island jacket",
    "issey miyake bao bao bag", "issey miyake pleats please",
]


class TrendEngine:
    """
    Orchestrates trend discovery and opportunity-scored target generation.
    """

    def __init__(self, max_queries: int = 120):
        self.max_queries = max_queries
        self.sources: list[TrendSource] = [
            GrailedVelocitySource(),
        ]
        os.makedirs(DAILY_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)

    # ═══════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════

    async def get_cycle_targets(self, n: int = 60) -> list[str]:
        """
        Returns a varied subset of targets for a single hunt cycle.

        Pulls from the golden catalog (built from real Grailed sold data):
          - Tier 1 items always included (high-price + high-volume)
          - Tier 2: ~70% randomly selected each cycle
          - Tier 3: ~30% randomly selected each cycle
          - Dead queries (50+ runs, 0 deals) excluded throughout

        Falls back to CORE_TARGETS + EXTENDED_TARGETS if catalog unavailable.
        """
        catalog = await self._get_golden_catalog()
        dead = self._get_dead_queries()

        def _clean(queries: list[str]) -> list[str]:
            """Dedupe and remove dead queries from a list."""
            seen = set()
            out = []
            for q in queries:
                ql = q.lower().strip()
                if ql not in seen and ql not in dead:
                    seen.add(ql)
                    out.append(q)
            return out

        if catalog:
            t1 = _clean([e["query"] for e in catalog.get("tier1", [])])
            t2 = _clean([e["query"] for e in catalog.get("tier2", [])])
            t3 = _clean([e["query"] for e in catalog.get("tier3", [])])

            # Tier 1: always all of them
            selected = list(t1)
            used = {q.lower() for q in selected}
            slots_left = n - len(selected)

            # Tier 2: take ~70% randomly
            random.shuffle(t2)
            t2_pick = max(1, int(len(t2) * 0.70))
            for q in t2[:t2_pick]:
                if len(selected) >= n:
                    break
                if q.lower() not in used:
                    selected.append(q)
                    used.add(q.lower())

            # Tier 3: take ~30% randomly
            random.shuffle(t3)
            t3_pick = max(1, int(len(t3) * 0.30))
            for q in t3[:t3_pick]:
                if len(selected) >= n:
                    break
                if q.lower() not in used:
                    selected.append(q)
                    used.add(q.lower())

            logger.info(
                f"🎯 Cycle targets: {len(selected)} total from golden catalog "
                f"(T1={len(t1)}, T2 sample={min(t2_pick, len(t2))}, T3 sample={min(t3_pick, len(t3))}) "
                f"| {len(dead)} dead excluded"
            )
            return selected

        # Fallback: catalog unavailable, use static lists with rotation
        logger.warning("⚠️  Golden catalog unavailable — falling back to static targets")
        return self._fallback_targets(n, dead)

    async def get_today_targets(self) -> list[str]:
        """
        Legacy API: full daily pool for backward compatibility.
        Triggers catalog build if stale; returns all catalog queries.
        """
        catalog = await self._get_golden_catalog()
        if catalog:
            all_q = (
                [e["query"] for e in catalog.get("tier1", [])]
                + [e["query"] for e in catalog.get("tier2", [])]
                + [e["query"] for e in catalog.get("tier3", [])]
            )
            # Dedupe
            seen, out = set(), []
            for q in all_q:
                if q.lower() not in seen:
                    seen.add(q.lower())
                    out.append(q)
            logger.info(f"📋 Full catalog pool: {len(out)} queries")
            return out

        logger.warning("⚠️  Golden catalog unavailable — using fallback targets")
        return list(CORE_TARGETS)

    async def discover_trends(self) -> list[TrendSignal]:
        """Run all signal sources, merge and return sorted signals."""
        logger.info("🔥 Fetching Grailed sold velocity data...")
        all_signals: list[TrendSignal] = []

        results = await asyncio.gather(*[self._safe_fetch(s) for s in self.sources])
        for source, signals in zip(self.sources, results):
            if signals:
                for sig in signals:
                    sig.trend_score *= source.weight
                all_signals.extend(signals)
                logger.info(f"  {source.name}: {len(signals)} signals")

        merged = self._merge_signals(all_signals)
        for sig in merged:
            if len(sig.signal_sources) > 1:
                sig.trend_score = min(1.0, sig.trend_score * 1.3)
                sig.opportunity_score *= 1.3

        # Sort by opportunity score (dollar velocity)
        merged.sort(key=lambda s: s.opportunity_score, reverse=True)
        logger.info(f"  Total merged signals: {len(merged)}")
        return merged

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

    def get_dead_query_report(self) -> list[dict]:
        """Return dead queries (50+ runs, 0 deals) sorted by run count."""
        perf = self._load_performance()
        dead = [
            {"query": q, "runs": d["total_runs"], "last_run": d.get("last_run")}
            for q, d in perf.items()
            if d.get("total_runs", 0) >= DEAD_QUERY_MIN_RUNS
            and d.get("total_deals", 0) == DEAD_QUERY_MAX_DEALS
        ]
        dead.sort(key=lambda x: x["runs"], reverse=True)
        return dead

    def get_catalog_summary(self) -> Optional[dict]:
        """Return a human-readable summary of the current golden catalog."""
        if not os.path.exists(GOLDEN_CATALOG_FILE):
            return None
        try:
            with open(GOLDEN_CATALOG_FILE) as f:
                cat = json.load(f)
            return {
                "generated_at": cat.get("generated_at"),
                "refresh_due": cat.get("refresh_due"),
                "tier1_count": len(cat.get("tier1", [])),
                "tier2_count": len(cat.get("tier2", [])),
                "tier3_count": len(cat.get("tier3", [])),
                "tier1_top5": [e["query"] for e in cat.get("tier1", [])[:5]],
            }
        except Exception:
            return None

    # ═══════════════════════════════════════════════════════════════════
    # GOLDEN CATALOG
    # ═══════════════════════════════════════════════════════════════════

    async def _get_golden_catalog(self) -> Optional[dict]:
        """
        Load the golden catalog, rebuilding it if stale or missing.
        Returns the catalog dict or None on failure.
        """
        if self._catalog_needs_refresh():
            logger.info("📦 Golden catalog is stale or missing — rebuilding...")
            try:
                await self._build_golden_catalog()
            except Exception as e:
                logger.error(f"❌ Catalog build failed: {e}")
                # Return stale catalog if available, rather than nothing
                if os.path.exists(GOLDEN_CATALOG_FILE):
                    logger.warning("⚠️  Returning stale catalog as fallback")
                    return self._load_golden_catalog()
                return None

        return self._load_golden_catalog()

    def _catalog_needs_refresh(self) -> bool:
        """True if catalog doesn't exist or is older than CATALOG_REFRESH_DAYS."""
        if not os.path.exists(GOLDEN_CATALOG_FILE):
            return True
        try:
            with open(GOLDEN_CATALOG_FILE) as f:
                cat = json.load(f)
            refresh_due = cat.get("refresh_due")
            if not refresh_due:
                return True
            due_dt = datetime.fromisoformat(refresh_due)
            return datetime.utcnow() >= due_dt
        except Exception:
            return True

    async def _build_golden_catalog(self):
        """
        Fetch Grailed velocity data and build a tiered golden catalog.
        Persists to GOLDEN_CATALOG_FILE.
        """
        signals = await self.discover_trends()
        signals = self._apply_feedback(signals)

        tier1, tier2, tier3 = [], [], []

        for sig in signals:
            entry = {
                "query": sig.specific_query,
                "brand": sig.brand,
                "item_type": sig.item_type,
                "avg_sold_price": round(sig.avg_sold_price, 2),
                "monthly_volume": sig.est_sold_volume,
                "opportunity_score": round(sig.opportunity_score, 2),
            }

            price = sig.avg_sold_price
            vol   = sig.est_sold_volume

            if price >= TIER1_MIN_PRICE and vol >= TIER1_MIN_VOLUME:
                tier1.append(entry)
            elif price >= TIER2_MIN_PRICE and vol >= TIER2_MIN_VOLUME:
                tier2.append(entry)
            elif price >= TIER3_MIN_PRICE and vol >= TIER3_MIN_VOLUME:
                tier3.append(entry)
            # else: below all floors → not included

        # Sort each tier by opportunity score descending
        for tier in (tier1, tier2, tier3):
            tier.sort(key=lambda e: e["opportunity_score"], reverse=True)

        catalog = {
            "generated_at": datetime.utcnow().isoformat(),
            "refresh_due": (datetime.utcnow() + timedelta(days=CATALOG_REFRESH_DAYS)).isoformat(),
            "thresholds": {
                "tier1": {"min_price": TIER1_MIN_PRICE, "min_volume": TIER1_MIN_VOLUME},
                "tier2": {"min_price": TIER2_MIN_PRICE, "min_volume": TIER2_MIN_VOLUME},
                "tier3": {"min_price": TIER3_MIN_PRICE, "min_volume": TIER3_MIN_VOLUME},
            },
            "tier1": tier1,
            "tier2": tier2,
            "tier3": tier3,
        }

        with open(GOLDEN_CATALOG_FILE, "w") as f:
            json.dump(catalog, f, indent=2)

        logger.info(
            f"  ✅ Golden catalog saved: "
            f"T1={len(tier1)} (≥${TIER1_MIN_PRICE:.0f}/≥{TIER1_MIN_VOLUME}mo), "
            f"T2={len(tier2)} (≥${TIER2_MIN_PRICE:.0f}/≥{TIER2_MIN_VOLUME}mo), "
            f"T3={len(tier3)} (≥${TIER3_MIN_PRICE:.0f}/≥{TIER3_MIN_VOLUME}mo)"
        )
        if tier1:
            logger.info("  🏆 Top Tier 1 items:")
            for e in tier1[:10]:
                logger.info(
                    f"    ${e['avg_sold_price']:.0f} avg × {e['monthly_volume']} sold/mo "
                    f"= ${e['opportunity_score']:.0f} | {e['query']}"
                )

    def _load_golden_catalog(self) -> Optional[dict]:
        if not os.path.exists(GOLDEN_CATALOG_FILE):
            return None
        try:
            with open(GOLDEN_CATALOG_FILE) as f:
                return json.load(f)
        except Exception:
            return None

    # ═══════════════════════════════════════════════════════════════════
    # INTERNAL HELPERS
    # ═══════════════════════════════════════════════════════════════════

    def _fallback_targets(self, n: int, dead: set) -> list[str]:
        """Static fallback when golden catalog is unavailable."""
        candidates = []
        seen = set()
        for q in CORE_TARGETS + EXTENDED_TARGETS:
            ql = q.lower().strip()
            if ql not in seen and ql not in dead:
                candidates.append(q)
                seen.add(ql)
        random.shuffle(candidates)
        return candidates[:n]

    def _get_dead_queries(self) -> set[str]:
        return {d["query"].lower() for d in self.get_dead_query_report()}

    def _apply_feedback(self, trends: list[TrendSignal]) -> list[TrendSignal]:
        """
        Boost/penalize signals based on historical deal performance.
        - >10% hit rate → boost opportunity_score by up to 30%
        - 50+ runs, 0 deals → penalize opportunity_score by 70%
        - 10+ runs, 0 deals → light penalty 40%
        """
        perf = self._load_performance()
        if not perf:
            return trends

        for sig in trends:
            query_lower = sig.specific_query.lower()
            best_match = None
            for q, data in perf.items():
                if q.lower() == query_lower or q.lower() in query_lower or query_lower in q.lower():
                    if best_match is None or data.get("total_deals", 0) > best_match.get("total_deals", 0):
                        best_match = data

            if best_match:
                runs  = best_match.get("total_runs", 0)
                deals = best_match.get("total_deals", 0)
                if runs > 0:
                    hit_rate = deals / runs
                    if hit_rate > 0.1:
                        boost = min(0.3, hit_rate)
                        sig.opportunity_score *= (1 + boost)
                        sig.trend_score = min(1.0, sig.trend_score * (1 + boost))
                    elif runs >= DEAD_QUERY_MIN_RUNS and deals == 0:
                        sig.opportunity_score *= 0.3
                        sig.trend_score *= 0.3
                    elif runs >= 10 and deals == 0:
                        sig.opportunity_score *= 0.6
                        sig.trend_score *= 0.6

        trends.sort(key=lambda s: s.opportunity_score, reverse=True)
        return trends

    async def _safe_fetch(self, source: TrendSource) -> list[TrendSignal]:
        try:
            return await source.fetch_signals()
        except Exception as e:
            logger.error(f"  ❌ {source.name} failed: {e}")
            return []

    def _merge_signals(self, signals: list[TrendSignal]) -> list[TrendSignal]:
        merged: dict[str, TrendSignal] = {}
        for sig in signals:
            key = sig.merge_key
            if key in merged:
                merged[key] = merged[key].merge(sig)
            else:
                merged[key] = sig
        return list(merged.values())

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

    # Legacy method — kept for backward compat but no longer used internally
    def generate_searches(self, trends: list[TrendSignal]) -> list[str]:
        """Legacy: convert signals to query list sorted by opportunity score."""
        queries, used = [], set()
        for sig in sorted(trends, key=lambda s: s.opportunity_score, reverse=True):
            q = sig.specific_query
            if q.lower() not in used:
                used.add(q.lower())
                queries.append(q)
            if len(queries) >= self.max_queries:
                break
        return queries


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    async def main():
        engine = TrendEngine()

        summary = engine.get_catalog_summary()
        if summary:
            print(f"\n📦 Current golden catalog:")
            print(f"   Generated: {summary['generated_at']}")
            print(f"   Refresh due: {summary['refresh_due']}")
            print(f"   Tier 1: {summary['tier1_count']} items")
            print(f"   Tier 2: {summary['tier2_count']} items")
            print(f"   Tier 3: {summary['tier3_count']} items")
            print(f"   Top T1: {summary['tier1_top5']}")
        else:
            print("\n📦 No catalog yet — will build on first call")

        print("\n🎯 Building cycle targets...")
        targets = await engine.get_cycle_targets(n=60)
        print(f"   {len(targets)} targets this cycle")
        for i, q in enumerate(targets, 1):
            print(f"  {i:2}. {q}")

        dead = engine.get_dead_query_report()
        if dead:
            print(f"\n💀 Dead queries ({len(dead)} excluded):")
            for d in dead[:10]:
                print(f"   {d['runs']:3d} runs — {d['query']}")

    asyncio.run(main())
