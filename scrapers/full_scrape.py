#!/usr/bin/env python3
"""
Full Scrape — All platforms, trending-first strategy.

1. Analyze Grailed sold data to find highest-volume items
2. Search ALL platforms (Grailed, Poshmark, Mercari, Vinted, eBay) for those items
3. Reverse image search to ID exact model + get precise comps
4. Demand/trend scoring for each item
5. Price check against Grailed comps (generic + image-matched)
6. Send alerts to Discord + Telegram for profitable finds

Usage:
    python full_scrape.py                      # Default: top 20 trending queries
    python full_scrape.py --queries 30         # More queries
    python full_scrape.py --brands-only        # Skip trending, just scrape priority brands
    python full_scrape.py --min-margin 0.30    # Override min margin
    python full_scrape.py --min-profit 100     # Override min profit
    python full_scrape.py --no-auth            # Skip authenticity checks
    python full_scrape.py --no-image-id        # Skip reverse image search
    python full_scrape.py --dry-run            # Find deals but don't send alerts
"""

import asyncio
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Force unbuffered output
os.environ["PYTHONUNBUFFERED"] = "1"

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from scrapers import (
    GrailedScraper,
    PoshmarkScraper,
    EbayScraper,
    ARCHIVE_BRANDS,
    PRIORITY_BRANDS,
    ScrapedItem,
)
from scrapers.mercari_subprocess import mercari_search

# Optional scrapers
try:
    from scrapers import VintedScraper
except ImportError:
    VintedScraper = None

from scrapers.trending_analyzer import TrendingAnalyzer, save_report
from api.services.pricing import PricingService
from db.sqlite_models import init_db, save_item, Item
from alerts import AlertService, AlertItem, alert_if_profitable

# Telegram alerts
try:
    from telegram_bot import send_deal_to_subscribers
    TELEGRAM_AVAILABLE = True
except Exception:
    TELEGRAM_AVAILABLE = False

# Authenticity checker
try:
    from authenticity_v2 import AuthenticityCheckerV2
    AUTH_V2_AVAILABLE = True
except Exception:
    AUTH_V2_AVAILABLE = False

# CLIP-based product identification (local, unlimited)
try:
    from scrapers.clip_matcher import CLIPMatcher
    IMAGE_ID_AVAILABLE = True
except Exception as _e:
    IMAGE_ID_AVAILABLE = False
    _clip_import_err = str(_e)
else:
    _clip_import_err = ""

# Demand scoring
try:
    from scrapers.demand_scorer import score_demand
    DEMAND_AVAILABLE = True
except Exception:
    DEMAND_AVAILABLE = False

# ── Config ──────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "data"
TRENDING_CACHE = DATA_DIR / "trending_report.json"
SCRAPE_STATE = DATA_DIR / "full_scrape_state.json"
TRENDING_CACHE_HOURS = 4

# Pagination state — rotate through queries so each run gets fresh items
PAGE_STATE_FILE = DATA_DIR / "page_state.json"

# Brands with relaxed thresholds (high volume, tighter margins but still profitable)
RELAXED_BRANDS = {
    "balenciaga": {"min_margin": 0.40, "min_profit": 150},
}

# All sources to search for deals
# Standard scrapers (async context manager pattern)
ALL_SOURCES = {
    "grailed": GrailedScraper,
    "poshmark": PoshmarkScraper,
    "ebay": EbayScraper,
}

# Mercari runs in a subprocess (Playwright crashes event loop otherwise)
MERCARI_ENABLED = True

if VintedScraper is not None:
    ALL_SOURCES["vinted"] = VintedScraper


# ── Helpers ─────────────────────────────────────────────────────────────────

def detect_brand(title: str) -> str | None:
    title_lower = title.lower()
    for brand in ARCHIVE_BRANDS:
        if brand.lower() in title_lower:
            return brand
    return None


def detect_category(title: str) -> str | None:
    title_lower = title.lower()
    cats = {
        "jacket": ["jacket", "blazer", "coat", "bomber", "parka"],
        "pants": ["pants", "trousers", "jeans", "denim"],
        "shirt": ["shirt", "button up", "flannel"],
        "tee": ["t-shirt", "tee", "tshirt"],
        "hoodie": ["hoodie", "hooded", "pullover"],
        "sweater": ["sweater", "knit", "cardigan"],
        "shoes": ["shoes", "sneakers", "boots"],
        "bag": ["bag", "backpack", "tote"],
    }
    for cat, kws in cats.items():
        if any(kw in title_lower for kw in kws):
            return cat
    return None


def load_cached_trending() -> list[str]:
    """Load trending queries if cache is fresh."""
    if TRENDING_CACHE.exists():
        try:
            data = json.loads(TRENDING_CACHE.read_text())
            ts = datetime.fromisoformat(data.get("timestamp", "2000-01-01"))
            if datetime.utcnow() - ts < timedelta(hours=TRENDING_CACHE_HOURS):
                return data.get("recommended_queries", [])
        except Exception:
            pass
    return []


def save_state(state: dict):
    DATA_DIR.mkdir(exist_ok=True)
    SCRAPE_STATE.write_text(json.dumps(state, indent=2, default=str))


# ── Core ────────────────────────────────────────────────────────────────────

async def get_trending_queries(num_queries: int = 20, fresh: bool = False) -> list[str]:
    """Get highest-volume queries from Grailed sold data."""
    # Try cache first (unless forced fresh)
    if not fresh:
        cached = load_cached_trending()
        if cached:
            # Rotate: use page state to serve different slices each run
            page_state = _load_page_state()
            offset = page_state.get("query_offset", 0)
            # Wrap around
            if offset >= len(cached):
                offset = 0
            rotated = cached[offset:] + cached[:offset]
            # Advance offset for next run
            page_state["query_offset"] = (offset + num_queries) % max(len(cached), 1)
            _save_page_state(page_state)
            print(f"📊 Using cached trending queries (offset {offset}, {len(cached)} total)")
            return rotated[:num_queries]

    print("📊 Analyzing Grailed sold data for trending items (fresh)...")
    try:
        async with TrendingAnalyzer() as analyzer:
            report = await asyncio.wait_for(
                analyzer.analyze_trending(items_per_query=40),
                timeout=60,
            )
            analyzer.print_report(report)
            save_report(report, str(TRENDING_CACHE))
            # Reset rotation
            _save_page_state({"query_offset": 0})
            return report.recommended_queries[:num_queries]
    except asyncio.TimeoutError:
        print("⚠ Trending analysis timed out, falling back to priority brands")
        return list(PRIORITY_BRANDS)[:num_queries]


def _load_page_state() -> dict:
    """Load pagination state so each run gets fresh results."""
    if PAGE_STATE_FILE.exists():
        try:
            return json.loads(PAGE_STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_page_state(state: dict):
    DATA_DIR.mkdir(exist_ok=True)
    PAGE_STATE_FILE.write_text(json.dumps(state, indent=2))


async def get_grailed_comps(queries: list[str]) -> dict:
    """Fetch Grailed sold prices for comparison."""
    prices = {}
    page_state = _load_page_state()
    print("\n📈 Fetching Grailed sold comps...")

    async with GrailedScraper() as scraper:
        for q in queries[:30]:
            try:
                sold = await asyncio.wait_for(
                    scraper.search_sold(q, max_results=10),
                    timeout=10,
                )
                if sold:
                    sold_prices = [i.price for i in sold if i.price > 0]
                    if sold_prices:
                        prices[q] = {
                            "avg": sum(sold_prices) / len(sold_prices),
                            "min": min(sold_prices),
                            "max": max(sold_prices),
                            "median": sorted(sold_prices)[len(sold_prices) // 2],
                            "count": len(sold_prices),
                            "_items": sold,
                        }
                        print(f"   ✓ {q}: avg ${prices[q]['avg']:.0f} ({len(sold_prices)} comps)")
                await asyncio.sleep(0.3)
            except asyncio.TimeoutError:
                print(f"   ✗ {q}: timeout")
            except Exception as e:
                print(f"   ✗ {q}: {e}")

    return prices


async def _safe_search(scraper_cls, query: str, max_results: int, timeout: int) -> list[ScrapedItem]:
    """Run a single scraper search with timeout and error isolation."""
    try:
        scraper_ctx = scraper_cls(use_proxies=False)
    except TypeError:
        scraper_ctx = scraper_cls()

    async def _run():
        async with scraper_ctx as scraper:
            return await scraper.search(query, max_results=max_results)

    return await asyncio.wait_for(_run(), timeout=timeout)


async def search_all_platforms(
    query: str,
    sources: dict,
    max_per_source: int = 15,
    seen_ids: set = None,
) -> list[ScrapedItem]:
    """Search all platforms for a query, deduplicating across runs."""
    all_items = []
    if seen_ids is None:
        seen_ids = set()

    SOURCE_TIMEOUT = {"vinted": 20}
    DEFAULT_TIMEOUT = 15

    def _dedup(items_list, label):
        new_items = []
        for item in items_list:
            uid = f"{item.source}:{item.source_id}"
            if uid not in seen_ids:
                seen_ids.add(uid)
                new_items.append(item)
        dupes = len(items_list) - len(new_items)
        if new_items:
            print(f"    ✓ {label}: {len(new_items)} items" + (f" ({dupes} dupes)" if dupes else ""))
            all_items.extend(new_items)
        elif items_list:
            print(f"    · {label}: {len(items_list)} items (all dupes)")
        else:
            print(f"    · {label}: 0 items")

    for name, scraper_cls in sources.items():
        timeout = SOURCE_TIMEOUT.get(name, DEFAULT_TIMEOUT)
        try:
            items = await _safe_search(scraper_cls, query, max_per_source, timeout)
            _dedup(items or [], name)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            print(f"    ✗ {name}: timed out ({timeout}s)")
        except BaseException as e:
            print(f"    ✗ {name}: {str(e)[:80]}")
        await asyncio.sleep(0.5)

    # Mercari via subprocess (isolated from event loop)
    if MERCARI_ENABLED:
        try:
            items = await mercari_search(query, max_results=max_per_source, timeout=45)
            _dedup(items or [], "mercari")
        except Exception as e:
            print(f"    ✗ mercari: {str(e)[:80]}")

    return all_items


async def check_demand(brand: str, title: str) -> dict | None:
    """Score demand/trend for an item via Grailed velocity."""
    if not DEMAND_AVAILABLE:
        return None
    try:
        result = await asyncio.wait_for(
            score_demand(brand, title, max_results=15),
            timeout=15,
        )
        return {
            "score": result.score,
            "level": result.level,
            "sold_count": result.sold_count,
            "active_count": result.active_count,
            "avg_sold_price": result.avg_sold_price,
            "est_days_to_sell": result.est_days_to_sell,
            "reasoning": result.reasoning,
        }
    except (asyncio.TimeoutError, Exception):
        return None


async def run_full_scrape(
    num_queries: int = 20,
    max_per_source: int = 15,
    min_margin: float = 0.25,
    min_profit: float = 50,
    brands_only: bool = False,
    skip_auth: bool = False,
    skip_image_id: bool = False,
    dry_run: bool = False,
    fresh: bool = False,
):
    """Main entry point — trending-first full platform scrape."""

    use_image_id = IMAGE_ID_AVAILABLE and not skip_image_id
    use_demand = DEMAND_AVAILABLE

    print()
    print("=" * 70)
    print("🚀 FULL SCRAPE — All Platforms, Trending-First Strategy")
    print("=" * 70)
    print(f"   Platforms: {', '.join(ALL_SOURCES.keys())}")
    print(f"   Min margin: {min_margin*100:.0f}%  |  Min profit: ${min_profit:.0f}")
    print(f"   Auth checks: {'OFF' if skip_auth else 'ON'}")
    if use_image_id:
        print(f"   Image ID:    ON (CLIP local, no API key)")
    else:
        reason = "disabled" if skip_image_id else f"unavailable ({_clip_import_err if not IMAGE_ID_AVAILABLE else ''})"
        print(f"   Image ID:    OFF ({reason})")
    print(f"   Demand score: {'ON' if use_demand else 'OFF'}")
    print(f"   Alerts: {'DRY RUN' if dry_run else 'Discord + Telegram'}")
    print()

    init_db()
    pricing = PricingService()
    alerts = AlertService(min_profit=min_profit, min_margin=min_margin)
    clip_matcher = None

    # ── Step 1: Build query list ────────────────────────────────────────
    if brands_only:
        queries = list(PRIORITY_BRANDS)
        print(f"📋 Using {len(queries)} priority brands (no trending analysis)")
    else:
        queries = await get_trending_queries(num_queries, fresh=fresh)
        if not queries:
            print("⚠ No trending queries found, falling back to priority brands")
            queries = list(PRIORITY_BRANDS)

    print(f"\n🔍 Searching {len(queries)} queries across {len(ALL_SOURCES)} platforms")
    print(f"   Queries: {', '.join(queries[:8])}{'...' if len(queries) > 8 else ''}")

    # ── Step 2: Grailed sold comps ──────────────────────────────────────
    grailed_comps = await get_grailed_comps(queries)

    # ── Step 2b: Index sold items into CLIP DB (builds over time) ──────
    if use_image_id and clip_matcher:
        indexed_total = 0
        for q, data in grailed_comps.items():
            sold_items = data.pop("_items", [])
            if sold_items:
                try:
                    n = await clip_matcher.index_sold_items(sold_items, brand=q.split()[0])
                    indexed_total += n
                except Exception:
                    pass
        if indexed_total > 0:
            print(f"\n   🧠 Indexed {indexed_total} sold items into CLIP DB (total: {clip_matcher.db.size})")

    # ── Step 3: Search all platforms ────────────────────────────────────
    print(f"\n{'='*70}")
    print("🔎 SEARCHING ALL PLATFORMS")
    print(f"{'='*70}\n")

    stats = {
        "queries": len(queries),
        "total_found": 0,
        "saved": 0,
        "skipped_margin": 0,
        "skipped_auth": 0,
        "skipped_pricing": 0,
        "skipped_demand": 0,
        "image_id_hits": 0,
        "demand_checks": 0,
        "alerts_discord": 0,
        "alerts_telegram": 0,
        "by_source": {},
        "by_brand": {},
    }

    auth_checker = None
    if AUTH_V2_AVAILABLE and not skip_auth:
        auth_checker = AuthenticityCheckerV2()

    # Initialize CLIP matcher for product identification
    clip_matcher = None
    if use_image_id:
        try:
            clip_matcher = CLIPMatcher()
            await clip_matcher.__aenter__()
            print(f"   🧠 CLIP matcher ready (reference DB: {clip_matcher.db.size} items)")
        except Exception as e:
            print(f"   ⚠ CLIP matcher failed to init: {e}")
            clip_matcher = None
            use_image_id = False

    # Track seen items across all queries to avoid duplicates
    global_seen_ids = set()

    for i, query in enumerate(queries):
        print(f"\n  [{i+1}/{len(queries)}] 🔍 {query}")

        items = await search_all_platforms(query, ALL_SOURCES, max_per_source, global_seen_ids)
        stats["total_found"] += len(items)

        if not items:
            continue

        ref = grailed_comps.get(query, {})
        ref_avg = ref.get("avg")

        for scraped in items:
            detected_brand = detect_brand(scraped.title) or query.split()[0]
            category = detect_category(scraped.title)

            # ── Pricing ─────────────────────────────────────────────
            # Use pre-fetched Grailed comps first (fast, no network)
            # Only fall back to async pricing if no comps available
            price_info = None

            if ref_avg and ref_avg > 0 and scraped.price > 0 and scraped.price < ref_avg:
                # We have Grailed comps — calculate directly
                grailed_margin = (ref_avg - scraped.price) / ref_avg
                try:
                    price_info = pricing.calculate_price(
                        source_price=scraped.price,
                        brand=detected_brand,
                        title=scraped.title,
                    )
                    # Override with our better Grailed data
                    if grailed_margin > price_info.margin_percent:
                        price_info.market_price = ref_avg
                        price_info.margin_percent = grailed_margin
                        price_info.recommended_price = ref_avg * 0.85
                except Exception:
                    # Create a minimal price info from Grailed comps
                    from types import SimpleNamespace
                    price_info = SimpleNamespace(
                        market_price=ref_avg,
                        margin_percent=grailed_margin,
                        recommended_price=ref_avg * 0.85,
                        confidence="medium",
                        profit_estimate=ref_avg * 0.85 - scraped.price,
                        comps_count=ref.get("count", 0),
                        season_name=None,
                        season_multiplier=1.0,
                        demand_level="unknown",
                        demand_score=0.0,
                    )

            if price_info is None:
                # No pre-fetched comps — try async pricing (with timeout)
                try:
                    price_info = await asyncio.wait_for(
                        pricing.calculate_price_async(
                            source_price=scraped.price,
                            brand=detected_brand,
                            title=scraped.title,
                            shipping_cost=scraped.shipping_cost or 0,
                        ),
                        timeout=15,
                    )
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    stats["skipped_pricing"] += 1
                    continue
                except Exception:
                    try:
                        price_info = pricing.calculate_price(
                            source_price=scraped.price,
                            brand=detected_brand,
                            title=scraped.title,
                        )
                    except Exception:
                        stats["skipped_pricing"] += 1
                        continue

            # Skip unprofitable
            if price_info.confidence == "skip" or price_info.recommended_price == 0:
                stats["skipped_pricing"] += 1
                continue

            profit = float(price_info.recommended_price) - scraped.price

            # Use relaxed thresholds for specific brands
            brand_lower = detected_brand.lower()
            effective_margin = min_margin
            effective_profit = min_profit
            if brand_lower in RELAXED_BRANDS:
                effective_margin = RELAXED_BRANDS[brand_lower]["min_margin"]
                effective_profit = RELAXED_BRANDS[brand_lower]["min_profit"]

            if price_info.margin_percent < effective_margin or profit < effective_profit:
                stats["skipped_margin"] += 1
                continue

            # ── Authenticity ────────────────────────────────────────
            auth_result = None
            if auth_checker:
                try:
                    auth_result = await auth_checker.check(
                        title=scraped.title,
                        description=scraped.description or "",
                        price=scraped.price,
                        brand=detected_brand,
                        category=category or "",
                        seller_name=scraped.seller or "",
                        seller_sales=getattr(scraped, "seller_sales", 0),
                        seller_rating=getattr(scraped, "seller_rating", None),
                        images=scraped.images,
                        source=scraped.source,
                    )
                    if auth_result.action == "block":
                        stats["skipped_auth"] += 1
                        continue
                    if auth_result.confidence < 0.4:
                        stats["skipped_auth"] += 1
                        continue
                except Exception:
                    pass  # Don't block on auth errors

            # ── Product ID (CLIP image + title parsing, local) ───────
            product_id = None
            if use_image_id and clip_matcher:
                try:
                    img_url = scraped.images[0] if scraped.images else ""
                    product_id = await clip_matcher.identify_and_price(
                        image_url=img_url,
                        title=scraped.title,
                        brand=detected_brand,
                    )

                    if product_id and product_id.get("product_name"):
                        stats["image_id_hits"] += 1
                        pid_name = product_id["product_name"][:50]
                        pid_conf = product_id["confidence"]
                        pid_season = product_id.get("season") or ""
                        pid_method = product_id.get("method", "")
                        print(f"      🔎 ID [{pid_method}]: {pid_name} {pid_season} ({pid_conf:.0%} conf)")

                        # Use CLIP match prices if available
                        pr = product_id.get("price_range")
                        if pr and pr[0] > 0 and pr[1] > 0:
                            image_avg = product_id.get("avg_price", (pr[0] + pr[1]) / 2)
                            if image_avg > scraped.price:
                                img_margin = (image_avg - scraped.price) / image_avg
                                if img_margin > price_info.margin_percent:
                                    price_info.market_price = image_avg
                                    price_info.margin_percent = img_margin
                                    price_info.recommended_price = image_avg * 0.85
                                    print(f"      📸 CLIP comps: ${pr[0]:.0f}-${pr[1]:.0f} → sell at ${price_info.recommended_price:.0f}")

                        # Use precise Grailed comps from identify_and_price
                        pc = product_id.get("precise_comps")
                        if pc and pc.get("avg", 0) > scraped.price:
                            pc_margin = (pc["avg"] - scraped.price) / pc["avg"]
                            if pc_margin > price_info.margin_percent:
                                price_info.market_price = pc["avg"]
                                price_info.margin_percent = pc_margin
                                price_info.recommended_price = pc["avg"] * 0.85
                                print(f"      🎯 Exact comps ({pc['count']}): avg ${pc['avg']:.0f} → sell at ${price_info.recommended_price:.0f}")

                except Exception as e:
                    pass  # Don't block pipeline on ID failures

                # Re-check margin after repricing
                profit = float(price_info.recommended_price) - scraped.price
                if price_info.margin_percent < effective_margin or profit < effective_profit:
                    stats["skipped_margin"] += 1
                    continue

            # ── Demand / Trend Check ────────────────────────────────
            demand_info = None
            if use_demand:
                # Use image-ID'd product name if available for tighter demand scoring
                demand_title = scraped.title
                if product_id and product_id.get("product_name"):
                    demand_title = f"{detected_brand} {product_id['product_name']}"

                demand_info = await check_demand(detected_brand, demand_title)
                if demand_info:
                    stats["demand_checks"] += 1
                    d_emoji = {"hot": "🔥", "warm": "🟡", "cold": "🔵", "dead": "💀"}.get(demand_info["level"], "❓")
                    print(f"      {d_emoji} Demand: {demand_info['level'].upper()} ({demand_info['score']:.0%}) — {demand_info['sold_count']} sold, {demand_info['active_count']} active")

                    # Skip dead-demand items — high margin means nothing if nobody's buying
                    if demand_info["level"] == "dead":
                        stats["skipped_demand"] += 1
                        continue

                    # Attach demand info to price_info for alerts
                    price_info.demand_level = demand_info["level"]
                    price_info.demand_score = demand_info["score"]

                    # If demand scoring found better sold price data, use it
                    if demand_info["avg_sold_price"] > 0:
                        demand_margin = (demand_info["avg_sold_price"] - scraped.price) / demand_info["avg_sold_price"] if demand_info["avg_sold_price"] > scraped.price else 0
                        if demand_margin > price_info.margin_percent:
                            price_info.market_price = demand_info["avg_sold_price"]
                            price_info.margin_percent = demand_margin
                            price_info.recommended_price = demand_info["avg_sold_price"] * 0.85

            # ── Save to DB ──────────────────────────────────────────
            try:
                db_item = Item(
                    source=scraped.source,
                    source_id=scraped.source_id,
                    source_url=scraped.url,
                    title=scraped.title,
                    brand=detected_brand,
                    category=category,
                    size=scraped.size,
                    condition=scraped.condition,
                    source_price=scraped.price,
                    our_price=float(price_info.recommended_price),
                    market_price=float(price_info.market_price) if price_info.market_price else None,
                    margin_percent=price_info.margin_percent,
                    images=scraped.images,
                    is_auction=scraped.is_auction,
                    status="active",
                )
                save_item(db_item)
                stats["saved"] += 1

                # Track per-source and per-brand
                src = scraped.source
                stats["by_source"][src] = stats["by_source"].get(src, 0) + 1
                stats["by_brand"][detected_brand] = stats["by_brand"].get(detected_brand, 0) + 1

            except Exception as e:
                continue

            # ── Log good finds ──────────────────────────────────────
            grailed_note = f" (Grailed avg: ${ref_avg:.0f})" if ref_avg else ""
            demand_note = f" [{demand_info['level'].upper()}]" if demand_info else ""
            model_note = f" [{product_id['product_name'][:30]}]" if product_id and product_id.get("product_name") else ""
            print(f"      💰 {scraped.source} | ${scraped.price:.0f} → ${price_info.recommended_price:.0f} ({price_info.margin_percent*100:.0f}%){grailed_note}{demand_note}{model_note}")

            # ── Alerts ──────────────────────────────────────────────
            if dry_run:
                continue

            # Discord
            try:
                sent = await alert_if_profitable(
                    scraped, price_info, brand=detected_brand, alerts=alerts,
                )
                if sent:
                    stats["alerts_discord"] += 1
            except Exception:
                pass

            # Telegram
            if TELEGRAM_AVAILABLE:
                try:
                    await send_deal_to_subscribers(
                        scraped, price_info,
                        brand=detected_brand,
                        auth_result=None,
                        auth_v2=auth_result,
                    )
                    stats["alerts_telegram"] += 1
                except Exception:
                    pass

        await asyncio.sleep(1)  # Rate limit between queries

    # ── Cleanup CLIP matcher ───────────────────────────────────────────
    if clip_matcher:
        try:
            await clip_matcher.__aexit__(None, None, None)
        except Exception:
            pass

    # ── Summary ─────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("📊 RESULTS")
    print("=" * 70)
    print(f"   Queries searched:    {stats['queries']}")
    print(f"   Total items found:   {stats['total_found']}")
    print(f"   Deals saved:         {stats['saved']}")
    print(f"   Skipped (margin):    {stats['skipped_margin']}")
    print(f"   Skipped (auth):      {stats['skipped_auth']}")
    print(f"   Skipped (pricing):   {stats['skipped_pricing']}")
    print(f"   Skipped (demand):    {stats['skipped_demand']}")
    print(f"   Image ID hits:       {stats['image_id_hits']}")
    print(f"   Demand checks:       {stats['demand_checks']}")
    print(f"   Discord alerts:      {stats['alerts_discord']}")
    print(f"   Telegram alerts:     {stats['alerts_telegram']}")

    if stats["by_source"]:
        print(f"\n   By platform:")
        for src, count in sorted(stats["by_source"].items(), key=lambda x: -x[1]):
            print(f"     {src:12s} {count} deals")

    if stats["by_brand"]:
        print(f"\n   Top brands:")
        top = sorted(stats["by_brand"].items(), key=lambda x: -x[1])[:10]
        for brand, count in top:
            print(f"     {brand:30s} {count} deals")

    # Send daily summary
    if stats["saved"] > 0 and not dry_run:
        try:
            await alerts.send_daily_summary()
            print(f"\n   📨 Discord summary sent")
        except Exception:
            pass

    # Save state
    save_state({
        "last_run": datetime.utcnow().isoformat(),
        "stats": stats,
    })

    print()
    return stats


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Full scrape — all platforms, trending-first strategy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--queries", type=int, default=20,
                        help="Number of trending queries to search (default: 20)")
    parser.add_argument("--per-source", type=int, default=15,
                        help="Max items per source per query (default: 15)")
    parser.add_argument("--min-margin", type=float, default=0.40,
                        help="Minimum margin threshold (default: 0.40)")
    parser.add_argument("--min-profit", type=float, default=150,
                        help="Minimum profit in $ (default: 150)")
    parser.add_argument("--brands-only", action="store_true",
                        help="Skip trending analysis, just scrape priority brands")
    parser.add_argument("--no-auth", action="store_true",
                        help="Skip authenticity checks")
    parser.add_argument("--no-image-id", action="store_true",
                        help="Skip reverse image search / product identification")
    parser.add_argument("--dry-run", action="store_true",
                        help="Find deals but don't send alerts")
    parser.add_argument("--fresh", action="store_true",
                        help="Force fresh trending analysis (ignore cache)")

    args = parser.parse_args()

    asyncio.run(run_full_scrape(
        num_queries=args.queries,
        max_per_source=args.per_source,
        min_margin=args.min_margin,
        min_profit=args.min_profit,
        brands_only=args.brands_only,
        skip_auth=args.no_auth,
        skip_image_id=args.no_image_id,
        dry_run=args.dry_run,
        fresh=args.fresh,
    ))


if __name__ == "__main__":
    main()
