# ERD Piece-Specific Queries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 16 most liquid ERD pieces as specific queries across all system layers so users receive accurate, high-profit ERD deals automatically and can hunt specific pieces from the UI.

**Architecture:** Data-layer changes across 9 files — no new files created. Families in `target_families.py` define query groupings, normalization in `query_normalization.py` handles aliases, target pools in `trend_engine.py` control rotation, and downstream systems (pricing, auth, seasons, JP, blue chip, smart_scrape) all get ERD piece-specific data.

**Tech Stack:** Python (all backend), JSON config, katakana transliterations

**Spec:** `docs/superpowers/specs/2026-03-24-erd-piece-specific-queries-design.md`

---

### Task 1: Add 4 new ERD families to target_families.py

**Files:**
- Modify: `core/target_families.py:928` (insert after `erd_accessories`, before `rick_owens_geobasket`)

- [ ] **Step 1: Add `erd_grails_tier1` family**

Insert after line 928 (closing `}` of `erd_accessories`):

```python
    "erd_grails_tier1": {
        "canonical": "enfants riches deprimes classic logo hoodie",
        "aliases": [
            "enfants riches deprimes classic logo hoodie",
            "enfants riches deprimes classic logo tee",
            "enfants riches deprimes safety pin earring",
            "enfants riches deprimes classic logo long sleeve",
            "erd classic logo hoodie",
            "erd classic logo tee",
            "erd safety pin earring",
            "erd classic logo long sleeve",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "enfants riches deprimes classic logo hoodie",
            "enfants riches deprimes classic logo tee",
            "enfants riches deprimes safety pin earring",
            "enfants riches deprimes classic logo long sleeve",
        ],
        "demoted_queries": [],
    },
```

- [ ] **Step 2: Add `erd_trending` family**

```python
    "erd_trending": {
        "canonical": "enfants riches deprimes bennys video hoodie",
        "aliases": [
            "enfants riches deprimes bennys video hoodie",
            "enfants riches deprimes menendez hoodie",
            "enfants riches deprimes viper room hat",
            "enfants riches deprimes teenage snuff tee",
            "enfants riches deprimes flowers of anger",
            "enfants riches deprimes bohemian scum tee",
            "erd bennys video",
            "erd menendez hoodie",
            "erd viper room hat",
            "erd teenage snuff",
            "erd flowers of anger",
            "erd bohemian scum",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "enfants riches deprimes bennys video hoodie",
            "enfants riches deprimes menendez hoodie",
            "enfants riches deprimes viper room hat",
            "enfants riches deprimes teenage snuff tee",
            "enfants riches deprimes flowers of anger",
            "enfants riches deprimes bohemian scum tee",
        ],
        "demoted_queries": [],
    },
```

- [ ] **Step 3: Add `erd_premium_outerwear` family**

```python
    "erd_premium_outerwear": {
        "canonical": "enfants riches deprimes spanish elegy jacket",
        "aliases": [
            "enfants riches deprimes spanish elegy jacket",
            "enfants riches deprimes god with revolver",
            "erd spanish elegy",
            "erd god with revolver",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "enfants riches deprimes spanish elegy jacket",
            "enfants riches deprimes god with revolver",
        ],
        "demoted_queries": [],
    },
```

- [ ] **Step 4: Add `erd_collector` family**

```python
    "erd_collector": {
        "canonical": "enfants riches deprimes frozen beauties flannel",
        "aliases": [
            "enfants riches deprimes frozen beauties flannel",
            "enfants riches deprimes le rosey tee",
            "erd frozen beauties",
            "erd le rosey",
        ],
        "broad_allowed": False,
        "allowed_queries": [
            "enfants riches deprimes frozen beauties flannel",
            "enfants riches deprimes le rosey tee",
        ],
        "demoted_queries": [],
    },
```

- [ ] **Step 5: Update `erd_bottoms` — add menendez pants**

At `core/target_families.py:899-912`, add to aliases and allowed_queries:

In aliases (after `"enfants riches deprimes denim"`):
```python
            "enfants riches deprimes menendez pants",
            "erd menendez pants",
```

In allowed_queries (after `"enfants riches deprimes jeans"`):
```python
            "enfants riches deprimes menendez pants",
```

- [ ] **Step 6: Update `erd_accessories` — add rose buckle belt**

At `core/target_families.py:913-928`, add to aliases and allowed_queries:

In aliases (after `"enfants riches deprimes cap"`):
```python
            "enfants riches deprimes rose buckle belt",
            "erd rose buckle belt",
```

In allowed_queries (after `"enfants riches deprimes belt"`):
```python
            "enfants riches deprimes rose buckle belt",
```

- [ ] **Step 7: Verify families load**

Run: `python -c "from core.target_families import family_id_map; fam = family_id_map(); print([k for k in fam if 'classic logo' in k or 'bennys' in k or 'frozen' in k or 'spanish' in k])"`

Expected: List showing the 4 new canonical queries mapped correctly.

- [ ] **Step 8: Commit**

```
git add core/target_families.py
git commit -m "feat: add 4 ERD piece-specific families (grails, trending, premium outerwear, collector)"
```

---

### Task 2: Add quirky aliases + promoted queries to query_normalization.py

**Files:**
- Modify: `core/query_normalization.py:13-43` (QUERY_ALIASES) and `core/query_normalization.py:126-137` (PROMOTED_LIQUIDITY_QUERIES ERD section)

- [ ] **Step 1: Add 4 quirky aliases to QUERY_ALIASES**

After the existing ERD aliases (around line 38, before `"bottega veneta orbit sneakers"`):

```python
    # ERD piece-specific quirky aliases (structural aliases handled by target_families)
    "erd benny's video": "enfants riches deprimes bennys video hoodie",
    "erd safety pin": "enfants riches deprimes safety pin earring",
    "erd rose buckle": "enfants riches deprimes rose buckle belt",
    "erd menendez": "enfants riches deprimes menendez hoodie",
```

- [ ] **Step 2: Add 16 piece-specific queries to PROMOTED_LIQUIDITY_QUERIES**

After the existing ERD section (line 137, after `"enfants riches deprimes bomber"`):

```python
    # ERD piece-specific (proven liquid, March 2026 research)
    "enfants riches deprimes classic logo hoodie",
    "enfants riches deprimes classic logo tee",
    "enfants riches deprimes safety pin earring",
    "enfants riches deprimes classic logo long sleeve",
    "enfants riches deprimes bennys video hoodie",
    "enfants riches deprimes menendez hoodie",
    "enfants riches deprimes viper room hat",
    "enfants riches deprimes teenage snuff tee",
    "enfants riches deprimes flowers of anger",
    "enfants riches deprimes bohemian scum tee",
    "enfants riches deprimes god with revolver",
    "enfants riches deprimes spanish elegy jacket",
    "enfants riches deprimes menendez pants",
    "enfants riches deprimes rose buckle belt",
    "enfants riches deprimes frozen beauties flannel",
    "enfants riches deprimes le rosey tee",
```

- [ ] **Step 3: Verify normalization and promotion**

Run: `python -c "from core.query_normalization import normalize_query, is_promoted_query; print(normalize_query('erd benny\\'s video')); print(is_promoted_query('enfants riches deprimes classic logo hoodie'))"`

Expected: `enfants riches deprimes bennys video hoodie` and `True`.

- [ ] **Step 4: Commit**

```
git add core/query_normalization.py
git commit -m "feat: add ERD piece-specific aliases and promote 16 queries"
```

---

### Task 3: Add queries to CORE/EXTENDED/LONGTAIL target pools

**Files:**
- Modify: `trend_engine.py:148-150` (CORE_TARGETS ERD section), `trend_engine.py:244-249` (EXTENDED_TARGETS ERD section), `trend_engine.py:327-351` (LONGTAIL_TARGETS)

- [ ] **Step 1: Add 4 piece-specific queries to CORE_TARGETS**

Replace `trend_engine.py:148-150` (existing ERD section):

```python
    # ERD
    "enfants riches deprimes hoodie",
    "enfants riches deprimes leather jacket",
```

With:

```python
    # ERD (generic + piece-specific grails)
    "enfants riches deprimes hoodie",
    "enfants riches deprimes leather jacket",
    "enfants riches deprimes classic logo hoodie",
    "enfants riches deprimes classic logo tee",
    "enfants riches deprimes safety pin earring",
    "enfants riches deprimes classic logo long sleeve",
```

- [ ] **Step 2: Add 10 piece-specific queries to EXTENDED_TARGETS**

Replace `trend_engine.py:244-249` (existing ERD section):

```python
    # ERD (full line)
    "enfants riches deprimes tee", "enfants riches deprimes long sleeve",
    "enfants riches deprimes denim jacket", "enfants riches deprimes jeans",
    "enfants riches deprimes hat", "enfants riches deprimes belt",
    "enfants riches deprimes sweater", "enfants riches deprimes flannel",
    "enfants riches deprimes bomber",
```

With:

```python
    # ERD (generic categories)
    "enfants riches deprimes tee", "enfants riches deprimes long sleeve",
    "enfants riches deprimes denim jacket", "enfants riches deprimes jeans",
    "enfants riches deprimes hat", "enfants riches deprimes belt",
    "enfants riches deprimes sweater", "enfants riches deprimes flannel",
    "enfants riches deprimes bomber",
    # ERD piece-specific (trending + premium + existing family additions)
    "enfants riches deprimes bennys video hoodie",
    "enfants riches deprimes menendez hoodie",
    "enfants riches deprimes viper room hat",
    "enfants riches deprimes teenage snuff tee",
    "enfants riches deprimes flowers of anger",
    "enfants riches deprimes bohemian scum tee",
    "enfants riches deprimes spanish elegy jacket",
    "enfants riches deprimes god with revolver",
    "enfants riches deprimes menendez pants",
    "enfants riches deprimes rose buckle belt",
```

- [ ] **Step 3: Add 2 collector queries to LONGTAIL_TARGETS**

At `trend_engine.py:351` (end of LONGTAIL_TARGETS, before `]`), add:

```python
    # ERD collector/grail pieces
    "enfants riches deprimes frozen beauties flannel",
    "enfants riches deprimes le rosey tee",
```

- [ ] **Step 4: Verify target pools**

Run: `python -c "from trend_engine import CORE_TARGETS, EXTENDED_TARGETS, LONGTAIL_TARGETS; erd_core = [t for t in CORE_TARGETS if 'classic logo' in t or 'safety pin' in t]; erd_ext = [t for t in EXTENDED_TARGETS if 'bennys' in t or 'menendez' in t or 'viper' in t]; erd_lt = [t for t in LONGTAIL_TARGETS if 'frozen' in t or 'le rosey' in t]; print(f'CORE: {len(erd_core)}, EXTENDED: {len(erd_ext)}, LONGTAIL: {len(erd_lt)}')"`

Expected: `CORE: 4, EXTENDED: 3, LONGTAIL: 2` (spot check — full count is 4/10/2)

- [ ] **Step 5: Commit**

```
git add trend_engine.py
git commit -m "feat: place 16 ERD piece-specific queries in CORE/EXTENDED/LONGTAIL pools"
```

---

### Task 4: Add 8 ERD blue chip targets

**Files:**
- Modify: `core/blue_chip_targets.py:365` (insert after Number Nine section, before The Soloist)

- [ ] **Step 1: Add ERD BlueChipTarget entries**

After line 365 (`BlueChipTarget("number nine boots", ...)`), before `# The Soloist`:

```python

    # Enfants Riches Déprimés — Piece-specific blue chips
    BlueChipTarget("enfants riches deprimes classic logo hoodie", "fashion", 0.30, 0.45, 6, 1600, "preferred", 9, "Most liquid ERD piece"),
    BlueChipTarget("enfants riches deprimes classic logo tee", "fashion", 0.35, 0.50, 8, 900, "preferred", 9, "Highest volume ERD listing"),
    BlueChipTarget("enfants riches deprimes safety pin earring", "fashion", 0.30, 0.45, 6, 400, "preferred", 9, "Most iconic ERD accessory"),
    BlueChipTarget("enfants riches deprimes bennys video hoodie", "fashion", 0.25, 0.40, 5, 2000, "preferred", 8, "Film reference, cult following"),
    BlueChipTarget("enfants riches deprimes menendez hoodie", "fashion", 0.30, 0.45, 5, 1400, "preferred", 8, "Trend-driven, true crime wave"),
    BlueChipTarget("enfants riches deprimes viper room hat", "fashion", 0.35, 0.55, 4, 10000, "preferred", 7, "C&D piece, wide price range"),
    BlueChipTarget("enfants riches deprimes spanish elegy jacket", "fashion", 0.25, 0.40, 4, 6000, "preferred", 7, "Premium moto leather"),
    BlueChipTarget("enfants riches deprimes frozen beauties flannel", "fashion", 0.30, 0.50, 3, 4500, "preferred", 6, "Only 50 made, Kanye co-sign"),
```

- [ ] **Step 2: Verify blue chip loads**

Run: `python -c "from core.blue_chip_targets import BLUE_CHIP_FASHION; erd = [t for t in BLUE_CHIP_FASHION if 'enfants' in t.query]; print(f'{len(erd)} ERD blue chip targets'); [print(f'  {t.query}: liq={t.liquidity_score}, max_price={t.max_price}') for t in erd]"`

Expected: 8 ERD blue chip targets listed.

- [ ] **Step 3: Commit**

```
git add core/blue_chip_targets.py
git commit -m "feat: add 8 ERD piece-specific blue chip targets"
```

---

### Task 5: Update pricing anchors

**Files:**
- Modify: `api/services/pricing.py:99-100` (both ERD keys)

- [ ] **Step 1: Update `"enfants riches deprimes"` pricing**

Replace line 99:

```python
    "enfants riches deprimes": {"jacket": 1500, "denim jacket": 800, "bomber": 1200, "pants": 400, "jeans": 500, "shirt": 400, "tee": 400, "long sleeve": 300, "hoodie": 500, "sweater": 600, "flannel": 400, "hat": 200, "belt": 500, "default": 400},
```

With:

```python
    "enfants riches deprimes": {"jacket": 2000, "leather jacket": 2500, "denim jacket": 1000, "bomber": 1200, "flannel": 600, "pants": 450, "jeans": 500, "shirt": 450, "tee": 500, "long sleeve": 450, "hoodie": 750, "sweater": 650, "hat": 400, "belt": 700, "earring": 250, "default": 450},
```

- [ ] **Step 2: Update `"erd"` pricing (mirror)**

Replace line 100:

```python
    "erd": {"jacket": 1500, "denim jacket": 800, "bomber": 1200, "pants": 400, "jeans": 500, "shirt": 400, "tee": 400, "long sleeve": 300, "hoodie": 500, "sweater": 600, "flannel": 400, "hat": 200, "belt": 500, "default": 400},
```

With:

```python
    "erd": {"jacket": 2000, "leather jacket": 2500, "denim jacket": 1000, "bomber": 1200, "flannel": 600, "pants": 450, "jeans": 500, "shirt": 450, "tee": 500, "long sleeve": 450, "hoodie": 750, "sweater": 650, "hat": 400, "belt": 700, "earring": 250, "default": 450},
```

- [ ] **Step 3: Commit**

```
git add api/services/pricing.py
git commit -m "feat: update ERD pricing anchors to March 2026 market values"
```

---

### Task 6: Add JP query translations

**Files:**
- Modify: `core/jp_query_translator.py:90+` (PRODUCT_TRANSLATIONS dict)

- [ ] **Step 1: Add 15 ERD piece-specific translations**

Add after the existing product translations (before the closing `}` of PRODUCT_TRANSLATIONS, or grouped with other piece-specific terms). Insert a section comment:

```python
    # ── ERD piece-specific ───────────────────────────────────────────────────
    "classic logo hoodie":      "クラシックロゴフーディー",
    "classic logo tee":         "クラシックロゴTシャツ",
    "classic logo long sleeve": "クラシックロゴロングスリーブ",
    "safety pin earring":       "セーフティピンイヤリング",
    "bennys video":             "ベニーズビデオ",
    "menendez":                 "メネンデス",
    "viper room":               "バイパールーム",
    "teenage snuff":            "ティーンエイジスナッフ",
    "flowers of anger":         "フラワーズオブアンガー",
    "god with revolver":        "ゴッドウィズリボルバー",
    "spanish elegy":            "スパニッシュエレジー",
    "rose buckle belt":         "ローズバックルベルト",
    "bohemian scum":            "ボヘミアンスカム",
    "frozen beauties":          "フローズンビューティーズ",
    "le rosey":                 "ル・ロゼ",
```

**Note:** The module header says "Sorted longest-first at module init for greedy matching" — the runtime re-sorts by string length, so insertion position in the dict doesn't matter for correctness. Append anywhere convenient (end of dict is fine).

- [ ] **Step 2: Verify JP translation**

Run: `python -c "from core.jp_query_translator import build_japan_targets; targets = build_japan_targets(['enfants riches deprimes classic logo hoodie', 'enfants riches deprimes bennys video hoodie']); [print(f'{t}') for t in targets[:4]]"`

Expected: Japanese query strings containing katakana translations.

- [ ] **Step 3: Commit**

```
git add core/jp_query_translator.py
git commit -m "feat: add 15 ERD piece-specific JP translations for Yahoo Auctions"
```

---

### Task 7: Expand auth rules

**Files:**
- Modify: `core/authenticity_v2.py:216-222` (ERD BRAND_RULES entry)

- [ ] **Step 1: Update ERD auth config**

Replace `core/authenticity_v2.py:216-222`:

```python
    "enfants riches deprimes": {
        "price_floor": 150,
        "price_typical_min": 300,
        "auth_keywords": ["erd", "henri alexander levy", "made in usa"],
        "rep_misspellings": ["enfant riche deprime"],
        "high_rep_categories": [],
    },
```

With:

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
    },
```

- [ ] **Step 2: Commit**

```
git add core/authenticity_v2.py
git commit -m "feat: expand ERD auth keywords and rep misspellings"
```

---

### Task 8: Add season scoring patterns

**Files:**
- Modify: `scrapers/seasons.py:1089-1090` (after existing ERD patterns, before `],`)

- [ ] **Step 1: Add 12 piece-specific season patterns**

Insert after line 1089 (`(r"sample|1.?of|one.?of", 2.5, "Sample/1-of-1"),`), before the closing `],`:

```python
        # Piece-specific multipliers (March 2026 research)
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

- [ ] **Step 2: Commit**

```
git add scrapers/seasons.py
git commit -m "feat: add 12 ERD piece-specific season scoring patterns"
```

---

### Task 9: Update smart_scrape.py ERD queries

**Files:**
- Modify: `scrapers/smart_scrape.py:140-143` (ERD section)

- [ ] **Step 1: Expand ERD section in smart_scrape.py**

Replace lines 140-143:

```python
    # ERD
    "enfants riches deprimes",
    "erd hoodie",
    "erd tee",
```

With:

```python
    # ERD (generic + piece-specific)
    "enfants riches deprimes",
    "erd hoodie",
    "erd tee",
    "enfants riches deprimes classic logo hoodie",
    "enfants riches deprimes classic logo tee",
    "enfants riches deprimes safety pin earring",
    "enfants riches deprimes bennys video hoodie",
    "enfants riches deprimes menendez hoodie",
    "enfants riches deprimes viper room hat",
```

- [ ] **Step 2: Commit**

```
git add scrapers/smart_scrape.py
git commit -m "feat: add ERD piece-specific queries to smart_scrape"
```

---

### Task 10: End-to-end smoke test

**Files:**
- No file changes — verification only

- [ ] **Step 1: Verify all imports work**

Run: `python -c "from core.target_families import family_id_map, family_policy_map; from core.query_normalization import normalize_query, is_promoted_query, is_demoted_query; from trend_engine import CORE_TARGETS, EXTENDED_TARGETS, LONGTAIL_TARGETS; from core.blue_chip_targets import BLUE_CHIP_FASHION, get_targets_by_tier; from core.jp_query_translator import build_japan_targets; print('All imports OK')"`

Expected: `All imports OK`

- [ ] **Step 2: Verify ERD query count in each pool**

Run: `python -c "
from trend_engine import CORE_TARGETS, EXTENDED_TARGETS, LONGTAIL_TARGETS
from core.query_normalization import is_promoted_query
erd_core = [t for t in CORE_TARGETS if 'enfants riches deprimes' in t]
erd_ext = [t for t in EXTENDED_TARGETS if 'enfants riches deprimes' in t]
erd_lt = [t for t in LONGTAIL_TARGETS if 'enfants riches deprimes' in t]
erd_promoted = [t for t in erd_core + erd_ext + erd_lt if is_promoted_query(t)]
print(f'CORE: {len(erd_core)} ({len([t for t in erd_core if \"classic\" in t or \"safety\" in t])} piece-specific)')
print(f'EXTENDED: {len(erd_ext)} ({len([t for t in erd_ext if \"bennys\" in t or \"menendez\" in t or \"viper\" in t or \"teenage\" in t or \"flowers\" in t or \"bohemian\" in t or \"spanish\" in t or \"god with\" in t or \"rose buckle\" in t])} piece-specific)')
print(f'LONGTAIL: {len(erd_lt)} ({len([t for t in erd_lt if \"frozen\" in t or \"le rosey\" in t])} piece-specific)')
print(f'Promoted: {len(erd_promoted)} of {len(erd_core) + len(erd_ext) + len(erd_lt)} total')
"`

Expected: CORE 6 (4 piece-specific), EXTENDED 19 (10 piece-specific), LONGTAIL 2 (2 piece-specific). All 16 piece-specific promoted.

- [ ] **Step 3: Verify family dedup works**

Run: `python -c "
from core.query_normalization import family_id_for_query
queries = [
    'enfants riches deprimes classic logo hoodie',
    'enfants riches deprimes classic logo tee',
    'enfants riches deprimes bennys video hoodie',
    'enfants riches deprimes menendez hoodie',
    'enfants riches deprimes spanish elegy jacket',
    'enfants riches deprimes frozen beauties flannel',
    'enfants riches deprimes hoodie',
]
for q in queries:
    print(f'{q[:45]:45s} -> {family_id_for_query(q)}')
"`

Expected: classic logo hoodie/tee map to same family, bennys/menendez map to same family, spanish elegy/god with revolver map to same family, frozen/le rosey map to same family, generic hoodie maps to `erd_tops`.

- [ ] **Step 4: Verify no conflicts with demoted queries**

Run: `python -c "
from core.query_normalization import is_demoted_query
piece_queries = [
    'enfants riches deprimes classic logo hoodie',
    'enfants riches deprimes bennys video hoodie',
    'enfants riches deprimes viper room hat',
    'enfants riches deprimes frozen beauties flannel',
]
for q in piece_queries:
    if is_demoted_query(q):
        print(f'CONFLICT: {q} is demoted!')
    else:
        print(f'OK: {q}')
"`

Expected: All OK, no conflicts.

- [ ] **Step 5: Final commit**

```
git add -A
git commit -m "chore: verify ERD piece-specific query integration (smoke test passed)"
```

Only commit if there are unstaged fixes discovered during verification.
