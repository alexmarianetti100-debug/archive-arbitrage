"""Tests for comp feedback processing — rejection, re-grading, and snapshots."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helper: create a PooledConnection-like wrapper that keeps the same in-memory
# connection alive across calls (sqlite3 in-memory DBs vanish when the last
# connection closes).
# ---------------------------------------------------------------------------

class _FakePooledConn:
    """Thin wrapper so .close() is a no-op — keeps the shared conn alive."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        # Intentional no-op — the fixture owns the connection lifetime.
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


# ---------------------------------------------------------------------------
# Fixture: in-memory test database with schema + seed data
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_db(tmp_path):
    """Create a test SQLite DB with all required tables and seed data.

    Patches ``_get_conn`` in both ``db.sqlite_models`` and
    ``api.services.comp_feedback`` so every production call hits this DB.
    """
    db_path = tmp_path / "test_archive.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # ---- items table (full production schema) ----
    c.execute("""
        CREATE TABLE items (
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
            price_high REAL,
            needs_review INTEGER DEFAULT 0
        )
    """)

    # ---- sold_comps table ----
    c.execute("""
        CREATE TABLE sold_comps (
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
            fetched_at TEXT DEFAULT (datetime('now')),
            times_matched INTEGER DEFAULT 0,
            times_rejected INTEGER DEFAULT 0,
            rejection_reasons TEXT DEFAULT '{}',
            quality_score REAL DEFAULT 1.0,
            last_rejected_at TEXT
        )
    """)

    # ---- item_comps table ----
    c.execute("""
        CREATE TABLE item_comps (
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

    # ---- regrade_log table ----
    c.execute("""
        CREATE TABLE regrade_log (
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

    # ---- Seed data ----

    # 1 test item
    c.execute("""
        INSERT INTO items (
            id, source, title, brand, source_price, source_shipping,
            grade, exact_sell_price, exact_profit, exact_margin, status
        ) VALUES (
            1, 'grailed', 'Geobasket Sneakers', 'Rick Owens',
            200, 0, 'B', 500, 300, 0.60, 'active'
        )
    """)

    # 5 sold comps (prices 400-600 in $50 increments)
    comp_titles = [
        "Rick Owens Geobasket High Top Sneakers",
        "Rick Owens Geobasket Leather Sneakers Black",
        "Rick Owens Geobasket Milk White Sneakers",
        "Rick Owens Geobasket Sneakers Size 42",
        "Rick Owens Geobasket Sneakers SS24",
    ]
    for i in range(5):
        comp_id = i + 1
        price = 400 + i * 50  # 400, 450, 500, 550, 600
        c.execute("""
            INSERT INTO sold_comps (
                id, search_key, brand, title, sold_price, size, source,
                source_id, condition, sold_date, times_matched, times_rejected,
                rejection_reasons, quality_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            comp_id, "rick owens geobasket", "Rick Owens",
            comp_titles[i], price, "42", "ebay",
            f"ebay_{comp_id}", "pre-owned", "2026-03-01",
            1, 0, "{}", 1.0,
        ))

    # 5 item_comps linking item 1 → sold_comps 1-5
    for i in range(5):
        comp_id = i + 1
        sim_score = round(0.9 - i * 0.1, 2)  # 0.9, 0.8, 0.7, 0.6, 0.5
        price = 400 + i * 50
        c.execute("""
            INSERT INTO item_comps (
                id, item_id, sold_comp_id, similarity_score, rank,
                feedback_status, snapshot_title, snapshot_price,
                snapshot_condition, snapshot_source, snapshot_sold_date,
                snapshot_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            comp_id, 1, comp_id, sim_score, comp_id,
            "pending", comp_titles[i], price,
            "pre-owned", "ebay", "2026-03-01",
            f"https://ebay.com/itm/ebay_{comp_id}",
        ))

    conn.commit()

    # Build a factory that always returns a wrapper around the SAME connection.
    def _fake_get_conn():
        return _FakePooledConn(conn)

    with patch("db.sqlite_models._get_conn", _fake_get_conn), \
         patch("api.services.comp_feedback._get_conn", _fake_get_conn):
        yield db_path

    conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCompFeedbackProcessing:
    def test_accept_comp(self, mock_db):
        """Acceptance should not trigger re-grade."""
        from api.services.comp_feedback import process_comp_feedback
        result = process_comp_feedback(1, 1, "accepted")
        assert result["updated"] is True
        assert result["regrade"]["triggered"] is False

    def test_reject_triggers_regrade_when_enough_comps(self, mock_db):
        """Rejection with >= 3 remaining comps should trigger re-grade."""
        from api.services.comp_feedback import process_comp_feedback
        result = process_comp_feedback(1, 1, "rejected", "wrong_model")
        assert result["updated"] is True
        assert result["regrade"]["triggered"] is True
        assert result["regrade"]["comps_remaining"] == 4

    def test_reject_flags_review_when_too_few_comps(self, mock_db):
        """Rejection below threshold should flag for review."""
        from api.services.comp_feedback import process_comp_feedback
        process_comp_feedback(1, 1, "rejected", "wrong_model")
        process_comp_feedback(1, 2, "rejected", "wrong_brand")
        result = process_comp_feedback(1, 3, "rejected", "outlier")
        assert result["regrade"]["triggered"] is False
        assert result["regrade"]["flagged_for_review"] is True
        assert result["regrade"]["comps_remaining"] == 2

    def test_rejection_updates_sold_comp_quality(self, mock_db):
        """Rejection should increment times_rejected and reduce quality_score."""
        from api.services.comp_feedback import process_comp_feedback
        process_comp_feedback(1, 1, "rejected", "wrong_model")

        conn = sqlite3.connect(str(mock_db))
        c = conn.cursor()
        c.execute("SELECT times_rejected, quality_score FROM sold_comps WHERE id = 1")
        row = c.fetchone()
        conn.close()
        assert row[0] == 1
        assert row[1] < 1.0

    def test_regrade_log_inserted(self, mock_db):
        """Rejection should create a regrade_log entry."""
        from api.services.comp_feedback import process_comp_feedback
        process_comp_feedback(1, 1, "rejected", "wrong_model")

        conn = sqlite3.connect(str(mock_db))
        c = conn.cursor()
        c.execute("SELECT * FROM regrade_log WHERE item_id = 1")
        rows = c.fetchall()
        conn.close()
        assert len(rows) == 1

    def test_snapshot_immutability(self, mock_db):
        """Snapshots must not change when sold_comps are modified."""
        conn = sqlite3.connect(str(mock_db))
        c = conn.cursor()
        c.execute("SELECT snapshot_title, snapshot_price FROM item_comps WHERE id = 2")
        original = c.fetchone()
        c.execute("UPDATE sold_comps SET title = 'MODIFIED', sold_price = 9999 WHERE id = 2")
        conn.commit()
        c.execute("SELECT snapshot_title, snapshot_price FROM item_comps WHERE id = 2")
        after = c.fetchone()
        conn.close()
        assert original[0] == after[0]
        assert original[1] == after[1]
