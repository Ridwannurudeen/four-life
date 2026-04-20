"""MYX V2 hedge manager — automated perp hedging tied to token lifecycle phases.

Since MYX V2 permissionless pair creation is not yet live, FOUR-LIFE hedges
meme token exposure using existing MYX pairs (BNB/USDT). The reasoning:
meme tokens on Four.meme are priced in BNB, so shorting BNB/USDT on MYX
effectively hedges the agent's BNB-denominated meme token exposure.

Hedge logic by lifecycle phase:
- NURTURE: No hedge (small exposure, still evaluating)
- DEFEND:  Open short hedge when health drops (protect capital)
- ACCELERATE: Scale down hedge as token gains momentum
- GRADUATED: Close all hedges (token moved to PancakeSwap)
"""

import time
from dataclasses import dataclass, field
from loguru import logger

from agent.myx.client import MYXClient, MYXStrategy
from agent.myx.store import (
    MYXAttestationChain,
    MYXSignalAttestationChain,
    get_myx_chain,
    get_myx_signal_chain,
    get_position_log,
    get_signal_log,
)


@dataclass
class HedgePosition:
    """Tracks an active hedge position on MYX."""

    token_address: str
    pair_index: int
    is_long: bool
    collateral_wei: int
    size_amount: int
    open_price: int  # 1e30
    open_tx: str
    opened_at: float
    reason: str
    close_tx: str | None = None
    closed_at: float | None = None
    close_price: int | None = None


@dataclass
class HedgeState:
    """Per-token hedge tracking."""

    token_address: str
    positions: list[HedgePosition] = field(default_factory=list)
    total_hedged: int = 0  # cumulative collateral committed
    total_closed: int = 0
    signals_generated: int = 0
    last_signal: dict | None = None
    last_signal_at: float = 0

    @property
    def active_positions(self) -> list[HedgePosition]:
        return [p for p in self.positions if p.close_tx is None]

    @property
    def has_active_hedge(self) -> bool:
        return len(self.active_positions) > 0


# Default BNB/USDT pair index on MYX (most liquid pair on BSC)
DEFAULT_HEDGE_PAIR = 0  # BNB/USDT — will be resolved dynamically if possible

# Hedge thresholds
MIN_HEALTH_FOR_HEDGE = 50  # Below this health score, consider hedging
HEDGE_COOLDOWN = 600  # 10 min between hedge actions per token
SIGNAL_COOLDOWN = 300  # 5 min between signal generations


class HedgeManager:
    """Manages perp hedges across all active tokens."""

    def __init__(
        self,
        myx: MYXClient,
        strategy: MYXStrategy,
        execution_enabled: bool = False,
    ) -> None:
        self.myx = myx
        self.strategy = strategy
        # When False, the manager generates signals but does not submit on-chain orders.
        # Keeps the demo surface honest until real oracle pricing + production collateral
        # are wired up.
        self.execution_enabled = execution_enabled
        self.states: dict[str, HedgeState] = {}  # token_address -> state
        self._pair_index_cache: dict[str, int] = {}

    @property
    def execution_mode(self) -> str:
        return "executable" if self.execution_enabled else "signal_only"

    def _get_state(self, token_address: str) -> HedgeState:
        if token_address not in self.states:
            self.states[token_address] = HedgeState(token_address=token_address)
        return self.states[token_address]

    async def resolve_pair_index(self) -> int:
        """Resolve the BNB/USDT pair index from MYX."""
        cache_key = "bnb_usdt"
        if cache_key in self._pair_index_cache:
            return self._pair_index_cache[cache_key]

        try:
            # WBNB and USDT on BSC
            wbnb = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
            usdt = "0x55d398326f99059fF775485246999027B3197955"
            idx = await self.myx.get_pair_index(wbnb, usdt)
            self._pair_index_cache[cache_key] = idx
            return idx
        except Exception as e:
            logger.warning("Could not resolve BNB/USDT pair index: {}", e)
            return DEFAULT_HEDGE_PAIR

    async def evaluate_and_act(
        self,
        token_address: str,
        token_health: dict,
        phase: str,
    ) -> dict | None:
        """Evaluate hedge needs for a token and act if appropriate.

        Args:
            token_address: The Four.meme token being managed
            token_health: Dict with health metrics (health_score, phase, etc.)
            phase: Current lifecycle phase

        Returns:
            Action taken dict, or None if no action needed.
        """
        state = self._get_state(token_address)
        now = time.time()

        # Generate a signal (rate-limited). For DEFEND — the phase where the
        # agent actually executes — we fan the decision across 3 DGrid models
        # and take the majority vote. This is the cross-partner flex: the
        # single-provider integration can't do this at all.
        use_consensus = phase == "defend"
        signal = None
        if now - state.last_signal_at >= SIGNAL_COOLDOWN:
            try:
                markets = await self.myx.get_markets()
                signal = await self.strategy.generate_signal(
                    token_health,
                    {
                        "available_markets": len(markets),
                        "has_active_hedge": state.has_active_hedge,
                        "active_positions": len(state.active_positions),
                        "phase": phase,
                    },
                    use_consensus=use_consensus,
                )
                state.last_signal = signal
                state.last_signal_at = now
                state.signals_generated += 1
                logger.info(
                    "[HEDGE] Signal for {}: {} (confidence: {:.0%})",
                    token_address[:10],
                    signal.get("action", "unknown"),
                    signal.get("confidence", 0),
                )
                # Persist every signal so the dashboard can show unbounded
                # history AND fold into the signal attestation chain so the
                # agent's thinking is cryptographically committed even when
                # no trade ever executes (MYX router verification pending).
                try:
                    import hashlib as _hashlib
                    ts_ms = int(time.time() * 1000)
                    action = str(signal.get("action", "unknown"))
                    confidence = float(signal.get("confidence", 0) or 0)
                    size_pct = float(signal.get("size_pct", 0) or 0)
                    reasoning_text = str(signal.get("reasoning", ""))[:400]
                    reasoning_hash = _hashlib.sha256(reasoning_text.encode()).hexdigest()
                    consensus_meta = signal.get("consensus") or {}
                    consensus_method = consensus_meta.get("method") if isinstance(consensus_meta, dict) else None
                    consensus_conf = consensus_meta.get("confidence") if isinstance(consensus_meta, dict) else None

                    digest = MYXSignalAttestationChain.signal_digest(
                        token_address=token_address,
                        phase=phase,
                        action=action,
                        confidence=confidence,
                        size_pct=size_pct,
                        reasoning_hash=reasoning_hash,
                        ts_ms=ts_ms,
                        consensus_method=consensus_method,
                        consensus_confidence=consensus_conf,
                    )
                    chain_tip = get_myx_signal_chain().append(digest)

                    get_signal_log().append({
                        "ts_ms": ts_ms,
                        "token_address": token_address.lower(),
                        "phase": phase,
                        "action": action,
                        "confidence": confidence,
                        "size_pct": size_pct,
                        "reasoning": reasoning_text,
                        "reasoning_hash": reasoning_hash,
                        "execution_mode": self.execution_mode,
                        "health_score": token_health.get("health_score"),
                        "active_positions": len(state.active_positions),
                        "consensus": consensus_meta if isinstance(consensus_meta, dict) else None,
                        "signal_digest": digest,
                        "chain_tip": chain_tip,
                    })
                except Exception as persist_err:
                    logger.warning("[HEDGE] Signal persist skipped: {}", persist_err)
            except Exception as e:
                logger.error("[HEDGE] Signal generation failed: {}", e)
                return None
        else:
            signal = state.last_signal

        if not signal:
            return None

        action = signal.get("action", "hold")
        confidence = signal.get("confidence", 0)

        # Phase-based hedge logic
        if phase == "nurture":
            # Too early to hedge — just track signals
            return {
                "action": "monitor",
                "signal": signal,
                "reason": "Nurture phase — monitoring only",
            }

        if phase == "graduated":
            # Token graduated — close all hedges
            if state.has_active_hedge:
                return await self._close_all_hedges(token_address, "Token graduated to PancakeSwap")
            return None

        # DEFEND / ACCELERATE — act on signals, but only when execution is enabled
        if not self.execution_enabled:
            return {
                "action": "signal_only",
                "execution_mode": self.execution_mode,
                "would_execute": action,
                "signal": signal,
                "reason": "MYX execution disabled (MYX_EXECUTION_ENABLED=false). Signal generated but not submitted.",
            }

        if action == "short" and confidence >= 0.6 and not state.has_active_hedge:
            return await self._open_hedge(
                token_address,
                token_health,
                signal,
                is_long=False,
            )

        if action == "long" and confidence >= 0.7 and not state.has_active_hedge:
            return await self._open_hedge(
                token_address,
                token_health,
                signal,
                is_long=True,
            )

        if action == "close" and state.has_active_hedge:
            return await self._close_all_hedges(
                token_address,
                signal.get("reasoning", "Signal says close"),
            )

        # Hold — no action
        return {
            "action": "hold",
            "signal": signal,
            "active_positions": len(state.active_positions),
        }

    async def _open_hedge(
        self,
        token_address: str,
        token_health: dict,
        signal: dict,
        is_long: bool,
    ) -> dict:
        """Open a hedge position on MYX."""
        state = self._get_state(token_address)
        pair_index = await self.resolve_pair_index()

        size_pct = min(signal.get("size_pct", 0.05), 0.10)
        # Use 0.01 BNB as base collateral for demo (conservative)
        collateral_wei = int(0.01 * 1e18 * (size_pct / 0.05))
        size_amount = collateral_wei * 5  # 5x leverage

        # Get current BNB price for order (approximate)
        price_1e30 = int(600 * 1e30)  # Will be overridden by market order

        try:
            tx_hash = await self.myx.open_position(
                pair_index=pair_index,
                is_long=is_long,
                collateral_wei=collateral_wei,
                size_amount=size_amount,
                price_1e30=price_1e30,
            )

            position = HedgePosition(
                token_address=token_address,
                pair_index=pair_index,
                is_long=is_long,
                collateral_wei=collateral_wei,
                size_amount=size_amount,
                open_price=price_1e30,
                open_tx=tx_hash,
                opened_at=time.time(),
                reason=signal.get("reasoning", "AI signal"),
            )
            state.positions.append(position)
            state.total_hedged += collateral_wei

            direction = "LONG" if is_long else "SHORT"
            logger.info(
                "[HEDGE] Opened {} for {} — tx: {}",
                direction, token_address[:10], tx_hash,
            )
            # Chain this trade into the MYX attestation. Each position open/
            # close is hashed into a rolling Merkle tip that can be published
            # on-chain as cryptographic proof of trading activity.
            try:
                ts_ms = int(time.time() * 1000)
                digest = MYXAttestationChain.event_digest(
                    kind="open", token_address=token_address,
                    pair_index=pair_index, is_long=is_long,
                    collateral_wei=collateral_wei, size_amount=size_amount,
                    tx_hash=tx_hash, ts_ms=ts_ms,
                )
                chain_tip = get_myx_chain().append(digest)
                get_position_log().append({
                    "ts_ms": ts_ms,
                    "kind": "open",
                    "token_address": token_address.lower(),
                    "pair_index": pair_index,
                    "is_long": is_long,
                    "collateral_wei": str(collateral_wei),
                    "size_amount": str(size_amount),
                    "tx_hash": tx_hash,
                    "event_digest": digest,
                    "chain_tip": chain_tip,
                    "reason": signal.get("reasoning", "")[:200],
                })
            except Exception as chain_err:
                logger.warning("[HEDGE] Attestation append skipped: {}", chain_err)

            return {
                "action": f"open_{direction.lower()}",
                "tx_hash": tx_hash,
                "collateral_wei": collateral_wei,
                "size_amount": size_amount,
                "leverage": "5x",
                "signal": signal,
            }

        except Exception as e:
            logger.error("[HEDGE] Failed to open position: {}", e)
            return {
                "action": "open_failed",
                "error": str(e),
                "signal": signal,
            }

    async def _close_all_hedges(self, token_address: str, reason: str) -> dict:
        """Close all active hedge positions for a token."""
        state = self._get_state(token_address)
        closed = []

        for pos in state.active_positions:
            try:
                price_1e30 = int(600 * 1e30)  # Market order
                tx_hash = await self.myx.close_position(
                    pair_index=pos.pair_index,
                    is_long=pos.is_long,
                    size_amount=pos.size_amount,
                    price_1e30=price_1e30,
                )
                pos.close_tx = tx_hash
                pos.closed_at = time.time()
                pos.close_price = price_1e30
                state.total_closed += 1
                closed.append(tx_hash)
                logger.info("[HEDGE] Closed position for {} — tx: {}", token_address[:10], tx_hash)
                # Fold the close event into the attestation chain too.
                try:
                    ts_ms = int(time.time() * 1000)
                    digest = MYXAttestationChain.event_digest(
                        kind="close", token_address=token_address,
                        pair_index=pos.pair_index, is_long=pos.is_long,
                        collateral_wei=pos.collateral_wei, size_amount=pos.size_amount,
                        tx_hash=tx_hash, ts_ms=ts_ms,
                    )
                    chain_tip = get_myx_chain().append(digest)
                    get_position_log().append({
                        "ts_ms": ts_ms,
                        "kind": "close",
                        "token_address": token_address.lower(),
                        "pair_index": pos.pair_index,
                        "is_long": pos.is_long,
                        "collateral_wei": str(pos.collateral_wei),
                        "size_amount": str(pos.size_amount),
                        "tx_hash": tx_hash,
                        "event_digest": digest,
                        "chain_tip": chain_tip,
                        "reason": reason[:200],
                    })
                except Exception as chain_err:
                    logger.warning("[HEDGE] Close attestation skipped: {}", chain_err)
            except Exception as e:
                logger.error("[HEDGE] Failed to close position: {}", e)

        return {
            "action": "close_all",
            "reason": reason,
            "closed_count": len(closed),
            "tx_hashes": closed,
        }

    def get_portfolio_summary(self) -> dict:
        """Get summary of all hedge positions across all tokens."""
        total_active = 0
        total_closed = 0
        total_signals = 0
        token_summaries = []

        for addr, state in self.states.items():
            active = state.active_positions
            total_active += len(active)
            total_closed += state.total_closed
            total_signals += state.signals_generated

            token_summaries.append({
                "token_address": addr,
                "active_positions": len(active),
                "total_positions": len(state.positions),
                "total_hedged_wei": state.total_hedged,
                "signals_generated": state.signals_generated,
                "last_signal": state.last_signal,
            })

        return {
            "execution_mode": self.execution_mode,
            "total_active_positions": total_active,
            "total_closed_positions": total_closed,
            "total_signals_generated": total_signals,
            "tokens_hedged": len(self.states),
            "token_summaries": token_summaries,
        }

    def get_token_positions(self, token_address: str) -> list[dict]:
        """Get all positions for a specific token."""
        state = self._get_state(token_address)
        return [
            {
                "pair_index": p.pair_index,
                "is_long": p.is_long,
                "collateral_wei": p.collateral_wei,
                "size_amount": p.size_amount,
                "open_tx": p.open_tx,
                "opened_at": p.opened_at,
                "reason": p.reason,
                "close_tx": p.close_tx,
                "closed_at": p.closed_at,
                "status": "closed" if p.close_tx else "active",
            }
            for p in state.positions
        ]
