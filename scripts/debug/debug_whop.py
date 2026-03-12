import asyncio, httpx, os
from dotenv import load_dotenv

load_dotenv()


async def run():
    key = os.getenv("WHOP_API_KEY")
    experience_id = os.getenv("WHOP_EXPERIENCE_ID")
    url = "https://api.whop.com/api/v5/forum_posts"

    if not key:
        raise RuntimeError("WHOP_API_KEY is not set")
    if not experience_id:
        raise RuntimeError("WHOP_EXPERIENCE_ID is not set")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "experience_id": experience_id,
        "title": "Test Title",
        "content": "Test Content"
    }

    print(f"POSTing to {url}")
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")


asyncio.run(run())
