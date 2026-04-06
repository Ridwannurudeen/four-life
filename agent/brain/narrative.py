"""Narrative analysis — detect trends, find gaps, generate token concepts."""

import json
from datetime import datetime

import anthropic
from loguru import logger

from agent.config import settings


class NarrativeEngine:
    """Analyzes trending narratives and generates token concepts."""

    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"

    async def analyze_market(self, trending_tokens: list[dict], recent_creates: list[dict]) -> dict:
        """Analyze current Four.meme market for narrative opportunities.

        Returns:
            dict with 'trending_narratives', 'saturated_themes', 'opportunity_gaps'
        """
        token_summary = json.dumps(trending_tokens[:20], indent=2, default=str)
        recent_summary = json.dumps(recent_creates[:30], indent=2, default=str)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": f"""Analyze these meme tokens currently on Four.meme (BNB Chain).

TRENDING TOKENS:
{token_summary}

RECENTLY CREATED:
{recent_summary}

Identify:
1. **trending_narratives**: Top 3-5 active narrative themes (e.g., "dog tokens", "AI agents", "political memes"). For each: name, strength (1-10), saturation level (low/medium/high).
2. **saturated_themes**: Themes with too many tokens — launching here would get lost.
3. **opportunity_gaps**: Narrative angles that are trending culturally but have NO or FEW tokens on Four.meme. These are launch opportunities.
4. **recommended_narrative**: The single best narrative to launch into right now, with reasoning.

Respond in JSON only. No markdown."""
            }],
        )

        try:
            return json.loads(response.content[0].text)
        except json.JSONDecodeError:
            text = response.content[0].text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            raise

    async def generate_concept(self, narrative: str, avoid_names: list[str] = None) -> dict:
        """Generate a complete token concept for a given narrative.

        Returns:
            dict with 'name', 'symbol', 'description', 'lore', 'personality',
            'meme_angles', 'target_communities'
        """
        avoid = json.dumps(avoid_names or [])

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": f"""Create a meme token concept for Four.meme (BNB Chain launchpad).

NARRATIVE TO TARGET: {narrative}
AVOID THESE NAMES (already taken): {avoid}

Generate:
1. **name**: Catchy, memeable token name (max 20 chars)
2. **symbol**: Ticker (3-6 chars, all caps)
3. **description**: Token description for Four.meme listing (max 200 chars). Must be funny, sharp, and immediately understandable.
4. **lore**: Origin story / backstory (3-5 sentences). Should be absurd enough to meme but coherent enough to build on.
5. **personality**: The token's "voice" for community content. Describe the tone, humor style, and character in 2 sentences.
6. **meme_angles**: 5 specific meme ideas/formats that would work for this token.
7. **target_communities**: 3 specific communities (Twitter accounts, Telegram groups, subreddits) where this token would resonate.
8. **launch_hook**: One-sentence viral hook for the launch tweet.

Make it GENUINELY funny — not corporate, not generic. Think 4chan humor meets crypto Twitter.

Respond in JSON only. No markdown."""
            }],
        )

        try:
            return json.loads(response.content[0].text)
        except json.JSONDecodeError:
            text = response.content[0].text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            raise

    async def generate_image_prompt(self, concept: dict) -> str:
        """Generate a DALL-E prompt for the token's artwork."""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": f"""Create a DALL-E image prompt for a meme token logo.

Token: {concept['name']} ({concept['symbol']})
Lore: {concept['lore']}

Requirements:
- Square format, simple background (solid color or gradient)
- Cartoon/meme art style
- Central character or mascot
- Bold, readable at small sizes
- Funny and memorable
- NO text in the image

Return ONLY the prompt, nothing else."""
            }],
        )
        return response.content[0].text.strip()
