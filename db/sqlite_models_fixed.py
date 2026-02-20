"""
SQLite database models for Archive Arbitrage MVP.
Simpler than PostgreSQL, works out of the box.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, asdict

DB_PATH = Path(__file__).parent.parent / "data" / "archive.db"


def _add_column_if_missing(cursor, table: str, column: str, col_type: str):
    """Add a column to a table if it doesn't exist."""
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        return True
    return False


@dataclass
class Item:
    """A scraped item with authentication data."""
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
    images: List[str] = None
    is_auction: bool = False
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # Authentication columns
    auth_status: Optional[str] = None  # authentic, suspicious, replica
    auth_confidence: Optional[float] = None  # 0.0-1.0
    auth_reasons: Optional[List[str]] = None  # List of reasons for the status