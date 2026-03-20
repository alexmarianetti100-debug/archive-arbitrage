#!/usr/bin/env python3
"""
Seller Blocklist Manager

Manages seller blocklist with:
- Persistent storage
- Auto-blocklist after N auth failures
- In-memory caching
- Atomic file operations
- Thread-safe operations
"""

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

logger = logging.getLogger("seller_manager")

DEFAULT_BLOCKLIST_FILE = Path(__file__).parent.parent / "data" / "seller_blocklist.json"
AUTO_BLOCKLIST_THRESHOLD = 3  # Auto-block after 3 auth failures


class SellerManager:
    """
    Manages seller blocklist with persistence and auto-blocking.
    
    Usage:
        manager = SellerManager()
        
        # Check if seller is blocked
        if manager.is_blocked("seller_name"):
            return
        
        # Record auth failure
        manager.record_auth_failure("seller_name")
        
        # Manually block/unblock
        manager.block_seller("bad_seller")
        manager.unblock_seller("reformed_seller")
        
        # Get stats
        stats = manager.get_stats()
    """
    
    def __init__(self, blocklist_file: Optional[Path] = None):
        self.blocklist_file = blocklist_file or DEFAULT_BLOCKLIST_FILE
        self._blocklist: Set[str] = set()
        self._block_counts: Dict[str, int] = {}
        self._block_reasons: Dict[str, str] = {}  # seller -> reason
        self._block_timestamps: Dict[str, str] = {}  # seller -> ISO timestamp
        self._lock = threading.Lock()
        self._last_save = 0
        self._dirty = False
        
        # Ensure directory exists
        self.blocklist_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing blocklist
        self._load()
    
    def _load(self) -> bool:
        """Load blocklist from disk."""
        try:
            if not self.blocklist_file.exists():
                logger.info(f"No existing blocklist at {self.blocklist_file}")
                return False
            
            with open(self.blocklist_file, 'r') as f:
                data = json.load(f)
            
            with self._lock:
                self._blocklist = set(data.get("blocklist", []))
                self._block_counts = data.get("block_counts", {})
                self._block_reasons = data.get("block_reasons", {})
                self._block_timestamps = data.get("block_timestamps", {})
            
            logger.info(f"Loaded blocklist: {len(self._blocklist)} sellers blocked")
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted blocklist file: {e}")
            self._backup_corrupted_file()
            return False
        except Exception as e:
            logger.error(f"Failed to load blocklist: {e}")
            return False
    
    def _save(self, force: bool = False) -> bool:
        """Save blocklist to disk (atomic operation)."""
        # Throttle saves to once per 5 seconds unless forced
        if not force and time.time() - self._last_save < 5:
            self._dirty = True
            return True
        
        try:
            with self._lock:
                data = {
                    "blocklist": sorted(list(self._blocklist)),
                    "block_counts": self._block_counts,
                    "block_reasons": self._block_reasons,
                    "block_timestamps": self._block_timestamps,
                    "updated_at": datetime.now().isoformat(),
                    "version": 1,
                }
            
            # Atomic write: write to temp file, then rename
            temp_file = self.blocklist_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Atomic rename
            temp_file.replace(self.blocklist_file)
            
            self._last_save = time.time()
            self._dirty = False
            
            logger.debug(f"Saved blocklist: {len(self._blocklist)} sellers")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save blocklist: {e}")
            return False
    
    def _backup_corrupted_file(self):
        """Backup corrupted blocklist file."""
        try:
            if self.blocklist_file.exists():
                backup_path = self.blocklist_file.with_suffix('.corrupted')
                self.blocklist_file.rename(backup_path)
                logger.warning(f"Backed up corrupted blocklist to {backup_path}")
        except Exception as e:
            logger.error(f"Failed to backup corrupted file: {e}")
    
    def is_blocked(self, seller: str) -> bool:
        """Check if a seller is blocklisted."""
        if not seller:
            return False
        key = seller.lower().strip()
        return key in self._blocklist
    
    def block_seller(self, seller: str, reason: str = "manual") -> bool:
        """Manually block a seller."""
        if not seller:
            return False
        
        key = seller.lower().strip()
        
        with self._lock:
            if key in self._blocklist:
                logger.debug(f"Seller '{seller}' already blocked")
                return False
            
            self._blocklist.add(key)
            self._block_reasons[key] = reason
            self._block_timestamps[key] = datetime.now().isoformat()
        
        logger.info(f"🚫 Blocked seller '{seller}' (reason: {reason})")
        self._save()
        return True
    
    def unblock_seller(self, seller: str) -> bool:
        """Unblock a seller."""
        if not seller:
            return False
        
        key = seller.lower().strip()
        
        with self._lock:
            if key not in self._blocklist:
                logger.debug(f"Seller '{seller}' not in blocklist")
                return False
            
            self._blocklist.discard(key)
            self._block_counts.pop(key, None)
            self._block_reasons.pop(key, None)
            self._block_timestamps.pop(key, None)
        
        logger.info(f"✅ Unblocked seller '{seller}'")
        self._save()
        return True
    
    def record_auth_failure(self, seller: str) -> bool:
        """
        Record an auth failure for a seller.
        Auto-blocklist after AUTO_BLOCKLIST_THRESHOLD failures.
        """
        if not seller:
            return False
        
        key = seller.lower().strip()
        
        with self._lock:
            # Increment count
            self._block_counts[key] = self._block_counts.get(key, 0) + 1
            count = self._block_counts[key]
        
        logger.debug(f"Auth failure for '{seller}' (count: {count})")
        
        # Auto-blocklist after threshold
        if count >= AUTO_BLOCKLIST_THRESHOLD and not self.is_blocked(seller):
            self.block_seller(seller, reason=f"auto_blocked_after_{count}_auth_failures")
            return True
        
        # Save counts (throttled)
        self._save()
        return False
    
    def get_block_count(self, seller: str) -> int:
        """Get auth failure count for a seller."""
        if not seller:
            return 0
        key = seller.lower().strip()
        return self._block_counts.get(key, 0)
    
    def get_blocked_sellers(self) -> List[Dict[str, Any]]:
        """Get list of blocked sellers with metadata."""
        with self._lock:
            return [
                {
                    "seller": seller,
                    "reason": self._block_reasons.get(seller, "unknown"),
                    "timestamp": self._block_timestamps.get(seller),
                    "auth_failures": self._block_counts.get(seller, 0),
                }
                for seller in sorted(self._blocklist)
            ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get blocklist statistics."""
        with self._lock:
            return {
                "blocked_count": len(self._blocklist),
                "total_auth_failures": sum(self._block_counts.values()),
                "sellers_with_failures": len(self._block_counts),
                "auto_blocked": sum(
                    1 for r in self._block_reasons.values()
                    if r.startswith("auto_blocked")
                ),
                "manually_blocked": sum(
                    1 for r in self._block_reasons.values()
                    if r == "manual"
                ),
            }
    
    def clear_blocklist(self, confirm: bool = False) -> bool:
        """Clear all blocked sellers (use with caution!)."""
        if not confirm:
            logger.warning("Clear blocklist called without confirmation - use confirm=True")
            return False
        
        with self._lock:
            count = len(self._blocklist)
            self._blocklist.clear()
            self._block_counts.clear()
            self._block_reasons.clear()
            self._block_timestamps.clear()
        
        logger.warning(f"🗑️  Cleared blocklist ({count} sellers removed)")
        self._save(force=True)
        return True
    
    def flush(self):
        """Force save any pending changes."""
        if self._dirty:
            self._save(force=True)


# Convenience functions for CLI usage
def block_seller_cli(seller: str, reason: str = "manual"):
    """CLI helper to block a seller."""
    manager = SellerManager()
    if manager.block_seller(seller, reason):
        print(f"✅ Blocked seller: {seller}")
    else:
        print(f"⚠️  Seller already blocked or invalid: {seller}")


def unblock_seller_cli(seller: str):
    """CLI helper to unblock a seller."""
    manager = SellerManager()
    if manager.unblock_seller(seller):
        print(f"✅ Unblocked seller: {seller}")
    else:
        print(f"⚠️  Seller not in blocklist: {seller}")


def list_blocked_cli():
    """CLI helper to list blocked sellers."""
    manager = SellerManager()
    sellers = manager.get_blocked_sellers()
    stats = manager.get_stats()
    
    print(f"\n🚫 Blocked Sellers ({stats['blocked_count']} total)\n")
    print(f"{'Seller':<30} {'Reason':<30} {'Failures':<10}")
    print("-" * 80)
    
    for s in sellers:
        reason = s['reason'][:28] if s['reason'] else 'unknown'
        print(f"{s['seller']:<30} {reason:<30} {s['auth_failures']:<10}")
    
    print(f"\nStats:")
    print(f"  Auto-blocked: {stats['auto_blocked']}")
    print(f"  Manually blocked: {stats['manually_blocked']}")
    print(f"  Total auth failures tracked: {stats['total_auth_failures']}")


def clear_blocklist_cli():
    """CLI helper to clear blocklist."""
    manager = SellerManager()
    stats = manager.get_stats()
    
    print(f"\n⚠️  WARNING: This will remove {stats['blocked_count']} sellers from blocklist")
    confirm = input("Type 'CLEAR' to confirm: ")
    
    if confirm == "CLEAR":
        if manager.clear_blocklist(confirm=True):
            print("✅ Blocklist cleared")
        else:
            print("❌ Failed to clear blocklist")
    else:
        print("Cancelled")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Seller Blocklist Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Block command
    block_parser = subparsers.add_parser("block", help="Block a seller")
    block_parser.add_argument("seller", help="Seller name to block")
    block_parser.add_argument("--reason", default="manual", help="Reason for blocking")
    
    # Unblock command
    unblock_parser = subparsers.add_parser("unblock", help="Unblock a seller")
    unblock_parser.add_argument("seller", help="Seller name to unblock")
    
    # List command
    subparsers.add_parser("list", help="List blocked sellers")
    
    # Stats command
    subparsers.add_parser("stats", help="Show blocklist statistics")
    
    # Clear command
    subparsers.add_parser("clear", help="Clear all blocked sellers")
    
    args = parser.parse_args()
    
    if args.command == "block":
        block_seller_cli(args.seller, args.reason)
    elif args.command == "unblock":
        unblock_seller_cli(args.seller)
    elif args.command == "list":
        list_blocked_cli()
    elif args.command == "stats":
        manager = SellerManager()
        stats = manager.get_stats()
        print("\nBlocklist Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    elif args.command == "clear":
        clear_blocklist_cli()
    else:
        parser.print_help()
