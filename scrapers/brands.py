"""
Archive fashion brands and keywords for filtering.
Brand detection list + optimized search queries based on March 2026 telemetry audit.

Architecture:
- ARCHIVE_BRANDS: Brand detection (substring matching in item titles)
- SEARCH_QUERIES: Optimized Grailed search queries (broad + piece-specific)
- PRIORITY_BRANDS: Top search queries run most frequently
"""

# ── Brand detection list ─────────────────────────────────────────────────────
# Used by detect_brand() across the codebase for substring matching in titles.
# Contains canonical brand names only — NOT search queries.
# Longer entries before shorter ones within a brand group to prevent partials.
ARCHIVE_BRANDS = [
    # === TIER 1: KEEP BROAD — proven arbitrage gap ===
    "enfants riches deprimes",
    "erd",
    "bottega veneta",
    "chrome hearts",
    "saint laurent",
    "maison margiela",
    "martin margiela",
    "margiela",
    "rick owens",
    "drkshdw",
    "dior homme",
    "dior",
    "jean paul gaultier",
    "gaultier",
    "helmut lang",
    "raf simons",
    "carol christian poell",
    "ccp",

    # === TIER 2: PIECE-SPECIFIC ONLY — detected but searched specifically ===
    "balenciaga",
    "kapital",
    "number (n)ine",
    "number nine",
    "julius",
    "undercover",
    "undercoverism",
    "thierry mugler",
    "mugler",
    "alexander mcqueen",
    "mcqueen",
    "prada",
    "vivienne westwood",
    "ann demeulemeester",
    "yohji yamamoto",
    "vetements",
    "dries van noten",
    "gucci",
    "louis vuitton",
    "guidi",

    # === BRANDS KEPT FOR DETECTION (in tier_rules, may appear in results) ===
    "takahiromiyashita thesoloist",
    "soloist",
    "acne studios",
    "lemaire",
    "simone rocha",
    "brunello cucinelli",
    "haider ackermann",
    "chanel",
    "hermes",
    "burberry",
]

# ── Search queries ───────────────────────────────────────────────────────────
# Optimized Grailed search queries based on telemetry audit (March 2026).
# Tier 1 brands: broad queries. Tier 2 brands: piece-specific only.
# Removed 23 dead brands (0 deals across 500+ runs combined).
SEARCH_QUERIES = [
    # ── TIER 1: BROAD BRAND QUERIES (proven deal flow) ──────────────────────

    # Enfants Riches Deprimes (4.00 ratio, 98% gap — BEST in system)
    "enfants riches deprimes",
    "erd",
    "enfants riches deprimes subhumans leather jacket",
    "enfants riches deprimes bathroom stall tee",
    "enfants riches deprimes high risk hoodie",

    # Bottega Veneta (3.12 ratio, 96% gap)
    "bottega veneta",
    "bottega veneta puddle boots",
    "bottega veneta lug boots",
    "bottega veneta tire boots",
    "bottega veneta cassette bag",
    "bottega veneta intrecciato",
    "bottega veneta leather jacket",
    "bottega veneta padded",

    # Chrome Hearts (1.71 ratio, 97% gap)
    "chrome hearts",
    "chrome hearts ch cross pendant",
    "chrome hearts roll chain necklace",
    "chrome hearts wallet",
    "chrome hearts cross patch trucker jacket",

    # Saint Laurent (1.70 ratio, 81% gap)
    "saint laurent",
    "saint laurent wyatt boots",
    "saint laurent teddy jacket",
    "saint laurent leather jacket",
    "saint laurent l01",
    "saint laurent court classic",
    "saint laurent sac de jour",
    "saint laurent hedi slimane",

    # Maison Margiela (1.31 ratio, 96% gap)
    # Split: mainline Maison vs MM6 diffusion — MM6 is 40-60% cheaper
    "maison margiela",
    "maison margiela artisanal",
    "margiela tabi",
    "margiela gat",
    "margiela replica sneaker",
    # MM6 is separate — diffusion line, lower price points
    "mm6 margiela",

    # Rick Owens (1.16 ratio, 90% gap — killed geobasket 1/276, ramones 0/61)
    "rick owens",
    "drkshdw",
    "rick owens dunks",

    # Dior (0.83 ratio, 89% gap)
    # Split: Homme (menswear archive) vs Women's/mainline accessories
    "dior homme",
    "dior homme hedi slimane",
    "dior homme kris van assche",
    "dior men kim jones",
    "dior b23",
    "dior saddle bag",
    "dior oblique",

    # Jean Paul Gaultier (0.82 ratio, 97% gap)
    "jean paul gaultier",
    "gaultier",
    "jean paul gaultier soleil",
    "jean paul gaultier mesh",

    # Helmut Lang (0.75 ratio, 89% gap)
    "helmut lang",
    "helmut lang astro biker",
    "helmut lang bondage",
    "helmut lang leather jacket",
    "helmut lang painter jeans",
    "helmut lang archive",
    "helmut lang reflective",

    # Raf Simons (0.61 ratio, 94% gap — killed ozweego 0/61)
    "raf simons",

    # Carol Christian Poell (chronic mispricing, ultra-niche)
    "carol christian poell",
    "ccp",

    # ── TIER 2: PIECE-SPECIFIC ONLY (broad returns noise) ───────────────────

    # Balenciaga — broad dead (0/14), piece-specific proven
    "balenciaga runner",
    "balenciaga skater baggy sweatpants",
    "balenciaga lamborghini hoodie",
    "balenciaga lost tape flared",
    "balenciaga political campaign",
    "balenciaga hummer boots",
    "balenciaga leather jacket",
    "balenciaga bomber jacket",

    # Kapital — boro is the play (2.33 ratio)
    "kapital boro jacket",
    "kapital century denim",
    "kapital smiley boro",
    "kapital kountry patchwork",

    # Number Nine — piece-specific to avoid title noise (broad 0.04 ratio)
    "number nine leather jacket",
    "number nine mohair",
    "number nine hoodie",
    "number nine skull",

    # Julius — leather jacket (43%) + boots
    "julius leather jacket",
    "julius boots",

    # Undercover — collection-specific (arts & crafts 54%)
    "undercover arts and crafts",
    "undercover bug denim",
    "undercover witches",
    "undercover nike",
    "undercover parka",

    # Thierry Mugler — leather only (67%)
    "thierry mugler leather jacket",
    "mugler vintage",
    "mugler bodysuit",

    # Alexander McQueen — leather jacket (15%) + skull ring
    "alexander mcqueen leather jacket",
    "alexander mcqueen skull ring",

    # Prada — America's Cup (proven) + velvet blouson (75%)
    "prada america's cup sneakers",
    "prada cotton velvet blouson",
    "prada chocolate loafers",

    # Vivienne Westwood — jewelry/corset only (clothing = 0 deals)
    "vivienne westwood orb necklace",
    "vivienne westwood armor ring",
    "vivienne westwood corset",

    # Ann Demeulemeester — leather focus (boots 67%)
    "ann demeulemeester leather boots",
    "ann demeulemeester leather jacket",
    "ann demeulemeester backlace boots",

    # Yohji Yamamoto — targeted (gabardine 1/53 was terrible)
    "yohji yamamoto pour homme coat",
    "yohji yamamoto pour homme blazer",

    # Vetements — fully rewritten (old queries 0/50, wrong pieces)
    "vetements polizei hoodie",
    "vetements total darkness hoodie",
    "vetements dhl tee",
    "vetements metal logo hoodie",

    # Dries Van Noten — post-retirement appreciation opportunity
    "dries van noten embroidered jacket",
    "dries van noten velvet",
    "dries van noten floral jacket",

    # Gucci — Tom Ford era only (current = efficient pricing)
    "tom ford gucci",

    # Louis Vuitton — Murakami collab only (strict auth gate)
    "louis vuitton murakami",

    # Guidi — niche leather, small but dedicated market
    "guidi boots",
]

# Keywords that indicate archive/vintage pieces
ARCHIVE_KEYWORDS = [
    "archive",
    "vintage",
    "rare",
    "grail",
    "ss98", "aw98", "ss99", "aw99",
    "ss00", "aw00", "ss01", "aw01",
    "ss02", "aw02", "ss03", "aw03",
    "ss04", "aw04", "ss05", "aw05",
    "ss06", "aw06", "ss07", "aw07",
    "ss08", "aw08", "ss09", "aw09",
    "ss10", "aw10", "ss11", "aw11",
    "ss12", "aw12", "ss13", "aw13",
    "fw",
    "runway",
    "sample",
    "japan",
    "made in japan",
    "made in italy",
    "deadstock",
    "nwt",
    "bnwt",
]

# Categories to search
CATEGORIES = [
    "jacket",
    "blazer",
    "coat",
    "pants",
    "trousers",
    "jeans",
    "denim",
    "shirt",
    "hoodie",
    "sweater",
    "knit",
    "t-shirt",
    "tee",
    "boots",
    "shoes",
    "sneakers",
    "bag",
    "accessories",
]


def normalize_brand(brand: str) -> str:
    """Normalize brand name for matching."""
    return brand.lower().strip().replace("-", " ").replace("_", " ")


def get_search_queries() -> list[str]:
    """Return optimized search queries for Grailed scraping."""
    return list(SEARCH_QUERIES)


# Priority queries — scraped first and most frequently.
# These are the highest-performing queries from telemetry.
PRIORITY_BRANDS = [
    # Tier 1 broad brands (highest deal ratios, sorted by ratio)
    "enfants riches deprimes",
    "bottega veneta",
    "chrome hearts",
    "saint laurent",
    "maison margiela",
    "margiela tabi",
    "rick owens",
    "dior homme",
    "dior homme hedi slimane",
    "jean paul gaultier",
    "helmut lang",
    "raf simons",
    "carol christian poell",

    # High-value piece-specific queries
    "balenciaga runner",
    "kapital boro jacket",
    "undercover arts and crafts",
    "thierry mugler leather jacket",
    "alexander mcqueen leather jacket",
    "prada america's cup sneakers",
    "prada cotton velvet blouson",
    "ann demeulemeester leather boots",
    "vetements polizei hoodie",
    "dries van noten embroidered jacket",
    "tom ford gucci",
    "louis vuitton murakami",
]
