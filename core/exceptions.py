"""
Custom exception classes for Archive Arbitrage scrapers.

Provides structured error handling with error codes and categories.
"""

from enum import Enum
from typing import Optional, Dict, Any


class ErrorCategory(Enum):
    """Categories of errors for grouping and handling."""
    NETWORK = "network"
    PARSE = "parse"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    PROXY = "proxy"
    UNKNOWN = "unknown"


class ScraperError(Exception):
    """Base exception for all scraper errors."""
    
    error_code = "SCRAPER_001"
    category = ErrorCategory.UNKNOWN
    retryable = False
    
    def __init__(
        self,
        message: str,
        source: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.source = source
        self.details = details or {}
        self.original_error = original_error
        self.timestamp = __import__('datetime').datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging."""
        return {
            "error_code": self.error_code,
            "category": self.category.value,
            "message": self.message,
            "source": self.source,
            "details": self.details,
            "retryable": self.retryable,
            "timestamp": self.timestamp,
            "original_error": str(self.original_error) if self.original_error else None,
        }
    
    def __str__(self) -> str:
        return f"[{self.error_code}] {self.category.value}: {self.message}"


class NetworkError(ScraperError):
    """Network-related errors (DNS, connection, SSL)."""
    
    error_code = "NET_001"
    category = ErrorCategory.NETWORK
    retryable = True


class TimeoutError(ScraperError):
    """Request timeout errors."""
    
    error_code = "NET_002"
    category = ErrorCategory.TIMEOUT
    retryable = True


class RateLimitError(ScraperError):
    """Rate limit exceeded errors."""
    
    error_code = "NET_003"
    category = ErrorCategory.RATE_LIMIT
    retryable = True
    
    def __init__(self, *args, retry_after: Optional[int] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.retry_after = retry_after


class ProxyError(ScraperError):
    """Proxy-related errors."""
    
    error_code = "NET_004"
    category = ErrorCategory.PROXY
    retryable = True


class ParseError(ScraperError):
    """HTML/JSON parsing errors."""
    
    error_code = "PARSE_001"
    category = ErrorCategory.PARSE
    retryable = False


class SelectorError(ScraperError):
    """CSS/XPath selector errors (page structure changed)."""
    
    error_code = "PARSE_002"
    category = ErrorCategory.PARSE
    retryable = False


class AuthError(ScraperError):
    """Authentication/authorization errors."""
    
    error_code = "AUTH_001"
    category = ErrorCategory.AUTH
    retryable = False


class BotDetectionError(ScraperError):
    """Detected as bot/blocked."""
    
    error_code = "AUTH_002"
    category = ErrorCategory.AUTH
    retryable = True


class ValidationError(ScraperError):
    """Data validation errors."""
    
    error_code = "VAL_001"
    category = ErrorCategory.UNKNOWN
    retryable = False
