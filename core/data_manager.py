#!/usr/bin/env python3
"""
Data Manager - Unified data persistence with pruning and retention policies.

Manages all JSON state files with:
- Automatic size-based pruning
- TTL-based expiration
- Atomic file operations
- Compression for large files
- Metrics and monitoring
"""

import gzip
import json
import logging
import os
import shutil
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger("data_manager")

# Default retention policies
DEFAULT_POLICIES = {
    "image_hashes": {
        "max_size_mb": 10,
        "max_entries": 50000,
        "ttl_days": 30,
        "compress": True,
    },
    "gap_state": {
        "max_size_mb": 1,
        "max_entries": 10000,
        "ttl_days": 90,
        "compress": False,
    },
    "sold_cache": {
        "max_size_mb": 5,
        "max_entries": 10000,
        "ttl_days": 7,  # Sold data gets stale quickly
        "compress": False,
    },
    "price_cache": {
        "max_size_mb": 1,
        "max_entries": 1000,
        "ttl_days": 1,
        "compress": False,
    },
}


class DataManager:
    """
    Manages JSON data files with automatic pruning and retention.
    
    Usage:
        manager = DataManager()
        
        # Load data
        data = manager.load("image_hashes")
        
        # Save data
        manager.save("image_hashes", data)
        
        # Prune old data
        manager.prune("image_hashes")
        
        # Get metrics
        metrics = manager.get_metrics()
    """
    
    def __init__(self, data_dir: Optional[Path] = None, policies: Optional[Dict] = None):
        self.data_dir = data_dir or Path(__file__).parent.parent / "data"
        self.policies = policies or DEFAULT_POLICIES
        self._cache: Dict[str, Any] = {}
        self._cache_time: Dict[str, float] = {}
        self._cache_ttl = 5  # seconds
        
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Run initial pruning
        self.prune_all()
    
    def _get_file_path(self, name: str) -> Path:
        """Get the file path for a data file."""
        # Check for compressed version first
        compressed_path = self.data_dir / f"{name}.json.gz"
        normal_path = self.data_dir / f"{name}.json"
        
        if compressed_path.exists():
            return compressed_path
        return normal_path
    
    def _get_temp_path(self, name: str) -> Path:
        """Get a temporary file path for atomic writes."""
        return self.data_dir / f".{name}.tmp"
    
    def load(self, name: str, default: Any = None) -> Any:
        """
        Load data from file.
        
        Args:
            name: Base name of the data file (without .json extension)
            default: Default value if file doesn't exist
            
        Returns:
            Parsed JSON data or default
        """
        # Check cache first
        if name in self._cache:
            if time.time() - self._cache_time.get(name, 0) < self._cache_ttl:
                return self._cache[name]
        
        file_path = self._get_file_path(name)
        
        if not file_path.exists():
            return default if default is not None else {}
        
        try:
            if file_path.suffix == '.gz':
                with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            # Cache the result
            self._cache[name] = data
            self._cache_time[name] = time.time()
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted data file {file_path}: {e}")
            self._backup_corrupted_file(file_path)
            return default if default is not None else {}
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
            return default if default is not None else {}
    
    def save(self, name: str, data: Any, compress: Optional[bool] = None) -> bool:
        """
        Save data to file atomically.
        
        Args:
            name: Base name of the data file
            data: Data to save (must be JSON serializable)
            compress: Whether to gzip compress (defaults to policy)
            
        Returns:
            True if successful
        """
        policy = self.policies.get(name, {})
        should_compress = compress if compress is not None else policy.get('compress', False)
        
        file_path = self.data_dir / f"{name}.json"
        if should_compress:
            file_path = file_path.with_suffix('.json.gz')
        
        temp_path = self._get_temp_path(name)
        
        try:
            # Write to temp file
            if should_compress:
                with gzip.open(temp_path, 'wt', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
            else:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
            
            # Atomic rename
            temp_path.replace(file_path)
            
            # Update cache
            self._cache[name] = data
            self._cache_time[name] = time.time()
            
            logger.debug(f"Saved {name}: {len(json.dumps(data))} bytes")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save {name}: {e}")
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()
            return False
    
    def prune(self, name: str, force: bool = False) -> Dict[str, Any]:
        """
        Prune data according to retention policy.
        
        Args:
            name: Name of the data file
            force: Force pruning even if not due
            
        Returns:
            Statistics about pruning operation
        """
        policy = self.policies.get(name)
        if not policy:
            return {"error": "No policy defined"}
        
        file_path = self._get_file_path(name)
        if not file_path.exists():
            return {"status": "no_file"}
        
        # Check if pruning is needed
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        max_size = policy.get('max_size_mb', float('inf'))
        
        if not force and file_size_mb < max_size * 0.8:  # Prune at 80% threshold
            return {
                "status": "skipped",
                "file_size_mb": round(file_size_mb, 2),
                "threshold_mb": max_size * 0.8,
            }
        
        # Load data
        data = self.load(name, {})
        if not data:
            return {"status": "empty"}
        
        original_count = len(data) if isinstance(data, (dict, list)) else 1
        
        # Apply pruning strategies
        if isinstance(data, dict):
            data = self._prune_dict(data, policy)
        elif isinstance(data, list):
            data = self._prune_list(data, policy)
        
        # Save pruned data
        if self.save(name, data):
            new_size_mb = self._get_file_path(name).stat().st_size / (1024 * 1024)
            new_count = len(data) if isinstance(data, (dict, list)) else 1
            
            result = {
                "status": "pruned",
                "original_entries": original_count,
                "new_entries": new_count,
                "removed": original_count - new_count,
                "original_size_mb": round(file_size_mb, 2),
                "new_size_mb": round(new_size_mb, 2),
                "reduction_percent": round((1 - new_size_mb / file_size_mb) * 100, 1) if file_size_mb > 0 else 0,
            }
            
            logger.info(f"Pruned {name}: {result['removed']} entries removed, "
                       f"{result['reduction_percent']}% size reduction")
            return result
        else:
            return {"status": "save_failed"}
    
    def _prune_dict(self, data: Dict, policy: Dict) -> Dict:
        """Prune a dictionary (e.g., image_hashes, gap_state)."""
        max_entries = policy.get('max_entries')
        ttl_days = policy.get('ttl_days')
        
        # If we have a timestamp field, use TTL pruning
        if ttl_days and len(data) > 1000:
            cutoff = datetime.now() - timedelta(days=ttl_days)
            cutoff_timestamp = cutoff.timestamp()
            
            # Try to find timestamp fields
            pruned = {}
            for key, value in data.items():
                # Check various timestamp formats
                timestamp = None
                if isinstance(value, dict):
                    timestamp = value.get('timestamp') or value.get('created_at') or value.get('scraped_at')
                elif isinstance(value, list) and value:
                    if isinstance(value[0], dict):
                        timestamp = value[0].get('timestamp') or value[0].get('created_at')
                
                # Keep if no timestamp or timestamp is recent
                if timestamp is None or timestamp > cutoff_timestamp:
                    pruned[key] = value
            
            data = pruned
        
        # If still too large, use LRU pruning (keep most recent)
        if max_entries and len(data) > max_entries:
            # Convert to list of (key, value) pairs
            items = list(data.items())
            
            # Sort by timestamp if available, otherwise keep last N
            def get_timestamp(item):
                key, value = item
                if isinstance(value, dict):
                    return value.get('timestamp', 0) or value.get('created_at', 0) or 0
                elif isinstance(value, list) and value:
                    if isinstance(value[0], dict):
                        return value[0].get('timestamp', 0) or value[0].get('created_at', 0) or 0
                return 0
            
            # Sort by timestamp descending (newest first)
            items.sort(key=get_timestamp, reverse=True)
            
            # Keep only max_entries
            items = items[:max_entries]
            
            # Convert back to dict
            data = dict(items)
        
        return data
    
    def _prune_list(self, data: List, policy: Dict) -> List:
        """Prune a list (e.g., sold_cache as list)."""
        max_entries = policy.get('max_entries')
        ttl_days = policy.get('ttl_days')
        
        if ttl_days:
            cutoff = datetime.now() - timedelta(days=ttl_days)
            cutoff_timestamp = cutoff.timestamp()
            
            pruned = []
            for item in data:
                if isinstance(item, dict):
                    timestamp = item.get('timestamp') or item.get('created_at') or item.get('sold_at')
                    if timestamp is None or timestamp > cutoff_timestamp:
                        pruned.append(item)
            data = pruned
        
        if max_entries and len(data) > max_entries:
            # Keep most recent
            data = data[-max_entries:]
        
        return data
    
    def prune_all(self, force: bool = False) -> Dict[str, Dict]:
        """Prune all managed data files."""
        results = {}
        for name in self.policies.keys():
            results[name] = self.prune(name, force=force)
        return results
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics about all data files."""
        metrics = {
            "total_size_mb": 0,
            "files": {},
        }
        
        for name, policy in self.policies.items():
            file_path = self._get_file_path(name)
            if file_path.exists():
                size_mb = file_path.stat().st_size / (1024 * 1024)
                metrics["total_size_mb"] += size_mb
                
                # Try to count entries
                entry_count = "unknown"
                try:
                    data = self.load(name)
                    if isinstance(data, (dict, list)):
                        entry_count = len(data)
                except:
                    pass
                
                metrics["files"][name] = {
                    "size_mb": round(size_mb, 2),
                    "entries": entry_count,
                    "max_size_mb": policy.get('max_size_mb'),
                    "compress": policy.get('compress', False),
                }
        
        metrics["total_size_mb"] = round(metrics["total_size_mb"], 2)
        return metrics
    
    def _backup_corrupted_file(self, file_path: Path):
        """Backup a corrupted data file."""
        try:
            backup_path = file_path.with_suffix('.corrupted')
            shutil.copy2(file_path, backup_path)
            logger.warning(f"Backed up corrupted file to {backup_path}")
        except Exception as e:
            logger.error(f"Failed to backup corrupted file: {e}")
    
    def clear_cache(self, name: Optional[str] = None):
        """Clear in-memory cache."""
        if name:
            self._cache.pop(name, None)
            self._cache_time.pop(name, None)
        else:
            self._cache.clear()
            self._cache_time.clear()


# Convenience functions for CLI usage
def prune_data_cli(force: bool = False):
    """CLI helper to prune all data."""
    manager = DataManager()
    results = manager.prune_all(force=force)
    
    print("\n📊 Data Pruning Results\n")
    print(f"{'File':<20} {'Status':<15} {'Removed':<10} {'Size Change':<15}")
    print("-" * 65)
    
    for name, result in results.items():
        status = result.get('status', 'unknown')
        removed = result.get('removed', '-')
        size_change = '-'
        
        if 'original_size_mb' in result and 'new_size_mb' in result:
            orig = result['original_size_mb']
            new = result['new_size_mb']
            pct = result.get('reduction_percent', 0)
            size_change = f"{orig:.1f}MB → {new:.1f}MB ({pct:.0f}%)"
        
        print(f"{name:<20} {status:<15} {str(removed):<10} {size_change:<15}")
    
    # Show metrics
    metrics = manager.get_metrics()
    print(f"\nTotal data size: {metrics['total_size_mb']:.2f} MB")


def data_metrics_cli():
    """CLI helper to show data metrics."""
    manager = DataManager()
    metrics = manager.get_metrics()
    
    print("\n📈 Data File Metrics\n")
    print(f"{'File':<20} {'Size':<12} {'Entries':<12} {'Max Size':<12} {'Compressed':<12}")
    print("-" * 75)
    
    for name, info in metrics['files'].items():
        size = f"{info['size_mb']:.2f} MB"
        entries = str(info['entries'])
        max_size = f"{info['max_size_mb']} MB"
        compressed = "Yes" if info['compress'] else "No"
        print(f"{name:<20} {size:<12} {entries:<12} {max_size:<12} {compressed:<12}")
    
    print(f"\nTotal: {metrics['total_size_mb']:.2f} MB")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Data Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Prune command
    prune_parser = subparsers.add_parser("prune", help="Prune all data files")
    prune_parser.add_argument("--force", action="store_true", help="Force pruning")
    
    # Metrics command
    subparsers.add_parser("metrics", help="Show data metrics")
    
    args = parser.parse_args()
    
    if args.command == "prune":
        prune_data_cli(force=args.force)
    elif args.command == "metrics":
        data_metrics_cli()
    else:
        # Default: show metrics
        data_metrics_cli()
