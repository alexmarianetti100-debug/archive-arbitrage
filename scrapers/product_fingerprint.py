"""
Product Fingerprinting — Exact Product Identification

Converts messy listing titles into canonical product fingerprints.

Example:
  "Rick Owens DRKSHDW Black Geobasket Sneakers Size 42"
  → ProductFingerprint(
      brand="rick owens",
      sub_brand="drkshdw",
      model="geobasket",
      item_type="sneakers",
      material="",
      color="black",
      canonical_name="Rick Owens DRKSHDW Geobasket Sneaker"
    )
"""

import re
from typing import Optional, List, Tuple, Dict, Set
from dataclasses import dataclass, field
from collections import defaultdict
import hashlib


# === BRAND HIERARCHY ===
SUB_BRANDS = {
    "rick owens": ["drkshdw", "lilies", "mainline", "champion", "converse", "birkenstock", "moncler"],
    "comme des garcons": ["homme plus", "homme", "shirt", "play", "black", "tao", "junya", "parfum", "guerrilla store"],
    "raf simons": ["redux", "sterling ruby", "fred perry", "adidas", "calvin klein", "eastpak"],
    "maison margiela": ["artisanal", "line 0", "replica", "mm6", "couture"],
    "yohji yamamoto": ["pour homme", "y's", "costume d'homme", "noir", "ground y", "new era"],
    "undercover": ["undercoverism", "supreme", "nike", "valentino", "fragment"],
    "issey miyake": ["homme plisse", "homme plissé", "pleats please", "bao bao", "plantation", "men"],
    "dior": ["homme", "men", "lady", "saddle", "book tote", "b23"],
    "saint laurent": ["paris", "rive gauche", "surf sound"],
    "prada": ["sport", "linea rossa", "re-nylon"],
    "balenciaga": [],  # triple s, track, speed, defender are MODELS not sub-brands
    "supreme": ["nike", "north face", "louis vuitton", "comme des garcons", "stone island"],
    "helmut lang": ["vintage", "re-edition", "j crew"],
    "number (n)ine": ["the high streets", "touch me i'm sick", "collage", "michelangelo"],
}

# === ITEM TYPE HIERARCHY ===
# ORDER MATTERS — more specific categories MUST come before generic ones.
# "trucker hat" must match "hats" before "trucker" matches "outerwear".
# "chain bracelet" must match "bracelets" before "chain" matches "necklaces".
# We use OrderedDict semantics (Python 3.7+ dicts preserve insertion order).
# Item type keywords — imported from canonical taxonomy
from core.categories import ITEM_TYPES

# === MODEL DATABASE ===
# Specific product models that define exact products
MODELS = {
    # Rick Owens — footwear models (NOT season names)
    "geobasket": ["rick owens", "drkshdw"],
    "ramones": ["rick owens", "drkshdw"],
    "kiss boot": ["rick owens"],
    "creatch": ["rick owens", "drkshdw"],
    "mega lace": ["rick owens"],
    "larry": ["rick owens"],
    # Rick Owens — clothing models (actual product names, not seasons)
    "stooges": ["rick owens"],  # Stooges leather jacket — specific product
    "bela": ["rick owens"],     # Bela pants/shorts — specific product line
    "pods": ["rick owens", "drkshdw"],
    "hustler": ["rick owens"],
    "bauhaus": ["rick owens"],  # Bauhaus cargo — specific product
    # NOTE: dust, babel, sphinx, cyclops, memphis, intarsia are SEASONS not models.
    # "Rick Owens Babel Ramones" → model=ramones, season=babel (not model=babel)

    # Chrome Hearts
    "forever ring": ["chrome hearts"],
    "keeper ring": ["chrome hearts"],
    "fuck you ring": ["chrome hearts"],
    "plus ring": ["chrome hearts"],
    "scroll ring": ["chrome hearts"],
    "fleur de lis": ["chrome hearts"],
    "cemetery cross": ["chrome hearts"],
    "dagger pendant": ["chrome hearts"],
    "cross ball": ["chrome hearts"],
    "filigree cross": ["chrome hearts"],
    "baby fat": ["chrome hearts"],
    "spacer": ["chrome hearts"],
    "paper chain": ["chrome hearts"],
    "tiny e": ["chrome hearts"],
    "cross pendant": ["chrome hearts"],

    # Raf Simons — specific sub-models BEFORE generic
    "runner cylon": ["raf simons", "adidas"],
    "runner orion": ["raf simons", "adidas"],
    "runner response": ["raf simons", "adidas"],
    "ozweego 2": ["raf simons", "adidas"],
    "ozweego 3": ["raf simons", "adidas"],
    "ozweego": ["raf simons", "adidas"],  # Generic — after versioned ones
    "response trail": ["raf simons", "adidas"],
    "cylon": ["raf simons", "adidas"],
    "replicant": ["raf simons"],
    "orion": ["raf simons"],
    "virginia creeper": ["raf simons"],
    # NOTE: generic "runner" removed — too broad, groups different shoes.
    # Use specific sub-models above instead.

    # Margiela
    "tabi": ["maison margiela", "mm6"],
    "replica": ["maison margiela"],
    "gat": ["maison margiela"],
    "german army": ["maison margiela"],
    "fusion": ["maison margiela"],

    # Undercover
    "scab": ["undercover"],
    "but": ["undercover"],
    "cindy sherman": ["undercover"],

    # Number (N)ine
    "touch me i'm sick": ["number (n)ine"],
    "the high streets": ["number (n)ine"],
    "collage": ["number (n)ine"],

    # Dior — "christian dior" removed (it's a brand variant, not a model)
    "clawmark": ["dior"],
    "jake": ["dior"],
    "saddle": ["dior"],
    "b23": ["dior"],

    # Balenciaga
    "triple s": ["balenciaga"],
    "speed": ["balenciaga"],
    "defender": ["balenciaga"],
    "le city": ["balenciaga"],
    "hourglass": ["balenciaga"],
    "le cagole": ["balenciaga"],
    "arena": ["balenciaga"],
    # NOTE: "track" removed from models — too ambiguous (matches track jackets/pants).
    # "Track" sneaker is handled by detect_track_sneaker() below.

    # Gucci
    "marmont": ["gucci"],
    "dionysus": ["gucci"],
    "jackie": ["gucci"],
    "bamboo": ["gucci"],
    "ophidia": ["gucci"],
    "horsebit": ["gucci"],
    "jordaan": ["gucci"],
    "ace": ["gucci"],
    "rhyton": ["gucci"],

    # Louis Vuitton
    "keepall": ["louis vuitton"],
    "neverfull": ["louis vuitton"],
    "speedy": ["louis vuitton"],
    "alma": ["louis vuitton"],
    "murakami": ["louis vuitton"],

    # Chanel
    "classic flap": ["chanel"],
    "boy bag": ["chanel"],
    "2.55": ["chanel"],
    "timeless": ["chanel"],

    # Bottega Veneta
    "cassette": ["bottega veneta"],
    "padded cassette": ["bottega veneta"],
    "intrecciato": ["bottega veneta"],
    "pouch": ["bottega veneta"],
    
    # Nike/Adidas models
    "air force 1": ["nike", "supreme", "off-white"],
    "air jordan": ["nike", "supreme", "off-white", "travis scott"],
    "dunk": ["nike", "supreme", "off-white", "travis scott"],
    "blazer": ["nike", "off-white", "sacai"],
    "foamposite": ["nike", "supreme"],
    "yeezy": ["adidas"],
}

# === MATERIAL KEYWORDS ===
MATERIALS = [
    "leather", "suede", "cashmere", "silk", "wool", "linen", "denim", "corduroy",
    "nylon", "gore-tex", "goretex", "canvas", "velvet", "shearling", "fur",
    "rubber", "mesh", "knit", "waxed", "coated", "distressed", "raw", "nubuck",
    "patent leather", "lambskin", "calfskin", "crocodile", "alligator", "python",
]

# === COLOR NORMALIZATION ===
COLORS = [
    "black", "white", "grey", "gray", "navy", "brown", "tan", "cream",
    "red", "blue", "green", "pink", "purple", "orange", "yellow", "beige",
    "olive", "burgundy", "maroon", "charcoal", "ivory", "camel", "khaki",
    "silver", "gold", "bronze", "clear", "transparent", "multicolor", "tie dye",
]

# === NOISE WORDS ===
NOISE_WORDS = {
    "new", "nwt", "bnwt", "nib", "brand", "authentic", "genuine", "rare", "vintage",
    "amazing", "beautiful", "perfect", "condition", "excellent", "great", "good",
    "pre-owned", "preowned", "pre", "owned", "used", "worn", "mint", "deadstock", "ds",
    "see", "photos", "description", "details", "check", "look", "pic", "pics",
    "size", "sz", "fits", "like", "fit", "true", "sized",
    "free", "shipping", "ship", "fast", "quick",
    "mens", "men's", "womens", "women's", "unisex", "women", "men",
    "the", "a", "an", "and", "or", "of", "in", "on", "for", "to", "with", "from",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "this", "that", "these", "those", "it", "its",
}


@dataclass
class ProductFingerprint:
    """Canonical product identity extracted from a listing."""
    brand: str
    sub_brand: str = ""
    model: str = ""
    item_type: str = ""  # e.g., "sneakers", "jacket"
    material: str = ""
    color: str = ""
    season: str = ""     # e.g., "FW05", "SS18"
    year: Optional[int] = None
    
    # Derived fields
    canonical_name: str = ""  # Human-readable canonical name
    fingerprint_hash: str = ""  # Unique hash for this product
    confidence: str = "medium"  # high/medium/low based on data quality
    
    def __post_init__(self):
        if not self.canonical_name:
            self.canonical_name = self._build_canonical_name()
        if not self.fingerprint_hash:
            self.fingerprint_hash = self._compute_hash()
    
    def _build_canonical_name(self) -> str:
        """Build human-readable canonical product name."""
        parts = []
        
        # Brand with sub-brand
        if self.sub_brand:
            parts.append(f"{self.brand.title()} {self.sub_brand.upper()}")
        else:
            parts.append(self.brand.title())
        
        # Model (most specific identifier)
        if self.model:
            parts.append(self.model.title())
        
        # Material
        if self.material:
            parts.append(self.material.title())
        
        # Item type
        if self.item_type:
            parts.append(self.item_type.title())
        
        # Color
        if self.color:
            parts.append(f"({self.color.title()})")
        
        return " | ".join(parts)
    
    def _compute_hash(self) -> str:
        """Compute unique hash from fingerprint components.

        Color IS part of the identity — a black Geobasket and a milk Geobasket
        are different products with different market prices.
        """
        key_parts = [
            self.brand.lower().replace(" ", "_"),
            self.sub_brand.lower().replace(" ", "_") if self.sub_brand else "mainline",
            self.model.lower().replace(" ", "_") if self.model else "",
            self.item_type.lower().replace(" ", "_") if self.item_type else "",
            self.material.lower().replace(" ", "_") if self.material else "any",
            self.color.lower().replace(" ", "_") if self.color else "any",
        ]
        key = "|".join(key_parts)
        return hashlib.md5(key.encode()).hexdigest()[:16]
    
    def to_search_query(self) -> str:
        """Generate optimal search query for finding this product."""
        parts = [self.brand]
        if self.model:
            parts.append(self.model)
        elif self.sub_brand:
            parts.append(self.sub_brand)
        if self.item_type:
            parts.append(self.item_type)
        return " ".join(parts)
    
    def is_complete(self) -> bool:
        """Check if this fingerprint has enough data to be useful."""
        return bool(self.brand and (self.model or self.item_type))
    


# Sub-type patterns for splitting over-grouped models
_TABI_SUBTYPES = ["western boot", "ankle boot", "mary jane", "loafer", "derby", "flat", "slipper"]
_BELA_SUBTYPES = ["cargo", "track"]
_PODS_SUBTYPES = ["short", "shorts"]
_RAMONES_SUBTYPES = ["high", "hi", "high top", "hightop", "low"]
_GAT_SUBTYPES = ["high", "hi", "high top", "hightop", "low"]

# Model aliases — normalize spelling variants to canonical model names
MODEL_ALIASES = {
    "geo basket": "geobasket",
    "geo baskets": "geobasket",
    "geobaskets": "geobasket",
    "ramone": "ramones",
    "ramone hi": "ramones high",
    "ramones hi": "ramones high",
    "ramones high top": "ramones high",
    "ramones hightop": "ramones high",
    "tabi boot": "tabi",
    "tabi boots": "tabi",
    "triple-s": "triple s",
    "ozweego 2s": "ozweego 2",
    "ozweego ii": "ozweego 2",
    "ozweego 3s": "ozweego 3",
    "ozweego iii": "ozweego 3",
}

# Brand name strings that should NOT be extracted as models
_BRAND_NAME_STRINGS = {
    "christian dior", "dior homme", "dior men", "yves saint laurent",
    "maison martin margiela", "comme des garcons",
}


def _detect_subtype(title_lower: str, subtypes: list) -> str:
    """Find the most specific sub-type match in a title."""
    # Sort longest first so "high top" matches before "high"
    for st in sorted(subtypes, key=len, reverse=True):
        if st in title_lower:
            return st
    return ""


def parse_title_to_fingerprint(brand: str, title: str) -> ProductFingerprint:
    """
    Extract a product fingerprint from a listing title.

    This is the core function for exact product identification.
    """
    title_lower = title.lower()
    brand = brand.lower().strip()

    # Detect sub-brand
    sub_brand = ""
    brand_subs = SUB_BRANDS.get(brand, [])
    for sub in brand_subs:
        if sub.lower() in title_lower:
            sub_brand = sub
            break

    # Detect item type BEFORE model (needed for gating "track" to footwear)
    item_type = ""
    for category, keywords in ITEM_TYPES.items():
        for kw in sorted(keywords, key=len, reverse=True):
            if kw in title_lower:
                item_type = category
                break
        if item_type:
            break

    # Detect model (most specific identifier)
    # Sort by length descending so "runner cylon" matches before "cylon"
    # Skip models that equal the sub_brand (e.g., "replica" for Margiela)
    # Skip brand name strings (e.g., "christian dior" is NOT a model)
    model = ""
    sorted_models = sorted(MODELS.items(), key=lambda x: len(x[0]), reverse=True)
    for model_name, model_brands in sorted_models:
        if brand in [b.lower() for b in model_brands]:
            mn_lower = model_name.lower()
            if mn_lower in title_lower:
                if mn_lower == sub_brand.lower():
                    continue  # Skip — it's the sub_brand, keep looking
                if mn_lower in _BRAND_NAME_STRINGS:
                    continue  # Skip — it's a brand variant, not a product model
                model = model_name
                break

    # Check model aliases (normalize spelling variants)
    if not model:
        for alias, canonical in sorted(MODEL_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
            if alias in title_lower:
                # Verify the canonical model is valid for this brand
                if canonical in MODELS and brand in [b.lower() for b in MODELS[canonical]]:
                    model = canonical
                    break

    # Special case: Balenciaga "Track" — only a model for footwear
    if brand == "balenciaga" and not model and "track" in title_lower:
        footwear_types = {"footwear", "sneakers", "shoes", "boots"}
        if item_type in footwear_types or any(kw in title_lower for kw in ["sneaker", "shoe", "trainer"]):
            model = "track"

    # Detect material
    material = ""
    for mat in MATERIALS:
        if mat in title_lower:
            material = mat
            break

    # Detect color
    color = ""
    for col in COLORS:
        if re.search(rf'\b{col}\b', title_lower):
            color = col
            break

    # Detect season/year
    season = ""
    year = None
    season_match = re.search(r'((?:ss|aw|fw|spring|fall|autumn|winter)[/\s.-]?(\d{2,4}))', title_lower)
    if season_match:
        season = season_match.group(1).strip()
        year_str = season_match.group(2)
        if year_str:
            year_int = int(year_str)
            if year_int < 50:
                year = 2000 + year_int
            elif year_int < 100:
                year = 1900 + year_int
            else:
                year = year_int

    # ── Sub-type splitting for over-grouped models ──
    # Appends sub-type to model so different variants get different fingerprints
    if model == "tabi":
        st = _detect_subtype(title_lower, _TABI_SUBTYPES)
        if st:
            # Normalize: "ankle boot" → "boot", "western boot" → "western boot"
            model = "tabi " + st
    elif model == "bela":
        st = _detect_subtype(title_lower, _BELA_SUBTYPES)
        if st:
            model = "bela " + st
        elif "short" in title_lower or "shorts" in title_lower:
            model = "bela shorts"
    elif model == "pods":
        if "short" in title_lower or "shorts" in title_lower:
            model = "pods shorts"
        else:
            model = "pods pants"
    elif model == "ramones":
        st = _detect_subtype(title_lower, _RAMONES_SUBTYPES)
        if st in ("high", "hi", "high top", "hightop"):
            model = "ramones high"
        elif st == "low":
            model = "ramones low"
    elif model == "gat":
        st = _detect_subtype(title_lower, _GAT_SUBTYPES)
        if st in ("high", "hi", "high top", "hightop"):
            model = "gat high"
        elif st == "low":
            model = "gat low"
    elif model == "dagger pendant":
        if "double" in title_lower:
            model = "double dagger pendant"
        elif "heart" in title_lower:
            model = "heart dagger pendant"
        elif "large" in title_lower:
            model = "large dagger pendant"
    elif model == "baby fat":
        if "diamond" in title_lower or "pave" in title_lower or "pavé" in title_lower:
            model = "baby fat diamond"

    # Determine confidence
    confidence = "low"
    if model:
        confidence = "high"
    elif item_type and sub_brand:
        confidence = "medium"
    elif item_type:
        confidence = "low"

    return ProductFingerprint(
        brand=brand,
        sub_brand=sub_brand,
        model=model,
        item_type=item_type,
        material=material,
        color=color,
        season=season,
        year=year,
        confidence=confidence,
    )


def cluster_titles_to_products(titles: List[Tuple[str, str, float]]) -> Dict[str, List[Tuple[str, str, float]]]:
    """
    Cluster listing titles into product groups.
    
    Args:
        titles: List of (brand, title, price) tuples from sold comps
        
    Returns:
        Dict mapping fingerprint_hash → list of matching (brand, title, price)
    """
    clusters: Dict[str, List[Tuple[str, str, float]]] = defaultdict(list)
    
    for brand, title, price in titles:
        fp = parse_title_to_fingerprint(brand, title)
        if fp.is_complete():
            clusters[fp.fingerprint_hash].append((brand, title, price))
    
    return dict(clusters)


def generate_canonical_products(clusters: Dict[str, List[Tuple[str, str, float]]], 
                                 min_samples: int = 3) -> List[Dict]:
    """
    Generate canonical product records from clusters.
    
    Only keep products with enough samples to have reliable pricing.
    """
    products = []
    
    for fp_hash, listings in clusters.items():
        if len(listings) < min_samples:
            continue
        
        # Parse first listing to get fingerprint
        brand, title, _ = listings[0]
        fp = parse_title_to_fingerprint(brand, title)
        
        # Calculate price stats
        prices = [p for _, _, p in listings]
        prices.sort()
        
        products.append({
            "fingerprint_hash": fp_hash,
            "canonical_name": fp.canonical_name,
            "brand": fp.brand,
            "sub_brand": fp.sub_brand,
            "model": fp.model,
            "item_type": fp.item_type,
            "material": fp.material,
            "sample_count": len(listings),
            "min_price": prices[0],
            "max_price": prices[-1],
            "median_price": prices[len(prices) // 2],
            "avg_price": sum(prices) / len(prices),
            "price_std": (sum((p - sum(prices)/len(prices))**2 for p in prices) / len(prices)) ** 0.5,
        })
    
    # Sort by sample count (most reliable first)
    products.sort(key=lambda p: -p["sample_count"])
    return products


if __name__ == "__main__":
    # Test examples
    test_titles = [
        ("rick owens", "Rick Owens DRKSHDW Black Geobasket Sneakers Size 42", 650),
        ("rick owens", "Rick Owens Drkshdw Geobasket Leather Sneaker Black", 680),
        ("rick owens", "Rick Owens Mainline Black Leather Geobasket High Top", 1200),
        ("rick owens", "Rick Owens DRKSHDW White Ramones Sneakers", 450),
        ("rick owens", "Rick Owens Mainline Ramones High Top", 550),
        ("maison margiela", "Maison Margiela Tabi Boots Black Leather", 850),
        ("maison margiela", "Maison Margiela Tabi Ankle Boot Black", 820),
        ("maison margiela", "Margiela White Tabi Sneakers", 600),
    ]
    
    print("=== Product Fingerprinting Test ===\n")
    
    for brand, title, price in test_titles:
        fp = parse_title_to_fingerprint(brand, title)
        print(f"Title: {title}")
        print(f"  Brand: {fp.brand} | Sub: {fp.sub_brand} | Model: {fp.model} | Type: {fp.item_type}")
        print(f"  Canonical: {fp.canonical_name}")
        print(f"  Hash: {fp.fingerprint_hash}")
        print(f"  Confidence: {fp.confidence}")
        print()
    
    print("\n=== Clustering Test ===\n")
    clusters = cluster_titles_to_products(test_titles)
    products = generate_canonical_products(clusters, min_samples=2)
    
    for p in products:
        print(f"Product: {p['canonical_name']}")
        print(f"  Samples: {p['sample_count']} | Median: ${p['median_price']:.0f}")
        print(f"  Range: ${p['min_price']:.0f} - ${p['max_price']:.0f}")
        print()
