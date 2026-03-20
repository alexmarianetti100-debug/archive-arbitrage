"""
Unit tests for core/exceptions.py
"""

import pytest
from core.exceptions import (
    ScraperError,
    NetworkError,
    TimeoutError,
    RateLimitError,
    ParseError,
    ErrorCategory,
)


class TestScraperError:
    """Test base ScraperError class."""
    
    def test_basic_error(self):
        """Test basic error creation."""
        error = ScraperError("Test error")
        assert error.message == "Test error"
        assert error.error_code == "SCRAPER_001"
        assert error.category == ErrorCategory.UNKNOWN
        assert error.retryable is False
    
    def test_error_with_source(self):
        """Test error with source."""
        error = ScraperError("Test error", source="ebay")
        assert error.source == "ebay"
    
    def test_error_with_details(self):
        """Test error with details."""
        details = {"url": "https://ebay.com", "status": 500}
        error = ScraperError("Test error", details=details)
        assert error.details == details
    
    def test_error_to_dict(self):
        """Test error serialization to dict."""
        error = ScraperError(
            message="Test error",
            source="ebay",
            details={"url": "https://ebay.com"},
        )
        
        data = error.to_dict()
        assert data["error_code"] == "SCRAPER_001"
        assert data["category"] == "unknown"
        assert data["message"] == "Test error"
        assert data["source"] == "ebay"
        assert data["details"]["url"] == "https://ebay.com"
        assert data["retryable"] is False
        assert "timestamp" in data
    
    def test_error_string_representation(self):
        """Test error string representation."""
        error = NetworkError("Connection failed")
        assert "NET_001" in str(error)
        assert "network" in str(error)
        assert "Connection failed" in str(error)


class TestNetworkError:
    """Test NetworkError class."""
    
    def test_network_error_properties(self):
        """Test network error has correct properties."""
        error = NetworkError("Connection refused")
        assert error.error_code == "NET_001"
        assert error.category == ErrorCategory.NETWORK
        assert error.retryable is True


class TestTimeoutError:
    """Test TimeoutError class."""
    
    def test_timeout_error_properties(self):
        """Test timeout error has correct properties."""
        error = TimeoutError("Request timed out")
        assert error.error_code == "NET_002"
        assert error.category == ErrorCategory.TIMEOUT
        assert error.retryable is True


class TestRateLimitError:
    """Test RateLimitError class."""
    
    def test_rate_limit_error_properties(self):
        """Test rate limit error has correct properties."""
        error = RateLimitError("Rate limited")
        assert error.error_code == "NET_003"
        assert error.category == ErrorCategory.RATE_LIMIT
        assert error.retryable is True
    
    def test_rate_limit_with_retry_after(self):
        """Test rate limit with retry_after."""
        error = RateLimitError("Rate limited", retry_after=60)
        assert error.retry_after == 60


class TestParseError:
    """Test ParseError class."""
    
    def test_parse_error_properties(self):
        """Test parse error has correct properties."""
        error = ParseError("Failed to parse HTML")
        assert error.error_code == "PARSE_001"
        assert error.category == ErrorCategory.PARSE
        assert error.retryable is False
