"""
Reverse Image Search - Identify exact products from images.

Integrates with external reverse image search APIs to:
1. Find the same product across different platforms
2. Extract exact product names from result titles
3. Cross-reference with sold comps for pricing

Supports multiple backends:
- Google Lens (via custom scraping or unofficial API)
- TinEye (commercial API)
- SerpAPI (Google Lens via API)
"""

import os
import re
import json
import asyncio
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from urllib.parse import quote, urlparse

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from scrapers.image_fingerprinter import ImageFingerprinter, ImageFingerprint


@dataclass
class ReverseImageResult:
    """Result from reverse image search."""
    title: str
    url: str
    source: str                      # 'google', 'tineye', 'grailed', etc.
    image_url: Optional[str] = None
    price: Optional[float] = None    # Extracted if available
    confidence: float = 0.0          # 0.0-1.0 match confidence
    metadata: Dict = field(default_factory=dict)


class ReverseImageSearcher:
    """
    Reverse image search client.
    
    Usage:
        async with ReverseImageSearcher() as searcher:
            results = await searcher.search(image_url)
            for result in results:
                print(f"Found: {result.title} on {result.source}")
    """
    
    def __init__(self, 
                 serpapi_key: Optional[str] = None,
                 tineye_key: Optional[str] = None):
        """
        Args:
            serpapi_key: SerpAPI key for Google Lens (optional)
            tineye_key: TinEye API key (optional)
        """
        self.serpapi_key = serpapi_key or os.getenv('SERPAPI_KEY')
        self.tineye_key = tineye_key or os.getenv('TINEYE_API_KEY')
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self._http_client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
        )
        return self
    
    async def __aexit__(self, *args):
        if self._http_client:
            await self._http_client.aclose()
    
    async def search(self, image_url: str, max_results: int = 10) -> List[ReverseImageResult]:
        """
        Search for similar images across all available backends.
        
        Args:
            image_url: URL of image to search
            max_results: Max results per backend
        
        Returns:
            Combined results from all backends, sorted by confidence
        """
        if not self._http_client:
            raise RuntimeError("Use async context manager")
        
        all_results = []
        
        # Try SerpAPI (Google Lens) if key available
        if self.serpapi_key:
            try:
                results = await self._search_serpapi(image_url, max_results)
                all_results.extend(results)
            except Exception as e:
                print(f"SerpAPI search failed: {e}")
        
        # Try free Google Lens scrape (no API key needed)
        if not self.serpapi_key and not all_results:
            try:
                results = await self._search_google_lens_free(image_url, max_results)
                all_results.extend(results)
            except Exception as e:
                print(f"Google Lens free search failed: {e}")

        # Try TinEye if key available
        if self.tineye_key:
            try:
                results = await self._search_tineye(image_url, max_results)
                all_results.extend(results)
            except Exception as e:
                print(f"TinEye search failed: {e}")
        
        # Fallback: Search known fashion platforms directly
        try:
            results = await self._search_fashion_platforms(image_url)
            all_results.extend(results)
        except Exception as e:
            print(f"Fashion platform search failed: {e}")
        
        # Sort by confidence
        all_results.sort(key=lambda r: r.confidence, reverse=True)
        return all_results[:max_results]
    
    async def _search_serpapi(self, image_url: str, max_results: int = 10) -> List[ReverseImageResult]:
        """
        Search via SerpAPI (Google Lens).
        
        SerpAPI provides structured access to Google Lens results.
        """
        url = "https://serpapi.com/search"
        params = {
            'engine': 'google_lens',
            'url': image_url,
            'api_key': self.serpapi_key,
            'num': max_results
        }
        
        response = await self._http_client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        results = []
        
        # Parse visual matches
        visual_matches = data.get('visual_matches', [])
        for match in visual_matches[:max_results]:
            result = ReverseImageResult(
                title=match.get('title', ''),
                url=match.get('link', ''),
                source='google_lens',
                image_url=match.get('thumbnail'),
                confidence=self._calculate_confidence(match),
                metadata={'type': 'visual_match', 'source_page': match.get('source')}
            )
            # Try to extract price
            result.price = self._extract_price(match.get('title', ''))
            results.append(result)
        
        # Parse exact matches (if available)
        exact_matches = data.get('exact_matches', [])
        for match in exact_matches[:max_results]:
            result = ReverseImageResult(
                title=match.get('title', ''),
                url=match.get('link', ''),
                source='google_lens_exact',
                image_url=match.get('thumbnail'),
                confidence=1.0,  # Exact match = highest confidence
                metadata={'type': 'exact_match'}
            )
            result.price = self._extract_price(match.get('title', ''))
            results.append(result)
        
        return results
    
    async def _search_google_lens_free(self, image_url: str, max_results: int = 10) -> List[ReverseImageResult]:
        """
        Search Google Lens without an API key.
        
        Uses Google's public Lens URL which returns an HTML page with visual matches.
        Rate-limited but works for moderate volumes.
        """
        results = []

        try:
            # Google Lens accepts an image URL as a query param
            lens_url = f"https://lens.google.com/uploadbyurl?url={quote(image_url)}"

            response = await self._http_client.get(lens_url, follow_redirects=True)
            if response.status_code != 200:
                return results

            html = response.text

            # Google Lens embeds structured data in the page as AF_initDataCallback chunks
            # Extract visual match data from the HTML
            import json as _json

            # Method 1: Look for product/shopping results in structured data
            # Google embeds JSON arrays in script tags with AF_initDataCallback
            for pattern in [
                r'AF_initDataCallback\(\{[^}]*key:\s*\'ds:1\'[^}]*data:(.*?)\}\s*\)\s*;',
                r'AF_initDataCallback\(\{[^}]*key:\s*\'ds:0\'[^}]*data:(.*?)\}\s*\)\s*;',
            ]:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    try:
                        # This is deeply nested — we extract what we can
                        raw = match.group(1).strip()
                        # Truncate at reasonable length to avoid parsing issues
                        if len(raw) > 100000:
                            raw = raw[:100000]
                        data = _json.loads(raw)
                        results.extend(self._parse_lens_data(data, max_results))
                        if results:
                            break
                    except (_json.JSONDecodeError, Exception):
                        continue

            # Method 2: Fallback — extract titles and URLs from meta/link tags
            if not results:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "lxml")

                # Look for visual match cards
                for link in soup.select("a[href*='imgres'], a[data-action-url]"):
                    href = link.get("href", "") or link.get("data-action-url", "")
                    title_el = link.select_one("div, span, h3")
                    title = title_el.get_text(strip=True) if title_el else ""

                    if not title or len(title) < 5:
                        continue

                    # Extract actual URL from Google redirect
                    url_match = re.search(r'(?:url|imgurl)=([^&]+)', href)
                    actual_url = url_match.group(1) if url_match else href

                    result = ReverseImageResult(
                        title=title,
                        url=actual_url,
                        source="google_lens_free",
                        confidence=self._calculate_confidence({"title": title, "source": actual_url}),
                    )
                    result.price = self._extract_price(title)
                    results.append(result)

                    if len(results) >= max_results:
                        break

        except Exception as e:
            print(f"Google Lens free error: {e}")

        return results[:max_results]

    def _parse_lens_data(self, data, max_results: int) -> List[ReverseImageResult]:
        """Parse structured data from Google Lens AF_initDataCallback."""
        results = []

        def _walk(obj, depth=0):
            """Recursively walk nested arrays looking for result-like structures."""
            if depth > 15 or len(results) >= max_results:
                return
            if isinstance(obj, list):
                # Look for [title, url, ...] patterns
                if (len(obj) >= 3
                    and isinstance(obj[0], str) and len(obj[0]) > 5
                    and isinstance(obj[1], str) and obj[1].startswith("http")):
                    title = obj[0]
                    url = obj[1]
                    # Skip Google's own URLs
                    if "google.com" not in url:
                        result = ReverseImageResult(
                            title=title,
                            url=url,
                            source="google_lens_free",
                            confidence=self._calculate_confidence({"title": title, "source": url}),
                        )
                        result.price = self._extract_price(title)
                        results.append(result)
                for item in obj:
                    _walk(item, depth + 1)
            elif isinstance(obj, dict):
                for v in obj.values():
                    _walk(v, depth + 1)

        _walk(data)
        return results

    async def _search_tineye(self, image_url: str, max_results: int = 10) -> List[ReverseImageResult]:
        """
        Search via TinEye API.
        
        TinEye specializes in exact and near-exact image matches.
        """
        url = "https://api.tineye.com/rest/search/"
        
        # TinEye uses image URL directly
        params = {
            'api_key': self.tineye_key,
            'image_url': image_url,
            'limit': max_results
        }
        
        response = await self._http_client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        results = []
        matches = data.get('results', {}).get('matches', [])
        
        for match in matches[:max_results]:
            # Calculate confidence from overlap score
            overlap = match.get('overlap', 0)  # 0-100
            confidence = overlap / 100.0
            
            for backlink in match.get('backlinks', [])[:3]:  # Limit backlinks per match
                result = ReverseImageResult(
                    title=backlink.get('crawl_date', 'TinEye Result'),
                    url=backlink.get('url', ''),
                    source='tineye',
                    confidence=confidence,
                    metadata={
                        'tineye_match_id': match.get('image_hash', ''),
                        'crawl_date': backlink.get('crawl_date', '')
                    }
                )
                results.append(result)
        
        return results
    
    async def _search_fashion_platforms(self, image_url: str) -> List[ReverseImageResult]:
        """
        Fallback: Search known fashion platforms using image similarity.
        
        This is a lightweight fallback that checks if similar images exist
        on Grailed by using our own database.
        """
        results = []
        
        # First, fingerprint the query image
        try:
            async with ImageFingerprinter() as fp:
                fingerprint = await fp.fingerprint_from_url(image_url)
                
                if not fingerprint.is_valid:
                    return results
                
                # Search our own database for similar images
                from db.sqlite_models import find_similar_by_phash
                similar_items = find_similar_by_phash(fingerprint.phash, threshold=10, limit=5)
                
                for item in similar_items:
                    result = ReverseImageResult(
                        title=item.title,
                        url=item.source_url,
                        source='archive_arbitrage_db',
                        confidence=0.8,  # High confidence from our own db
                        metadata={
                            'item_id': item.id,
                            'brand': item.brand,
                            'our_price': item.our_price
                        }
                    )
                    results.append(result)
        
        except Exception as e:
            print(f"Fashion platform search error: {e}")
        
        return results
    
    def _calculate_confidence(self, match: dict) -> float:
        """Calculate confidence score from Google Lens match."""
        confidence = 0.5  # Base confidence
        
        # Boost if it's an exact domain match for fashion
        source = match.get('source', '').lower()
        if any(domain in source for domain in ['grailed', 'ebay', 'poshmark', 'depop']):
            confidence += 0.2
        
        # Boost if title looks like a product listing
        title = match.get('title', '')
        if any(keyword in title.lower() for keyword in ['size', 'authentic', 'vintage', 'rare']):
            confidence += 0.1
        
        # Boost if there's a price in the title
        if self._extract_price(title):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _extract_price(self, text: str) -> Optional[float]:
        """Extract price from text."""
        if not text:
            return None
        
        # Look for price patterns: $123, $123.45, 123 USD, etc.
        patterns = [
            r'\$([\d,]+\.?\d*)',           # $123 or $123.45
            r'([\d,]+\.?\d*)\s*USD',       # 123 USD
            r'([\d,]+\.?\d*)\s*dollars',  # 123 dollars
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    price_str = match.group(1).replace(',', '')
                    return float(price_str)
                except ValueError:
                    continue
        
        return None


class ProductIdentifier:
    """
    Identify exact products from images and text.
    
    Combines reverse image search with title analysis to extract:
    - Exact product name
    - Season/year (from title or matches)
    - Typical selling price (from matches)
    """
    
    def __init__(self, serpapi_key: Optional[str] = None):
        self.serpapi_key = serpapi_key or os.getenv('SERPAPI_KEY')
    
    async def identify_product(self, 
                               image_url: str, 
                               title: str,
                               brand: str) -> Dict:
        """
        Identify exact product from image and title.
        
        Returns:
            {
                'product_name': str,
                'confidence': float,
                'season': Optional[str],
                'year': Optional[int],
                'price_range': Optional[Tuple[float, float]],
                'sources': List[str],
                'matches': List[ReverseImageResult]
            }
        """
        async with ReverseImageSearcher(serpapi_key=self.serpapi_key) as searcher:
            # Search by image
            results = await searcher.search(image_url, max_results=10)
        
        if not results:
            return {
                'product_name': None,
                'confidence': 0.0,
                'season': None,
                'year': None,
                'price_range': None,
                'sources': [],
                'matches': []
            }
        
        # Analyze titles from matches to extract product name
        product_names = []
        prices = []
        seasons = []
        years = []
        sources = set()
        
        for result in results:
            if result.title:
                # Clean and extract product name
                clean_name = self._clean_product_name(result.title, brand)
                if clean_name:
                    product_names.append(clean_name)
            
            if result.price:
                prices.append(result.price)
            
            # Extract season/year from result title
            from scrapers.seasons import extract_exact_season
            season_result = extract_exact_season(result.title)
            if season_result:
                season, year = season_result
                if season:
                    seasons.append(season)
                if year:
                    years.append(year)
            
            sources.add(result.source)
        
        # Find most common product name
        from collections import Counter
        product_name = None
        if product_names:
            name_counter = Counter(product_names)
            product_name, count = name_counter.most_common(1)[0]
            name_confidence = count / len(product_names)
        else:
            name_confidence = 0.0
        
        # Calculate price range
        price_range = None
        if prices:
            price_range = (min(prices), max(prices))
        
        # Most common season/year
        season = None
        year = None
        if seasons:
            season = Counter(seasons).most_common(1)[0][0]
        if years:
            year = Counter(years).most_common(1)[0][0]
        
        # Overall confidence
        avg_match_confidence = sum(r.confidence for r in results) / len(results)
        overall_confidence = (name_confidence * 0.5) + (avg_match_confidence * 0.5)
        
        return {
            'product_name': product_name,
            'confidence': overall_confidence,
            'season': season,
            'year': year,
            'price_range': price_range,
            'sources': list(sources),
            'matches': results
        }
    
    def _clean_product_name(self, title: str, brand: str) -> Optional[str]:
        """Extract clean product name from title."""
        if not title:
            return None
        
        title_lower = title.lower()
        brand_lower = brand.lower()
        
        # Remove brand name if at start
        if title_lower.startswith(brand_lower):
            title = title[len(brand):].strip()
        
        # Remove common noise words
        noise_words = [
            'authentic', 'genuine', 'vintage', 'rare', 'nwt', 'bnwt', 'new',
            'pre-owned', 'preowned', 'used', 'excellent', 'condition',
            'size', 'sz', 'fits', 'like', 'free shipping', 'fast shipping'
        ]
        
        for word in noise_words:
            title = re.sub(rf'\b{word}\b', '', title, flags=re.IGNORECASE)
        
        # Remove extra whitespace
        title = ' '.join(title.split())
        
        # Remove size info (e.g., "size M", "sz 42")
        title = re.sub(r'\bsize\s*\w+\b', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\bsz\s*\w+\b', '', title, flags=re.IGNORECASE)
        
        # Clean up again
        title = ' '.join(title.split())
        
        return title.strip() if len(title) > 5 else None


# ============================================================================
# CLI / TEST
# ============================================================================

if __name__ == "__main__":
    import asyncio
    import sys
    
    async def test():
        print("Reverse Image Search Test")
        print("=" * 60)
        
        # Test image (Rick Owens Geobasket)
        test_url = 'https://process.fs.grailed.com/AJdAgnqCST4iPtnUxiGtTz/cache=expiry:max/rotate=deg:exif/resize=width:480,fit:crop/output=format:webp,quality:80/compress/https://cdn.fs.grailed.com/api/file/2XcTmqNTZ2hX6slkNV6Q'
        
        serpapi_key = os.getenv('SERPAPI_KEY')
        
        if not serpapi_key:
            print("⚠️  No SERPAPI_KEY found. Testing with fallback only.")
            print("   Set SERPAPI_KEY env var for Google Lens search.")
        
        async with ReverseImageSearcher(serpapi_key=serpapi_key) as searcher:
            print(f"\nSearching for: {test_url[:60]}...")
            results = await searcher.search(test_url, max_results=5)
            
            print(f"\nFound {len(results)} results:\n")
            
            for i, result in enumerate(results, 1):
                print(f"{i}. [{result.source}] {result.title[:60]}...")
                print(f"   URL: {result.url[:60]}...")
                print(f"   Confidence: {result.confidence:.0%}")
                if result.price:
                    print(f"   Price: ${result.price:.0f}")
                print()
        
        # Test product identification
        print("=" * 60)
        print("Product Identification Test")
        print("=" * 60)
        
        identifier = ProductIdentifier(serpapi_key=serpapi_key)
        info = await identifier.identify_product(
            image_url=test_url,
            title="Rick Owens Geobasket Black Leather Size 42",
            brand="rick owens"
        )
        
        print(f"\nIdentified Product:")
        print(f"  Name: {info['product_name'] or 'Unknown'}")
        print(f"  Confidence: {info['confidence']:.0%}")
        print(f"  Season: {info['season'] or 'Unknown'}")
        print(f"  Year: {info['year'] or 'Unknown'}")
        if info['price_range']:
            print(f"  Price Range: ${info['price_range'][0]:.0f} - ${info['price_range'][1]:.0f}")
        print(f"  Sources: {', '.join(info['sources'])}")
    
    asyncio.run(test())
