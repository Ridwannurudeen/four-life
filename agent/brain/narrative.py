"""Narrative analysis — detect trends, find gaps, generate token concepts."""

import json

from loguru import logger

from agent.brain.llm import get_llm


class NarrativeEngine:
    """Analyzes trending narratives and generates token concepts."""

    async def analyze_market(self, trending_tokens: list[dict], recent_creates: list[dict]) -> dict:
        """Analyze current Four.meme market for narrative opportunities.

        Returns:
            dict with 'trending_narratives', 'saturated_themes', 'opportunity_gaps'
        """
        # Trim to essential fields to stay within token limits
        def slim(t: dict) -> dict:
            return {k: t.get(k) for k in ("name", "shortName", "tag", "hold", "progress", "volume", "cap") if t.get(k)}

        token_summary = json.dumps([slim(t) for t in trending_tokens[:10]], indent=2, default=str)
        recent_summary = json.dumps([slim(t) for t in recent_creates[:10]], indent=2, default=str)

        return await get_llm().chat_json_task([{
            "role": "user",
            "content": f"""Analyze these meme tokens currently on Four.meme (BNB Chain).

TRENDING TOKENS (top 10):
{token_summary}

RECENTLY CREATED (top 10):
{recent_summary}

Identify:
1. **trending_narratives**: Top 3-5 active narrative themes (e.g., "dog tokens", "AI agents", "political memes"). For each: name, strength (1-10), saturation level (low/medium/high).
2. **saturated_themes**: Themes with too many tokens — launching here would get lost.
3. **opportunity_gaps**: Narrative angles that are trending culturally but have NO or FEW tokens on Four.meme. These are launch opportunities.
4. **recommended_narrative**: The single best narrative to launch into right now, with reasoning.

Respond in JSON only. No markdown. Be concise."""
        }], task="narrative", max_tokens=4000)

    async def generate_concept(self, narrative: str, avoid_names: list[str] = None) -> dict:
        """Generate a complete token concept for a given narrative.

        Returns:
            dict with 'name', 'symbol', 'description', 'lore', 'personality',
            'meme_angles', 'target_communities'
        """
        avoid = json.dumps(avoid_names or [])

        return await get_llm().chat_json_task([{
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
        }], task="content", max_tokens=4000)

    async def generate_image_prompt(self, concept: dict) -> str:
        """Generate a DALL-E prompt for the token's artwork."""
        return await get_llm().chat_task([{
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
        }], task="vision", max_tokens=300)
