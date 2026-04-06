"""Launch timing and lifecycle strategy."""

import json
from datetime import datetime, timezone

import anthropic
from loguru import logger

from agent.config import settings
from agent.fourmeme.monitor import TokenHealth


class StrategyEngine:
    """Decides WHEN to launch and WHAT to do at each lifecycle phase."""

    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"

    async def should_launch(
        self,
        market_analysis: dict,
        active_tokens: list[TokenHealth],
        memory_context: str = "",
    ) -> dict:
        """Decide whether to launch a new token now.

        Returns:
            dict with 'should_launch' (bool), 'reason', 'optimal_delay_minutes',
            'confidence' (0-1)
        """
        active_summary = []
        for t in active_tokens:
            active_summary.append({
                "name": t.name,
                "symbol": t.symbol,
                "age_hours": round(t.age_hours, 1),
                "health_score": t.health_score,
                "phase": t.phase,
                "curve_progress": round(t.curve_progress_pct, 1),
            })

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"""You are FOUR-LIFE, an autonomous meme token agent on Four.meme (BNB Chain).
Should you launch a new token right now?

CURRENT TIME (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}
MAX CONCURRENT TOKENS: {settings.max_concurrent_tokens}

MARKET ANALYSIS:
{json.dumps(market_analysis, indent=2, default=str)}

YOUR ACTIVE TOKENS:
{json.dumps(active_summary, indent=2, default=str)}

PAST LAUNCH LEARNINGS:
{memory_context or 'No previous launches yet.'}

Consider:
- Don't launch if you already have {settings.max_concurrent_tokens} active tokens
- Don't launch if your newest token is less than {settings.min_launch_interval_hours}h old
- Launch when there's a clear narrative opportunity
- Avoid launching during low-activity hours (roughly 00:00-06:00 UTC)
- If past launches show patterns, learn from them

Respond in JSON: {{"should_launch": bool, "reason": str, "optimal_delay_minutes": int, "confidence": float}}"""
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
            return {"should_launch": False, "reason": "Failed to parse strategy", "optimal_delay_minutes": 60, "confidence": 0}

    async def get_lifecycle_action(self, health: TokenHealth, concept: dict, memory_context: str = "") -> dict:
        """Get the next action for a token based on its current phase and health.

        Returns:
            dict with 'action_type' (post_content|transparency|alert|celebrate|defend|nothing),
            'content' (the actual post/message), 'urgency' (low|medium|high), 'reasoning'
        """
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""You are FOUR-LIFE, managing the token {health.name} ({health.symbol}) on Four.meme.

TOKEN HEALTH:
- Phase: {health.phase}
- Age: {round(health.age_hours, 1)}h
- Health Score: {health.health_score}/100
- Graduation Probability: {round(health.graduation_probability * 100, 1)}%
- Unique Buyers: {health.unique_buyers}
- Buy/Sell Ratio: {round(health.buy_sell_ratio, 2)}
- Top Holder: {round(health.top_holder_pct, 1)}% of supply
- Whale Count: {health.whale_count}
- Bonding Curve: {round(health.curve_progress_pct, 1)}%
- Holder Velocity: {round(health.holder_velocity, 1)} new holders/hour

TOKEN CONCEPT:
{json.dumps(concept, indent=2, default=str)}

PAST LEARNINGS:
{memory_context or 'No past data.'}

PHASE GUIDELINES:
- nurture (0-6h): Build initial community. Post memes, engage, celebrate milestones.
- defend (6-24h): Watch for sell pressure, whale dumps. Post transparency if needed.
- accelerate (24-72h): Push toward graduation. Time content for peak hours. Build narrative arcs.

What should FOUR-LIFE do RIGHT NOW? Choose one action:
- post_content: Generate a meme/update/celebration post for Twitter
- transparency: Post holder distribution or liquidity data (when whales concentrate)
- celebrate: Milestone reached (holder count, curve progress)
- defend: Counter FUD or address concerning metrics
- alert: Something urgent needs attention
- nothing: No action needed right now

Respond in JSON: {{"action_type": str, "content": str, "urgency": str, "reasoning": str}}

The content should be in the token's personality voice. Max 280 chars for Twitter.
Make it genuinely engaging — not corporate, not cringe."""
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
            return {"action_type": "nothing", "content": "", "urgency": "low", "reasoning": "Parse failed"}
