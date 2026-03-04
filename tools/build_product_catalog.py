"""
Product Catalog Builder — Phase 2A

Builds the canonical product catalog from sold comps data.

Usage:
    python build_product_catalog.py           # Build from all sold_comps
    python build_product_catalog.py --reset   # Clear and rebuild
"""

import asyncio
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from db.sqlite_models import (
    init_db, get_or_create_product, add_product_sale, 
    get_product_by_fingerprint, DB_PATH
)
from scrapers.product_fingerprint import parse_title_to_fingerprint, cluster_titles_to_products


def get_all_sold_comps_from_db():
    """Fetch all sold comps from the database."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT brand, title, sold_price, size, sold_url, source, source_id, fetched_at
        FROM sold_comps
        WHERE brand IS NOT NULL AND title IS NOT NULL
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "brand": row["brand"],
            "title": row["title"],
            "price": row["sold_price"],
            "size": row["size"],
            "url": row["sold_url"],
            "source": row["source"],
            "source_id": row["source_id"],
            "sold_at": row["fetched_at"],
        }
        for row in rows
    ]


def build_catalog(min_samples: int = 3, reset: bool = False):
    """Build the product catalog from sold comps."""
    
    if reset:
        print("⚠️  Resetting product catalog...")
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM product_prices")
        cursor.execute("DELETE FROM products")
        conn.commit()
        conn.close()
        print("✅ Catalog cleared")
    
    # Initialize DB (creates tables if needed)
    init_db()
    
    print("\n📦 Building product catalog...")
    print(f"   Min samples per product: {min_samples}")
    
    # Fetch all sold comps
    print("\n⏳ Fetching sold comps from database...")
    comps = get_all_sold_comps_from_db()
    print(f"   Found {len(comps):,} sold comps")
    
    if len(comps) < min_samples * 10:
        print(f"\n⚠️  Not enough comps to build catalog (need {min_samples * 10}+)")
        print("   Run some scrapes first to collect sold data.")
        return
    
    # Convert to format for clustering
    print("\n⏳ Clustering titles into products...")
    title_tuples = [(c["brand"], c["title"], c["price"]) for c in comps]
    clusters = cluster_titles_to_products(title_tuples)
    print(f"   Found {len(clusters)} potential products")
    
    # Filter to products with enough samples
    valid_clusters = {
        h: listings for h, listings in clusters.items() 
        if len(listings) >= min_samples
    }
    print(f"   {len(valid_clusters)} products have {min_samples}+ samples")
    
    # Create products and add sales
    print("\n⏳ Creating products and recording sales...")
    products_created = 0
    sales_added = 0
    
    for fp_hash, listings in valid_clusters.items():
        # Use first listing to get fingerprint
        brand, title, _ = listings[0]
        fp = parse_title_to_fingerprint(brand, title)
        
        # Skip incomplete fingerprints
        if not fp.is_complete():
            continue
        
        # Get or create product
        product = get_or_create_product(
            fingerprint_hash=fp_hash,
            canonical_name=fp.canonical_name,
            brand=fp.brand,
            sub_brand=fp.sub_brand,
            model=fp.model,
            item_type=fp.item_type,
            material=fp.material,
        )
        products_created += 1
        
        # Add sales for this product
        # Find matching comps for this cluster
        for comp in comps:
            comp_fp = parse_title_to_fingerprint(comp["brand"], comp["title"])
            if comp_fp.fingerprint_hash == fp_hash:
                add_product_sale(
                    product_id=product.id,
                    sold_price=comp["price"],
                    sold_at=comp["sold_at"] or datetime.utcnow().isoformat(),
                    size=comp["size"],
                    source=comp["source"],
                    source_id=comp["source_id"],
                )
                sales_added += 1
        
        if products_created % 50 == 0:
            print(f"   ...{products_created} products, {sales_added} sales")
    
    print(f"\n✅ Catalog built!")
    print(f"   Products created: {products_created}")
    print(f"   Sales recorded: {sales_added}")
    
    # Print stats
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM products WHERE is_high_velocity = 1")
    high_vel = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM products WHERE total_sales >= 10")
    ten_plus = cursor.fetchone()[0]
    
    cursor.execute("SELECT brand, COUNT(*) FROM products GROUP BY brand ORDER BY COUNT(*) DESC LIMIT 5")
    top_brands = cursor.fetchall()
    
    conn.close()
    
    print(f"\n📊 Catalog Stats:")
    print(f"   High velocity products (5+ sales/30d): {high_vel}")
    print(f"   Products with 10+ sales: {ten_plus}")
    print(f"   Top brands by product count:")
    for brand, count in top_brands:
        print(f"     {brand}: {count}")


def show_catalog(brand: str = None, min_sales: int = 5, limit: int = 20):
    """Show products in the catalog."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM products WHERE total_sales >= ?"
    params = [min_sales]
    
    if brand:
        query += " AND brand = ?"
        params.append(brand.lower())
    
    query += " ORDER BY sales_30d DESC, total_sales DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    print(f"\n📦 Products (min {min_sales} sales):")
    print("-" * 80)
    
    for row in rows:
        velocity = "🔥" if row["is_high_velocity"] else "  "
        print(f"{velocity} {row['canonical_name']}")
        print(f"   Sales: {row['total_sales']} total, {row['sales_30d']} in 30d ({row['velocity_trend']})")
        print()
    
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build product catalog from sold comps")
    parser.add_argument("--reset", action="store_true", help="Clear and rebuild catalog")
    parser.add_argument("--min-samples", type=int, default=3, help="Min samples per product")
    parser.add_argument("--show", action="store_true", help="Show catalog")
    parser.add_argument("--brand", type=str, help="Filter by brand")
    
    args = parser.parse_args()
    
    if args.show:
        show_catalog(brand=args.brand)
    else:
        build_catalog(min_samples=args.min_samples, reset=args.reset)
