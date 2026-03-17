"""
Smart Comp Matcher — matches items against the most relevant sold comps.

Instead of generic "brand + category" searches, this module:
1. Extracts key terms from item titles (sub-brand, model, material, etc.)
2. Searches with increasingly specific queries
3. Scores each comp by similarity to the source item
4. Returns a weighted price based on similarity

This dramatically improves pricing accuracy vs. the generic approach.
"""

import logging
import math
import re
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("comp_matcher")


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

# Hybrid model type aliases — models that span multiple item type categories.
# Used by is_exact_match() to allow valid cross-type comp matching.
# Includes both current ("shoes") and post-split ("sneakers", "loafers") names
# so aliases work before and after the item_type split in Task 3.
TYPE_ALIASES: dict[str, set[str]] = {
    "geobasket": {"boots", "shoes", "sneakers"},
    "geo basket": {"boots", "shoes", "sneakers"},
    "kiss boot": {"boots", "shoes", "sneakers"},
    "tractor": {"boots", "shoes", "sneakers"},
    "ramones": {"boots", "shoes", "sneakers"},
    "tabi": {"boots", "shoes", "loafers", "sneakers"},
}

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
    platform: str = ""
    sold_date: Optional[datetime] = None
    condition: Optional[str] = None
    size: Optional[str] = None
    is_auction: bool = False
    num_bids: Optional[int] = None
    shipping_cost: Optional[float] = None
    normalized_price: Optional[float] = None  # After all normalizations


@dataclass
class CompResult:
    """Result of comp matching."""
    weighted_price: float           # Similarity-weighted median
    simple_median: float            # Simple median for comparison
    comps_count: int                # Total comps found
    high_quality_count: int         # Comps with similarity > 0.5
    confidence: str                 # high, medium, low (kept for backward compat)
    query_used: str                 # Which query found the best comps
    top_comps: List[ScoredComp] = field(default_factory=list)
    confidence_score: float = 0.0   # Numeric 0.0-1.0
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


def is_exact_match(listing: ParsedTitle, comp: ParsedTitle) -> bool:
    """Hard dimension gate — ALL checks must pass for a comp to be valid.

    Dimensions checked:
        1. Brand: must match exactly
        2. Model: must match if detected on both sides
        3. Item type: must match (broad category level)
        4. Line tier: mainline/diffusion must agree
        5. Material: must match if detectable in both titles
    """
    # 1. Brand — always required
    if listing.brand != comp.brand:
        return False

    # 2. Model — reject only if BOTH detected and different
    if listing.model and comp.model:
        if listing.model.lower() != comp.model.lower():
            return False

    # 3. Item type — reject if both detected and different
    if listing.item_type and comp.item_type:
        if listing.item_type != comp.item_type:
            # Check type aliases for hybrid models (e.g., geobasket = boots OR sneakers)
            listing_model = (listing.model or "").lower()
            comp_model = (comp.model or "").lower()
            listing_types = TYPE_ALIASES.get(listing_model, {listing.item_type})
            comp_types = TYPE_ALIASES.get(comp_model, {comp.item_type})
            if not listing_types & comp_types:
                return False

    # 4. Line tier — mainline vs diffusion must agree
    listing_is_diffusion = bool(listing.sub_brand)
    comp_is_diffusion = bool(comp.sub_brand)
    if listing_is_diffusion != comp_is_diffusion:
        return False
    # If both are diffusion, must be SAME diffusion line
    if listing_is_diffusion and comp_is_diffusion:
        if listing.sub_brand.lower() != comp.sub_brand.lower():
            return False

    # 5. Material — reject only if BOTH detected and different
    if listing.material and comp.material:
        if listing.material.lower() != comp.material.lower():
            return False

    return True


# ══════════════════════════════════════════════════════════════
# CATEGORY-SPECIFIC PARAMETERS
# ══════════════════════════════════════════════════════════════

CATEGORY_CONFIG = {
    "leather_jacket": {
        "time_decay_halflife": 90,      # Leathers hold value, slow change
        "condition_sensitivity": 0.7,    # Patina is acceptable
    },
    "jacket": {
        "time_decay_halflife": 60,
        "condition_sensitivity": 0.85,
    },
    "boots": {
        "time_decay_halflife": 60,
        "condition_sensitivity": 0.9,
    },
    "shoes": {
        "time_decay_halflife": 30,       # Sneaker prices move fast
        "condition_sensitivity": 1.3,     # Condition matters a lot
    },
    "tee": {
        "time_decay_halflife": 45,
        "condition_sensitivity": 1.1,
    },
    "hoodie": {
        "time_decay_halflife": 45,
        "condition_sensitivity": 1.0,
    },
    "sweater": {
        "time_decay_halflife": 50,
        "condition_sensitivity": 1.0,
    },
    "pants": {
        "time_decay_halflife": 60,
        "condition_sensitivity": 0.9,
    },
    "bag": {
        "time_decay_halflife": 60,
        "condition_sensitivity": 1.0,
    },
    "accessories": {
        "time_decay_halflife": 60,
        "condition_sensitivity": 0.9,
    },
}

DEFAULT_HALFLIFE = 45
DEFAULT_CONDITION_SENSITIVITY = 1.0


def get_category_config(item_type: str) -> dict:
    """Get category-specific parameters, falling back to defaults."""
    item_type = (item_type or "").lower()
    # Check for leather jacket specifically
    if "leather" in item_type and ("jacket" in item_type or "coat" in item_type):
        return CATEGORY_CONFIG["leather_jacket"]
    for key, config in CATEGORY_CONFIG.items():
        if key in item_type:
            return config
    return {"time_decay_halflife": DEFAULT_HALFLIFE, "condition_sensitivity": DEFAULT_CONDITION_SENSITIVITY}


# ══════════════════════════════════════════════════════════════
# TIME-DECAY WEIGHTING
# ══════════════════════════════════════════════════════════════

def time_decay_weight(sold_date: Optional[datetime], half_life_days: int = 45) -> float:
    """
    Exponential decay: a sale from half_life_days ago has half the weight.
    Returns 1.0 for today, 0.5 for half_life_days ago, etc.
    """
    if sold_date is None:
        return 0.5  # Unknown date — assume ~half-life old

    age_days = (datetime.now(tz=None) - sold_date).total_seconds() / 86400
    if age_days < 0:
        age_days = 0
    return math.exp(-0.693 * age_days / max(half_life_days, 1))


# ══════════════════════════════════════════════════════════════
# CONDITION ADJUSTMENT
# ══════════════════════════════════════════════════════════════

CONDITION_MULTIPLIERS = {
    "deadstock": 1.35,
    "nwt": 1.35,
    "near_deadstock": 1.25,
    "nwot": 1.25,
    "excellent": 1.15,
    "very_good": 1.05,
    "good": 1.00,
    "gently_used": 0.85,
    "used": 0.75,
    "fair": 0.65,
    "poor": 0.50,
}

# How much condition affects price for specific brands
BRAND_CONDITION_SENSITIVITY = {
    "rick owens": 0.8,       # Leather patina is expected/desired
    "number nine": 0.85,     # Vintage wear expected
    "helmut lang": 0.85,     # Vintage pieces
    "undercover": 0.9,
    "maison margiela": 0.9,  # Deconstructed aesthetic
    "raf simons": 1.0,
    "supreme": 1.2,          # Collectors — condition matters MORE
    "bape": 1.2,
    "chrome hearts": 1.1,
}


def normalize_condition(condition: Optional[str]) -> Optional[str]:
    """Normalize condition strings to our tier keys."""
    if not condition:
        return None
    c = condition.lower().strip()

    mappings = [
        (["deadstock", "ds", "bnwt", "brand new with tags", "new with tags", "nwt"], "nwt"),
        (["nwot", "new without tags", "like new", "vnds"], "nwot"),
        (["excellent", "pristine", "mint", "worn once"], "excellent"),
        (["very good", "great condition", "lightly worn"], "very_good"),
        (["good", "pre-owned", "preowned"], "good"),
        (["gently used", "gently_used"], "gently_used"),
        (["used", "normal wear"], "used"),
        (["fair", "worn", "stained", "flaw"], "fair"),
        (["poor", "beater", "thrashed", "damaged"], "poor"),
    ]

    for keywords, tier in mappings:
        for kw in keywords:
            if kw in c:
                return tier
    return "good"  # Default assumption for archive fashion


def adjust_for_condition(
    comp_price: float,
    comp_condition: Optional[str],
    listing_condition: Optional[str],
    brand: str = "",
    category_sensitivity: float = 1.0,
) -> float:
    """
    Adjust a comp's price based on condition difference from listing.
    If comp is NWT and listing is used, adjust comp price down.
    """
    comp_cond = normalize_condition(comp_condition)
    list_cond = normalize_condition(listing_condition)

    if comp_cond is None or list_cond is None:
        return comp_price  # Can't adjust without both conditions

    comp_mult = CONDITION_MULTIPLIERS.get(comp_cond, 1.0)
    list_mult = CONDITION_MULTIPLIERS.get(list_cond, 1.0)

    if comp_mult == 0:
        return comp_price

    # Raw adjustment ratio
    ratio = list_mult / comp_mult

    # Apply brand sensitivity (dampens or amplifies the adjustment)
    brand_sens = BRAND_CONDITION_SENSITIVITY.get(brand.lower().strip(), 1.0)
    sensitivity = brand_sens * category_sensitivity

    # Blend toward 1.0 based on sensitivity (1.0 = full adjustment, 0.5 = half)
    adjusted_ratio = 1.0 + (ratio - 1.0) * sensitivity

    # Cap extreme adjustments
    adjusted_ratio = max(0.40, min(1.60, adjusted_ratio))

    return comp_price * adjusted_ratio


# ══════════════════════════════════════════════════════════════
# BUNDLE DETECTION (delegates to price_normalizer)
# ══════════════════════════════════════════════════════════════

BUNDLE_RE = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\blot\s+of\b",
        r"\bbundle\b",
        r"\bset\s+of\s+\d+\b",
        r"\b\d+\s*(?:pc|piece|item)s?\b",
        r"\b[2-9]x\b",
    ]
]


def is_bundle(title: str) -> bool:
    """Quick check if a listing title indicates a bundle/lot."""
    for pattern in BUNDLE_RE:
        if pattern.search(title):
            return True
    return False


# ══════════════════════════════════════════════════════════════
# NUMERIC CONFIDENCE SCORING
# ══════════════════════════════════════════════════════════════

def calculate_confidence_score(comps: List[ScoredComp]) -> float:
    """
    Calculate a numeric confidence score (0.0 - 1.0) for a comp set.

    Factors:
    - sample_size (25%): more comps = higher confidence
    - price_agreement (30%): low coefficient of variation = prices agree
    - recency (15%): recent comps are more reliable
    - similarity (20%): high-similarity comps = better match
    - platform_diversity (10%): cross-platform validation
    """
    if not comps:
        return 0.0

    prices = [c.price for c in comps if c.price > 0]
    if not prices:
        return 0.0

    n = len(prices)

    # Sample size: 0→0, 3→0.5, 8+→1.0
    f_sample = min(1.0, n / 8.0)

    # Price agreement: coefficient of variation (lower = better)
    import numpy as np
    mean_p = np.mean(prices)
    if mean_p > 0:
        cv = np.std(prices) / mean_p
        f_agreement = max(0.0, 1.0 - cv)
    else:
        f_agreement = 0.0

    # Recency: how many comps are from the last 60 days
    now = datetime.now(tz=None)
    recent = sum(1 for c in comps if c.sold_date and (now - c.sold_date).days < 60)
    dated = sum(1 for c in comps if c.sold_date is not None)
    if dated > 0:
        f_recency = min(1.0, recent / 3.0)
    else:
        f_recency = 0.3  # Unknown dates — moderate confidence

    # Similarity: average similarity of comps
    avg_sim = np.mean([c.similarity for c in comps])
    f_similarity = avg_sim

    # Platform diversity
    platforms = set(c.platform for c in comps if c.platform)
    f_diversity = min(1.0, len(platforms) / 2.0) if platforms else 0.3

    # Weighted combination
    score = (
        0.25 * f_sample
        + 0.30 * f_agreement
        + 0.15 * f_recency
        + 0.20 * f_similarity
        + 0.10 * f_diversity
    )

    return round(max(0.0, min(1.0, score)), 3)


# ══════════════════════════════════════════════════════════════
# IMPROVED OUTLIER REMOVAL
# ══════════════════════════════════════════════════════════════

def filter_outliers_mad(comps: List[ScoredComp]) -> List[ScoredComp]:
    """
    Remove outliers using Median Absolute Deviation (MAD).
    More robust than IQR for skewed distributions common in archive fashion.
    Falls back to IQR if MAD is too aggressive.
    """
    if len(comps) < 4:
        return comps

    import numpy as np

    prices = np.array([c.price for c in comps])
    median = np.median(prices)
    mad = np.median(np.abs(prices - median))

    if mad == 0:
        # All prices identical or nearly so — use IQR fallback
        return filter_outliers_iqr(comps)

    # Modified Z-score with MAD
    modified_z = 0.6745 * (prices - median) / mad
    threshold = 3.0

    filtered = [c for c, z in zip(comps, modified_z) if abs(z) < threshold]

    # If MAD was too aggressive (removed too many), fall back to IQR
    if len(filtered) < 3 and len(comps) >= 4:
        return filter_outliers_iqr(comps)

    return filtered if filtered else comps


def filter_outliers_iqr(comps: List[ScoredComp]) -> List[ScoredComp]:
    """Original IQR outlier removal — used as fallback."""
    if len(comps) < 4:
        return comps

    prices = sorted(c.price for c in comps)
    q1 = prices[len(prices) // 4]
    q3 = prices[3 * len(prices) // 4]
    iqr = q3 - q1

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    filtered = [c for c in comps if lower <= c.price <= upper]
    return filtered if filtered else comps


def weighted_median(
    scored_comps: List[ScoredComp],
    half_life_days: int = 45,
    use_normalized_price: bool = True,
) -> float:
    """
    Calculate similarity + time-decay weighted median price.
    Uses normalized_price when available, otherwise raw price.
    """
    if not scored_comps:
        return 0.0

    # Sort by price
    sorted_comps = sorted(scored_comps, key=lambda c: c.normalized_price if (use_normalized_price and c.normalized_price) else c.price)

    # Calculate combined weights: similarity × time_decay
    total_weight = 0.0
    weights = []
    for c in sorted_comps:
        decay = time_decay_weight(c.sold_date, half_life_days)
        w = c.similarity * decay
        weights.append(w)
        total_weight += w

    if total_weight == 0:
        return sorted_comps[len(sorted_comps) // 2].price

    cumulative = 0.0
    for comp, w in zip(sorted_comps, weights):
        cumulative += w
        if cumulative >= total_weight / 2:
            price = comp.normalized_price if (use_normalized_price and comp.normalized_price) else comp.price
            return price

    return sorted_comps[-1].price


def filter_outliers(comps: List[ScoredComp]) -> List[ScoredComp]:
    """Remove price outliers — now uses MAD (more robust), with IQR fallback."""
    return filter_outliers_mad(comps)

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
    listing_condition: Optional[str] = None,
    listing_size: Optional[str] = None,
    use_embeddings: bool = False,
    use_historical_db: bool = False,
) -> CompResult:
    """
    Find the best comparable sold items for pricing.

    Tries increasingly specific queries, scores results by similarity,
    applies normalization (platform fees, auction adjustment, condition,
    size, time decay), and returns a confidence-scored weighted price.

    New in Phase 3:
    - use_embeddings: Use sentence-transformer embeddings for hybrid similarity
    - use_historical_db: Also search the local historical comp database
    """
    try:
        from .grailed import GrailedScraper
    except ImportError:
        from scrapers.grailed import GrailedScraper

    try:
        from .price_normalizer import PriceNormalizer, is_bundle as check_bundle
    except ImportError:
        from scrapers.price_normalizer import PriceNormalizer, is_bundle as check_bundle

    try:
        from .size_normalizer import adjust_for_size
    except ImportError:
        from scrapers.size_normalizer import adjust_for_size

    # Embedding support (Phase 3)
    listing_embedding = None
    if use_embeddings:
        try:
            from .title_matcher import (
                get_title_embedding, hybrid_similarity as calc_hybrid,
                save_comp_with_embedding, search_comps_by_embedding,
                canonicalize_brand,
            )
            listing_embedding = get_title_embedding(title)
        except Exception as e:
            logger.warning(f"Embedding init failed, falling back to keyword matching: {e}")
            use_embeddings = False

    # Parse the title
    parsed = parse_title(brand, title)

    # Get category-specific config
    cat_config = get_category_config(parsed.item_type or parsed.item_type_specific)
    half_life = cat_config.get("time_decay_halflife", DEFAULT_HALFLIFE)
    cond_sensitivity = cat_config.get("condition_sensitivity", DEFAULT_CONDITION_SENSITIVITY)

    # Build search queries
    queries = build_search_queries(parsed)

    all_comps = []
    best_query = ""
    seen_ids = set()

    # ── Phase 3: Search historical DB first ──
    if use_historical_db and use_embeddings and listing_embedding is not None:
        try:
            historical = search_comps_by_embedding(
                listing_embedding, brand=brand, limit=30
            )
            for h in historical:
                if h.get("source_id") in seen_ids:
                    continue
                if not h.get("sold_price") or h["sold_price"] <= 0:
                    continue

                seen_ids.add(h.get("source_id", ""))
                sim = h.get("similarity", 0.5)

                # Parse sold_date
                sd = None
                if h.get("sold_date"):
                    try:
                        sd = datetime.fromisoformat(h["sold_date"])
                    except (ValueError, TypeError):
                        pass

                norm_price = h.get("normalized_price") or h["sold_price"]

                all_comps.append(ScoredComp(
                    title=h["title"],
                    price=h["sold_price"],
                    similarity=sim,
                    url=h.get("url", ""),
                    source_id=h.get("source_id", ""),
                    platform=h.get("platform", ""),
                    sold_date=sd,
                    condition=h.get("condition"),
                    size=h.get("size"),
                    is_auction=h.get("is_auction", False),
                    num_bids=h.get("num_bids"),
                    shipping_cost=h.get("shipping_cost"),
                    normalized_price=norm_price,
                ))

            if all_comps:
                best_query = "historical_db"
                logger.info(f"Found {len(all_comps)} historical comps for '{title[:50]}'")
        except Exception as e:
            logger.warning(f"Historical DB search failed: {e}")

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

                    # ── Bundle detection: skip bundles ──
                    if is_bundle(item.title) or check_bundle(item.title):
                        continue

                    seen_ids.add(item.source_id)

                    # Save to database for catalog building
                    if save_comps:
                        save_sold_comp_to_db(query, item, brand)

                    # Score similarity (keyword-based)
                    similarity = score_comp_similarity(parsed, item.title)

                    # Boost with embedding similarity if available
                    if use_embeddings and listing_embedding is not None:
                        try:
                            comp_embedding = get_title_embedding(item.title)
                            if comp_embedding is not None:
                                similarity = calc_hybrid(
                                    item.title, item.title,
                                    similarity,
                                    listing_embedding, comp_embedding,
                                )
                        except Exception:
                            pass  # Fall back to keyword-only

                    # Boost similarity by query quality
                    adjusted_similarity = similarity * 0.7 + query_quality * 0.3

                    # Extract platform from item source
                    platform = getattr(item, "source", "grailed")
                    sold_date = getattr(item, "listed_at", None)  # Best available date proxy
                    condition = getattr(item, "condition", None)
                    size = getattr(item, "size", None)
                    is_auction = getattr(item, "is_auction", False)
                    num_bids = getattr(item, "raw_data", {}).get("num_bids") if hasattr(item, "raw_data") else None
                    shipping = getattr(item, "shipping_cost", None)

                    # ── Normalize price ──
                    norm_price = item.price

                    # 1. Auction adjustment
                    norm_price = PriceNormalizer.auction_adjustment(
                        norm_price, is_auction, num_bids
                    )

                    # 2. Cross-platform fee normalization
                    norm_price = PriceNormalizer.normalize_price(
                        norm_price, shipping, platform
                    )

                    # 3. Condition adjustment
                    if listing_condition or condition:
                        norm_price = adjust_for_condition(
                            norm_price,
                            comp_condition=condition,
                            listing_condition=listing_condition,
                            brand=brand,
                            category_sensitivity=cond_sensitivity,
                        )

                    # 4. Size adjustment
                    if listing_size and size:
                        norm_price = adjust_for_size(
                            norm_price,
                            listing_size=listing_size,
                            comp_size=size,
                            item_type=parsed.item_type or parsed.item_type_specific,
                            brand=brand,
                        )

                    all_comps.append(ScoredComp(
                        title=item.title,
                        price=item.price,
                        similarity=adjusted_similarity,
                        url=item.url,
                        source_id=item.source_id,
                        platform=platform,
                        sold_date=sold_date,
                        condition=condition,
                        size=size,
                        is_auction=is_auction,
                        num_bids=num_bids,
                        shipping_cost=shipping,
                        normalized_price=norm_price,
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
            confidence_score=0.0,
            query_used="",
        )

    # ── Filter outliers (using MAD with IQR fallback) ──
    filtered = filter_outliers(all_comps)
    if not filtered:
        filtered = all_comps

    # Sort by similarity (best matches first)
    filtered.sort(key=lambda c: -c.similarity)

    # ── Calculate prices with time-decay weighting ──
    w_median = weighted_median(filtered, half_life_days=half_life, use_normalized_price=True)

    prices = sorted(c.normalized_price or c.price for c in filtered)
    simple_med = prices[len(prices) // 2]

    high_quality = [c for c in filtered if c.similarity >= 0.5]

    # ── Confidence: both string (backward compat) and numeric ──
    confidence_score = calculate_confidence_score(filtered)

    if confidence_score >= 0.65:
        confidence = "high"
    elif confidence_score >= 0.40:
        confidence = "medium"
    elif confidence_score >= 0.20:
        confidence = "low"
    else:
        confidence = "very_low"

    # Extract season data from top comps
    exact_season = None
    exact_year = None
    season_confidence = "unknown"

    try:
        from .seasons import aggregate_seasons_from_comps
    except ImportError:
        from scrapers.seasons import aggregate_seasons_from_comps

    if filtered:
        comp_titles = [c.title for c in filtered[:10]]
        exact_season, exact_year, season_confidence = aggregate_seasons_from_comps(comp_titles)

    return CompResult(
        weighted_price=w_median,
        simple_median=simple_med,
        comps_count=len(filtered),
        high_quality_count=len(high_quality),
        confidence=confidence,
        confidence_score=confidence_score,
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
