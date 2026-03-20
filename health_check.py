#!/usr/bin/env python3
"""
Health check script for Archive Arbitrage.

Performs comprehensive health checks and reports status.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from core.monitoring import monitor, get_health_status, print_dashboard


def check_disk_space():
    """Check available disk space."""
    import shutil
    
    total, used, free = shutil.disk_usage(".")
    percent_used = (used / total) * 100
    
    status = "✅" if percent_used < 80 else "⚠️ " if percent_used < 90 else "❌"
    
    print(f"\n{status} Disk Space")
    print(f"   Used: {used // (2**30)} GB / {total // (2**30)} GB ({percent_used:.1f}%)")
    
    return percent_used < 90


def check_database():
    """Check database accessibility."""
    data_dir = Path("data")
    
    if not data_dir.exists():
        print("\n⚠️  Data directory not found")
        return False
    
    db_files = list(data_dir.glob("*.db"))
    
    if not db_files:
        print("\n⚠️  No database files found")
        return False
    
    print(f"\n✅ Database Files ({len(db_files)} found)")
    for db_file in db_files:
        size = db_file.stat().st_size
        print(f"   {db_file.name}: {size // 1024} KB")
    
    return True


def check_logs():
    """Check log directory."""
    log_dir = Path("logs")
    
    if not log_dir.exists():
        print("\n⚠️  Log directory not found")
        return False
    
    log_files = list(log_dir.glob("*.log"))
    
    print(f"\n✅ Log Files ({len(log_files)} found)")
    for log_file in log_files[:5]:  # Show first 5
        size = log_file.stat().st_size
        print(f"   {log_file.name}: {size // 1024} KB")
    
    return True


def check_environment():
    """Check environment variables."""
    required = ["DISCORD_WEBHOOK_URL"]
    optional = ["TELEGRAM_BOT_TOKEN", "PROXY_HOST"]
    
    print("\n📋 Environment Variables")
    
    all_good = True
    
    for var in required:
        value = os.getenv(var)
        status = "✅" if value else "❌"
        print(f"   {status} {var}: {'Set' if value else 'MISSING'}")
        if not value:
            all_good = False
    
    for var in optional:
        value = os.getenv(var)
        status = "✅" if value else "⚠️ "
        print(f"   {status} {var}: {'Set' if value else 'Not set'}")
    
    return all_good


def check_scrapers():
    """Check scraper health."""
    print("\n🔍 Checking Scraper Health...")
    
    try:
        from scrapers.ebay import EbayScraper
        from scrapers.poshmark import PoshmarkScraper
        from scrapers.grailed import GrailedScraper
        from scrapers.vinted_fixed import VintedScraperFixed
        
        scrapers = [
            ("eBay", EbayScraper),
            ("Poshmark", PoshmarkScraper),
            ("Grailed", GrailedScraper),
            ("Vinted", VintedScraperFixed),
        ]
        
        all_healthy = True
        
        for name, scraper_class in scrapers:
            try:
                if hasattr(scraper_class, 'get_health_status'):
                    if name == 'Vinted':
                        health = scraper_class().get_health_status()
                    else:
                        health = scraper_class.get_health_status()
                    
                    is_healthy = health.get('healthy', True)
                    status = "✅" if is_healthy else "❌"
                    print(f"   {status} {name}: {'Healthy' if is_healthy else 'Unhealthy'}")
                    
                    if not is_healthy:
                        all_healthy = False
                else:
                    print(f"   ⚠️  {name}: No health check")
            except Exception as e:
                print(f"   ❌ {name}: Error - {e}")
                all_healthy = False
        
        return all_healthy
        
    except Exception as e:
        print(f"   ❌ Error checking scrapers: {e}")
        return False


def main():
    """Run all health checks."""
    print("=" * 70)
    print("🔍 ARCHIVE ARBITRAGE HEALTH CHECK")
    print("=" * 70)
    
    checks = []
    
    # Run checks
    checks.append(("Environment", check_environment()))
    checks.append(("Disk Space", check_disk_space()))
    checks.append(("Database", check_database()))
    checks.append(("Logs", check_logs()))
    checks.append(("Scrapers", check_scrapers()))
    
    # Print dashboard
    print("\n")
    print_dashboard()
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅" if result else "❌"
        print(f"   {status} {name}")
    
    print(f"\n   Passed: {passed}/{total}")
    
    if passed == total:
        print("\n   🎉 ALL CHECKS PASSED - System Healthy!")
        return 0
    else:
        print(f"\n   ⚠️  {total - passed} check(s) failed - Review required")
        return 1


if __name__ == "__main__":
    sys.exit(main())
