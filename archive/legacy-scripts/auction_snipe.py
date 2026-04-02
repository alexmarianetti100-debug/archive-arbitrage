#!/usr/bin/env python3
"""
Auction Sniping Script - Find eBay auctions ending soon with no/low bids.

Run frequently (every 1-2 hours) to catch opportunities before they end.

Usage:
    python auction_snipe.py                    # Snipe priority brands
    python auction_snipe.py --brand "raf simons"  # Specific brand
    python auction_snipe.py --hours 6          # Auctions ending in 6 hours
"""

import asyncio
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Force unbuffered output
os.environ['PYTHONUNBUFFERED'] = '1'

# Load environment
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from scrapers import PRIORITY_BRANDS
from scrapers.auction_sniper import AuctionSniper
from api.services.pricing import PricingService
from db.sqlite_models import init_db, save_item, get_stats, Item


async def snipe_auctions(
    brands: list = None,
    ending_within_hours: int = 12,
    max_price: float = 500,
    max_per_brand: int = 10,
):
    """Find and save profitable auction opportunities."""
    
    print(f"\n🎯 Auction Snipe starting at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   Looking for auctions ending within {ending_within_hours} hours")
    print("=" * 60)
    
    init_db()
    pricing = PricingService()
    
    if brands is None:
        # Default: top archive brands
        brands = PRIORITY_BRANDS[:15]
    
    print(f"📋 Searching {len(brands)} brands for auctions...")
    print(f"   Brands: {', '.join(brands[:5])}{'...' if len(brands) > 5 else ''}")
    print()
    
    async with AuctionSniper() as sniper:
        if not sniper.enabled:
            print("❌ eBay API not configured!")
            print("   Set EBAY_APP_ID and EBAY_CERT_ID in .env")
            print("   Get credentials at: https://developer.ebay.com/")
            return
        
        all_auctions = []
        
        for brand in brands:
            print(f"  🔍 {brand}", end="", flush=True)
            
            try:
                auctions = await sniper.search_auctions(
                    query=brand,
                    max_results=max_per_brand,
                    ending_within_hours=ending_within_hours,
                    max_bids=2,
                    max_price=max_price,
                )
                
                if auctions:
                    print(f" → {len(auctions)} auctions")
                    all_auctions.extend(auctions)
                else:
                    print(f" → 0 auctions")
                    
            except Exception as e:
                print(f" → error: {e}")
            
            await asyncio.sleep(0.5)  # Rate limit
        
        print()
        print(f"📊 Found {len(all_auctions)} total auctions, analyzing...")
        print()
        
        # Pre-warm price cache for brands we found
        found_brands = set()
        for auction in all_auctions:
            for brand in brands:
                if brand.lower() in auction.title.lower():
                    found_brands.add(brand)
                    break
        
        for brand in found_brands:
            await pricing.get_live_market_price(brand, "jacket")
            await pricing.get_live_market_price(brand, "pants")
            await pricing.get_live_market_price(brand, "shirt")
        
        # Analyze and save profitable auctions
        saved_count = 0
        skipped_count = 0
        opportunities = []
        
        for auction in all_auctions:
            # Detect brand
            detected_brand = None
            for brand in brands:
                if brand.lower() in auction.title.lower():
                    detected_brand = brand
                    break
            
            if not detected_brand:
                detected_brand = "unknown"
            
            # Include shipping in cost
            total_cost = auction.price + (auction.shipping_cost or 10)  # Assume $10 shipping if unknown
            
            # Get pricing recommendation
            price_info = await pricing.calculate_price_async(
                source_price=total_cost,
                brand=detected_brand,
                title=auction.title,
            )
            
            if price_info.confidence == "skip" or price_info.margin_percent < 0.25:
                skipped_count += 1
                continue
            
            # This is a potential opportunity!
            opportunities.append({
                "auction": auction,
                "brand": detected_brand,
                "price_info": price_info,
            })
            
            # Save to database
            try:
                db_item = Item(
                    source="ebay_auction",
                    source_id=auction.source_id,
                    source_url=auction.url,
                    title=f"⏰ {auction.title}",  # Mark as auction
                    brand=detected_brand,
                    size=auction.size,
                    condition=auction.condition,
                    source_price=total_cost,
                    our_price=float(price_info.recommended_price),
                    market_price=float(price_info.market_price) if price_info.market_price else None,
                    margin_percent=price_info.margin_percent,
                    images=auction.images,
                    is_auction=True,
                    status="active",
                )
                save_item(db_item)
                saved_count += 1
            except Exception as e:
                pass
        
        # Sort opportunities by profit potential
        opportunities.sort(key=lambda x: -float(x["price_info"].profit_estimate))
        
        print("=" * 60)
        print(f"📊 Results:")
        print(f"   Found: {len(all_auctions)} auctions")
        print(f"   Profitable: {len(opportunities)}")
        print(f"   Skipped: {skipped_count} (low margin)")
        print(f"   Saved: {saved_count} to database")
        print()
        
        if opportunities:
            print("🔥 TOP OPPORTUNITIES:")
            print("-" * 60)
            
            for opp in opportunities[:10]:
                auction = opp["auction"]
                info = opp["price_info"]
                
                time_str = f"{auction.time_left_hours:.1f}h" if auction.time_left_hours < 24 else f"{auction.time_left_hours/24:.1f}d"
                season_tag = f" 🔥{info.season_name}" if info.season_name else ""
                
                print(f"💰 ${auction.price:.0f} → ${info.recommended_price:.0f} (+${info.profit_estimate:.0f}, {info.margin_percent*100:.0f}%){season_tag}")
                print(f"   ⏰ {time_str} left | {auction.bid_count} bids | {opp['brand']}")
                print(f"   {auction.title[:55]}...")
                print(f"   {auction.url}")
                print()
        else:
            print("No profitable opportunities found this run.")
            print("Try again later or expand search criteria.")
    
    print()


def main():
    parser = argparse.ArgumentParser(description="Auction Sniper")
    parser.add_argument("--brand", help="Specific brand to search")
    parser.add_argument("--hours", type=int, default=12, help="Ending within hours (default: 12)")
    parser.add_argument("--max-price", type=float, default=500, help="Max current bid (default: $500)")
    parser.add_argument("--max-per-brand", type=int, default=10, help="Max auctions per brand")
    
    args = parser.parse_args()
    
    if args.brand:
        brands = [args.brand]
    else:
        brands = None  # Will use PRIORITY_BRANDS
    
    asyncio.run(snipe_auctions(
        brands=brands,
        ending_within_hours=args.hours,
        max_price=args.max_price,
        max_per_brand=args.max_per_brand,
    ))


if __name__ == "__main__":
    main()
