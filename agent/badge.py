"""FOUR-LIFE Certified — deterministic public trust layer for Four.meme launches.

A badge is a tier-level label (observed | healthy | at_risk | graduation_watch | graduated)
computed purely from raw on-chain + ranking metrics. No LLM involvement. Every response
includes a `why[]` array with the exact metric values that triggered each criterion,
so the result is fully auditable and reproducible.

The badge is the primary UX primitive Four.meme can embed on token pages.

Tier rules (evaluated top-down — first match wins):
  - graduated         : curve_progress_pct >= 100 OR phase == "graduated"
  - graduation_watch  : curve_progress_pct >= 70 AND buy_sell_ratio >= 1.2 AND top_holder_pct < 30
  - at_risk           : top_holder_pct >= 40 OR (buy_sell_ratio < 0.6 AND age_hours > 2)
                        OR (age_hours > 12 AND curve_progress_pct < 5 AND confidence == "high")
  - healthy           : age_hours >= 1 AND buy_sell_ratio >= 1.2 AND holder_velocity >= 5
                        AND top_holder_pct < 20 AND health_score >= 60
  - observed          : otherwise (default — tracked but not yet trust-graded)
"""

from dataclasses import dataclass, asdict
from typing import Any


TIER_GRADUATED = "graduated"
TIER_GRADUATION_WATCH = "graduation_watch"
TIER_AT_RISK = "at_risk"
TIER_HEALTHY = "healthy"
TIER_OBSERVED = "observed"

TIER_DESCRIPTIONS = {
    TIER_GRADUATED: "Reached the bonding-curve graduation threshold.",
    TIER_GRADUATION_WATCH: "On track to graduate — strong buy pressure, healthy distribution, curve past 70%.",
    TIER_AT_RISK: "Meaningful risk signal triggered — whale concentration, sell pressure, or stalled curve.",
    TIER_HEALTHY: "Clean distribution, rising holders, buys outpacing sells after 1h.",
    TIER_OBSERVED: "Tracked, but not enough signal yet to trust-grade.",
}


@dataclass
class Badge:
    tier: str
    label: str           # human-readable display label
    description: str
    why: list[dict]      # list of {rule, metric, value, threshold, operator, passed}
    metrics_snapshot: dict
    version: str = "four-life-certified-v1"

    def to_dict(self) -> dict:
        return asdict(self)


def _rule(name: str, metric: str, value: Any, threshold: Any, operator: str, passed: bool) -> dict:
    return {
        "rule": name,
        "metric": metric,
        "value": value,
        "threshold": threshold,
        "operator": operator,
        "passed": passed,
    }


def compute_badge(
    *,
    curve_progress_pct: float,
    phase: str,
    health_score: float,
    buy_sell_ratio: float,
    holder_velocity: float,
    top_holder_pct: float,
    age_hours: float,
    graduation_confidence: str = "high",
    unique_buyers: int = 0,
    whale_count: int = 0,
    contract_risk_score: int = 0,
) -> Badge:
    """Compute the Certified badge from raw metrics. Deterministic, no network, no LLM."""

    metrics = {
        "curve_progress_pct": round(curve_progress_pct, 2),
        "phase": phase,
        "health_score": round(health_score, 2),
        "buy_sell_ratio": round(buy_sell_ratio, 2),
        "holder_velocity": round(holder_velocity, 2),
        "top_holder_pct": round(top_holder_pct, 2),
        "age_hours": round(age_hours, 2),
        "graduation_confidence": graduation_confidence,
        "unique_buyers": unique_buyers,
        "whale_count": whale_count,
        "contract_risk_score": int(contract_risk_score),
    }

    # 0) CONTRACT RUG OVERRIDE — force at_risk when the contract-level analyzer
    #    scores >= 60 (mint + blacklist, or mint + proxy, etc.). Runs FIRST so the
    #    override is audit-visible even for tokens that would otherwise graduate.
    if contract_risk_score >= 60:
        return Badge(
            tier=TIER_AT_RISK,
            label="At Risk",
            description=TIER_DESCRIPTIONS[TIER_AT_RISK],
            why=[
                _rule("contract_rug_risk", "contract_risk_score", int(contract_risk_score), 60, ">=", True),
            ],
            metrics_snapshot=metrics,
        )

    # 1) GRADUATED — curve is full or phase explicitly says graduated
    if curve_progress_pct >= 100 or phase == "graduated":
        return Badge(
            tier=TIER_GRADUATED,
            label="Graduated",
            description=TIER_DESCRIPTIONS[TIER_GRADUATED],
            why=[
                _rule("curve_complete", "curve_progress_pct", metrics["curve_progress_pct"], 100, ">=", curve_progress_pct >= 100),
                _rule("phase_graduated", "phase", phase, "graduated", "==", phase == "graduated"),
            ],
            metrics_snapshot=metrics,
        )

    # 2) GRADUATION_WATCH — strong signals that graduation is close
    gw_curve = curve_progress_pct >= 70
    gw_buy = buy_sell_ratio >= 1.2
    gw_whale = top_holder_pct < 30
    gw_conf = graduation_confidence == "high"
    if gw_curve and gw_buy and gw_whale and gw_conf:
        return Badge(
            tier=TIER_GRADUATION_WATCH,
            label="Graduation Watch",
            description=TIER_DESCRIPTIONS[TIER_GRADUATION_WATCH],
            why=[
                _rule("curve_advanced", "curve_progress_pct", metrics["curve_progress_pct"], 70, ">=", gw_curve),
                _rule("buy_pressure", "buy_sell_ratio", metrics["buy_sell_ratio"], 1.2, ">=", gw_buy),
                _rule("whale_ok", "top_holder_pct", metrics["top_holder_pct"], 30, "<", gw_whale),
                _rule("target_confident", "graduation_confidence", graduation_confidence, "high", "==", gw_conf),
            ],
            metrics_snapshot=metrics,
        )

    # 3) AT_RISK — any one of several concrete failure modes
    ar_whale = top_holder_pct >= 40
    ar_sell = buy_sell_ratio > 0 and buy_sell_ratio < 0.6 and age_hours > 2
    ar_stall = age_hours > 12 and curve_progress_pct < 5 and graduation_confidence == "high"
    ar_whale_cluster = whale_count >= 3
    if ar_whale or ar_sell or ar_stall or ar_whale_cluster:
        reasons = [
            _rule("whale_extreme", "top_holder_pct", metrics["top_holder_pct"], 40, ">=", ar_whale),
            _rule("sell_pressure", "buy_sell_ratio", metrics["buy_sell_ratio"], 0.6, "<", ar_sell),
            _rule("curve_stalled", "curve_progress_pct", metrics["curve_progress_pct"], 5, "<", ar_stall),
            _rule("whale_cluster", "whale_count", metrics["whale_count"], 3, ">=", ar_whale_cluster),
        ]
        return Badge(
            tier=TIER_AT_RISK,
            label="At Risk",
            description=TIER_DESCRIPTIONS[TIER_AT_RISK],
            why=reasons,
            metrics_snapshot=metrics,
        )

    # 4) HEALTHY — all the good signals line up
    h_age = age_hours >= 1
    h_buy = buy_sell_ratio >= 1.2
    h_vel = holder_velocity >= 5
    h_whale = top_holder_pct < 20
    h_score = health_score >= 60
    if h_age and h_buy and h_vel and h_whale and h_score:
        return Badge(
            tier=TIER_HEALTHY,
            label="Healthy",
            description=TIER_DESCRIPTIONS[TIER_HEALTHY],
            why=[
                _rule("age_min", "age_hours", metrics["age_hours"], 1, ">=", h_age),
                _rule("buy_pressure", "buy_sell_ratio", metrics["buy_sell_ratio"], 1.2, ">=", h_buy),
                _rule("holder_growth", "holder_velocity", metrics["holder_velocity"], 5, ">=", h_vel),
                _rule("whale_ok", "top_holder_pct", metrics["top_holder_pct"], 20, "<", h_whale),
                _rule("health_score", "health_score", metrics["health_score"], 60, ">=", h_score),
            ],
            metrics_snapshot=metrics,
        )

    # 5) OBSERVED — default: tracked but not yet graded
    return Badge(
        tier=TIER_OBSERVED,
        label="Observed",
        description=TIER_DESCRIPTIONS[TIER_OBSERVED],
        why=[
            _rule("default", "age_hours", metrics["age_hours"], 1, ">=", h_age),
            _rule("default", "buy_sell_ratio", metrics["buy_sell_ratio"], 1.2, ">=", buy_sell_ratio >= 1.2),
            _rule("default", "holder_velocity", metrics["holder_velocity"], 5, ">=", holder_velocity >= 5),
            _rule("default", "top_holder_pct", metrics["top_holder_pct"], 20, "<", top_holder_pct < 20),
        ],
        metrics_snapshot=metrics,
    )


def badge_from_health(health, contract_risk_score: int = 0) -> Badge:
    """Convenience: compute a badge from a TokenHealth dataclass."""
    return compute_badge(
        curve_progress_pct=health.curve_progress_pct,
        phase=health.phase,
        health_score=health.health_score,
        buy_sell_ratio=health.buy_sell_ratio,
        holder_velocity=health.holder_velocity,
        top_holder_pct=health.top_holder_pct,
        age_hours=health.age_hours,
        graduation_confidence=getattr(health, "graduation_confidence", "high"),
        unique_buyers=health.unique_buyers,
        whale_count=health.whale_count,
        contract_risk_score=contract_risk_score,
    )


def badge_from_ranking(
    *,
    curve_progress_pct: float,
    holders: int,
    increase_pct: float,
    graduation_confidence: str,
) -> Badge:
    """Compute a lower-fidelity badge from public ranking data only.

    Ranking tokens lack on-chain buy/sell detail, so only tiers that can be decided
    from curve progress + holders are returned — everything else falls to OBSERVED.
    """
    # Approximate buy_sell_ratio from `increase` (positive means buy pressure)
    approx_buy_sell = 1.0 + max(-0.5, min(1.0, increase_pct / 100))
    # Approximate holder velocity: can't know without age, so set to 0
    approx_velocity = 0.0
    # Approximate top_holder_pct: unknown — assume safe-ish so we don't false-positive at_risk
    approx_top = 0.0

    return compute_badge(
        curve_progress_pct=curve_progress_pct,
        phase="graduated" if curve_progress_pct >= 100 else "accelerate",
        health_score=0.0,
        buy_sell_ratio=approx_buy_sell,
        holder_velocity=approx_velocity,
        top_holder_pct=approx_top,
        age_hours=2.0,  # assume past the 1h threshold for healthy eligibility
        graduation_confidence=graduation_confidence,
        unique_buyers=holders,
        whale_count=0,
    )
