#!/usr/bin/env python3
"""
Scheduled scraping - finds trending items on Grailed, then searches other platforms.

Strategy:
1. Analyze what's selling on Grailed (trending items)
2. Search for those items on cheaper platforms (Poshmark, Mercari, eBay)
3. Alert on items we can flip for profit

This focuses effort on items with proven demand.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Force unbuffered output
os.environ['PYTHONUNBUFFERED'] = '1'

# Load environment
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from scrapers import (
    GrailedScraper, PoshmarkScraper, MercariScraper,
    ARCHIVE_BRANDS, PRIORITY_BRANDS, ScrapedItem
)
from scrapers.trending_analyzer import TrendingAnalyzer, get_trending_queries, save_report
from api.services.pricing import PricingService
from db.sqlite_models import init_db, save_item, get
from alerts import AlertService, alert_if_profitable
from qualify import run_qualification

# Config
QUERIES_PER_RUN = 15       # Number of trending queries to search per run
ITEMS_PER_QUERY = 15       # Items per query per source
TRENDING_CACHE_HOURS = 4   # Re-analyze trending every N hours
STATE_FILE = Path(__file__).parent / "data" / "scrape_state.json"
TRENDING_FILE = Path(__file__).parent / "data" / "trending_report.json"

# Sources to search for deals (not Grailed - that's our price reference)
DEAL_SOURCES = {
    "poshmark": PoshmarkScraper,
    # "mercari": MercariScraper,  # Enable when ready
}


def load_state() -> dict:
    """Load scrape state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_scraped": {}, "last_run": None, "last_trending": None}


def save_state(state: dict):
    """Save scrape state to file."""
    STATE_FILE.parent.mkdir(exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def load_trending_queries() -> list[str]:
    """Load cached trending queries if fresh enough."""
    if TRENDING_FILE.exists():
        with open(TRENDING_FILE) as f:
            data = json.load(f)
            # Check if fresh enough
            ts = datetime.fromisoformat(data.get("timestamp", "2000-01-01"))
            if datetime.utcnow() - ts < timedelta(hours=TRENDING_CACHE_HOURS):
                return data.get("recommended_queries", [])
    return []


def detect_brand(title: str) -> str | None:
    """Detect brand from title."""
    title_lower = title.lower()
    for brand in ARCHIVE_BRANDS:
        if brand.lower() in title_lower:
            return brand
    return None


def detect_category(title: str) -> str | None:
    """Detect category from title."""
    title_lower = title.lower()
    categories = {
        "jacket": ["jacket", "blazer", "coat", "bomber", "parka"],
        "pants": ["pants", "trousers", "jeans", "denim"],
        "shirt": ["shirt", "button up", "flannel"],
        "tee": ["t-shirt", "tee", "tshirt"],
        "hoodie": ["hoodie", "hooded", "pullover"],
        "sweater": ["sweater", "knit", "cardigan"],
        "shoes": ["shoes", "sneakers", "boots"],
    }
    for cat, keywords in categories.items():
        if any(kw in title_lower for kw in keywords):
            return cat
    return None


async def scrape_query(query: str, sources: dict, max_per_source: int = 15) -> list[ScrapedItem]:
    """Search all deal sources for a query."""
    all_items = []
    
    for source_name, scraper_class in sources.items():
        try:
            async with scraper_class(use_proxies=False) as scraper:
                items = await scraper.search(query, max_results=max_per_source)
                if items:
                    print(f"    ✓ {source_name}: {len(items)} items")
                    all_items.extend(items)
                else:
                    print(f"    - {source_name}: 0 items")
        except Exception as e:
            print(f"    ✗ {source_name}: {e}")
        
        await asyncio.sleep(0.5)
    
    return all_items


async def get_grailed_prices(queries: list[str]) -> dict:
    """Get average sold prices from Grailed for each query."""
    prices = {}
    
    print("📈 Fetching Grailed sold prices for comparison...")
    
    async with GrailedScraper() as scraper:
        for query in queries[:20]:  # Limit to prevent rate limiting
            try:
                sold = await scraper.search_sold(query, max_results=10)
                if sold:
                    sold_prices = [i.price for i in sold if i.price > 0]
                    if sold_prices:
                        prices[query] = {
                            "avg": sum(sold_prices) / len(sold_prices),
                            "min": min(sold_prices),
                            "max": max(sold_prices),
                            "count": len(sold_prices),
                        }
                        print(f"   ✓ {query}: avg ${prices[query]['avg']:.0f} ({len(sold_prices)} comps)")
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"   ✗ {query}: {e}")
    
    return prices


async def run_scheduled_scrape():
    """Run a scheduled scrape using trending data."""
    print(f"\n🕐 Trending-based scrape starting at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    init_db()
    state = load_state()
    pricing = PricingService()
    alerts = AlertService()
    
    # Step 1: Get trending queries (from cache or fresh)
    queries = load_trending_queries()
    
    if not queries:
        print("📊 Analyzing Grailed trending (cache expired)...")
        async with TrendingAnalyzer() as analyzer:
            report = await analyzer.analyze_trending(items_per_query=40)
            analyzer.print_report(report)
            save_report(report, str(TRENDING_FILE))
            queries = report.recommended_queries
            state["last_trending"] = datetime.utcnow().isoformat()
            save_state(state)
    else:
        print(f"📊 Using cached trending queries ({len(queries)} queries)")
    
    # Take top N queries
    queries = queries[:QUERIES_PER_RUN]
    print(f"\n🔍 Searching {len(queries)} trending queries on deal platforms")
    print(f"   Queries: {', '.join(queries[:5])}{'...' if len(queries) > 5 else ''}")
    print()
    
    # Step 2: Get Grailed prices for comparison
    grailed_prices = await get_grailed_prices(queries)
    print()
    
    # Step 3: Search deal sources for each query
    saved_count = 0
    skipped_count = 0
    alert_count = 0
    
    for query in queries:
        print(f"  🔍 {query}")
        items = await scrape_query(query, DEAL_SOURCES, ITEMS_PER_QUERY)
        
        # Get Grailed reference price for this query
        ref_price = grailed_prices.get(query, {}).get("avg")
        
        for scraped in items:
            detected_brand = detect_brand(scraped.title) or query.split()[0]
            category = detect_category(scraped.title)
            
            # Calculate pricing
            price_info = pricing.calculate_price(
                source_price=scraped.price,
                brand=detected_brand,
                title=scraped.title,
            )
            
            # If we have Grailed reference, use it for better margin calc
            if ref_price and ref_price > 0:
                potential_margin = (ref_price - scraped.price) / ref_price if ref_price > scraped.price else 0
                # Override if Grailed comp gives better signal
                if potential_margin > price_info.margin_percent:
                    price_info.market_price = ref_price
                    price_info.margin_percent = potential_margin
                    price_info.recommended_price = ref_price * 0.85  # Sell slightly below Grailed avg
            
            # Skip if not profitable
            if price_info.confidence == "skip" or price_info.recommended_price == 0:
                skipped_count += 1
                continue
            
            # Skip if margin is too low (< 25% for this strategy)
            if price_info.margin_percent < 0.25:
                skipped_count += 1
                continue
            
            # Save to database
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
                saved_count += 1
                
                # Log good finds
                if price_info.margin_percent >= 0.35:
                    grailed_note = f" (Grailed avg: ${ref_price:.0f})" if ref_price else ""
                    print(f"      💰 ${scraped.price:.0f} → ${price_info.recommended_price:.0f} ({price_info.margin_percent*100:.0f}%){grailed_note}")
                
                # Send Discord alert for high-profit items
                try:
                    sent = await alert_if_profitable(scraped, price_info, brand=detected_brand, alerts=alerts)
                    if sent:
                        alert_count += 1
                except Exception:
                    pass
                    
            except Exception as e:
                print(f"      ⚠ Save error: {e}")
        
        # Update state
        state["last_scraped"][query] = datetime.utcnow().isoformat()
        save_state(state)
        
        await asyncio.sleep(1)  # Rate limit between queries
    
    # Save final state
    state["last_run"] = datetime.utcnow().isoformat()
    save_state(state)
    
    # Get final stats
    stats = get_stats()
    
    print()
    print("=" * 60)
    print(f"📊 Results:")
    print(f"   Saved: {saved_count} potential deals")
    print(f"   Skipped: {skipped_count} (low margin)")
    print(f"   Discord alerts: {alert_count}")
    print(f"   Total in DB: {stats['active_items']} items")
    
    # --- Pass 2: Qualify new items ---
    if saved_count > 0:
        print()
        print("🔬 Running Pass 2: Deal Qualification...")
        try:
            await run_qualification(
                min_margin=0.25,
                min_profit=25,
                send_alerts=True,
                limit=saved_count + 50,
            )
        except Exception as e:
            print(f"   ⚠ Qualification error: {e}")

    # Send daily summary
    if saved_count > 0:
        try:
            await alerts.send_daily_summary()
            print(f"   📨 Discord summary sent")
        except Exception:
            pass
    
    print()


if __name__ == "__main__":
    asyncio.run(run_scheduled_scrape())
