"""Content generation — memes, threads, community posts."""

import json

import httpx
from loguru import logger

from agent.config import settings
from agent.brain.llm import get_llm
from agent.fourmeme.monitor import TokenHealth


class ContentEngine:
    """Generates token artwork and social content."""

    async def generate_image(self, prompt: str) -> bytes:
        """Generate token artwork via OpenAI DALL-E 3."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": "dall-e-3",
                    "prompt": prompt,
                    "size": "1024x1024",
                    "quality": "standard",
                    "n": 1,
                },
            )
            resp.raise_for_status()
            image_url = resp.json()["data"][0]["url"]

            img_resp = await client.get(image_url)
            img_resp.raise_for_status()
            return img_resp.content

    async def generate_launch_thread(self, concept: dict) -> list[str]:
        """Generate a Twitter launch thread (3-5 tweets)."""
        llm = get_llm()
        text = await llm.chat([{
            "role": "user",
            "content": f"""Write a launch announcement thread for a new meme token on Four.meme (BNB Chain).

TOKEN:
- Name: {concept['name']}
- Symbol: ${concept['symbol']}
- Description: {concept['description']}
- Lore: {concept['lore']}
- Personality: {concept['personality']}
- Launch Hook: {concept.get('launch_hook', '')}

Write 3-4 tweets as a thread. Rules:
- Tweet 1: The hook — grab attention immediately. Use the launch_hook or improve it.
- Tweet 2: The lore/story — make people curious
- Tweet 3: The CTA — link to Four.meme, tell people to check it out
- Each tweet max 280 chars
- Voice: match the token's personality
- NO emojis. NO hashtags except $SYMBOL.
- Sound like a degenerate crypto trader, not a marketing team

Return as JSON array of strings. No markdown."""
        }], max_tokens=1500)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            return [text.strip()]

    async def generate_update_post(
        self, health: TokenHealth, concept: dict, milestone: str = ""
    ) -> str:
        """Generate a single update/milestone/meme tweet."""
        return await get_llm().chat([{
            "role": "user",
            "content": f"""Write a tweet for ${concept['symbol']} ({concept['name']}) on Four.meme.

CONTEXT:
- Token age: {round(health.age_hours, 1)} hours
- Holders: {health.unique_buyers}
- Bonding curve: {round(health.curve_progress_pct, 1)}%
- Health score: {health.health_score}/100
- Phase: {health.phase}
- Milestone (if any): {milestone}

TOKEN PERSONALITY: {concept.get('personality', 'Degen crypto energy')}

Write ONE tweet (max 280 chars). Match the token's voice.
If there's a milestone, celebrate it. If health is dropping, rally the community.
NO emojis. Be raw and real, not corporate.

Return ONLY the tweet text, nothing else."""
        }], max_tokens=400)

    async def generate_transparency_post(self, health: TokenHealth, concept: dict) -> str:
        """Generate a transparency update when whale concentration is high."""
        return await get_llm().chat([{
            "role": "user",
            "content": f"""Write a transparency tweet for ${concept['symbol']} ({concept['name']}).

The top holder owns {round(health.top_holder_pct, 1)}% of supply.
There are {health.whale_count} wallets with >5% supply.
Holders: {health.unique_buyers}
Buy/sell ratio: {round(health.buy_sell_ratio, 2)}

This is an HONEST transparency post from the token's AI agent (FOUR-LIFE).
Acknowledge the concentration, explain why it's not a rug, show the data.
Be direct. No sugar-coating. Trust is earned through transparency.

Max 280 chars. No emojis. Return ONLY the tweet text."""
        }], max_tokens=400)
