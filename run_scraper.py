#!/usr/bin/env python3
"""
CLI to test scrapers and run manual scrapes.

Usage:
    python run_scraper.py search ebay "raf simons jacket"
    python run_scraper.py search shopgoodwill "number nine"
    python run_scraper.py market "raf simons" --category jacket
    python run_scraper.py details ebay 123456789
"""

import asyncio
import argparse
import json
from datetime import datetime

from scrapers import (
    EbayScraper,
    ShopGoodwillScraper,
    GrailedScraper,
    PoshmarkScraper,
    ARCHIVE_BRANDS,
    PRIORITY_BRANDS,
)
from scrapers.base import ScrapedItem
from api.services.pricing import PricingService
from db.sqlite_models import init_db, save_item, get_stats, Item


def item_to_dict(item: ScrapedItem) -> dict:
    """Convert ScrapedItem to JSON-serializable dict."""
    return {
        "source": item.source,
        "source_id": item.source_id,
        "url": item.url,
        "title": item.title,
        "price": item.price,
        "currency": item.currency,
        "brand": item.brand,
        "category": item.category,
        "size": item.size,
        "condition": item.condition,
        "images": item.images[:3],  # First 3 images
        "shipping_cost": item.shipping_cost,
        "is_auction": item.is_auction,
        "ends_at": item.ends_at.isoformat() if item.ends_at else None,
    }


async def search_source(source: str, query: str, max_results: int = 20):
    """Search a specific source."""
    print(f"\n🔍 Searching {source} for: {query}")
    print("-" * 50)
    
    scraper_class = {
        "ebay": EbayScraper,
        "shopgoodwill": ShopGoodwillScraper,
        "grailed": GrailedScraper,
    }.get(source)
    
    if not scraper_class:
        print(f"❌ Unknown source: {source}")
        return
    
    async with scraper_class() as scraper:
        items = await scraper.search(query, max_results=max_results)
        
        print(f"\n✅ Found {len(items)} items:\n")
        
        for i, item in enumerate(items, 1):
            print(f"{i}. {item.title[:60]}...")
            print(f"   💰 ${item.price:.2f} {'(auction)' if item.is_auction else ''}")
            if item.size:
                print(f"   📏 Size: {item.size}")
            if item.ends_at:
                print(f"   ⏰ Ends: {item.ends_at}")
            print(f"   🔗 {item.url}")
            print()
        
        return items


async def get_market_price(brand: str, category: str = None, size: str = None):
    """Get market price from Grailed."""
    print(f"\n📊 Getting market price for: {brand}")
    if category:
        print(f"   Category: {category}")
    if size:
        print(f"   Size: {size}")
    print("-" * 50)
    
    async with GrailedScraper() as scraper:
        market_data = await scraper.get_market_price(brand, category, size)
        
        if market_data["sample_size"] == 0:
            print("❌ No sold items found")
            return
        
        print(f"\n📈 Market Data ({market_data['sample_size']} samples):")
        print(f"   Average: ${market_data['avg_price']:.2f}")
        print(f"   Median:  ${market_data['median_price']:.2f}")
        print(f"   Range:   ${market_data['min_price']:.2f} - ${market_data['max_price']:.2f}")
        
        if market_data.get("items"):
            print("\n   Recent sales:")
            for item in market_data["items"][:3]:
                print(f"   - ${item.price:.2f}: {item.title[:50]}...")
        
        return market_data


async def get_item_details(source: str, item_id: str):
    """Get full details for a specific item."""
    print(f"\n📦 Getting details for {source} item: {item_id}")
    print("-" * 50)
    
    scraper_class = {
        "ebay": EbayScraper,
        "shopgoodwill": ShopGoodwillScraper,
    }.get(source)
    
    if not scraper_class:
        print(f"❌ Unknown source: {source}")
        return
    
    async with scraper_class() as scraper:
        item = await scraper.get_item_details(item_id)
        
        if not item:
            print("❌ Item not found")
            return
        
        print(f"\n📋 Item Details:")
        print(f"   Title: {item.title}")
        print(f"   Price: ${item.price:.2f}")
        print(f"   Condition: {item.condition}")
        print(f"   Size: {item.size}")
        print(f"   Seller: {item.seller}")
        print(f"   Images: {len(item.images)}")
        print(f"   URL: {item.url}")
        
        # Check availability
        available = await scraper.check_availability(item_id)
        print(f"   Available: {'✅ Yes' if available else '❌ No'}")
        
        return item


async def calculate_price(source: str, item_id: str):
    """Calculate recommended price for an item."""
    print(f"\n💵 Calculating price for {source} item: {item_id}")
    print("-" * 50)
    
    scraper_class = {
        "ebay": EbayScraper,
        "shopgoodwill": ShopGoodwillScraper,
    }.get(source)
    
    if not scraper_class:
        print(f"❌ Unknown source: {source}")
        return
    
    async with scraper_class() as source_scraper:
        async with GrailedScraper() as grailed:
            item = await source_scraper.get_item_details(item_id)
            
            if not item:
                print("❌ Item not found")
                return
            
            pricing = PricingService(grailed)
            recommendation = await pricing.calculate_price(item)
            
            print(f"\n💰 Pricing Recommendation:")
            print(f"   Source cost:      ${recommendation.source_price:.2f}")
            if recommendation.market_price:
                print(f"   Market price:     ${recommendation.market_price:.2f}")
            print(f"   Recommended:      ${recommendation.recommended_price:.2f}")
            print(f"   Margin:           {recommendation.margin_percent*100:.1f}%")
            print(f"   Est. profit:      ${recommendation.profit_estimate:.2f}")
            print(f"   Confidence:       {recommendation.confidence}")
            print(f"   Reasoning:        {recommendation.reasoning}")
            
            return recommendation


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


async def scrape_all_brands(
    brands: list = None,
    priority_only: bool = False,
    max_per_brand: int = 10,
    sources: list = None,
    min_margin: float = 0.20,
):
    """Scrape all brands and save to database."""
    print(f"\n🚀 Scraping brands to database...")
    print("-" * 60)
    
    init_db()
    pricing = PricingService()
    
    # Determine which brands to scrape
    if brands:
        target_brands = brands
    elif priority_only:
        target_brands = PRIORITY_BRANDS
    else:
        target_brands = ARCHIVE_BRANDS
    
    print(f"📋 Scraping {len(target_brands)} brands")
    print(f"📦 Sources: {', '.join(sources or ['grailed', 'poshmark'])}")
    print(f"📊 Min margin: {min_margin*100:.0f}%")
    print()
    
    # Set up scrapers
    scraper_classes = {
        "grailed": GrailedScraper,
        "poshmark": PoshmarkScraper,
        "ebay": EbayScraper,
        "shopgoodwill": ShopGoodwillScraper,
    }
    
    sources = sources or ["grailed", "poshmark"]
    
    saved_count = 0
    skipped_count = 0
    error_count = 0
    
    for brand in target_brands:
        print(f"  🔍 {brand}")
        
        for source_name in sources:
            scraper_class = scraper_classes.get(source_name)
            if not scraper_class:
                continue
            
            try:
                async with scraper_class(use_proxies=False) as scraper:
                    items = await scraper.search(brand, max_results=max_per_brand)
                    
                    if not items:
                        print(f"      {source_name}: 0 items")
                        continue
                    
                    source_saved = 0
                    for scraped in items:
                        detected_brand = detect_brand(scraped.title) or brand
                        category = detect_category(scraped.title)
                        
                        # Calculate pricing
                        price_info = pricing.calculate_price(
                            source_price=scraped.price,
                            brand=detected_brand,
                            title=scraped.title,
                        )
                        
                        # Skip if margin is too low
                        if price_info.margin_percent < min_margin:
                            skipped_count += 1
                            continue
                        
                        # Save to database
                        try:
                            item = Item(
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
                            )
                            save_item(item)
                            saved_count += 1
                            source_saved += 1
                        except Exception as e:
                            error_count += 1
                    
                    print(f"      ✓ {source_name}: {source_saved} saved")
                    
            except Exception as e:
                print(f"      ✗ {source_name}: {str(e)[:50]}")
                error_count += 1
            
            await asyncio.sleep(0.5)  # Rate limiting
    
    # Final stats
    stats = get_stats()
    print()
    print("=" * 60)
    print(f"📊 Results:")
    print(f"   Saved: {saved_count} items")
    print(f"   Skipped: {skipped_count} (below {min_margin*100:.0f}% margin)")
    print(f"   Errors: {error_count}")
    print(f"   Total in DB: {stats['active_items']} items")
    print()


async def run_full_scrape(max_per_brand: int = 5):
    """Run a full scrape across all brands and sources."""
    print("\n🚀 Running full scrape...")
    print("-" * 50)
    
    all_items = []
    
    # Sample of brands for testing
    test_brands = ["raf simons", "rick owens", "number nine", "undercover", "helmut lang"]
    
    async with EbayScraper() as ebay:
        async with ShopGoodwillScraper() as goodwill:
            for brand in test_brands:
                print(f"\n🔍 Searching: {brand}")
                
                try:
                    ebay_items = await ebay.search(brand, max_results=max_per_brand)
                    print(f"   eBay: {len(ebay_items)} items")
                    all_items.extend(ebay_items)
                except Exception as e:
                    print(f"   eBay error: {e}")
                
                try:
                    gw_items = await goodwill.search(brand, max_results=max_per_brand)
                    print(f"   Goodwill: {len(gw_items)} items")
                    all_items.extend(gw_items)
                except Exception as e:
                    print(f"   Goodwill error: {e}")
                
                # Small delay between brands
                await asyncio.sleep(1)
    
    print(f"\n✅ Total items found: {len(all_items)}")
    
    # Save results
    output = {
        "scraped_at": datetime.utcnow().isoformat(),
        "total_items": len(all_items),
        "items": [item_to_dict(item) for item in all_items],
    }
    
    with open("scrape_results.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print("💾 Results saved to scrape_results.json")
    
    return all_items


def main():
    parser = argparse.ArgumentParser(description="Archive Arbitrage Scraper CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search a source")
    search_parser.add_argument("source", choices=["ebay", "shopgoodwill", "grailed"])
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--max", type=int, default=20, help="Max results")
    
    # Market price command
    market_parser = subparsers.add_parser("market", help="Get market price from Grailed")
    market_parser.add_argument("brand", help="Brand name")
    market_parser.add_argument("--category", help="Item category (jacket, pants, etc)")
    market_parser.add_argument("--size", help="Size")
    
    # Details command
    details_parser = subparsers.add_parser("details", help="Get item details")
    details_parser.add_argument("source", choices=["ebay", "shopgoodwill"])
    details_parser.add_argument("item_id", help="Item ID")
    
    # Price command
    price_parser = subparsers.add_parser("price", help="Calculate recommended price")
    price_parser.add_argument("source", choices=["ebay", "shopgoodwill"])
    price_parser.add_argument("item_id", help="Item ID")
    
    # Full scrape command
    full_parser = subparsers.add_parser("full", help="Run full scrape")
    full_parser.add_argument("--max-per-brand", type=int, default=5)
    
    # Brands command
    brands_parser = subparsers.add_parser("brands", help="List tracked brands")
    
    # Scrape all brands command
    scrape_all_parser = subparsers.add_parser("scrape-brands", help="Scrape all brands and save to database")
    scrape_all_parser.add_argument("--brands", nargs="*", help="Specific brands to scrape (default: all)")
    scrape_all_parser.add_argument("--priority-only", action="store_true", help="Only scrape priority brands")
    scrape_all_parser.add_argument("--max-per-brand", type=int, default=10, help="Max items per brand per source")
    scrape_all_parser.add_argument("--sources", nargs="*", default=["grailed", "poshmark"], help="Sources to scrape")
    scrape_all_parser.add_argument("--min-margin", type=float, default=0.20, help="Minimum margin to save, default 0.20 for 20 percent")
    
    args = parser.parse_args()
    
    if args.command == "search":
        asyncio.run(search_source(args.source, args.query, args.max))
    elif args.command == "market":
        asyncio.run(get_market_price(args.brand, args.category, args.size))
    elif args.command == "details":
        asyncio.run(get_item_details(args.source, args.item_id))
    elif args.command == "price":
        asyncio.run(calculate_price(args.source, args.item_id))
    elif args.command == "full":
        asyncio.run(run_full_scrape(args.max_per_brand))
    elif args.command == "brands":
        print("\n📋 Tracked Brands:")
        for brand in ARCHIVE_BRANDS:
            priority = "⭐" if brand in PRIORITY_BRANDS else "  "
            print(f"   {priority} {brand}")
        print(f"\n   Total: {len(ARCHIVE_BRANDS)} brands ({len(PRIORITY_BRANDS)} priority)")
    elif args.command == "scrape-brands":
        asyncio.run(scrape_all_brands(
            brands=args.brands,
            priority_only=args.priority_only,
            max_per_brand=args.max_per_brand,
            sources=args.sources,
            min_margin=args.min_margin,
        ))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
