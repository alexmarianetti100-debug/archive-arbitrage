"""
Unit tests for core/monitoring.py
"""

import pytest
import time
from datetime import datetime
from core.monitoring import (
    ScraperMetrics,
    HealthMonitor,
    monitor,
    record_scraper_request,
    get_health_status,
)


class TestScraperMetrics:
    """Test ScraperMetrics class."""
    
    def test_initial_state(self):
        """Test initial metrics state."""
        metrics = ScraperMetrics(scraper_name="test")
        assert metrics.scraper_name == "test"
        assert metrics.requests_total == 0
        assert metrics.success_rate == 1.0  # Default when no requests
        assert metrics.average_latency == 0.0
    
    def test_record_success(self):
        """Test recording successful request."""
        metrics = ScraperMetrics(scraper_name="test")
        metrics.record_success(latency=0.5)
        
        assert metrics.requests_total == 1
        assert metrics.requests_success == 1
        assert metrics.requests_failed == 0
        assert metrics.success_rate == 1.0
        assert metrics.average_latency == 0.5
        assert metrics.last_success is not None
        assert metrics.consecutive_failures == 0
    
    def test_record_failure(self):
        """Test recording failed request."""
        metrics = ScraperMetrics(scraper_name="test")
        metrics.record_failure(error="Timeout")
        
        assert metrics.requests_total == 1
        assert metrics.requests_success == 0
        assert metrics.requests_failed == 1
        assert metrics.success_rate == 0.0
        assert metrics.last_error == "Timeout"
        assert metrics.consecutive_failures == 1
    
    def test_consecutive_failures(self):
        """Test consecutive failure tracking."""
        metrics = ScraperMetrics(scraper_name="test")
        
        metrics.record_failure(error="Error 1")
        assert metrics.consecutive_failures == 1
        
        metrics.record_failure(error="Error 2")
        assert metrics.consecutive_failures == 2
        
        # Success resets counter
        metrics.record_success(latency=0.5)
        assert metrics.consecutive_failures == 0
    
    def test_average_latency_calculation(self):
        """Test average latency calculation."""
        metrics = ScraperMetrics(scraper_name="test")
        
        metrics.record_success(latency=0.5)
        metrics.record_success(latency=1.0)
        metrics.record_success(latency=1.5)
        
        assert metrics.average_latency == 1.0
    
    def test_to_dict(self):
        """Test metrics serialization."""
        metrics = ScraperMetrics(scraper_name="test")
        metrics.record_success(latency=0.5)
        
        data = metrics.to_dict()
        assert data["scraper_name"] == "test"
        assert data["requests_total"] == 1
        assert data["success_rate"] == 1.0
        assert data["average_latency_ms"] == 500.0


class TestHealthMonitor:
    """Test HealthMonitor class."""
    
    def test_singleton(self):
        """Test monitor is singleton."""
        monitor1 = HealthMonitor()
        monitor2 = HealthMonitor()
        assert monitor1 is monitor2
    
    def test_get_metrics_creates_new(self):
        """Test get_metrics creates new metrics if not exists."""
        # Reset singleton for test
        HealthMonitor._instance = None
        monitor = HealthMonitor()
        
        metrics = monitor.get_metrics("new_scraper")
        assert metrics.scraper_name == "new_scraper"
        assert "new_scraper" in monitor.metrics
    
    def test_record_request_success(self):
        """Test recording successful request."""
        HealthMonitor._instance = None
        monitor = HealthMonitor()
        
        monitor.record_request("test", success=True, latency=0.5)
        
        metrics = monitor.get_metrics("test")
        assert metrics.requests_success == 1
        assert metrics.success_rate == 1.0
    
    def test_record_request_failure(self):
        """Test recording failed request."""
        HealthMonitor._instance = None
        monitor = HealthMonitor()
        
        monitor.record_request("test", success=False, latency=2.0, error="Timeout")
        
        metrics = monitor.get_metrics("test")
        assert metrics.requests_failed == 1
        assert metrics.success_rate == 0.0
        assert metrics.last_error == "Timeout"
    
    def test_get_health_status_empty(self):
        """Test health status with no metrics."""
        HealthMonitor._instance = None
        monitor = HealthMonitor()
        
        status = monitor.get_health_status()
        assert status["status"] == "unknown"
    
    def test_get_health_status_healthy(self):
        """Test health status when healthy."""
        HealthMonitor._instance = None
        monitor = HealthMonitor()
        
        monitor.record_request("test", success=True, latency=0.5)
        monitor.record_request("test", success=True, latency=0.6)
        
        status = monitor.get_health_status()
        assert status["status"] == "healthy"
        assert status["healthy_count"] == 1
    
    def test_get_health_status_degraded(self):
        """Test health status when degraded."""
        HealthMonitor._instance = None
        monitor = HealthMonitor()
        
        # Create some failures
        for _ in range(5):
            monitor.record_request("test", success=False, latency=0.5, error="Error")
        
        status = monitor.get_health_status()
        assert status["status"] == "unhealthy"
        assert status["scrapers"]["test"]["healthy"] is False


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_record_scraper_request(self):
        """Test record_scraper_request function."""
        HealthMonitor._instance = None
        
        record_scraper_request("test", True, 0.5)
        
        status = get_health_status()
        assert status["scrapers"]["test"]["requests_total"] == 1
    
    def test_get_health_status(self):
        """Test get_health_status function."""
        HealthMonitor._instance = None
        
        record_scraper_request("test1", True, 0.5)
        record_scraper_request("test2", True, 0.6)
        
        status = get_health_status()
        assert "scrapers" in status
        assert len(status["scrapers"]) >= 2  # May have more from other tests
