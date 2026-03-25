# Chrome Hearts Query Optimization Design

**Date:** 2026-03-24
**Status:** Approved
**Scope:** Replace generic CH category queries with 67 piece-specific queries, kill 12 dead queries, restructure into 11 families, overhaul pricing anchors and rep ceilings

---

## Motivation

Chrome Hearts is the #1 selling brand on Grailed (2024, 2025) and the most tracked brand in this system with 150+ queries. But telemetry shows the top 5 queries produce 80% of all CH deals while 12 queries are completely dead. The current queries are too generic — "chrome hearts ring" returns 500+ results spanning $200 spacer rings to $1,200 cemetery rings. Piece-specific queries like "chrome hearts cemetery ring" dramatically improve comp accuracy and deal quality.

Triple-validated against Grailed sold data with source links (March 2026).

---

## Part 1: Kill 12 Dead Queries

Add to `DEMOTED_QUERY_FAMILIES` in `core/query_normalization.py`:

```
"chrome hearts bomber jacket",       # 7 runs, 0 deals
"chrome hearts box officer glasses",  # 8 runs, 0 deals
"chrome hearts cemetery horseshoe logo", # 1 run, 0 deals, 1.0 junk
"chrome hearts cemetery triple cross",   # 3 runs, 0 deals, 1.0 junk
"chrome hearts hollywood trucker hat",   # 7 runs, 0 deals, 1.0 junk
"chrome hearts leather jacket",          # 5 runs, 0 deals
"chrome hearts longsleeve",              # 1 run, 0 deals, 1.0 junk
"chrome hearts scroll logo hoodie",      # 4 runs, 0 deals, 1.0 junk
"chrome hearts silicone cross necklace", # 3 runs, 0 deals, 1.0 junk
"chrome hearts vertical logo hoodie",    # 3 runs, 0 deals, 1.0 junk
"chrome hearts tokyo",                   # 1 run, 0 deals
"chrome hearts t shirt",                 # 2 runs, 0 deals (use "tee")
```

Note: Some of these are already in DEMOTED_QUERY_FAMILIES. Only add ones not already present. Check before inserting.

---

## Part 2: Remove Generic Queries from Target Pools

Remove these GENERIC queries from `trend_engine.py` CORE_TARGETS and EXTENDED_TARGETS — they'll be replaced by piece-specific queries:

**Remove from CORE_TARGETS:**
- `"chrome hearts ring"` — replaced by forever ring, fuck you ring, cemetery ring, etc.
- `"chrome hearts bracelet"` — replaced by paper chain bracelet, roller cross, etc.
- `"chrome hearts necklace"` — replaced by paper chain necklace, fancy chain, etc.
- `"chrome hearts tiny ring"` — replaced by spacer ring (more accurate name)
- `"chrome hearts wallet"` — already demoted, shouldn't be in CORE
- `"chrome hearts hat"` — replaced by pony hair trucker, cross patch hat, beanie

**Keep in CORE_TARGETS:**
- `"chrome hearts tee"` — 246 runs, 29 deals. Keep as broad catch-all alongside piece-specific tees.
- `"chrome hearts dagger pendant"` — validated, performing well
- `"chrome hearts paper chain"` — 443 runs, 46 deals. THE workhorse. Keep.
- `"chrome hearts floral cross"` — validated, performing well

**Remove from EXTENDED_TARGETS:**
- `"chrome hearts mini cross"` — too vague
- `"chrome hearts diamond ring"` — too broad, low deal rate
- `"chrome hearts sneakers"` — replaced by "chrome hearts converse"
- `"chrome hearts boots"` — low liquidity (5/10), demote to LONGTAIL
- `"chrome hearts glitter friends family"` — already demoted

**Keep in EXTENDED_TARGETS (proven performers):**
- All cross patch denim/flannel queries
- All Matty Boy queries
- All Deadly Doll queries
- All eyewear queries (trypoleagain, vagilante, see you tea)
- `"chrome hearts zip up hoodie"`, `"chrome hearts shorts"`, `"chrome hearts track pants"`
- `"chrome hearts cross patch hat"`, `"chrome hearts leather cross patch"`

---

## Part 3: The 67 Piece-Specific Queries

### JEWELRY — Pendants (7 queries)

| # | Query | Grailed Sold Price | Liquidity | Pool |
|---|-------|-------------------|-----------|------|
| 1 | `chrome hearts baby fat cross pendant` | $350-550 | 9/10 | CORE |
| 2 | `chrome hearts tiny e` | $200-350 | 10/10 | CORE |
| 3 | `chrome hearts floral cross pendant` | $500-900 | 8/10 | CORE |
| 4 | `chrome hearts dagger pendant` | $400-650 | 8/10 | CORE (KEEP) |
| 5 | `chrome hearts cemetery cross pendant` | $600-900 | 7/10 | EXTENDED |
| 6 | `chrome hearts nail cross pendant` | $500-800 | 7/10 | EXTENDED |
| 7 | `chrome hearts filigree cross pendant` | $1,200-2,000 | 6/10 | LONGTAIL |

### JEWELRY — Rings (10 queries)

| # | Query | Grailed Sold Price | Liquidity | Pool |
|---|-------|-------------------|-----------|------|
| 8 | `chrome hearts forever ring` | $300-500 | 9/10 | CORE |
| 9 | `chrome hearts spacer ring` | $200-350 | 9/10 | CORE |
| 10 | `chrome hearts fuck you ring` | $400-700 | 9/10 | CORE |
| 11 | `chrome hearts scroll band ring` | $300-500 | 9/10 | EXTENDED |
| 12 | `chrome hearts plus ring` | $350-550 | 8/10 | EXTENDED |
| 13 | `chrome hearts keeper ring` | $500-800 | 8/10 | EXTENDED |
| 14 | `chrome hearts cemetery ring` | $700-1,200 | 8/10 | EXTENDED |
| 15 | `chrome hearts dagger ring` | $400-650 | 8/10 | EXTENDED |
| 16 | `chrome hearts floral cross ring` | $500-850 | 7/10 | EXTENDED |
| 17 | `chrome hearts sbt band ring` | $350-550 | 7/10 | LONGTAIL |

### JEWELRY — Bracelets (6 queries)

| # | Query | Grailed Sold Price | Liquidity | Pool |
|---|-------|-------------------|-----------|------|
| 18 | `chrome hearts paper chain bracelet` | $500-1,400 | 9/10 | CORE |
| 19 | `chrome hearts roller cross bracelet` | $600-1,000 | 8/10 | EXTENDED |
| 20 | `chrome hearts plus bracelet` | $500-800 | 8/10 | EXTENDED |
| 21 | `chrome hearts fancy link bracelet` | $800-1,500 | 7/10 | EXTENDED |
| 22 | `chrome hearts morning star bracelet` | $700-1,200 | 7/10 | EXTENDED |
| 23 | `chrome hearts bead bracelet` | $400-700 | 7/10 | LONGTAIL |

### JEWELRY — Chains (4 queries)

| # | Query | Grailed Sold Price | Liquidity | Pool |
|---|-------|-------------------|-----------|------|
| 24 | `chrome hearts paper chain necklace` | $600-1,800 | 9/10 | CORE |
| 25 | `chrome hearts ball chain necklace` | $400-800 | 8/10 | EXTENDED |
| 26 | `chrome hearts fancy chain necklace` | $1,200-2,500 | 7/10 | EXTENDED |
| 27 | `chrome hearts ne chain necklace` | $600-1,200 | 7/10 | LONGTAIL |

### JEWELRY — Earrings (4 queries)

| # | Query | Grailed Sold Price | Liquidity | Pool |
|---|-------|-------------------|-----------|------|
| 28 | `chrome hearts plus stud earring` | $150-275 | 9/10 | EXTENDED |
| 29 | `chrome hearts cross stud earring` | $175-300 | 9/10 | EXTENDED |
| 30 | `chrome hearts hoop earring` | $250-450 | 8/10 | EXTENDED |
| 31 | `chrome hearts star stud earring` | $150-250 | 8/10 | LONGTAIL |

### APPAREL — Tees (8 queries)

| # | Query | Grailed Sold Price | Liquidity | Pool |
|---|-------|-------------------|-----------|------|
| 32 | `chrome hearts horseshoe tee` | $200-450 | 9/10 | CORE |
| 33 | `chrome hearts scroll tee` | $150-375 | 8/10 | EXTENDED |
| 34 | `chrome hearts fuck you tee` | $150-350 | 8/10 | EXTENDED |
| 35 | `chrome hearts matty boy sex records` | $350-550 | 8/10 | EXTENDED |
| 36 | `chrome hearts matty boy chomper` | $300-500 | 7/10 | EXTENDED |
| 37 | `chrome hearts deadly doll` | $250-400 | 8/10 | EXTENDED (KEEP) |
| 38 | `chrome hearts cemetery tee` | $120-450 | 7/10 | EXTENDED |
| 39 | `chrome hearts hollywood tee` | $250-400 | 7/10 | EXTENDED |

### APPAREL — Hoodies (4 queries)

| # | Query | Grailed Sold Price | Liquidity | Pool |
|---|-------|-------------------|-----------|------|
| 40 | `chrome hearts cross patch hoodie` | $800-1,500 | 8/10 | CORE |
| 41 | `chrome hearts cemetery hoodie` | $600-1,000 | 7/10 | EXTENDED |
| 42 | `chrome hearts matty boy sex records hoodie` | $500-900 | 7/10 | EXTENDED |
| 43 | `chrome hearts fuck you hoodie` | $500-800 | 7/10 | EXTENDED |

### APPAREL — Other (7 queries)

| # | Query | Grailed Sold Price | Liquidity | Pool |
|---|-------|-------------------|-----------|------|
| 44 | `chrome hearts neck logo long sleeve` | $300-500 | 7/10 | EXTENDED (KEEP) |
| 45 | `chrome hearts thermal` | $300-550 | 7/10 | EXTENDED (KEEP) |
| 46 | `chrome hearts crewneck` | $500-900 | 7/10 | EXTENDED |
| 47 | `chrome hearts sweatpants` | $400-750 | 7/10 | EXTENDED (KEEP) |
| 48 | `chrome hearts shorts` | $350-650 | 7/10 | EXTENDED (KEEP) |
| 49 | `chrome hearts track pants` | $500-900 | 6/10 | EXTENDED (KEEP) |
| 50 | `chrome hearts long sleeve` | $300-500 | 7/10 | EXTENDED |

### DENIM (4 queries)

| # | Query | Grailed Sold Price | Liquidity | Pool |
|---|-------|-------------------|-----------|------|
| 51 | `chrome hearts cross patch jeans` | $700-1,500 (std), $2K-6K (Levi's) | 7/10 | CORE (KEEP) |
| 52 | `chrome hearts cross patch flannel` | $1,200-2,500 | 7/10 | EXTENDED (KEEP) |
| 53 | `chrome hearts fleur knee jeans` | $300-1,200 | 6/10 | LONGTAIL |
| 54 | `chrome hearts denim jacket` | $1,500-3,000 | 6/10 | EXTENDED (KEEP) |

### EYEWEAR (7 queries)

| # | Query | Grailed Sold Price | Liquidity | Pool |
|---|-------|-------------------|-----------|------|
| 55 | `chrome hearts trypoleagain glasses` | $450-800 | 8/10 | CORE (KEEP — 19 deals/9 runs) |
| 56 | `chrome hearts vagilante glasses` | $800-1,500 | 8/10 | CORE (KEEP — appreciated) |
| 57 | `chrome hearts see you tea` | $200-800 | 8/10 | EXTENDED (KEEP) |
| 58 | `chrome hearts gittin any glasses` | $250-750 | 8/10 | EXTENDED (UN-DEMOTE — 3 deals/4 runs) |
| 59 | `chrome hearts paper jam glasses` | $400-700 | 7/10 | EXTENDED (UN-DEMOTE — 5 deals/5 runs) |
| 60 | `chrome hearts penetranus sunglasses` | $600-1,200 | 7/10 | EXTENDED |
| 61 | `chrome hearts bone prone glasses` | $500-850 | 7/10 | LONGTAIL |

### ACCESSORIES (6 queries)

| # | Query | Grailed Sold Price | Liquidity | Pool |
|---|-------|-------------------|-----------|------|
| 62 | `chrome hearts pony hair trucker` | $400-800 | 7/10 | EXTENDED |
| 63 | `chrome hearts cross patch hat` | $400-800 | 7/10 | EXTENDED (KEEP) |
| 64 | `chrome hearts beanie` | $200-400 | 7/10 | EXTENDED |
| 65 | `chrome hearts belt` | $500-900 | 7/10 | EXTENDED |
| 66 | `chrome hearts converse` | $400-800 | 7/10 | EXTENDED |
| 67 | `chrome hearts rolling stones` | $200-479 | 6/10 | LONGTAIL |

---

## Part 4: Family Structure (Replace 12 existing → 11 new)

### Existing Families to DELETE (all 12):
1. `chrome_hearts_cross_pendant`
2. `chrome_hearts_matty_boy`
3. `chrome_hearts_apparel`
4. `chrome_hearts_denim`
5. `chrome_hearts_deadly_doll`
6. `chrome_hearts_matty_boy_apparel`
7. `chrome_hearts_necklaces`
8. `chrome_hearts_rings`
9. `chrome_hearts_bracelets`
10. `chrome_hearts_eyewear`
11. `chrome_hearts_demoted_misc`
12. `chrome_hearts_accessories`

All 12 are replaced by the 11 new families below. The `chrome_hearts_necklaces` family (which conflated pendants and chains) is correctly split into `ch_pendants` and `ch_chains`. The `chrome_hearts_matty_boy`, `chrome_hearts_matty_boy_apparel`, and `chrome_hearts_deadly_doll` families are absorbed into `ch_tees` and `ch_hoodies`. The `chrome_hearts_demoted_misc` (cox ucker variants) is not recreated — those queries remain in `DEMOTED_QUERY_FAMILIES`.

### New Families (11)

### `ch_pendants` (7 queries)
- Canonical: `chrome hearts baby fat cross pendant`
- Members: baby fat, tiny e, floral cross pendant, dagger pendant, cemetery cross pendant, nail cross pendant, filigree cross pendant
- Aliases: Both full name and shortened variants for each

### `ch_rings` (10 queries)
- Canonical: `chrome hearts forever ring`
- Members: forever, spacer, scroll band, fuck you, plus, keeper, cemetery, dagger, floral cross, sbt band
- Aliases: Full name + common abbreviations

### `ch_bracelets` (6 queries)
- Canonical: `chrome hearts paper chain bracelet`
- Members: paper chain bracelet, roller cross, plus, fancy link, morning star, bead

### `ch_chains` (4 queries)
- Canonical: `chrome hearts paper chain necklace`
- Members: paper chain necklace, ball chain, fancy chain, ne chain

### `ch_earrings` (4 queries)
- Canonical: `chrome hearts plus stud earring`
- Members: plus stud, cross stud, hoop, star stud

### `ch_tees` (8 queries)
- Canonical: `chrome hearts horseshoe tee`
- Members: horseshoe tee, scroll tee, fuck you tee, matty boy sex records, matty boy chomper, deadly doll, cemetery tee, hollywood tee

### `ch_hoodies` (4 queries)
- Canonical: `chrome hearts cross patch hoodie`
- Members: cross patch hoodie, cemetery hoodie, matty boy sex records hoodie, fuck you hoodie

### `ch_apparel_other` (7 queries)
- Canonical: `chrome hearts neck logo long sleeve`
- Members: neck logo LS, thermal, crewneck, sweatpants, shorts, track pants, long sleeve

### `ch_denim` (4 queries)
- Canonical: `chrome hearts cross patch jeans`
- Members: cross patch jeans, cross patch flannel, fleur knee jeans, denim jacket

### `ch_eyewear` (7 queries)
- Canonical: `chrome hearts trypoleagain glasses`
- Members: trypoleagain, vagilante, see you tea, gittin any, paper jam, penetranus, bone prone

### `ch_accessories` (6 queries)
- Canonical: `chrome hearts pony hair trucker`
- Members: pony hair trucker, cross patch hat, beanie, belt, converse, rolling stones

---

## Part 5: CORE_TARGETS Placement (10 queries — trimmed to prevent cycle domination)

With ~73 total CORE entries, 10 CH queries = ~14% allocation. This is appropriate for the #1 brand.

```
# CH Jewelry (highest liquidity — 4 queries)
"chrome hearts baby fat cross pendant",
"chrome hearts tiny e",
"chrome hearts forever ring",
"chrome hearts paper chain bracelet",
# CH Apparel (proven performers — 3 queries)
"chrome hearts tee",
"chrome hearts cross patch hoodie",
"chrome hearts cross patch jeans",
# CH Eyewear (best deal efficiency — 2 queries)
"chrome hearts trypoleagain glasses",
"chrome hearts vagilante glasses",
# CH Legacy (workhorse — 1 query)
"chrome hearts paper chain",
```

Queries moved from proposed CORE to EXTENDED (still rotate, just not always-on):
- `floral cross pendant`, `spacer ring`, `fuck you ring`, `paper chain necklace`, `horseshoe tee`, `dagger pendant`

These are liquid but don't need always-on status. EXTENDED rotation ensures they still run frequently.

---

## Part 6: Pricing Anchors (pricing.py)

**Important:** Use `_detect_category`-compatible keys only (jacket, pants, shirt, tee, hoodie, boots, bag, hat, default).

Update `"chrome hearts"` entry:

```python
"chrome hearts": {"jacket": 2000, "pants": 800, "shirt": 600, "tee": 350, "hoodie": 1000, "boots": 1500, "hat": 550, "default": 500},
```

Changes from current: tee $400→$350 (Grailed sold correction), boots added at $1,500, hat added at $550, default $800→$500 (jewelry entry points are $200-500 range).

Note: Many new pricing categories (ring, pendant, bracelet, chain, earring, jeans, flannel, glasses, sneakers) CANNOT be added because `_detect_category()` won't produce those keys. The comp matching system handles piece-specific pricing via actual sold data — these fallbacks are safety nets only.

---

## Part 7: Rep Price Ceilings (gap_hunter.py)

Expand existing CH ceilings to cover new piece-specific queries:

```python
"chrome hearts": {
    "trucker hat": 350, "hat": 300, "beanie": 200,
    "cross pendant": 350, "baby fat": 300, "tiny e": 175,
    "dagger pendant": 400, "floral cross": 450, "nail cross": 400,
    "cemetery cross": 500, "filigree cross": 700,
    "cross ring": 300, "ring": 250, "forever ring": 275,
    "spacer ring": 150, "scroll band": 275, "fuck you ring": 350,
    "plus ring": 300, "keeper ring": 400, "cemetery ring": 550,
    "dagger ring": 350, "sbt band": 300,
    "bracelet": 400, "paper chain": 450, "roller cross bracelet": 450,
    "plus bracelet": 400, "fancy link": 550, "morning star": 500,
    "bead bracelet": 300,
    "necklace": 300, "chain": 350, "paper chain necklace": 450,
    "fancy chain": 700, "ball chain": 300, "ne chain": 400,
    "earring": 125, "stud earring": 100, "hoop earring": 175,
    "leather": 1200, "denim jacket": 1000,
    "hoodie": 450, "zip up": 500, "cross patch hoodie": 600,
    "tee": 250, "tank": 175,
    "jeans": 500, "cross patch jeans": 1000, "flannel": 800,
    "fleur knee": 300,
    "belt": 350, "wallet": 500,
    "glasses": 350, "sunglasses": 400,
    "converse": 300,
    "boots": 800, "sneakers": 500,
}
```

---

## Part 8: Auth Rules (authenticity_v2.py)

Expand existing CH entry:

```python
"chrome hearts": {
    "price_floor": 100,
    "price_typical_min": 200,
    "auth_keywords": [
        "925", "sterling", "made in usa", "hollywood",
        "scroll work", "cross", "floral",
    ],
    "rep_misspellings": ["chrome heart", "chromhearts", "crome hearts"],
    "high_rep_categories": ["jewelry", "ring", "pendant", "cross", "trucker hat", "logo tee"],
    "tag_details": "Authentic CH has .925 stamp, scroll work details, proper weight",
},
```

Changes: EXTEND existing `high_rep_categories` (keep broad "jewelry", "ring", "pendant", "cross"), ADD "trucker hat" and "logo tee". Keep existing `auth_keywords` (already match via substring). Preserve `tag_details` for institutional knowledge.

Changes: lowered `price_floor` $150→$100 (earrings/spacer rings start at $150), `price_typical_min` $300→$200 (earrings, tiny e), added ".925", "sterling silver" to auth_keywords, added "chrome heart" (singular — common misspelling), expanded high_rep_categories.

---

## Part 9: Season Scoring (seasons.py)

Current CH scoring only has 2 patterns. Expand with piece-specific multipliers:

```python
"chrome hearts": [
    (r"cemetery|cross", 1.3, "Cemetery/Cross"),
    (r"leather", 1.4, "Leather piece"),
    # Piece-specific (March 2026 research)
    (r"baby.?fat", 1.8, "Baby Fat — most popular pendant"),
    (r"paper.?chain", 1.8, "Paper Chain — #1 telemetry performer"),
    (r"matty.?boy", 1.6, "Matty Boy collab"),
    (r"deadly.?doll", 1.6, "Deadly Doll — high deal efficiency"),
    (r"sex.?records", 1.7, "Sex Records — #1 Matty Boy design"),
    (r"fuck.?you", 1.5, "Fuck You — novelty fast seller"),
    (r"cross.?patch", 1.7, "Cross Patch — grail denim/hoodie/hat"),
    (r"trypoleagain|vagilante|see.?you.?tea", 1.8, "Top eyewear models"),
    (r"pony.?hair", 1.6, "Pony Hair trucker — money hat"),
    (r"filigree", 1.5, "Filigree — collector piece"),
    (r"keeper", 1.4, "Keeper ring — classic CH"),
    (r"fleur.?knee", 1.3, "Fleur Knee jeans"),
    (r"rolling.?stones", 1.5, "Rolling Stones collab"),
    (r"las.?vegas|tokyo|aspen|paris", 1.4, "City exclusive"),
],
```

---

## Part 10: JP Translations (jp_query_translator.py)

Add piece-specific product terms:

```python
# ── Chrome Hearts piece-specific ─────────────────────────────────────
"baby fat cross":       "ベビーファットクロス",
"tiny e":               "タイニーE",
"floral cross pendant": "フローラルクロスペンダント",
"nail cross":           "ネイルクロス",
"cemetery cross":       "セメタリークロス",
"filigree cross":       "フィリグリークロス",
"forever ring":         "フォーエバーリング",
"spacer ring":          "スペーサーリング",
"scroll band ring":     "スクロールバンドリング",
"keeper ring":          "キーパーリング",
"cemetery ring":        "セメタリーリング",
"roller cross bracelet":"ローラークロスブレスレット",
"plus bracelet":        "プラスブレスレット",
"fancy link bracelet":  "ファンシーリンクブレスレット",
"fancy chain necklace": "ファンシーチェーンネックレス",
"ball chain necklace":  "ボールチェーンネックレス",
"ne chain necklace":    "NEチェーンネックレス",
"plus stud earring":    "プラススタッドイヤリング",
"cross stud earring":   "クロススタッドイヤリング",
"hoop earring":         "フープイヤリング",
"horseshoe tee":        "ホースシューTシャツ",
"scroll tee":           "スクロールTシャツ",
"cross patch hoodie":   "クロスパッチフーディー",
"cemetery hoodie":      "セメタリーフーディー",
"fleur knee jeans":     "フルールニージーンズ",
"penetranus":           "ペネトラナス",
"bone prone":           "ボーンプローン",
"pony hair trucker":    "ポニーヘアトラッカー",
"rolling stones":       "ローリングストーンズ",
```

---

## Part 11: smart_scrape.py

Replace existing CH entries with top piece-specific queries:

```python
# Chrome Hearts (piece-specific)
"chrome hearts baby fat cross pendant",
"chrome hearts forever ring",
"chrome hearts paper chain bracelet",
"chrome hearts trypoleagain glasses",
"chrome hearts cross patch hoodie",
"chrome hearts horseshoe tee",
"chrome hearts cross patch jeans",
```

---

## Part 12: Fix Family-Level Demotions

**IMPORTANT:** The 9 queries below are NOT in `DEMOTED_QUERY_FAMILIES` — they're already in `PROMOTED_LIQUIDITY_QUERIES`. However, some are demoted at the FAMILY level inside `target_families.py` `demoted_queries` arrays. When building the new 11 families, ensure these queries are in `allowed_queries`, NOT `demoted_queries`:

- `"chrome hearts spacer ring"` — currently demoted in `chrome_hearts_rings` family. UN-DEMOTE in new `ch_rings` family.
- `"chrome hearts filigree cross pendant"` — currently demoted in `chrome_hearts_necklaces` family. UN-DEMOTE in new `ch_pendants` family.
- `"chrome hearts bead bracelet"` — currently demoted in `chrome_hearts_bracelets` family. UN-DEMOTE in new `ch_bracelets` family.
- `"chrome hearts horseshoe hoodie"` — currently demoted in `chrome_hearts_apparel` family. Leave out of new families (not in our 67 query list).

Also ensure these telemetry-proven performers are in `allowed_queries` (not demoted) in their new families:
- `"chrome hearts gittin any glasses"` — 3 deals/4 runs
- `"chrome hearts paper jam glasses"` — 5 deals/5 runs
- `"chrome hearts bone prone glasses"` — new addition
- `"chrome hearts boots"` — 6 deals/7 runs, move to LONGTAIL pool
- `"chrome hearts belt"` — consistent demand, add to `ch_accessories`

---

## Files Modified

| File | Change |
|------|--------|
| `core/target_families.py` | Replace existing 11 CH families with 11 new piece-specific families |
| `core/query_normalization.py` | Kill 12 dead queries, un-demote 9, promote all 67, add aliases |
| `trend_engine.py` | Remove generic queries, add 16 CORE + ~35 EXTENDED + ~8 LONGTAIL |
| `core/blue_chip_targets.py` | Replace 22 generic CH entries with piece-specific entries |
| `api/services/pricing.py` | Update CH pricing with corrected values |
| `gap_hunter.py` | Expand REP_PRICE_CEILINGS for 40+ piece-specific entries |
| `core/authenticity_v2.py` | Expand auth keywords, lower price floors |
| `scrapers/seasons.py` | Add 14 piece-specific scoring patterns |
| `core/jp_query_translator.py` | Add 29 piece-specific product translations |
| `scrapers/smart_scrape.py` | Replace generic CH with 7 piece-specific queries |
| `scrapers/product_fingerprint.py` | Add new CH model names (roller cross, morning star, hoop earring, ne chain, etc.) for fingerprint matching |
