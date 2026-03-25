# ERD Piece-Specific Query Integration Design

**Date:** 2026-03-24
**Status:** Approved
**Scope:** Add 16 most liquid Enfants Riches Déprimés pieces as specific queries across all system layers

---

## Motivation

ERD currently has 11 generic category queries ("enfants riches deprimes hoodie", "enfants riches deprimes tee", etc.) but zero piece-specific queries. Piece-specific queries like "enfants riches deprimes classic logo hoodie" dramatically improve comp accuracy and deal detection — a generic "hoodie" query returns 50+ results including $200 basics, while "classic logo hoodie" targets the $600-$1,600 segment directly. This is the difference between finding noise and finding profit.

This design serves as the **template for other brands** (Chrome Hearts, Raf Simons archive, etc.) once proven.

---

## The 16 Queries

| # | Piece | Primary Query | ERD Alias | Avg Sold Range | Family |
|---|-------|--------------|-----------|----------------|--------|
| 1 | Classic Logo Hoodie | `enfants riches deprimes classic logo hoodie` | `erd classic logo hoodie` | $600-$1,600 | `erd_grails_tier1` |
| 2 | Thrashed Classic Logo Tee | `enfants riches deprimes classic logo tee` | `erd classic logo tee` | $350-$900 | `erd_grails_tier1` |
| 3 | Safety Pin Earring | `enfants riches deprimes safety pin earring` | `erd safety pin earring` | $150-$400 | `erd_grails_tier1` |
| 4 | Classic Logo Longsleeve | `enfants riches deprimes classic logo long sleeve` | `erd classic logo long sleeve` | $450-$1,200 | `erd_grails_tier1` |
| 5 | Benny's Video Hoodie | `enfants riches deprimes bennys video hoodie` | `erd bennys video` | $800-$2,000 | `erd_trending` |
| 6 | Menendez Murder Trial Hoodie | `enfants riches deprimes menendez hoodie` | `erd menendez` | $450-$1,400 | `erd_trending` |
| 7 | Viper Room Hat | `enfants riches deprimes viper room hat` | `erd viper room` | $800-$10,000 | `erd_trending` |
| 8 | Teenage Snuff Tee | `enfants riches deprimes teenage snuff tee` | `erd teenage snuff` | $500-$1,200 | `erd_trending` |
| 9 | Flowers of Anger LS | `enfants riches deprimes flowers of anger` | `erd flowers of anger` | $600-$1,500 | `erd_trending` |
| 10 | Bohemian Scum Tee | `enfants riches deprimes bohemian scum tee` | `erd bohemian scum` | $300-$850 | `erd_trending` |
| 11 | God With Revolver Zip Hoodie | `enfants riches deprimes god with revolver` | `erd god with revolver` | $900-$2,200 | `erd_premium_outerwear` |
| 12 | Spanish Elegy Moto Jacket | `enfants riches deprimes spanish elegy jacket` | `erd spanish elegy` | $2,500-$6,000 | `erd_premium_outerwear` |
| 13 | Menendez Murder Trial Pants | `enfants riches deprimes menendez pants` | `erd menendez pants` | $500-$1,000 | `erd_bottoms` (existing) |
| 14 | Rose Buckle Studded Belt | `enfants riches deprimes rose buckle belt` | `erd rose buckle belt` | $800-$1,800 | `erd_accessories` (existing) |
| 15 | Frozen Beauties Flannel | `enfants riches deprimes frozen beauties flannel` | `erd frozen beauties` | $2,500-$4,500 | `erd_collector` |
| 16 | Le Rosey Tee | `enfants riches deprimes le rosey tee` | `erd le rosey` | $800-$2,000 | `erd_collector` |

---

## Family Structure (target_families.py)

### Approach: Tiered Families by Liquidity

4 new families + 2 existing families updated. Family dedup ensures 1 query per family per cycle.

### Relationship to Existing Generic Families

ERD currently has 4 generic families: `erd_tops`, `erd_outerwear`, `erd_bottoms`, `erd_accessories`. These remain unchanged — they continue to serve the existing generic queries ("enfants riches deprimes hoodie", "enfants riches deprimes leather jacket", etc.).

With 4 new + 4 existing = **8 total ERD families**, the system could theoretically run up to 8 ERD queries per 25-query cycle. In practice, the rotation pool algorithm limits this to ~3-4 due to brand diversity weighting and cooldown logic. This is acceptable because:
- Generic queries cast a wide net (catch unlisted/new ERD pieces)
- Piece-specific queries target the highest-value items precisely
- Both are needed — they serve different purposes

### New Families

**`erd_grails_tier1`** — Fastest sellers (days to 2 weeks)
- Canonical: `enfants riches deprimes classic logo hoodie`
- Aliases: all 4 queries + ERD abbreviations
- allowed_queries: all 4 primary queries
- Rationale: Perennial demand, always liquid. ERD's equivalent of Rick Owens Geobaskets.

**`erd_trending`** — Culture-driven pieces (1-4 weeks)
- Canonical: `enfants riches deprimes bennys video hoodie`
- Aliases: all 6 queries + ERD abbreviations
- allowed_queries: all 6 primary queries
- Rationale: Trend-sensitive pieces grouped for independent weight tuning. When Menendez cultural moment fades, demote this family without touching grails.

**`erd_premium_outerwear`** — $2K+ leather/outerwear
- Canonical: `enfants riches deprimes spanish elegy jacket`
- Aliases: both queries + ERD abbreviations
- allowed_queries: both primary queries
- Rationale: High price point, rare enough that 2 queries competing in one family is fine.

**`erd_collector`** — Grail-tier (1-3 months sell-through)
- Canonical: `enfants riches deprimes frozen beauties flannel`
- Aliases: both queries + ERD abbreviations
- allowed_queries: both primary queries
- Rationale: Ultra-rare. Fewer runs needed — massive margins when they hit.

### Existing Families Updated

**`erd_bottoms`**: Add `enfants riches deprimes menendez pants` to aliases and allowed_queries.

**`erd_accessories`**: Add `enfants riches deprimes rose buckle belt` to aliases and allowed_queries.

---

## Query Normalization (query_normalization.py)

### Alias Ownership: target_families.py vs query_normalization.py

**In `target_families.py` (auto-flow into QUERY_ALIASES via `alias_to_canonical_map()`):**
- All `"erd <piece>"` abbreviations go here as family aliases (e.g., `"erd classic logo hoodie"`)
- These are structural aliases tied to family membership

**In `query_normalization.py` QUERY_ALIASES (explicit, for quirky variants only):**
Only variants that don't fit the family alias pattern:

```
"erd benny's video" -> "enfants riches deprimes bennys video hoodie"  # apostrophe variant
"erd safety pin" -> "enfants riches deprimes safety pin earring"       # shortened
"erd rose buckle" -> "enfants riches deprimes rose buckle belt"        # shortened
"erd menendez" -> "enfants riches deprimes menendez hoodie"            # ambiguous (hoodie vs pants) — defaults to hoodie
```

All other ERD abbreviations are handled by the family aliases in `target_families.py` and do NOT need explicit entries in `query_normalization.py`.

### PROMOTED_LIQUIDITY_QUERIES

All 16 piece-specific queries added (1.35x weight boost). Proven liquid from market research.

---

## Target Pool Placement (trend_engine.py)

- **CORE_TARGETS** (always-on, highest priority): classic logo hoodie, classic logo tee, safety pin earring, classic logo long sleeve
- **EXTENDED_TARGETS** (expanded rotation): bennys video hoodie, menendez hoodie, viper room hat, teenage snuff tee, flowers of anger, bohemian scum tee, spanish elegy jacket, god with revolver, menendez pants, rose buckle belt
- **LONGTAIL_TARGETS** (curated archive, slower rotation): frozen beauties flannel, le rosey tee

---

## Blue Chip Targets (blue_chip_targets.py)

Add 8 strongest margin + liquidity profiles to `BLUE_CHIP_FASHION`, placed after the existing `# Number (N)ine` section (~line 365) and before `# The Soloist`:

```python
BlueChipTarget("enfants riches deprimes classic logo hoodie", "fashion", 0.30, 0.45, 6, 1600, "preferred", 9, "Most liquid ERD piece")
BlueChipTarget("enfants riches deprimes classic logo tee", "fashion", 0.35, 0.50, 8, 900, "preferred", 9, "Highest volume ERD listing")
BlueChipTarget("enfants riches deprimes safety pin earring", "fashion", 0.30, 0.45, 6, 400, "preferred", 9, "Most iconic ERD accessory")
BlueChipTarget("enfants riches deprimes bennys video hoodie", "fashion", 0.25, 0.40, 5, 2000, "preferred", 8, "Film reference, cult following")
BlueChipTarget("enfants riches deprimes menendez hoodie", "fashion", 0.30, 0.45, 5, 1400, "preferred", 8, "Trend-driven, true crime wave")
BlueChipTarget("enfants riches deprimes viper room hat", "fashion", 0.35, 0.55, 4, 10000, "preferred", 7, "C&D piece, wide price range")
BlueChipTarget("enfants riches deprimes spanish elegy jacket", "fashion", 0.25, 0.40, 4, 6000, "preferred", 7, "Premium moto leather")
BlueChipTarget("enfants riches deprimes frozen beauties flannel", "fashion", 0.30, 0.50, 3, 4500, "preferred", 6, "Only 50 made, Kanye co-sign")
```

Remaining 8 enter the system through query rotation but don't need blue chip status.

---

## Pricing Anchors (api/services/pricing.py)

**Important:** These anchors are generic category fallbacks for ALL ERD items, not just the top pieces. Values must reflect the median sold price across all ERD items of that category, not be skewed by grails like Viper Room ($10K) or Frozen Beauties ($4.5K).

Update both `"enfants riches deprimes"` and `"erd"` keys with moderate increases from current values:

```python
# Current -> Updated (moderate, not piece-skewed)
"enfants riches deprimes": {
    "jacket": 2000, "leather jacket": 2500, "denim jacket": 1000,
    "bomber": 1200, "flannel": 600, "pants": 450, "jeans": 500,
    "shirt": 450, "tee": 500, "long sleeve": 450, "hoodie": 750,
    "sweater": 650, "hat": 400, "belt": 700, "earring": 250,
    "default": 450,
}
```

Changes from current: hoodie $500->$750 (+50%), tee $400->$500 (+25%), jacket $1500->$2000 (+33%), hat $200->$400 (+100%), belt $500->$700 (+40%). These are justified by the overall ERD market moving up, but not inflated to piece-specific extremes.

The piece-specific pricing (Classic Logo Hoodie at $1,100, Viper Room Hat at $3,000+) is handled by the comp matching system which uses actual sold data, not these fallback anchors.

---

## JP Query Translations (jp_query_translator.py)

Add piece-specific product terms to `PRODUCT_TRANSLATIONS` (katakana transliterations for Yahoo Auctions):

```python
"classic logo hoodie": "クラシックロゴフーディー",
"classic logo tee": "クラシックロゴTシャツ",
"safety pin earring": "セーフティピンイヤリング",
"bennys video": "ベニーズビデオ",
"menendez": "メネンデス",
"viper room": "バイパールーム",
"teenage snuff": "ティーンエイジスナッフ",
"flowers of anger": "フラワーズオブアンガー",
"god with revolver": "ゴッドウィズリボルバー",
"spanish elegy": "スパニッシュエレジー",
"rose buckle belt": "ローズバックルベルト",
"bohemian scum": "ボヘミアンスカム",
"frozen beauties": "フローズンビューティーズ",
"classic logo long sleeve": "クラシックロゴロングスリーブ",
"le rosey": "ル・ロゼ",
```

Total: 15 product term translations.

---

## Auth Rules (authenticity_v2.py)

Use the **existing BRAND_RULES schema** (`price_floor`, `price_typical_min`, `auth_keywords`, `rep_misspellings`, `high_rep_categories`). Do NOT introduce new schema keys — the `AuthChecker` class only reads the existing keys.

Update from current:
```python
"enfants riches deprimes": {
    "price_floor": 150,
    "price_typical_min": 300,
    "auth_keywords": ["erd", "henri alexander levy", "made in usa"],
    "rep_misspellings": ["enfant riche deprime"],
    "high_rep_categories": [],
}
```

To:
```python
"enfants riches deprimes": {
    "price_floor": 150,
    "price_typical_min": 350,
    "auth_keywords": [
        "erd", "henri alexander levy", "made in usa", "made in la",
        "hand distressed", "cigarette burns", "thrashed",
        "henri levy", "los angeles",
    ],
    "rep_misspellings": ["enfant riche deprime", "enfant riches", "enfants riche"],
    "high_rep_categories": [],
}
```

Changes: expanded `auth_keywords` with piece-relevant terms (hand distressed, cigarette burns are ERD hallmarks), added common misspellings to `rep_misspellings`, bumped `price_typical_min` slightly to $350.

---

## Season Scoring (seasons.py)

Add piece-name regex patterns to existing ERD section:

```python
(r"classic.?logo", 2.2, "Classic Logo — most liquid ERD piece"),
(r"benny.?s?.?video", 2.0, "Benny's Video — cult film reference"),
(r"menendez", 2.0, "Menendez Murder Trial — trend-driven"),
(r"viper.?room", 2.5, "Viper Room — C&D, extreme provenance"),
(r"teenage.?snuff", 1.8, "Teenage Snuff — consistent seller"),
(r"flowers?.?of.?anger", 1.8, "Flowers of Anger LS"),
(r"god.?with.?revolver", 1.9, "God With Revolver zip"),
(r"spanish.?elegy", 2.3, "Spanish Elegy moto — premium leather"),
(r"rose.?buckle", 1.8, "Rose Buckle studded belt"),
(r"frozen.?beaut", 2.8, "Frozen Beauties — only 50 made"),
(r"le.?rosey", 2.5, "Le Rosey — first ERD design ever"),
(r"bohemian.?scum", 1.6, "Bohemian Scum tee"),
```

---

## Files Modified

| File | Change |
|------|--------|
| `core/target_families.py` | 4 new families, 2 updated |
| `core/query_normalization.py` | 4 quirky aliases, 16 promoted queries |
| `trend_engine.py` | 4 CORE, 10 EXTENDED, 2 LONGTAIL queries |
| `core/blue_chip_targets.py` | 8 new BlueChipTarget entries (after Number Nine section) |
| `api/services/pricing.py` | Moderate ERD + erd price anchor increases |
| `core/jp_query_translator.py` | 15 product term translations |
| `core/authenticity_v2.py` | Expanded auth_keywords + rep_misspellings (existing schema) |
| `scrapers/seasons.py` | 12 new season scoring patterns |
| `scrapers/smart_scrape.py` | Add ERD piece-specific queries to hardcoded ERD section (~line 140) |

**Post-deploy steps (not code changes):**
- Run gap hunter cycle with new ERD queries to collect sold comps
- Run `build_product_catalog.py --brand "enfants riches deprimes"` to seed catalog
- Verify pieces appear in BrandModelPicker via catalog API

---

## User-Facing Hunting: Catalog Seeding

### The Gap

The Scraper page's `BrandModelPicker` is catalog-driven — users select products from the `products` table, not free text. ERD piece-specific products (e.g., "Classic Logo Hoodie") won't appear in the picker until:

1. The gap hunter runs the new queries and collects sold comp data
2. `build_product_catalog.py` fingerprints those comps into `products` table entries
3. Products then appear in the BrandModelPicker for user selection

### Implementation Sequence

After deploying the code changes:

1. **Run one gap hunter cycle** with the 16 new ERD queries (`custom_queries` mode) to collect sold comps
2. **Run `python scripts/build_product_catalog.py --brand "enfants riches deprimes"`** to fingerprint sold comps into catalog products
3. **Verify** ERD pieces appear in `GET /api/catalog/brands/enfants riches deprimes/models`

### Fallback

Until catalog entries exist, users can still hunt ERD pieces via:
- **Watchlists** that reference ERD product fingerprints (once seeded)
- **Direct API calls**: `POST /api/scrape/start` with `custom_queries=["enfants riches deprimes classic logo hoodie"]`

### Automatic Deals (No User Action Needed)

The CORE/EXTENDED/LONGTAIL placement ensures ERD piece-specific queries run automatically every cycle. Deals found are:
- Saved to DB and displayed on the Deals page
- Sent to subscribers via Telegram/Discord/Whop
- Scored with deal grades (A/B/C) using 5+ authenticated sold comps

---

## Template Pattern for Future Brands

This design establishes a repeatable pattern:
1. Research top liquid pieces via luxury-resale-pricer agent
2. Create tiered families by liquidity speed
3. Add piece-specific queries with abbreviation aliases
4. Promote all to PROMOTED_LIQUIDITY_QUERIES
5. Place in CORE/EXTENDED/LONGTAIL by liquidity tier
6. Add strongest to blue chip targets
7. Update generic pricing anchors moderately (don't skew to top pieces)
8. Add JP translations for Yahoo Auctions coverage
9. Expand auth_keywords within existing BRAND_RULES schema
10. Add season scoring multipliers
11. Update smart_scrape.py hardcoded query lists

Next candidates: Chrome Hearts (specific jewelry pieces), Raf Simons (archive season pieces), Dior Homme (Hedi era specifics).
