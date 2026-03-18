# Gap Hunter DB Persistence Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When gap_hunter sends a deal to Discord, also persist it to the `items` table with grade, comp count, and profit data so the frontend displays qualified deals.

**Architecture:** Add a `persist_deal_to_db()` function in `gap_hunter.py` that calls `save_item()` + `update_item_qualification()` after alerts succeed. Map gap_hunter's `quality_score`/`fire_level` to the A/B/C/D grade system. Also default the API's `get_items()` to `min_sold_count=3` so only comp-backed items show.

**Tech Stack:** Python, SQLite (existing `db/sqlite_models.py`)

---

### Task 1: Add `persist_deal_to_db()` to gap_hunter.py

**Files:**
- Modify: `gap_hunter.py` (add function + call it after `self.stats["deals_sent"] += 1`)
- Modify: `db/sqlite_models.py` (no changes needed — uses existing `save_item` + `update_item_qualification`)

The function maps gap_hunter's deal/item/signals data to the DB `Item` dataclass and saves it. It also calls `update_item_qualification` to set grade, comp_count, profit, etc.

**Grade mapping from gap_hunter signals:**
- fire_level >= 3 AND quality_score >= 80 → Grade A
- fire_level >= 2 AND quality_score >= 65 → Grade B
- fire_level >= 1 AND quality_score >= 50 → Grade C
- else → Grade D

- [ ] **Step 1: Add the persist function and import**

At the top of `gap_hunter.py`, add import:
```python
from db.sqlite_models import save_item, update_item_qualification, Item as DbItem
```

Add function before `process_deal`:
```python
def _map_grade(fire_level: int, quality_score: float) -> str:
    """Map gap_hunter quality signals to A/B/C/D grade."""
    if fire_level >= 3 and quality_score >= 80:
        return "A"
    if fire_level >= 2 and quality_score >= 65:
        return "B"
    if fire_level >= 1 and quality_score >= 50:
        return "C"
    return "D"
```

- [ ] **Step 2: Add persist call in process_deal after deals_sent increment**

In `process_deal`, after `self.stats["deals_sent"] += 1` (line ~2482), add:

```python
            # Persist deal to DB for frontend display
            try:
                import hashlib
                # Extract source_id from URL
                url_hash = hashlib.md5(item.url.encode()).hexdigest()[:12] if item.url else ""
                source_id = f"gap_{url_hash}"

                db_item = DbItem(
                    source=item.source,
                    source_id=source_id,
                    source_url=item.url,
                    title=item.title,
                    brand=brand,
                    category=category,
                    size=getattr(item, 'size', None),
                    condition=getattr(item, 'condition', None),
                    source_price=item.price,
                    source_shipping=0.0,
                    market_price=deal.sold_avg,
                    our_price=deal.sold_avg,
                    margin_percent=deal.gap_percent * 100,
                    images=item.images or [],
                    is_auction=getattr(item, 'is_auction', False),
                    status="active",
                )
                item_id = save_item(db_item)

                # Map fire_level to grade
                grade = _map_grade(signals.fire_level, quality_score)
                grade_reasoning = (
                    f"Gap Hunter: {signals.fire_level} fire, "
                    f"score {quality_score:.0f}/100, "
                    f"{deal.sold_count} comps, "
                    f"${deal.profit_estimate:.0f} profit"
                )

                update_item_qualification(
                    item_id=item_id,
                    grade=grade,
                    grade_reasoning=grade_reasoning,
                    demand_score=signals.liquidity_score / 10 if hasattr(signals, 'liquidity_score') else 0.5,
                    sell_through_days=getattr(signals, 'avg_days_to_sell', 0) or 0,
                    comp_count=deal.sold_count,
                    our_price=deal.sold_avg,
                    margin_percent=deal.gap_percent * 100,
                )

                # Also set exact pricing fields directly
                from db.sqlite_models import _get_conn
                conn = _get_conn()
                conn.execute(
                    """UPDATE items SET
                        exact_sell_price=?, exact_profit=?, exact_margin=?,
                        demand_level=?, sold_count=?
                    WHERE id=?""",
                    (
                        deal.sold_avg,
                        deal.expected_net_profit,
                        deal.gap_percent * 100,
                        "hot" if signals.fire_level >= 3 else "warm" if signals.fire_level >= 2 else "cold",
                        deal.sold_count,
                        item_id,
                    ),
                )
                conn.commit()
                conn.close()

                logger.info(f"    💾 Persisted to DB: item #{item_id}, grade {grade}")
            except Exception as e:
                logger.debug(f"    DB persist failed (non-fatal): {e}")
```

- [ ] **Step 3: Verify gap_hunter.py compiles**

Run: `python3 -c "import py_compile; py_compile.compile('gap_hunter.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add gap_hunter.py
git commit -m "feat: persist gap_hunter deals to items DB for frontend display"
```

---

### Task 2: Default API to only return items with comps

**Files:**
- Modify: `db/sqlite_models.py:553-632` (`get_items` function)

- [ ] **Step 1: Add default min_sold_count=3 to get_items**

In `get_items()`, change the `min_sold_count` parameter default from `None` to `3`:

```python
def get_items(
    ...
    min_sold_count: Optional[int] = 3,  # Only show items with comps by default
    ...
```

This means the `/api/items` endpoint will only return items with 3+ comps unless the caller explicitly passes `min_sold_count=0`.

- [ ] **Step 2: Verify compilation**

Run: `python3 -c "from db.sqlite_models import get_items; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add db/sqlite_models.py
git commit -m "feat: default items API to min 3 comps, filtering unqualified items"
```

---

### Task 3: Verify end-to-end

- [ ] **Step 1: Run a dry test that simulates the full persist flow**

```python
python3 -c "
from db.sqlite_models import init_db, save_item, update_item_qualification, get_items, Item as DbItem
init_db()

# Simulate gap_hunter persisting a deal
db_item = DbItem(
    source='grailed', source_id='gap_test123', source_url='https://grailed.com/test',
    title='Helmut Lang Bondage Strap Jacket', brand='Helmut Lang',
    category='outerwear', size='M', source_price=310, market_price=600,
    our_price=600, margin_percent=48, images=[], status='active',
)
item_id = save_item(db_item)
update_item_qualification(item_id, grade='B', grade_reasoning='Test', comp_count=8, our_price=600, margin_percent=48)
print(f'Saved item #{item_id}')

# Verify it shows up in get_items (min_sold_count=3 default)
items = get_items(limit=10)
found = any(i.id == item_id for i in items)
print(f'Found in get_items: {found}')
assert found, 'Item with 8 comps should appear with default min_sold_count=3'

# Verify items with 0 comps are filtered out
zero_comp_items = [i for i in items if (i.comp_count or 0) < 3]
print(f'Zero-comp items in results: {len(zero_comp_items)}')
assert len(zero_comp_items) == 0, 'Items with <3 comps should be filtered'

# Clean up test item
from db.sqlite_models import _get_conn
conn = _get_conn()
conn.execute('DELETE FROM items WHERE source_id = ?', ('gap_test123',))
conn.commit()
conn.close()
print('Cleaned up. All assertions passed.')
"
```

- [ ] **Step 2: Commit all verified changes**

```bash
git add -A
git commit -m "test: verify gap_hunter DB persistence and comp filtering"
```
