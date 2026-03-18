# Pipeline Hardening Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate all identified pipeline weaknesses — silent failures, data quality risks, connection leaks, wrong sorting, stale frontend display.

**Architecture:** Targeted fixes to each pipeline layer (gap_hunter, DB, API, frontend) in dependency order. No refactoring — surgical fixes only.

**Tech Stack:** Python/SQLite (backend), React/TypeScript (frontend)

---

## File Map

| File | Changes |
|------|---------|
| `gap_hunter.py` | Fix silent exception logging, comp validator fallback, bimodal confidence penalty |
| `db/sqlite_models.py` | Add `count_items()`, fix NULL sort ordering |
| `api/main.py` | Use `count_items()` for O(1) pagination, normalize margin in API response |
| `frontend-react/src/components/DealCard.tsx` | Add image onError fallback, cap est_days_to_sell display |

---

### Task 1: Fix silent exception logging in gap_hunter

**Files:**
- Modify: `gap_hunter.py:2565`

- [ ] **Step 1: Change debug to warning for DB persist failures**

In `gap_hunter.py`, find:
```python
            except Exception as e:
                logger.debug(f"    DB persist failed (non-fatal): {e}")
```
Change to:
```python
            except Exception as e:
                logger.warning(f"    ⚠️ DB persist failed: {e}")
```

- [ ] **Step 2: Verify compilation**

Run: `python3 -c "import py_compile; py_compile.compile('gap_hunter.py', doraise=True); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add gap_hunter.py
git commit -m "fix: surface DB persist failures as warnings instead of debug"
```

---

### Task 2: Fix comp validator fallback (stop using bad comps)

**Files:**
- Modify: `gap_hunter.py:1238-1245`

Currently when comp validator leaves 1-2 surviving comps (below min_comps=3), the code keeps the *original unfiltered set* including bad comps. Fix: return None so the deal is skipped.

- [ ] **Step 1: Fix the elif branch**

Find:
```python
                elif validation.surviving_count == 0:
                    logger.info(f"  ❌ Comp validator rejected all comps for '{query[:50]}'")
                    return None
                # 1-2 survive: keep original set, note low confidence
```
Change to:
```python
                elif validation.surviving_count < 3:
                    logger.info(f"  ❌ Comp validator: only {validation.surviving_count} comps survived for '{query[:50]}' (need 3)")
                    return None
```

- [ ] **Step 2: Verify compilation**

Run: `python3 -c "import py_compile; py_compile.compile('gap_hunter.py', doraise=True); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add gap_hunter.py
git commit -m "fix: reject deals with fewer than 3 surviving comps instead of using bad data"
```

---

### Task 3: Add confidence penalty for bimodal price distributions

**Files:**
- Modify: `gap_hunter.py:1251-1255`

When prices have a 2.5x spread and we use the lower half, also force a confidence penalty so the quality score reflects the uncertainty.

- [ ] **Step 1: Add confidence penalty after bimodal detection**

Find:
```python
                if p25 > 0 and p75 > p25 * 2.5:
                    logger.warning(f"  ⚠️ Bimodal price distribution detected for '{query}': p25=${p25:.0f}, p75=${p75:.0f} (ratio {p75/p25:.1f}x)")
                    # Use only lower half — more conservative
                    prices = prices[:len(prices) // 2]
                    logger.info(f"  📉 Using lower half of comps ({len(prices)} items) for conservative estimate")
```
Change to:
```python
                if p25 > 0 and p75 > p25 * 2.5:
                    logger.warning(f"  ⚠️ Bimodal price distribution detected for '{query}': p25=${p25:.0f}, p75=${p75:.0f} (ratio {p75/p25:.1f}x)")
                    # Use only lower half — more conservative
                    prices = prices[:len(prices) // 2]
                    comp_confidence_penalty = max(comp_confidence_penalty, 15)
                    logger.info(f"  📉 Using lower half of comps ({len(prices)} items), +{comp_confidence_penalty}pt penalty")
```

- [ ] **Step 2: Verify compilation**

Run: `python3 -c "import py_compile; py_compile.compile('gap_hunter.py', doraise=True); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add gap_hunter.py
git commit -m "fix: add quality score penalty for bimodal price distributions"
```

---

### Task 4: Fix NULL sort ordering in DB queries

**Files:**
- Modify: `db/sqlite_models.py:614-624`

NULL values in demand_score, est_days_to_sell, comp_count sort to the top in SQLite. Fix with NULLS LAST.

- [ ] **Step 1: Update sort mapping**

Find:
```python
    order_map = {
        "newest": "id DESC",
        "grade_asc": "grade ASC, demand_score DESC",
        "profit_desc": "COALESCE(exact_profit, our_price - source_price) DESC",
        "margin_desc": "margin_percent DESC",
        "sellthrough_desc": "demand_score DESC",
        "days_asc": "sell_through_days ASC",
        "price_asc": "our_price ASC",
        "price_desc": "our_price DESC",
        "sold_count_desc": "comp_count DESC",
    }
```
Change to:
```python
    order_map = {
        "newest": "id DESC",
        "grade_asc": "grade ASC NULLS LAST, demand_score DESC NULLS LAST",
        "profit_desc": "COALESCE(exact_profit, our_price - source_price) DESC NULLS LAST",
        "margin_desc": "margin_percent DESC NULLS LAST",
        "sellthrough_desc": "demand_score DESC NULLS LAST",
        "days_asc": "sell_through_days ASC NULLS LAST",
        "price_asc": "our_price ASC NULLS LAST",
        "price_desc": "our_price DESC NULLS LAST",
        "sold_count_desc": "comp_count DESC NULLS LAST",
    }
```

- [ ] **Step 2: Verify it works**

Run: `python3 -c "from db.sqlite_models import get_items; items = get_items(status='active', sort='grade_asc', limit=5); print('OK:', len(items), 'items')"`

- [ ] **Step 3: Commit**

```bash
git add db/sqlite_models.py
git commit -m "fix: sort NULLs last in item queries to prevent unknown items ranking first"
```

---

### Task 5: Add efficient count_items() for pagination

**Files:**
- Modify: `db/sqlite_models.py` (add function after `get_items`)
- Modify: `api/main.py:230-237` (use it)

- [ ] **Step 1: Add count_items function to sqlite_models.py**

Add after the `get_items` function:

```python
def count_items(
    status: Optional[str] = None,
    brand: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_sold_count: Optional[int] = 3,
    season: Optional[str] = None,
    year: Optional[int] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    created_after: Optional[str] = None,
) -> int:
    """Count items matching filters using SQL COUNT(*) instead of fetching all rows."""
    conn = _get_conn()
    c = conn.cursor()
    clauses: List[str] = []
    params: list = []

    if status:
        clauses.append("status = ?")
        params.append(status)
    if brand:
        clauses.append("LOWER(brand) = LOWER(?)")
        params.append(brand)
    if category:
        clauses.append("LOWER(category) = LOWER(?)")
        params.append(category)
    if min_price is not None:
        clauses.append("our_price >= ?")
        params.append(min_price)
    if max_price is not None:
        clauses.append("our_price <= ?")
        params.append(max_price)
    if min_sold_count is not None:
        clauses.append("comp_count >= ?")
        params.append(min_sold_count)
    if season:
        clauses.append("UPPER(exact_season) = UPPER(?)")
        params.append(season)
    if year is not None:
        clauses.append("exact_year = ?")
        params.append(year)
    if year_min is not None:
        clauses.append("exact_year >= ?")
        params.append(year_min)
    if year_max is not None:
        clauses.append("exact_year <= ?")
        params.append(year_max)
    if created_after:
        clauses.append("created_at >= ?")
        params.append(created_after)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    c.execute(f"SELECT COUNT(*) FROM items {where}", params)
    count = c.fetchone()[0]
    conn.close()
    return count
```

- [ ] **Step 2: Update api/main.py to use count_items**

Add `count_items` to the import from `db.sqlite_models`.

Then replace the total count block:
```python
    # Get total count (simplified - would need separate count query for pagination)
    all_items = get_items(status="active", brand=brand, category=category, min_price=min_price, max_price=max_price, **sold_count_kwarg, season=season, year=year, year_min=year_min, year_max=year_max, sort=sort, limit=1000, created_after=created_after)
    if needs_review is not None:
        if needs_review:
            all_items = [i for i in all_items if getattr(i, 'needs_review', 0)]
        else:
            all_items = [i for i in all_items if not getattr(i, 'needs_review', 0)]
    total = len(all_items)
```
With:
```python
    total = count_items(
        status="active", brand=brand, category=category,
        min_price=min_price, max_price=max_price, **sold_count_kwarg,
        season=season, year=year, year_min=year_min, year_max=year_max,
        created_after=created_after,
    )
```

- [ ] **Step 3: Verify API imports**

Run: `python3 -c "from api.main import app; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add db/sqlite_models.py api/main.py
git commit -m "perf: use SQL COUNT(*) for pagination instead of fetching all items"
```

---

### Task 6: Normalize margin in API response

**Files:**
- Modify: `api/main.py:85` (ItemResponse.from_db)

- [ ] **Step 1: Normalize margin_percent to decimal (0-1) in from_db**

Find in `ItemResponse.from_db`:
```python
        margin_percent=item.margin_percent,
```
Change to:
```python
        margin_percent=(item.margin_percent / 100) if item.margin_percent and item.margin_percent > 1 else (item.margin_percent or 0),
```

And do the same for `exact_margin`:
```python
        exact_margin=item.exact_margin,
```
Change to:
```python
        exact_margin=(item.exact_margin / 100) if item.exact_margin and item.exact_margin > 1 else (item.exact_margin or 0),
```

- [ ] **Step 2: Verify**

Run: `python3 -c "from api.main import ItemResponse; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add api/main.py
git commit -m "fix: normalize margin to 0-1 decimal range in API response"
```

---

### Task 7: Fix frontend image error handling and days-to-sell display

**Files:**
- Modify: `frontend-react/src/components/DealCard.tsx`

- [ ] **Step 1: Add onError fallback to both image tags**

Find the grid view image (should be around line 115):
```tsx
    <img
      src={item.images[0]}
      alt={item.title}
      className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-500"
      loading="lazy"
    />
```
Change to:
```tsx
    <img
      src={item.images[0]}
      alt={item.title}
      className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-500"
      loading="lazy"
      onError={(e) => { e.currentTarget.style.display = 'none'; }}
    />
```

Find the list view image (should be around line 43):
```tsx
  <img src={item.images[0]} alt="" className="w-full h-full object-cover" loading="lazy" />
```
Change to:
```tsx
  <img src={item.images[0]} alt="" className="w-full h-full object-cover" loading="lazy" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
```

- [ ] **Step 2: Cap est_days_to_sell display**

Find:
```tsx
{item.est_days_to_sell ? (
  <div className="flex items-center gap-1">
    <Clock className="w-2.5 h-2.5" />
    <span>~{item.est_days_to_sell.toFixed(0)}d</span>
  </div>
) : null}
```
Change to:
```tsx
{item.est_days_to_sell && item.est_days_to_sell < 365 ? (
  <div className="flex items-center gap-1">
    <Clock className="w-2.5 h-2.5" />
    <span>~{item.est_days_to_sell.toFixed(0)}d</span>
  </div>
) : null}
```

- [ ] **Step 3: Commit**

```bash
git add frontend-react/src/components/DealCard.tsx
git commit -m "fix: add image error fallback and cap days-to-sell display at 365"
```

---

### Task 8: Final verification

- [ ] **Step 1: Run full compilation check**

```bash
python3 -c "
import py_compile
for f in ['gap_hunter.py', 'db/sqlite_models.py', 'api/main.py']:
    py_compile.compile(f, doraise=True)
    print(f'  ✅ {f}')
print('All files compile OK')
"
```

- [ ] **Step 2: Run integration test**

```bash
python3 -c "
from db.sqlite_models import get_items, count_items, init_db
init_db()
items = get_items(status='active', sort='grade_asc', limit=10)
count = count_items(status='active')
print(f'get_items: {len(items)} items')
print(f'count_items: {count}')
assert count >= len(items), 'Count should be >= page size'
print('All OK')
"
```

- [ ] **Step 3: Verify frontend builds**

```bash
cd frontend-react && npx tsc --noEmit 2>&1 | head -20
```
