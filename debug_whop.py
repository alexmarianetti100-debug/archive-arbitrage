import asyncio, httpx, os

async def run():
    key = "apik_3uNGiITNSQWdc_C4536724_C_d8d48154f3e0c9f68959daf5d7be9bad3bbedb988a356b64eda104f4300958"
    url = "https://api.whop.com/api/v5/forum_posts"
    # Wait, let's also try https://api.whop.com/v5/forum_posts just in case "api/v5" is redundant
    
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "experience_id": "exp_c8acBs3P3KyJKa",
        "title": "Test Title",
        "content": "Test Content"
    }
    
    print(f"POSTing to {url}")
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")

asyncio.run(run())
