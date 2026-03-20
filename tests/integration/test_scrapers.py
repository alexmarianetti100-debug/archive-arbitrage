"""
Integration tests for scrapers with mocked HTTP responses.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from bs4 import BeautifulSoup

from scrapers.ebay import EbayScraper
from scrapers.poshmark import PoshmarkScraper


class TestEbayScraper:
    """Integration tests for eBay scraper."""
    
    @pytest.mark.asyncio
    async def test_search_success(self, sample_ebay_html):
        """Test successful eBay search."""
        scraper = EbayScraper()
        
        # Mock the _fetch method
        scraper._fetch = AsyncMock(return_value=BeautifulSoup(sample_ebay_html, "html.parser"))
        
        items = await scraper.search("nike", max_results=5)
        
        assert len(items) == 2
        assert items[0].title == "Nike Air Max 90"
        assert items[0].price == 120.0
        assert items[0].source == "ebay"
    
    @pytest.mark.asyncio
    async def test_search_no_results(self):
        """Test eBay search with no results."""
        scraper = EbayScraper()
        
        # Return empty HTML
        scraper._fetch = AsyncMock(return_value=BeautifulSoup("<html></html>", "html.parser"))
        
        items = await scraper.search("nike", max_results=5)
        
        assert len(items) == 0
    
    @pytest.mark.asyncio
    async def test_search_fetch_failure(self):
        """Test eBay search when fetch fails."""
        scraper = EbayScraper()
        
        # Return None (fetch failure)
        scraper._fetch = AsyncMock(return_value=None)
        
        items = await scraper.search("nike", max_results=5)
        
        assert len(items) == 0
    
    @pytest.mark.asyncio
    async def test_search_skips_auctions(self):
        """Test that auction items are skipped."""
        html = """
        <html>
        <body>
            <ul>
                <li class="s-item">Ad</li>
                <li class="s-item">
                    <h3>Nike Shoes</h3>
                    <span class="s-item__price">$100</span>
                    <span>place bid</span>
                    <a href="/itm/123">Link</a>
                </li>
                <li class="s-item">
                    <h3>Adidas Shoes</h3>
                    <span class="s-item__price">$150</span>
                    <a href="/itm/456">Link</a>
                </li>
            </ul>
        </body>
        </html>
        """
        
        scraper = EbayScraper()
        scraper._fetch = AsyncMock(return_value=BeautifulSoup(html, "html.parser"))
        
        items = await scraper.search("shoes", max_results=5)
        
        # Should only have the Adidas item (Nike was auction)
        assert len(items) == 1
        assert items[0].title == "Adidas Shoes"


class TestPoshmarkScraper:
    """Integration tests for Poshmark scraper."""
    
    @pytest.mark.asyncio
    async def test_search_success(self, sample_poshmark_html):
        """Test successful Poshmark search."""
        scraper = PoshmarkScraper()
        
        # Mock the fetch method
        with patch.object(scraper, 'fetch', new_callable=AsyncMock) as mock_fetch:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = sample_poshmark_html
            mock_fetch.return_value = mock_response
            
            items = await scraper.search("nike", max_results=5)
            
            assert len(items) == 2
            assert items[0].title == "Nike Air Force 1"
            assert items[0].price == 85.0
            assert items[0].brand == "Nike"
            assert items[0].size == "10"
    
    @pytest.mark.asyncio
    async def test_search_no_results(self):
        """Test Poshmark search with no results."""
        scraper = PoshmarkScraper()
        
        with patch.object(scraper, 'fetch', new_callable=AsyncMock) as mock_fetch:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "<html><body>No results</body></html>"
            mock_fetch.return_value = mock_response
            
            items = await scraper.search("nike", max_results=5)
            
            assert len(items) == 0
    
    @pytest.mark.asyncio
    async def test_search_http_error(self):
        """Test Poshmark search with HTTP error."""
        scraper = PoshmarkScraper()
        
        with patch.object(scraper, 'fetch', new_callable=AsyncMock) as mock_fetch:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_fetch.return_value = mock_response
            
            items = await scraper.search("nike", max_results=5)
            
            assert len(items) == 0


class TestScraperHealthIntegration:
    """Test scraper health monitoring integration."""
    
    @pytest.mark.asyncio
    async def test_ebay_health_tracking(self, sample_ebay_html):
        """Test that eBay scraper tracks health."""
        from core.monitoring import monitor
        
        # Reset monitor
        monitor.metrics = {}
        
        scraper = EbayScraper()
        scraper._fetch = AsyncMock(return_value=BeautifulSoup(sample_ebay_html, "html.parser"))
        
        await scraper.search("nike")
        
        # Check health was recorded
        health = EbayScraper.get_health_status()
        assert health["success_count"] >= 1
        assert health["healthy"] is True
    
    @pytest.mark.asyncio
    async def test_poshmark_health_tracking(self, sample_poshmark_html):
        """Test that Poshmark scraper tracks health."""
        scraper = PoshmarkScraper()
        
        with patch.object(scraper, 'fetch', new_callable=AsyncMock) as mock_fetch:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = sample_poshmark_html
            mock_fetch.return_value = mock_response
            
            await scraper.search("nike")
            
            health = PoshmarkScraper.get_health_status()
            assert health["success_count"] >= 1 or health["failure_count"] >= 1
