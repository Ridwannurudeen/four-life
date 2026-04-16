"""Tests for FOUR-LIFE Certified badge system — must be fully deterministic."""

import pytest

from agent.badge import (
    compute_badge,
    badge_from_ranking,
    TIER_GRADUATED,
    TIER_GRADUATION_WATCH,
    TIER_AT_RISK,
    TIER_HEALTHY,
    TIER_OBSERVED,
)


def _base_metrics(**overrides):
    base = dict(
        curve_progress_pct=0.0,
        phase="nurture",
        health_score=0.0,
        buy_sell_ratio=1.0,
        holder_velocity=0.0,
        top_holder_pct=0.0,
        age_hours=0.0,
        graduation_confidence="high",
        unique_buyers=0,
        whale_count=0,
    )
    base.update(overrides)
    return base


class TestBadgeTiers:
    def test_graduated_by_curve_progress(self):
        badge = compute_badge(**_base_metrics(curve_progress_pct=100.5, age_hours=10))
        assert badge.tier == TIER_GRADUATED

    def test_graduated_by_phase(self):
        badge = compute_badge(**_base_metrics(phase="graduated"))
        assert badge.tier == TIER_GRADUATED

    def test_graduation_watch(self):
        badge = compute_badge(**_base_metrics(
            curve_progress_pct=75, buy_sell_ratio=1.5, top_holder_pct=15,
            graduation_confidence="high", age_hours=10,
        ))
        assert badge.tier == TIER_GRADUATION_WATCH
        passed = {r["rule"]: r["passed"] for r in badge.why}
        assert passed["curve_advanced"] is True
        assert passed["buy_pressure"] is True

    def test_graduation_watch_requires_high_confidence(self):
        badge = compute_badge(**_base_metrics(
            curve_progress_pct=75, buy_sell_ratio=1.5, top_holder_pct=15,
            graduation_confidence="low", age_hours=10,
        ))
        # Low-confidence target should not earn graduation watch
        assert badge.tier != TIER_GRADUATION_WATCH

    def test_at_risk_extreme_whale(self):
        badge = compute_badge(**_base_metrics(
            top_holder_pct=45, age_hours=5,
        ))
        assert badge.tier == TIER_AT_RISK
        whale_rule = next(r for r in badge.why if r["rule"] == "whale_extreme")
        assert whale_rule["passed"] is True

    def test_at_risk_sell_pressure(self):
        badge = compute_badge(**_base_metrics(
            buy_sell_ratio=0.4, age_hours=5, curve_progress_pct=10,
        ))
        assert badge.tier == TIER_AT_RISK

    def test_at_risk_stalled_curve(self):
        badge = compute_badge(**_base_metrics(
            age_hours=20, curve_progress_pct=3, graduation_confidence="high",
        ))
        assert badge.tier == TIER_AT_RISK

    def test_at_risk_many_whales(self):
        badge = compute_badge(**_base_metrics(
            whale_count=4, top_holder_pct=15, age_hours=5,
        ))
        assert badge.tier == TIER_AT_RISK

    def test_healthy_requires_all_signals(self):
        badge = compute_badge(**_base_metrics(
            age_hours=2, buy_sell_ratio=1.5, holder_velocity=10,
            top_holder_pct=15, health_score=70, curve_progress_pct=30,
        ))
        assert badge.tier == TIER_HEALTHY

    def test_healthy_blocked_by_low_velocity(self):
        badge = compute_badge(**_base_metrics(
            age_hours=2, buy_sell_ratio=1.5, holder_velocity=2,  # too low
            top_holder_pct=15, health_score=70,
        ))
        assert badge.tier != TIER_HEALTHY

    def test_observed_is_default(self):
        badge = compute_badge(**_base_metrics(age_hours=0.5))
        assert badge.tier == TIER_OBSERVED


class TestBadgeDeterminism:
    def test_same_input_same_output(self):
        metrics = _base_metrics(
            curve_progress_pct=50, buy_sell_ratio=1.3, holder_velocity=8,
            top_holder_pct=12, age_hours=3, health_score=65,
        )
        b1 = compute_badge(**metrics)
        b2 = compute_badge(**metrics)
        assert b1.tier == b2.tier
        assert b1.why == b2.why
        assert b1.metrics_snapshot == b2.metrics_snapshot

    def test_every_badge_includes_why(self):
        for overrides in [
            {"curve_progress_pct": 100},
            {"top_holder_pct": 45, "age_hours": 5},
            {"age_hours": 2, "buy_sell_ratio": 1.5, "holder_velocity": 10, "top_holder_pct": 15, "health_score": 70},
            {"curve_progress_pct": 75, "buy_sell_ratio": 1.5, "top_holder_pct": 15},
            {},  # observed path
        ]:
            badge = compute_badge(**_base_metrics(**overrides))
            assert isinstance(badge.why, list)
            assert len(badge.why) > 0
            for rule in badge.why:
                assert "rule" in rule and "metric" in rule and "value" in rule
                assert "threshold" in rule and "operator" in rule and "passed" in rule

    def test_metrics_snapshot_is_serializable(self):
        badge = compute_badge(**_base_metrics())
        snap = badge.metrics_snapshot
        # Every value must be JSON-safe (no floats like inf, no custom types)
        import json
        json.dumps(snap)


class TestBadgeFromRanking:
    def test_ranking_fallback_graduated(self):
        badge = badge_from_ranking(
            curve_progress_pct=100, holders=500, increase_pct=20, graduation_confidence="high",
        )
        assert badge.tier == TIER_GRADUATED

    def test_ranking_fallback_observed_for_new_token(self):
        badge = badge_from_ranking(
            curve_progress_pct=5, holders=10, increase_pct=0, graduation_confidence="high",
        )
        assert badge.tier == TIER_OBSERVED

    def test_ranking_low_confidence_blocks_watch(self):
        # High curve but low-confidence target → cannot earn graduation watch
        badge = badge_from_ranking(
            curve_progress_pct=80, holders=100, increase_pct=50, graduation_confidence="low",
        )
        assert badge.tier != TIER_GRADUATION_WATCH
