"""
Vinted international health check — Phase 1 diagnostic.
Uses Camoufox + semaphore (MAX_CONCURRENT=4) to test all 20 domains.
Outputs a per-domain table + JSON health report to vinted_health.json.
"""
import asyncio, json, re, sys, time
from urllib.parse import quote_plus
from datetime import datetime

QUERY        = "balenciaga"
MAX_CONC     = 2
PAGE_TIMEOUT = 30000
SETTLE       = 2
MAX_RETRIES  = 2

DOMAINS = [
    "https://www.vinted.com",
    "https://www.vinted.co.uk",
    "https://www.vinted.fr",
    "https://www.vinted.de",
    "https://www.vinted.es",
    "https://www.vinted.it",
    "https://www.vinted.pl",
    "https://www.vinted.be",
    "https://www.vinted.nl",
    "https://www.vinted.at",
    "https://www.vinted.lu",
    "https://www.vinted.cz",
    "https://www.vinted.sk",
    "https://www.vinted.hu",
    "https://www.vinted.ro",
    "https://www.vinted.pt",
    "https://www.vinted.se",
    "https://www.vinted.dk",
    "https://www.vinted.fi",
    "https://www.vinted.lt",
]

try:
    from camoufox.async_api import AsyncCamoufox
except ImportError:
    print("ERROR: camoufox not installed.")
    sys.exit(1)


async def test_domain(sem, browser, domain: str) -> dict:
    r = {
        "domain": domain, "loaded": False, "cf_blocked": False,
        "cards": 0, "items": 0, "sample": None,
        "error": None, "attempts": 0, "elapsed_s": 0,
    }
    search_url = f"{domain}/catalog?search_text={quote_plus(QUERY)}&order=newest_first"

    async with sem:
        t0 = time.time()
        for attempt in range(1, MAX_RETRIES + 1):
            r["attempts"] = attempt
            ctx = None
            try:
                ctx = await browser.new_context()
                page = await ctx.new_page()

                try:
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
                    r["loaded"] = True
                except Exception as e:
                    r["error"] = f"goto: {str(e)[:80]}"
                    await ctx.close()
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(2 ** attempt)
                    continue

                # Cloudflare check
                title = (await page.title()).lower()
                body  = await page.evaluate("() => document.body?.innerText || ''")
                if "just a moment" in title or "verifying you are human" in body.lower():
                    r["cf_blocked"] = True
                    r["error"] = "Cloudflare challenge"
                    await ctx.close()
                    break  # no point retrying without proxy

                # Wait for JS-rendered product grid
                try:
                    await page.wait_for_selector(
                        ".feed-grid__item, [data-testid*='product-item-id']",
                        timeout=15000
                    )
                except Exception:
                    pass

                # Count cards
                cards = await page.query_selector_all(".feed-grid__item")
                if not cards:
                    cards = await page.query_selector_all('[data-testid*="product-item-id"]')
                r["cards"] = len(cards)

                # Try to extract a sample item
                items_found = 0
                for card in cards[:5]:
                    try:
                        link = await card.query_selector("a.new-item-box__overlay, a[href*='/items/']")
                        if not link:
                            continue
                        title_attr = await link.get_attribute("title") or ""
                        prices = re.findall(r"[\$€£][\d,]+\.?\d*", title_attr)
                        if prices:
                            items_found += 1
                            if not r["sample"]:
                                # Title is up to first metadata comma
                                cut = min(
                                    (m.start() for p in [r",\s*brand:", r",\s*condition:", r",\s*[\$€£]"]
                                     if (m := re.search(p, title_attr, re.I))),
                                    default=len(title_attr)
                                )
                                r["sample"] = f"{title_attr[:cut].strip()} — {prices[0]}"
                    except Exception:
                        continue
                r["items"] = items_found or r["cards"]  # fallback to card count

                await ctx.close()
                r["error"] = None
                break  # success

            except Exception as e:
                r["error"] = str(e)[:80]
                if ctx:
                    try: await ctx.close()
                    except Exception: pass
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)

        r["elapsed_s"] = round(time.time() - t0, 1)
    return r


async def main():
    print(f"\n🔍 Vinted International Health Check — query: '{QUERY}'")
    print(f"   Concurrency: {MAX_CONC} | Retries: {MAX_RETRIES} | Timeout: {PAGE_TIMEOUT//1000}s\n")
    print(f"{'Domain':<28} {'Load':>5} {'CF?':>4} {'Cards':>6} {'Items':>6} {'Tries':>6} {'Time':>6}  Sample")
    print("─" * 110)

    sem = asyncio.Semaphore(MAX_CONC)
    health = {"generated": datetime.utcnow().isoformat(), "query": QUERY, "domains": []}

    async with AsyncCamoufox(headless=True, geoip=True) as browser:
        tasks   = [test_domain(sem, browser, d) for d in DOMAINS]
        results = await asyncio.gather(*tasks)

    working, broken = [], []
    for r in results:
        short = r["domain"].replace("https://www.", "")
        load  = "✅" if r["loaded"] else "❌"
        cf    = "🔴" if r["cf_blocked"] else "  "
        ok    = r["items"] > 0

        sample = r["sample"] or (r["error"] or "0 items")
        if len(sample) > 55:
            sample = sample[:52] + "..."

        print(f"{short:<28} {load:>5} {cf:>4} {r['cards']:>6} {r['items']:>6} "
              f"{r['attempts']:>6} {r['elapsed_s']:>5}s  {sample}")

        health["domains"].append({
            "domain": r["domain"], "loaded": r["loaded"], "cf_blocked": r["cf_blocked"],
            "cards": r["cards"], "items": r["items"],
            "attempts": r["attempts"], "elapsed_s": r["elapsed_s"],
            "sample": r["sample"], "error": r["error"],
        })
        (working if ok else broken).append(short)

    print("─" * 110)
    print(f"\n✅ Working ({len(working)}): {', '.join(working) or 'none'}")
    print(f"❌ Broken  ({len(broken)}):  {', '.join(broken) or 'none'}\n")

    with open("vinted_health.json", "w") as f:
        json.dump(health, f, indent=2)
    print(f"📄 Full report saved to vinted_health.json\n")


if __name__ == "__main__":
    asyncio.run(main())
