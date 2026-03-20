"""
Desirability Filter — Only alert on items the archive community actually wants.

Uses Grailed sold data as ground truth: if similar items sell frequently 
at good prices, it's desirable. If not, skip it.

This prevents sending alerts for:
- Random basics (boxer shorts, socks, underwear)
- Undesirable categories (damaged beyond repair, accessories nobody wants)
- Items with no proven resale market
- Low-value items that aren't worth the flip
"""

import re
from typing import Optional, Tuple

# ══════════════════════════════════════════════════════════════════════
# INSTANT REJECT — Never alert on these regardless of price
# ══════════════════════════════════════════════════════════════════════

REJECT_KEYWORDS = [
    # Underwear / basics
    r"\bboxer\b", r"\bunderwear\b", r"\bbrief\b", r"\bthong\b",
    r"\bsock\b", r"\bsocks\b", r"\bundershirt\b", r"\bunderpants\b",
    r"\btrunks\b",  # swim trunks or underwear
    r"\bshorts\b(?!.*\b(?:bondage|leather|cargo|runway|archive|vintage|sample)\b)",  # basic shorts (unless special)
    
    # Damaged / parts
    r"\bfor parts\b", r"\bas is\b", r"\bheavily damaged\b",
    r"\bthrashed\b", r"\bdestroyed\b", r"\bstained\b.*\bheavily\b",
    
    # Low-value accessories
    r"\bkeychain\b", r"\bphone case\b", r"\bpin\b(?!\s*stripe)",
    r"\bsticker\b", r"\bpatch\b", r"\bmagnet\b", r"\bcoaster\b",
    r"\bcandle\b", r"\bincense\b", r"\bsoap\b",
    
    # Fragrances — hard to authenticate, poor resale, skip entirely
    r"\bfragrance\b", r"\bperfume\b", r"\bcologne\b", r"\beau\s+de\b",
    r"\bparfum\b", r"\bedp\b", r"\bedt\b", r"\btoilette\b",
    r"\bsample\b.*\bfragrance\b", r"\bfragrance\b.*\bsample\b",
    r"\bdecant\b", r"\baftershave\b",
    
    # Generic non-fashion
    r"\bbook\b", r"\bmagazine\b", r"\bcatalog\b",
    r"\bposter\b", r"\bprint\b(?!ed)",
    r"\btowel\b", r"\bpillow\b", r"\bblanket\b",

    # Fast-fashion collabs — NOT worth flipping
    r"\bh&m\b", r"\bh\s*&\s*m\b", r"\bhm\s*x\b", r"\bx\s*h&m\b",
    r"\buniqlo\b", r"\btarget\b(?!.*\b(?:target\s+market)\b)",
    r"\bzara\b", r"\bshein\b", r"\bforever\s*21\b",
    r"\bgap\b(?!.*\byeezy\b)",  # gap collabs except Yeezy
    r"\bprimark\b", r"\basos\b",

    # Lookalikes / "style" / "type" / "inspired by" — NOT the real thing
    r"\blike\s+(?:margiela|raf|rick|chrome\s*hearts|dior|gaultier|balenciaga|prada)\b",
    r"\b(?:margiela|chrome\s*hearts|raf|rick|dior|gaultier)\s+style\b",
    r"\breplica\s+style\b",
    r"\b(?:type|inspired)\s*(?:by)?\s*(?:margiela|raf|rick|dior|gaultier|chrome\s*hearts|balenciaga|prada|gucci)\b",
    r"\bstyle\s+(?:of|like)\b",
    r"\b(?:chrome\s*hearts|ch)\s+style\b",
    r"\binspired\s+(?:by\s+)?(?:chrome|ch|hearts)\b",
    r"\bgerman\s+army\s+trainer\b(?!.*\bmargiela\b)",
    r"\bbw\s+sport\b(?!.*\bmargiela\b)",
    # Obvious fakes / unbranded claiming brand
    r"\bunbranded\b.*\b(?:chrome|rick|raf|margiela|dior)\b",
    r"\b(?:chrome|rick|raf|margiela|dior)\b.*\bunbranded\b",
    r"\bno\s+brand\b",
]

REJECT_PATTERNS = [re.compile(p, re.IGNORECASE) for p in REJECT_KEYWORDS]


# ══════════════════════════════════════════════════════════════════════
# HIGH DESIRABILITY — Items the archive community loves
# Presence of these keywords BOOSTS the item's desirability score
# ══════════════════════════════════════════════════════════════════════

DESIRABLE_KEYWORDS = {
    # Outerwear — always in demand
    "jacket": 0.8, "leather jacket": 1.0, "bomber": 0.9, "blazer": 0.7,
    "coat": 0.8, "parka": 0.7, "varsity": 0.8, "moto": 0.9,
    "denim jacket": 0.8, "trucker jacket": 0.7, "flight jacket": 0.8,
    "overcoat": 0.7, "trench": 0.7,
    
    # Pants
    "jeans": 0.7, "cargo": 0.8, "flared": 0.8, "bondage pants": 1.0,
    "leather pants": 0.9, "denim": 0.7, "painter pants": 0.8,
    "trousers": 0.6,
    
    # Knitwear
    "sweater": 0.6, "knit": 0.6, "cardigan": 0.6, "mohair": 0.8,
    "intarsia": 0.8,
    
    # Tops
    "mesh top": 0.9, "mesh": 0.7, "corset": 0.9,
    "hoodie": 0.7, "sweatshirt": 0.6,
    
    # Footwear — very desirable
    "boots": 0.9, "geobasket": 1.0, "ramones": 1.0, "dunks": 0.9,
    "tabi": 1.0, "kiss boots": 0.9, "combat boots": 0.8,
    "platform": 0.8, "creepers": 0.8, "sneakers": 0.7,
    "derby": 0.7, "loafers": 0.6,
    
    # Jewelry & accessories (high value)
    "necklace": 0.8, "pendant": 0.8, "cross pendant": 1.0,
    "ring": 0.7, "bracelet": 0.7, "chain": 0.7,
    "sterling": 0.7, "925": 0.7,
    "belt": 0.7,
    "eyewear": 0.7, "sunglasses": 0.7,
    
    # Headwear
    "trucker hat": 0.7, "cap": 0.5,
    
    # Archive-specific terms
    "archive": 0.8, "vintage": 0.6, "runway": 0.9, "sample": 0.8,
    "deadstock": 0.9, "nwt": 0.8, "new with tags": 0.8,
    "rare": 0.7, "grail": 1.0, "limited": 0.7,
    "ss": 0.5, "fw": 0.5, "aw": 0.5,  # Season tags
    
    # Iconic pieces / collections
    "bondage": 1.0, "astro": 0.9, "painter": 0.8,
    "riot": 1.0, "virginia creeper": 1.0, "consumed": 0.9,
    "peter saville": 0.9, "new order": 0.9,
    "soloist": 0.9, "skull": 0.7,
    "scab": 0.9, "85": 0.8,
    "cemetery": 0.8, "dagger": 0.8, "floral cross": 0.9,
    "cyberbaba": 0.9, "tattoo": 0.7,
    "orb": 0.8, "artisanal": 0.9,
    "hedi": 0.9, "navigate": 0.8,
}

# ══════════════════════════════════════════════════════════════════════
# MINIMUM REQUIREMENTS by confidence level
# ══════════════════════════════════════════════════════════════════════

# Only send deals where we have STRONG comp data
QUALITY_REQUIREMENTS = {
    "high": {       # 5+ sold comps matched
        "min_profit": 40,
        "min_margin": 0.25,
        "min_desirability": 0.3,
    },
    "medium": {     # 3-4 comps
        "min_profit": 60,
        "min_margin": 0.30,
        "min_desirability": 0.5,
    },
    "low": {        # Static estimates only — need very high desirability
        "min_profit": 100,
        "min_margin": 0.40,
        "min_desirability": 0.7,
    },
}


def check_desirability(
    title: str,
    brand: str = "",
    price: float = 0,
    profit: float = 0,
    margin: float = 0,
    confidence: str = "low",
    comps_count: int = 0,
    demand_level: str = "unknown",
) -> Tuple[bool, float, str]:
    """
    Check if an item is desirable enough to alert on.
    
    Returns:
        (should_alert, desirability_score, reason)
    """
    title_lower = title.lower()
    
    # Step 1: Instant reject
    for pattern in REJECT_PATTERNS:
        if pattern.search(title_lower):
            return False, 0.0, f"Rejected: {pattern.pattern}"
    
    # Step 2: Calculate desirability score
    score = 0.0
    matched_keywords = []
    
    for keyword, weight in DESIRABLE_KEYWORDS.items():
        if keyword.lower() in title_lower:
            score = max(score, weight)  # Take highest matching weight
            matched_keywords.append(keyword)
    
    # Boost for multiple desirable keywords
    if len(matched_keywords) >= 2:
        score = min(1.0, score + 0.1)
    if len(matched_keywords) >= 3:
        score = min(1.0, score + 0.1)
    
    # Demand level boost
    if demand_level == "hot":
        score = min(1.0, score + 0.2)
    elif demand_level == "warm":
        score = min(1.0, score + 0.1)
    elif demand_level == "dead":
        score = max(0.0, score - 0.3)
    
    # Step 3: Check quality requirements based on pricing confidence
    reqs = QUALITY_REQUIREMENTS.get(confidence, QUALITY_REQUIREMENTS["low"])
    
    # Override: if we have 0 comps, require very high desirability
    if comps_count == 0:
        reqs = QUALITY_REQUIREMENTS["low"]
    
    reasons = []
    passes = True
    
    if profit < reqs["min_profit"]:
        passes = False
        reasons.append(f"Profit ${profit:.0f} < ${reqs['min_profit']} required for {confidence} confidence")
    
    if margin < reqs["min_margin"]:
        passes = False
        reasons.append(f"Margin {margin*100:.0f}% < {reqs['min_margin']*100:.0f}% required")
    
    if score < reqs["min_desirability"]:
        passes = False
        reasons.append(f"Desirability {score:.1f} < {reqs['min_desirability']} required (matched: {', '.join(matched_keywords[:3]) or 'none'})")
    
    if passes:
        reason = f"✅ Desirable ({score:.1f}): {', '.join(matched_keywords[:3])}"
    else:
        reason = "; ".join(reasons)
    
    return passes, score, reason


def get_desirability_emoji(score: float) -> str:
    """Get emoji representation of desirability."""
    if score >= 0.9:
        return "🔥🔥🔥"
    elif score >= 0.7:
        return "🔥🔥"
    elif score >= 0.5:
        return "🔥"
    elif score >= 0.3:
        return "✓"
    else:
        return "—"


if __name__ == "__main__":
    # Test cases
    tests = [
        ("Rick Owens Geobasket High Top Sneakers", "rick owens", 300, 150, 0.33, "high", 8, "hot"),
        ("Rick Owens black Cyclops boxer shorts", "rick owens", 188, 92, 0.33, "medium", 5, "warm"),
        ("Helmut Lang Bondage Strap Leather Jacket", "helmut lang", 400, 300, 0.43, "high", 12, "hot"),
        ("Thierry Mugler men vintage shorts", "mugler", 52, 62, 0.54, "medium", 4, "warm"),
        ("Raf Simons Riot Riot Riot Bomber FW01", "raf simons", 800, 1200, 0.60, "high", 6, "hot"),
        ("Chrome Hearts Cross Pendant Sterling Silver", "chrome hearts", 200, 300, 0.60, "high", 10, "hot"),
        ("CDG Play Heart Tee", "comme des garcons", 40, 20, 0.33, "low", 0, "cold"),
        ("Supreme Box Logo Sticker", "supreme", 5, 3, 0.37, "low", 0, "cold"),
        ("Jean Paul Gaultier Mesh Top Cyberbaba", "jean paul gaultier", 150, 250, 0.62, "high", 7, "hot"),
    ]
    
    print(f"\n{'='*80}")
    print("DESIRABILITY FILTER TEST")
    print(f"{'='*80}\n")
    
    for title, brand, price, profit, margin, conf, comps, demand in tests:
        passes, score, reason = check_desirability(
            title, brand, price, profit, margin, conf, comps, demand
        )
        emoji = "✅" if passes else "❌"
        print(f"{emoji} {title[:55]:55s} | Score: {score:.1f} | {reason[:60]}")
