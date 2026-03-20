"""
Logging configuration for Archive Arbitrage.

Provides structured logging with rotation and multiple output formats.
"""

import json
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, "scraper"):
            log_data["scraper"] = record.scraper
        if hasattr(record, "source"):
            log_data["source"] = record.source
        if hasattr(record, "error_code"):
            log_data["error_code"] = record.error_code
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, default=str)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output."""
    
    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
        "RESET": "\033[0m",
    }
    
    def format(self, record: logging.LogRecord) -> str:
        # Add color to levelname
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        
        result = super().format(record)
        record.levelname = levelname  # Restore original
        return result


def setup_logging(
    log_dir: str = "logs",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    json_format: bool = True,
) -> logging.Logger:
    """
    Set up logging with rotation.
    
    Args:
        log_dir: Directory for log files
        console_level: Logging level for console output
        file_level: Logging level for file output
        json_format: Whether to use JSON formatting for files
    
    Returns:
        Root logger
    """
    # Create logs directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    console_handler.setFormatter(ColoredFormatter(console_format))
    root_logger.addHandler(console_handler)
    
    # Main log file (rotating)
    main_handler = logging.handlers.RotatingFileHandler(
        log_path / "archive_arbitrage.log",
        maxBytes=10_000_000,  # 10 MB
        backupCount=7,
        encoding="utf-8",
    )
    main_handler.setLevel(file_level)
    if json_format:
        main_handler.setFormatter(JSONFormatter())
    else:
        main_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
    root_logger.addHandler(main_handler)
    
    # Error log file (rotating, errors only)
    error_handler = logging.handlers.RotatingFileHandler(
        log_path / "errors.log",
        maxBytes=5_000_000,  # 5 MB
        backupCount=7,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    if json_format:
        error_handler.setFormatter(JSONFormatter())
    else:
        error_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
    root_logger.addHandler(error_handler)
    
    # Scraper-specific log file
    scraper_handler = logging.handlers.RotatingFileHandler(
        log_path / "scrapers.log",
        maxBytes=10_000_000,  # 10 MB
        backupCount=7,
        encoding="utf-8",
    )
    scraper_handler.setLevel(file_level)
    if json_format:
        scraper_handler.setFormatter(JSONFormatter())
    else:
        scraper_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
    
    # Only add to scraper loggers
    scraper_logger = logging.getLogger("scraper")
    scraper_logger.addHandler(scraper_handler)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(name)


def log_scraper_request(
    logger: logging.Logger,
    scraper_name: str,
    success: bool,
    duration_ms: float,
    items_count: int = 0,
    error: Optional[str] = None,
):
    """Log a scraper request with structured data."""
    extra = {
        "scraper": scraper_name,
        "duration_ms": round(duration_ms, 2),
        "items_count": items_count,
    }
    
    if success:
        logger.info(
            f"{scraper_name}: Success in {duration_ms:.0f}ms, {items_count} items",
            extra=extra
        )
    else:
        extra["error"] = error
        logger.error(
            f"{scraper_name}: Failed after {duration_ms:.0f}ms - {error}",
            extra=extra
        )


# Convenience function for setting up logging on import
def init_logging():
    """Initialize logging with default configuration."""
    return setup_logging()
