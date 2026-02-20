"""
Scan existing database for replicas and suspicious items.
Run this to clean up the current inventory.
"""

import sys
sys.path.insert(0, ".")

from db.sqlite_models import init_db, get_items
from authenticity_checker import AuthenticityChecker, AuthStatus


def scan_existing_items():
    """Scan all items in database for replicas."""
    print("🔍 Scanning existing items for replicas...")
    print("=" * 60)
    
    init_db()
    items = get_items(status="active", limit=10000)
    
    checker = AuthenticityChecker()
    
    replicas = []
    suspicious = []
    
    for item in items:
        result = checker.check_item(
            title=item.title,
            description="",  # Items don't store description in current schema
            price=item.source_price,
            brand=item.brand or "",
            seller_name=getattr(item, 'seller', '') or "",
            images=item.images or [],
        )
        
        if result.status == AuthStatus.REPLICA:
            replicas.append({
                "id": item.id,
                "title": item.title[:60],
                "price": item.source_price,
                "brand": item.brand,
                "reasons": result.reasons[:2],
            })
        elif result.status == AuthStatus.SUSPICIOUS:
            suspicious.append({
                "id": item.id,
                "title": item.title[:60],
                "price": item.source_price,
                "brand": item.brand,
                "reasons": result.reasons[:2],
            })
    
    print(f"\n📊 SCAN RESULTS:")
    print(f"   Total items scanned: {len(items)}")
    print(f"   🚫 REPLICAS found: {len(replicas)}")
    print(f"   ⚠️  SUSPICIOUS items: {len(suspicious)}")
    
    if replicas:
        print(f"\n🚫 REPLICAS (Auto-reject these):")
        for r in replicas[:10]:  # Show first 10
            print(f"   ID {r['id']}: {r['title']}...")
            print(f"      ${r['price']} | {r['brand']} | {', '.join(r['reasons'])}")
        if len(replicas) > 10:
            print(f"   ... and {len(replicas) - 10} more")
    
    if suspicious:
        print(f"\n⚠️  SUSPICIOUS (Review manually):")
        for s in suspicious[:10]:
            print(f"   ID {s['id']}: {s['title']}...")
            print(f"      ${s['price']} | {s['brand']} | {', '.join(s['reasons'])}")
        if len(suspicious) > 10:
            print(f"   ... and {len(suspicious) - 10} more")
    
    print(f"\n✅ Clean items: {len(items) - len(replicas) - len(suspicious)}")
    
    return replicas, suspicious


if __name__ == "__main__":
    replicas, suspicious = scan_existing_items()
    
    # Optionally delete replicas
    if replicas and input(f"\nDelete {len(replicas)} replicas from database? (yes/no): ").lower() == "yes":
        from db.sqlite_models import delete_item
        deleted = 0
        for r in replicas:
            if delete_item(r["id"]):
                deleted += 1
        print(f"✅ Deleted {deleted} replica items")
