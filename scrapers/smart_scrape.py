#!/usr/bin/env python3
"""
Smart Scraper — Finds high-quality archive deals using targeted search strategies.

Instead of generic brand searches, this targets:
1. Specific iconic pieces/collections that resellers want
2. Mistagged/undervalued listings (seller doesn't know what they have)
3. Newly listed items (first to see = first to buy)
4. Cross-platform price gaps
5. eBay auctions ending soon with no/low bids
"""

import asyncio
import os
import sys
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from scrapers import GrailedScraper, PoshmarkScraper, ScrapedItem
from api.services.pricing import PricingService
from core.authenticity_v2 import AuthenticityCheckerV2, format_auth_bar, format_auth_grade, MIN_AUTH_SCORE
from telegram_bot import send_deal_to_subscribers, get_active_subscribers
from db.sqlite_models import init_db, save_item, Item

# ==========================================================================
# Targeted searches — specific grail pieces the archive community wants
# ==========================================================================

GRAIL_SEARCHES = [
    # Rick Owens iconic pieces
    "rick owens geobasket",
    "rick owens ramones",
    "rick owens dunks",
    "rick owens kiss boots",
    "rick owens bauhaus",
    "rick owens creatch",
    "rick owens memphis",
    "rick owens dust",
    "rick owens babel",
    "rick owens island",
    "rick owens stag",
    "rick owens moody",
    "rick owens limo",
    "rick owens intarsia",
    
    # Raf Simons grails
    "raf simons riot",
    "raf simons virginia creeper",
    "raf simons consumed",
    "raf simons peter saville",
    "raf simons antwerp",
    "raf simons new order",
    "raf simons ozweego",
    "raf simons history of my world",
    "raf simons waves",
    "raf simons poltergeist",
    
    # Helmut Lang archive
    "helmut lang bondage",
    "helmut lang astro",
    "helmut lang painter",
    "helmut lang bulletproof",
    "helmut lang vintage leather",
    "helmut lang 1998",
    "helmut lang 1999",
    "helmut lang 2000",
    "helmut lang 2001",
    "helmut lang flak jacket",
    
    # Number Nine grails
    "number nine soloist",
    "number nine skull",
    "number nine touch me",
    "number nine gun",
    "number nine cigarette",
    "number nine 2005",
    "number nine 2006",
    
    # Undercover
    "undercover scab",
    "undercover 85",
    "undercover languid",
    "undercover but beautiful",
    "undercover arts and crafts",
    "undercover davf",
    "undercover psycho color",
    
    # Chrome Hearts
    "chrome hearts cross pendant",
    "chrome hearts cemetery",
    "chrome hearts dagger",
    "chrome hearts floral cross",
    "chrome hearts eyewear",
    "chrome hearts leather",
    "chrome hearts trucker hat",
    
    # JPG
    "jean paul gaultier mesh",
    "jean paul gaultier maille",
    "jean paul gaultier cyberbaba",
    "jean paul gaultier tattoo",
    "jean paul gaultier femme",
    "jean paul gaultier homme",
    "gaultier mesh top",
    "gaultier corset",
    
    # Vivienne Westwood
    "vivienne westwood orb necklace",
    "vivienne westwood pearl",
    "vivienne westwood corset",
    "vivienne westwood armor ring",
    
    # Maison Margiela
    "margiela tabi",
    "margiela artisanal",
    "margiela flat tabi",
    "margiela painted",
    "maison martin margiela",
    
    # Dior Homme (Hedi era)
    "dior homme hedi",
    "dior homme 2003",
    "dior homme 2004",
    "dior homme 2005",
    "dior homme 2006",
    "dior homme navigate",
    "dior homme luster",
    "dior homme victim",
    
    # Thierry Mugler
    "thierry mugler vintage",
    "mugler blazer",
    "mugler power shoulder",
    "mugler corset",
    "mugler robot",
    
    # ERD (generic + piece-specific)
    "enfants riches deprimes",
    "erd hoodie",
    "erd tee",
    "enfants riches deprimes classic logo hoodie",
    "enfants riches deprimes classic logo tee",
    "enfants riches deprimes safety pin earring",
    "enfants riches deprimes bennys video hoodie",
    "enfants riches deprimes menendez hoodie",
    "enfants riches deprimes viper room hat",
    
    # Hysteric Glamour
    "hysteric glamour vintage",
    "hysteric glamour courtney love",
    "hysteric glamour skull",
    
    # CDG — removed (margins not there, all sub-labels demoted)
    
    # Issey Miyake
    "issey miyake homme plisse",
    "issey miyake pleats please",
    "issey miyake bomber",
    
    # Kapital
    "kapital century denim",
    "kapital boro",
    "kapital skeleton",
    "kapital smiley",
    
    # Other sought-after
    "carol christian poell",
    "boris bidjan saberi",
    "julius gas mask",
    "julius cargo",
    "ann demeulemeester boots",
    "vetements champion hoodie",
    "vetements total darkness hoodie",
    "vetements polizei hoodie",
    "vetements metal logo hoodie",
    "vetements dhl tee",
    "vetements snoop dogg",
    "vetements alpha industries bomber",
    "vetements staff hoodie",
    "vetements securite hoodie",
    "alexander mcqueen bumster",
    "hussein chalayan",
]

# Mistagged / undervalued search terms — find items where sellers don't know the value
MISTAGGED_SEARCHES = [
    # Generic terms that might hide grails
    "vintage designer jacket",
    "vintage leather jacket designer",
    "vintage japanese designer",
    "vintage avant garde",
    "vintage punk jacket",
    "vintage goth clothing",
    "made in italy vintage jacket",
    "made in japan vintage",
    "avant garde vintage",
    "deconstructed jacket vintage",
    "asymmetric designer",
    "archive fashion",
    "archive designer",
    "90s designer jacket",
    "2000s designer rare",
    "runway sample",
    "fashion sample",
    "designer estate sale",
    "vintage mesh top",
    "vintage corset top",
    "vintage bondage",
    "military boots designer",
    "platform boots vintage",
    "sterling silver cross pendant",
    "925 silver designer ring",
    "japanese streetwear vintage",
]


async def smart_scrape(max_per_search: int = 10, include_mistagged: bool = True):
    """Run smart targeted scrapes."""
    init_db()
    pricing = PricingService()
    auth = AuthenticityCheckerV2()
    
    all_searches = list(GRAIL_SEARCHES)
    if include_mistagged:
        all_searches.extend(MISTAGGED_SEARCHES)
    
    total_found = 0
    deals_sent = 0
    blocked = 0
    
    print(f"\n{'='*60}")
    print(f"🎯 SMART SCRAPE — {len(all_searches)} targeted searches")
    print(f"{'='*60}\n")
    
    for i, query in enumerate(all_searches):
        print(f"  [{i+1}/{len(all_searches)}] 🔍 {query}")
        
        items = []
        
        # Search Grailed
        try:
            async with GrailedScraper() as scraper:
                results = await scraper.search(query, max_results=max_per_search)
                items.extend(results)
                if results:
                    print(f"    ✓ grailed: {len(results)} items")
        except Exception as e:
            print(f"    ✗ grailed: {e}")
        
        # Search Poshmark
        try:
            async with PoshmarkScraper() as scraper:
                results = await scraper.search(query, max_results=max_per_search)
                items.extend(results)
                if results:
                    print(f"    ✓ poshmark: {len(results)} items")
        except Exception as e:
            print(f"    ✗ poshmark: {e}")
        
        total_found += len(items)
        
        for scraped in items:
            try:
                # Detect brand
                brand = _detect_brand(scraped.title) or query.split()[0]
                category = _detect_category(scraped.title)
                
                # Get pricing
                price_rec = await pricing.calculate_price_async(
                    title=scraped.title,
                    brand=brand,
                    category=category,
                    source_price=scraped.price,
                    condition=scraped.condition,
                    size=getattr(scraped, "size", ""),
                )
                
                if not price_rec or price_rec.margin_percent < 0.25:
                    continue
                
                # Auth check
                auth_result = await auth.check(
                    title=scraped.title,
                    description=scraped.description or "",
                    price=scraped.price,
                    brand=brand,
                    category=category or "",
                    seller_name=scraped.seller or "",
                    seller_sales=getattr(scraped, "seller_sales", 0),
                    seller_rating=getattr(scraped, "seller_rating", None),
                    images=scraped.images,
                    source=scraped.source,
                )
                
                if auth_result.action == "block" or auth_result.confidence < MIN_AUTH_SCORE:
                    blocked += 1
                    continue
                
                profit = float(price_rec.profit_estimate) if hasattr(price_rec, 'profit_estimate') else 0
                
                print(f"    💰 {scraped.title[:50]}...")
                print(f"       ${scraped.price:.0f} → ${price_rec.recommended_price:.0f} ({price_rec.margin_percent*100:.0f}%) {format_auth_grade(auth_result.grade)}")
                
                # Send to Telegram
                try:
                    await send_deal_to_subscribers(
                        scraped, price_rec, brand=brand,
                        auth_result=None, auth_v2=auth_result
                    )
                    deals_sent += 1
                except Exception as e:
                    print(f"       ⚠️ Send failed: {e}")
                    
            except Exception as e:
                continue
        
        # Rate limit between searches
        await asyncio.sleep(2)
    
    print(f"\n{'='*60}")
    print(f"📊 Smart Scrape Results:")
    print(f"   Searches: {len(all_searches)}")
    print(f"   Items found: {total_found}")
    print(f"   Deals sent: {deals_sent}")
    print(f"   Blocked (auth): {blocked}")
    print(f"{'='*60}\n")


def _detect_brand(title: str) -> str:
    """Detect brand from title."""
    title_lower = title.lower()
    brands = [
        "rick owens", "chrome hearts", "raf simons", "helmut lang",
        "number nine", "undercover", "jean paul gaultier", "gaultier",
        "vivienne westwood", "maison margiela", "martin margiela", "margiela",
        "dior homme", "dior", "thierry mugler", "mugler",
        "enfants riches deprimes", "erd", "hysteric glamour",
        "comme des garcons", "cdg",
        "issey miyake", "kapital", "carol christian poell",
        "boris bidjan saberi", "julius", "ann demeulemeester",
        "vetements", "alexander mcqueen",
        "hussein chalayan", "balenciaga", "saint laurent",
        "prada", "gucci", "louis vuitton", "supreme", "off-white",
        "gallery dept", "amiri", "bape",
    ]
    for brand in brands:
        if brand in title_lower:
            return brand
    return ""


def _detect_category(title: str) -> str:
    """Detect category from title."""
    title_lower = title.lower()
    categories = {
        "jacket": ["jacket", "blazer", "coat", "bomber", "parka", "varsity"],
        "pants": ["pants", "trousers", "jeans", "denim", "cargo"],
        "shirt": ["shirt", "button up", "button down"],
        "tee": ["t-shirt", "tee", "t shirt"],
        "hoodie": ["hoodie", "hooded", "pullover"],
        "sweater": ["sweater", "knit", "cardigan"],
        "boots": ["boots", "boot", "geobasket", "ramones"],
        "shoes": ["shoes", "sneakers", "runners", "dunks"],
        "bag": ["bag", "backpack", "tote"],
        "jewelry": ["necklace", "ring", "bracelet", "pendant", "chain", "cross"],
        "accessories": ["belt", "wallet", "hat", "cap", "eyewear", "sunglasses"],
        "top": ["mesh", "tank", "corset"],
    }
    for cat, keywords in categories.items():
        if any(kw in title_lower for kw in keywords):
            return cat
    return ""


if __name__ == "__main__":
    asyncio.run(smart_scrape())
