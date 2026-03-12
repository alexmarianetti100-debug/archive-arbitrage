"""
Vinted scraper — Fixed implementation with cookie factory and health tracking.

As of March 2025, Vinted requires authentication tokens for API access.
This implementation uses a "Cookie Factory" approach to obtain valid tokens.

Features:
- Automatic cookie management with expiration tracking
- Health monitoring with auto-disable on repeated failures
- Reduced domain list (4 most reliable domains)
- Graceful degradation when blocked
- No external dependencies (pure httpx)

Proxy config (in .env):
  PROXY_HOST=p.webshare.io
  PROXY_PORT=10000
  PROXY_USERNAME=...
  PROXY_PASSWORD=...
"""

# Import the fixed implementation
from .vinted_fixed import VintedScraperFixed, VintedScraperWrapper

# Keep backwards compatibility
__all__ = ["VintedScraperWrapper", "VintedScraperFixed"]
