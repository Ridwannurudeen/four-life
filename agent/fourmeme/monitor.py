"""Real-time on-chain monitor for Four.meme token health."""

import asyncio
import time
from dataclasses import dataclass, field
from collections import defaultdict

from loguru import logger
from web3 import AsyncWeb3

from agent.fourmeme.chain import FourMemeChain
from agent.fourmeme.graduation import GraduationRegistry, get_registry


@dataclass
class TokenHealth:
    """Snapshot of a token's on-chain health metrics."""

    address: str
    name: str = ""
    symbol: str = ""
    creator: str = ""
    created_at: float = 0.0
    created_block: int = 0

    # Holder metrics
    unique_buyers: int = 0
    unique_sellers: int = 0
    holder_velocity: float = 0.0  # new holders per hour

    # Volume metrics (denominated in the token's quote asset, e.g. BNB for BNB-pair tokens)
    total_buys: int = 0
    total_sells: int = 0
    buy_volume_bnb: float = 0.0   # historical name; actually tracks volume in quote_asset
    sell_volume_bnb: float = 0.0  # historical name; actually tracks volume in quote_asset
    buy_sell_ratio: float = 0.0

    # Whale metrics
    top_holder_pct: float = 0.0
    whale_count: int = 0  # holders with >5% supply

    # Bonding curve
    curve_progress_pct: float = 0.0
    current_price_wei: int = 0

    # Derived scores
    health_score: float = 0.0  # 0-100
    graduation_probability: float = 0.0  # 0-1

    # Phase tracking
    age_hours: float = 0.0
    phase: str = "nurture"  # nurture | defend | accelerate | graduated

    # Pair-aware graduation metadata (sourced from Four.meme live config)
    quote_asset: str = "BNB"             # BNB | USD1 | USDT | USDC | CAKE | ...
    graduation_target: float = 0.0       # e.g. 18.0 for BNB, 12000.0 for USD1
    graduation_target_unit: str = ""     # mirror of quote_asset, for display
    graduation_confidence: str = "low"   # "high" | "medium" | "low"
    graduation_source: str = ""          # "fourmeme_config" | "cache" | "fallback"


@dataclass
class MonitorState:
    """Tracks all monitored tokens and their health."""

    tokens: dict[str, TokenHealth] = field(default_factory=dict)
    buyer_sets: dict[str, set] = field(default_factory=lambda: defaultdict(set))
    seller_sets: dict[str, set] = field(default_factory=lambda: defaultdict(set))
    holder_balances: dict[str, dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(int))
    )
    last_scanned_block: dict[str, int] = field(default_factory=dict)


class TokenMonitor:
    """Monitors Four.meme tokens in real-time, computing health metrics."""

    TOTAL_SUPPLY = 1_000_000_000
    WHALE_THRESHOLD_PCT = 5.0
    SCAN_INTERVAL_BLOCKS = 100  # ~50 seconds at 0.5s/block

    def __init__(
        self,
        chain: FourMemeChain,
        graduation_registry: GraduationRegistry | None = None,
    ) -> None:
        self.chain = chain
        self.state = MonitorState()
        # Pair-aware graduation registry — sourced from Four.meme's live config
        self.graduation_registry = graduation_registry or get_registry()

    async def track_token(
        self,
        token_address: str,
        name: str = "",
        symbol: str = "",
        creator: str = "",
        created_block: int = 0,
        quote_asset: str = "BNB",
        seed: dict | None = None,
        launched_at: float | None = None,
    ) -> None:
        """Start tracking a token. Resolves its graduation target from Four.meme's config.

        ``launched_at`` is the token's *actual* launch timestamp (from the
        launch record or the mint-block timestamp). If the token has been
        launched before we started observing (restart, manual /api/agent/track
        of an existing token), passing ``launched_at`` makes ``age_hours``
        reflect the real on-chain age — not the observation age. Without it we
        fall back to ``time.time()`` and the badge/health report the
        observation age, which is dishonest for tokens older than 1 block.

        ``seed`` is currently unused for numeric fields because
        ``update_token`` recomputes every health metric (unique_buyers,
        curve_progress, top_holder_pct, …) from accumulated on-chain events
        on the next tick and would overwrite any seeded value. We only
        observe from the moment we start tracking, by design. Keep the arg
        for signature compatibility in case a future version adds a
        non-overwritten "initial snapshot" field.
        """
        del seed
        # Resolve pair-aware graduation target (falls back to low-confidence for unknown assets)
        target = await self.graduation_registry.get(quote_asset)

        health = TokenHealth(
            address=token_address,
            name=name,
            symbol=symbol,
            creator=creator,
            created_at=launched_at if launched_at else time.time(),
            created_block=created_block,
            quote_asset=target.quote_asset,
            graduation_target=target.target_amount,
            graduation_target_unit=target.quote_asset,
            graduation_confidence=target.confidence,
            graduation_source=target.source,
        )
        self.state.tokens[token_address] = health
        logger.info(
            "Now tracking {} ({}) at {} — graduation target {} {} (confidence: {})",
            name, symbol, token_address,
            target.target_amount, target.quote_asset, target.confidence,
        )

    async def update_token(self, token_address: str) -> TokenHealth:
        """Update health metrics for a tracked token."""
        health = self.state.tokens.get(token_address)
        if not health:
            raise ValueError(f"Token {token_address} not tracked")

        # Resume scanning ONE block after the last scanned tip — replaying the
        # terminal block would double-count every trade in that block, which
        # cascades into corrupted buy/sell counts, balances, curve progress,
        # health score, and badge tier. When the chain hasn't advanced we skip
        # the trade fetch (empty window) but STILL update time-based fields
        # below (age, phase, velocity) so the lifecycle keeps ticking.
        last_scanned = self.state.last_scanned_block.get(token_address)
        if last_scanned is None:
            from_block = health.created_block
        else:
            from_block = max(health.created_block, last_scanned + 1)
        current_block = await self.chain.get_block_number()

        if from_block > current_block:
            trades = {"buys": [], "sells": []}
        else:
            # Public BSC RPCs cap eth_getLogs at ~50k blocks per request. If a
            # token was tracked from a much older block (e.g. long downtime),
            # skip forward to a scannable window — the first tick loses some
            # history but every subsequent tick is on the live tip.
            if current_block - from_block > 50_000:
                from_block = current_block - 50_000
            trades = await self.chain.get_token_trades(
                token_address, from_block=from_block, to_block=current_block
            )

        # Process buys
        for buy in trades["buys"]:
            self.state.buyer_sets[token_address].add(buy["buyer"])
            self.state.holder_balances[token_address][buy["buyer"]] += buy["amount"]

        # Process sells
        for sell in trades["sells"]:
            self.state.seller_sets[token_address].add(sell["seller"])
            self.state.holder_balances[token_address][sell["seller"]] -= sell["amount"]

        # Compute metrics
        health.unique_buyers = len(self.state.buyer_sets[token_address])
        health.unique_sellers = len(self.state.seller_sets[token_address])
        health.total_buys += len(trades["buys"])
        health.total_sells += len(trades["sells"])
        health.buy_volume_bnb += sum(b["cost"] for b in trades["buys"]) / 1e18
        health.sell_volume_bnb += sum(s["revenue"] for s in trades["sells"]) / 1e18

        if health.total_sells > 0:
            health.buy_sell_ratio = health.total_buys / health.total_sells
        else:
            health.buy_sell_ratio = float(health.total_buys) if health.total_buys > 0 else 0

        # Age
        health.age_hours = (time.time() - health.created_at) / 3600

        # Holder velocity
        if health.age_hours > 0:
            health.holder_velocity = health.unique_buyers / health.age_hours

        # Whale analysis
        balances = self.state.holder_balances[token_address]
        active_balances = {a: b for a, b in balances.items() if b > 0}
        if active_balances:
            max_balance = max(active_balances.values())
            health.top_holder_pct = (max_balance / self.TOTAL_SUPPLY) * 100
            whale_threshold = self.TOTAL_SUPPLY * (self.WHALE_THRESHOLD_PCT / 100)
            health.whale_count = sum(1 for b in active_balances.values() if b >= whale_threshold)

        # Price & curve
        try:
            health.current_price_wei = await self.chain.get_price(token_address)
        except Exception:
            pass

        # Bonding curve progress: buy volume as fraction of pair-aware graduation target.
        # If the target is unknown (low confidence), progress is reported as 0 rather than
        # fabricated against a default — callers see confidence="low" and can react.
        if health.graduation_target > 0:
            health.curve_progress_pct = min(
                100, (health.buy_volume_bnb / health.graduation_target) * 100,
            )
        else:
            health.curve_progress_pct = 0.0

        # Phase (must be after curve_progress_pct is computed)
        if health.curve_progress_pct >= 100:
            health.phase = "graduated"
        elif health.age_hours < 6:
            health.phase = "nurture"
        elif health.age_hours < 24:
            health.phase = "defend"
        else:
            health.phase = "accelerate"

        # Health score (0-100)
        health.health_score = self._compute_health_score(health)

        # Graduation probability
        health.graduation_probability = self._compute_graduation_prob(health)

        self.state.last_scanned_block[token_address] = current_block
        return health

    def _compute_health_score(self, h: TokenHealth) -> float:
        """Composite health score 0-100."""
        score = 0.0

        # Holder growth (0-30 points)
        if h.holder_velocity >= 50:
            score += 30
        elif h.holder_velocity >= 20:
            score += 20
        elif h.holder_velocity >= 5:
            score += 10
        elif h.holder_velocity >= 1:
            score += 5

        # Buy/sell ratio (0-25 points)
        if h.buy_sell_ratio >= 3:
            score += 25
        elif h.buy_sell_ratio >= 2:
            score += 20
        elif h.buy_sell_ratio >= 1.5:
            score += 15
        elif h.buy_sell_ratio >= 1:
            score += 10

        # Whale concentration (0-25 points, lower = better)
        if h.top_holder_pct < 5:
            score += 25
        elif h.top_holder_pct < 10:
            score += 20
        elif h.top_holder_pct < 20:
            score += 15
        elif h.top_holder_pct < 40:
            score += 5

        # Curve progress (0-20 points)
        score += min(20, h.curve_progress_pct / 5)

        return round(min(100, score), 1)

    def _compute_graduation_prob(self, h: TokenHealth) -> float:
        """Estimate graduation probability based on current metrics."""
        # Simple logistic-style model based on key signals
        prob = 0.0

        # Curve progress is the strongest predictor
        if h.curve_progress_pct >= 80:
            prob += 0.5
        elif h.curve_progress_pct >= 50:
            prob += 0.3
        elif h.curve_progress_pct >= 25:
            prob += 0.15

        # Holder count matters
        if h.unique_buyers >= 500:
            prob += 0.2
        elif h.unique_buyers >= 200:
            prob += 0.1
        elif h.unique_buyers >= 50:
            prob += 0.05

        # Buy pressure
        if h.buy_sell_ratio >= 2:
            prob += 0.15
        elif h.buy_sell_ratio >= 1.5:
            prob += 0.1

        # Low whale concentration is good
        if h.top_holder_pct < 10:
            prob += 0.1

        # Momentum (velocity)
        if h.holder_velocity >= 20:
            prob += 0.1
        elif h.holder_velocity >= 5:
            prob += 0.05

        return round(min(1.0, prob), 3)

    async def get_all_health(self) -> list[TokenHealth]:
        """Update and return health for all tracked tokens."""
        results = []
        for addr in list(self.state.tokens.keys()):
            try:
                health = await self.update_token(addr)
                results.append(health)
            except Exception as e:
                logger.error("Failed to update {}: {}", addr, e)
        return results
