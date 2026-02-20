"""
Image Fingerprinter - Perceptual hashing for image deduplication and matching.

Uses pHash (perceptual hash) to generate 64-bit fingerprints of images.
Similar images (same product, different angles/lighting) will have similar hashes.
"""

import io
import asyncio
from typing import Optional, List, Tuple
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image
    import imagehash
    HAS_IMAGE_LIBS = True
except ImportError:
    HAS_IMAGE_LIBS = False
    print("Warning: imagehash/PIL not installed. Run: pip install imagehash Pillow")

import hashlib
import httpx
from urllib.parse import urlparse


@dataclass
class ImageFingerprint:
    """Fingerprint result for an image."""
    url: str
    phash: str           # Perceptual hash (64-bit)
    ahash: str           # Average hash (64-bit)
    dhash: str           # Difference hash (64-bit)
    whash: str           # Wavelet hash (64-bit)
    file_hash: str       # MD5 of image content (for exact dupes)
    width: int
    height: int
    error: Optional[str] = None
    
    @property
    def is_valid(self) -> bool:
        return self.phash is not None and self.error is None


class ImageFingerprinter:
    """
    Generate perceptual hashes for images.
    
    pHash is resistant to:
    - Minor cropping
    - Color adjustments
    - Compression artifacts
    - Small rotations
    - Watermarks
    
    Perfect for matching the same product across different listings.
    """
    
    def __init__(self, hash_size: int = 8):
        """
        Args:
            hash_size: Size of hash (8 = 64-bit, 16 = 256-bit)
                      Larger = more precise but slower
        """
        self.hash_size = hash_size
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self._http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        return self
    
    async def __aexit__(self, *args):
        if self._http_client:
            await self._http_client.aclose()
    
    async def download_image(self, url: str) -> Optional[bytes]:
        """Download image from URL."""
        if not self._http_client:
            raise RuntimeError("Use async context manager: async with ImageFingerprinter() as fp:")
        
        try:
            response = await self._http_client.get(url)
            response.raise_for_status()
            return response.content
        except Exception as e:
            return None
    
    def fingerprint_from_bytes(self, image_bytes: bytes, url: str = "") -> ImageFingerprint:
        """
        Generate fingerprints from image bytes.
        
        Returns multiple hash types for different use cases:
        - phash: Best for finding similar images (resilient to minor changes)
        - ahash: Fast, good for exact/near-exact matches
        - dhash: Good for detecting similar images with different crops
        - whash: Good for detecting structural similarity
        """
        if not HAS_IMAGE_LIBS:
            return ImageFingerprint(
                url=url,
                phash=None, ahash=None, dhash=None, whash=None,
                file_hash=None, width=0, height=0,
                error="imagehash/PIL not installed"
            )
        
        try:
            # Load image
            img = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Get dimensions
            width, height = img.size
            
            # File hash (for exact duplicates)
            file_hash = hashlib.md5(image_bytes).hexdigest()
            
            # Generate perceptual hashes
            phash = str(imagehash.phash(img, hash_size=self.hash_size))
            ahash = str(imagehash.average_hash(img, hash_size=self.hash_size))
            dhash = str(imagehash.dhash(img, hash_size=self.hash_size))
            whash = str(imagehash.whash(img, hash_size=self.hash_size))
            
            return ImageFingerprint(
                url=url,
                phash=phash,
                ahash=ahash,
                dhash=dhash,
                whash=whash,
                file_hash=file_hash,
                width=width,
                height=height
            )
            
        except Exception as e:
            return ImageFingerprint(
                url=url,
                phash=None, ahash=None, dhash=None, whash=None,
                file_hash=None, width=0, height=0,
                error=str(e)
            )
    
    async def fingerprint_from_url(self, url: str) -> ImageFingerprint:
        """Download and fingerprint an image from URL."""
        image_bytes = await self.download_image(url)
        
        if image_bytes is None:
            return ImageFingerprint(
                url=url,
                phash=None, ahash=None, dhash=None, whash=None,
                file_hash=None, width=0, height=0,
                error="Failed to download image"
            )
        
        return self.fingerprint_from_bytes(image_bytes, url)
    
    async def fingerprint_multiple(self, urls: List[str], max_concurrent: int = 5) -> List[ImageFingerprint]:
        """Fingerprint multiple images with concurrency limit."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def _fingerprint(url: str) -> ImageFingerprint:
            async with semaphore:
                return await self.fingerprint_from_url(url)
        
        tasks = [_fingerprint(url) for url in urls]
        return await asyncio.gather(*tasks)


# ============================================================================
# HASH COMPARISON UTILITIES
# ============================================================================

def hex_to_binary(hex_string: str) -> str:
    """Convert hex hash to binary string for hamming distance."""
    return bin(int(hex_string, 16))[2:].zfill(len(hex_string) * 4)


def hamming_distance(hash1: str, hash2: str) -> int:
    """
    Calculate Hamming distance between two hashes.
    
    Lower = more similar
    0 = identical
    5-10 = likely same image with minor changes
    20+ = different images
    """
    if len(hash1) != len(hash2):
        return float('inf')
    
    # Convert hex to binary and count differences
    bin1 = hex_to_binary(hash1)
    bin2 = hex_to_binary(hash2)
    
    return sum(c1 != c2 for c1, c2 in zip(bin1, bin2))


def are_images_similar(fp1: ImageFingerprint, fp2: ImageFingerprint, 
                       threshold: int = 10) -> Tuple[bool, int]:
    """
    Check if two images are likely the same product.
    
    Args:
        threshold: Max Hamming distance for similarity (default 10 for 64-bit hash)
    
    Returns:
        (is_similar, distance)
    """
    if not fp1.is_valid or not fp2.is_valid:
        return False, float('inf')
    
    # Check exact duplicate first
    if fp1.file_hash == fp2.file_hash:
        return True, 0
    
    # Use pHash for similarity
    distance = hamming_distance(fp1.phash, fp2.phash)
    return distance <= threshold, distance


def find_similar_images(target: ImageFingerprint, 
                       candidates: List[ImageFingerprint],
                       threshold: int = 10) -> List[Tuple[ImageFingerprint, int]]:
    """
    Find all images similar to target.
    
    Returns list of (fingerprint, distance) sorted by similarity.
    """
    results = []
    
    for candidate in candidates:
        is_similar, distance = are_images_similar(target, candidate, threshold)
        if is_similar:
            results.append((candidate, distance))
    
    # Sort by distance (most similar first)
    results.sort(key=lambda x: x[1])
    return results


# ============================================================================
# DATABASE INTEGRATION
# ============================================================================

def save_image_hash_to_db(item_id: int, fingerprint: ImageFingerprint):
    """Save image hash to database (to be called from pipeline)."""
    from db.sqlite_models import DB_PATH
    import sqlite3
    
    if not fingerprint.is_valid:
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Add image_hash column if not exists
    cursor.execute("PRAGMA table_info(items)")
    columns = {row[1] for row in cursor.fetchall()}
    
    if 'image_hash' not in columns:
        cursor.execute("ALTER TABLE items ADD COLUMN image_hash TEXT")
    
    if 'image_phash' not in columns:
        cursor.execute("ALTER TABLE items ADD COLUMN image_phash TEXT")
    
    # Update item with hash
    cursor.execute(
        "UPDATE items SET image_hash = ?, image_phash = ? WHERE id = ?",
        (fingerprint.file_hash, fingerprint.phash, item_id)
    )
    
    conn.commit()
    conn.close()


def find_items_by_image_hash(phash: str, threshold: int = 10) -> List[dict]:
    """Find items with similar images."""
    from db.sqlite_models import DB_PATH
    import sqlite3
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all items with image hashes
    cursor.execute("SELECT id, title, brand, image_phash FROM items WHERE image_phash IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()
    
    # Find similar hashes
    similar = []
    for row in rows:
        distance = hamming_distance(phash, row['image_phash'])
        if distance <= threshold:
            similar.append({
                'id': row['id'],
                'title': row['title'],
                'brand': row['brand'],
                'distance': distance
            })
    
    similar.sort(key=lambda x: x['distance'])
    return similar


# ============================================================================
# CLI / TEST
# ============================================================================

if __name__ == "__main__":
    import sys
    import asyncio
    
    async def test():
        print("Image Fingerprinter Test")
        print("=" * 60)
        
        if not HAS_IMAGE_LIBS:
            print("❌ imagehash/PIL not installed")
            print("   Run: pip install imagehash Pillow")
            sys.exit(1)
        
        # Test with sample images
        test_urls = [
            "https://process.fs.grailed.com/AJdAgnqCST4iPtnUxiGtTz/cache=expiry:max/rotate=deg:exif/resize=width:480,fit:crop/output=format:webp,quality:80/compress/https://cdn.fs.grailed.com/api/file/AeqO3cRSCW5cG4f6TX6A",  # Rick Owens
            "https://process.fs.grailed.com/AJdAgnqCST4iPtnUxiGtTz/cache=expiry:max/rotate=deg:exif/resize=width:480,fit:crop/output=format:webp,quality:80/compress/https://cdn.fs.grailed.com/api/file/2XcTmqNTZ2hX6slkNVqQ",  # Different RO
            "https://process.fs.grailed.com/AJdAgnqCST4iPtnUxiGtTz/cache=expiry:max/rotate=deg:exif/resize=width:480,fit:crop/output=format:webp,quality:80/compress/https://cdn.fs.grailed.com/api/file/abc123",  # Different item
        ]
        
        async with ImageFingerprinter(hash_size=8) as fingerprinter:
            print(f"\nFingerprinting {len(test_urls)} images...\n")
            
            fingerprints = await fingerprinter.fingerprint_multiple(test_urls)
            
            for i, fp in enumerate(fingerprints, 1):
                print(f"Image {i}:")
                if fp.is_valid:
                    print(f"  URL: {fp.url[:60]}...")
                    print(f"  pHash: {fp.phash}")
                    print(f"  aHash: {fp.ahash}")
                    print(f"  Size: {fp.width}x{fp.height}")
                    print(f"  File hash: {fp.file_hash[:16]}...")
                else:
                    print(f"  ❌ Error: {fp.error}")
                print()
            
            # Compare similarities
            if len(fingerprints) >= 2 and all(fp.is_valid for fp in fingerprints[:2]):
                print("Similarity Analysis:")
                print("-" * 60)
                
                fp1, fp2 = fingerprints[0], fingerprints[1]
                is_similar, distance = are_images_similar(fp1, fp2, threshold=10)
                
                print(f"Image 1 vs Image 2:")
                print(f"  Hamming distance: {distance}")
                print(f"  Similar: {'✅ Yes' if is_similar else '❌ No'}")
                
                if fp1.file_hash == fp2.file_hash:
                    print(f"  ⚠️  Exact duplicate detected!")
        
        print("\n" + "=" * 60)
        print("Test complete!")
    
    asyncio.run(test())
