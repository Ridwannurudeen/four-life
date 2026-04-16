"""Lifecycle engine — manages tokens through nurture → defend → accelerate → graduated."""

import asyncio
import time
from dataclasses import dataclass

from loguru import logger

from agent.fourmeme.monitor import TokenMonitor, TokenHealth
from agent.brain.strategy import StrategyEngine
from agent.brain.content import ContentEngine
from agent.memory.store import MemoryStore
from agent.social.twitter import TwitterClient
from agent.myx.hedge import HedgeManager
from agent.identity.registry import AgentIdentity


@dataclass
class LifecycleAction:
    """An action taken by the lifecycle engine."""

    token_address: str
    action_type: str  # post_content | transparency | celebrate | defend | alert | nothing
    content: str
    urgency: str
    reasoning: str
    timestamp: float
    tweet_id: str | None = None


class LifecycleEngine:
    """Manages the post-launch lifecycle of tokens."""

    # Minimum intervals between actions per phase (seconds)
    PHASE_INTERVALS = {
        "nurture": 30 * 60,     # Every 30 min
        "defend": 45 * 60,      # Every 45 min
        "accelerate": 60 * 60,  # Every hour
        "graduated": 4 * 3600,  # Every 4 hours
    }

    # Milestones to celebrate
    HOLDER_MILESTONES = [50, 100, 250, 500, 1000, 2500, 5000]
    CURVE_MILESTONES = [25, 50, 75, 90, 100]

    def __init__(
        self,
        monitor: TokenMonitor,
        strategy: StrategyEngine,
        content: ContentEngine,
        memory: MemoryStore,
        twitter: TwitterClient,
        hedge_manager: HedgeManager | None = None,
        identity: AgentIdentity | None = None,
    ) -> None:
        self.monitor = monitor
        self.strategy = strategy
        self.content = content
        self.memory = memory
        self.twitter = twitter
        self.hedge_manager = hedge_manager
        self.identity = identity
        self.action_log: list[LifecycleAction] = []
        self._last_action_time: dict[str, float] = {}
        self._celebrated_milestones: dict[str, set] = {}

    async def tick(self, token_address: str, concept: dict) -> LifecycleAction | None:
        """Run one lifecycle tick for a token. Returns action taken, or None."""
        # Update health
        health = await self.monitor.update_token(token_address)

        # Run MYX hedge evaluation (independent of content actions)
        if self.hedge_manager:
            try:
                token_health = {
                    "name": health.name,
                    "symbol": health.symbol,
                    "health_score": health.health_score,
                    "phase": health.phase,
                    "buy_sell_ratio": health.buy_sell_ratio,
                    "holder_velocity": health.holder_velocity,
                    "curve_progress": health.curve_progress_pct,
                    "top_holder_pct": health.top_holder_pct,
                }
                hedge_result = await self.hedge_manager.evaluate_and_act(
                    token_address, token_health, health.phase,
                )
                if hedge_result and hedge_result.get("action") not in ("hold", "monitor"):
                    logger.info("[HEDGE] {} for {}: {}", hedge_result["action"], health.symbol, hedge_result)
            except Exception as e:
                logger.error("[HEDGE] Error for {}: {}", health.symbol, e)

        # Check if we should act (rate limiting per phase)
        interval = self.PHASE_INTERVALS.get(health.phase, 3600)
        last_action = self._last_action_time.get(token_address, 0)
        if time.time() - last_action < interval:
            return None

        # Check for milestones first
        milestone = self._check_milestones(token_address, health)

        # Update memory with peak metrics
        self.memory.update_launch(
            token_address,
            peak_holders=max(
                health.unique_buyers,
                self.memory.get_launch(token_address).peak_holders
                if self.memory.get_launch(token_address) else 0,
            ),
            peak_health_score=max(
                health.health_score,
                self.memory.get_launch(token_address).peak_health_score
                if self.memory.get_launch(token_address) else 0,
            ),
            peak_curve_progress=max(
                health.curve_progress_pct,
                self.memory.get_launch(token_address).peak_curve_progress
                if self.memory.get_launch(token_address) else 0,
            ),
            total_buys=health.total_buys,
            total_sells=health.total_sells,
        )

        # Check graduation
        if health.curve_progress_pct >= 100 and not (
            self.memory.get_launch(token_address)
            and self.memory.get_launch(token_address).graduated
        ):
            grad_time = time.time()
            self.memory.update_launch(
                token_address,
                graduated=True,
                graduation_time=grad_time,
            )
            milestone = "GRADUATED to PancakeSwap"
            logger.info("{} ({}) GRADUATED!", health.name, health.symbol)

            # Submit ERC-8004 reputation attestation. Failures must not crash the tick.
            if self.identity is not None:
                launch = self.memory.get_launch(token_address)
                try:
                    record = await self.identity.attest_graduation(
                        token_address,
                        metadata={
                            "symbol": health.symbol,
                            "name": health.name,
                            "quote_asset": health.quote_asset,
                            "graduation_time": grad_time,
                            "peak_holders": launch.peak_holders if launch else health.unique_buyers,
                        },
                    )
                    if record and record.tx_hash:
                        self.memory.update_launch(
                            token_address,
                            attestation_tx_hash=record.tx_hash,
                            attestation_block=record.block_number,
                        )
                except Exception as e:
                    logger.error("[ATTEST] Unexpected error for {}: {}", health.symbol, e)

        # Decide action based on health + phase
        if milestone:
            # Force a celebration post for milestones
            post = await self.content.generate_update_post(health, concept, milestone)
            action = LifecycleAction(
                token_address=token_address,
                action_type="celebrate",
                content=post,
                urgency="medium",
                reasoning=f"Milestone: {milestone}",
                timestamp=time.time(),
            )
        elif health.top_holder_pct > 30 and health.phase in ("defend", "accelerate"):
            # Force transparency post when whale concentration is dangerous
            post = await self.content.generate_transparency_post(health, concept)
            action = LifecycleAction(
                token_address=token_address,
                action_type="transparency",
                content=post,
                urgency="high",
                reasoning=f"Whale concentration at {health.top_holder_pct:.1f}%",
                timestamp=time.time(),
            )
        else:
            # Ask strategy engine for the best action
            memory_ctx = self.memory.get_context_for_ai()
            decision = await self.strategy.get_lifecycle_action(
                health, concept, memory_ctx
            )

            if decision["action_type"] == "nothing":
                return None

            action = LifecycleAction(
                token_address=token_address,
                action_type=decision["action_type"],
                content=decision["content"],
                urgency=decision["urgency"],
                reasoning=decision["reasoning"],
                timestamp=time.time(),
            )

        # Execute the action (post to Twitter)
        if action.content:
            tweet_id = self.twitter.post_tweet(action.content)
            action.tweet_id = tweet_id

        # Record
        self.action_log.append(action)
        self._last_action_time[token_address] = time.time()
        logger.info(
            "[{}] {} action for {} ({}): {}",
            health.phase.upper(),
            action.action_type,
            health.name,
            health.symbol,
            action.content[:100],
        )

        return action

    def _check_milestones(self, token_address: str, health: TokenHealth) -> str | None:
        """Check if any milestones have been reached."""
        if token_address not in self._celebrated_milestones:
            self._celebrated_milestones[token_address] = set()

        celebrated = self._celebrated_milestones[token_address]

        for milestone in self.HOLDER_MILESTONES:
            key = f"holders_{milestone}"
            if health.unique_buyers >= milestone and key not in celebrated:
                celebrated.add(key)
                return f"{milestone} holders"

        for milestone in self.CURVE_MILESTONES:
            key = f"curve_{milestone}"
            if health.curve_progress_pct >= milestone and key not in celebrated:
                celebrated.add(key)
                return f"{milestone}% bonding curve"

        return None

    def get_action_history(self, token_address: str, limit: int = 20) -> list[dict]:
        """Get recent actions for a token."""
        actions = [a for a in self.action_log if a.token_address == token_address]
        return [
            {
                "action_type": a.action_type,
                "content": a.content,
                "urgency": a.urgency,
                "reasoning": a.reasoning,
                "timestamp": a.timestamp,
                "tweet_id": a.tweet_id,
            }
            for a in actions[-limit:]
        ]
