#!/usr/bin/env python3
"""
Main pipeline script - scrapes items from multiple sources, calculates prices, stores in database.

Usage:
    python pipeline.py run                       # Full pipeline: scrape → qualify → alerts
    python pipeline.py scrape                    # Scrape priority brands from all sources
    python pipeline.py scrape --brand "supreme"  # Scrape specific brand
    python pipeline.py scrape --source ebay      # Scrape only from eBay
    python pipeline.py list                      # List items in database
    python pipeline.py stats                     # Show statistics
    python pipeline.py serve                     # Start API server
    python pipeline.py qualify                   # Deep-qualify scraped items with volume metrics
    python pipeline.py deals --grade A           # Show A-grade (guaranteed flip) deals
"""

import asyncio
import argparse
import os
import sys
from typing import List

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

# Add project to path
sys.path.insert(0, ".")

from scrapers import (
    EbayScraper, DepopScraper, MercariScraper, PoshmarkScraper,
    ShopGoodwillScraper, NoBidsScraper, GemScraper, GrailedScraper,
    ARCHIVE_BRANDS, PRIORITY_BRANDS, ScrapedItem
)
from api.services.pricing import PricingService
from db.sqlite_models import init_db, save_item, get_items, get_stats, Item, update_item_image_hashes, find_duplicate_by_image_hash
from core.alerts import AlertService, alert_if_profitable
from telegram_bot import send_deal_to_subscribers, init_telegram_db
from scrapers.image_fingerprinter import ImageFingerprinter, save_image_hash_to_db
from core.authenticity_checker import AuthenticityChecker, AuthStatus
from core.authenticity_v2 import AuthenticityCheckerV2, AuthStatus as AuthStatusV2, format_auth_bar, format_auth_grade, MIN_AUTH_SCORE


# All available sources
ALL_SOURCES = {
    "grailed": GrailedScraper,    # Best for archive fashion - always works
    "poshmark": PoshmarkScraper,  # Good variety, works well
    "ebay": EbayScraper,          # Needs API key or residential proxies
    "depop": DepopScraper,        # Often 403s
    "mercari": MercariScraper,    # Often 403s
    "shopgoodwill": ShopGoodwillScraper,  # API unreliable
    "nobids": NoBidsScraper,      # eBay auctions with no bids
    "gem": GemScraper,            # Japanese consignment
}

# Default active sources - these work reliably without special setup
ACTIVE_SOURCES = {
    "grailed": GrailedScraper,
    "poshmark": PoshmarkScraper,
}


def detect_brand(title: str) -> str | None:
    """Try to detect brand from item title."""
    title_lower = title.lower()
    for brand in ARCHIVE_BRANDS:
        if brand.lower() in title_lower:
            return brand
    return None


def detect_category(title: str) -> str | None:
    """Try to detect category from item title."""
    title_lower = title.lower()
    
    categories = {
        "jacket": ["jacket", "blazer", "coat", "bomber", "parka", "varsity", "denim jacket", "leather jacket"],
        "pants": ["pants", "trousers", "jeans", "denim", "cargos", "cargo"],
        "shirt": ["shirt", "button up", "button down", "flannel"],
        "tee": ["t-shirt", "tee", "t shirt", "tshirt"],
        "hoodie": ["hoodie", "hooded", "pullover", "zip up"],
        "sweater": ["sweater", "knit", "cardigan", "jumper"],
        "boots": ["boots", "boot", "combat"],
        "shoes": ["shoes", "sneakers", "runners", "trainers", "loafers"],
        "bag": ["bag", "backpack", "tote", "messenger", "duffle"],
        "hat": ["hat", "cap", "beanie"],
        "accessories": ["belt", "wallet", "chain", "jewelry", "necklace", "ring", "bracelet"],
    }
    
    for cat, keywords in categories.items():
        if any(kw in title_lower for kw in keywords):
            return cat
    
    return None


async def scrape_source(source_name: str, scraper_class, brand: str, max_items: int = 15) -> List[ScrapedItem]:
    """Scrape a single source for a brand."""
    # Guard against a misconfigured scraper_class being a string
    if isinstance(scraper_class, str):
        try:
            # First try our explicit ALL_SOURCES mapping if it has strings
            resolver = ALL_SOURCES.get(source_name)
            if isinstance(resolver, str):
                import importlib
                mod_name = f"scrapers.{resolver.lower()}"
                mod = importlib.import_module(mod_name)
                scraper_class = getattr(mod, resolver)
            else:
                scraper_class = resolver
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"    {source_name} error resolving class: {e}")
            return []

    try:
        async with scraper_class() as scraper:
            items = await scraper.search(brand, max_results=max_items)
            return items
    except Exception as e:
        print(f"    {source_name} error: {e}")
        return []


async def scrape_brand(brand: str, sources: dict, max_per_source: int = 10) -> List[ScrapedItem]:
    """Scrape all sources for a single brand."""
    print(f"  🔍 {brand}")
    
    all_items = []
    
    for source_name, scraper_class in sources.items():
        items = await scrape_source(source_name, scraper_class, brand, max_per_source)
        if items:
            print(f"    ✓ {source_name}: {len(items)} items")
            all_items.extend(items)
        else:
            print(f"    ✗ {source_name}: 0 items")
        
        # Small delay between sources
        await asyncio.sleep(1)
    
    return all_items


async def run_scrape(
    brands: List[str] = None,
    sources: dict = None,
    max_per_source: int = 10,
):
    """Run the full scraping pipeline with async pricing + Discord alerts."""
    if brands is None:
        brands = PRIORITY_BRANDS
    if sources is None:
        sources = ACTIVE_SOURCES
    
    print(f"\n🚀 Scraping {len(brands)} brands from {len(sources)} sources...")
    print(f"   Sources: {', '.join(sources.keys())}")
    print("=" * 60)
    
    pricing = PricingService()
    alerts = AlertService()
    
    # Init telegram users table
    try:
        init_telegram_db()
    except Exception:
        pass
    saved_count = 0
    skipped_count = 0
    total_found = 0
    live_comps_used = 0
    alerts_sent = 0
    replica_rejected = 0  # Track replicas filtered out
    
    for brand in brands:
        items = await scrape_brand(brand, sources, max_per_source)
        total_found += len(items)
        
        for scraped in items:
            # Detect brand and category
            detected_brand = detect_brand(scraped.title) or brand
            category = detect_category(scraped.title)
            
            # Calculate price using async pricing (smart comps + demand scoring)
            price_rec = await pricing.calculate_price_async(
                source_price=scraped.price,
                brand=detected_brand,
                title=scraped.title,
                shipping_cost=scraped.shipping_cost or 0,
            )
            
            # Track live comp usage
            if price_rec.comps_count > 0:
                live_comps_used += 1
            
            # Skip if not profitable
            if price_rec.confidence == "skip" or price_rec.recommended_price == 0:
                skipped_count += 1
                continue
            
            # Skip if margin too low (< 20%)
            if price_rec.margin_percent < 0.20:
                skipped_count += 1
                continue
            
            # ═══ AUTHENTICITY CHECK V2 (multi-signal) ═══
            auth_v2 = AuthenticityCheckerV2()
            auth_result = await auth_v2.check(
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
                print(f"      🚫 BLOCKED [{auth_result.status.value}] {format_auth_bar(auth_result.confidence)} — {'; '.join(auth_result.reasons[:2])}")
                replica_rejected += 1
                skipped_count += 1
                continue
            elif auth_result.confidence < MIN_AUTH_SCORE:
                print(f"      ⚠️  LOW AUTH {format_auth_bar(auth_result.confidence)} — {'; '.join(auth_result.reasons[:2])}")
                replica_rejected += 1
                skipped_count += 1
                continue
            else:
                print(f"      🔐 {format_auth_grade(auth_result.grade)} {format_auth_bar(auth_result.confidence)}")
            
            # Create database item
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
                source_shipping=scraped.shipping_cost or 0,
                market_price=float(price_rec.market_price) if price_rec.market_price else None,
                our_price=float(price_rec.recommended_price),
                margin_percent=price_rec.margin_percent,
                images=scraped.images,
                is_auction=scraped.is_auction,
                status="active",
            )
            
            # Save to database
            try:
                item_id = save_item(db_item)
                saved_count += 1
                
                # Fingerprint first image (Phase 1.1)
                if scraped.images:
                    try:
                        async with ImageFingerprinter() as fingerprinter:
                            fp = await fingerprinter.fingerprint_from_url(scraped.images[0])
                            if fp.is_valid:
                                # Check for exact duplicate
                                duplicate = find_duplicate_by_image_hash(fp.file_hash)
                                if duplicate and duplicate.id != item_id:
                                    print(f"      ⚠️  Image duplicate detected: matches item {duplicate.id}")
                                
                                # Save hashes to database
                                update_item_image_hashes(item_id, fp.file_hash, fp.phash)
                    except Exception as e:
                        # Don't fail the scrape if fingerprinting fails
                        pass
                
                # Log profitable finds with good margins
                if price_rec.margin_percent >= 0.30:
                    season_tag = f" 🔥{price_rec.season_name}" if price_rec.season_name else ""
                    demand_tag = f" [{price_rec.demand_level}]" if price_rec.demand_level != "unknown" else ""
                    print(f"      💰 ${scraped.price:.0f} → ${price_rec.recommended_price:.0f} ({price_rec.margin_percent*100:.0f}%){season_tag}{demand_tag}")
                
                # Send Discord alert for high-profit items
                try:
                    sent = await alert_if_profitable(scraped, price_rec, brand=detected_brand, alerts=alerts)
                    if sent:
                        alerts_sent += 1
                except Exception:
                    pass
                # Send to Telegram subscribers
                try:
                    await send_deal_to_subscribers(scraped, price_rec, brand=detected_brand, auth_result=auth_result, auth_v2=auth_result)
                except Exception:
                    pass
            except Exception as e:
                print(f"      ⚠ Save error: {e}")
        
        # Delay between brands to avoid rate limiting
        await asyncio.sleep(3)
    
    print("\n" + "=" * 60)
    print(f"📊 Results:")
    print(f"   Found: {total_found} items")
    print(f"   Saved: {saved_count} profitable items")
    print(f"   Skipped: {skipped_count} unprofitable items")
    if replica_rejected > 0:
        print(f"   🚫 Replicas filtered: {replica_rejected} items")
    print(f"   Live comps used: {live_comps_used} price lookups")
    print(f"   Discord alerts sent: {alerts_sent}")
    
    # Send daily summary if items were found
    if saved_count > 0:
        try:
            sent = await alerts.send_daily_summary()
            if sent:
                print(f"   📨 Discord summary sent")
        except Exception:
            pass
    
    return saved_count


def list_items(limit: int = 20, brand: str = None):
    """List items from the database."""
    items = get_items(status="active", brand=brand, limit=limit)
    
    print(f"\n📦 {len(items)} items in database:\n")
    
    for item in items:
        margin_str = f"{item.margin_percent*100:.0f}%" if item.margin_percent else "N/A"
        print(f"  [{item.id}] {item.title[:50]}...")
        print(f"      Brand: {item.brand or 'Unknown'} | Size: {item.size or 'N/A'} | Source: {item.source}")
        print(f"      ${item.source_price:.2f} → ${item.our_price:.2f} ({margin_str} margin)")
        print()


def show_stats():
    """Show database statistics."""
    stats = get_stats()
    
    print("\n📊 Database Statistics:")
    print("=" * 40)
    print(f"  Total Items:    {stats['total_items']}")
    print(f"  Active Items:   {stats['active_items']}")
    print(f"  Unique Brands:  {stats['unique_brands']}")
    print(f"  Avg Margin:     {stats['avg_margin']}%")
    print()


def start_server():
    """Start the FastAPI server."""
    import uvicorn
    from api.main import app
    
    print("\n🚀 Starting API server...")
    print("   Frontend: http://localhost:8000")
    print("   API Docs: http://localhost:8000/docs")
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)


def main():
    parser = argparse.ArgumentParser(description="Archive Arbitrage Pipeline")
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape items from sources")
    scrape_parser.add_argument("--brand", help="Specific brand to scrape")
    scrape_parser.add_argument("--source", choices=list(ALL_SOURCES.keys()), help="Specific source")
    scrape_parser.add_argument("--sources", help="Comma-separated list of sources (e.g. ebay,depop,mercari)")
    scrape_parser.add_argument("--all-sources", action="store_true", help="Use all available sources")
    scrape_parser.add_argument("--max", type=int, default=10, help="Max items per source per brand")
    scrape_parser.add_argument("--all-brands", action="store_true", help="Scrape all brands (slow)")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List items in database")
    list_parser.add_argument("--limit", type=int, default=20, help="Number of items")
    list_parser.add_argument("--brand", help="Filter by brand")
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    
    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start API server")
    
    # Qualify command
    qualify_parser = subparsers.add_parser("qualify", help="Run deal qualification (Pass 2)")
    qualify_parser.add_argument("--brand", help="Filter by brand")
    qualify_parser.add_argument("--min-margin", type=float, default=0.20, help="Min margin (default 0.20)")
    qualify_parser.add_argument("--min-profit", type=float, default=20, help="Min profit (default $20)")
    qualify_parser.add_argument("--limit", type=int, default=200, help="Max items to qualify")
    qualify_parser.add_argument("--dry-run", action="store_true", help="Don't update DB")
    qualify_parser.add_argument("--alert", action="store_true", help="Send Discord alerts for A/B deals")
    qualify_parser.add_argument("--requalify", action="store_true", help="Re-qualify all items")

    # Deals command
    deals_parser = subparsers.add_parser("deals", help="Show qualified deals by grade")
    deals_parser.add_argument("--grade", choices=["A", "B", "C"], help="Filter by grade")
    deals_parser.add_argument("--brand", help="Filter by brand")
    deals_parser.add_argument("--limit", type=int, default=20, help="Number of deals")

    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize database")

    # Fingerprint command — backfill image hashes for existing items
    fingerprint_parser = subparsers.add_parser("fingerprint", help="Generate image hashes for existing items")
    fingerprint_parser.add_argument("--limit", type=int, default=100, help="Max items to process")
    fingerprint_parser.add_argument("--brand", help="Filter by brand")
    fingerprint_parser.add_argument("--dry-run", action="store_true", help="Don't update DB")

    # Run command — unified scrape + qualify + alert
    run_parser = subparsers.add_parser("run", help="Full pipeline: scrape → qualify → Discord alerts → site updated")
    run_parser.add_argument("--brand", help="Specific brand to scrape")
    run_parser.add_argument("--sources", help="Comma-separated sources (default: grailed,poshmark)")
    run_parser.add_argument("--max", type=int, default=10, help="Max items per source per brand (default 10)")
    run_parser.add_argument("--all-brands", action="store_true", help="Scrape all brands (slow)")
    run_parser.add_argument("--qualify-limit", type=int, default=200, help="Max items to qualify (default 200)")
    run_parser.add_argument("--min-grade", choices=["A", "B", "C"], default="B", help="Minimum grade to alert (default B)")
    run_parser.add_argument("--dry-run", action="store_true", help="Don't save to DB or send alerts")
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_db()
    elif args.command == "qualify":
        from core.qualify import run_qualification
        init_db()
        asyncio.run(run_qualification(
            brand_filter=args.brand,
            min_margin=args.min_margin,
            min_profit=args.min_profit,
            dry_run=args.dry_run,
            send_alerts=args.alert,
            limit=args.limit,
            requalify=args.requalify,
        ))
    elif args.command == "deals":
        from db.sqlite_models import get_qualified_items
        init_db()
        deals = get_qualified_items(grade=args.grade, brand=args.brand, limit=args.limit)
        if not deals:
            print("\nNo qualified deals found. Run: python pipeline.py qualify")
        else:
            print(f"\n{'🅰️ ' if args.grade == 'A' else '🔥 '}Qualified Deals ({len(deals)}):\n")
            for d in deals:
                grade_emoji = {"A": "🅰️", "B": "🅱️", "C": "🔵"}.get(d["deal_grade"], "⬜")
                brand = (d["brand"] or "Unknown")[:18]
                title = (d["title"] or "")[:45]
                profit = d.get("exact_profit") or 0
                margin = d.get("exact_margin") or 0
                demand = d.get("demand_level") or "?"
                comps = d.get("comp_count") or 0
                sell_through = d.get("sell_through_rate") or 0
                days_to_sell = d.get("est_days_to_sell") or 999
                days_str = f"~{days_to_sell:.0f}d" if days_to_sell < 999 else "n/a"
                print(f"  {grade_emoji} {d['deal_grade']} | {brand}: {title}...")
                print(f"     ${d['source_price']:.0f} → ${d.get('exact_sell_price', 0):.0f} | ${profit:.0f} profit ({margin:.0%}) | {comps} comps [{demand}]")
                print(f"     Sell-through: {sell_through:.0%} | Est. time to sell: {days_str}")
                print(f"     {d.get('deal_grade_reasoning', '')}")
                print()
    elif args.command == "scrape":
        init_db()
        
        # Determine brands
        if args.brand:
            brands = [args.brand]
        elif args.all_brands:
            brands = ARCHIVE_BRANDS[:50]  # First 50 brands
        else:
            brands = PRIORITY_BRANDS
        
        # Determine sources
        if args.source:
            sources = {args.source: ALL_SOURCES[args.source]}
        elif args.sources:
            source_list = [s.strip() for s in args.sources.split(',')]
            sources = {s: ALL_SOURCES[s] for s in source_list if s in ALL_SOURCES}
        elif args.all_sources:
            sources = ALL_SOURCES
        else:
            sources = ACTIVE_SOURCES
        
        asyncio.run(run_scrape(brands, sources, args.max))
    elif args.command == "list":
        list_items(args.limit, args.brand)
    elif args.command == "stats":
        show_stats()
    elif args.command == "serve":
        start_server()
    elif args.command == "run":
        # Full pipeline: scrape → qualify → alert
        from core.qualify import run_qualification
        
        init_db()
        
        # Determine brands
        if args.brand:
            brands = [args.brand]
        elif args.all_brands:
            brands = ARCHIVE_BRANDS[:50]
        else:
            brands = PRIORITY_BRANDS
        
        # Determine sources
        if args.sources:
            source_list = [s.strip() for s in args.sources.split(',')]
            sources = {s: ALL_SOURCES[s] for s in source_list if s in ALL_SOURCES}
        else:
            sources = ACTIVE_SOURCES
        
        print("\n" + "=" * 70)
        print("🚀 ARCHIVE ARBITRAGE FULL PIPELINE")
        print("=" * 70)
        print(f"Brands: {len(brands)} | Sources: {', '.join(sources.keys())}")
        print(f"Qualify limit: {args.qualify_limit} | Min alert grade: {args.min_grade}")
        if args.dry_run:
            print("⚠️  DRY RUN — no DB changes or alerts")
        print("=" * 70)
        
        # STEP 1: SCRAPE
        print("\n📦 STEP 1: SCRAPING")
        print("-" * 40)
        saved_count = asyncio.run(run_scrape(brands, sources, args.max))
        
        if saved_count == 0:
            print("\n⚠️  No new items found. Pipeline complete.")
        else:
            # STEP 2: QUALIFY (with Discord alerts for good deals)
            print("\n🔍 STEP 2: QUALIFYING ITEMS")
            print("-" * 40)
            print("Analyzing: exact comps, demand score, sell-through rate, days-to-sell...")
            
            # Map min_grade to alert setting
            send_alerts = not args.dry_run
            
            asyncio.run(run_qualification(
                brand_filter=args.brand,
                min_margin=0.20,
                min_profit=20,
                dry_run=args.dry_run,
                send_alerts=send_alerts,
                limit=args.qualify_limit,
                requalify=False,
            ))
            
            # STEP 3: SUMMARY
            print("\n✅ STEP 3: PIPELINE COMPLETE")
            print("=" * 70)
            stats = get_stats()
            print(f"📊 Database: {stats['active_items']} active items across {stats['unique_brands']} brands")
            print(f"💰 Average margin: {stats['avg_margin']}%")
            
            # Get deal breakdown
            from db.sqlite_models import get_qualified_items
            grade_a = len(get_qualified_items(grade="A", limit=1000))
            grade_b = len(get_qualified_items(grade="B", limit=1000))
            grade_c = len(get_qualified_items(grade="C", limit=1000))
            
            print(f"🎯 Deals by grade: 🅰️ {grade_a} | 🅱️ {grade_b} | 🔵 {grade_c}")
            print(f"🌐 Site updated: http://localhost:8000 (run 'pipeline.py serve' to view)")
            if not args.dry_run:
                print(f"📨 Discord alerts sent for Grade A/B deals")
            print("=" * 70)
    elif args.command == "fingerprint":
        # Backfill image hashes for existing items
        init_db()
        
        print(f"\n🔍 Fingerprinting images for {args.limit} items...")
        print("=" * 60)
        
        items = get_items(status='active', brand=args.brand, limit=args.limit)
        
        # Filter to items without hashes
        items_to_process = [item for item in items if not item.image_hash and item.images]
        
        print(f"Found {len(items_to_process)} items without image hashes")
        
        if args.dry_run:
            print("⚠️  DRY RUN — not updating database")
        
        processed = 0
        duplicates_found = 0
        
        async def process_items():
            nonlocal processed, duplicates_found
            
            async with ImageFingerprinter() as fingerprinter:
                for item in items_to_process:
                    try:
                        fp = await fingerprinter.fingerprint_from_url(item.images[0])
                        
                        if not fp.is_valid:
                            print(f"  ⚠️  Failed to fingerprint item {item.id}")
                            continue
                        
                        # Check for duplicate
                        duplicate = find_duplicate_by_image_hash(fp.file_hash)
                        if duplicate and duplicate.id != item.id:
                            print(f"  🔍 Item {item.id}: duplicate of {duplicate.id}")
                            duplicates_found += 1
                        
                        if not args.dry_run:
                            update_item_image_hashes(item.id, fp.file_hash, fp.phash)
                        
                        processed += 1
                        
                        if processed % 10 == 0:
                            print(f"  ... processed {processed}/{len(items_to_process)}")
                        
                    except Exception as e:
                        print(f"  ⚠️  Error processing item {item.id}: {e}")
        
        asyncio.run(process_items())
        
        print("=" * 60)
        print(f"✅ Complete: {processed} items fingerprinted")
        print(f"🔍 Duplicates found: {duplicates_found}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
