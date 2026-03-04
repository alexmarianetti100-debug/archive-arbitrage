"""
Mercari subprocess wrapper — runs the Playwright scraper in an isolated process.

Mercari requires Playwright (headless browser) which crashes the async event loop
when cancelled. This wrapper runs it in a subprocess so failures are contained.

Usage:
    results = await mercari_search("rick owens", max_results=15, timeout=30)
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from typing import List

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.base import ScrapedItem


async def mercari_search(query: str, max_results: int = 15, timeout: int = 45) -> List[ScrapedItem]:
    """
    Search Mercari in a subprocess. Returns ScrapedItem list.
    If the subprocess crashes or times out, returns empty list (never crashes caller).
    """
    script = Path(__file__).parent / "_mercari_worker.py"

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(script), query, str(max_results),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(__file__).parent.parent),
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return []

        if proc.returncode != 0:
            return []

        # Parse JSON output
        try:
            data = json.loads(stdout.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return []

        items = []
        for raw in data:
            items.append(ScrapedItem(
                source="mercari",
                source_id=raw.get("source_id", ""),
                url=raw.get("url", ""),
                title=raw.get("title", ""),
                price=float(raw.get("price", 0)),
                currency="USD",
                images=raw.get("images", []),
                raw_data=raw.get("raw_data", {}),
            ))
        return items

    except Exception:
        return []
