"""
Smart Comp Matcher — matches items against the most relevant sold comps.

Instead of generic "brand + category" searches, this module:
1. Extracts key terms from item titles (sub-brand, model, material, etc.)
2. Searches with increasingly specific queries
3. Scores each comp by similarity to the source item
4. Returns a weighted price based on similarity

This dramatically improves pricing accuracy vs. the generic approach.
"""

import re
from typing import Optional, List, Tuple
from dataclasses import dataclass, field


# Sub-brands / lines that distinguish pricing tiers
SUB_BRANDS = {
    "rick owens": ["drkshdw", "lilies", "mainline", "hun rick owens", "champion", "converse", "birkenstock", "moncler"],
    "comme des garcons": ["homme plus", "homme", "shirt", "play", "black", "tao", "junya", "parfum", "guerrilla"],
    "raf simons": ["redux", "sterling ruby", "fred perry", "adidas", "calvin klein"],
    "maison margiela": ["artisanal", "line 0", "replica", "mm6", "couture"],
    "yohji yamamoto": ["pour homme", "y's", "costume d'homme", "noir", "ground y", "new era"],
    "undercover": ["undercoverism", "supreme", "nike", "valentino"],
    "issey miyake": ["homme plisse", "pleats please", "bao bao", "plantation", "men"],
    "dior": ["homme", "men", "lady", "saddle", "book tote", "b23"],
    "saint laurent": ["paris", "rive gauche", "surf sound"],
    "prada": ["sport", "linea rossa", "re-nylon"],
    "balenciaga": ["triple s", "track", "speed", "defender"],
    "supreme": ["nike", "north face", "louis vuitton", "comme des garcons", "stone island"],
}

# Item type keywords grouped by category
ITEM_TYPES = {
    "jacket": ["jacket", "blazer", "coat", "bomber", "parka", "varsity", "windbreaker", "anorak",
                "leather jacket", "denim jacket", "trucker", "overshirt", "harrington"],
    "pants": ["pants", "trousers", "jeans", "denim", "cargo", "jogger", "sweatpants", "track pants",
              "chinos", "slacks", "cargos", "wide leg", "flare", "slim", "straight"],
    "shorts": ["shorts", "short", "swim trunks"],
    "shirt": ["shirt", "button up", "button down", "flannel", "camp collar", "hawaiian", "oxford"],
    "tee": ["t-shirt", "tee", "tshirt", "t shirt"],
    "hoodie": ["hoodie", "hooded", "sweatshirt", "pullover", "zip up", "zip-up"],
    "sweater": ["sweater", "knit", "cardigan", "jumper", "crewneck", "crew neck", "turtleneck", "mohair"],
    "boots": ["boots", "boot", "combat boots", "chelsea", "side zip", "lace up"],
    "shoes": ["shoes", "sneakers", "runners", "trainers", "loafers", "derbies", "oxford shoes",
              "slides", "sandals", "mules", "slip on"],
    "bag": ["bag", "backpack", "tote", "messenger", "duffle", "crossbody", "pouch", "clutch", "wallet"],
    "hat": ["hat", "cap", "beanie", "bucket hat", "trucker hat", "snapback"],
    "accessories": ["belt", "chain", "jewelry", "necklace", "ring", "bracelet", "scarf", "gloves", "sunglasses"],
}

# Material keywords that affect value
MATERIALS = [
    "leather", "suede", "cashmere", "silk", "wool", "linen", "denim", "corduroy",
    "nylon", "gore-tex", "goretex", "canvas", "velvet", "shearling", "fur",
    "rubber", "mesh", "knit", "waxed", "coated", "distressed", "raw",
]

# Model/style names that are specific enough to search for
MODEL_PATTERNS = [
    # Rick Owens
    r"geobasket|geo basket|ramones|ramone|kiss boot|creatch|bauhaus|bela|drkshdw|pods|mega lace",
    r"stooges|intarsia|dust|memphis|babel|sphinx|cyclops|island|sisyphus|hustler",
    # Raf Simons
    r"ozweego|response trail|replicant|cylon|runner|orion|virginia creeper|riot",
    # Margiela
    r"tabi|replica|gat|german army|fusion|paint splatter|deconstructed",
    # Others
    r"geobasket|ramones|dunks|triple s|track|speed trainer|defender",
    r"box logo|bogo|tabi|astro|flak|painter",
]

# Words to strip from search queries (noise)
NOISE_WORDS = {
    "new", "nwt", "bnwt", "nib", "brand", "authentic", "genuine", "rare", "vintage",
    "amazing", "beautiful", "perfect", "condition", "excellent", "great", "good",
    "pre-owned", "preowned", "pre", "owned", "used", "worn", "mint",
    "see", "photos", "description", "details", "check", "look",
    "size", "sz", "fits", "like", "fit", "true",
    "free", "shipping", "ship", "fast",
    "mens", "men's", "womens", "women's", "unisex",
    "the", "a", "an", "and", "or", "of", "in", "on", "for", "to", "with", "from",
}


@dataclass
class ParsedTitle:
    """Structured data extracted from an item title."""
    brand: str = ""
    sub_brand: str = ""
    item_type: str = ""          # e.g., "pants", "jacket"
    item_type_specific: str = "" # e.g., "cargo pants", "bomber jacket"
    model: str = ""              # e.g., "geobasket", "tabi"
    material: str = ""           # e.g., "leather", "cashmere"
    color: str = ""
    season: str = ""             # e.g., "AW01", "SS05"
    key_details: List[str] = field(default_factory=list)  # Other distinctive terms
    clean_title: str = ""        # Title with noise removed


@dataclass
class ScoredComp:
    """A sold comp with similarity score."""
    title: str
    price: float
    similarity: float  # 0.0 to 1.0
    url: str = ""
    source_id: str = ""


@dataclass
class CompResult:
    """Result of comp matching."""
    weighted_price: float           # Similarity-weighted median
    simple_median: float            # Simple median for comparison
    comps_count: int                # Total comps found
    high_quality_count: int         # Comps with similarity > 0.5
    confidence: str                 # high, medium, low
    query_used: str                 # Which query found the best comps
    top_comps: List[ScoredComp] = field(default_factory=list)
    # Season extraction from comps (Quick Win)
    exact_season: Optional[str] = None      # "FW", "SS", etc.
    exact_year: Optional[int] = None        # 2018, 2005, etc.
    season_confidence: str = "unknown"      # "confirmed", "inferred", "unknown"


def parse_title(brand: str, title: str) -> ParsedTitle:
    """
    Extract structured data from an item title.
    
    Example:
        "Rick Owens DRKSHDW Logo-print Rubber Slides 39 M6 W9 Black Milk New"
        → brand: rick owens, sub_brand: drkshdw, item_type: shoes,
          item_type_specific: slides, material: rubber, color: black
    """
    result = ParsedTitle()
    result.brand = brand.lower().strip()
    
    title_lower = title.lower()
    
    # Detect sub-brand
    brand_subs = SUB_BRANDS.get(result.brand, [])
    for sub in brand_subs:
        if sub.lower() in title_lower:
            result.sub_brand = sub
            break
    
    # Detect item type (most specific match first)
    best_type = ""
    best_type_specific = ""
    for category, keywords in ITEM_TYPES.items():
        for kw in sorted(keywords, key=len, reverse=True):  # Longest match first
            if kw in title_lower:
                if not best_type_specific or len(kw) > len(best_type_specific):
                    best_type = category
                    best_type_specific = kw
    result.item_type = best_type
    result.item_type_specific = best_type_specific
    
    # Detect model names (skip if it's the same as sub-brand)
    for pattern in MODEL_PATTERNS:
        match = re.search(pattern, title_lower)
        if match:
            model = match.group(0)
            if model != result.sub_brand.lower():
                result.model = model
            break
    
    # Detect material
    for mat in MATERIALS:
        if mat in title_lower:
            result.material = mat
            break
    
    # Detect season
    season_match = re.search(r'((?:ss|aw|fw|spring|fall|autumn|winter)[/\s.-]?\d{2,4})', title_lower)
    if season_match:
        result.season = season_match.group(1).strip()
    
    # Detect color (common colors)
    colors = ["black", "white", "grey", "gray", "navy", "brown", "tan", "cream",
              "red", "blue", "green", "pink", "purple", "orange", "yellow", "beige",
              "olive", "burgundy", "maroon", "charcoal", "ivory", "camel"]
    for color in colors:
        if re.search(rf'\b{color}\b', title_lower):
            result.color = color
            break
    
    # Build clean title (remove noise words)
    words = re.findall(r'[a-zA-Z]+', title)
    clean_words = [w for w in words if w.lower() not in NOISE_WORDS and len(w) > 1]
    result.clean_title = " ".join(clean_words)
    
    # Extract key details (words that aren't brand, type, or noise)
    brand_words = set(result.brand.split())
    sub_words = set(result.sub_brand.lower().split()) if result.sub_brand else set()
    type_words = set(result.item_type_specific.split()) if result.item_type_specific else set()
    
    detail_words = []
    for w in clean_words:
        wl = w.lower()
        if wl not in brand_words and wl not in sub_words and wl not in type_words:
            if wl not in NOISE_WORDS and not wl.isdigit() and len(wl) > 2:
                detail_words.append(wl)
    result.key_details = detail_words[:8]  # Keep top 8 distinctive terms
    
    return result


def build_search_queries(parsed: ParsedTitle) -> List[Tuple[str, float]]:
    """
    Build a ranked list of search queries from most specific to least.
    
    Returns: List of (query, expected_quality) tuples.
    Higher quality = more specific = better comp match.
    """
    queries = []
    brand = parsed.brand
    
    # Level 1: Very specific (model + sub-brand)
    if parsed.model and parsed.sub_brand and parsed.model != parsed.sub_brand.lower():
        queries.append((f"{brand} {parsed.sub_brand} {parsed.model}", 1.0))
    if parsed.model:
        queries.append((f"{brand} {parsed.model}", 0.95))
    
    # Level 2: Sub-brand + specific item type + material
    if parsed.sub_brand and parsed.item_type_specific:
        if parsed.material:
            queries.append((f"{brand} {parsed.sub_brand} {parsed.material} {parsed.item_type_specific}", 0.9))
        queries.append((f"{brand} {parsed.sub_brand} {parsed.item_type_specific}", 0.85))
    
    # Level 3: Brand + specific item type + material
    if parsed.item_type_specific:
        if parsed.material:
            queries.append((f"{brand} {parsed.material} {parsed.item_type_specific}", 0.8))
        queries.append((f"{brand} {parsed.item_type_specific}", 0.75))
    
    # Level 4: Key details from title
    if parsed.key_details and len(parsed.key_details) >= 2:
        detail_query = " ".join([brand] + parsed.key_details[:4])
        queries.append((detail_query, 0.7))
    
    # Level 5: Brand + category (current approach — fallback)
    if parsed.item_type:
        queries.append((f"{brand} {parsed.item_type}", 0.5))
    
    # Level 6: Just brand (last resort)
    queries.append((brand, 0.3))
    
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for q, score in queries:
        q_clean = " ".join(q.lower().split())
        if q_clean not in seen:
            seen.add(q_clean)
            unique.append((q_clean, score))
    
    return unique


def score_comp_similarity(source_parsed: ParsedTitle, comp_title: str) -> float:
    """
    Score how similar a sold comp is to our source item.
    Returns 0.0 (totally different) to 1.0 (near identical).
    """
    comp_lower = comp_title.lower()
    score = 0.0
    factors = 0
    
    # Brand match (should always match since we search by brand)
    if source_parsed.brand in comp_lower:
        score += 1.0
    factors += 1
    
    # Sub-brand match (big deal — DRKSHDW vs mainline is huge)
    if source_parsed.sub_brand:
        factors += 2  # Weight heavily
        if source_parsed.sub_brand.lower() in comp_lower:
            score += 2.0
    
    # Model match (very specific — geobasket, tabi, etc.)
    if source_parsed.model:
        factors += 3  # Weight very heavily
        if source_parsed.model in comp_lower:
            score += 3.0
    
    # Item type match
    if source_parsed.item_type_specific:
        factors += 1.5
        if source_parsed.item_type_specific in comp_lower:
            score += 1.5
        elif source_parsed.item_type and source_parsed.item_type in comp_lower:
            score += 0.75  # Partial match (category level)
    
    # Material match
    if source_parsed.material:
        factors += 1
        if source_parsed.material in comp_lower:
            score += 1.0
    
    # Color match (minor factor)
    if source_parsed.color:
        factors += 0.3
        if source_parsed.color in comp_lower:
            score += 0.3
    
    # Season match
    if source_parsed.season:
        factors += 1.5
        if source_parsed.season in comp_lower:
            score += 1.5
    
    # Key detail word overlap
    if source_parsed.key_details:
        comp_words = set(re.findall(r'[a-z]+', comp_lower))
        matches = sum(1 for d in source_parsed.key_details if d in comp_words)
        if source_parsed.key_details:
            overlap = matches / len(source_parsed.key_details)
            factors += 1
            score += overlap
    
    if factors == 0:
        return 0.0
    
    return min(score / factors, 1.0)


def weighted_median(scored_comps: List[ScoredComp]) -> float:
    """
    Calculate similarity-weighted median price.
    High-similarity comps have more influence.
    """
    if not scored_comps:
        return 0.0
    
    # Sort by price
    sorted_comps = sorted(scored_comps, key=lambda c: c.price)
    
    # Calculate weighted cumulative
    total_weight = sum(c.similarity for c in sorted_comps)
    if total_weight == 0:
        # Fall back to simple median
        return sorted_comps[len(sorted_comps) // 2].price
    
    cumulative = 0.0
    for comp in sorted_comps:
        cumulative += comp.similarity
        if cumulative >= total_weight / 2:
            return comp.price
    
    return sorted_comps[-1].price


def filter_outliers(comps: List[ScoredComp]) -> List[ScoredComp]:
    """Remove price outliers using IQR method."""
    if len(comps) < 4:
        return comps
    
    prices = sorted(c.price for c in comps)
    q1 = prices[len(prices) // 4]
    q3 = prices[3 * len(prices) // 4]
    iqr = q3 - q1
    
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    
    return [c for c in comps if lower <= c.price <= upper]

def save_sold_comp_to_db(search_key: str, item, brand: str = ""):
    """Save a sold comp to the database for catalog building."""
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from db.sqlite_models import save_sold_comp
        
        comp_data = {
            "source": item.source,
            "source_id": item.source_id,
            "title": item.title,
            "brand": brand or item.brand,
            "sold_price": item.price,
            "size": getattr(item, "size", None),
            "image_url": getattr(item, "image_url", None),
            "sold_url": item.url,
        }
        save_sold_comp(search_key, comp_data)
    except Exception as e:
        # Don't fail if saving fails
        pass


async def find_best_comps(
    brand: str,
    title: str,
    max_comps: int = 20,
    min_comps: int = 5,
    save_comps: bool = True,
) -> CompResult:
    """
    Find the best comparable sold items for pricing.
    
    Tries increasingly specific queries, scores results by similarity,
    and returns a weighted price.
    """
    try:
        from .grailed import GrailedScraper
    except ImportError:
        from scrapers.grailed import GrailedScraper
    
    # Parse the title
    parsed = parse_title(brand, title)
    
    # Build search queries
    queries = build_search_queries(parsed)
    
    all_comps = []
    best_query = ""
    seen_ids = set()
    
    async with GrailedScraper() as scraper:
        for query, query_quality in queries:
            try:
                sold_items = await scraper.search_sold(query, max_results=max_comps)
                
                if not sold_items:
                    continue
                
                new_comps = 0
                for item in sold_items:
                    if item.source_id in seen_ids:
                        continue
                    if not item.price or item.price <= 0:
                        continue
                    
                    seen_ids.add(item.source_id)
                    
                    # Save to database for catalog building
                    if save_comps:
                        save_sold_comp_to_db(query, item, brand)
                    
                    # Score similarity
                    similarity = score_comp_similarity(parsed, item.title)
                    
                    # Boost similarity by query quality
                    # Comps from specific queries are inherently more relevant
                    adjusted_similarity = similarity * 0.7 + query_quality * 0.3
                    
                    all_comps.append(ScoredComp(
                        title=item.title,
                        price=item.price,
                        similarity=adjusted_similarity,
                        url=item.url,
                        source_id=item.source_id,
                    ))
                    new_comps += 1
                
                if not best_query and new_comps > 0:
                    best_query = query
                
                # If we have enough high-quality comps, stop searching
                high_quality = [c for c in all_comps if c.similarity >= 0.5]
                if len(high_quality) >= min_comps:
                    break
                    
            except Exception as e:
                continue
    
    if not all_comps:
        return CompResult(
            weighted_price=0,
            simple_median=0,
            comps_count=0,
            high_quality_count=0,
            confidence="none",
            query_used="",
        )
    
    # Filter outliers
    filtered = filter_outliers(all_comps)
    if not filtered:
        filtered = all_comps
    
    # Sort by similarity (best matches first)
    filtered.sort(key=lambda c: -c.similarity)
    
    # Calculate prices
    w_median = weighted_median(filtered)
    
    prices = sorted(c.price for c in filtered)
    simple_med = prices[len(prices) // 2]
    
    high_quality = [c for c in filtered if c.similarity >= 0.5]
    
    # Determine confidence
    if len(high_quality) >= 8:
        confidence = "high"
    elif len(high_quality) >= 3:
        confidence = "medium"
    elif len(filtered) >= 5:
        confidence = "low"
    else:
        confidence = "very_low"
    
    # Extract season data from top comps (Quick Win)
    exact_season = None
    exact_year = None
    season_confidence = "unknown"
    
    try:
        from .seasons import aggregate_seasons_from_comps
    except ImportError:
        from scrapers.seasons import aggregate_seasons_from_comps
    
    if filtered:
        comp_titles = [c.title for c in filtered[:10]]  # Use top 10 comps
        exact_season, exact_year, season_confidence = aggregate_seasons_from_comps(comp_titles)
    
    return CompResult(
        weighted_price=w_median,
        simple_median=simple_med,
        comps_count=len(filtered),
        high_quality_count=len(high_quality),
        confidence=confidence,
        query_used=best_query,
        top_comps=filtered[:5],
        exact_season=exact_season,
        exact_year=exact_year,
        season_confidence=season_confidence,
    )


# CLI test
if __name__ == "__main__":
    import asyncio
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    tests = [
        ("rick owens", "Rick Owens DRKSHDW Logo-print Rubber Slides 39 Black"),
        ("rick owens", "Rick Owens Mainline Leather Stooges Jacket 48"),
        ("raf simons", "Raf Simons AW01 Riot Riot Riot Bomber Jacket"),
        ("raf simons", "Raf Simons x Fred Perry Polo Shirt"),
        ("helmut lang", "Helmut Lang Painter Denim Jeans 32"),
        ("number nine", "Number Nine Skull Cashmere Sweater"),
        ("maison margiela", "Maison Margiela Tabi Boots 42"),
    ]
    
    async def test():
        print("Smart Comp Matcher Test")
        print("=" * 70)
        
        for brand, title in tests:
            parsed = parse_title(brand, title)
            queries = build_search_queries(parsed)
            
            print(f"\n{'─' * 70}")
            print(f"📦 {title}")
            print(f"   Brand: {parsed.brand} | Sub: {parsed.sub_brand or '—'} | Type: {parsed.item_type_specific or parsed.item_type or '—'}")
            print(f"   Model: {parsed.model or '—'} | Material: {parsed.material or '—'} | Season: {parsed.season or '—'}")
            print(f"   Details: {parsed.key_details[:5]}")
            print(f"   Queries ({len(queries)}):")
            for q, score in queries[:4]:
                print(f"     [{score:.1f}] {q}")
            
            result = await find_best_comps(brand, title)
            
            if result.comps_count > 0:
                print(f"\n   💰 Weighted: ${result.weighted_price:.0f} | Simple: ${result.simple_median:.0f}")
                print(f"   📊 {result.comps_count} comps ({result.high_quality_count} high quality) — {result.confidence}")
                print(f"   🔍 Best query: \"{result.query_used}\"")
                if result.top_comps:
                    print(f"   Top comps:")
                    for c in result.top_comps[:3]:
                        print(f"     ${c.price:.0f} ({c.similarity:.0%}) — {c.title[:45]}...")
            else:
                print(f"   ❌ No comps found")
    
    asyncio.run(test())
