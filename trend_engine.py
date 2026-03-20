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
from core.query_tiering import get_weight_multiplier, get_tier_summary, QueryTier
from core.query_normalization import normalize_query, promoted_query_multiplier, is_demoted_query, is_promoted_query, is_broad_query, family_id_for_query, is_allowed_family_query

logger = logging.getLogger("trend_engine")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "trends")
DAILY_DIR = os.path.join(DATA_DIR, "daily")
PERFORMANCE_FILE = os.path.join(DATA_DIR, "query_performance.json")
FAMILY_PERFORMANCE_FILE = os.path.join(DATA_DIR, "family_performance.json")
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
ROTATION_CYCLE_SIZE    = 20   # Queries drawn from rotation pool per cycle
QUERY_COOLDOWN_MINUTES = 90   # Skip query if ran less than this many minutes ago
                               # (sold_cache TTL is 4 hours — cache survives one cooldown cycle)
LONGTAIL_PER_CYCLE     = 3    # Long-tail queries included per cycle
PROMOTED_PER_CYCLE     = 4    # Explicit liquidity-first exact queries guaranteed per cycle when available
BROAD_ANCHOR_CAP       = 2    # Prevent broad umbrella queries from dominating anchor slots

# ── Dead query exclusion ──────────────────────────────────────────────────────
DEAD_QUERY_MIN_RUNS  = 25   # After this many runs…
DEAD_QUERY_MAX_DEALS = 0    # …with zero deals → excluded from rotation

# ── Fallback targets (used only when catalog is empty / velocity fetch fails) ─
# HIGH-VALUE TARGETS: Focus on items with strong liquidity and margins
# Based on successful sellers like 4gseller and archivethreads

CORE_TARGETS = [
    # Rick Owens — footwear + outerwear
    "rick owens dunks",
    "rick owens leather jacket",
    "rick owens stooges",
    "rick owens kiss boots",
    "rick owens sneakers",
    "rick owens champion",
    # Rick Owens — pants + bags
    "rick owens cargo pants",
    "rick owens drkshdw pants",
    "rick owens bag",
    # Chrome Hearts — high-volume categories (not style-specific)
    "chrome hearts ring",
    "chrome hearts bracelet",
    "chrome hearts necklace",
    "chrome hearts dagger pendant",
    "chrome hearts paper chain",
    "chrome hearts floral cross",
    "chrome hearts tiny ring",
    "chrome hearts tee",
    "chrome hearts hat",
    "chrome hearts wallet",
    # Margiela
    "maison margiela tabi boots",
    "maison margiela replica gat",
    "maison margiela boots",
    "maison margiela leather jacket",
    # Saint Laurent (Hedi era)
    "saint laurent wyatt boots",
    "saint laurent leather jacket",
    "saint laurent paris oil",
    # Vetements
    "vetements hoodie",
    "vetements total fucking darkness",
    "vetements raincoat",
    "vetements polizei hoodie",
    # JPG
    "jean paul gaultier mesh",
    "jean paul gaultier tattoo",
    "jean paul gaultier corset",
    # Raf Simons (archive)
    "raf simons consumed hoodie",
    "raf simons riot riot riot",
    # Balenciaga (proven performers)
    "balenciaga runner",
    "balenciaga skater sweatpants",
    # Dior Homme (Hedi era)
    "dior homme leather jacket",
    "dior homme jacket",
    # Number Nine
    "number nine leather jacket",
    # Prada
    "prada monolith boots",
    "prada derby",
    "prada america's cup",
    # Helmut Lang (archive)
    "helmut lang leather jacket",
    # ERD
    "enfants riches deprimes hoodie",
    "enfants riches deprimes leather jacket",
    # Bottega Veneta
    "bottega veneta intrecciato",
    "bottega veneta bag",
    # Other archive
    "undercover bomber jacket",
    "undercover tee",
    "vivienne westwood orb",
    "ann demeulemeester boots",
]

# ── Extended luxury targets (high-value accessories and watches) ─
EXTENDED_TARGETS = [
    # Chrome Hearts jewelry (only high-volume, no style-specific ring names)
    "chrome hearts mini cross", "chrome hearts baby fat pendant",
    "chrome hearts belt", "chrome hearts diamond ring",

    # Chrome Hearts clothing (proven performers)
    "chrome hearts cross patch jeans", "chrome hearts cross patch flannel",
    "chrome hearts zip up hoodie", "chrome hearts shorts",
    "chrome hearts deadly doll tank", "chrome hearts matty boy hoodie",
    "chrome hearts trucker jacket", "chrome hearts denim jacket",
    "chrome hearts track pants", "chrome hearts leather cross patch",
    "chrome hearts cross patch hat",

    # Chrome Hearts eyewear (telemetry-proven)
    "chrome hearts vagilante glasses", "chrome hearts trypoleagain glasses",
    "chrome hearts see you tea", "chrome hearts gittin any frame",
    "chrome hearts glitter friends family",
    "chrome hearts sneakers", "chrome hearts boots",

    # Rick Owens (outerwear + footwear expansion)
    "rick owens coat", "rick owens hoodie", "rick owens bomber",
    "rick owens denim jacket", "rick owens biker jacket",
    "rick owens level tee", "rick owens drkshdw jumbo lace",
    "rick owens tractor boots", "rick owens grained leather sneakers",

    # Vetements (expanded)
    "vetements dhl", "vetements dhl tee", "vetements metal hoodie",
    "vetements champion", "vetements oversized hoodie",
    "vetements bomber jacket", "vetements leather jacket",
    "vetements sweatpants", "vetements staff hoodie",

    # Margiela
    "maison margiela deconstructed blazer", "maison margiela glam slam",
    "maison margiela artisanal", "maison margiela duvet coat",
    "maison margiela deconstructed", "maison margiela tabi loafers",

    # Helmut Lang (year-based + feature-based)
    "helmut lang painter jeans", "helmut lang flak jacket",
    "helmut lang bondage pants", "helmut lang bondage jacket",
    "helmut lang 1998", "helmut lang 1999",
    "helmut lang bondage strap", "helmut lang reflective", "helmut lang raw denim",

    # Raf Simons (season + collection queries)
    "raf simons tape bomber", "raf simons sterling ruby",
    "raf simons leather jacket", "raf simons denim jacket",
    "raf simons nebraska", "raf simons parka", "raf simons bomber jacket",
    "raf simons fishtail parka", "raf simons power corruption lies",
    "raf simons peter saville", "raf simons kollaps",

    # JPG (expanded)
    "jean paul gaultier tattoo top", "jean paul gaultier sailor",
    "jean paul gaultier leather jacket", "jean paul gaultier leather pants",
    "jean paul gaultier sheer", "jean paul gaultier cyberbaba",
    "jean paul gaultier maille", "jean paul gaultier boots",

    # Dior Homme (Hedi era — using collection names not season codes)
    "dior homme boots", "dior homme jeans", "dior homme bomber",
    "dior homme navigate", "dior homme luster denim", "dior homme waxed jeans",

    # Balenciaga (archive pieces with proven margin)
    "balenciaga leather jacket", "balenciaga political campaign",
    "balenciaga speedhunters hoodie", "balenciaga destroyed hoodie",
    "balenciaga leather biker", "balenciaga hummer boots",
    "balenciaga lamborghini", "balenciaga lost tape flared",

    # Saint Laurent
    "saint laurent chain wyatt", "saint laurent teddy jacket",
    "saint laurent leather boots",

    # Bottega Veneta
    "bottega veneta chelsea boots", "bottega veneta tire boots",
    "bottega veneta leather jacket",

    # Number Nine
    "number nine skull cashmere", "number nine skull",
    "number nine cargo pants", "number nine denim", "number nine hoodie",

    # Undercover
    "undercover 85 bomber", "undercover arts and crafts",
    "undercover leather jacket", "undercover but beautiful",
    "undercover bones", "undercover scab", "undercover bug denim",

    # ERD (full line)
    "enfants riches deprimes tee", "enfants riches deprimes long sleeve",
    "enfants riches deprimes denim jacket", "enfants riches deprimes jeans",
    "enfants riches deprimes hat", "enfants riches deprimes belt",
    "enfants riches deprimes sweater", "enfants riches deprimes flannel",
    "enfants riches deprimes bomber",

    # Wacko Maria
    "wacko maria leopard", "wacko maria hawaiian", "wacko maria shirt",
    "wacko maria leather jacket", "wacko maria varsity jacket",
    "wacko maria knit cardigan",

    # Ann Demeulemeester
    "ann demeulemeester leather jacket", "ann demeulemeester leather boots",
    "ann demeulemeester lace up boots",

    # CCP
    "carol christian poell leather jacket", "carol christian poell coat",
    "carol christian poell drip sneaker",

    # Vivienne Westwood
    "vivienne westwood orb necklace", "vivienne westwood armor ring",
    "vivienne westwood corset", "vivienne westwood pearl necklace",

    # Julius
    "julius cargo pants", "julius boots", "julius bomber jacket",
    "julius gas mask hoodie", "julius leather jacket",

    # BBS
    "boris bidjan saberi leather", "boris bidjan saberi jacket",

    # Thierry Mugler
    "thierry mugler leather jacket", "thierry mugler blazer",

    # Kapital
    "kapital boro jacket", "kapital kountry", "kapital denim",
    "kapital kountry coat", "kapital denim jacket",

    # Visvim
    "visvim fbt", "visvim virgil boots", "visvim lhamo coat",

    # Hysteric Glamour
    "hysteric glamour leather jacket", "hysteric glamour denim jacket",
    "hysteric glamour jeans", "hysteric glamour tee", "hysteric glamour archive",

    # Prada
    "prada re-nylon", "prada nylon jacket", "prada leather jacket",
    "prada chocolate loafers", "prada leather loafers",
    "prada cotton velvet blouson",

    # Celine (Hedi era)
    "celine leather jacket", "celine teddy jacket", "celine boots",
    "celine western boots", "celine varsity jacket", "celine triomphe belt",

    # Haider Ackermann
    "haider ackermann leather jacket", "haider ackermann blazer",
    "haider ackermann velvet blazer", "haider ackermann silk bomber",

    # Dries Van Noten
    "dries van noten embroidered jacket", "dries van noten velvet blazer",
    "dries van noten floral jacket", "dries van noten coat",

    # Sacai
    "sacai leather jacket", "sacai bomber jacket", "sacai coat",

    # Guidi
    "guidi boots", "guidi back zip boots", "guidi horse leather",
    "guidi 988", "guidi 995", "guidi 986",

    # Acne Studios
    "acne studios leather jacket", "acne studios velocite jacket",

    # The Soloist
    "soloist leather jacket", "takahiromiyashita soloist",

    # Louis Vuitton
    "louis vuitton murakami bag", "louis vuitton trainer",

    # Alexander McQueen
    "alexander mcqueen leather jacket", "alexander mcqueen skull ring",
]

# ── Long-tail pool ─────────────────────────────────────────────────────────────
# Curated archive queries that may not hit Grailed velocity thresholds at any
# given moment but are consistently liquid and often underscanned.
# These always circulate in the rotation at LONGTAIL_PER_CYCLE slots/cycle.
LONGTAIL_TARGETS = [
    # Helmut Lang deep cuts
    "helmut lang archive jacket", "helmut lang nylon jacket",
    "helmut lang mesh top", "helmut lang leather shirt",
    # Kapital
    "kapital kountry denim", "kapital century denim",
    # Raf Simons deep archive
    "raf simons knit sweater", "raf simons antwerp jacket",
    "raf simons 2001", "raf simons 2002",
    "raf simons peter saville joy division",
    # Number (N)ine
    "number nine quilted",
    # Undercover deep cuts
    "undercover scab tour", "undercover witch cell division",
    # Carol Christian Poell
    "carol christian poell boots",
    # Dries Van Noten
    "dries van noten printed jacket",
    # Thierry Mugler
    "thierry mugler coat",
    # Vetements niche
    "vetements inside out", "vetements haute couture",
    # Wacko Maria niche
    "wacko maria guilty parties", "wacko maria tim lehi",
    # Visvim niche
    "visvim ring",
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
            canonical = normalize_query(query)
            entry = perf.get(canonical) or perf.get(query) or perf.get(query.lower())
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
            canonical = normalize_query(query)
            entry = perf.get(canonical) or perf.get(query) or perf.get(query.lower())
            if not entry:
                return True  # Never seen at all
            return entry.get("last_run") is None  # Seen but never actually executed

        def _under_evaluated(query: str) -> bool:
            """True if query has <3 runs — not enough data for tiering to classify."""
            canonical = normalize_query(query)
            entry = perf.get(canonical) or perf.get(query) or perf.get(query.lower())
            if not entry:
                return True
            return entry.get("total_runs", 0) < 3

        def _clean_pool(queries: list[str]) -> list[str]:
            """Dedupe, canonicalize, and strip dead/demoted queries."""
            seen, out = set(), []
            for q in queries:
                canonical = normalize_query(q)
                ql = canonical.lower().strip()
                if (
                    ql not in seen
                    and ql not in dead
                    and not is_demoted_query(canonical)
                    and is_allowed_family_query(canonical)
                ):
                    seen.add(ql)
                    out.append(canonical)
            return out

        # ── Build global catalog pool sorted by opp score ──────────────────
        if catalog:
            all_entries = (
                catalog.get("tier1", [])
                + catalog.get("tier2", [])
                + catalog.get("tier3", [])
            )
            # Liquidity gate: skip queries with < 5 monthly sales regardless
            # of margin — too illiquid to be actionable for subscribers.
            pre_filter = len(all_entries)
            all_entries = [e for e in all_entries if e.get("monthly_volume", 0) >= 5]
            if len(all_entries) < pre_filter:
                logger.info(
                    f"  Liquidity filter: dropped {pre_filter - len(all_entries)} "
                    f"queries with <5 monthly sales"
                )
            # Sort globally by opportunity score, best first
            all_entries.sort(key=lambda e: e.get("opportunity_score", 0), reverse=True)
            catalog_queries = _clean_pool([e["query"] for e in all_entries])
            opp_scores = {}
            for e in all_entries:
                canonical = normalize_query(e["query"])
                score = e.get("opportunity_score", 1) * promoted_query_multiplier(canonical)
                opp_scores[canonical.lower()] = max(score, opp_scores.get(canonical.lower(), 0))
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
        used_families: set[str] = set()

        # ── 1. Anchor queries (every ANCHOR_CYCLE_INTERVAL cycles) ─────────
        anchor_due = (self.cycle_counter % ANCHOR_CYCLE_INTERVAL == 0)
        anchors_added = 0
        broad_anchors_added = 0
        for q in anchor_pool:
            family_id = family_id_for_query(q)
            if q.lower() in used or family_id in used_families:
                continue
            if is_broad_query(q) and broad_anchors_added >= BROAD_ANCHOR_CAP:
                continue
            if anchor_due and not _in_cooldown(q):
                selected.append(q)
                used.add(q.lower())
                used_families.add(family_id)
                anchors_added += 1
                if is_broad_query(q):
                    broad_anchors_added += 1

        # ── 2. Promoted liquidity-first exact queries ───────────────────────
        promoted_pool = [
            q for q in catalog_queries
            if is_promoted_query(q)
            and q.lower() not in used
            and family_id_for_query(q) not in used_families
            and not _in_cooldown(q)
        ]
        promoted_added = 0
        for q in promoted_pool[:PROMOTED_PER_CYCLE]:
            family_id = family_id_for_query(q)
            if q.lower() not in used and family_id not in used_families:
                selected.append(q)
                used.add(q.lower())
                used_families.add(family_id)
                promoted_added += 1

        # ── 3. Never-run queries get priority slots ─────────────────────────
        never_run = [
            q for q in catalog_queries
            if _never_run(q) and q.lower() not in used and family_id_for_query(q) not in used_families
        ]
        for q in never_run[:5]:   # up to 5 priority never-run slots
            family_id = family_id_for_query(q)
            if q.lower() not in used and family_id not in used_families and not _in_cooldown(q):
                selected.append(q)
                used.add(q.lower())
                used_families.add(family_id)

        # ── 4. Rotation pool: weighted-random draw ─────────────────────────
        candidates = [
            q for q in rotation_pool
            if q.lower() not in used and family_id_for_query(q) not in used_families and not _in_cooldown(q)
        ]
        # Weight by opportunity score, modulated by query tier (A/B/trap)
        # and never-run boost
        weights = []
        for q in candidates:
            w = opp_scores.get(q.lower(), 1.0)
            if _never_run(q):
                w *= 2.0
            elif _under_evaluated(q):
                w *= 1.5  # boost queries with <3 runs to reach classification threshold
            # Apply tier-based weight multiplier from telemetry
            w *= get_weight_multiplier(q, perf)
            w *= promoted_query_multiplier(q)
            if is_broad_query(q):
                w *= 0.55
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
                family_id = family_id_for_query(q)
                if q.lower() not in used and family_id not in used_families:
                    selected.append(q)
                    used.add(q.lower())
                    used_families.add(family_id)

        # ── 4. Long-tail pool ──────────────────────────────────────────────
        lt_never_run = [q for q in LONGTAIL_TARGETS
                        if q.lower() not in dead and q.lower() not in used
                        and family_id_for_query(q) not in used_families and _never_run(q)]
        lt_cooled = [q for q in LONGTAIL_TARGETS
                     if q.lower() not in dead and q.lower() not in used
                     and family_id_for_query(q) not in used_families
                     and not _never_run(q) and not _in_cooldown(q)]

        # Prioritise never-run long-tail, then cooled-down long-tail
        lt_candidates = lt_never_run + lt_cooled
        random.shuffle(lt_candidates)
        for q in lt_candidates[:LONGTAIL_PER_CYCLE]:
            family_id = family_id_for_query(q)
            if q.lower() not in used and family_id not in used_families:
                selected.append(q)
                used.add(q.lower())
                used_families.add(family_id)

        # ── Increment internal cycle counter ──────────────────────────────
        self.cycle_counter += 1

        # ── Log summary ───────────────────────────────────────────────────
        never_run_count = sum(1 for q in selected if _never_run(q))
        logger.info(
            f"🎯 Cycle targets: {len(selected)} queries | "
            f"anchors={anchors_added} (due={anchor_due}, broad={broad_anchors_added}) | "
            f"promoted={promoted_added} | "
            f"rotation={len(selected) - anchors_added - promoted_added - LONGTAIL_PER_CYCLE} | "
            f"long-tail={min(LONGTAIL_PER_CYCLE, len(lt_candidates))} | "
            f"never-run={never_run_count} | "
            f"{len(dead)} dead excluded | "
            f"catalog size={len(catalog_queries)}"
        )
        # Log query tier distribution across full catalog
        try:
            tier_summary = get_tier_summary(perf)
            logger.info(
                f"📊 Query tiers: A={tier_summary['a_count']} "
                f"B={tier_summary['b_count']} "
                f"trap={tier_summary['trap_count']}"
            )
            if tier_summary["worst_traps"]:
                logger.debug(f"   Trap queries: {', '.join(tier_summary['worst_traps'][:3])}")
        except Exception:
            pass  # tier logging is non-critical
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
                canonical = normalize_query(q)
                if canonical.lower() not in seen and not is_demoted_query(canonical):
                    seen.add(canonical.lower())
                    out.append(canonical)
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

    def log_query_performance(self, query: str, found_deals: int, best_gap_pct: float = 0.0, metrics: Optional[dict] = None):
        """Track which queries actually found deals (feedback loop)."""
        perf = self._load_performance()
        canonical = normalize_query(query)
        if canonical not in perf:
            perf[canonical] = {
                "total_runs": 0,
                "total_deals": 0,
                "best_gap": 0,
                "last_run": None,
                "raw_items_found": 0,
                "post_filter_candidates": 0,
                "public_alerts_sent": 0,
                "brand_mismatch_skips": 0,
                "category_mismatch_skips": 0,
                "stale_skips": 0,
                "rep_ceiling_skips": 0,
                "implausible_gap_skips": 0,
                "low_trust_skips": 0,
                "validation_failed": 0,
                "junk_ratio": 0.0,
                "alert_ratio": 0.0,
                "aliases": [],
            }
        if query != canonical and query not in perf[canonical].get("aliases", []):
            perf[canonical].setdefault("aliases", []).append(query)
        perf[canonical]["total_runs"] += 1
        perf[canonical]["total_deals"] += found_deals
        perf[canonical]["best_gap"] = max(perf[canonical]["best_gap"], best_gap_pct)
        perf[canonical]["last_run"] = datetime.utcnow().isoformat()

        metrics = metrics or {}
        for src_key, dest_key in [
            ("raw_items_found", "raw_items_found"),
            ("post_filter_candidates", "post_filter_candidates"),
            ("public_alerts_sent", "public_alerts_sent"),
            ("brand_mismatch_skips", "brand_mismatch_skips"),
            ("category_mismatch_skips", "category_mismatch_skips"),
            ("stale_skips", "stale_skips"),
            ("rep_ceiling_skips", "rep_ceiling_skips"),
            ("implausible_gap_skips", "implausible_gap_skips"),
            ("low_trust_skips", "low_trust_skips"),
            ("validation_failed", "validation_failed"),
        ]:
            perf[canonical][dest_key] += int(metrics.get(src_key, 0) or 0)

        raw_items = perf[canonical].get("raw_items_found", 0)
        candidates = perf[canonical].get("post_filter_candidates", 0)
        alerts = perf[canonical].get("public_alerts_sent", 0)
        perf[canonical]["junk_ratio"] = round(1 - (candidates / raw_items), 4) if raw_items else 0.0
        perf[canonical]["alert_ratio"] = round(alerts / perf[canonical]["total_runs"], 4) if perf[canonical]["total_runs"] else 0.0

        # Stamp the current tier classification for observability
        from core.query_tiering import classify_query
        tier_result = classify_query(canonical, perf[canonical])
        perf[canonical]["tier"] = tier_result.tier.value
        perf[canonical]["tier_reason"] = tier_result.reason

        family_perf = self._load_family_performance()
        family_id = family_id_for_query(canonical)
        family_entry = family_perf.setdefault(family_id, {
            "family_id": family_id,
            "canonical_query": canonical,
            "queries": [],
            "total_runs": 0,
            "total_deals": 0,
            "best_gap": 0.0,
            "raw_items_found": 0,
            "post_filter_candidates": 0,
            "public_alerts_sent": 0,
            "validation_failed": 0,
            "junk_ratio": 0.0,
            "alert_ratio": 0.0,
        })
        if canonical not in family_entry["queries"]:
            family_entry["queries"].append(canonical)
        family_entry["total_runs"] += 1
        family_entry["total_deals"] += found_deals
        family_entry["best_gap"] = max(family_entry["best_gap"], best_gap_pct)
        family_entry["raw_items_found"] += int(metrics.get("raw_items_found", 0) or 0)
        family_entry["post_filter_candidates"] += int(metrics.get("post_filter_candidates", 0) or 0)
        family_entry["public_alerts_sent"] += int(metrics.get("public_alerts_sent", 0) or 0)
        family_entry["validation_failed"] += int(metrics.get("validation_failed", 0) or 0)
        raw_items_f = family_entry["raw_items_found"]
        candidates_f = family_entry["post_filter_candidates"]
        alerts_f = family_entry["public_alerts_sent"]
        family_entry["junk_ratio"] = round(1 - (candidates_f / raw_items_f), 4) if raw_items_f else 0.0
        family_entry["alert_ratio"] = round(alerts_f / family_entry["total_runs"], 4) if family_entry["total_runs"] else 0.0

        self._save_performance(perf)
        self._save_family_performance(family_perf)

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

    def get_family_performance_summary(self, limit: int = 10) -> list[dict]:
        """Return top family-level performance summaries for debugging/reporting."""
        perf = self._load_family_performance()
        rows = list(perf.values())
        rows.sort(key=lambda x: (x.get("public_alerts_sent", 0), x.get("total_deals", 0), x.get("best_gap", 0.0)), reverse=True)
        return rows[:limit]

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
        canonical_entries: dict[str, dict] = {}
        skipped_by_policy = 0

        for sig in signals:
            canonical = normalize_query(sig.specific_query)
            if is_demoted_query(canonical) or not is_allowed_family_query(canonical):
                skipped_by_policy += 1
                continue

            entry = canonical_entries.get(canonical)
            if not entry:
                canonical_entries[canonical] = {
                    "query": canonical,
                    "brand": sig.brand,
                    "item_type": sig.item_type,
                    "avg_sold_price": round(sig.avg_sold_price, 2),
                    "monthly_volume": sig.est_sold_volume,
                    "opportunity_score": round(sig.opportunity_score * promoted_query_multiplier(canonical), 2),
                }
            else:
                # Merge duplicate/alias signals conservatively: keep the strongest observed
                # opportunity signature rather than double-counting duplicate families.
                entry["avg_sold_price"] = max(entry["avg_sold_price"], round(sig.avg_sold_price, 2))
                entry["monthly_volume"] = max(entry["monthly_volume"], sig.est_sold_volume)
                entry["opportunity_score"] = max(
                    entry["opportunity_score"],
                    round(sig.opportunity_score * promoted_query_multiplier(canonical), 2),
                )

        for entry in canonical_entries.values():
            price = entry["avg_sold_price"]
            vol = entry["monthly_volume"]

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
            f"T3={len(tier3)} (≥${TIER3_MIN_PRICE:.0f}/≥{TIER3_MIN_VOLUME}mo) | "
            f"canonical={len(canonical_entries)} | policy-skipped={skipped_by_policy}"
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
            canonical = normalize_query(q)
            entry = perf.get(canonical) or perf.get(q) or perf.get(q.lower())
            if not entry or not entry.get("last_run"):
                return True
            try:
                return (now - datetime.fromisoformat(entry["last_run"])) >= cooldown_delta
            except (ValueError, TypeError):
                return True

        # Never-run first, then cooled-down, both from combined static pool
        canonical_static = [normalize_query(q) for q in CORE_TARGETS + EXTENDED_TARGETS + LONGTAIL_TARGETS]
        all_static = list(dict.fromkeys(
            q for q in canonical_static
            if q.lower().strip() not in dead and not is_demoted_query(q) and is_allowed_family_query(q)
        ))
        promoted = [q for q in all_static if is_promoted_query(q) and _cooled(q)]
        never_run = [q for q in all_static if q not in promoted and not perf.get(q) and not perf.get(q.lower())]
        cooled = [q for q in all_static if q not in never_run and _cooled(q)]
        rest = [q for q in all_static if q not in never_run and q not in cooled]

        random.shuffle(promoted)
        random.shuffle(never_run)
        random.shuffle(cooled)
        random.shuffle(rest)

        candidates = promoted[:PROMOTED_PER_CYCLE] + never_run + cooled + rest
        out, used_families = [], set()
        for q in candidates:
            family_id = family_id_for_query(q)
            if family_id in used_families:
                continue
            out.append(q)
            used_families.add(family_id)
            if len(out) >= n:
                break
        return out

    def _get_dead_queries(self) -> set[str]:
        dead = {normalize_query(d["query"]).lower() for d in self.get_dead_query_report()}
        dead.update({q for q in dead if is_demoted_query(q)})
        return dead

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
                    raw = json.load(f)
                merged: dict[str, dict] = {}
                for query, data in raw.items():
                    canonical = normalize_query(query)
                    entry = merged.setdefault(canonical, {
                        "total_runs": 0,
                        "total_deals": 0,
                        "best_gap": 0,
                        "last_run": None,
                        "raw_items_found": 0,
                        "post_filter_candidates": 0,
                        "public_alerts_sent": 0,
                        "brand_mismatch_skips": 0,
                        "category_mismatch_skips": 0,
                        "stale_skips": 0,
                        "rep_ceiling_skips": 0,
                        "implausible_gap_skips": 0,
                        "low_trust_skips": 0,
                        "validation_failed": 0,
                        "junk_ratio": 0.0,
                        "alert_ratio": 0.0,
                        "aliases": [],
                    })
                    for key in [
                        "total_runs", "total_deals", "raw_items_found", "post_filter_candidates",
                        "public_alerts_sent", "brand_mismatch_skips", "category_mismatch_skips",
                        "stale_skips", "rep_ceiling_skips", "implausible_gap_skips", "low_trust_skips",
                        "validation_failed",
                    ]:
                        entry[key] += int(data.get(key, 0) or 0)
                    entry["best_gap"] = max(entry["best_gap"], float(data.get("best_gap", 0) or 0))
                    last_run = data.get("last_run")
                    if last_run and (not entry["last_run"] or last_run > entry["last_run"]):
                        entry["last_run"] = last_run
                    if query != canonical and query not in entry["aliases"]:
                        entry["aliases"].append(query)
                for canonical, entry in merged.items():
                    raw_items = entry.get("raw_items_found", 0)
                    candidates = entry.get("post_filter_candidates", 0)
                    alerts = entry.get("public_alerts_sent", 0)
                    entry["junk_ratio"] = round(1 - (candidates / raw_items), 4) if raw_items else 0.0
                    entry["alert_ratio"] = round(alerts / entry["total_runs"], 4) if entry["total_runs"] else 0.0
                return merged
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save_performance(self, perf: dict):
        with open(PERFORMANCE_FILE, "w") as f:
            json.dump(dict(sorted(perf.items())), f, indent=2)

    def _load_family_performance(self) -> dict:
        if os.path.exists(FAMILY_PERFORMANCE_FILE):
            try:
                with open(FAMILY_PERFORMANCE_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save_family_performance(self, perf: dict):
        with open(FAMILY_PERFORMANCE_FILE, "w") as f:
            json.dump(dict(sorted(perf.items())), f, indent=2)

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
