"""
Product Catalog Refresh — recompute all product stats from sold_comps.

Maps new comps to products, registers new products, recomputes pricing
and freshness stats. Designed to run at the start of every gap_hunter cycle.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from statistics import median as calc_median
from typing import Dict, Any

logger = logging.getLogger("catalog_refresh")

DB_PATH = None  # Set on first call


def detect_bimodal(prices: list) -> dict:
    """Detect bimodal price distribution by finding the largest relative gap."""
    if len(prices) < 10:
        return {"is_bimodal": False}

    sorted_p = sorted(prices)
    n = len(sorted_p)

    max_gap_ratio = 0.0
    gap_index = 0

    for i in range(1, n):
        if sorted_p[i - 1] <= 0:
            continue
        ratio = (sorted_p[i] - sorted_p[i - 1]) / sorted_p[i - 1]
        if ratio > max_gap_ratio:
            max_gap_ratio = ratio
            gap_index = i

    low = sorted_p[:gap_index]
    high = sorted_p[gap_index:]

    if max_gap_ratio > 0.50 and len(low) >= 3 and len(high) >= 3:
        return {
            "is_bimodal": True,
            "gap": round(max_gap_ratio, 2),
            "low_median": calc_median(low),
            "high_median": calc_median(high),
            "low_count": len(low),
            "high_count": len(high),
        }
    return {"is_bimodal": False}


def trimmed_median(prices: list, trim_pct: float = 0.10) -> float:
    """Compute median after trimming top and bottom trim_pct of values."""
    if not prices:
        return 0.0
    sorted_p = sorted(prices)
    n = len(sorted_p)
    trim_n = max(1, int(n * trim_pct))
    if n <= trim_n * 2 + 1:
        return calc_median(sorted_p)
    trimmed = sorted_p[trim_n:-trim_n]
    return calc_median(trimmed)


def _get_db_path():
    global DB_PATH
    if DB_PATH is None:
        from db.sqlite_models import DB_PATH as _p
        DB_PATH = _p
    return DB_PATH


def _get_conn():
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def refresh_product_catalog(verbose: bool = False) -> Dict[str, Any]:
    """Recompute all product stats from current sold_comps data.

    1. Maps new comps (product_id IS NULL) to existing products
    2. Registers new products for unmapped high-confidence comps
    3. Recomputes all stats: pricing, freshness, confidence tier

    Returns summary dict with counts of changes made.
    """
    from scrapers.product_fingerprint import parse_title_to_fingerprint

    conn = _get_conn()
    c = conn.cursor()

    stats = {
        "new_comps_mapped": 0,
        "new_products": 0,
        "tier_changes": 0,
        "price_drifts": [],
        "total_products": 0,
        "guaranteed_count": 0,
        "high_count": 0,
    }

    # ── Phase 1: Map new comps to products ──
    c.execute("""
        SELECT id, brand, title FROM sold_comps
        WHERE product_id IS NULL AND title IS NOT NULL AND brand IS NOT NULL
        LIMIT 5000
    """)
    unmapped = c.fetchall()

    if unmapped:
        # Build fingerprint lookup cache
        c.execute("SELECT id, fingerprint_hash FROM products")
        fp_to_id = {row["fingerprint_hash"]: row["id"] for row in c.fetchall()}

        batch_updates = []
        new_products_batch = []

        for row in unmapped:
            brand = row["brand"] or ""
            if not brand:
                continue
            fp = parse_title_to_fingerprint(brand.lower(), row["title"])
            if fp.confidence == "low" and not fp.model:
                continue

            pid = fp_to_id.get(fp.fingerprint_hash)
            if pid:
                batch_updates.append((pid, row["id"]))
                stats["new_comps_mapped"] += 1
            else:
                # Register new product
                try:
                    c.execute("""
                        INSERT INTO products (brand, sub_brand, model, item_type, material, color, fingerprint_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (fp.brand, fp.sub_brand, fp.model, fp.item_type, fp.material, fp.color, fp.fingerprint_hash))
                    new_pid = c.lastrowid
                    fp_to_id[fp.fingerprint_hash] = new_pid
                    batch_updates.append((new_pid, row["id"]))
                    stats["new_products"] += 1
                    stats["new_comps_mapped"] += 1
                except sqlite3.IntegrityError:
                    pass  # Duplicate fingerprint — race condition, safe to skip

        # Batch update product_ids
        for pid, sc_id in batch_updates:
            c.execute("UPDATE sold_comps SET product_id = ? WHERE id = ?", (pid, sc_id))
        conn.commit()

    # ── Phase 2: Recompute all product stats ──
    now_str = datetime.utcnow().isoformat()
    cutoff_90 = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")
    cutoff_180 = (datetime.utcnow() - timedelta(days=180)).strftime("%Y-%m-%d")

    c.execute("SELECT id FROM products")
    product_ids = [row["id"] for row in c.fetchall()]

    for pid in product_ids:
        # Get all comps for this product
        c.execute("""
            SELECT sold_price, sold_date FROM sold_comps
            WHERE product_id = ? AND sold_price > 0
        """, (pid,))
        comps = c.fetchall()

        if not comps:
            continue

        prices = [r["sold_price"] for r in comps]
        total = len(prices)
        avg_p = sum(prices) / total
        med_p = calc_median(prices)
        min_p = min(prices)
        max_p = max(prices)

        # Freshness stats
        dated_count = 0
        recent_count = 0
        very_recent_count = 0
        newest_date = None
        oldest_date = None
        recent_prices = []

        for r in comps:
            sd = r["sold_date"]
            if sd and isinstance(sd, str) and len(sd) >= 10:
                dated_count += 1
                date_str = sd[:10]
                if newest_date is None or date_str > newest_date:
                    newest_date = date_str
                if oldest_date is None or date_str < oldest_date:
                    oldest_date = date_str
                if date_str >= cutoff_180:
                    recent_count += 1
                    recent_prices.append(r["sold_price"])
                if date_str >= cutoff_90:
                    very_recent_count += 1

        # Data freshness classification
        if dated_count < total * 0.3:
            freshness = "unknown"
        elif very_recent_count >= 5:
            freshness = "fresh"
        elif recent_count >= 5:
            freshness = "aging"
        else:
            freshness = "stale"

        # Recent median
        recent_med = calc_median(recent_prices) if len(recent_prices) >= 5 else None

        # Check for price drift
        if recent_med is not None and med_p > 0:
            drift = abs(recent_med - med_p) / med_p
            if drift > 0.15:
                stats["price_drifts"].append({
                    "product_id": pid,
                    "all_time": round(med_p),
                    "recent": round(recent_med),
                    "drift_pct": round(drift * 100, 1),
                })
                if verbose:
                    logger.warning(
                        "Price drift on product %d: $%.0f → $%.0f (%.0f%% drift)",
                        pid, med_p, recent_med, drift * 100,
                    )

        # Bimodal detection
        bimodal = detect_bimodal(prices)
        is_bimodal = 1 if bimodal.get("is_bimodal") else 0
        bimodal_gap = bimodal.get("gap")
        low_cluster_med = bimodal.get("low_median")
        high_cluster_med = bimodal.get("high_median")

        if is_bimodal and verbose:
            logger.warning(
                "Bimodal pricing on product %d: low $%.0f (%d), high $%.0f (%d)",
                pid, low_cluster_med, bimodal.get("low_count", 0),
                high_cluster_med, bimodal.get("high_count", 0),
            )

        # Trimmed median (drop top/bottom 10% for robustness)
        t_med = trimmed_median(prices, 0.10)

        # Confidence tier
        spread = (max_p - min_p) / med_p if med_p > 0 else 0
        if is_bimodal:
            pass  # Bimodal → moderate at best, never guaranteed
        elif total >= 10 and spread <= 1.5:
            tier = "guaranteed"
            stats["guaranteed_count"] += 1
        elif total >= 10 and spread <= 2.0:
            tier = "high"
            stats["high_count"] += 1
        elif total >= 10:
            pass  # moderate
        # else insufficient

        # Update product
        c.execute("""
            UPDATE products SET
                total_sales=?, avg_price=?, min_price=?, max_price=?, median_price=?,
                dated_comp_count=?, recent_comp_count=?, very_recent_comp_count=?,
                data_freshness=?, newest_comp_date=?, oldest_comp_date=?,
                recent_median_price=?, trimmed_median_price=?,
                is_bimodal=?, bimodal_gap=?, low_cluster_median=?, high_cluster_median=?,
                updated_at=?
            WHERE id=?
        """, (
            total, round(avg_p, 2), min_p, max_p, round(med_p, 2),
            dated_count, recent_count, very_recent_count,
            freshness, newest_date, oldest_date,
            round(recent_med, 2) if recent_med else None,
            round(t_med, 2),
            is_bimodal, bimodal_gap, low_cluster_med, high_cluster_med,
            now_str,
            pid,
        ))

    conn.commit()

    stats["total_products"] = len(product_ids)
    conn.close()

    if stats["new_comps_mapped"] > 0 or stats["new_products"] > 0 or verbose:
        logger.info(
            "Catalog refreshed: %d new comps, %d new products, %d guaranteed, %d high",
            stats["new_comps_mapped"], stats["new_products"],
            stats["guaranteed_count"], stats["high_count"],
        )
    if stats["price_drifts"]:
        logger.warning("Price drift on %d products", len(stats["price_drifts"]))

    return stats
