"""
Canonical item category taxonomy — single source of truth.

Used by comp_matcher, comp_validator, product_fingerprint, and gap_hunter
for consistent category classification across the pipeline.

Two levels:
- ITEM_TYPES: fine-grained (rings, sneakers, jacket) — used for matching and fingerprinting
- BROAD_CATEGORIES: coarse (jewelry, footwear, outerwear) — used for validation and eBay uplift

Each fine-grained type maps to exactly one broad category via CATEGORY_MAP.
"""

# Fine-grained item types with keyword lists (longest match first wins).
# Order matters: jewelry/accessories checked first (most specific), clothing last (most generic).
ITEM_TYPES: dict[str, list[str]] = {
    # Jewelry — check FIRST (most specific, easily confused with accessories)
    "rings": ["ring", "band", "signet", "signet ring", "pinky ring", "spinner ring",
              "forever ring", "cross ring", "scroll ring", "keeper ring"],
    "bracelets": ["bracelet", "cuff", "bangle", "chain bracelet", "paper chain bracelet",
                  "rollercoaster bracelet", "id bracelet"],
    "necklaces": ["necklace", "pendant", "choker", "paper chain", "cross pendant",
                  "baby fat", "dagger pendant", "dog tag", "chain"],
    "earrings": ["earring", "earrings", "stud", "hoop", "drop earring", "huggie"],
    # Accessories
    "eyewear": ["sunglasses", "glasses", "frames", "optical", "eyewear", "aviator"],
    "hats": ["trucker hat", "trucker cap", "bucket hat", "snapback", "beanie", "hat", "cap"],
    "belts": ["belt", "leather belt", "studded belt"],
    "wallets": ["wallet", "card holder", "card case", "coin purse", "zip wallet",
                "bifold", "trifold", "long wallet", "continental wallet"],
    "scarves": ["scarf", "shawl", "stole", "bandana"],
    # Bags — before clothing (clutch/pouch could overlap)
    "bags": ["bag", "handbag", "purse", "tote", "clutch", "shoulder bag", "crossbody",
             "satchel", "backpack", "duffle", "keepall", "weekender", "pouch",
             "briefcase", "messenger bag", "belt bag", "bum bag", "fanny pack"],
    # Footwear — before clothing (boots/shoes overlap with outerwear keywords)
    "boots": ["boots", "boot", "combat boots", "chelsea", "side zip", "lace up"],
    "sneakers": ["sneakers", "runners", "trainers", "high top", "low top", "shoes"],
    "loafers": ["loafers", "derbies", "oxford shoes", "slip on", "mules"],
    "sandals": ["slides", "sandals"],
    # Clothing — check LAST (most generic keywords)
    "jacket": ["leather jacket", "denim jacket", "trucker jacket", "jacket", "blazer", "coat",
               "bomber", "parka", "varsity", "windbreaker", "anorak", "overshirt", "harrington", "trench"],
    "hoodie": ["hoodie", "hooded", "sweatshirt", "pullover", "zip up", "zip-up"],
    "sweater": ["sweater", "knit", "cardigan", "jumper", "crewneck", "crew neck", "turtleneck", "mohair", "cable knit"],
    "shirt": ["shirt", "button up", "button down", "flannel", "camp collar", "hawaiian", "oxford", "dress shirt"],
    "tee": ["t-shirt", "tee", "tshirt", "t shirt"],
    "pants": ["pants", "trousers", "jeans", "denim", "cargo", "jogger", "sweatpants", "track pants",
              "chinos", "slacks", "cargos", "wide leg", "flare"],
    "shorts": ["shorts", "short", "swim trunks"],
}

# Map fine-grained types → broad categories (used by comp_validator, eBay uplift)
CATEGORY_MAP: dict[str, str] = {
    # Jewelry
    "rings": "jewelry",
    "bracelets": "jewelry",
    "necklaces": "jewelry",
    "earrings": "jewelry",
    # Accessories
    "eyewear": "accessories",
    "hats": "accessories",
    "belts": "accessories",
    "wallets": "accessories",
    "scarves": "accessories",
    # Bags
    "bags": "bags",
    # Footwear
    "boots": "footwear",
    "sneakers": "footwear",
    "loafers": "footwear",
    "sandals": "footwear",
    # Outerwear
    "jacket": "outerwear",
    # Tops
    "hoodie": "tops",
    "sweater": "tops",
    "shirt": "tops",
    "tee": "tops",
    # Bottoms
    "pants": "bottoms",
    "shorts": "bottoms",
}

# Broad categories (derived from CATEGORY_MAP values)
BROAD_CATEGORIES: set[str] = set(CATEGORY_MAP.values())


def detect_item_type(title: str) -> str:
    """Detect fine-grained item type from title. Returns empty string if undetectable."""
    title_lower = title.lower()
    best_type = ""
    best_kw = ""
    for category, keywords in ITEM_TYPES.items():
        for kw in sorted(keywords, key=len, reverse=True):
            if kw in title_lower:
                if not best_kw or len(kw) > len(best_kw):
                    best_type = category
                    best_kw = kw
    return best_type


def detect_broad_category(title: str) -> str:
    """Detect broad category from title. Returns empty string if undetectable."""
    item_type = detect_item_type(title)
    return CATEGORY_MAP.get(item_type, "")


def get_broad_category(item_type: str) -> str:
    """Map a fine-grained item type to its broad category."""
    return CATEGORY_MAP.get(item_type, "")
