"""
TrendEngine — Dynamic search target generation for Archive Arbitrage.

Strategy: hunt items that combine HIGH resale price with CONSISTENT sales volume.
Not trending items — consistently liquid, high-value items with real deal room.

Scoring:
    opportunity_score = avg_sold_price × monthly_sold_volume
    e.g. $600 jacket × 10 sales/mo = 6000  (better than $50 tee × 100 sales/mo = 5000)

Rotation model (replaces rigid tier system):
    ALL catalog queries are sorted globally by opportunity score.
    Top ANCHOR_POOL_SIZE → anchor pool: run once every ANCHOR_CYCLE_INTERVAL cycles.
    Rest → rotation pool: weighted-random draw each cycle.
    Per-query cooldown (QUERY_COOLDOWN_MINUTES) prevents re-running before
    sold cache (30 min TTL) would refresh anyway.
    Queries with zero runs always get priority slots.
    Dead queries (DEAD_QUERY_MIN_RUNS runs, 0 deals) stay excluded.

Long-tail pool:
    A static ~80-query set of curated archive brands that may not hit Grailed
    velocity thresholds at any given moment but are consistently liquid.
    Always circulates in the rotation pool at low weight.

Golden Catalog:
    Persisted to data/trends/golden_catalog.json, refreshed weekly.
    Inspectable — shows exactly why each item is being hunted.

Usage:
    engine = TrendEngine()
    targets = await engine.get_cycle_targets(n=20)   # varied per-cycle subset
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

# ── Tier thresholds (used only during catalog BUILD, not rotation) ────────────
# Items must clear BOTH price AND volume floors to enter the catalog.
TIER1_MIN_PRICE  = 400.0
TIER1_MIN_VOLUME = 6

TIER2_MIN_PRICE  = 250.0
TIER2_MIN_VOLUME = 4

TIER3_MIN_PRICE  = 150.0
TIER3_MIN_VOLUME = 2

# ── Rotation model ────────────────────────────────────────────────────────────
# Replaces the old "tier1 always runs" logic.
ANCHOR_POOL_SIZE       = 10   # Top N by opp-score → anchor pool
ANCHOR_CYCLE_INTERVAL  = 3    # Anchors run once every N cycles
ROTATION_CYCLE_SIZE    = 15   # Queries drawn from rotation pool per cycle
QUERY_COOLDOWN_MINUTES = 25   # Skip query if ran less than this many minutes ago
                               # (matches sold_cache TTL of 30 min)
LONGTAIL_PER_CYCLE     = 3    # Long-tail queries included per cycle

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

# ── Long-tail pool ─────────────────────────────────────────────────────────────
# Curated archive queries that may not hit Grailed velocity thresholds at any
# given moment but are consistently liquid and often underscanned.
# These always circulate in the rotation at LONGTAIL_PER_CYCLE slots/cycle.
LONGTAIL_TARGETS = [
    # Helmut Lang deep cuts
    "helmut lang archive jacket", "helmut lang nylon jacket", "helmut lang bondage pants",
    "helmut lang flak jacket", "helmut lang astro biker", "helmut lang painter jeans",
    "helmut lang mesh top", "helmut lang leather shirt",
    # Junya Watanabe
    "junya watanabe man jacket", "junya watanabe denim jacket", "junya watanabe patchwork",
    "junya watanabe comme des garcons jacket", "junya watanabe reconstruction",
    # Yohji Yamamoto
    "yohji yamamoto pour homme jacket", "yohji yamamoto coat black", "yohji yamamoto asymmetric",
    "yohji yamamoto blazer", "y's yohji yamamoto jacket",
    # Kapital
    "kapital boro jacket", "kapital kountry denim", "kapital knit hoodie",
    "kapital century denim", "kapital boro pants",
    # Needles
    "needles track pants", "needles butterfly jacket", "needles rebuild by needles",
    "needles papillon jacket",
    # Walter Van Beirendonck
    "walter van beirendonck jacket", "walter van beirendonck shirt",
    # Raf Simons deep cuts
    "raf simons consumed hoodie", "raf simons tape bomber", "raf simons denim jacket",
    "raf simons knit sweater", "raf simons antwerp jacket", "raf simons riot bomber",
    "raf simons 2001", "raf simons 2002", "raf simons virginia creepers",
    # Number (N)ine
    "number nine leather jacket", "number nine skull cashmere", "number nine kurt cobain",
    "number nine quilted", "number nine heart skull",
    # Undercover deep cuts
    "undercover but beautiful", "undercover arts and crafts", "undercover scab tour",
    "undercover witch cell division", "undercover leather jacket",
    # Ann Demeulemeester
    "ann demeulemeester coat", "ann demeulemeester blazer", "ann demeulemeester shirt",
    "ann demeulemeester leather boots",
    # Carol Christian Poell
    "carol christian poell leather jacket", "carol christian poell coat",
    "carol christian poell boots", "carol christian poell drip rubber",
    # Haider Ackermann
    "haider ackermann leather jacket", "haider ackermann blazer", "haider ackermann silk shirt",
    # Julius
    "julius leather jacket", "julius boots", "julius cargo pants", "julius gas mask hoodie",
    # Issey Miyake
    "issey miyake homme plisse jacket", "issey miyake pleats please coat",
    # Boris Bidjan Saberi
    "boris bidjan saberi jacket", "boris bidjan saberi leather",
    # Dries Van Noten
    "dries van noten embroidered jacket", "dries van noten velvet jacket",
    "dries van noten printed jacket",
    # Jean Colonna
    "jean colonna jacket", "jean colonna leather",
    # Maison Martin Margiela artisanal
    "margiela artisanal jacket", "margiela deconstructed blazer", "margiela numbers label",
    # Thierry Mugler
    "thierry mugler jacket", "thierry mugler leather jacket", "thierry mugler coat",
    # Alexander McQueen archive
    "alexander mcqueen bumster", "alexander mcqueen skull scarf", "alexander mcqueen leather jacket",
    # Comme des Garçons deep cuts
    "comme des garcons homme plus jacket", "comme des garcons noir jacket",
    "comme des garcons shirt jacket",
    # Mihara Yasuhiro
    "mihara yasuhiro boots", "mihara yasuhiro sneakers platform",
]


class TrendEngine:
    """
    Orchestrates trend discovery and opportunity-scored target generation.
    """

    def __init__(self, max_queries: int = 120):
        self.max_queries = max_queries
        self.cycle_counter = 0   # Tracks cycles for anchor rotation interval
        self.sources: list[TrendSource] = [
            GrailedVelocitySource(),
        ]
        os.makedirs(DAILY_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)

    # ═══════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════

    async def get_cycle_targets(self, n: int = 20) -> list[str]:
        """
        Returns a varied, cooldown-aware subset of targets for one hunt cycle.

        Rotation model (replaces old tier1-always logic):
          1. Build a global pool sorted by opportunity score (catalog + long-tail).
          2. Split into anchor pool (top ANCHOR_POOL_SIZE) and rotation pool (rest).
          3. Anchors included only if due (every ANCHOR_CYCLE_INTERVAL cycles)
             AND not in cooldown.
          4. Rotation pool: weighted-random draw (opp-score as weight), skipping
             cooldown queries. Prioritises never-run queries with a strong boost.
          5. Always include LONGTAIL_PER_CYCLE queries from the long-tail pool
             (never-run long-tail queries get priority).
          6. Dead queries excluded throughout.

        Result: full catalog coverage over time, no single query dominates,
        expensive Grailed scrapes not wasted inside sold-cache window.
        """
        catalog = await self._get_golden_catalog()
        dead = self._get_dead_queries()
        perf = self._load_performance()
        now = datetime.utcnow()
        cooldown_delta = timedelta(minutes=QUERY_COOLDOWN_MINUTES)

        def _in_cooldown(query: str) -> bool:
            """True if query ran less than QUERY_COOLDOWN_MINUTES ago."""
            entry = perf.get(query) or perf.get(query.lower())
            if not entry:
                return False
            last = entry.get("last_run")
            if not last:
                return False
            try:
                last_dt = datetime.fromisoformat(last)
                return (now - last_dt) < cooldown_delta
            except (ValueError, TypeError):
                return False

        def _never_run(query: str) -> bool:
            """True only for queries with NO last_run timestamp — completely new queries.
            Queries that were reset (total_runs=0 but last_run exists) are treated
            as cooled-down regulars, not as brand-new, to prevent them dominating
            every cycle after a reset."""
            entry = perf.get(query) or perf.get(query.lower())
            if not entry:
                return True  # Never seen at all
            return entry.get("last_run") is None  # Seen but never actually executed

        def _clean_pool(queries: list[str]) -> list[str]:
            """Dedupe and strip dead queries."""
            seen, out = set(), []
            for q in queries:
                ql = q.lower().strip()
                if ql not in seen and ql not in dead:
                    seen.add(ql)
                    out.append(q)
            return out

        # ── Build global catalog pool sorted by opp score ──────────────────
        if catalog:
            all_entries = (
                catalog.get("tier1", [])
                + catalog.get("tier2", [])
                + catalog.get("tier3", [])
            )
            # Sort globally by opportunity score, best first
            all_entries.sort(key=lambda e: e.get("opportunity_score", 0), reverse=True)
            catalog_queries = _clean_pool([e["query"] for e in all_entries])
            opp_scores = {
                e["query"].lower(): e.get("opportunity_score", 1)
                for e in all_entries
            }
        else:
            catalog_queries = []
            opp_scores = {}

        # Fall back to static lists if catalog empty
        if not catalog_queries:
            logger.warning("⚠️  Golden catalog unavailable — falling back to static targets")
            return self._fallback_targets(n, dead)

        # ── Split into anchor and rotation pools ───────────────────────────
        anchor_pool   = catalog_queries[:ANCHOR_POOL_SIZE]
        rotation_pool = catalog_queries[ANCHOR_POOL_SIZE:]

        selected: list[str] = []
        used: set[str] = set()

        # ── 1. Anchor queries (every ANCHOR_CYCLE_INTERVAL cycles) ─────────
        anchor_due = (self.cycle_counter % ANCHOR_CYCLE_INTERVAL == 0)
        anchors_added = 0
        for q in anchor_pool:
            if q.lower() in used:
                continue
            if anchor_due and not _in_cooldown(q):
                selected.append(q)
                used.add(q.lower())
                anchors_added += 1

        # ── 2. Never-run queries get priority slots ─────────────────────────
        never_run = [q for q in catalog_queries if _never_run(q) and q.lower() not in used]
        for q in never_run[:5]:   # up to 5 priority never-run slots
            if q.lower() not in used and not _in_cooldown(q):
                selected.append(q)
                used.add(q.lower())

        # ── 3. Rotation pool: weighted-random draw ─────────────────────────
        candidates = [q for q in rotation_pool if q.lower() not in used and not _in_cooldown(q)]
        # Weight by opportunity score; never-run queries get a 2× boost
        weights = []
        for q in candidates:
            w = opp_scores.get(q.lower(), 1.0)
            if _never_run(q):
                w *= 2.0
            weights.append(w)

        slots = max(0, ROTATION_CYCLE_SIZE - (len(selected) - anchors_added))
        if candidates and slots > 0:
            k = min(slots, len(candidates))
            total_w = sum(weights)
            norm = [w / total_w for w in weights]
            rotation_picks = []
            # Weighted sample without replacement
            pool_copy = list(zip(candidates, norm))
            for _ in range(k):
                if not pool_copy:
                    break
                r = random.random()
                cumulative = 0.0
                chosen_idx = len(pool_copy) - 1
                for idx, (_, p) in enumerate(pool_copy):
                    cumulative += p
                    if r <= cumulative:
                        chosen_idx = idx
                        break
                chosen_q = pool_copy[chosen_idx][0]
                rotation_picks.append(chosen_q)
                pool_copy.pop(chosen_idx)
                # Re-normalise remaining weights
                remaining_w = sum(p for _, p in pool_copy)
                if remaining_w > 0:
                    pool_copy = [(q, p / remaining_w) for q, p in pool_copy]
            for q in rotation_picks:
                if q.lower() not in used:
                    selected.append(q)
                    used.add(q.lower())

        # ── 4. Long-tail pool ──────────────────────────────────────────────
        lt_never_run = [q for q in LONGTAIL_TARGETS
                        if q.lower() not in dead and q.lower() not in used and _never_run(q)]
        lt_cooled = [q for q in LONGTAIL_TARGETS
                     if q.lower() not in dead and q.lower() not in used
                     and not _never_run(q) and not _in_cooldown(q)]

        # Prioritise never-run long-tail, then cooled-down long-tail
        lt_candidates = lt_never_run + lt_cooled
        random.shuffle(lt_candidates)
        for q in lt_candidates[:LONGTAIL_PER_CYCLE]:
            if q.lower() not in used:
                selected.append(q)
                used.add(q.lower())

        # ── Increment internal cycle counter ──────────────────────────────
        self.cycle_counter += 1

        # ── Log summary ───────────────────────────────────────────────────
        never_run_count = sum(1 for q in selected if _never_run(q))
        logger.info(
            f"🎯 Cycle targets: {len(selected)} queries | "
            f"anchors={anchors_added} (due={anchor_due}) | "
            f"rotation={len(selected) - anchors_added - LONGTAIL_PER_CYCLE} | "
            f"long-tail={min(LONGTAIL_PER_CYCLE, len(lt_candidates))} | "
            f"never-run={never_run_count} | "
            f"{len(dead)} dead excluded | "
            f"catalog size={len(catalog_queries)}"
        )
        return selected

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
        """Static fallback when golden catalog is unavailable. Respects cooldown."""
        perf = self._load_performance()
        now = datetime.utcnow()
        cooldown_delta = timedelta(minutes=QUERY_COOLDOWN_MINUTES)

        def _cooled(q: str) -> bool:
            entry = perf.get(q) or perf.get(q.lower())
            if not entry or not entry.get("last_run"):
                return True
            try:
                return (now - datetime.fromisoformat(entry["last_run"])) >= cooldown_delta
            except (ValueError, TypeError):
                return True

        # Never-run first, then cooled-down, both from combined static pool
        all_static = list(dict.fromkeys(
            q for q in CORE_TARGETS + EXTENDED_TARGETS + LONGTAIL_TARGETS
            if q.lower().strip() not in dead
        ))
        never_run = [q for q in all_static if not perf.get(q) and not perf.get(q.lower())]
        cooled = [q for q in all_static if q not in never_run and _cooled(q)]
        rest = [q for q in all_static if q not in never_run and q not in cooled]

        random.shuffle(never_run)
        random.shuffle(cooled)
        random.shuffle(rest)

        candidates = never_run + cooled + rest
        return candidates[:n]

    def _get_dead_queries(self) -> set[str]:
        return {d["query"].lower() for d in self.get_dead_query_report()}

    def reset_dead_queries(self, queries: list[str] = None) -> int:
        """
        Remove dead-query exclusions so they get another chance.
        Call after adding new sold-data sources (e.g. eBay fallback) that may
        now provide comps for queries that previously had no sold data.

        Args:
            queries: specific queries to reset. If None, resets ALL dead queries.
        Returns:
            number of queries reset.
        """
        perf = self._load_performance()
        dead_set = {d["query"] for d in self.get_dead_query_report()}
        targets = [q for q in (queries or dead_set) if q in perf]
        count = 0
        for q in targets:
            if q in perf:
                # Reset run/deal counters so the query is no longer excluded.
                # Preserve best_gap so we don't lose historical signal entirely.
                perf[q]["total_runs"] = 0
                perf[q]["total_deals"] = 0
                count += 1
        self._save_performance(perf)
        return count

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
