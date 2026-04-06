"""
Auto-generate Instagram captions from deal data.

Produces platform-ready captions with:
- Deal breakdown (price, market value, profit)
- Brand + item context
- Comp-backed confidence language
- Rotating hashtag sets
- CTA (subscribe link)

Tone: Confident, data-driven, not hype. Speaks to people who already
know archive fashion. Never desperate — the product speaks for itself.
"""

from __future__ import annotations

import random
from typing import Optional

from .deal_card import DealCardData


# ── Hashtag sets (rotate to avoid IG shadowban) ──
HASHTAG_SETS = [
    "#archivefashion #grailed #designerresale #luxuryresale #fashionflip #reseller #archiveclothing #grailedfinds",
    "#archivereseller #designerfashion #luxuryflip #resellercommunity #graileddeals #fashiontech #flipforprofit",
    "#archivefashion #luxuryresale #designerresale #archivereseller #fashionflip #resellertips #grailed",
]

# Brand-specific hashtags
BRAND_HASHTAGS = {
    "rick owens": "#rickowens #drkshdw #geobasket #ramones",
    "chrome hearts": "#chromehearts #chromeheartsjewelry #chromeheartsforlife",
    "maison margiela": "#maisonmargiela #margiela #tabiboots #margielajeans",
    "enfants riches deprimes": "#erd #enfantsrichesdeprimes",
    "erd": "#erd #enfantsrichesdeprimes",
    "saint laurent": "#saintlaurent #slp #ysl #hedislimane",
    "jean paul gaultier": "#jeanpaulgaultier #jpg #gaultier #jpgmesh",
    "helmut lang": "#helmutlang #helmutlangarchive",
    "raf simons": "#rafsimons #rafsimonsarchive",
    "bottega veneta": "#bottegaveneta #bottega",
    "dior homme": "#diorhomme #hedislimane #dior",
    "undercover": "#undercover #juntakahashi #undercoverism",
    "balenciaga": "#balenciaga #demna",
    "kapital": "#kapital #borojacket #kapitalboro",
    "number nine": "#numbernine #numberninearchive",
    "prada": "#prada #pradasport #miumiu",
    "vivienne westwood": "#viviennewestwood #westwood",
    "yohji yamamoto": "#yohjiyamamoto #yohji #pourhomme",
    "guidi": "#guidi #guidiboots",
    "julius": "#julius #julius7",
    "dries van noten": "#driesvannoten #dvn",
    "alexander mcqueen": "#alexandermcqueen #mcqueen",
    "thierry mugler": "#thierrymugler #mugler",
    "acne studios": "#acnestudios #acne",
}

# Opening lines — rotated for variety
OPENERS_FIRE = [
    "This one hit different.",
    "The bot doesn't miss.",
    "This is why you subscribe.",
    "Caught this before the reseller pages did.",
    "The comps don't lie.",
    "Priced wrong. Verified real.",
]

OPENERS_STANDARD = [
    "Another one from the scanner.",
    "Found on {source}. Verified against sold comps.",
    "The system flagged this in seconds.",
    "Numbers speak for themselves.",
]

# CTAs — rotated
CTAS = [
    "Real deals. Verified by comps. 24/7.\nLink in bio.",
    "We scan so you don't have to.\nLink in bio.",
    "One flip pays for months of the subscription.\nLink in bio.",
    "Real-time alerts. Authenticated deals. 270+ brands.\nLink in bio.",
]


def _source_display(source: str) -> str:
    return {
        "grailed": "Grailed",
        "poshmark": "Poshmark",
        "ebay": "eBay",
        "depop": "Depop",
        "mercari": "Mercari",
        "vinted": "Vinted",
    }.get(source.lower(), source.title())


def generate_deal_caption(data: DealCardData) -> str:
    """Generate an Instagram caption for a deal post.

    Returns a ready-to-post caption string.
    """
    source_name = _source_display(data.source)

    # Pick opener based on fire level
    if data.fire_level >= 2:
        opener = random.choice(OPENERS_FIRE)
    else:
        opener = random.choice(OPENERS_STANDARD).format(source=source_name)

    # Core deal breakdown
    breakdown = (
        f"{data.brand} — {data.title}\n"
        f"\n"
        f"Listed: ${data.buy_price:,.0f}\n"
        f"Market value: ${data.market_price:,.0f} (based on {data.comp_count} sold comps)\n"
        f"Est. profit: ${data.profit:,.0f} ({data.margin * 100:.0f}% below market)\n"
        f"Found on {source_name}"
    )

    # Optional context lines
    context_parts = []
    if data.season_name:
        context_parts.append(f"Season: {data.season_name}")
    if data.auth_confidence >= 0.7:
        context_parts.append(f"Auth confidence: {data.auth_confidence * 100:.0f}%")
    if data.demand_level in ("hot", "warm"):
        context_parts.append(f"Demand: {data.demand_level.upper()}")

    context = ""
    if context_parts:
        context = "\n" + " | ".join(context_parts)

    # CTA
    cta = random.choice(CTAS)

    # Hashtags
    base_tags = random.choice(HASHTAG_SETS)
    brand_tags = BRAND_HASHTAGS.get(data.brand.lower(), "")
    all_tags = f"{brand_tags} {base_tags}".strip()

    caption = f"{opener}\n\n{breakdown}{context}\n\n{cta}\n\n{all_tags}"

    return caption


def generate_weekly_recap_caption(
    total_deals: int,
    total_profit: float,
    top_brands: list[tuple[str, int]],
    best_deal_profit: float,
    date_range: str,
) -> str:
    """Generate a caption for the weekly deal recap carousel."""

    brand_lines = "\n".join(
        f"  {brand}: {count} deal{'s' if count > 1 else ''}"
        for brand, count in top_brands[:5]
    )

    caption = (
        f"This week's numbers ({date_range}):\n"
        f"\n"
        f"{total_deals} verified deals sent to subscribers\n"
        f"${total_profit:,.0f} total profit opportunity\n"
        f"Best single deal: ${best_deal_profit:,.0f} profit\n"
        f"\n"
        f"Top brands:\n{brand_lines}\n"
        f"\n"
        f"Every deal backed by sold comp data. Every item authenticated.\n"
        f"\n"
        f"One flip pays for months of the subscription.\n"
        f"Link in bio.\n"
        f"\n"
        f"#archivefashion #grailed #designerresale #luxuryresale #reseller #archiveclothing"
    )

    return caption


def generate_market_intel_caption(
    trending_up: list[tuple[str, float]],
    trending_down: list[tuple[str, float]],
    insight: str,
) -> str:
    """Generate a caption for a market intelligence post."""

    up_lines = "\n".join(
        f"  {brand} +{pct:.0f}%"
        for brand, pct in trending_up[:5]
    )
    down_lines = "\n".join(
        f"  {brand} {pct:.0f}%"
        for brand, pct in trending_down[:3]
    )

    caption = (
        f"Market intel — what's moving this week:\n"
        f"\n"
        f"Trending up:\n{up_lines}\n"
    )

    if down_lines:
        caption += f"\nCooling off:\n{down_lines}\n"

    caption += (
        f"\n{insight}\n"
        f"\n"
        f"We track price velocity across 7 platforms. Our subscribers get the deals before the market catches up.\n"
        f"Link in bio.\n"
        f"\n"
        f"#archivefashion #marketdata #designerresale #luxuryresale #reseller"
    )

    return caption
