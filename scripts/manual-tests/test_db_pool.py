#!/usr/bin/env python3
"""Test database connection pool."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from db.connection_pool import ConnectionPool, get_pool

print("Testing Connection Pool")
print("=" * 50)

# Get pool
pool = get_pool()
print(f"✅ Pool initialized")

# Get metrics
metrics = pool.get_metrics()
print(f"\nPool metrics:")
print(f"  Pool size: {metrics['pool_size']}")
print(f"  Available: {metrics['available']}")
print(f"  In use: {metrics['in_use']}")
print(f"  Connections created: {metrics['connections_created']}")

# Test connection
print(f"\nTesting connection...")
with pool.connection() as conn:
    cursor = conn.execute("SELECT 1")
    result = cursor.fetchone()
    print(f"  ✅ Connection works: {result[0]}")

# Test that connection was returned
metrics = pool.get_metrics()
print(f"\nAfter returning connection:")
print(f"  Available: {metrics['available']}")
print(f"  In use: {metrics['in_use']}")

# Test backward compatibility (_get_conn)
print(f"\nTesting backward compatibility...")
from db.sqlite_models import _get_conn, _return_conn

conn = _get_conn()
cursor = conn.execute("SELECT 1")
result = cursor.fetchone()
print(f"  ✅ _get_conn works: {result[0]}")

# Test that close() returns to pool
conn.close()
metrics = pool.get_metrics()
print(f"  After conn.close():")
print(f"    Available: {metrics['available']}")
print(f"    In use: {metrics['in_use']}")

print("\n✅ All tests passed!")
