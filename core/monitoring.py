"""
Health monitoring and metrics tracking for Archive Arbitrage.

Provides real-time health checks, metrics collection, and alerting.
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from collections import defaultdict
import threading

logger = logging.getLogger("monitoring")


@dataclass
class MetricPoint:
    """A single metric data point."""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class ScraperMetrics:
    """Metrics for a single scraper."""
    scraper_name: str
    requests_total: int = 0
    requests_success: int = 0
    requests_failed: int = 0
    latency_sum: float = 0.0
    latency_count: int = 0
    last_success: Optional[str] = None
    last_failure: Optional[str] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    
    @property
    def success_rate(self) -> float:
        if self.requests_total == 0:
            return 1.0
        return self.requests_success / self.requests_total
    
    @property
    def average_latency(self) -> float:
        if self.latency_count == 0:
            return 0.0
        return self.latency_sum / self.latency_count
    
    def record_success(self, latency: float):
        self.requests_total += 1
        self.requests_success += 1
        self.latency_sum += latency
        self.latency_count += 1
        self.last_success = datetime.now().isoformat()
        self.consecutive_failures = 0
    
    def record_failure(self, error: str):
        self.requests_total += 1
        self.requests_failed += 1
        self.last_failure = datetime.now().isoformat()
        self.last_error = error
        self.consecutive_failures += 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scraper_name": self.scraper_name,
            "requests_total": self.requests_total,
            "requests_success": self.requests_success,
            "requests_failed": self.requests_failed,
            "success_rate": self.success_rate,
            "average_latency_ms": round(self.average_latency * 1000, 2),
            "last_success": self.last_success,
            "last_failure": self.last_failure,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
        }


class HealthMonitor:
    """Central health monitoring system."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.metrics: Dict[str, ScraperMetrics] = {}
        self.alerts: List[Dict[str, Any]] = []
        self.alert_handlers: List[Callable] = []
        self._alert_thresholds = {
            "consecutive_failures": 5,
            "failure_rate": 0.5,
            "latency_ms": 30000,  # 30 seconds
        }
        self._alert_cooldowns: Dict[str, float] = {}
        self._alert_cooldown_seconds = 300  # 5 minutes
        
        # Ensure metrics directory exists
        self.metrics_dir = Path("data/metrics")
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
    
    def get_metrics(self, scraper_name: str) -> ScraperMetrics:
        """Get or create metrics for a scraper."""
        if scraper_name not in self.metrics:
            self.metrics[scraper_name] = ScraperMetrics(scraper_name=scraper_name)
        return self.metrics[scraper_name]
    
    def record_request(
        self,
        scraper_name: str,
        success: bool,
        latency: float,
        error: Optional[str] = None
    ):
        """Record a scraper request."""
        metrics = self.get_metrics(scraper_name)
        
        if success:
            metrics.record_success(latency)
        else:
            metrics.record_failure(error or "Unknown error")
            self._check_alerts(scraper_name, metrics)
        
        logger.debug(f"Recorded request for {scraper_name}: success={success}, latency={latency:.2f}s")
    
    def _check_alerts(self, scraper_name: str, metrics: ScraperMetrics):
        """Check if alerts should be triggered."""
        now = time.time()
        
        # Check consecutive failures
        if metrics.consecutive_failures >= self._alert_thresholds["consecutive_failures"]:
            alert_key = f"{scraper_name}:consecutive_failures"
            if self._can_send_alert(alert_key, now):
                self._trigger_alert(
                    level="error",
                    scraper=scraper_name,
                    message=f"{scraper_name} has {metrics.consecutive_failures} consecutive failures",
                    metric="consecutive_failures",
                    value=metrics.consecutive_failures,
                )
        
        # Check failure rate
        if metrics.requests_total >= 10:
            failure_rate = 1 - metrics.success_rate
            if failure_rate >= self._alert_thresholds["failure_rate"]:
                alert_key = f"{scraper_name}:failure_rate"
                if self._can_send_alert(alert_key, now):
                    self._trigger_alert(
                        level="warning",
                        scraper=scraper_name,
                        message=f"{scraper_name} failure rate is {failure_rate:.1%}",
                        metric="failure_rate",
                        value=failure_rate,
                    )
    
    def _can_send_alert(self, alert_key: str, now: float) -> bool:
        """Check if alert can be sent (respect cooldown)."""
        last_sent = self._alert_cooldowns.get(alert_key, 0)
        if now - last_sent >= self._alert_cooldown_seconds:
            self._alert_cooldowns[alert_key] = now
            return True
        return False
    
    def _trigger_alert(self, level: str, scraper: str, message: str, metric: str, value: Any):
        """Trigger an alert."""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "scraper": scraper,
            "message": message,
            "metric": metric,
            "value": value,
        }
        self.alerts.append(alert)
        
        # Log alert
        log_method = getattr(logger, level)
        log_method(f"ALERT: {message}")
        
        # Call registered handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
    
    def add_alert_handler(self, handler: Callable):
        """Add an alert handler callback."""
        self.alert_handlers.append(handler)
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status."""
        if not self.metrics:
            return {
                "status": "unknown",
                "healthy_count": 0,
                "total_count": 0,
                "scrapers": {},
                "alerts": [],
            }
        
        scraper_statuses = {}
        healthy_count = 0
        
        for name, metrics in self.metrics.items():
            is_healthy = (
                metrics.consecutive_failures < self._alert_thresholds["consecutive_failures"]
                and metrics.success_rate >= 0.8
            )
            scraper_statuses[name] = {
                "healthy": is_healthy,
                **metrics.to_dict(),
            }
            if is_healthy:
                healthy_count += 1
        
        overall_status = "healthy" if healthy_count == len(self.metrics) else "degraded"
        if healthy_count == 0 and self.metrics:
            overall_status = "unhealthy"
        
        return {
            "status": overall_status,
            "healthy_count": healthy_count,
            "total_count": len(self.metrics),
            "scrapers": scraper_statuses,
            "alerts": self.alerts[-10:],  # Last 10 alerts
        }
    
    def save_metrics(self):
        """Save metrics to disk."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics_file = self.metrics_dir / f"metrics_{timestamp}.json"
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "scrapers": {name: m.to_dict() for name, m in self.metrics.items()},
        }
        
        with open(metrics_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.debug(f"Saved metrics to {metrics_file}")
        
        # Clean up old metrics files (keep last 24 hours)
        self._cleanup_old_metrics()
    
    def _cleanup_old_metrics(self):
        """Remove metrics files older than 24 hours."""
        cutoff = datetime.now() - timedelta(hours=24)
        
        for file in self.metrics_dir.glob("metrics_*.json"):
            try:
                # Extract timestamp from filename
                timestamp_str = file.stem.split('_')[1] + '_' + file.stem.split('_')[2]
                file_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                
                if file_time < cutoff:
                    file.unlink()
                    logger.debug(f"Removed old metrics file: {file}")
            except Exception:
                pass
    
    def print_dashboard(self):
        """Print a text-based health dashboard."""
        status = self.get_health_status()
        
        print("\n" + "=" * 70)
        print("📊 SCRAPER HEALTH DASHBOARD")
        print("=" * 70)
        print(f"Overall Status: {status['status'].upper()}")
        print(f"Healthy: {status['healthy_count']}/{status['total_count']} scrapers")
        print("-" * 70)
        
        for name, scraper in status['scrapers'].items():
            health_icon = "✅" if scraper['healthy'] else "❌"
            print(f"\n{health_icon} {name.upper()}")
            print(f"   Success Rate: {scraper['success_rate']:.1%}")
            print(f"   Requests: {scraper['requests_total']} (✓{scraper['requests_success']} ✗{scraper['requests_failed']})")
            print(f"   Avg Latency: {scraper['average_latency_ms']:.0f}ms")
            if scraper['last_error']:
                print(f"   Last Error: {scraper['last_error'][:50]}...")
        
        if status['alerts']:
            print("\n" + "-" * 70)
            print("🚨 RECENT ALERTS")
            print("-" * 70)
            for alert in status['alerts'][-5:]:
                level_icon = "🔴" if alert['level'] == 'error' else "🟡"
                print(f"{level_icon} [{alert['timestamp'][:19]}] {alert['message']}")
        
        print("\n" + "=" * 70)


# Global monitor instance
monitor = HealthMonitor()


def record_scraper_request(scraper_name: str, success: bool, latency: float, error: Optional[str] = None):
    """Convenience function to record a scraper request."""
    monitor.record_request(scraper_name, success, latency, error)


def get_health_status() -> Dict[str, Any]:
    """Convenience function to get health status."""
    return monitor.get_health_status()


def print_dashboard():
    """Convenience function to print dashboard."""
    monitor.print_dashboard()
