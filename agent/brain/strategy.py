"""Launch timing and lifecycle strategy."""

import json
from datetime import datetime, timezone

from loguru import logger

from agent.config import settings
from agent.brain.llm import get_llm
from agent.brain.consensus import consensus_vote, DEFAULT_CONSENSUS_MODELS
from agent.fourmeme.monitor import TokenHealth


class StrategyEngine:
    """Decides WHEN to launch and WHAT to do at each lifecycle phase."""

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

        return await get_llm().chat_json_task([{
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
        }], task="risk")

    async def get_lifecycle_action(self, health: TokenHealth, concept: dict, memory_context: str = "") -> dict:
        """Get the next action for a token based on its current phase and health.

        Returns:
            dict with 'action_type' (post_content|transparency|alert|celebrate|defend|nothing),
            'content' (the actual post/message), 'urgency' (low|medium|high), 'reasoning'
        """
        prompt = self._lifecycle_prompt(health, concept, memory_context)
        return await get_llm().chat_json_task([{"role": "user", "content": prompt}], task="risk")

    async def get_defend_action_consensus(
        self,
        health: TokenHealth,
        concept: dict,
        memory_context: str = "",
    ) -> dict:
        """Consensus path for DEFEND phase — the highest-stakes agent decision.

        Runs the lifecycle prompt across multiple DGrid models in parallel and
        votes on the action. This is only possible because DGrid gives us one
        API and one auth for every model. Returns the same shape as
        get_lifecycle_action, with a ``consensus`` field describing the vote.

        If the vote is inconclusive (no model succeeded) we fall back to a
        deterministic "nothing" decision so the lifecycle keeps moving.
        """
        prompt = self._lifecycle_prompt(health, concept, memory_context)
        messages = [{"role": "user", "content": prompt}]
        result = await consensus_vote(
            messages,
            models=DEFAULT_CONSENSUS_MODELS,
            vote_key="action_type",
            max_tokens=600,
            temperature=0.4,
            json_mode=True,
        )

        # Pick the full response from whichever succeeding model's verdict
        # matched the final one — preserves content/urgency/reasoning fields.
        verdict = result.get("final_verdict")
        chosen_response: dict | None = None
        if verdict is not None:
            for r in result.get("results", []):
                if r.get("ok") and str(r.get("verdict")) == str(verdict):
                    full = r.get("full_response") or {}
                    if isinstance(full, dict) and full.get("action_type"):
                        chosen_response = full
                        break

        if chosen_response is None:
            # Graceful degradation — no model answered usably. Don't post.
            chosen_response = {
                "action_type": "nothing",
                "content": "",
                "urgency": "low",
                "reasoning": "consensus inconclusive — deferring to next tick",
            }

        chosen_response["consensus"] = {
            "models_queried": result.get("models_queried"),
            "models_succeeded": result.get("models_succeeded"),
            "confidence": result.get("confidence"),
            "tally": result.get("tally"),
            "method": result.get("method"),
        }
        return chosen_response

    @staticmethod
    def _lifecycle_prompt(health: TokenHealth, concept: dict, memory_context: str) -> str:
        """Shared prompt body for the lifecycle action — used by both single-model
        and consensus paths so the two always see the same context."""
        return f"""You are FOUR-LIFE, managing the token {health.name} ({health.symbol}) on Four.meme.

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
