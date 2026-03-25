# Chrome Hearts Query Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan. Given the ERD experience where subagents lacked Edit permissions, inline execution is recommended. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace generic CH category queries with 67 piece-specific queries, kill 12 dead queries, restructure 12 families → 11 new ones, overhaul pricing/rep ceilings/auth/seasons/JP translations.

**Architecture:** This is an optimization pass on the most-tracked brand. 11 files modified, no new files created. The changes cascade: families define groupings → normalization handles aliases/promotion → target pools control rotation → downstream systems (pricing, auth, seasons, JP, rep ceilings) all get CH piece-specific data.

**Tech Stack:** Python, JSON config, katakana transliterations

**Spec:** `docs/superpowers/specs/2026-03-24-chrome-hearts-optimization-design.md`

---

### Task 1: Kill dead queries + add new demotions (query_normalization.py)

**Files:**
- Modify: `core/query_normalization.py` — DEMOTED_QUERY_FAMILIES section and PROMOTED_LIQUIDITY_QUERIES section

- [ ] **Step 1: Add 8 new dead queries to DEMOTED_QUERY_FAMILIES**

Check which of the 12 dead queries are NOT already in the demoted set, then add only the missing ones. Already demoted: `chrome hearts box officer glasses`, `chrome hearts bomber jacket`, `chrome hearts hollywood trucker hat`, `chrome hearts leather jacket`. Add these 8:

```python
    # CH dead queries — 0 deals, demoted 2026-03-24
    "chrome hearts cemetery horseshoe logo",
    "chrome hearts cemetery triple cross",
    "chrome hearts longsleeve",
    "chrome hearts scroll logo hoodie",
    "chrome hearts silicone cross necklace",
    "chrome hearts vertical logo hoodie",
    "chrome hearts tokyo",
    "chrome hearts t shirt",
```

- [ ] **Step 2: Add all 67 piece-specific queries to PROMOTED_LIQUIDITY_QUERIES**

Many already exist (29 CH queries currently promoted). Add only new ones. The new queries to add to the existing CH section:

```python
    # CH piece-specific jewelry (March 2026 optimization)
    "chrome hearts baby fat cross pendant",
    "chrome hearts tiny e",
    "chrome hearts floral cross pendant",
    "chrome hearts cemetery cross pendant",
    "chrome hearts nail cross pendant",
    "chrome hearts filigree cross pendant",
    "chrome hearts forever ring",
    "chrome hearts spacer ring",
    "chrome hearts scroll band ring",
    "chrome hearts cemetery ring",
    "chrome hearts dagger ring",
    "chrome hearts floral cross ring",
    "chrome hearts sbt band ring",
    "chrome hearts paper chain bracelet",
    "chrome hearts roller cross bracelet",
    "chrome hearts plus bracelet",
    "chrome hearts fancy link bracelet",
    "chrome hearts bead bracelet",
    "chrome hearts paper chain necklace",
    "chrome hearts ball chain necklace",
    "chrome hearts fancy chain necklace",
    "chrome hearts ne chain necklace",
    "chrome hearts plus stud earring",
    "chrome hearts cross stud earring",
    "chrome hearts hoop earring",
    "chrome hearts star stud earring",
    # CH piece-specific apparel
    "chrome hearts horseshoe tee",
    "chrome hearts scroll tee",
    "chrome hearts fuck you tee",
    "chrome hearts matty boy sex records",
    "chrome hearts matty boy chomper",
    "chrome hearts cemetery tee",
    "chrome hearts hollywood tee",
    "chrome hearts cross patch hoodie",
    "chrome hearts cemetery hoodie",
    "chrome hearts matty boy sex records hoodie",
    "chrome hearts fuck you hoodie",
    "chrome hearts crewneck",
    "chrome hearts long sleeve",
    # CH piece-specific denim/eyewear/accessories
    "chrome hearts fleur knee jeans",
    "chrome hearts gittin any glasses",
    "chrome hearts paper jam glasses",
    "chrome hearts penetranus sunglasses",
    "chrome hearts bone prone glasses",
    "chrome hearts pony hair trucker",
    "chrome hearts beanie",
    "chrome hearts belt",
    "chrome hearts converse",
    "chrome hearts rolling stones",
```

Note: Skip any that are already in the set. Check before adding.

- [ ] **Step 3: Verify**

Run: `python3 -c "from core.query_normalization import is_demoted_query, is_promoted_query; print('cemetery horseshoe demoted:', is_demoted_query('chrome hearts cemetery horseshoe logo')); print('baby fat promoted:', is_promoted_query('chrome hearts baby fat cross pendant')); print('forever ring promoted:', is_promoted_query('chrome hearts forever ring'))"`

- [ ] **Step 4: Commit**

```
git add core/query_normalization.py
git commit -m "feat(ch): kill 8 dead queries, promote 49 new piece-specific queries"
```

---

### Task 2: Replace 12 CH families with 11 new ones (target_families.py)

**Files:**
- Modify: `core/target_families.py` — delete all 12 existing CH family blocks, insert 11 new ones

This is the largest single edit. Delete everything from `chrome_hearts_cross_pendant` through `chrome_hearts_demoted_misc` (or `chrome_hearts_accessories`), then insert the 11 new families.

- [ ] **Step 1: Delete all 12 existing CH families**

Find and remove the entire block from the first CH family (`chrome_hearts_cross_pendant`) through the last one. Replace with the 11 new families.

- [ ] **Step 2: Insert 11 new CH families**

The new families follow the same dict pattern as existing families. Each has: canonical, aliases, broad_allowed (False), allowed_queries, demoted_queries.

Key points:
- `ch_pendants`: 7 queries, all in allowed_queries (including filigree — un-demoted from old family)
- `ch_rings`: 10 queries, spacer ring in allowed_queries (un-demoted from old family)
- `ch_bracelets`: 6 queries, bead bracelet in allowed_queries (un-demoted from old family)
- `ch_chains`: 4 queries (NEW family — split from old `chrome_hearts_necklaces`)
- `ch_earrings`: 4 queries (NEW category)
- `ch_tees`: 8 queries (absorbs old matty_boy, deadly_doll families)
- `ch_hoodies`: 4 queries
- `ch_apparel_other`: 7 queries
- `ch_denim`: 4 queries
- `ch_eyewear`: 7 queries (gittin any and paper jam in allowed, not demoted)
- `ch_accessories`: 6 queries

- [ ] **Step 3: Verify families load**

Run: `python3 -c "from core.target_families import family_id_map; fam = family_id_map(); ch = [k for k in fam if 'chrome hearts' in k]; print(f'{len(ch)} CH queries mapped'); print([family_id_map()[k] for k in ['chrome hearts baby fat cross pendant', 'chrome hearts forever ring', 'chrome hearts paper chain bracelet', 'chrome hearts horseshoe tee', 'chrome hearts cross patch jeans', 'chrome hearts trypoleagain glasses']])"`

Expected: 6 different family IDs (ch_pendants, ch_rings, ch_bracelets, ch_tees, ch_denim, ch_eyewear).

- [ ] **Step 4: Commit**

```
git add core/target_families.py
git commit -m "feat(ch): replace 12 generic families with 11 piece-specific families"
```

---

### Task 3: Update target pools (trend_engine.py)

**Files:**
- Modify: `trend_engine.py` — CORE_TARGETS, EXTENDED_TARGETS, LONGTAIL_TARGETS CH sections

- [ ] **Step 1: Replace CORE_TARGETS CH section**

Remove the existing 10 CH entries in CORE_TARGETS (lines ~102-112). Replace with:

```python
    # Chrome Hearts (piece-specific — 10 queries, ~14% of CORE)
    "chrome hearts baby fat cross pendant",
    "chrome hearts tiny e",
    "chrome hearts forever ring",
    "chrome hearts paper chain bracelet",
    "chrome hearts tee",
    "chrome hearts cross patch hoodie",
    "chrome hearts cross patch jeans",
    "chrome hearts trypoleagain glasses",
    "chrome hearts vagilante glasses",
    "chrome hearts paper chain",
```

- [ ] **Step 2: Replace EXTENDED_TARGETS CH section**

Remove the existing CH entries in EXTENDED_TARGETS (lines ~168-183). Replace with all EXTENDED queries from the spec (approximately 43 queries across jewelry, apparel, denim, eyewear, accessories).

- [ ] **Step 3: Add LONGTAIL CH queries**

Add to LONGTAIL_TARGETS:

```python
    # Chrome Hearts collector/niche pieces
    "chrome hearts filigree cross pendant",
    "chrome hearts sbt band ring",
    "chrome hearts bead bracelet",
    "chrome hearts ne chain necklace",
    "chrome hearts star stud earring",
    "chrome hearts fleur knee jeans",
    "chrome hearts bone prone glasses",
    "chrome hearts rolling stones",
    "chrome hearts boots",
```

- [ ] **Step 4: Verify pool counts**

Run: `python3 -c "from trend_engine import CORE_TARGETS, EXTENDED_TARGETS, LONGTAIL_TARGETS; ch_c = [t for t in CORE_TARGETS if 'chrome hearts' in t]; ch_e = [t for t in EXTENDED_TARGETS if 'chrome hearts' in t]; ch_l = [t for t in LONGTAIL_TARGETS if 'chrome hearts' in t]; print(f'CORE: {len(ch_c)}, EXTENDED: {len(ch_e)}, LONGTAIL: {len(ch_l)}, TOTAL: {len(ch_c)+len(ch_e)+len(ch_l)}')"`

Expected: CORE ~10, EXTENDED ~43, LONGTAIL ~9, TOTAL ~62+

- [ ] **Step 5: Commit**

```
git add trend_engine.py
git commit -m "feat(ch): replace generic target pools with 67 piece-specific queries"
```

---

### Task 4: Replace blue chip targets (blue_chip_targets.py)

**Files:**
- Modify: `core/blue_chip_targets.py` — delete existing 22 CH entries, add piece-specific entries

- [ ] **Step 1: Delete existing 22 CH BlueChipTarget entries** (lines ~48-82)

- [ ] **Step 2: Add piece-specific CH BlueChipTarget entries**

Add 15 entries covering the highest liquidity/margin pieces across all categories:

```python
    # Chrome Hearts — Piece-specific blue chips (March 2026 optimization)
    BlueChipTarget("chrome hearts baby fat cross pendant", "jewelry", 0.30, 0.45, 8, 550, "preferred", 9, "Most popular CH pendant"),
    BlueChipTarget("chrome hearts tiny e", "jewelry", 0.30, 0.45, 10, 350, "preferred", 10, "Highest volume entry pendant"),
    BlueChipTarget("chrome hearts forever ring", "jewelry", 0.30, 0.45, 10, 500, "preferred", 9, "Most popular CH ring"),
    BlueChipTarget("chrome hearts fuck you ring", "jewelry", 0.30, 0.45, 8, 700, "preferred", 9, "Novelty fast seller"),
    BlueChipTarget("chrome hearts cemetery ring", "jewelry", 0.30, 0.50, 6, 1200, "preferred", 8, "Best margin-to-liquidity ring"),
    BlueChipTarget("chrome hearts paper chain bracelet", "jewelry", 0.25, 0.40, 8, 1400, "preferred", 9, "#1 telemetry performer"),
    BlueChipTarget("chrome hearts paper chain necklace", "jewelry", 0.25, 0.40, 6, 1800, "preferred", 9, "Length-dependent pricing"),
    BlueChipTarget("chrome hearts plus stud earring", "jewelry", 0.30, 0.45, 8, 275, "preferred", 9, "Entry-level jewelry"),
    BlueChipTarget("chrome hearts horseshoe tee", "fashion", 0.30, 0.45, 10, 450, "preferred", 9, "Core CH tee"),
    BlueChipTarget("chrome hearts cross patch hoodie", "fashion", 0.25, 0.40, 6, 1500, "preferred", 8, "Grail hoodie"),
    BlueChipTarget("chrome hearts cross patch jeans", "fashion", 0.25, 0.40, 5, 5000, "preferred", 7, "Big ticket denim"),
    BlueChipTarget("chrome hearts cross patch flannel", "fashion", 0.25, 0.40, 5, 2500, "preferred", 7, "Sweet spot denim"),
    BlueChipTarget("chrome hearts trypoleagain glasses", "fashion", 0.30, 0.50, 6, 800, "preferred", 9, "Best deal efficiency — 19 deals/9 runs"),
    BlueChipTarget("chrome hearts vagilante glasses", "fashion", 0.25, 0.40, 5, 1500, "preferred", 8, "Appreciated significantly"),
    BlueChipTarget("chrome hearts pony hair trucker", "fashion", 0.25, 0.40, 6, 800, "preferred", 7, "Money hat"),
```

- [ ] **Step 3: Commit**

```
git add core/blue_chip_targets.py
git commit -m "feat(ch): replace 22 generic blue chips with 15 piece-specific entries"
```

---

### Task 5: Update pricing anchors (pricing.py)

**Files:**
- Modify: `api/services/pricing.py` — CH entry

- [ ] **Step 1: Replace CH pricing**

Replace existing `"chrome hearts"` line with:

```python
    "chrome hearts": {"jacket": 2000, "pants": 800, "shirt": 600, "tee": 350, "hoodie": 1000, "boots": 1500, "hat": 550, "default": 500},
```

- [ ] **Step 2: Commit**

```
git add api/services/pricing.py
git commit -m "feat(ch): update pricing anchors — tee correction, add boots/hat, lower default"
```

---

### Task 6: Expand rep price ceilings (gap_hunter.py)

**Files:**
- Modify: `gap_hunter.py` — REP_PRICE_CEILINGS["chrome hearts"] section

- [ ] **Step 1: Replace CH rep ceilings**

Replace the existing CH dict in REP_PRICE_CEILINGS with the expanded 40+ entry version from the spec (Part 7).

- [ ] **Step 2: Commit**

```
git add gap_hunter.py
git commit -m "feat(ch): expand rep price ceilings for 40+ piece-specific entries"
```

---

### Task 7: Update auth rules (authenticity_v2.py)

**Files:**
- Modify: `core/authenticity_v2.py` — BRAND_RULES["chrome hearts"]

- [ ] **Step 1: Replace CH auth config**

Replace with the spec's Part 8 config (extended high_rep_categories, preserved tag_details, lowered price floors).

- [ ] **Step 2: Commit**

```
git add core/authenticity_v2.py
git commit -m "feat(ch): expand auth keywords, lower price floors for jewelry"
```

---

### Task 8: Add season scoring patterns (seasons.py)

**Files:**
- Modify: `scrapers/seasons.py` — CH section

- [ ] **Step 1: Replace CH season patterns**

Replace the existing 2-pattern CH section with the full 16-pattern section from spec Part 9.

- [ ] **Step 2: Commit**

```
git add scrapers/seasons.py
git commit -m "feat(ch): add 14 piece-specific season scoring patterns"
```

---

### Task 9: Add JP translations (jp_query_translator.py)

**Files:**
- Modify: `core/jp_query_translator.py` — PRODUCT_TRANSLATIONS

- [ ] **Step 1: Add 29 CH piece-specific translations**

Append before closing `}` of PRODUCT_TRANSLATIONS. The runtime re-sorts by length.

- [ ] **Step 2: Commit**

```
git add core/jp_query_translator.py
git commit -m "feat(ch): add 29 piece-specific JP translations"
```

---

### Task 10: Update smart_scrape.py

**Files:**
- Modify: `scrapers/smart_scrape.py` — CH section

- [ ] **Step 1: Replace CH section**

Replace existing CH entries with 7 piece-specific queries from spec Part 11.

- [ ] **Step 2: Commit**

```
git add scrapers/smart_scrape.py
git commit -m "feat(ch): replace generic smart_scrape queries with piece-specific"
```

---

### Task 11: Update product fingerprint (product_fingerprint.py)

**Files:**
- Modify: `scrapers/product_fingerprint.py` — BRAND_MODELS or equivalent CH section

- [ ] **Step 1: Add new CH model names**

Add model names for new pieces not currently in the fingerprint system: roller cross, morning star, hoop earring, ne chain, plus stud, cross stud, horseshoe tee, scroll tee, cemetery hoodie, etc.

- [ ] **Step 2: Commit**

```
git add scrapers/product_fingerprint.py
git commit -m "feat(ch): add new model names to product fingerprint"
```

---

### Task 12: End-to-end smoke test

- [ ] **Step 1: Verify all imports**

Run: `python3 -c "from core.target_families import family_id_map; from core.query_normalization import normalize_query, is_promoted_query, is_demoted_query; from trend_engine import CORE_TARGETS, EXTENDED_TARGETS, LONGTAIL_TARGETS; from core.blue_chip_targets import BLUE_CHIP_FASHION; print('All imports OK')"`

- [ ] **Step 2: Verify family dedup**

Run: `python3 -c "
from core.query_normalization import family_id_for_query
queries = ['chrome hearts baby fat cross pendant', 'chrome hearts tiny e', 'chrome hearts forever ring', 'chrome hearts spacer ring', 'chrome hearts paper chain bracelet', 'chrome hearts roller cross bracelet', 'chrome hearts paper chain necklace', 'chrome hearts plus stud earring', 'chrome hearts horseshoe tee', 'chrome hearts cross patch hoodie', 'chrome hearts cross patch jeans']
for q in queries:
    print(f'{q[:45]:45s} -> {family_id_for_query(q)}')
"`

Expected: Each maps to its correct family (ch_pendants, ch_rings, ch_bracelets, ch_chains, ch_earrings, ch_tees, ch_hoodies, ch_denim).

- [ ] **Step 3: Verify no demoted conflicts**

Run: `python3 -c "
from core.query_normalization import is_demoted_query, is_promoted_query
test = ['chrome hearts baby fat cross pendant', 'chrome hearts forever ring', 'chrome hearts spacer ring', 'chrome hearts filigree cross pendant', 'chrome hearts bead bracelet']
for q in test:
    d = is_demoted_query(q)
    p = is_promoted_query(q)
    status = 'CONFLICT' if d and p else ('promoted' if p else ('demoted' if d else 'neutral'))
    print(f'{status}: {q}')
"`

Expected: All promoted, no conflicts. Spacer, filigree, bead should all be promoted (un-demoted from old families).

- [ ] **Step 4: Verify dead queries are killed**

Run: `python3 -c "
from core.query_normalization import is_demoted_query
dead = ['chrome hearts cemetery horseshoe logo', 'chrome hearts scroll logo hoodie', 'chrome hearts t shirt', 'chrome hearts tokyo']
for q in dead:
    print(f'{'KILLED' if is_demoted_query(q) else 'ALIVE'}: {q}')
"`

Expected: All KILLED.
