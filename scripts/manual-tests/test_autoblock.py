#!/usr/bin/env python3
"""Test auto-blocklist functionality."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.seller_manager import SellerManager

manager = SellerManager()

# Simulate 3 auth failures
seller = "suspicious_seller_456"

print(f"Testing auto-blocklist for '{seller}'")
print(f"Initial block count: {manager.get_block_count(seller)}")
print(f"Is blocked: {manager.is_blocked(seller)}")

print("\nSimulating auth failures...")
for i in range(1, 4):
    was_blocked = manager.record_auth_failure(seller)
    print(f"  Failure {i}: blocked={was_blocked}, count={manager.get_block_count(seller)}")

print(f"\nFinal state:")
print(f"  Is blocked: {manager.is_blocked(seller)}")
print(f"  Block count: {manager.get_block_count(seller)}")

# Show stats
stats = manager.get_stats()
print(f"\nStats:")
print(f"  Blocked count: {stats['blocked_count']}")
print(f"  Auto-blocked: {stats['auto_blocked']}")

# Cleanup
manager.unblock_seller(seller)
manager.unblock_seller("bad_seller_123")
print("\n✅ Test complete, cleaned up test sellers")
