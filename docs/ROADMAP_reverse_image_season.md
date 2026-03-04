# Reverse Image Search + Exact Season Implementation Plan

## Overview
Transform fuzzy text-based matching into **exact product fingerprinting** by:
1. Using **reverse image search** to identify the exact product across platforms
2. Extracting **exact season/year** from matches to power precision filtering

---

## Current State vs Target State

| Aspect | Current | Target |
|--------|---------|--------|
| **Product ID** | Title parsing (fuzzy) | Image hash + exact product catalog |
| **Season Detection** | Regex on titles (570 patterns) | Exact season/year from sold comps |
| **Comp Matching** | Text similarity scoring | Same-image verified comps |
| **Confidence** | "high/medium/low" | Exact match count + price band width |

---

## Phase 1: Reverse Image Search Foundation (Week 1)

### 1.1 Image Hashing & Storage
**New file: `scrapers/image_fingerprinter.py`**
- Perceptual hashing (pHash) for each item image
- Store hash in DB: `items.image_hash`
- Build reverse index: hash → [item_ids]
- Deduplicate: same image = same product

### 1.2 Google Lens / TinEye Integration
**New file: `scrapers/reverse_image.py`**
- Search item images via Google Lens API or TinEye
- Extract product names from result titles
- Cross-reference with Grailed sold listings
- Store matches in: `product_matches` table

### 1.3 Product Catalog Table
```sql
-- New table: products
CREATE TABLE products (
    id PRIMARY KEY,
    canonical_name,           -- "Rick Owens Geobasket Black Leather"
    canonical_brand,
    canonical_category,
    first_seen_date,
    image_hash,               -- pHash of reference image
    grailed_search_query,     -- Optimized search term
    verified_sales_count,     -- How many sold comps confirmed
    avg_sell_price,
    price_confidence,         -- tight/wide/unknown
    typical_season,           -- e.g., "FW18"
    typical_release_year
);
```

---

## Phase 2: Exact Season/Year Extraction (Week 2)

### 2.1 Season Parser Enhancement
**Enhanced: `scrapers/seasons.py`**
```python
def extract_exact_season(title: str) -> Tuple[str, int]:
    """
    Returns: ("FW", 2018) or ("SS", 2005)
    Handles: AW01, FW2005, Fall-Winter 2018, SS97, etc.
    """
    # Normalize: AW/FW/Fall → "FW", SS/Spring → "SS"
    # Extract 2-digit or 4-digit year
    # Return canonical (season_code, year)
```

### 2.2 Season from Sold Comps
**In: `scrapers/comp_matcher.py`**
- When fetching sold comps, extract season from each comp title
- Aggregate: "FW2018: 12 sales, avg $450", "SS2019: 8 sales, avg $380"
- Store in: `product_seasons` table

### 2.3 Database Schema Update
```sql
-- Add to items table:
ALTER TABLE items ADD COLUMN exact_season TEXT;      -- "FW"
ALTER TABLE items ADD COLUMN exact_year INTEGER;     -- 2018
ALTER TABLE items ADD COLUMN season_confidence TEXT; -- "confirmed" | "inferred" | "unknown"

-- New table: product_seasons (aggregated from sold comps)
CREATE TABLE product_seasons (
    product_id,
    season_code,        -- "FW" | "SS"
    year,
    sold_count,
    avg_price,
    last_sold_date
);
```

---

## Phase 3: Image-Verified Comp Matching (Week 3)

### 3.1 Smart Comp Matcher v2
**Update: `scrapers/comp_matcher.py`**
```python
async def find_best_comps_v2(brand, title, image_urls) -> CompResult:
    # 1. Try reverse image search first
    similar_images = await reverse_image_search(image_urls[0])
    
    # 2. Filter to same-product sold listings
    verified_comps = []
    for img_match in similar_images:
        if img_match.source == "grailed" and img_match.sold:
            # Verify title similarity
            similarity = score_comp_similarity(parsed, img_match.title)
            if similarity > 0.7:
                verified_comps.append(img_match)
    
    # 3. If image search fails, fall back to text matching
    if len(verified_comps) < 3:
        return await find_best_comps(brand, title)  # v1 fallback
    
    # 4. Return comps with "image_verified" flag
```

### 3.2 Price Confidence Bands
**In: `api/services/pricing.py`**
```python
def calculate_price_confidence(comps: List[ScoredComp]) -> dict:
    prices = [c.price for c in comps]
    return {
        "band_width": max(prices) - min(prices),
        "band_percent": (max(prices) - min(prices)) / mean(prices),
        "confidence": "high" if band_percent < 0.2 else "medium" if < 0.4 else "low",
        "price_range": f"${min(prices)}-${max(prices)}"
    }
```

---

## Phase 4: Pipeline Integration (Week 4)

### 4.1 Scrape Flow Update
**In: `pipeline.py` scrape()**
```python
for item in scraped_items:
    # 1. Generate image hash
    item.image_hash = generate_phash(item.images[0])
    
    # 2. Try to match to existing product
    existing_product = find_product_by_image_hash(item.image_hash)
    
    if existing_product:
        # Use cached product data
        item.product_id = existing_product.id
        item.exact_season = existing_product.typical_season
        item.exact_year = existing_product.typical_release_year
    else:
        # New product - trigger reverse image search
        matches = await reverse_image_search(item.images[0])
        product_data = await create_product_from_matches(matches, item)
        item.product_id = product_data.id
    
    # 3. Save with product linkage
    save_item(item)
```

### 4.2 Qualification Flow Update
**In: `pipeline.py` qualify()**
```python
# Now uses image-verified comps
comp_result = await find_best_comps_v2(
    brand=item.brand,
    title=item.title,
    image_urls=item.images
)

# Extract season from verified comps
seasons = extract_seasons_from_comps(comp_result.top_comps)
item.exact_season = seasons.most_common_season
item.exact_year = seasons.most_common_year
```

### 4.3 New Filters
**API filters in: `api/main.py`**
```python
@app.get("/api/items")
def list_items(
    season: Optional[str] = None,      -- "FW", "SS"
    year: Optional[int] = None,        -- 2018
    year_range: Optional[str] = None,  -- "2015-2020"
    verified_only: bool = False,       -- image-verified products only
    confidence: Optional[str] = None,  -- "high", "medium", "low"
):
```

---

## Technical Implementation Details

### Image Hashing (pHash)
```python
# pip install imagehash Pillow
from PIL import Image
import imagehash

def generate_phash(image_url: str) -> str:
    img = download_image(image_url)
    return str(imagehash.phash(img))  # 64-bit hash
```

### Google Lens API (Option A: Official)
- Requires Google Cloud Vision API key
- Use `PRODUCT_SEARCH` feature
- Cost: ~$3.50 per 1000 requests

### TinEye API (Option B: Easier)
- Commercial reverse image search
- JSON API available
- Good for fashion/product images

### Self-Hosted Alternative (Option C: Long-term)
- CLIP embeddings for image similarity
- Store vectors in sqlite-vss or pgvector
- Requires more setup but zero API costs

---

## Success Metrics

| Metric | Before | Target |
|--------|--------|--------|
| Exact product match rate | ~15% | 70%+ |
| Season accuracy | ~60% (regex) | 90%+ (verified) |
| Price confidence "high" | 20% | 60% |
| False positive alerts | ~30% | <10% |

---

## Quick Win (Immediate Value) ✅ COMPLETE

Before building full image search:

1. ✅ **Add `exact_season` + `exact_year` columns** to items table
2. ✅ **Extract season from sold comp titles** during qualification (no new APIs needed)
3. ✅ **Add season filters** to the API

This gives immediate value while building out the image search pipeline.

**Completed:** 2026-02-09
**Files modified:**
- `db/sqlite_models.py` - Added exact_season, exact_year, season_confidence columns
- `scrapers/seasons.py` - Added extract_exact_season(), aggregate_seasons_from_comps()
- `scrapers/comp_matcher.py` - CompResult now includes season data from comps
- `qualify.py` - QualificationResult saves season data from comp analysis
- `api/main.py` - Added season/year filters to /api/items endpoint

**API Filters Available:**
- `?season=FW` - Filter by season (FW, SS, AW, RESORT, CRUISE, PF)
- `?year=2018` - Filter by exact year
- `?year_min=2015&year_max=2020` - Filter by year range

---

## Status

- [x] Phase 1.1: Image hashing & storage ✅
  - [x] `scrapers/image_fingerprinter.py` - pHash, aHash, dHash, whash generation
  - [x] Hamming distance calculation for similarity matching
  - [x] Database columns: `image_hash`, `image_phash`
  - [x] Deduplication functions: `find_duplicate_by_image_hash()`, `find_similar_by_phash()`
  - [x] Pipeline integration - auto-fingerprint on scrape
  - [x] Dependencies: imagehash, Pillow installed
- [x] Phase 1.2: Reverse image API integration ✅
  - [x] `scrapers/reverse_image.py` - ReverseImageSearcher class
  - [x] SerpAPI (Google Lens) support
  - [x] TinEye API support
  - [x] Fashion platform fallback (Grailed via our DB)
  - [x] ProductIdentifier class - extracts exact product name from matches
  - [x] Price extraction from search results
- [ ] Phase 1.3: Product catalog table
- [x] Phase 2.1: Exact season parser ✅
- [x] Phase 2.2: Season extraction from comps ✅
- [x] Phase 2.3: Database schema update ✅
- [ ] Phase 3.1: Comp matcher v2
- [ ] Phase 3.2: Price confidence bands
- [x] Phase 4.1: Scrape flow update ✅ (auto-fingerprint on scrape)
- [x] Phase 4.2: Qualification flow update ✅ (season from comps + reverse image enhancement)
- [x] Phase 4.3: API filters ✅
  - [x] Image hash fields in API response
  - [x] `pipeline.py fingerprint` command for backfilling
- [x] Quick Win: Season columns + filters ✅
  - [x] Database columns (exact_season, exact_year, season_confidence)
  - [x] Season extraction from sold comp titles
  - [x] API filters (?season=FW&year=2018&year_min=2015&year_max=2020)
  - [x] Frontend season/year filters in sidebar
  - [x] Season badge on item cards
  - [x] Season info in item modal
