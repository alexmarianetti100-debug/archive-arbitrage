import os
import httpx
import logging
import json # Required for json.dumps in logging

logger = logging.getLogger("whop_alerts")

WHOP_API_KEY = os.getenv("WHOP_API_KEY")
WHOP_EXPERIENCE_ID = os.getenv("WHOP_EXPERIENCE_ID", "exp_c8acBs3P3KyJKa")
WHOP_ENDPOINT = os.getenv("WHOP_ENDPOINT", "https://api.whop.com/api/v5/forum_posts")
WHOP_ENABLED = os.getenv("WHOP_ENABLED", "true").lower() in ("1", "true", "yes")
WHOP_DRY_RUN = os.getenv("WHOP_DRY_RUN", "true").lower() in ("1", "true", "yes") # Default to dry-run for safe testing
WHOP_DIAGNOSTIC = os.getenv("WHOP_DIAGNOSTIC", "false").lower() in ("1", "true", "yes") # For verbose logging of the request

async def send_whop_alert(title: str, content: str) -> bool:
    """
    Sends an alert to Whop forums.
    """
    if not WHOP_ENABLED:
        logger.debug("Whop alerts are disabled via WHOP_ENABLED flag.")
        return False

    if not WHOP_API_KEY:
        logger.warning("WHOP_API_KEY is not set in environment. Skipping Whop alert.")
        return False
    
    if not WHOP_EXPERIENCE_ID:
        logger.warning("WHOP_EXPERIENCE_ID is not set. Skipping Whop alert.")
        return False

    if WHOP_DRY_RUN:
        logger.info("WHOP_DRY_RUN is enabled; skipping real network call, simulating post.")
        logger.info(f"Would post to Whop:")
        logger.info(f"  Endpoint: {WHOP_ENDPOINT}")
        logger.info(f"  Experience ID: {WHOP_EXPERIENCE_ID}")
        logger.info(f"  Title: {title[:60]}...")
        logger.info(f"  Content: {content[:100]}{'...' if len(content) > 100 else ''}")
        
        # If diagnostic mode is on, print more detailed request info
        if WHOP_DIAGNOSTIC:
            payload = {
                "experience_id": WHOP_EXPERIENCE_ID,
                "title": title,
                "content": content
            }
            logger.info(f"  Payload (JSON): {json.dumps(payload, indent=2)}")
            logger.info(f"  Headers: {{'Authorization': 'Bearer *****', 'Content-Type': 'application/json'}}")
        return True

    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "experience_id": WHOP_EXPERIENCE_ID,
                "title": title,
                "content": content
            }
            response = await client.post(
                WHOP_ENDPOINT,
                headers={   # Explicitly set headers to match curl command
                    "Authorization": f"Bearer {WHOP_API_KEY.strip()}", # Ensure no leading/trailing whitespace
                    "Content-Type": "application/json",
                    "Accept": "application/json" # Good practice to include Accept header
                },
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            logger.info(f"Successfully posted deal alert to Whop experience {WHOP_EXPERIENCE_ID}.")
            return True
    except Exception as e:
        logger.error(f"Failed to post to Whop: {e}")
        if isinstance(e, httpx.HTTPStatusError):
            logger.error(f"Whop API response: {e.response.status_code} - {e.response.text}")
        return False

def format_whop_deal_content(item, price_rec, margin, profit) -> tuple[str, str]:
    """Generates the title and markdown content for the Whop post."""
    short_title = item.title[:50] if item.title else "Unknown Item"
    title = f"Deal Alert: {short_title} | Profit: ${profit:.0f}"
    
    brand = item.brand or "Unknown Brand"
    price = getattr(item, "price", 0.0) or getattr(item, "source_price", 0.0)
    url = getattr(item, "url", "") or getattr(item, "source_url", "")
    
    content = f"""
## **{brand}** - {item.title}

**💰 The Numbers:**
- Buy For: ${price:.2f}
- True Market Value: ${price_rec.recommended_price:.2f}
- Estimated Profit: **${profit:.2f}** ({margin*100:.0f}% margin)

**🔗 Links:**
[Buy it here]({url})

**📊 Data:**
- Confidence: {price_rec.confidence}
- Comps checked: {price_rec.comps_count}
- Demand: {price_rec.demand_level}
"""
    return title, content
