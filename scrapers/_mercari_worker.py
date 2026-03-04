#!/usr/bin/env python3
"""
Mercari worker — runs in a subprocess, prints JSON to stdout.
Called by mercari_subprocess.py. Not meant to be imported.
"""

import asyncio
import json
import sys
import os

# Silence all logging to stderr
os.environ["PYTHONUNBUFFERED"] = "1"
import logging
logging.disable(logging.CRITICAL)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else ""
    max_results = int(sys.argv[2]) if len(sys.argv) > 2 else 15

    if not query:
        print("[]")
        return

    from scrapers.mercari import MercariScraper

    results = []
    try:
        scraper = MercariScraper()
        await scraper._ensure_browser()
        items = await scraper.search(query, max_results=max_results)

        for item in items:
            results.append({
                "source_id": item.source_id,
                "url": item.url,
                "title": item.title,
                "price": item.price,
                "images": item.images,
                "raw_data": item.raw_data or {},
            })

        await scraper.close()
    except Exception:
        pass

    print(json.dumps(results))


if __name__ == "__main__":
    asyncio.run(main())
