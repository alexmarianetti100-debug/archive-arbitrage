#!/usr/bin/env python3
"""
Status dashboard for Archive Arbitrage.

Real-time monitoring dashboard with auto-refresh capability.
"""

import sys
import time
import os
from pathlib import Path
from datetime import datetime

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from core.monitoring import get_health_status


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def format_duration(seconds):
    """Format seconds to human readable."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.0f}m"
    else:
        return f"{seconds/3600:.1f}h"


def get_system_stats():
    """Get system statistics."""
    import shutil
    import psutil
    
    # Disk usage
    total, used, free = shutil.disk_usage(".")
    disk_percent = (used / total) * 100
    
    # Memory usage
    memory = psutil.virtual_memory()
    
    # CPU usage
    cpu_percent = psutil.cpu_percent(interval=0.1)
    
    return {
        "disk_percent": disk_percent,
        "disk_free_gb": free // (2**30),
        "memory_percent": memory.percent,
        "memory_free_gb": memory.available // (2**30),
        "cpu_percent": cpu_percent,
    }


def get_data_stats():
    """Get data directory statistics."""
    data_dir = Path("data")
    
    if not data_dir.exists():
        return {"exists": False}
    
    stats = {"exists": True, "files": {}}
    
    for pattern in ["*.db", "*.json", "metrics/*.json"]:
        files = list(data_dir.glob(pattern))
        total_size = sum(f.stat().st_size for f in files)
        stats["files"][pattern] = {
            "count": len(files),
            "size_mb": total_size / (1024 * 1024),
        }
    
    return stats


def print_header():
    """Print dashboard header."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 80)
    print(f"📊 ARCHIVE ARBITRAGE STATUS DASHBOARD - {now}")
    print("=" * 80)


def print_system_status():
    """Print system resource status."""
    try:
        stats = get_system_stats()
        
        print("\n💻 SYSTEM RESOURCES")
        print("-" * 80)
        
        disk_color = "🟢" if stats["disk_percent"] < 70 else "🟡" if stats["disk_percent"] < 85 else "🔴"
        mem_color = "🟢" if stats["memory_percent"] < 70 else "🟡" if stats["memory_percent"] < 85 else "🔴"
        cpu_color = "🟢" if stats["cpu_percent"] < 50 else "🟡" if stats["cpu_percent"] < 80 else "🔴"
        
        print(f"   {disk_color} Disk: {stats['disk_percent']:.1f}% used ({stats['disk_free_gb']} GB free)")
        print(f"   {mem_color} Memory: {stats['memory_percent']:.1f}% used ({stats['memory_free_gb']} GB free)")
        print(f"   {cpu_color} CPU: {stats['cpu_percent']:.1f}%")
        
    except Exception as e:
        print(f"\n💻 SYSTEM RESOURCES")
        print("-" * 80)
        print(f"   ⚠️  Could not get system stats: {e}")


def print_data_status():
    """Print data directory status."""
    stats = get_data_stats()
    
    print("\n💾 DATA STORAGE")
    print("-" * 80)
    
    if not stats["exists"]:
        print("   ⚠️  Data directory not found")
        return
    
    for pattern, info in stats["files"].items():
        print(f"   📁 {pattern}: {info['count']} files ({info['size_mb']:.1f} MB)")


def print_scraper_status():
    """Print scraper health status."""
    health = get_health_status()
    
    print("\n🔍 SCRAPER HEALTH")
    print("-" * 80)
    
    if not health.get("scrapers"):
        print("   ℹ️  No scraper data available")
        return
    
    for name, scraper in health["scrapers"].items():
        status_icon = "✅" if scraper["healthy"] else "❌"
        success_rate = scraper["success_rate"] * 100
        
        print(f"   {status_icon} {name.upper()}")
        print(f"      Success Rate: {success_rate:.1f}%")
        print(f"      Requests: {scraper['requests_total']} (✓{scraper['requests_success']} ✗{scraper['requests_failed']})")
        print(f"      Avg Latency: {scraper['average_latency_ms']:.0f}ms")
        
        if scraper["last_error"]:
            print(f"      Last Error: {scraper['last_error'][:40]}...")


def print_alerts():
    """Print recent alerts."""
    health = get_health_status()
    alerts = health.get("alerts", [])
    
    print("\n🚨 RECENT ALERTS")
    print("-" * 80)
    
    if not alerts:
        print("   ✅ No recent alerts")
        return
    
    for alert in alerts[-5:]:  # Show last 5
        level_icon = "🔴" if alert["level"] == "error" else "🟡"
        timestamp = alert["timestamp"][:19]  # Trim to seconds
        print(f"   {level_icon} [{timestamp}] {alert['message']}")


def print_footer():
    """Print dashboard footer."""
    print("\n" + "=" * 80)
    print("Press Ctrl+C to exit | Run with --watch for auto-refresh (30s)")
    print("=" * 80)


def main():
    """Run status dashboard."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Archive Arbitrage Status Dashboard")
    parser.add_argument("--watch", "-w", action="store_true", help="Auto-refresh every 30 seconds")
    parser.add_argument("--interval", "-i", type=int, default=30, help="Refresh interval in seconds")
    args = parser.parse_args()
    
    try:
        while True:
            if args.watch:
                clear_screen()
            
            print_header()
            print_system_status()
            print_data_status()
            print_scraper_status()
            print_alerts()
            print_footer()
            
            if not args.watch:
                break
            
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\n\n👋 Dashboard stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
