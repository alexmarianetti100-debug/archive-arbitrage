# Comp Feedback System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a comp feedback system that links individual sold comps to items, allows accepting/rejecting comps with reason codes, auto re-grades items on rejection, and surfaces comp quality in the UI with links and dates.

**Architecture:** Junction table `item_comps` links items to sold_comps with snapshot fields. During qualification, individual comps are persisted. Rejection triggers re-grade from remaining comp pool. A `regrade_log` table tracks pricing evolution. Quality scores on sold_comps feed back into the comp_matcher scoring function.

**Tech Stack:** SQLite (db), FastAPI (api), React + TanStack Query + Tailwind (frontend), pytest (tests)

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `api/services/comp_feedback.py` | Feedback processing, re-grade logic, quality score updates |
| `frontend-react/src/components/CompTable.tsx` | Comp list with feedback controls |
| `tests/unit/test_comp_feedback.py` | Feedback service tests |
| `tests/unit/test_quality_weight.py` | Quality weight function tests |

### Modified Files
| File | Changes |
|------|---------|
| `db/sqlite_models.py` | Add `item_comps` + `regrade_log` tables, new columns on `sold_comps` + `items`, CRUD functions |
| `api/services/exact_qualification.py` | Persist comp assignments to `item_comps` after scoring |
| `scrapers/comp_matcher.py` | Add `quality_weight()` multiplier to `score_comp_similarity()` |
| `api/main.py` | Add GET/POST comp endpoints |
| `frontend-react/src/types/index.ts` | Add `ItemComp`, `CompFeedbackResponse`, `RegradeResult` types |
| `frontend-react/src/utils/api.ts` | Add `fetchItemComps()`, `submitCompFeedback()` |
| `frontend-react/src/hooks/useApi.ts` | Add `useItemComps()`, `useCompFeedback()` mutation |
| `frontend-react/src/components/ItemDetailPanel.tsx` | Wire in `CompTable` |
| `frontend-react/src/pages/Deals.tsx` | Add needs_review filter |
| `frontend-react/src/components/FilterSidebar.tsx` | Add needs_review toggle |
| `frontend-react/src/components/DealCard.tsx` | Add needs_review badge |

---

## Task 1: Database Schema — New Tables and Columns

**Files:**
- Modify: `db/sqlite_models.py`

This task adds `item_comps`, `regrade_log` tables and new columns on `sold_comps` and `items`.

- [ ] **Step 1: Add item_comps table creation to init_db()**

In `db/sqlite_models.py`, find the `init_db()` function (line ~229). After the existing CREATE TABLE statements (after sold_comps creation around line 363), add:

```python
c.execute("""
    CREATE TABLE IF NOT EXISTS item_comps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL REFERENCES items(id),
        sold_comp_id INTEGER NOT NULL REFERENCES sold_comps(id),
        similarity_score REAL,
        rank INTEGER,
        feedback_status TEXT DEFAULT 'pending',
        rejected_at TEXT,
        rejection_reason TEXT,
        snapshot_title TEXT,
        snapshot_price REAL,
        snapshot_condition TEXT,
        snapshot_source TEXT,
        snapshot_sold_date TEXT,
        snapshot_url TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
""")
c.execute("CREATE INDEX IF NOT EXISTS idx_item_comps_item_id ON item_comps(item_id)")
c.execute("CREATE INDEX IF NOT EXISTS idx_item_comps_sold_comp_id ON item_comps(sold_comp_id)")
c.execute("CREATE INDEX IF NOT EXISTS idx_item_comps_feedback ON item_comps(feedback_status)")
```

- [ ] **Step 2: Add regrade_log table creation to init_db()**

Immediately after item_comps creation:

```python
c.execute("""
    CREATE TABLE IF NOT EXISTS regrade_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL REFERENCES items(id),
        trigger TEXT NOT NULL,
        comps_before INTEGER,
        comps_after INTEGER,
        grade_before TEXT,
        grade_after TEXT,
        price_before REAL,
        price_after REAL,
        margin_before REAL,
        margin_after REAL,
        comp_pool_health REAL,
        rejected_comp_id INTEGER,
        created_at TEXT DEFAULT (datetime('now'))
    )
""")
c.execute("CREATE INDEX IF NOT EXISTS idx_regrade_log_item_id ON regrade_log(item_id)")
```

- [ ] **Step 3: Add new columns to sold_comps via migration**

In the migration section of `init_db()` (where existing ALTER TABLE statements are), add safe migrations:

```python
# Comp feedback columns on sold_comps
for col, typedef in [
    ("times_matched", "INTEGER DEFAULT 0"),
    ("times_rejected", "INTEGER DEFAULT 0"),
    ("rejection_reasons", "TEXT DEFAULT '{}'"),
    ("quality_score", "REAL DEFAULT 1.0"),
    ("last_rejected_at", "TEXT"),
]:
    try:
        c.execute(f"ALTER TABLE sold_comps ADD COLUMN {col} {typedef}")
    except Exception:
        pass
```

- [ ] **Step 4: Add needs_review column to items via migration**

In the same migration section:

```python
try:
    c.execute("ALTER TABLE items ADD COLUMN needs_review INTEGER DEFAULT 0")
except Exception:
    pass
```

- [ ] **Step 5: Add CRUD functions for item_comps**

After the existing `get_sold_comps_stats()` function (line ~830), add:

```python
def save_item_comps(item_id: int, comps: list) -> None:
    """Save comp assignments for an item. Replaces any existing assignments."""
    conn = _get_conn()
    c = conn.cursor()
    # Clear existing assignments
    c.execute("DELETE FROM item_comps WHERE item_id = ?", (item_id,))
    for comp in comps:
        c.execute("""
            INSERT INTO item_comps (
                item_id, sold_comp_id, similarity_score, rank,
                feedback_status, snapshot_title, snapshot_price,
                snapshot_condition, snapshot_source, snapshot_sold_date, snapshot_url
            ) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
        """, (
            item_id,
            comp["sold_comp_id"],
            comp["similarity_score"],
            comp["rank"],
            comp["snapshot_title"],
            comp["snapshot_price"],
            comp["snapshot_condition"],
            comp["snapshot_source"],
            comp["snapshot_sold_date"],
            comp["snapshot_url"],
        ))
        # Increment times_matched on the sold_comp
        c.execute("""
            UPDATE sold_comps
            SET times_matched = COALESCE(times_matched, 0) + 1,
                quality_score = CASE
                    WHEN COALESCE(times_matched, 0) + 1 > 0
                    THEN 1.0 - (CAST(COALESCE(times_rejected, 0) AS REAL) / (COALESCE(times_matched, 0) + 1))
                    ELSE 1.0
                END
            WHERE id = ?
        """, (comp["sold_comp_id"],))
    conn.commit()
    conn.close()


def get_item_comps(item_id: int) -> list:
    """Get all comp assignments for an item."""
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM item_comps
        WHERE item_id = ?
        ORDER BY rank ASC
    """, (item_id,))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def get_active_item_comps(item_id: int) -> list:
    """Get non-rejected comp assignments for an item."""
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM item_comps
        WHERE item_id = ? AND feedback_status != 'rejected'
        ORDER BY rank ASC
    """, (item_id,))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def update_item_comp_feedback(item_comp_id: int, status: str, reason: str = None) -> dict:
    """Update feedback status on an item_comp row. Returns the updated row."""
    from datetime import datetime
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    rejected_at = datetime.utcnow().isoformat() if status == "rejected" else None
    c.execute("""
        UPDATE item_comps
        SET feedback_status = ?, rejected_at = ?, rejection_reason = ?
        WHERE id = ?
    """, (status, rejected_at, reason, item_comp_id))

    c.execute("SELECT * FROM item_comps WHERE id = ?", (item_comp_id,))
    row = dict(c.fetchone())
    conn.commit()
    conn.close()
    return row


def update_sold_comp_rejection(sold_comp_id: int, reason: str) -> None:
    """Increment rejection counters on a sold_comp after feedback."""
    import json
    from datetime import datetime
    conn = _get_conn()
    c = conn.cursor()

    # Get current rejection_reasons
    c.execute("SELECT rejection_reasons, times_matched, times_rejected FROM sold_comps WHERE id = ?", (sold_comp_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return

    current_reasons = json.loads(row[0] or "{}")
    current_reasons[reason] = current_reasons.get(reason, 0) + 1
    times_matched = row[1] or 1
    new_times_rejected = (row[2] or 0) + 1
    new_quality = max(0.0, 1.0 - (new_times_rejected / max(times_matched, 1)))

    c.execute("""
        UPDATE sold_comps
        SET times_rejected = ?,
            rejection_reasons = ?,
            quality_score = ?,
            last_rejected_at = ?
        WHERE id = ?
    """, (new_times_rejected, json.dumps(current_reasons), new_quality,
          datetime.utcnow().isoformat(), sold_comp_id))
    conn.commit()
    conn.close()


def insert_regrade_log(log: dict) -> None:
    """Insert a regrade log entry."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO regrade_log (
            item_id, trigger, comps_before, comps_after,
            grade_before, grade_after, price_before, price_after,
            margin_before, margin_after, comp_pool_health, rejected_comp_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        log["item_id"], log["trigger"], log["comps_before"], log["comps_after"],
        log["grade_before"], log["grade_after"], log["price_before"], log["price_after"],
        log["margin_before"], log["margin_after"], log.get("comp_pool_health"),
        log.get("rejected_comp_id"),
    ))
    conn.commit()
    conn.close()


def set_item_needs_review(item_id: int, needs_review: bool) -> None:
    """Set or clear the needs_review flag on an item."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("UPDATE items SET needs_review = ? WHERE id = ?", (1 if needs_review else 0, item_id))
    conn.commit()
    conn.close()
```

- [ ] **Step 6: Run the app to verify tables create without errors**

```bash
cd /Users/alexmarianetti/Desktop/CodingProjects/archive-arbitrage
python -c "from db.sqlite_models import init_db; init_db(); print('OK')"
```

Expected: `OK` with no errors.

- [ ] **Step 7: Commit**

```bash
git add db/sqlite_models.py
git commit -m "feat: add item_comps and regrade_log tables with CRUD functions"
```

---

## Task 2: Comp Feedback Service

**Files:**
- Create: `api/services/comp_feedback.py`

This service handles rejection processing and re-grading.

- [ ] **Step 1: Create the feedback service**

```python
"""
Comp feedback processing and re-grade logic.

When a comp is rejected:
1. Update item_comps feedback status
2. Update sold_comps rejection counters
3. If remaining comps >= MIN_COMPS_FOR_REGRADE: re-grade item
4. If remaining comps < MIN_COMPS_FOR_REGRADE: flag for manual review
"""

from datetime import datetime
from typing import Optional

from db.sqlite_models import (
    get_item_by_id,
    get_active_item_comps,
    update_item_comp_feedback,
    update_sold_comp_rejection,
    insert_regrade_log,
    set_item_needs_review,
)

MIN_COMPS_FOR_REGRADE = 3


def process_comp_feedback(
    item_id: int,
    item_comp_id: int,
    status: str,
    reason: Optional[str] = None,
) -> dict:
    """
    Process feedback on a comp assignment.

    Returns dict with:
      - updated: bool
      - regrade: dict with triggered, comps_remaining, and before/after values
    """
    item = get_item_by_id(item_id)
    if not item:
        return {"error": "Item not found"}

    # Get the item_comp row to find the sold_comp_id
    from db.sqlite_models import _get_conn
    import sqlite3
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM item_comps WHERE id = ? AND item_id = ?", (item_comp_id, item_id))
    comp_row = c.fetchone()
    conn.close()

    if not comp_row:
        return {"error": "Comp assignment not found"}

    # 1. Update feedback status
    updated_comp = update_item_comp_feedback(item_comp_id, status, reason)

    # 2. If rejected, update sold_comp counters
    if status == "rejected" and reason:
        update_sold_comp_rejection(comp_row["sold_comp_id"], reason)

    # 3. Check remaining comp pool
    remaining_comps = get_active_item_comps(item_id)
    comps_remaining = len(remaining_comps)

    # Capture before state
    grade_before = item.grade
    price_before = item.exact_sell_price or item.our_price or 0
    margin_before = item.exact_margin or item.margin_percent or 0

    if status != "rejected":
        # Acceptance doesn't trigger re-grade
        return {
            "updated": True,
            "regrade": {
                "triggered": False,
                "comps_remaining": comps_remaining,
                "reason": "acceptance_only",
            },
        }

    if comps_remaining < MIN_COMPS_FOR_REGRADE:
        # Flag for manual review, don't re-grade
        set_item_needs_review(item_id, True)
        insert_regrade_log({
            "item_id": item_id,
            "trigger": "comp_rejected",
            "comps_before": comps_remaining + 1,
            "comps_after": comps_remaining,
            "grade_before": grade_before,
            "grade_after": grade_before,  # unchanged
            "price_before": price_before,
            "price_after": price_before,  # unchanged
            "margin_before": margin_before,
            "margin_after": margin_before,
            "comp_pool_health": _calc_pool_health(remaining_comps),
            "rejected_comp_id": item_comp_id,
        })
        return {
            "updated": True,
            "regrade": {
                "triggered": False,
                "comps_remaining": comps_remaining,
                "reason": "below_minimum_threshold",
                "flagged_for_review": True,
            },
        }

    # 4. Re-grade from remaining comps
    regrade_result = _regrade_from_comps(item, remaining_comps)

    # 5. Log the re-grade
    insert_regrade_log({
        "item_id": item_id,
        "trigger": "comp_rejected",
        "comps_before": comps_remaining + 1,
        "comps_after": comps_remaining,
        "grade_before": grade_before,
        "grade_after": regrade_result["grade"],
        "price_before": price_before,
        "price_after": regrade_result["price"],
        "margin_before": margin_before,
        "margin_after": regrade_result["margin"],
        "comp_pool_health": _calc_pool_health(remaining_comps),
        "rejected_comp_id": item_comp_id,
    })

    # Clear needs_review if it was set
    set_item_needs_review(item_id, False)

    return {
        "updated": True,
        "regrade": {
            "triggered": True,
            "comps_remaining": comps_remaining,
            "grade_before": grade_before,
            "grade_after": regrade_result["grade"],
            "price_before": price_before,
            "price_after": regrade_result["price"],
            "margin_before": margin_before,
            "margin_after": regrade_result["margin"],
        },
    }


def _regrade_from_comps(item, comps: list) -> dict:
    """
    Recalculate grade and pricing from a filtered comp pool.
    Uses snapshot_price from item_comps (not live sold_comps data).
    Writes results back to the item record.
    """
    prices = [c["snapshot_price"] for c in comps if c["snapshot_price"] and c["snapshot_price"] > 0]

    if not prices:
        return {"grade": item.grade, "price": item.exact_sell_price or 0, "margin": item.exact_margin or 0}

    prices.sort()
    count = len(prices)
    median_price = prices[count // 2] if count % 2 == 1 else (prices[count // 2 - 1] + prices[count // 2]) / 2
    price_low = prices[0]
    price_high = prices[-1]

    # Conservative pricing: 10% below low end for quick sale
    sell_price = price_low * 0.90
    total_cost = item.source_price + (item.source_shipping or 0)

    # Enforce minimum 35% margin
    min_sell_price = total_cost * 1.35
    if sell_price < min_sell_price:
        sell_price = min_sell_price

    profit = sell_price - total_cost
    margin = profit / sell_price if sell_price > 0 else 0

    # Price confidence
    spread = (price_high - price_low) / median_price if median_price > 0 else 1.0
    if count >= 8 and spread <= 0.30:
        price_confidence = "high"
    elif count >= 4:
        price_confidence = "medium"
    else:
        price_confidence = "low"

    # Grade determination (mirrors exact_qualification.py logic)
    # Simplified: uses comp count + margin + profit thresholds
    if count >= 8 and price_confidence == "high" and profit >= 150 and margin >= 0.40:
        grade = "A"
    elif count >= 4 and profit >= 150 and margin >= 0.30:
        grade = "B"
    elif count >= 4:
        grade = "C"
    else:
        grade = "D"

    # Write back to item
    from db.sqlite_models import _get_conn
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE items SET
            grade = ?, exact_sell_price = ?, exact_profit = ?,
            exact_margin = ?, our_price = ?, market_price = ?,
            margin_percent = ?, comp_count = ?, price_low = ?,
            price_high = ?, qualified_at = ?
        WHERE id = ?
    """, (
        grade, round(sell_price, 2), round(profit, 2),
        round(margin, 4), round(sell_price, 2), round(median_price, 2),
        round(margin * 100, 1), count, round(price_low, 2),
        round(price_high, 2), datetime.utcnow().isoformat(),
        item.id,
    ))
    conn.commit()
    conn.close()

    return {"grade": grade, "price": round(sell_price, 2), "margin": round(margin, 4)}


def _calc_pool_health(comps: list) -> float:
    """Average similarity score of remaining comps."""
    scores = [c["similarity_score"] for c in comps if c["similarity_score"]]
    return round(sum(scores) / len(scores), 4) if scores else 0.0
```

- [ ] **Step 2: Commit**

```bash
git add api/services/comp_feedback.py
git commit -m "feat: add comp feedback service with re-grade logic"
```

---

## Task 3: Qualification Integration — Persist Comp Assignments

**Files:**
- Modify: `api/services/exact_qualification.py`

After qualification scores comps, persist them to `item_comps`.

- [ ] **Step 1: Add comp persistence to _calculate_exact_qualification()**

In `exact_qualification.py`, find `_calculate_exact_qualification()` (line ~112). After the `update_item_product_match()` call (line ~190-199), and before the `return ExactProductQualification(...)` (line ~201), add:

```python
# Persist individual comp assignments
self._persist_comp_assignments(item.id, product.id)
```

- [ ] **Step 2: Add the _persist_comp_assignments method**

Add this method to the `ExactProductQualifier` class (after `_calculate_exact_qualification`):

```python
def _persist_comp_assignments(self, item_id: int, product_id: int) -> None:
    """
    Find and persist individual comps for this item from product_prices.
    Maps product_prices records to sold_comps via source_id matching,
    then stores in item_comps with snapshots.
    """
    import sqlite3
    from pathlib import Path
    from db.sqlite_models import save_item_comps

    conn = sqlite3.connect(Path(__file__).parent.parent.parent / "data" / "archive.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get recent product_prices for this product
    c.execute("""
        SELECT pp.*, sc.id as sold_comp_id, sc.title, sc.condition, sc.sold_url, sc.sold_date, sc.source
        FROM product_prices pp
        LEFT JOIN sold_comps sc ON pp.source_id = sc.source_id AND pp.source = sc.source
        WHERE pp.product_id = ?
        ORDER BY pp.sold_date DESC
        LIMIT 20
    """, (product_id,))
    rows = c.fetchall()

    # Also try direct sold_comps search if product_prices yielded few matches
    if len([r for r in rows if r["sold_comp_id"]]) < 3:
        # Get the item to build search queries
        c.execute("SELECT brand, title FROM items WHERE id = ?", (item_id,))
        item_row = c.fetchone()
        if item_row:
            brand = item_row["brand"] or ""
            c.execute("""
                SELECT id as sold_comp_id, title, sold_price as price, condition,
                       sold_url, sold_date, source, source_id, size
                FROM sold_comps
                WHERE brand = ? COLLATE NOCASE
                ORDER BY fetched_at DESC
                LIMIT 20
            """, (brand,))
            fallback_rows = c.fetchall()

            # Score and merge fallback comps
            from scrapers.comp_matcher import parse_title, score_comp_similarity
            parsed = parse_title(brand, item_row["title"] or "")
            scored_fallbacks = []
            for r in fallback_rows:
                sim = score_comp_similarity(parsed, r["title"] or "")
                if sim > 0.3:
                    scored_fallbacks.append((r, sim))
            scored_fallbacks.sort(key=lambda x: x[1], reverse=True)

            # Convert to same format
            existing_sc_ids = {r["sold_comp_id"] for r in rows if r["sold_comp_id"]}
            for r, sim in scored_fallbacks[:15]:
                if r["sold_comp_id"] not in existing_sc_ids:
                    rows.append(r)

    conn.close()

    # Build comp list with scores
    from scrapers.comp_matcher import parse_title, score_comp_similarity
    conn2 = sqlite3.connect(Path(__file__).parent.parent.parent / "data" / "archive.db")
    conn2.row_factory = sqlite3.Row
    c2 = conn2.cursor()
    c2.execute("SELECT brand, title FROM items WHERE id = ?", (item_id,))
    item_row = c2.fetchone()
    conn2.close()

    if not item_row:
        return

    parsed = parse_title(item_row["brand"] or "", item_row["title"] or "")
    comp_entries = []

    for row in rows:
        row = dict(row)
        sold_comp_id = row.get("sold_comp_id")
        if not sold_comp_id:
            continue

        title = row.get("title", "")
        sim = score_comp_similarity(parsed, title) if title else 0.0
        price = row.get("price") or row.get("sold_price") or 0

        comp_entries.append({
            "sold_comp_id": sold_comp_id,
            "similarity_score": round(sim, 4),
            "snapshot_title": title,
            "snapshot_price": price,
            "snapshot_condition": row.get("condition"),
            "snapshot_source": row.get("source"),
            "snapshot_sold_date": row.get("sold_date"),
            "snapshot_url": row.get("sold_url") or row.get("url"),
        })

    # Deduplicate by sold_comp_id, keep highest score
    seen = {}
    for entry in comp_entries:
        scid = entry["sold_comp_id"]
        if scid not in seen or entry["similarity_score"] > seen[scid]["similarity_score"]:
            seen[scid] = entry
    comp_entries = list(seen.values())

    # Sort by score desc, assign ranks
    comp_entries.sort(key=lambda x: x["similarity_score"], reverse=True)
    for i, entry in enumerate(comp_entries):
        entry["rank"] = i + 1

    # Persist (limit to top 15)
    if comp_entries:
        save_item_comps(item_id, comp_entries[:15])
```

- [ ] **Step 3: Test qualification still works**

```bash
cd /Users/alexmarianetti/Desktop/CodingProjects/archive-arbitrage
python -c "
from db.sqlite_models import init_db, get_items
init_db()
items = get_items(status='active', limit=1)
if items:
    print(f'Item {items[0].id}: {items[0].brand} - {items[0].title[:50]}')
    print('DB init OK, items accessible')
else:
    print('No items found, but DB init OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add api/services/exact_qualification.py
git commit -m "feat: persist comp assignments to item_comps during qualification"
```

---

## Task 4: Quality Weight in Comp Matcher

**Files:**
- Modify: `scrapers/comp_matcher.py`

- [ ] **Step 1: Add quality_weight function**

At the top of `comp_matcher.py`, after the existing imports (around line 30), add:

```python
def quality_weight(quality_score: float = None) -> float:
    """
    Convert a sold_comp quality_score (0.0-1.0) to a scoring multiplier.
    Floor 0.5, ceiling 1.0. New comps with no history get 1.0 (no penalty).
    """
    if quality_score is None:
        return 1.0
    return 0.5 + (max(0.0, min(1.0, quality_score)) * 0.5)
```

- [ ] **Step 2: Integrate quality_weight into score_comp_similarity**

In `score_comp_similarity()` (line ~291), the function currently returns `min(total_score / total_weight_factors, 1.0)`. Modify the function signature to accept an optional quality_score parameter, and multiply at the end:

Change the function signature from:
```python
def score_comp_similarity(source_parsed: ParsedTitle, comp_title: str) -> float:
```
to:
```python
def score_comp_similarity(source_parsed: ParsedTitle, comp_title: str, comp_quality_score: float = None) -> float:
```

At the end of the function, before the return, change:
```python
return min(total_score / total_weight_factors, 1.0)
```
to:
```python
base_score = min(total_score / total_weight_factors, 1.0)
return base_score * quality_weight(comp_quality_score)
```

- [ ] **Step 3: Run existing comp matcher tests**

```bash
cd /Users/alexmarianetti/Desktop/CodingProjects/archive-arbitrage
python -m pytest tests/unit/test_exact_matching.py -v
```

Expected: All existing tests still pass (quality_score defaults to None = 1.0 multiplier).

- [ ] **Step 4: Commit**

```bash
git add scrapers/comp_matcher.py
git commit -m "feat: add quality_weight multiplier to comp similarity scoring"
```

---

## Task 5: API Endpoints

**Files:**
- Modify: `api/main.py`

- [ ] **Step 1: Add GET /api/items/{item_id}/comps endpoint**

After the existing `/api/items/{item_id}/market-data` endpoint in `main.py`, add:

```python
@app.get("/api/items/{item_id}/comps")
async def get_item_comps_endpoint(item_id: int):
    """Get comp assignments for an item with snapshot data."""
    item = get_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    from db.sqlite_models import get_item_comps
    comps = get_item_comps(item_id)

    accepted = sum(1 for c in comps if c["feedback_status"] == "accepted")
    rejected = sum(1 for c in comps if c["feedback_status"] == "rejected")
    pending = sum(1 for c in comps if c["feedback_status"] == "pending")

    return {
        "comps": [
            {
                "item_comp_id": c["id"],
                "rank": c["rank"],
                "similarity_score": c["similarity_score"],
                "feedback_status": c["feedback_status"],
                "rejection_reason": c["rejection_reason"],
                "title": c["snapshot_title"],
                "sold_price": c["snapshot_price"],
                "sold_date": c["snapshot_sold_date"],
                "sold_url": c["snapshot_url"],
                "source": c["snapshot_source"],
                "condition": c["snapshot_condition"],
            }
            for c in comps
        ],
        "total": len(comps),
        "accepted": accepted,
        "rejected": rejected,
        "pending": pending,
    }
```

- [ ] **Step 2: Add POST /api/items/{item_id}/comps/{item_comp_id}/feedback endpoint**

```python
from pydantic import BaseModel as _BaseModel

class CompFeedbackRequest(_BaseModel):
    status: str  # accepted | rejected
    reason: str = None  # wrong_model | wrong_condition | wrong_brand | outlier | other


@app.post("/api/items/{item_id}/comps/{item_comp_id}/feedback")
async def submit_comp_feedback(item_id: int, item_comp_id: int, req: CompFeedbackRequest):
    """Submit feedback on a comp assignment. Triggers re-grade on rejection."""
    if req.status not in ("accepted", "rejected"):
        raise HTTPException(status_code=400, detail="status must be 'accepted' or 'rejected'")
    if req.status == "rejected" and req.reason not in (
        "wrong_model", "wrong_condition", "wrong_brand", "outlier", "other", None
    ):
        raise HTTPException(status_code=400, detail="Invalid rejection reason")

    from api.services.comp_feedback import process_comp_feedback
    result = process_comp_feedback(item_id, item_comp_id, req.status, req.reason)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result
```

- [ ] **Step 3: Add needs_review filter to GET /api/items**

In the existing `list_items()` function, add a `needs_review` query parameter:

Find the function signature (starts around line 179) and add after the `created_after` parameter:

```python
needs_review: Optional[bool] = Query(None, description="Filter to items needing manual review"),
```

Then in the function body, where the `get_items()` call is made, the `needs_review` filter needs to be applied. Since `get_items()` doesn't support this filter yet, add client-side filtering after the items are fetched. Find where `items` is returned and add:

After `items = get_items(...)` (line ~198):
```python
if needs_review is not None:
    import sqlite3 as _sq
    from pathlib import Path as _P
    _conn = _sq.connect(_P(__file__).parent.parent / "data" / "archive.db")
    _c = _conn.cursor()
    _c.execute("SELECT id FROM items WHERE needs_review = 1")
    _review_ids = {row[0] for row in _c.fetchall()}
    _conn.close()
    if needs_review:
        items = [i for i in items if i.id in _review_ids]
    else:
        items = [i for i in items if i.id not in _review_ids]
```

- [ ] **Step 4: Add needs_review to ItemResponse**

In the `ItemResponse` class, add:

```python
needs_review: bool = False
```

And in the `from_db` classmethod, add to the return:

```python
needs_review=bool(getattr(item, 'needs_review', 0)),
```

- [ ] **Step 5: Commit**

```bash
git add api/main.py
git commit -m "feat: add comp feedback API endpoints and needs_review filter"
```

---

## Task 6: Frontend Types and API Layer

**Files:**
- Modify: `frontend-react/src/types/index.ts`
- Modify: `frontend-react/src/utils/api.ts`
- Modify: `frontend-react/src/hooks/useApi.ts`

- [ ] **Step 1: Add TypeScript types**

In `types/index.ts`, after the `ArbitrageOpportunity` interface, add:

```typescript
export interface ItemComp {
  item_comp_id: number;
  rank: number;
  similarity_score: number;
  feedback_status: 'pending' | 'accepted' | 'rejected';
  rejection_reason?: string | null;
  title: string;
  sold_price: number;
  sold_date: string | null;
  sold_url: string | null;
  source: string | null;
  condition: string | null;
}

export interface ItemCompsResponse {
  comps: ItemComp[];
  total: number;
  accepted: number;
  rejected: number;
  pending: number;
}

export interface RegradeResult {
  triggered: boolean;
  comps_remaining: number;
  grade_before?: string;
  grade_after?: string;
  price_before?: number;
  price_after?: number;
  margin_before?: number;
  margin_after?: number;
  reason?: string;
  flagged_for_review?: boolean;
}

export interface CompFeedbackResponse {
  updated: boolean;
  regrade: RegradeResult;
}

export type RejectionReason = 'wrong_model' | 'wrong_condition' | 'wrong_brand' | 'outlier' | 'other';
```

Also add `needs_review` to the `Item` interface:

```typescript
needs_review?: boolean;
```

- [ ] **Step 2: Add fetch functions**

In `api.ts`, add:

```typescript
export const fetchItemComps = async (itemId: number): Promise<ItemCompsResponse> => {
  const { data } = await api.get(`/items/${itemId}/comps`);
  return data;
};

export const submitCompFeedback = async (
  itemId: number,
  itemCompId: number,
  status: 'accepted' | 'rejected',
  reason?: string,
): Promise<CompFeedbackResponse> => {
  const { data } = await api.post(`/items/${itemId}/comps/${itemCompId}/feedback`, {
    status,
    reason: reason || undefined,
  });
  return data;
};
```

Add the new types to the import line at the top:
```typescript
import type { Item, Product, Stats, ArbitrageOpportunity, ItemCompsResponse, CompFeedbackResponse } from '../types';
```

- [ ] **Step 3: Add React Query hooks**

In `useApi.ts`, add:

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
```

(Update the existing import to include `useMutation` and `useQueryClient`.)

Then add the hooks:

```typescript
export const useItemComps = (itemId: number | null) => {
  return useQuery({
    queryKey: ['item-comps', itemId],
    queryFn: () => fetchItemComps(itemId!),
    enabled: itemId !== null,
    staleTime: 5 * 60 * 1000,
  });
};

export const useCompFeedback = (itemId: number) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemCompId, status, reason }: {
      itemCompId: number;
      status: 'accepted' | 'rejected';
      reason?: string;
    }) => submitCompFeedback(itemId, itemCompId, status, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['item-comps', itemId] });
      queryClient.invalidateQueries({ queryKey: ['item', itemId] });
      queryClient.invalidateQueries({ queryKey: ['items'] });
    },
  });
};
```

Add `fetchItemComps` and `submitCompFeedback` to the imports from `../utils/api`.

- [ ] **Step 4: Commit**

```bash
git add frontend-react/src/types/index.ts frontend-react/src/utils/api.ts frontend-react/src/hooks/useApi.ts
git commit -m "feat: add comp feedback types, API functions, and React Query hooks"
```

---

## Task 7: CompTable Component

**Files:**
- Create: `frontend-react/src/components/CompTable.tsx`

- [ ] **Step 1: Create the CompTable component**

```tsx
import { useState } from 'react';
import { Check, X, ExternalLink, AlertTriangle } from 'lucide-react';
import { useItemComps, useCompFeedback } from '../hooks/useApi';
import type { RejectionReason } from '../types';

const REJECTION_REASONS: { value: RejectionReason; label: string }[] = [
  { value: 'wrong_model', label: 'Wrong model' },
  { value: 'wrong_condition', label: 'Wrong condition' },
  { value: 'wrong_brand', label: 'Wrong brand' },
  { value: 'outlier', label: 'Outlier price' },
  { value: 'other', label: 'Other' },
];

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}

function formatPrice(price: number | null): string {
  if (price === null || price === undefined) return '—';
  return `$${Math.round(price)}`;
}

interface CompTableProps {
  itemId: number;
}

export function CompTable({ itemId }: CompTableProps) {
  const { data, isLoading } = useItemComps(itemId);
  const feedback = useCompFeedback(itemId);
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const handleAccept = (itemCompId: number) => {
    feedback.mutate(
      { itemCompId, status: 'accepted' },
      {
        onSuccess: () => {
          setToast(null);
        },
      },
    );
  };

  const handleReject = (itemCompId: number, reason: RejectionReason) => {
    feedback.mutate(
      { itemCompId, status: 'rejected', reason },
      {
        onSuccess: (result) => {
          setRejectingId(null);
          if (result.regrade.triggered) {
            setToast(
              `Re-graded: ${result.regrade.grade_before} → ${result.regrade.grade_after} · ` +
              `${formatPrice(result.regrade.price_before ?? null)} → ${formatPrice(result.regrade.price_after ?? null)}`
            );
            setTimeout(() => setToast(null), 5000);
          } else if (result.regrade.flagged_for_review) {
            setToast('Flagged for review — too few comps remaining');
            setTimeout(() => setToast(null), 5000);
          }
        },
      },
    );
  };

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-10 bg-surface rounded border border-border animate-skeleton" />
        ))}
      </div>
    );
  }

  if (!data?.comps?.length) {
    return (
      <div className="text-center py-6">
        <span className="font-mono text-[11px] text-text-muted">No comps assigned to this item</span>
      </div>
    );
  }

  const needsReview = data.comps.length - data.rejected < 3 && data.rejected > 0;

  return (
    <div className="space-y-2">
      {/* Warning banner */}
      {needsReview && (
        <div className="flex items-center gap-2 px-3 py-2 bg-signal-amber/10 border border-signal-amber/20 rounded">
          <AlertTriangle className="w-3.5 h-3.5 text-signal-amber flex-shrink-0" />
          <span className="font-mono text-[10px] text-signal-amber">
            Low comp pool — {data.total - data.rejected} remaining. Item flagged for review.
          </span>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="px-3 py-2 bg-accent/10 border border-accent/20 rounded">
          <span className="font-mono text-[10px] text-accent">{toast}</span>
        </div>
      )}

      {/* Summary */}
      <div className="flex items-center gap-3 font-mono text-[10px] text-text-muted">
        <span>{data.total} comps</span>
        {data.accepted > 0 && <span className="text-signal-green">{data.accepted} accepted</span>}
        {data.rejected > 0 && <span className="text-signal-red">{data.rejected} rejected</span>}
        {data.pending > 0 && <span>{data.pending} pending</span>}
      </div>

      {/* Comp rows */}
      <div className="space-y-1">
        {data.comps.map((comp) => {
          const isRejected = comp.feedback_status === 'rejected';
          const isAccepted = comp.feedback_status === 'accepted';

          return (
            <div
              key={comp.item_comp_id}
              className={`flex items-center gap-3 px-3 py-2 rounded border transition-colors ${
                isRejected
                  ? 'border-signal-red/10 bg-signal-red/5 opacity-50'
                  : isAccepted
                  ? 'border-signal-green/10 bg-signal-green/5'
                  : 'border-border bg-surface'
              }`}
            >
              {/* Rank */}
              <span className="font-mono text-[10px] text-text-muted w-4 text-center flex-shrink-0">
                {comp.rank}
              </span>

              {/* Title + metadata */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className={`font-sans text-xs truncate ${isRejected ? 'line-through text-text-muted' : 'text-text-primary'}`}>
                    {comp.title || '—'}
                  </span>
                  {comp.sold_url && (
                    <a
                      href={comp.sold_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-shrink-0 text-text-muted hover:text-accent transition-colors"
                    >
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-0.5 font-mono text-[9px] text-text-muted">
                  {comp.source && <span className="uppercase">{comp.source}</span>}
                  {comp.condition && <span>{comp.condition}</span>}
                  {isRejected && comp.rejection_reason && (
                    <span className="text-signal-red">{comp.rejection_reason.replace('_', ' ')}</span>
                  )}
                </div>
              </div>

              {/* Price */}
              <span className={`font-mono text-xs flex-shrink-0 ${isRejected ? 'line-through text-text-muted' : 'text-text-primary'}`}>
                {formatPrice(comp.sold_price)}
              </span>

              {/* Date */}
              <span className="font-mono text-[10px] text-text-muted flex-shrink-0 w-14 text-right">
                {formatDate(comp.sold_date)}
              </span>

              {/* Score */}
              <span className="font-mono text-[10px] text-text-muted flex-shrink-0 w-8 text-right">
                {comp.similarity_score ? `${Math.round(comp.similarity_score * 100)}%` : '—'}
              </span>

              {/* Actions */}
              <div className="flex items-center gap-1 flex-shrink-0">
                {comp.feedback_status === 'pending' && (
                  <>
                    <button
                      onClick={() => handleAccept(comp.item_comp_id)}
                      className="p-1 rounded hover:bg-signal-green/10 text-text-muted hover:text-signal-green transition-colors"
                      title="Accept comp"
                    >
                      <Check className="w-3.5 h-3.5" />
                    </button>
                    <div className="relative">
                      <button
                        onClick={() => setRejectingId(
                          rejectingId === comp.item_comp_id ? null : comp.item_comp_id
                        )}
                        className="p-1 rounded hover:bg-signal-red/10 text-text-muted hover:text-signal-red transition-colors"
                        title="Reject comp"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                      {rejectingId === comp.item_comp_id && (
                        <div className="absolute right-0 top-full mt-1 z-50 bg-surface border border-border rounded-lg shadow-lg py-1 min-w-[140px]">
                          {REJECTION_REASONS.map((r) => (
                            <button
                              key={r.value}
                              onClick={() => handleReject(comp.item_comp_id, r.value)}
                              className="w-full text-left px-3 py-1.5 font-mono text-[10px] text-text-secondary hover:bg-surface-hover hover:text-text-primary transition-colors"
                            >
                              {r.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </>
                )}
                {isAccepted && (
                  <span className="p-1 text-signal-green"><Check className="w-3.5 h-3.5" /></span>
                )}
                {isRejected && (
                  <span className="p-1 text-signal-red"><X className="w-3.5 h-3.5" /></span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend-react/src/components/CompTable.tsx
git commit -m "feat: add CompTable component with feedback controls"
```

---

## Task 8: Wire CompTable into ItemDetailPanel

**Files:**
- Modify: `frontend-react/src/components/ItemDetailPanel.tsx`

- [ ] **Step 1: Import CompTable**

Add to the imports at the top of `ItemDetailPanel.tsx`:

```typescript
import { CompTable } from './CompTable';
```

- [ ] **Step 2: Add Sold Comps section**

Find the "Market Comps" section (around line 278). **Before** that section, add the new Sold Comps section:

```tsx
{/* Sold Comps — Feedback */}
{item.id && (
  <div className="surface-inset rounded-lg p-4">
    <h4 className="font-mono text-[10px] text-text-muted uppercase tracking-wider mb-3">
      Sold Comps
    </h4>
    <CompTable itemId={item.id} />
  </div>
)}
```

- [ ] **Step 3: Commit**

```bash
git add frontend-react/src/components/ItemDetailPanel.tsx
git commit -m "feat: add Sold Comps section to item detail panel"
```

---

## Task 9: Needs Review Filter on Deals Page

**Files:**
- Modify: `frontend-react/src/pages/Deals.tsx`
- Modify: `frontend-react/src/components/FilterSidebar.tsx`
- Modify: `frontend-react/src/components/DealCard.tsx`

- [ ] **Step 1: Add needs_review filter state to Deals.tsx**

In `Deals.tsx`, find where filters are extracted from URL params (around lines 30-45). Add:

```typescript
const needsReview = searchParams.get('needs_review') === '1';
```

Pass it to the `useItems` call as a parameter. Find the `useItems` call and add:

```typescript
needs_review: needsReview || undefined,
```

Also add to the `activeFiltersCount` computation and `activeFilters` list:

In activeFiltersCount (around line 63):
```typescript
if (needsReview) count++;
```

In activeFilters (around line 86):
```typescript
if (needsReview) filters.push({
  label: 'Needs Review',
  onRemove: () => setParam('needs_review', null),
});
```

In `handleClearFilters`:
```typescript
setParam('needs_review', null);
```

- [ ] **Step 2: Add toggle to FilterSidebar**

In `FilterSidebar.tsx`, add a "Review Status" section. Find where the Grade filter section starts and add before it:

```tsx
{/* Review Status */}
<div className="px-4 py-3 border-b border-border">
  <button
    onClick={() => {/* passed from parent */}}
    className={`w-full flex items-center justify-between px-3 py-2 rounded border transition-colors ${
      needsReview
        ? 'border-signal-amber/30 bg-signal-amber/10 text-signal-amber'
        : 'border-border bg-surface text-text-muted hover:text-text-secondary'
    }`}
  >
    <span className="font-mono text-[10px] uppercase tracking-wider">Needs Review</span>
    {needsReview && <span className="font-mono text-[10px]">ON</span>}
  </button>
</div>
```

Add `needsReview` and `onNeedsReviewChange` to the FilterSidebar props:

```typescript
needsReview: boolean;
onNeedsReviewChange: (value: boolean) => void;
```

Wire the button's onClick:
```typescript
onClick={() => onNeedsReviewChange(!needsReview)}
```

Pass these props from Deals.tsx where FilterSidebar is rendered.

- [ ] **Step 3: Add badge to DealCard**

In `DealCard.tsx`, in the grid view section where badges are shown (near the grade badge), add:

```tsx
{item.needs_review && (
  <span className="absolute top-2 left-2 px-1.5 py-0.5 bg-signal-amber/90 text-void rounded font-mono text-[9px] font-medium uppercase z-10">
    Review
  </span>
)}
```

- [ ] **Step 4: Commit**

```bash
git add frontend-react/src/pages/Deals.tsx frontend-react/src/components/FilterSidebar.tsx frontend-react/src/components/DealCard.tsx
git commit -m "feat: add needs_review filter and badge to deals page"
```

---

## Task 10: Backend Tests

**Files:**
- Create: `tests/unit/test_comp_feedback.py`
- Create: `tests/unit/test_quality_weight.py`

- [ ] **Step 1: Write quality_weight tests**

```python
"""Tests for the quality_weight function in comp_matcher."""

from scrapers.comp_matcher import quality_weight


class TestQualityWeight:
    def test_none_returns_one(self):
        """New comps with no history should get no penalty."""
        assert quality_weight(None) == 1.0

    def test_perfect_score(self):
        """Quality score of 1.0 should return 1.0."""
        assert quality_weight(1.0) == 1.0

    def test_zero_score(self):
        """Quality score of 0.0 should return floor of 0.5."""
        assert quality_weight(0.0) == 0.5

    def test_half_score(self):
        """Quality score of 0.5 should return 0.75."""
        assert quality_weight(0.5) == 0.75

    def test_clamps_above_one(self):
        """Values above 1.0 should be clamped."""
        assert quality_weight(1.5) == 1.0

    def test_clamps_below_zero(self):
        """Values below 0.0 should be clamped to floor."""
        assert quality_weight(-0.5) == 0.5

    def test_score_integrated_in_similarity(self):
        """quality_score should reduce the final similarity score."""
        from scrapers.comp_matcher import parse_title, score_comp_similarity
        parsed = parse_title("rick owens", "Rick Owens Geobasket Leather Sneakers")
        comp_title = "Rick Owens Geobasket High Top Sneakers"

        score_good = score_comp_similarity(parsed, comp_title, comp_quality_score=1.0)
        score_bad = score_comp_similarity(parsed, comp_title, comp_quality_score=0.0)

        assert score_good > score_bad
        assert score_bad >= score_good * 0.5  # floor is 50%
```

- [ ] **Step 2: Run quality_weight tests**

```bash
python -m pytest tests/unit/test_quality_weight.py -v
```

Expected: All pass.

- [ ] **Step 3: Write comp feedback tests**

```python
"""Tests for the comp feedback service."""

import sqlite3
import tempfile
import os
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

import pytest


@pytest.fixture
def test_db(tmp_path):
    """Create a test database with item_comps and related tables."""
    db_path = tmp_path / "test_archive.db"
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    # Create minimal tables
    c.execute("""CREATE TABLE items (
        id INTEGER PRIMARY KEY, brand TEXT, title TEXT, source_price REAL DEFAULT 100,
        source_shipping REAL DEFAULT 0, grade TEXT, exact_sell_price REAL,
        exact_profit REAL, exact_margin REAL, our_price REAL, market_price REAL,
        margin_percent REAL, comp_count INTEGER, price_low REAL, price_high REAL,
        qualified_at TEXT, needs_review INTEGER DEFAULT 0, status TEXT DEFAULT 'active'
    )""")
    c.execute("""CREATE TABLE sold_comps (
        id INTEGER PRIMARY KEY, search_key TEXT, brand TEXT, title TEXT,
        sold_price REAL, size TEXT, sold_url TEXT, source TEXT, source_id TEXT,
        condition TEXT, sold_date TEXT, fetched_at TEXT,
        times_matched INTEGER DEFAULT 0, times_rejected INTEGER DEFAULT 0,
        rejection_reasons TEXT DEFAULT '{}', quality_score REAL DEFAULT 1.0,
        last_rejected_at TEXT
    )""")
    c.execute("""CREATE TABLE item_comps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER, sold_comp_id INTEGER, similarity_score REAL,
        rank INTEGER, feedback_status TEXT DEFAULT 'pending',
        rejected_at TEXT, rejection_reason TEXT,
        snapshot_title TEXT, snapshot_price REAL, snapshot_condition TEXT,
        snapshot_source TEXT, snapshot_sold_date TEXT, snapshot_url TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    c.execute("""CREATE TABLE regrade_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER, trigger TEXT, comps_before INTEGER, comps_after INTEGER,
        grade_before TEXT, grade_after TEXT, price_before REAL, price_after REAL,
        margin_before REAL, margin_after REAL, comp_pool_health REAL,
        rejected_comp_id INTEGER, created_at TEXT DEFAULT (datetime('now'))
    )""")

    # Insert test data
    c.execute("INSERT INTO items (id, brand, title, source_price, grade, exact_sell_price, exact_margin) VALUES (1, 'Rick Owens', 'Geobasket Sneakers', 200, 'B', 500, 0.60)")

    for i in range(5):
        c.execute("INSERT INTO sold_comps (id, brand, title, sold_price, source, quality_score) VALUES (?, 'Rick Owens', ?, ?, 'grailed', 1.0)",
                  (i + 1, f'Rick Owens Comp {i+1}', 400 + i * 50))
        c.execute("INSERT INTO item_comps (item_id, sold_comp_id, similarity_score, rank, feedback_status, snapshot_title, snapshot_price, snapshot_source) VALUES (1, ?, ?, ?, 'pending', ?, ?, 'grailed')",
                  (i + 1, 0.9 - i * 0.1, i + 1, f'Rick Owens Comp {i+1}', 400 + i * 50))

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def mock_db(test_db):
    """Patch _get_conn to use test database."""
    def _get_test_conn():
        conn = sqlite3.connect(str(test_db))
        conn.row_factory = sqlite3.Row
        return conn

    with patch("db.sqlite_models._get_conn", _get_test_conn):
        with patch("api.services.comp_feedback._get_conn", _get_test_conn):
            yield test_db


class TestCompFeedbackProcessing:
    def test_accept_comp(self, mock_db):
        from api.services.comp_feedback import process_comp_feedback
        result = process_comp_feedback(1, 1, "accepted")
        assert result["updated"] is True
        assert result["regrade"]["triggered"] is False

    def test_reject_triggers_regrade_when_enough_comps(self, mock_db):
        from api.services.comp_feedback import process_comp_feedback
        result = process_comp_feedback(1, 1, "rejected", "wrong_model")
        assert result["updated"] is True
        assert result["regrade"]["triggered"] is True
        assert result["regrade"]["comps_remaining"] == 4

    def test_reject_flags_review_when_too_few_comps(self, mock_db):
        from api.services.comp_feedback import process_comp_feedback
        # Reject 3 comps to get below threshold
        process_comp_feedback(1, 1, "rejected", "wrong_model")
        process_comp_feedback(1, 2, "rejected", "wrong_brand")
        result = process_comp_feedback(1, 3, "rejected", "outlier")
        assert result["regrade"]["triggered"] is False
        assert result["regrade"]["flagged_for_review"] is True
        assert result["regrade"]["comps_remaining"] == 2

    def test_rejection_updates_sold_comp_quality(self, mock_db):
        from api.services.comp_feedback import process_comp_feedback
        process_comp_feedback(1, 1, "rejected", "wrong_model")

        conn = sqlite3.connect(str(mock_db))
        c = conn.cursor()
        c.execute("SELECT times_rejected, quality_score FROM sold_comps WHERE id = 1")
        row = c.fetchone()
        conn.close()
        assert row[0] == 1  # times_rejected
        assert row[1] < 1.0  # quality_score reduced

    def test_regrade_log_inserted(self, mock_db):
        from api.services.comp_feedback import process_comp_feedback
        process_comp_feedback(1, 1, "rejected", "wrong_model")

        conn = sqlite3.connect(str(mock_db))
        c = conn.cursor()
        c.execute("SELECT * FROM regrade_log WHERE item_id = 1")
        rows = c.fetchall()
        conn.close()
        assert len(rows) == 1

    def test_snapshot_immutability(self, mock_db):
        """Snapshots should not change when sold_comps are updated."""
        conn = sqlite3.connect(str(mock_db))
        c = conn.cursor()
        # Read original snapshot
        c.execute("SELECT snapshot_title, snapshot_price FROM item_comps WHERE id = 2")
        original = c.fetchone()
        # Modify the sold_comp
        c.execute("UPDATE sold_comps SET title = 'MODIFIED', sold_price = 9999 WHERE id = 2")
        conn.commit()
        # Verify snapshot unchanged
        c.execute("SELECT snapshot_title, snapshot_price FROM item_comps WHERE id = 2")
        after = c.fetchone()
        conn.close()
        assert original[0] == after[0]
        assert original[1] == after[1]
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/unit/test_quality_weight.py tests/unit/test_comp_feedback.py -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_quality_weight.py tests/unit/test_comp_feedback.py
git commit -m "test: add comp feedback and quality weight tests"
```

---

## Task 11: Build and Verify Frontend

- [ ] **Step 1: Build frontend to verify no TypeScript errors**

```bash
cd /Users/alexmarianetti/Desktop/CodingProjects/archive-arbitrage/frontend-react
npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 2: Fix any build errors**

If there are TypeScript errors, fix them. Common issues:
- Missing imports for new types
- Prop type mismatches in FilterSidebar
- Missing `useMutation`/`useQueryClient` imports

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve build errors in comp feedback frontend"
```

---

## Verification Checklist

After all tasks complete, verify:

- [ ] `item_comps` table exists and has correct schema
- [ ] `regrade_log` table exists
- [ ] `sold_comps` has new columns (times_matched, quality_score, etc.)
- [ ] `items` table has `needs_review` column
- [ ] GET `/api/items/{id}/comps` returns snapshot data
- [ ] POST `/api/items/{id}/comps/{comp_id}/feedback` processes rejection and returns regrade result
- [ ] Rejection with >= 3 remaining comps triggers auto re-grade
- [ ] Rejection with < 3 remaining comps flags for review
- [ ] `regrade_log` records all re-grade events
- [ ] `quality_weight()` returns correct values across range
- [ ] CompTable renders comps with links, dates, and feedback buttons
- [ ] Reject dropdown shows reason options
- [ ] Toast shows after re-grade
- [ ] Needs Review filter works on Deals page
- [ ] All tests pass
