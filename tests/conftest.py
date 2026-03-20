"""
Test fixtures for Archive Arbitrage.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock

# Add project to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_ebay_html():
    """Sample eBay search results HTML."""
    return """
    <html>
    <body>
        <ul>
            <li class="s-item">Ad item</li>
            <li class="s-item">
                <h3 class="s-item__title">Nike Air Max 90</h3>
                <span class="s-item__price">$120.00</span>
                <a href="https://www.ebay.com/itm/123456789">Link</a>
                <img src="https://i.ebayimg.com/00/s/MTAwMFgxMDAw/z/abc123/s-l500.jpg" />
            </li>
            <li class="s-item">
                <h3 class="s-item__title">Nike Dunk Low</h3>
                <span class="s-item__price">$150.00</span>
                <a href="https://www.ebay.com/itm/987654321">Link</a>
            </li>
        </ul>
    </body>
    </html>
    """


@pytest.fixture
def sample_grailed_response():
    """Sample Grailed API response."""
    return {
        "hits": [
            {
                "id": 12345,
                "title": "Rick Owens Jacket",
                "price": 450,
                "sold_price": 400,
                "designers": [{"name": "Rick Owens"}],
                "size": "M",
                "cover_photo": {"url": "https://example.com/image.jpg"},
                "created_at": "2024-01-15T10:00:00Z",
            },
            {
                "id": 67890,
                "title": "Vintage Nike Hoodie",
                "price": 120,
                "designers": [{"name": "Nike"}],
                "size": "L",
            },
        ]
    }


@pytest.fixture
def sample_poshmark_html():
    """Sample Poshmark search results HTML."""
    return """
    <html>
    <body>
        <div class="card">
            <a data-et-prop-listing_id="12345" href="/listing/Nike-Shoes-12345">
                <div class="tile__title">Nike Air Force 1</div>
                <span class="fw--bold">$85</span>
                <div class="tile__details__pipe__size">Size: 10</div>
                <div class="tile__details__pipe__brand">Nike</div>
            </a>
        </div>
        <div class="card">
            <a data-et-prop-listing_id="67890" href="/listing/Adidas-Shoes-67890">
                <div class="tile__title">Adidas Ultraboost</div>
                <span class="fw--bold">$120</span>
            </a>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def mock_httpx_response():
    """Create a mock httpx response."""
    def _create(status_code=200, json_data=None, text="", headers=None):
        mock = Mock()
        mock.status_code = status_code
        mock.json = Mock(return_value=json_data or {})
        mock.text = text
        mock.headers = headers or {}
        return mock
    return _create


@pytest.fixture
def mock_async_client():
    """Create a mock async HTTP client."""
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def sample_seller_data():
    """Sample seller blocklist data."""
    return {
        "blocked_sellers": {
            "bad_seller_123": {
                "reason": "selling fakes",
                "evidence": "confirmed counterfeit",
                "blocked_at": "2024-01-01T00:00:00Z",
                "failure_count": 0,
            }
        },
        "seller_failures": {
            "suspicious_seller": 2,
        },
    }


@pytest.fixture
def sample_cache_data():
    """Sample pricing cache data."""
    from datetime import datetime, timedelta
    
    now = datetime.now()
    return {
        "nike_air_max": {
            "price": 120.0,
            "timestamp": (now - timedelta(hours=1)).isoformat(),
            "source": "ebay",
            "query": "nike air max",
            "hit_count": 5,
        },
        "adidas_ultraboost": {
            "price": 150.0,
            "timestamp": (now - timedelta(hours=3)).isoformat(),
            "source": "grailed",
            "query": "adidas ultraboost",
            "hit_count": 2,
        },
    }
