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
from agent.fourmeme.graduation import get_registry as get_graduation_registry
from agent.brain.narrative import NarrativeEngine
from agent.brain.strategy import StrategyEngine
from agent.brain.content import ContentEngine
from agent.memory.store import MemoryStore, LaunchRecord
from agent.identity.registry import AgentIdentity
from agent.social.twitter import TwitterClient
from agent.lifecycle.engine import LifecycleEngine
from agent.myx.client import MYXClient, MYXStrategy
from agent.myx.hedge import HedgeManager


class FourLifeAgent:
    """Autonomous meme token lifecycle agent on Four.meme."""

    TICK_INTERVAL = 120  # seconds between lifecycle ticks
    THINK_INTERVAL = 1800  # seconds between launch opportunity checks

    def __init__(self) -> None:
        # Core services
        self.api = FourMemeAPI()
        self.chain = FourMemeChain()
        self.graduation_registry = get_graduation_registry()
        self.monitor = TokenMonitor(self.chain, graduation_registry=self.graduation_registry)
        self.narrative = NarrativeEngine()
        self.strategy = StrategyEngine()
        self.content_engine = ContentEngine()
        self.memory = MemoryStore()
        self.identity = AgentIdentity()
        self.twitter = TwitterClient()

        # MYX V2 perp integration. Signal-only mode needs the Pool (for on-chain
        # pair resolution + position reads). Router is only required when
        # MYX_EXECUTION_ENABLED=true — if execution is on without a router
        # address, fall back to signal-only rather than crashing.
        execution_enabled = (
            settings.myx_execution_enabled and bool(settings.myx_router_address)
        )
        if settings.myx_pool_address or settings.myx_router_address:
            self.myx = MYXClient(
                router_address=settings.myx_router_address,
                pool_address=settings.myx_pool_address,
            )
            self.myx_strategy = MYXStrategy(self.myx)
            self.hedge_manager = HedgeManager(
                self.myx, self.myx_strategy,
                execution_enabled=execution_enabled,
            )
        else:
            self.myx = None
            self.myx_strategy = None
            self.hedge_manager = None

        self.lifecycle = LifecycleEngine(
            self.monitor, self.strategy, self.content_engine, self.memory, self.twitter,
            hedge_manager=self.hedge_manager,
            identity=self.identity,
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

        # Warm up graduation registry from Four.meme's live config
        try:
            await self.graduation_registry.refresh()
        except Exception as e:
            logger.warning("Graduation registry warm-up failed (will retry on demand): {}", e)

        # Check/register ERC-8004 identity — idempotent, persists to data/identity.json.
        await self.identity.ensure_registered()

        # Load existing memory
        context = self.memory.get_context_for_ai()
        if self.memory.memory.total_launches > 0:
            logger.info("Memory loaded:\n{}", context)
        else:
            logger.info("Fresh start — no previous launches")

        # Restore tracked tokens from memory so a service restart doesn't
        # drop the agent's working set. We re-track every launch that is
        # (a) not yet graduated and (b) launched within the last 14 days —
        # older tokens either graduated already or went dormant.
        try:
            await self._restore_tracked_tokens()
        except Exception as e:
            logger.warning("Token restore skipped: {}", e)

        logger.info("Initialization complete. Agent is live.")

    # Public BSC RPCs cap eth_getLogs at 50k blocks per request. A token whose
    # launch block is older than that can't be scanned in one call — rather
    # than chunk the request (production problem, not hackathon-relevant),
    # we skip ancient launches on restore. Any token tracked in the last
    # ~50k blocks (~1.5 days of BSC) resumes cleanly.
    RESTORE_MAX_BLOCK_LAG = 45_000

    async def _restore_tracked_tokens(self) -> None:
        """Re-track every non-graduated recent launch from memory.

        Filters out (a) ancient launches whose on-chain range exceeds the
        50k-block getLogs cap and (b) launches from outdated Agentic Mode
        attempts that never produced a real token address.
        """
        cutoff_time = time.time() - 14 * 86400
        current_block = await self.chain.get_block_number()
        min_block = current_block - self.RESTORE_MAX_BLOCK_LAG
        restored = 0
        for launch in self.memory.memory.launches:
            if launch.graduated:
                continue
            if launch.launched_at and launch.launched_at < cutoff_time:
                continue
            if not launch.token_address:
                continue
            if launch.launch_block and launch.launch_block < min_block:
                continue
            if launch.token_address in self.monitor.state.tokens:
                continue
            try:
                created_block = launch.launch_block or current_block
                await self.monitor.track_token(
                    launch.token_address,
                    name=launch.name,
                    symbol=launch.symbol,
                    creator=launch.creator or self.chain.account.address,
                    created_block=created_block,
                    quote_asset=(launch.quote_asset or "BNB").upper(),
                )
                self.active_concepts[launch.token_address] = launch.concept or {
                    "name": launch.name,
                    "symbol": launch.symbol,
                    "narrative": launch.narrative or "",
                }
                restored += 1
            except Exception as e:
                logger.debug("Restore skipped for {}: {}", launch.token_address, e)
        if restored:
            logger.info("Restored {} tracked tokens from memory.", restored)

    # ── THINK Phase ───────────────────────────────────────────────────

    async def think(self) -> dict | None:
        """Analyze market and decide whether to launch.

        Returns:
            Token concept dict if launching, None otherwise.
        """
        logger.info("[THINK] Analyzing market...")

        # Get current Four.meme landscape via API (avoids RPC rate limits)
        trending = await self.api.get_trending()
        try:
            recent_creates = await self.api.get_new_tokens()
        except Exception:
            recent_creates = []

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

            # Save image to temp file for the reference script
            import tempfile
            img_path = tempfile.mktemp(suffix=".png")
            with open(img_path, "wb") as f:
                f.write(image_bytes)

            # Determine label
            valid_labels = ["Meme", "AI", "Defi", "Games", "Infra", "De-Sci", "Social", "Depin", "Charity", "Others"]
            label = concept.get("narrative", "AI")
            if label not in valid_labels:
                label = "AI"

            # Use the reference create-token-instant.ts script (proven working)
            # It handles: auth → upload → API create → on-chain tx in one shot
            import subprocess
            import os

            env = {
                **os.environ,
                "PRIVATE_KEY": settings.private_key,
                "BSC_RPC_URL": settings.bsc_rpc_url,
            }

            cmd = [
                "npx", "tsx", "scripts/create-token-instant.ts",
                f"--image={img_path}",
                f"--name={concept['name']}",
                f"--short-name={concept['symbol']}",
                f"--desc={concept['description'][:200]}",
                f"--label={label}",
            ]
            logger.info("[BIRTH] Running create-token-instant...")

            # Async subprocess so a 120s launch doesn't freeze the event loop —
            # the API worker keeps serving requests while the child runs.
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=str(Path(__file__).parent.parent),
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=120
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise RuntimeError("create-token-instant timed out after 120s")

            class _R:
                pass
            result = _R()
            result.returncode = proc.returncode or 0
            result.stdout = stdout_b.decode("utf-8", errors="replace")
            result.stderr = stderr_b.decode("utf-8", errors="replace")

            # Clean up temp image
            try:
                os.unlink(img_path)
            except OSError:
                pass

            if result.returncode != 0:
                logger.error("[BIRTH] Script failed: {}", result.stderr[:500])
                raise RuntimeError(f"create-token-instant failed: {result.stderr[:200]}")

            # Parse output — {"txHash": "0x..."}
            import json as json_mod
            output = json_mod.loads(result.stdout.strip())
            tx_hash = output["txHash"]
            logger.info("[BIRTH] Token created! tx: {}", tx_hash)

            # Wait for tx confirmation then get receipt
            receipt = await self.chain.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            token_address = None
            for log in receipt["logs"]:
                # Look for OwnershipTransferred from 0x0 — first log of new token
                if len(log["topics"]) >= 3 and log["topics"][0].hex().startswith("8be0079c"):
                    token_address = log["address"]
                    break

            if not token_address:
                # Fallback: first log address that isn't TokenManager
                for log in receipt["logs"]:
                    if log["address"].lower() != "0x5c952063c7fc8610ffdb798152d69f0b9550762b":
                        token_address = log["address"]
                        break

            if not token_address:
                logger.error("[BIRTH] Could not find token address from receipt")
                return None

            logger.info("[BIRTH] Token live at {}", token_address)

            # Get block number for tracking
            created_block = receipt["blockNumber"]

            # Start tracking
            await self.monitor.track_token(
                token_address,
                name=concept["name"],
                symbol=concept["symbol"],
                creator=self.chain.account.address,
                created_block=created_block,
            )

            # Record in memory
            self.memory.record_launch(LaunchRecord(
                token_address=token_address,
                name=concept["name"],
                symbol=concept["symbol"],
                narrative=concept.get("narrative", ""),
                concept=concept,
                launched_at=time.time(),
                launch_block=created_block,
                creator=self.chain.account.address,
                quote_asset="BNB",
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

    # Small gap between per-token lifecycle ticks so the BSC RPC doesn't see
    # a 10-request burst on every loop iteration (public nodes throttle at
    # ~10 rps and will return -32005 "limit exceeded" under that pattern).
    # 200 ms spread keeps throughput reasonable while staying well under any
    # reasonable provider's burst window.
    RAISE_INTER_TICK_DELAY = 0.2

    async def raise_tokens(self) -> None:
        """Run lifecycle ticks for all active tokens."""
        items = list(self.active_concepts.items())
        for i, (token_address, concept) in enumerate(items):
            try:
                action = await self.lifecycle.tick(token_address, concept)
                if action:
                    logger.debug("[RAISE] Action: {} for {}", action.action_type, concept["symbol"])
            except Exception as e:
                logger.error("[RAISE] Error managing {}: {}", concept["symbol"], e)
            if i < len(items) - 1 and self.RAISE_INTER_TICK_DELAY > 0:
                await asyncio.sleep(self.RAISE_INTER_TICK_DELAY)

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
