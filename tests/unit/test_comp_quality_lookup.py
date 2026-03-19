"""Tests for batch quality score lookup."""

import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from contextlib import contextmanager


def _make_in_memory_db():
    """Create an in-memory SQLite DB with the sold_comps table."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sold_comps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_key TEXT,
            brand TEXT,
            title TEXT,
            sold_price REAL,
            source TEXT,
            source_id TEXT,
            quality_score REAL DEFAULT 1.0
        )
    """)
    conn.commit()
    return conn


class TestGetCompQualityScores:
    def setup_method(self):
        """Use in-memory DB for tests."""
        self._mem_conn = _make_in_memory_db()
        c = self._mem_conn.cursor()
        c.execute(
            "INSERT INTO sold_comps (search_key, brand, title, sold_price, source, source_id, quality_score) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("test", "rick owens", "RO Geobasket", 500, "grailed", "g123", 0.8),
        )
        c.execute(
            "INSERT INTO sold_comps (search_key, brand, title, sold_price, source, source_id, quality_score) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("test", "rick owens", "RO Ramones", 300, "grailed", "g456", 0.3),
        )
        self._mem_conn.commit()

    def teardown_method(self):
        self._mem_conn.close()

    def _patched_get_conn(self):
        """Return a wrapper whose .close() is a no-op (keeps in-memory DB alive)."""
        mem = self._mem_conn

        class _FakeConn:
            def cursor(self_inner):
                return mem.cursor()

            def close(self_inner):
                pass  # don't close — we manage lifecycle in teardown_method

            def __getitem__(self_inner, key):
                return mem[key]

        return _FakeConn()

    def _run(self, pairs):
        import db.sqlite_models as sm

        # Patch _get_conn to return a fake connection backed by in-memory DB
        mem = self._mem_conn

        class _FakeConn:
            def cursor(self):
                return mem.cursor()

            def close(self):
                pass

        with patch.object(sm, "_get_conn", return_value=_FakeConn()):
            from db.sqlite_models import get_comp_quality_scores
            return get_comp_quality_scores(pairs)

    def test_returns_known_scores(self):
        scores = self._run([("grailed", "g123"), ("grailed", "g456")])
        assert scores[("grailed", "g123")] == 0.8
        assert scores[("grailed", "g456")] == 0.3

    def test_returns_1_for_unknown(self):
        scores = self._run([("grailed", "unknown")])
        assert scores[("grailed", "unknown")] == 1.0

    def test_empty_input(self):
        from db.sqlite_models import get_comp_quality_scores
        scores = get_comp_quality_scores([])
        assert scores == {}

    def test_mixed_known_and_unknown(self):
        scores = self._run([("grailed", "g123"), ("ebay", "e999")])
        assert scores[("grailed", "g123")] == 0.8
        assert scores[("ebay", "e999")] == 1.0
