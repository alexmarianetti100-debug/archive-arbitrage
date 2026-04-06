"""
Query Researcher — Automated discovery of high-yield search queries.

Runs overnight to discover new profitable queries by:
1. Generating candidates from product catalog (brand + model combos not in SEARCH_QUERIES)
2. Testing each through get_sold_data() + find_gaps()
3. Measuring deal yield (comps found, gaps detected, profit potential)
4. Promoting winners, discarding losers
5. Logging every experiment to data/experiments/

Usage:
    python -m core.query_researcher generate          # Show candidate queries
    python -m core.query_researcher test [--limit 20]  # Test candidates
    python -m core.query_researcher promote            # Graduate winners
    python -m core.query_researcher run                # Full overnight pipeline
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scrapers.brands import SEARCH_QUERIES, ARCHIVE_BRANDS, PRIORITY_BRANDS
from scrapers.product_fingerprint import MODELS, SUB_BRANDS
from core.target_families import TARGET_FAMILIES
from core.blue_chip_targets import (
    BLUE_CHIP_JEWELRY,
    BLUE_CHIP_BAGS,
)

logger = logging.getLogger(__name__)

EXPERIMENTS_DIR = PROJECT_ROOT / "data" / "experiments"
PROMOTED_PATH = PROJECT_ROOT / "data" / "discovered_queries.json"
PERFORMANCE_PATH = PROJECT_ROOT / "data" / "trends" / "query_performance.json"

# ── Probation / graduation thresholds ───────────────────────────────────────
PROBATION_PER_CYCLE = 2       # Probation queries included per gap_hunter cycle
GRADUATION_MIN_RUNS = 10      # Runs before a probation query can graduate
GRADUATION_MIN_DEALS = 3      # Deals needed across those runs to graduate
DEMOTION_MIN_RUNS = 15        # Runs before a failing query gets demoted
DEMOTION_MAX_DEALS = 0        # Max deals allowed to be considered a dud

# ── Existing query normalization ────────────────────────────────────────────
EXISTING_QUERIES = {q.lower().strip() for q in SEARCH_QUERIES}


# ── Data structures ─────────────────────────────────────────────────────────

@dataclass
class CandidateQuery:
    """A query to test."""
    query: str
    source: str          # "models", "blue_chip", "target_families", "manual"
    brand: str
    model: str = ""
    priority: int = 0    # Higher = test first (based on brand performance)


@dataclass
class ExperimentResult:
    """Result of testing a candidate query."""
    query: str
    source: str
    brand: str
    tested_at: str
    # Comp data
    comp_count: int = 0
    median_price: float = 0.0
    avg_price: float = 0.0
    # Gap data
    deals_found: int = 0
    total_profit_potential: float = 0.0
    best_gap_pct: float = 0.0
    avg_gap_pct: float = 0.0
    # Scoring
    score: float = 0.0
    promoted: bool = False
    discard_reason: str = ""


# ── Brand performance lookup ────────────────────────────────────────────────

def _load_query_performance() -> dict:
    """Load existing query performance data for brand-level scoring."""
    try:
        with open(PERFORMANCE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _extract_brand(query: str) -> str:
    """Extract the brand name from a query by matching against ARCHIVE_BRANDS.

    Handles multi-word brands like 'chrome hearts', 'van cleef', etc.
    Falls back to first word if no match.
    """
    query_lower = query.lower().strip()
    # Try longest brands first to match "chrome hearts" before "chrome"
    for brand in sorted(ARCHIVE_BRANDS, key=len, reverse=True):
        if query_lower.startswith(brand.lower()):
            return brand.lower()
    return query_lower.split()[0] if query_lower else ""


def _brand_deal_rate(brand: str, perf: dict) -> float:
    """Average deals-per-run across all queries for a brand.

    Uses word-boundary matching to avoid 'ace' matching 'backlace'.
    """
    import re
    brand_lower = brand.lower()
    pattern = re.compile(r'\b' + re.escape(brand_lower) + r'\b')
    runs, deals = 0, 0
    for q, data in perf.items():
        if pattern.search(q.lower()):
            runs += data.get("total_runs", 0)
            deals += data.get("total_deals", 0)
    return deals / max(runs, 1)


# ── Candidate generation ────────────────────────────────────────────────────

def generate_candidates() -> list[CandidateQuery]:
    """
    Generate candidate queries from three sources:
    1. MODELS dict × brand names (product_fingerprint.py)
    2. BLUE_CHIP_TARGETS not already in SEARCH_QUERIES
    3. TARGET_FAMILIES canonical names not already queried

    Deduplicates against SEARCH_QUERIES and ranks by brand performance.
    """
    perf = _load_query_performance()
    candidates: dict[str, CandidateQuery] = {}  # query -> CandidateQuery (dedup)

    # Source 1: Brand + Model combos from MODELS dict
    # Only for brands we actually track (ARCHIVE_BRANDS)
    tracked_brands = {b.lower() for b in ARCHIVE_BRANDS}
    for model, brand_list in MODELS.items():
        for brand in brand_list:
            if brand.lower() not in tracked_brands:
                continue
            query = f"{brand} {model}".lower().strip()
            if query in EXISTING_QUERIES or query in candidates:
                continue
            # Skip overly short/generic queries
            if len(query.split()) < 2 or len(model) < 3:
                continue
            candidates[query] = CandidateQuery(
                query=query,
                source="models",
                brand=brand,
                model=model,
                priority=int(_brand_deal_rate(brand, perf) * 100),
            )

    # Source 2: Blue-chip targets not in SEARCH_QUERIES
    for target in BLUE_CHIP_JEWELRY + BLUE_CHIP_BAGS:
        query = target.query.lower().strip()
        if query in EXISTING_QUERIES or query in candidates:
            continue
        brand = _extract_brand(query)
        # Blue chips get a priority boost — they're curated
        candidates[query] = CandidateQuery(
            query=query,
            source="blue_chip",
            brand=brand,
            model=query,
            priority=int(_brand_deal_rate(brand, perf) * 100) + 50,
        )

    # Source 3: TARGET_FAMILIES canonical names
    for family_key, family in TARGET_FAMILIES.items():
        canonical = family.get("canonical", "").lower().strip()
        if not canonical or canonical in EXISTING_QUERIES or canonical in candidates:
            continue
        brand = _extract_brand(canonical)
        candidates[canonical] = CandidateQuery(
            query=canonical,
            source="target_families",
            brand=brand,
            model=family_key,
            priority=int(_brand_deal_rate(brand, perf) * 100) + 25,
        )
        # Also check allowed_queries that aren't in SEARCH_QUERIES
        for aq in family.get("allowed_queries", []):
            aq_lower = aq.lower().strip()
            if aq_lower in EXISTING_QUERIES or aq_lower in candidates:
                continue
            candidates[aq_lower] = CandidateQuery(
                query=aq_lower,
                source="target_families",
                brand=brand,
                model=family_key,
                priority=int(_brand_deal_rate(brand, perf) * 100) + 20,
            )

    # Source 4: Perf gap revival — queries with proven deals NOT in active rotation
    # These were scraped by trend_engine but never added to SEARCH_QUERIES.
    promoted_queries = set()
    try:
        promoted_data = load_promoted()
        promoted_queries = {q.lower() for q in promoted_data}
    except Exception:
        pass

    for q, data in perf.items():
        q_lower = q.lower().strip()
        if q_lower in EXISTING_QUERIES or q_lower in candidates or q_lower in promoted_queries:
            continue
        total_deals = data.get("total_deals", 0)
        total_runs = data.get("total_runs", 0)
        if total_deals < 1 or total_runs < 1:
            continue
        deal_rate = total_deals / total_runs
        brand = _extract_brand(q_lower)
        # Priority based on actual deal rate — these are proven performers
        candidates[q_lower] = CandidateQuery(
            query=q_lower,
            source="perf_revival",
            brand=brand,
            model=q_lower,
            priority=int(deal_rate * 200) + 75,  # Strong boost — proven data
        )

    # Source 5: Under-tested queries — had <10 runs, deserve another shot
    for q, data in perf.items():
        q_lower = q.lower().strip()
        if q_lower in EXISTING_QUERIES or q_lower in candidates or q_lower in promoted_queries:
            continue
        total_runs = data.get("total_runs", 0)
        total_deals = data.get("total_deals", 0)
        if total_runs >= 10 or total_deals > 0:
            continue  # Already handled above or dead
        if total_runs < 1:
            continue
        brand = _extract_brand(q_lower)
        candidates[q_lower] = CandidateQuery(
            query=q_lower,
            source="under_tested",
            brand=brand,
            model=q_lower,
            priority=10,  # Low priority — unproven
        )

    # Filter out confirmed dead queries (10+ runs, 0 deals)
    already_dead = set()
    for q, data in perf.items():
        if data.get("total_runs", 0) >= 10 and data.get("total_deals", 0) == 0:
            already_dead.add(q.lower())

    filtered = {
        q: c for q, c in candidates.items()
        if q not in already_dead
    }

    # Sort by priority descending
    return sorted(filtered.values(), key=lambda c: c.priority, reverse=True)


async def discover_from_grailed(limit: int = 20) -> list[CandidateQuery]:
    """Source 6: Scrape Grailed sold feed to find hot items we don't cover.

    Looks at recently sold items, extracts brand+model combos,
    and returns candidates for brands/pieces not already tracked.
    """
    from scrapers.grailed import GrailedScraper

    candidates = []
    seen = set(EXISTING_QUERIES)

    # Search broad categories that might surface new niches
    discovery_queries = [
        "archive fashion",
        "vintage designer",
        "rare leather jacket",
        "japanese designer",
        "avant garde",
    ]

    try:
        async with GrailedScraper() as scraper:
            for dq in discovery_queries:
                try:
                    sold = await scraper.search_sold(dq, max_results=30)
                    if not sold:
                        continue

                    for item in sold:
                        if not item.price or item.price < 100:
                            continue
                        # Extract brand from title
                        brand = _extract_brand(item.title.lower())
                        if not brand or len(brand) < 3:
                            continue

                        # Build a candidate query from the item
                        title_lower = item.title.lower()
                        # Use brand + first meaningful words as query
                        words = [w for w in title_lower.split()
                                 if w not in brand.split() and len(w) > 2
                                 and w not in {"size", "new", "rare", "vintage", "authentic", "the", "and", "for"}]
                        if not words:
                            continue
                        query = f"{brand} {' '.join(words[:2])}".strip()

                        if query in seen or len(query.split()) < 2:
                            continue
                        seen.add(query)

                        candidates.append(CandidateQuery(
                            query=query,
                            source="grailed_discovery",
                            brand=brand,
                            model=query,
                            priority=int(item.price / 50),  # Higher price = higher priority
                        ))

                    await asyncio.sleep(2)  # Rate limit between discovery queries
                except Exception as e:
                    logger.warning(f"Grailed discovery failed for '{dq}': {e}")

    except Exception as e:
        logger.error(f"Grailed discovery scraper failed: {e}")

    # Dedup and limit
    unique = {c.query: c for c in candidates}
    return sorted(unique.values(), key=lambda c: c.priority, reverse=True)[:limit]


# ── LLM Discovery ───────────────────────────────────────────────────────────

LLM_DISCOVERY_PROMPT = """You are a luxury resale market researcher. Your job is to identify
search queries for items that are frequently MISPRICED on resale platforms like Grailed,
Poshmark, eBay, and Mercari.

We're looking for archive/designer fashion items where:
- Sellers underprice because they don't know the true market value
- There's enough demand that items sell within 30 days
- The item has a median sold price of at least $150

We already track these brands: {existing_brands}

Our best-performing queries by deal rate:
{top_performers}

Based on this, suggest {n} NEW search queries we should test. Focus on:
1. Models/pieces from existing brands that we might be missing
2. Entirely new brands with similar mispricing dynamics
3. Niche categories or collaborations with arbitrage potential

Return ONLY a JSON array of objects, each with "query" and "reasoning" fields.
Example: [{{"query": "issey miyake homme plisse pants", "reasoning": "High resale value, frequently underpriced on Poshmark"}}]

JSON array:"""


async def discover_from_llm(n: int = 15) -> list[CandidateQuery]:
    """Source 7: Use LLM to reason about market gaps and suggest new queries.

    Requires ANTHROPIC_API_KEY in environment.
    """
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — skipping LLM discovery")
        return []

    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed — skipping LLM discovery")
        return []

    perf = _load_query_performance()

    # Build context for the prompt
    existing_brands = ", ".join(sorted(set(b.lower() for b in ARCHIVE_BRANDS)))

    # Top performers by deal rate (min 5 runs)
    top = sorted(
        [(q, d) for q, d in perf.items()
         if d.get("total_runs", 0) >= 5 and d.get("total_deals", 0) > 0],
        key=lambda x: x[1]["total_deals"] / max(x[1]["total_runs"], 1),
        reverse=True,
    )[:15]
    top_performers = "\n".join(
        f"  - \"{q}\" ({d['total_deals']} deals / {d['total_runs']} runs)"
        for q, d in top
    )

    prompt = LLM_DISCOVERY_PROMPT.format(
        existing_brands=existing_brands,
        top_performers=top_performers,
        n=n,
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()

        # Parse JSON response
        import json
        # Handle markdown code blocks
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        suggestions = json.loads(text)

        candidates = []
        seen = set(EXISTING_QUERIES)
        for s in suggestions:
            query = s.get("query", "").lower().strip()
            if not query or query in seen or len(query.split()) < 2:
                continue
            seen.add(query)
            brand = _extract_brand(query)
            candidates.append(CandidateQuery(
                query=query,
                source="llm_discovery",
                brand=brand,
                model=s.get("reasoning", "")[:80],
                priority=40,  # Medium priority — needs validation
            ))

        logger.info(f"LLM suggested {len(candidates)} new queries")
        return candidates

    except Exception as e:
        logger.error(f"LLM discovery failed: {e}")
        return []


# ── Experiment runner ───────────────────────────────────────────────────────

_hunter_instance = None


def _get_hunter():
    """Lazy-init a shared GapHunter instance (heavy to construct)."""
    global _hunter_instance
    if _hunter_instance is None:
        from gap_hunter import GapHunter
        _hunter_instance = GapHunter()
    return _hunter_instance


async def test_candidate(query: str) -> ExperimentResult:
    """Test a single candidate query through GapHunter.get_sold_data + find_gaps."""
    hunter = _get_hunter()

    result = ExperimentResult(
        query=query,
        source="",
        brand="",
        tested_at=datetime.now().isoformat(),
    )

    try:
        sold_data = await hunter.get_sold_data(query, skip_cache=True)
        if sold_data is None:
            result.discard_reason = "no_comps"
            return result

        result.comp_count = sold_data.count
        result.median_price = sold_data.median_price
        result.avg_price = sold_data.avg_price

        if sold_data.count < 3:
            result.discard_reason = "insufficient_comps"
            return result

        gaps = await hunter.find_gaps(query, sold_data)
        result.deals_found = len(gaps)

        if gaps:
            profits = [g.profit_estimate for g in gaps if g.profit_estimate > 0]
            gap_pcts = [g.gap_percent for g in gaps]
            result.total_profit_potential = sum(profits)
            result.best_gap_pct = max(gap_pcts) if gap_pcts else 0
            result.avg_gap_pct = sum(gap_pcts) / len(gap_pcts) if gap_pcts else 0

    except Exception as e:
        logger.error(f"Error testing '{query}': {e}")
        result.discard_reason = f"error: {str(e)[:100]}"

    return result


async def run_experiments(
    candidates: list[CandidateQuery],
    limit: int = 20,
    batch_size: int = 3,
    delay_between_batches: float = 10.0,
) -> list[ExperimentResult]:
    """
    Test candidates in rate-limited batches.

    Args:
        candidates: Sorted candidate queries to test
        limit: Max candidates to test in this run
        batch_size: Concurrent queries per batch
        delay_between_batches: Seconds to wait between batches
    """
    to_test = candidates[:limit]
    results: list[ExperimentResult] = []

    total_batches = (len(to_test) + batch_size - 1) // batch_size
    logger.info(f"Testing {len(to_test)} candidates in {total_batches} batches of {batch_size}")

    for i in range(0, len(to_test), batch_size):
        batch = to_test[i:i + batch_size]
        batch_num = i // batch_size + 1
        logger.info(f"Batch {batch_num}/{total_batches}: {[c.query for c in batch]}")

        tasks = [test_candidate(c.query) for c in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for candidate, result in zip(batch, batch_results):
            if isinstance(result, Exception):
                result = ExperimentResult(
                    query=candidate.query,
                    source=candidate.source,
                    brand=candidate.brand,
                    tested_at=datetime.now().isoformat(),
                    discard_reason=f"exception: {str(result)[:100]}",
                )
            else:
                result.source = candidate.source
                result.brand = candidate.brand
            results.append(result)

        # Rate limiting between batches
        if i + batch_size < len(to_test):
            logger.info(f"Sleeping {delay_between_batches}s before next batch...")
            await asyncio.sleep(delay_between_batches)

    return results


# ── Scoring ─────────────────────────────────────────────────────────────────

def score_result(result: ExperimentResult) -> float:
    """
    Score an experiment result for promotion potential.

    TODO: This is where YOU define what makes a query worth promoting.
    Consider the trade-offs:
    - comp_count: More comps = more reliable pricing, but rare items have fewer
    - deals_found: Direct deal yield, but one run is a small sample
    - median_price: Higher price = bigger absolute profit, but slower sells
    - total_profit_potential: Raw money, but can be one huge outlier
    - best_gap_pct: Signal strength, but extreme gaps may be pricing errors

    Returns: Score from 0-100. Queries scoring >= PROMOTION_THRESHOLD get promoted.
    """
    if result.discard_reason:
        return 0.0
    if result.total_profit_potential < 0:
        return 0.0

    score = 0.0

    # Comp quality (0-30 points): enough comps for reliable pricing?
    if result.comp_count >= 8:
        score += 30
    elif result.comp_count >= 5:
        score += 20
    elif result.comp_count >= 3:
        score += 10

    # Deal yield (0-40 points): did it actually find deals?
    score += min(result.deals_found * 20, 40)

    # Profit magnitude (0-20 points)
    if result.total_profit_potential >= 500:
        score += 20
    elif result.total_profit_potential >= 200:
        score += 15
    elif result.total_profit_potential >= 50:
        score += 10

    # Gap quality (0-10 points)
    if 0.30 <= result.best_gap_pct <= 0.80:
        score += 10  # Sweet spot — not suspiciously high
    elif result.best_gap_pct > 0:
        score += 5

    return score


PROMOTION_THRESHOLD = 50  # Minimum score to promote


# ── Promotion ───────────────────────────────────────────────────────────────

def load_promoted() -> dict[str, dict]:
    """Load previously promoted queries."""
    try:
        with open(PROMOTED_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_promoted(promoted: dict[str, dict]):
    """Save promoted queries atomically (write tmp, then rename)."""
    PROMOTED_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROMOTED_PATH.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(promoted, f, indent=2)
    tmp.rename(PROMOTED_PATH)


def promote_winners(results: list[ExperimentResult]) -> list[str]:
    """Score results, promote winners to probation, return list of newly promoted queries."""
    promoted = load_promoted()
    newly_promoted = []

    for result in results:
        result.score = score_result(result)
        if result.score >= PROMOTION_THRESHOLD:
            result.promoted = True
            if result.query not in promoted:
                promoted[result.query] = {
                    "status": "probation",
                    "promoted_at": datetime.now().isoformat(),
                    "score": result.score,
                    "source": result.source,
                    "comp_count": result.comp_count,
                    "deals_found": result.deals_found,
                    "median_price": result.median_price,
                    "total_profit": result.total_profit_potential,
                    "best_gap": result.best_gap_pct,
                }
                newly_promoted.append(result.query)
                logger.info(f"PROBATION: '{result.query}' (score={result.score:.0f})")
        else:
            if result.discard_reason:
                logger.info(f"DISCARD: '{result.query}' — {result.discard_reason}")
            else:
                logger.info(f"SKIP: '{result.query}' (score={result.score:.0f} < {PROMOTION_THRESHOLD})")

    if newly_promoted:
        save_promoted(promoted)

    return newly_promoted


def get_probation_queries() -> list[str]:
    """Return queries currently in probation status."""
    promoted = load_promoted()
    return [q for q, data in promoted.items() if data.get("status") == "probation"]


def get_graduated_queries() -> list[str]:
    """Return queries that graduated from probation to full rotation."""
    promoted = load_promoted()
    return [q for q, data in promoted.items() if data.get("status") == "graduated"]


def review_promoted() -> dict:
    """Check real-world performance and graduate or demote probation queries.

    Reads query_performance.json for actual scrape results, then:
    - Graduate: queries with >= GRADUATION_MIN_DEALS in >= GRADUATION_MIN_RUNS
    - Demote: queries with <= DEMOTION_MAX_DEALS after >= DEMOTION_MIN_RUNS
    - Keep: everything else stays in probation

    Returns summary dict.
    """
    promoted = load_promoted()
    perf = _load_query_performance()

    graduated, demoted, kept = [], [], []

    for query, data in list(promoted.items()):
        if data.get("status") != "probation":
            continue

        # Look up real scrape stats
        stats = perf.get(query) or perf.get(query.lower(), {})
        runs = stats.get("total_runs", 0)
        deals = stats.get("total_deals", 0)

        if runs >= GRADUATION_MIN_RUNS and deals >= GRADUATION_MIN_DEALS:
            promoted[query]["status"] = "graduated"
            promoted[query]["graduated_at"] = datetime.now().isoformat()
            promoted[query]["real_runs"] = runs
            promoted[query]["real_deals"] = deals
            graduated.append(query)
            logger.info(f"GRADUATED: '{query}' ({deals} deals in {runs} runs)")

        elif runs >= DEMOTION_MIN_RUNS and deals <= DEMOTION_MAX_DEALS:
            promoted[query]["status"] = "demoted"
            promoted[query]["demoted_at"] = datetime.now().isoformat()
            promoted[query]["real_runs"] = runs
            promoted[query]["real_deals"] = deals
            demoted.append(query)
            logger.info(f"DEMOTED: '{query}' ({deals} deals in {runs} runs)")

        else:
            kept.append(query)

    if graduated or demoted:
        save_promoted(promoted)

    return {"graduated": graduated, "demoted": demoted, "kept": kept}


# ── Experiment logging ──────────────────────────────────────────────────────

def log_experiment(results: list[ExperimentResult], run_label: str = ""):
    """Save experiment results to data/experiments/."""
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = f"_{run_label}" if run_label else ""
    filename = f"experiment_{timestamp}{label}.json"

    output = {
        "run_at": datetime.now().isoformat(),
        "label": run_label,
        "total_tested": len(results),
        "total_promoted": sum(1 for r in results if r.promoted),
        "total_with_deals": sum(1 for r in results if r.deals_found > 0),
        "total_no_comps": sum(1 for r in results if r.discard_reason == "no_comps"),
        "results": [asdict(r) for r in results],
    }

    path = EXPERIMENTS_DIR / filename
    with open(path, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Experiment logged to {path}")
    return path


# ── CLI ─────────────────────────────────────────────────────────────────────

def cmd_generate(args):
    """Show candidate queries without testing them."""
    candidates = generate_candidates()
    print(f"\n{'='*70}")
    print(f"  CANDIDATE QUERIES: {len(candidates)} found")
    print(f"{'='*70}\n")

    for i, c in enumerate(candidates, 1):
        print(f"  {i:3d}. [{c.source:16s}] (priority={c.priority:3d}) {c.query}")

    print(f"\n  Sources: "
          f"models={sum(1 for c in candidates if c.source == 'models')}, "
          f"blue_chip={sum(1 for c in candidates if c.source == 'blue_chip')}, "
          f"target_families={sum(1 for c in candidates if c.source == 'target_families')}")
    print()


def cmd_test(args):
    """Test candidate queries."""
    candidates = generate_candidates()
    if not candidates:
        print("No candidates to test.")
        return

    limit = args.limit
    print(f"\nTesting top {limit} candidates (of {len(candidates)} total)...")
    print(f"Batch size: {args.batch_size}, delay: {args.delay}s\n")

    results = asyncio.run(run_experiments(
        candidates,
        limit=limit,
        batch_size=args.batch_size,
        delay_between_batches=args.delay,
    ))

    # Score and log
    for r in results:
        r.score = score_result(r)

    path = log_experiment(results, run_label="test")

    # Print summary
    print(f"\n{'='*70}")
    print(f"  TEST RESULTS")
    print(f"{'='*70}")
    for r in sorted(results, key=lambda r: r.score, reverse=True):
        status = "PROMOTE" if r.score >= PROMOTION_THRESHOLD else "skip"
        if r.discard_reason:
            status = f"DISCARD ({r.discard_reason})"
        print(f"  [{status:>20s}] score={r.score:5.1f}  comps={r.comp_count:2d}  "
              f"deals={r.deals_found}  profit=${r.total_profit_potential:7.0f}  {r.query}")

    print(f"\n  Logged to: {path}\n")


def cmd_promote(args):
    """Review experiment results and promote winners."""
    # Find most recent experiment file
    if not EXPERIMENTS_DIR.exists():
        print("No experiments found. Run 'test' first.")
        return

    experiment_files = sorted(EXPERIMENTS_DIR.glob("experiment_*.json"), reverse=True)
    if not experiment_files:
        print("No experiment files found.")
        return

    latest = experiment_files[0]
    print(f"Loading latest experiment: {latest.name}")

    with open(latest) as f:
        data = json.load(f)

    known_fields = {f.name for f in ExperimentResult.__dataclass_fields__.values()}
    results = [ExperimentResult(**{k: v for k, v in r.items() if k in known_fields}) for r in data["results"]]
    newly_promoted = promote_winners(results)

    if newly_promoted:
        print(f"\nPromoted {len(newly_promoted)} queries:")
        for q in newly_promoted:
            print(f"  + {q}")
        print(f"\nSaved to: {PROMOTED_PATH}")
    else:
        print("\nNo queries met the promotion threshold.")

    # Show promoted inventory
    promoted = load_promoted()
    if promoted:
        print(f"\nTotal promoted queries: {len(promoted)}")


def cmd_review(args):
    """Review probation queries against real scrape performance."""
    print(f"\n{'='*70}")
    print(f"  PROBATION REVIEW")
    print(f"{'='*70}")

    result = review_promoted()

    if result["graduated"]:
        print(f"\n  Graduated ({len(result['graduated'])}):")
        for q in result["graduated"]:
            print(f"    ✓ {q}")

    if result["demoted"]:
        print(f"\n  Demoted ({len(result['demoted'])}):")
        for q in result["demoted"]:
            print(f"    ✗ {q}")

    if result["kept"]:
        print(f"\n  Still in probation ({len(result['kept'])}):")
        perf = _load_query_performance()
        for q in result["kept"]:
            stats = perf.get(q) or perf.get(q.lower(), {})
            runs = stats.get("total_runs", 0)
            deals = stats.get("total_deals", 0)
            print(f"    ~ {q} ({runs} runs, {deals} deals — need {GRADUATION_MIN_RUNS} runs)")

    if not any(result.values()):
        print("\n  No probation queries to review.")

    print()


def cmd_run(args):
    """Full overnight pipeline: generate → test → promote → review → log."""
    print(f"\n{'='*70}")
    print(f"  QUERY RESEARCHER — OVERNIGHT RUN")
    print(f"  Started: {datetime.now().isoformat()}")
    print(f"{'='*70}\n")

    # Step 1: Review existing probation queries
    review_result = review_promoted()
    if review_result["graduated"] or review_result["demoted"]:
        print(f"  Review: {len(review_result['graduated'])} graduated, "
              f"{len(review_result['demoted'])} demoted\n")

    # Step 2: Discover new candidates
    candidates = generate_candidates()
    if not candidates:
        print("No candidates to test. All brand+model combos already covered.")
        return

    limit = args.limit
    print(f"Generated {len(candidates)} candidates, testing top {limit}...\n")

    results = asyncio.run(run_experiments(
        candidates,
        limit=limit,
        batch_size=args.batch_size,
        delay_between_batches=args.delay,
    ))

    newly_promoted = promote_winners(results)
    path = log_experiment(results, run_label="overnight")

    # Summary
    with_deals = [r for r in results if r.deals_found > 0]
    no_comps = [r for r in results if r.discard_reason == "no_comps"]

    print(f"\n{'='*70}")
    print(f"  OVERNIGHT RUN SUMMARY")
    print(f"{'='*70}")
    print(f"  Candidates tested:  {len(results)}")
    print(f"  With deals:         {len(with_deals)}")
    print(f"  No comps:           {len(no_comps)}")
    print(f"  New to probation:   {len(newly_promoted)}")
    if newly_promoted:
        print(f"  New queries:")
        for q in newly_promoted:
            print(f"    + {q}")
    if review_result["graduated"]:
        print(f"  Graduated:          {len(review_result['graduated'])}")
    if review_result["demoted"]:
        print(f"  Demoted:            {len(review_result['demoted'])}")
    print(f"  Experiment log:     {path}")
    print(f"  Finished:           {datetime.now().isoformat()}")
    print(f"{'='*70}\n")


def cmd_research(args):
    """Full research pipeline: all sources → test → present for approval."""
    print(f"\n{'='*70}")
    print(f"  QUERY RESEARCHER — RESEARCH MODE")
    print(f"  Started: {datetime.now().isoformat()}")
    print(f"{'='*70}\n")

    # Phase 1: Gather candidates from all sources
    print("Phase 1: Gathering candidates from all sources...\n")

    # Static sources (1-5)
    static_candidates = generate_candidates()
    by_source = {}
    for c in static_candidates:
        by_source.setdefault(c.source, []).append(c)
    for source, items in sorted(by_source.items()):
        print(f"  {source:20s}: {len(items)} candidates")

    all_candidates = list(static_candidates)

    # Source 6: Grailed market scan
    if not args.skip_grailed:
        print(f"\n  Scanning Grailed sold feed for new opportunities...")
        grailed_candidates = asyncio.run(discover_from_grailed(limit=args.grailed_limit))
        print(f"  {'grailed_discovery':20s}: {len(grailed_candidates)} candidates")
        all_candidates.extend(grailed_candidates)
    else:
        print(f"\n  Skipping Grailed scan (--skip-grailed)")

    # Source 7: LLM discovery
    if not args.skip_llm:
        print(f"\n  Asking LLM for market gap suggestions...")
        llm_candidates = asyncio.run(discover_from_llm(n=args.llm_suggestions))
        print(f"  {'llm_discovery':20s}: {len(llm_candidates)} candidates")
        all_candidates.extend(llm_candidates)
    else:
        print(f"\n  Skipping LLM discovery (--skip-llm)")

    # Dedup across all sources
    seen = set()
    deduped = []
    for c in all_candidates:
        if c.query not in seen:
            seen.add(c.query)
            deduped.append(c)
    deduped.sort(key=lambda c: c.priority, reverse=True)

    print(f"\n  Total unique candidates: {len(deduped)}")

    # Phase 2: Test top candidates
    limit = args.limit
    print(f"\nPhase 2: Testing top {limit} candidates...\n")

    results = asyncio.run(run_experiments(
        deduped,
        limit=limit,
        batch_size=args.batch_size,
        delay_between_batches=args.delay,
    ))

    # Score all
    for r in results:
        r.score = score_result(r)

    path = log_experiment(results, run_label="research")

    # Phase 3: Present results for approval
    viable = [r for r in results if r.score >= PROMOTION_THRESHOLD]
    marginal = [r for r in results if 0 < r.score < PROMOTION_THRESHOLD and not r.discard_reason]
    failed = [r for r in results if r.discard_reason or r.score == 0]

    print(f"\n{'='*70}")
    print(f"  RESEARCH RESULTS — APPROVAL REQUIRED")
    print(f"{'='*70}")

    if viable:
        print(f"\n  RECOMMENDED FOR PROBATION ({len(viable)}):")
        for i, r in enumerate(sorted(viable, key=lambda r: r.score, reverse=True), 1):
            print(f"    {i:2d}. [{r.source:18s}] score={r.score:5.1f}  comps={r.comp_count:2d}  "
                  f"deals={r.deals_found}  profit=${r.total_profit_potential:7.0f}  {r.query}")

    if marginal:
        print(f"\n  MARGINAL — MAYBE ({len(marginal)}):")
        for r in sorted(marginal, key=lambda r: r.score, reverse=True):
            print(f"    ? [{r.source:18s}] score={r.score:5.1f}  comps={r.comp_count:2d}  "
                  f"deals={r.deals_found}  profit=${r.total_profit_potential:7.0f}  {r.query}")

    if failed:
        print(f"\n  FAILED ({len(failed)}):")
        for r in sorted(failed, key=lambda r: r.score, reverse=True)[:10]:
            reason = r.discard_reason or "low score"
            print(f"    ✗ {r.query} — {reason}")
        if len(failed) > 10:
            print(f"    ... and {len(failed) - 10} more")

    print(f"\n  Experiment log: {path}")

    # Approval prompt
    if viable and not args.auto_approve:
        print(f"\n  Options:")
        print(f"    [a] Approve all {len(viable)} recommended queries")
        print(f"    [s] Select individually")
        print(f"    [n] Approve none")
        choice = input(f"\n  Your choice [a/s/n]: ").strip().lower()

        if choice == "a":
            approved = viable
        elif choice == "s":
            approved = []
            for r in sorted(viable, key=lambda r: r.score, reverse=True):
                yn = input(f"    Promote '{r.query}'? (score={r.score:.0f}, {r.deals_found} deals) [y/n]: ").strip().lower()
                if yn == "y":
                    approved.append(r)
        else:
            approved = []

        if approved:
            newly_promoted = promote_winners(approved)
            print(f"\n  Added {len(newly_promoted)} queries to probation.")
        else:
            print(f"\n  No queries promoted.")

    elif viable and args.auto_approve:
        newly_promoted = promote_winners(viable)
        print(f"\n  Auto-approved {len(newly_promoted)} queries to probation.")
    else:
        print(f"\n  No viable queries found this run.")

    print()


def cmd_status(args):
    """Show current state: promoted queries, recent experiments."""
    promoted = load_promoted()
    perf = _load_query_performance()

    probation = {q: d for q, d in promoted.items() if d.get("status") == "probation"}
    graduated = {q: d for q, d in promoted.items() if d.get("status") == "graduated"}
    demoted = {q: d for q, d in promoted.items() if d.get("status") == "demoted"}
    # Legacy entries without status field treated as probation
    legacy = {q: d for q, d in promoted.items() if "status" not in d}

    print(f"\n{'='*70}")
    print(f"  QUERY RESEARCHER STATUS")
    print(f"{'='*70}")

    print(f"\n  Curated SEARCH_QUERIES:  {len(SEARCH_QUERIES)}")
    print(f"  Probation (testing):     {len(probation) + len(legacy)}")
    print(f"  Graduated (full rotation): {len(graduated)}")
    print(f"  Demoted (removed):       {len(demoted)}")

    if graduated:
        print(f"\n  Graduated queries (in full rotation):")
        for q, data in sorted(graduated.items(), key=lambda x: x[1].get("score", 0), reverse=True):
            stats = perf.get(q) or perf.get(q.lower(), {})
            print(f"    ✓ [{data.get('score', 0):5.1f}] {q} "
                  f"({stats.get('total_runs', 0)} runs, {stats.get('total_deals', 0)} deals)")

    active_probation = {**probation, **legacy}
    if active_probation:
        print(f"\n  Probation queries (medium frequency):")
        for q, data in sorted(active_probation.items(), key=lambda x: x[1].get("score", 0), reverse=True):
            stats = perf.get(q) or perf.get(q.lower(), {})
            runs = stats.get("total_runs", 0)
            deals = stats.get("total_deals", 0)
            progress = f"{runs}/{GRADUATION_MIN_RUNS} runs"
            print(f"    ~ [{data.get('score', 0):5.1f}] {q} ({progress}, {deals} deals)")

    # Recent experiments
    if EXPERIMENTS_DIR.exists():
        experiments = sorted(EXPERIMENTS_DIR.glob("experiment_*.json"), reverse=True)[:5]
        if experiments:
            print(f"\n  Recent experiments:")
            for exp in experiments:
                with open(exp) as f:
                    data = json.load(f)
                print(f"    {exp.name}: tested={data['total_tested']}, "
                      f"promoted={data['total_promoted']}, deals={data['total_with_deals']}")
    print()


def main():
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Query Researcher — discover high-yield queries")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # generate
    subparsers.add_parser("generate", help="Show candidate queries")

    # test
    p_test = subparsers.add_parser("test", help="Test candidate queries")
    p_test.add_argument("--limit", type=int, default=20, help="Max queries to test")
    p_test.add_argument("--batch-size", type=int, default=3, help="Concurrent queries per batch")
    p_test.add_argument("--delay", type=float, default=10.0, help="Seconds between batches")

    # promote
    subparsers.add_parser("promote", help="Promote winners from latest experiment")

    # review
    subparsers.add_parser("review", help="Review probation queries — graduate or demote")

    # run (overnight)
    p_run = subparsers.add_parser("run", help="Full overnight: generate → test → promote")
    p_run.add_argument("--limit", type=int, default=30, help="Max queries to test")
    p_run.add_argument("--batch-size", type=int, default=3, help="Concurrent queries per batch")
    p_run.add_argument("--delay", type=float, default=15.0, help="Seconds between batches")

    # research (full pipeline with approval)
    p_research = subparsers.add_parser("research", help="Full research: all sources → test → approve")
    p_research.add_argument("--limit", type=int, default=25, help="Max queries to test")
    p_research.add_argument("--batch-size", type=int, default=3, help="Concurrent queries per batch")
    p_research.add_argument("--delay", type=float, default=12.0, help="Seconds between batches")
    p_research.add_argument("--skip-grailed", action="store_true", help="Skip Grailed sold feed scan")
    p_research.add_argument("--skip-llm", action="store_true", help="Skip LLM discovery")
    p_research.add_argument("--grailed-limit", type=int, default=20, help="Max Grailed discovery candidates")
    p_research.add_argument("--llm-suggestions", type=int, default=15, help="Number of LLM suggestions")
    p_research.add_argument("--auto-approve", action="store_true", help="Auto-approve all viable queries")

    # status
    subparsers.add_parser("status", help="Show researcher state")

    args = parser.parse_args()

    commands = {
        "generate": cmd_generate,
        "test": cmd_test,
        "promote": cmd_promote,
        "review": cmd_review,
        "run": cmd_run,
        "research": cmd_research,
        "status": cmd_status,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
