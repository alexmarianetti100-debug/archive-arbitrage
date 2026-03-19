"""
SQLite database models for Archive Arbitrage.
Rebuilt 2026-02-18 — all functions required by the codebase.
Updated 2026-03-09 — uses connection pooling
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field, asdict

from .connection_pool import get_pool, db_connection, db_transaction

DB_PATH = Path(__file__).parent.parent / "data" / "archive.db"
logger = logging.getLogger("sqlite_models")


# ---------------------------------------------------------------------------
# Helper: add column if missing (safe migration)
# ---------------------------------------------------------------------------

def _add_column_if_missing(cursor, table: str, column: str, col_type: str):
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        return True
    return False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Item:
    id: Optional[int] = None
    source: str = ""
    source_id: str = ""
    source_url: str = ""
    title: str = ""
    brand: Optional[str] = None
    category: Optional[str] = None
    size: Optional[str] = None
    condition: Optional[str] = None
    source_price: float = 0.0
    source_shipping: float = 0.0
    market_price: Optional[float] = None
    our_price: Optional[float] = None
    margin_percent: Optional[float] = None
    images: Optional[List[str]] = None
    is_auction: bool = False
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # Authentication
    auth_status: Optional[str] = None
    auth_confidence: Optional[float] = None
    auth_reasons: Optional[List[str]] = None
    # Image fingerprinting
    image_hash: Optional[str] = None
    phash: Optional[str] = None
    # Qualification
    grade: Optional[str] = None
    grade_reasoning: Optional[str] = None
    demand_score: Optional[float] = None
    sell_through_days: Optional[float] = None
    comp_count: Optional[int] = None
    high_quality_comps: Optional[int] = None
    qualified_at: Optional[str] = None
    # Demand details
    demand_level: Optional[str] = None
    sold_count: Optional[int] = None
    active_count: Optional[int] = None
    # Exact pricing
    exact_sell_price: Optional[float] = None
    exact_profit: Optional[float] = None
    exact_margin: Optional[float] = None
    sell_through_rate: Optional[float] = None
    est_days_to_sell: Optional[float] = None
    # Volume metrics
    weighted_volume: Optional[float] = None
    sales_per_day: Optional[float] = None
    volume_trend: Optional[str] = None
    same_size_sold: Optional[int] = None
    price_trend_percent: Optional[float] = None
    # Season detection
    exact_season: Optional[str] = None
    exact_year: Optional[int] = None
    season_confidence: Optional[str] = None
    # Product matching (Phase 2)
    product_id: Optional[int] = None
    fingerprint_hash: Optional[str] = None
    match_confidence: Optional[str] = None
    exact_comps: Optional[int] = None
    price_confidence: Optional[float] = None
    price_low: Optional[float] = None
    price_high: Optional[float] = None

    # Aliases used by API layer
    @property
    def deal_grade(self):
        return self.grade

    @property
    def deal_grade_reasoning(self):
        return self.grade_reasoning

    @property
    def image_phash(self):
        return self.phash


@dataclass
class Product:
    id: Optional[int] = None
    brand: str = ""
    sub_brand: Optional[str] = None
    model: str = ""
    item_type: str = ""
    material: Optional[str] = None
    color: Optional[str] = None
    fingerprint_hash: str = ""
    total_sales: int = 0
    avg_price: float = 0.0
    min_price: float = 0.0
    max_price: float = 0.0
    median_price: float = 0.0
    sales_30d: int = 0
    velocity_score: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Row → object converters
# ---------------------------------------------------------------------------

def _row_to_item(row) -> Item:
    """Convert a sqlite3.Row or dict-like row to an Item."""
    if isinstance(row, sqlite3.Row):
        d = dict(row)
    elif isinstance(row, dict):
        d = row
    else:
        # tuple — use column order from items table
        cols = [
            "id", "source", "source_id", "source_url", "title", "brand",
            "category", "size", "condition", "source_price", "source_shipping",
            "market_price", "our_price", "margin_percent", "images",
            "is_auction", "status", "created_at", "updated_at",
            "auth_status", "auth_confidence", "auth_reasons",
            "image_hash", "phash",
            "grade", "grade_reasoning", "demand_score", "sell_through_days",
            "comp_count", "qualified_at",
            "product_id", "fingerprint_hash", "match_confidence",
            "exact_comps", "price_confidence", "price_low", "price_high",
        ]
        d = {}
        for i, col in enumerate(cols):
            if i < len(row):
                d[col] = row[i]
        
    # Parse JSON fields
    for json_field in ("images", "auth_reasons"):
        val = d.get(json_field)
        if isinstance(val, str):
            try:
                d[json_field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                d[json_field] = []
    
    # Bool conversion
    if "is_auction" in d:
        d["is_auction"] = bool(d["is_auction"])
    
    return Item(**{k: v for k, v in d.items() if hasattr(Item, k)})


def _row_to_product(row) -> Product:
    """Convert a sqlite3.Row to a Product."""
    if isinstance(row, sqlite3.Row):
        d = dict(row)
    elif isinstance(row, dict):
        d = row
    else:
        cols = [
            "id", "brand", "sub_brand", "model", "item_type", "material",
            "color", "fingerprint_hash", "total_sales", "avg_price",
            "min_price", "max_price", "median_price", "sales_30d",
            "velocity_score", "created_at", "updated_at",
        ]
        d = {}
        for i, col in enumerate(cols):
            if i < len(row):
                d[col] = row[i]
    
    return Product(**{k: v for k, v in d.items() if hasattr(Product, k)})


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    """
    Get database connection from pool (for backward compatibility).
    
    NOTE: This gets a connection from the pool. The caller is responsible
    for returning it using conn.close() which returns it to the pool.
    """
    pool = get_pool()
    return pool._get_connection()


def _return_conn(conn):
    """Return connection to pool (for backward compatibility)."""
    pool = get_pool()
    pool._return_connection(conn)


# ---------------------------------------------------------------------------
# init_db — create / migrate all tables
# ---------------------------------------------------------------------------

def init_db():
    """Create all tables and run migrations."""
    # Use transaction context manager for proper connection handling
    with db_transaction() as conn:
        c = conn.cursor()

    # --- items ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL DEFAULT '',
            source_id TEXT DEFAULT '',
            source_url TEXT DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            brand TEXT,
            category TEXT,
            size TEXT,
            condition TEXT,
            source_price REAL DEFAULT 0,
            source_shipping REAL DEFAULT 0,
            market_price REAL,
            our_price REAL,
            margin_percent REAL,
            images TEXT DEFAULT '[]',
            is_auction INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            updated_at TEXT,
            auth_status TEXT,
            auth_confidence REAL,
            auth_reasons TEXT,
            image_hash TEXT,
            phash TEXT,
            grade TEXT,
            grade_reasoning TEXT,
            demand_score REAL,
            sell_through_days REAL,
            comp_count INTEGER,
            high_quality_comps INTEGER,
            qualified_at TEXT,
            demand_level TEXT,
            sold_count INTEGER,
            active_count INTEGER,
            exact_sell_price REAL,
            exact_profit REAL,
            exact_margin REAL,
            sell_through_rate REAL,
            est_days_to_sell REAL,
            weighted_volume REAL,
            sales_per_day REAL,
            volume_trend TEXT,
            same_size_sold INTEGER,
            price_trend_percent REAL,
            exact_season TEXT,
            exact_year INTEGER,
            season_confidence TEXT,
            product_id INTEGER,
            fingerprint_hash TEXT,
            match_confidence TEXT,
            exact_comps INTEGER,
            price_confidence REAL,
            price_low REAL,
            price_high REAL
        )
    """)

    # Migrate old tables that may be missing columns
    migrations = [
        ("items", "source_id", "TEXT DEFAULT ''"),
        ("items", "category", "TEXT"),
        ("items", "size", "TEXT"),
        ("items", "condition", "TEXT"),
        ("items", "market_price", "REAL"),
        ("items", "our_price", "REAL"),
        ("items", "margin_percent", "REAL"),
        ("items", "images", "TEXT DEFAULT '[]'"),
        ("items", "is_auction", "INTEGER DEFAULT 0"),
        ("items", "created_at", "TEXT"),
        ("items", "updated_at", "TEXT"),
        ("items", "auth_status", "TEXT"),
        ("items", "auth_confidence", "REAL"),
        ("items", "auth_reasons", "TEXT"),
        ("items", "image_hash", "TEXT"),
        ("items", "phash", "TEXT"),
        ("items", "grade", "TEXT"),
        ("items", "grade_reasoning", "TEXT"),
        ("items", "demand_score", "REAL"),
        ("items", "sell_through_days", "REAL"),
        ("items", "comp_count", "INTEGER"),
        ("items", "qualified_at", "TEXT"),
        ("items", "high_quality_comps", "INTEGER"),
        ("items", "demand_level", "TEXT"),
        ("items", "sold_count", "INTEGER"),
        ("items", "active_count", "INTEGER"),
        ("items", "exact_sell_price", "REAL"),
        ("items", "exact_profit", "REAL"),
        ("items", "exact_margin", "REAL"),
        ("items", "sell_through_rate", "REAL"),
        ("items", "est_days_to_sell", "REAL"),
        ("items", "weighted_volume", "REAL"),
        ("items", "sales_per_day", "REAL"),
        ("items", "volume_trend", "TEXT"),
        ("items", "same_size_sold", "INTEGER"),
        ("items", "price_trend_percent", "REAL"),
        ("items", "exact_season", "TEXT"),
        ("items", "exact_year", "INTEGER"),
        ("items", "season_confidence", "TEXT"),
        ("items", "product_id", "INTEGER"),
        ("items", "fingerprint_hash", "TEXT"),
        ("items", "match_confidence", "TEXT"),
        ("items", "exact_comps", "INTEGER"),
        ("items", "price_confidence", "REAL"),
        ("items", "price_low", "REAL"),
        ("items", "price_high", "REAL"),
        # Comp feedback system columns
        ("items", "needs_review", "INTEGER DEFAULT 0"),
        ("sold_comps", "times_matched", "INTEGER DEFAULT 0"),
        ("sold_comps", "times_rejected", "INTEGER DEFAULT 0"),
        ("sold_comps", "rejection_reasons", "TEXT DEFAULT '{}'"),
        ("sold_comps", "quality_score", "REAL DEFAULT 1.0"),
        ("sold_comps", "last_rejected_at", "TEXT"),
    ]
    for table, col, col_type in migrations:
        _add_column_if_missing(c, table, col, col_type)

    # --- sold_comps ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS sold_comps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_key TEXT,
            brand TEXT,
            title TEXT,
            sold_price REAL,
            size TEXT,
            sold_url TEXT,
            source TEXT,
            source_id TEXT,
            condition TEXT,
            sold_date TEXT,
            fetched_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- products (Phase 2) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT NOT NULL,
            sub_brand TEXT,
            model TEXT NOT NULL,
            item_type TEXT NOT NULL,
            material TEXT,
            color TEXT,
            fingerprint_hash TEXT UNIQUE,
            total_sales INTEGER DEFAULT 0,
            avg_price REAL DEFAULT 0,
            min_price REAL DEFAULT 0,
            max_price REAL DEFAULT 0,
            median_price REAL DEFAULT 0,
            sales_30d INTEGER DEFAULT 0,
            velocity_score REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- item_comps (comp feedback system) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS item_comps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            sold_comp_id INTEGER REFERENCES sold_comps(id) ON DELETE CASCADE,
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

    # --- regrade_log (tracks re-grading events) ---
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

    # --- product_prices (sale records per product) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS product_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id),
            price REAL NOT NULL,
            size TEXT,
            source TEXT,
            source_id TEXT,
            url TEXT,
            sold_date TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- price_history (item price tracking) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL REFERENCES items(id),
            source_price REAL,
            market_price REAL,
            our_price REAL,
            recorded_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Indexes
    for stmt in [
        "CREATE INDEX IF NOT EXISTS idx_items_status ON items(status)",
        "CREATE INDEX IF NOT EXISTS idx_items_brand ON items(brand)",
        "CREATE INDEX IF NOT EXISTS idx_items_grade ON items(grade)",
        "CREATE INDEX IF NOT EXISTS idx_items_source_id ON items(source, source_id)",
        "CREATE INDEX IF NOT EXISTS idx_items_image_hash ON items(image_hash)",
        "CREATE INDEX IF NOT EXISTS idx_items_phash ON items(phash)",
        "CREATE INDEX IF NOT EXISTS idx_items_product_id ON items(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_sold_comps_brand ON sold_comps(brand)",
        "CREATE INDEX IF NOT EXISTS idx_sold_comps_search_key ON sold_comps(search_key)",
        "CREATE INDEX IF NOT EXISTS idx_products_fingerprint ON products(fingerprint_hash)",
        "CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand)",
        "CREATE INDEX IF NOT EXISTS idx_product_prices_product ON product_prices(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_item_comps_item_id ON item_comps(item_id)",
        "CREATE INDEX IF NOT EXISTS idx_item_comps_sold_comp_id ON item_comps(sold_comp_id)",
        "CREATE INDEX IF NOT EXISTS idx_item_comps_feedback_status ON item_comps(feedback_status)",
        "CREATE INDEX IF NOT EXISTS idx_regrade_log_item_id ON regrade_log(item_id)",
    ]:
        c.execute(stmt)

    # ── Migration: make sold_comp_id nullable in existing DBs ──
    # SQLite can't ALTER COLUMN, so recreate the table if it has NOT NULL constraint
    try:
        c.execute("PRAGMA table_info(item_comps)")
        cols = c.fetchall()
        for col in cols:
            if col[1] == "sold_comp_id" and col[3] == 1:  # col[3] = notnull flag
                c.execute("ALTER TABLE item_comps RENAME TO item_comps_old")
                c.execute("""
                    CREATE TABLE item_comps (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                        sold_comp_id INTEGER REFERENCES sold_comps(id) ON DELETE CASCADE,
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
                c.execute("INSERT INTO item_comps SELECT * FROM item_comps_old")
                c.execute("DROP TABLE item_comps_old")
                # Recreate indexes
                c.execute("CREATE INDEX IF NOT EXISTS idx_item_comps_item_id ON item_comps(item_id)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_item_comps_sold_comp_id ON item_comps(sold_comp_id)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_item_comps_feedback_status ON item_comps(feedback_status)")
                break
    except Exception:
        pass  # Table might not exist yet (fresh DB)

    # Transaction committed automatically by context manager


# ---------------------------------------------------------------------------
# CRUD — Items
# ---------------------------------------------------------------------------

def save_item(item: Item) -> int:
    """Insert or update an item. Returns the item id."""
    conn = _get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()

    # Check for existing item by source + source_id
    if item.source and item.source_id:
        c.execute(
            "SELECT id FROM items WHERE source = ? AND source_id = ?",
            (item.source, item.source_id),
        )
        existing = c.fetchone()
        if existing:
            item_id = existing["id"]
            c.execute("""
                UPDATE items SET
                    title=?, brand=?, category=?, size=?, condition=?,
                    source_price=?, source_shipping=?, source_url=?,
                    market_price=?, our_price=?, margin_percent=?,
                    images=?, is_auction=?, status=?,
                    auth_status=?, auth_confidence=?, auth_reasons=?,
                    updated_at=?
                WHERE id=?
            """, (
                item.title, item.brand, item.category, item.size, item.condition,
                item.source_price, item.source_shipping, item.source_url,
                item.market_price, item.our_price, item.margin_percent,
                json.dumps(item.images or []), int(item.is_auction), item.status,
                item.auth_status, item.auth_confidence,
                json.dumps(item.auth_reasons) if item.auth_reasons else None,
                now, item_id,
            ))
            conn.commit()
            conn.close()
            return item_id

    # Insert new
    c.execute("""
        INSERT INTO items (
            source, source_id, source_url, title, brand, category, size,
            condition, source_price, source_shipping, market_price, our_price,
            margin_percent, images, is_auction, status,
            auth_status, auth_confidence, auth_reasons,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item.source, item.source_id, item.source_url, item.title,
        item.brand, item.category, item.size, item.condition,
        item.source_price, item.source_shipping,
        item.market_price, item.our_price, item.margin_percent,
        json.dumps(item.images or []), int(item.is_auction), item.status,
        item.auth_status, item.auth_confidence,
        json.dumps(item.auth_reasons) if item.auth_reasons else None,
        now, now,
    ))
    item_id = c.lastrowid
    conn.commit()
    conn.close()
    return item_id


def get_items(
    status: Optional[str] = None,
    brand: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    authenticated: Optional[bool] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_sold_count: Optional[int] = 3,
    season: Optional[str] = None,
    year: Optional[int] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    sort: str = "newest",
    created_after: Optional[str] = None,
) -> List[Item]:
    """Retrieve items with optional filtering."""
    conn = _get_conn()
    c = conn.cursor()
    clauses, params = [], []

    if status:
        clauses.append("status = ?")
        params.append(status)
    if brand:
        clauses.append("LOWER(brand) = LOWER(?)")
        params.append(brand)
    if category:
        clauses.append("LOWER(category) = LOWER(?)")
        params.append(category)
    if authenticated:
        clauses.append("auth_status = 'authentic'")
    if min_price is not None:
        clauses.append("our_price >= ?")
        params.append(min_price)
    if max_price is not None:
        clauses.append("our_price <= ?")
        params.append(max_price)
    if min_sold_count is not None:
        clauses.append("comp_count >= ?")
        params.append(min_sold_count)
    if created_after is not None:
        clauses.append("created_at >= ?")
        params.append(created_after)
    if season is not None:
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

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    # Sort mapping
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
    order = order_map.get(sort, "id DESC")

    c.execute(
        f"SELECT * FROM items {where} ORDER BY {order} LIMIT ? OFFSET ?",
        params + [limit, offset],
    )
    items = [_row_to_item(row) for row in c.fetchall()]
    conn.close()
    return items


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
    """Count items matching filters using SQL COUNT(*)."""
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


def get_item_by_id(item_id: int) -> Optional[Item]:
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    row = c.fetchone()
    conn.close()
    return _row_to_item(row) if row else None


def delete_item(item_id: int) -> bool:
    conn = _get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM items WHERE id = ?", (item_id,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_unqualified_items(limit: int = 500) -> List[Item]:
    """Get items that haven't been qualified yet."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM items WHERE status = 'active' AND grade IS NULL ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    items = [_row_to_item(row) for row in c.fetchall()]
    conn.close()
    return items


def get_qualified_items(
    grade: Optional[str] = None,
    brand: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Get qualified items, optionally filtered by grade."""
    conn = _get_conn()
    c = conn.cursor()
    clauses = ["grade IS NOT NULL"]
    params = []

    if grade:
        clauses.append("grade = ?")
        params.append(grade.upper())
    if brand:
        clauses.append("LOWER(brand) = LOWER(?)")
        params.append(brand)

    where = "WHERE " + " AND ".join(clauses)
    c.execute(
        f"SELECT * FROM items {where} ORDER BY demand_score DESC, margin_percent DESC LIMIT ?",
        params + [limit],
    )
    items = []
    for row in c.fetchall():
        item = _row_to_item(row)
        items.append(asdict(item))
    conn.close()
    return items


# ---------------------------------------------------------------------------
# Item updates
# ---------------------------------------------------------------------------

def update_item_qualification(
    item_id: int,
    grade: str,
    grade_reasoning: str = "",
    demand_score: float = 0,
    sell_through_days: float = 0,
    comp_count: int = 0,
    our_price: Optional[float] = None,
    margin_percent: Optional[float] = None,
):
    """Update qualification data for an item."""
    conn = _get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    
    sets = [
        "grade=?", "grade_reasoning=?", "demand_score=?",
        "sell_through_days=?", "comp_count=?", "qualified_at=?", "updated_at=?",
    ]
    params = [grade, grade_reasoning, demand_score, sell_through_days, comp_count, now, now]
    
    if our_price is not None:
        sets.append("our_price=?")
        params.append(our_price)
    if margin_percent is not None:
        sets.append("margin_percent=?")
        params.append(margin_percent)
    
    params.append(item_id)
    c.execute(f"UPDATE items SET {', '.join(sets)} WHERE id=?", params)
    conn.commit()
    conn.close()


def update_item_image_hashes(item_id: int, file_hash: str, phash: str):
    """Store image fingerprint hashes on an item."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE items SET image_hash=?, phash=?, updated_at=? WHERE id=?",
        (file_hash, phash, datetime.utcnow().isoformat(), item_id),
    )
    conn.commit()
    conn.close()


def update_item_product_match(
    item_id: int,
    product_id: int,
    fingerprint: str,
    confidence: str = "medium",
    exact_comps: int = 0,
    price_confidence: float = 0,
    price_low: float = 0,
    price_high: float = 0,
):
    """Update product match info on an item."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE items SET
            product_id=?, fingerprint_hash=?, match_confidence=?,
            exact_comps=?, price_confidence=?, price_low=?, price_high=?,
            updated_at=?
        WHERE id=?
    """, (
        product_id, fingerprint, confidence, exact_comps,
        price_confidence, price_low, price_high,
        datetime.utcnow().isoformat(), item_id,
    ))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Image duplicate detection
# ---------------------------------------------------------------------------

def find_duplicate_by_image_hash(file_hash: str) -> Optional[Item]:
    """Find an existing item with the same image file hash."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM items WHERE image_hash = ? LIMIT 1", (file_hash,))
    row = c.fetchone()
    conn.close()
    return _row_to_item(row) if row else None


def find_similar_by_phash(phash: str, threshold: int = 10, limit: int = 5) -> List[Item]:
    """Find items with similar perceptual hashes (hamming distance)."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM items WHERE phash IS NOT NULL")
    results = []
    for row in c.fetchall():
        try:
            dist = _hamming_distance(phash, row["phash"])
            if dist <= threshold:
                item = _row_to_item(row)
                results.append((dist, item))
        except (ValueError, TypeError):
            continue
    conn.close()
    results.sort(key=lambda x: x[0])
    return [item for _, item in results[:limit]]


def _hamming_distance(h1: str, h2: str) -> int:
    """Hamming distance between two hex hash strings."""
    if len(h1) != len(h2):
        return 999
    n1, n2 = int(h1, 16), int(h2, 16)
    return bin(n1 ^ n2).count("1")


# ---------------------------------------------------------------------------
# Sold Comps
# ---------------------------------------------------------------------------

def save_sold_comp(search_key: str, comp: Dict[str, Any]):
    """Save a sold comp to the database. Skips duplicates by source+source_id."""
    conn = _get_conn()
    c = conn.cursor()
    source = comp.get("source")
    source_id = comp.get("source_id")
    # Dedup: skip if this exact comp already exists
    if source and source_id:
        c.execute("SELECT id FROM sold_comps WHERE source = ? AND source_id = ?", (source, source_id))
        if c.fetchone():
            conn.close()
            return
    c.execute("""
        INSERT INTO sold_comps (search_key, brand, title, sold_price, size, sold_url, source, source_id, condition, sold_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        search_key,
        comp.get("brand"),
        comp.get("title"),
        comp.get("sold_price") or comp.get("price"),
        comp.get("size"),
        comp.get("sold_url") or comp.get("url"),
        source,
        source_id,
        comp.get("condition"),
        comp.get("sold_date"),
    ))
    conn.commit()
    conn.close()


def get_sold_comps(
    brand: Optional[str] = None,
    search_key: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Get sold comps, optionally filtered."""
    conn = _get_conn()
    c = conn.cursor()
    clauses, params = [], []
    if brand:
        clauses.append("LOWER(brand) = LOWER(?)")
        params.append(brand)
    if search_key:
        clauses.append("search_key = ?")
        params.append(search_key)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    c.execute(f"SELECT * FROM sold_comps {where} ORDER BY id DESC LIMIT ?", params + [limit])
    comps = [dict(row) for row in c.fetchall()]
    conn.close()
    return comps


def get_comp_quality_scores(source_id_pairs: list) -> dict:
    """Batch lookup quality scores for sold comps by (source, source_id).

    Args:
        source_id_pairs: List of (source, source_id) tuples

    Returns:
        Dict of (source, source_id) -> quality_score. Defaults to 1.0 for unknown comps.
    """
    if not source_id_pairs:
        return {}

    result = {pair: 1.0 for pair in source_id_pairs}

    conn = _get_conn()
    c = conn.cursor()

    placeholders = " OR ".join(["(source = ? AND source_id = ?)"] * len(source_id_pairs))
    params = []
    for source, source_id in source_id_pairs:
        params.extend([source, source_id])

    c.execute(
        f"SELECT source, source_id, quality_score FROM sold_comps WHERE {placeholders}",
        params,
    )
    for row in c.fetchall():
        key = (row["source"], row["source_id"])
        result[key] = row["quality_score"] if row["quality_score"] is not None else 1.0

    conn.close()
    return result


def get_sold_comps_stats(brand: Optional[str] = None) -> Dict[str, Any]:
    """Get aggregate stats on sold comps."""
    conn = _get_conn()
    c = conn.cursor()
    if brand:
        c.execute(
            "SELECT COUNT(*) as count, AVG(sold_price) as avg_price, MIN(sold_price) as min_price, MAX(sold_price) as max_price FROM sold_comps WHERE LOWER(brand) = LOWER(?)",
            (brand,),
        )
    else:
        c.execute(
            "SELECT COUNT(*) as count, AVG(sold_price) as avg_price, MIN(sold_price) as min_price, MAX(sold_price) as max_price FROM sold_comps"
        )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {"count": 0, "avg_price": 0, "min_price": 0, "max_price": 0}


# ---------------------------------------------------------------------------
# Item Comps (comp feedback system)
# ---------------------------------------------------------------------------

def save_item_comps(item_id: int, comps: List[Dict[str, Any]]):
    """Delete existing item_comps for this item, then insert new ones.

    Each comp dict has: sold_comp_id, similarity_score, rank,
    snapshot_title, snapshot_price, snapshot_condition, snapshot_source,
    snapshot_sold_date, snapshot_url.

    Also increments times_matched on each sold_comp and recalculates quality_score.
    """
    conn = _get_conn()
    c = conn.cursor()

    # Delete existing comps for this item
    c.execute("DELETE FROM item_comps WHERE item_id = ?", (item_id,))

    # Insert new comps
    for comp in comps:
        c.execute("""
            INSERT INTO item_comps (
                item_id, sold_comp_id, similarity_score, rank,
                snapshot_title, snapshot_price, snapshot_condition,
                snapshot_source, snapshot_sold_date, snapshot_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item_id,
            comp.get("sold_comp_id"),
            comp.get("similarity_score"),
            comp.get("rank"),
            comp.get("snapshot_title"),
            comp.get("snapshot_price"),
            comp.get("snapshot_condition"),
            comp.get("snapshot_source"),
            comp.get("snapshot_sold_date"),
            comp.get("snapshot_url"),
        ))

        # Increment times_matched on sold_comp and recalculate quality_score
        sold_comp_id = comp.get("sold_comp_id")
        if sold_comp_id is not None:
            c.execute("""
                UPDATE sold_comps
                SET times_matched = COALESCE(times_matched, 0) + 1
                WHERE id = ?
            """, (sold_comp_id,))
            # Recalculate quality_score with 0.2 floor
            c.execute("""
                UPDATE sold_comps
                SET quality_score = MAX(0.2, 1.0 - (CAST(COALESCE(times_rejected, 0) AS REAL) / MAX(times_matched, 1)))
                WHERE id = ?
            """, (sold_comp_id,))

    conn.commit()
    conn.close()


def get_item_comps(item_id: int) -> List[Dict[str, Any]]:
    """Get all item_comps for an item ordered by rank ASC."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM item_comps WHERE item_id = ? ORDER BY rank ASC",
        (item_id,),
    )
    comps = [dict(row) for row in c.fetchall()]
    conn.close()
    return comps


def link_item_to_sold_comps(
    item_id: int,
    search_key: str,
    limit: int = 15,
    similarity_scores: list = None,
) -> int:
    """Link an item to its sold comps by searching sold_comps table.

    Args:
        item_id: The item to link comps to
        search_key: Query used to find matching comps
        limit: Max comps to link
        similarity_scores: Pre-computed similarity scores from compute_weighted_price().
            If provided, used instead of synthetic rank-based scores.

    Returns number of comps linked.
    """
    comps = get_sold_comps(search_key=search_key, limit=limit)
    if not comps and search_key:
        # Fallback: try brand-only search (handles Japan deals where query differs from search_key)
        brand_words = search_key.lower().split()
        if len(brand_words) >= 2:
            # Try first two words as brand (e.g., "chrome hearts", "rick owens", "maison margiela")
            brand_guess = " ".join(brand_words[:2])
            comps = get_sold_comps(brand=brand_guess, limit=limit)
        if not comps and brand_words:
            comps = get_sold_comps(brand=brand_words[0], limit=limit)
    if not comps:
        return 0

    entries = []
    for rank, sc in enumerate(comps, start=1):
        # Use provided similarity score if available, otherwise synthetic fallback
        if similarity_scores and rank - 1 < len(similarity_scores):
            sim = similarity_scores[rank - 1]
        else:
            sim = max(0.5, 1.0 - rank * 0.03)

        entries.append({
            "sold_comp_id": sc.get("id"),
            "similarity_score": sim,
            "rank": rank,
            "snapshot_title": sc.get("title"),
            "snapshot_price": sc.get("sold_price"),
            "snapshot_condition": sc.get("condition"),
            "snapshot_source": sc.get("source", "grailed"),
            "snapshot_sold_date": sc.get("sold_date"),
            "snapshot_url": sc.get("sold_url"),
        })

    save_item_comps(item_id, entries)
    return len(entries)


def get_active_item_comps(item_id: int) -> List[Dict[str, Any]]:
    """Get item_comps for an item excluding rejected ones, ordered by rank ASC."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM item_comps WHERE item_id = ? AND feedback_status != 'rejected' ORDER BY rank ASC",
        (item_id,),
    )
    comps = [dict(row) for row in c.fetchall()]
    conn.close()
    return comps


def update_item_comp_feedback(item_comp_id: int, status: str, reason: str = None, expected_item_id: int = None) -> Optional[Dict[str, Any]]:
    """Update feedback_status, rejected_at (if rejected), rejection_reason.

    Returns updated row as dict, or None if not found or ownership check fails.
    """
    conn = _get_conn()
    c = conn.cursor()

    # Validate comp belongs to expected item
    if expected_item_id is not None:
        c.execute("SELECT item_id FROM item_comps WHERE id = ?", (item_comp_id,))
        row = c.fetchone()
        if not row or row["item_id"] != expected_item_id:
            conn.close()
            return None

    now = datetime.utcnow().isoformat()

    if status == "rejected":
        c.execute("""
            UPDATE item_comps
            SET feedback_status = ?, rejected_at = ?, rejection_reason = ?
            WHERE id = ?
        """, (status, now, reason, item_comp_id))
    else:
        c.execute("""
            UPDATE item_comps
            SET feedback_status = ?, rejection_reason = ?
            WHERE id = ?
        """, (status, reason, item_comp_id))

    conn.commit()

    # Fetch and return the updated row
    c.execute("SELECT * FROM item_comps WHERE id = ?", (item_comp_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_sold_comp_rejection(sold_comp_id: int, reason: str):
    """Increment times_rejected, update rejection_reasons JSON frequency map,
    recalculate quality_score, and set last_rejected_at.
    """
    conn = _get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()

    # Get current rejection_reasons JSON
    c.execute("SELECT rejection_reasons, times_rejected, times_matched FROM sold_comps WHERE id = ?", (sold_comp_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return

    # Parse existing rejection_reasons frequency map
    raw = row["rejection_reasons"]
    try:
        reasons_map = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        reasons_map = {}

    # Increment the count for this reason
    reasons_map[reason] = reasons_map.get(reason, 0) + 1

    times_rejected = (row["times_rejected"] or 0) + 1
    times_matched = max(row["times_matched"] or 1, 1)
    quality_score = max(0.2, 1.0 - (times_rejected / times_matched))

    c.execute("""
        UPDATE sold_comps
        SET times_rejected = ?,
            rejection_reasons = ?,
            quality_score = ?,
            last_rejected_at = ?
        WHERE id = ?
    """, (
        times_rejected,
        json.dumps(reasons_map),
        quality_score,
        now,
        sold_comp_id,
    ))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Regrade Log
# ---------------------------------------------------------------------------

def insert_regrade_log(log: Dict[str, Any]):
    """Insert a regrade_log entry from a dict."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO regrade_log (
            item_id, trigger, comps_before, comps_after,
            grade_before, grade_after, price_before, price_after,
            margin_before, margin_after, comp_pool_health, rejected_comp_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        log.get("item_id"),
        log.get("trigger"),
        log.get("comps_before"),
        log.get("comps_after"),
        log.get("grade_before"),
        log.get("grade_after"),
        log.get("price_before"),
        log.get("price_after"),
        log.get("margin_before"),
        log.get("margin_after"),
        log.get("comp_pool_health"),
        log.get("rejected_comp_id"),
    ))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Item Needs Review
# ---------------------------------------------------------------------------

def set_item_needs_review(item_id: int, needs_review: int):
    """Set or clear the needs_review flag on an item."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE items SET needs_review = ?, updated_at = ? WHERE id = ?",
        (needs_review, datetime.utcnow().isoformat(), item_id),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Price History
# ---------------------------------------------------------------------------

def get_price_history(item_id: int) -> List[Dict[str, Any]]:
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM price_history WHERE item_id = ? ORDER BY recorded_at ASC",
        (item_id,),
    )
    history = [dict(row) for row in c.fetchall()]
    conn.close()
    return history


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_stats(created_after: str = None) -> Dict[str, Any]:
    """Get overall database statistics, optionally filtered by created_after."""
    conn = _get_conn()
    c = conn.cursor()

    stats = {}

    # Build optional date clause for item queries
    date_clause = ""
    date_params: list = []
    if created_after:
        date_clause = " AND created_at >= ?"
        date_params = [created_after]

    c.execute("SELECT COUNT(*) FROM items WHERE 1=1" + date_clause, date_params)
    stats["total_items"] = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM items WHERE status = 'active'" + date_clause, date_params)
    stats["active_items"] = c.fetchone()[0]

    c.execute("SELECT COUNT(DISTINCT brand) FROM items WHERE brand IS NOT NULL" + date_clause, date_params)
    stats["total_brands"] = c.fetchone()[0]
    stats["unique_brands"] = stats["total_brands"]  # alias

    c.execute("SELECT AVG(margin_percent) FROM items WHERE margin_percent IS NOT NULL" + date_clause, date_params)
    row = c.fetchone()
    stats["avg_margin"] = round(row[0], 1) if row[0] else 0

    c.execute("SELECT COUNT(*) FROM items WHERE grade IS NOT NULL" + date_clause, date_params)
    stats["qualified_items"] = c.fetchone()[0]

    for g in ("A", "B", "C", "D"):
        c.execute("SELECT COUNT(*) FROM items WHERE grade = ?" + date_clause, [g] + date_params)
        stats[f"grade_{g.lower()}_count"] = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM sold_comps")
    stats["total_sold_comps"] = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM products")
    stats["total_products"] = c.fetchone()[0]

    conn.close()
    return stats


# ---------------------------------------------------------------------------
# Products (Phase 2)
# ---------------------------------------------------------------------------

def get_or_create_product(
    brand: str,
    model: str,
    item_type: str,
    fingerprint_hash: str,
    sub_brand: Optional[str] = None,
    material: Optional[str] = None,
    color: Optional[str] = None,
) -> Product:
    """Get existing product by fingerprint or create new one."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE fingerprint_hash = ?", (fingerprint_hash,))
    row = c.fetchone()
    if row:
        product = _row_to_product(row)
        conn.close()
        return product

    now = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO products (brand, sub_brand, model, item_type, material, color, fingerprint_hash, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (brand, sub_brand, model, item_type, material, color, fingerprint_hash, now, now))
    product_id = c.lastrowid
    conn.commit()
    conn.close()

    return Product(
        id=product_id, brand=brand, sub_brand=sub_brand, model=model,
        item_type=item_type, material=material, color=color,
        fingerprint_hash=fingerprint_hash, created_at=now, updated_at=now,
    )


def add_product_sale(product_id: int, price: float, size: str = None, source: str = None, source_id: str = None, url: str = None, sold_date: str = None):
    """Record a sale for a product and update aggregate stats."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO product_prices (product_id, price, size, source, source_id, url, sold_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (product_id, price, size, source, source_id, url, sold_date))

    # Update product aggregate stats
    c.execute("SELECT price FROM product_prices WHERE product_id = ?", (product_id,))
    prices = sorted([row["price"] for row in c.fetchall()])
    total = len(prices)
    avg_p = sum(prices) / total if total else 0
    med_p = prices[total // 2] if total else 0

    # 30-day sales
    cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
    c.execute(
        "SELECT COUNT(*) FROM product_prices WHERE product_id = ? AND created_at >= ?",
        (product_id, cutoff),
    )
    sales_30d = c.fetchone()[0]

    c.execute("""
        UPDATE products SET
            total_sales=?, avg_price=?, min_price=?, max_price=?, median_price=?,
            sales_30d=?, velocity_score=?, updated_at=?
        WHERE id=?
    """, (
        total, round(avg_p, 2), min(prices), max(prices), round(med_p, 2),
        sales_30d, round(sales_30d / 30, 4),
        datetime.utcnow().isoformat(), product_id,
    ))
    conn.commit()
    conn.close()


def get_product_by_fingerprint(fingerprint_hash: str) -> Optional[Product]:
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE fingerprint_hash = ?", (fingerprint_hash,))
    row = c.fetchone()
    conn.close()
    return _row_to_product(row) if row else None


def get_product_price_stats(product_id: int, days: int = 90) -> Dict[str, Any]:
    """Get price statistics for a product over the last N days."""
    conn = _get_conn()
    c = conn.cursor()
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    c.execute(
        "SELECT price FROM product_prices WHERE product_id = ? AND created_at >= ?",
        (product_id, cutoff),
    )
    prices = sorted([row["price"] for row in c.fetchall()])
    conn.close()

    if not prices:
        return {"count": 0, "avg": 0, "min": 0, "max": 0, "median": 0}

    return {
        "count": len(prices),
        "avg": round(sum(prices) / len(prices), 2),
        "min": min(prices),
        "max": max(prices),
        "median": round(prices[len(prices) // 2], 2),
    }


def find_matching_products(
    brand: str,
    model: Optional[str] = None,
    item_type: Optional[str] = None,
    min_sales: int = 1,
    limit: int = 5,
) -> List[Product]:
    """Find products matching brand/model/type criteria."""
    conn = _get_conn()
    c = conn.cursor()
    clauses = ["LOWER(brand) = LOWER(?)", "total_sales >= ?"]
    params: list = [brand, min_sales]

    if model:
        clauses.append("LOWER(model) LIKE LOWER(?)")
        params.append(f"%{model}%")
    if item_type:
        clauses.append("LOWER(item_type) = LOWER(?)")
        params.append(item_type)

    where = "WHERE " + " AND ".join(clauses)
    c.execute(
        f"SELECT * FROM products {where} ORDER BY total_sales DESC LIMIT ?",
        params + [limit],
    )
    products = [_row_to_product(row) for row in c.fetchall()]
    conn.close()
    return products


def get_high_velocity_products(min_sales_30d: int = 5) -> List[Product]:
    """Get products with high sales velocity."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM products WHERE sales_30d >= ? ORDER BY sales_30d DESC",
        (min_sales_30d,),
    )
    products = [_row_to_product(row) for row in c.fetchall()]
    conn.close()
    return products
