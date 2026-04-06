"""FOUR-LIFE main agent — the autonomous loop: THINK → BIRTH → RAISE → LEARN."""

import asyncio
import time
import json
from pathlib import Path

from loguru import logger

from agent.config import settings
from agent.fourmeme.api import FourMemeAPI
from agent.fourmeme.chain import FourMemeChain
from agent.fourmeme.monitor import TokenMonitor
from agent.brain.narrative import NarrativeEngine
from agent.brain.strategy import StrategyEngine
from agent.brain.content import ContentEngine
from agent.memory.store import MemoryStore, LaunchRecord
from agent.identity.registry import AgentIdentity
from agent.social.twitter import TwitterClient
from agent.lifecycle.engine import LifecycleEngine


class FourLifeAgent:
    """Autonomous meme token lifecycle agent on Four.meme."""

    TICK_INTERVAL = 120  # seconds between lifecycle ticks
    THINK_INTERVAL = 1800  # seconds between launch opportunity checks

    def __init__(self) -> None:
        # Core services
        self.api = FourMemeAPI()
        self.chain = FourMemeChain()
        self.monitor = TokenMonitor(self.chain)
        self.narrative = NarrativeEngine()
        self.strategy = StrategyEngine()
        self.content_engine = ContentEngine()
        self.memory = MemoryStore()
        self.identity = AgentIdentity()
        self.twitter = TwitterClient()
        self.lifecycle = LifecycleEngine(
            self.monitor, self.strategy, self.content_engine, self.memory, self.twitter
        )

        # State
        self.active_concepts: dict[str, dict] = {}  # token_address -> concept
        self.running = False

    async def initialize(self) -> None:
        """Boot sequence — authenticate and register identity."""
        logger.info("=" * 60)
        logger.info("FOUR-LIFE v1.0.0 — Autonomous Meme Token Lifecycle Agent")
        logger.info("=" * 60)

        # Authenticate with Four.meme
        await self.api.login()
        logger.info("Four.meme authenticated")

        # Check/register ERC-8004 identity
        agent_id = await self.identity.get_agent_id()
        if agent_id:
            logger.info("ERC-8004 Agent ID: {}", agent_id)
        else:
            logger.info("No ERC-8004 identity found — will register on first launch")

        # Load existing memory
        context = self.memory.get_context_for_ai()
        if self.memory.memory.total_launches > 0:
            logger.info("Memory loaded:\n{}", context)
        else:
            logger.info("Fresh start — no previous launches")

        logger.info("Initialization complete. Agent is live.")

    # ── THINK Phase ───────────────────────────────────────────────────

    async def think(self) -> dict | None:
        """Analyze market and decide whether to launch.

        Returns:
            Token concept dict if launching, None otherwise.
        """
        logger.info("[THINK] Analyzing market...")

        # Get current Four.meme landscape
        trending = await self.api.get_trending()
        current_block = await self.chain.get_block_number()
        recent_creates = await self.chain.get_recent_creates(
            from_block=current_block - 2000  # ~15 minutes of blocks
        )

        # Analyze narratives
        market_analysis = await self.narrative.analyze_market(trending, recent_creates)
        logger.info("[THINK] Market analysis: {}", json.dumps(market_analysis.get("recommended_narrative", ""), default=str))

        # Get health of active tokens
        active_health = await self.monitor.get_all_health()

        # Ask strategy engine
        memory_ctx = self.memory.get_context_for_ai()
        decision = await self.strategy.should_launch(
            market_analysis, active_health, memory_ctx
        )

        if not decision.get("should_launch"):
            logger.info("[THINK] Not launching: {}", decision.get("reason", ""))
            delay = decision.get("optimal_delay_minutes", 30)
            logger.info("[THINK] Will re-evaluate in {} minutes", delay)
            return None

        logger.info("[THINK] LAUNCH DECISION: {} (confidence: {})",
                     decision.get("reason"), decision.get("confidence"))

        # Generate concept
        narrative = market_analysis.get("recommended_narrative", {})
        narrative_name = narrative.get("name", "trending meme") if isinstance(narrative, dict) else str(narrative)

        existing_names = [lr.name for lr in self.memory.memory.launches]
        concept = await self.narrative.generate_concept(narrative_name, existing_names)
        concept["narrative"] = narrative_name

        logger.info("[THINK] Concept: {} ({}) — {}",
                     concept["name"], concept["symbol"], concept["description"])

        return concept

    # ── BIRTH Phase ───────────────────────────────────────────────────

    async def birth(self, concept: dict) -> str | None:
        """Launch a token on Four.meme.

        Returns:
            Token address if successful, None otherwise.
        """
        logger.info("[BIRTH] Launching {} ({})...", concept["name"], concept["symbol"])

        try:
            # Generate artwork
            image_prompt = await self.narrative.generate_image_prompt(concept)
            logger.info("[BIRTH] Generating artwork...")
            image_bytes = await self.content_engine.generate_image(image_prompt)

            # Upload to Four.meme
            image_url = await self.api.upload_image(image_bytes)

            # Prepare token
            prep = await self.api.prepare_token(
                name=concept["name"],
                symbol=concept["symbol"],
                description=concept["description"],
                image_url=image_url,
            )

            # Create on-chain
            tx_hash = await self.chain.create_token(
                create_arg=prep["create_arg"],
                signature=prep["signature"],
                dev_buy_bnb=0.01,  # Small dev buy for sniper protection
            )

            # Find the token address from events
            current_block = await self.chain.get_block_number()
            creates = await self.chain.get_recent_creates(
                from_block=current_block - 10
            )

            token_address = None
            for create in creates:
                if create["name"] == concept["name"]:
                    token_address = create["token"]
                    break

            if not token_address:
                logger.error("[BIRTH] Could not find token address from events")
                return None

            logger.info("[BIRTH] Token live at {}", token_address)

            # Start tracking
            await self.monitor.track_token(
                token_address,
                name=concept["name"],
                symbol=concept["symbol"],
                creator=self.chain.account.address,
                created_block=current_block,
            )

            # Record in memory
            self.memory.record_launch(LaunchRecord(
                token_address=token_address,
                name=concept["name"],
                symbol=concept["symbol"],
                narrative=concept.get("narrative", ""),
                concept=concept,
                launched_at=time.time(),
                launch_block=current_block,
                market_conditions={},
            ))

            # Store concept for lifecycle engine
            self.active_concepts[token_address] = concept

            # Post launch thread to Twitter
            thread = await self.content_engine.generate_launch_thread(concept)
            thread_ids = self.twitter.post_thread(thread)
            logger.info("[BIRTH] Launch thread posted: {} tweets", len(thread_ids))

            return token_address

        except Exception as e:
            logger.error("[BIRTH] Launch failed: {}", e)
            self.memory.add_learning(f"Launch of {concept['name']} failed: {str(e)}")
            return None

    # ── RAISE Phase ───────────────────────────────────────────────────

    async def raise_tokens(self) -> None:
        """Run lifecycle ticks for all active tokens."""
        for token_address, concept in list(self.active_concepts.items()):
            try:
                action = await self.lifecycle.tick(token_address, concept)
                if action:
                    logger.debug("[RAISE] Action: {} for {}", action.action_type, concept["symbol"])
            except Exception as e:
                logger.error("[RAISE] Error managing {}: {}", concept["symbol"], e)

    # ── LEARN Phase ───────────────────────────────────────────────────

    async def learn(self) -> None:
        """Analyze completed launches and extract learnings."""
        for launch in self.memory.memory.launches:
            # Check if launch is old enough to evaluate (72h+)
            if launch.launched_at > time.time() - 72 * 3600:
                continue
            if launch.what_worked or launch.what_failed:
                continue  # Already evaluated

            # Evaluate the launch
            if launch.graduated:
                launch.what_worked.append(f"Narrative '{launch.narrative}' led to graduation")
                launch.what_worked.append(f"Peak {launch.peak_holders} holders")
                self.memory.add_learning(
                    f"Narrative '{launch.narrative}' graduated with {launch.peak_holders} peak holders"
                )
            else:
                launch.what_failed.append(
                    f"Failed to graduate: peak {launch.peak_curve_progress:.1f}% curve, "
                    f"{launch.peak_holders} holders"
                )
                self.memory.add_learning(
                    f"Narrative '{launch.narrative}' failed: "
                    f"{launch.peak_curve_progress:.1f}% curve, {launch.peak_holders} holders"
                )

            self.memory.save()

        # Sync to Unibase
        await self.memory.sync_to_unibase()

    # ── Main Loop ─────────────────────────────────────────────────────

    async def run(self) -> None:
        """Main agent loop."""
        await self.initialize()
        self.running = True

        last_think = 0
        last_learn = 0

        logger.info("Entering main loop...")

        while self.running:
            try:
                now = time.time()

                # THINK — check for launch opportunities
                if now - last_think >= self.THINK_INTERVAL:
                    concept = await self.think()
                    if concept:
                        token_address = await self.birth(concept)
                        if token_address:
                            logger.info("Successfully launched {} at {}",
                                         concept["symbol"], token_address)
                    last_think = now

                # RAISE — manage active tokens
                await self.raise_tokens()

                # LEARN — periodic reflection
                if now - last_learn >= 3600:  # Every hour
                    await self.learn()
                    last_learn = now

                # Wait before next tick
                await asyncio.sleep(self.TICK_INTERVAL)

            except KeyboardInterrupt:
                logger.info("Shutting down...")
                self.running = False
            except Exception as e:
                logger.error("Main loop error: {}", e)
                await asyncio.sleep(30)

        # Cleanup
        await self.api.close()
        self.memory.save()
        logger.info("Agent stopped. Memory saved.")

    async def stop(self) -> None:
        self.running = False
