"""Generate FOUR-LIFE logo via DALL-E."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import httpx


async def main():
    api_key = os.environ["OPENAI_API_KEY"]
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "dall-e-3",
                "prompt": "A minimalist logo for FOUR-LIFE, an AI agent. Design: a stylized number 4 morphing into a DNA helix or infinity loop, representing lifecycle and evolution. Colors: cyan and electric blue on dark background. Clean, modern, tech aesthetic. No text. Square format. Simple enough to work as a small icon.",
                "size": "1024x1024",
                "quality": "standard",
                "n": 1,
            },
        )
        resp.raise_for_status()
        url = resp.json()["data"][0]["url"]

        img = await client.get(url)
        out_path = "/opt/four-life/web/out/logo.png"
        with open(out_path, "wb") as f:
            f.write(img.content)
        print(f"Logo saved: {out_path}")
        print(f"Public URL: https://four-life.gudman.xyz/logo.png")


asyncio.run(main())
