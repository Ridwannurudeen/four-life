"""Tests for Protection Mode — pure evaluator + persistent policy store."""

from pathlib import Path

import pytest

from agent.protection import (
    DEFAULT_POLICY,
    LEVEL_CRITICAL,
    LEVEL_SAFE,
    LEVEL_WARN,
    ProtectionPolicy,
    ProtectionStore,
    evaluate_protection,
)


TOKEN = "0xAbC0000000000000000000000000000000000001"


def _safe_kwargs(**overrides):
    base = dict(
        token_address=TOKEN,
        policy=None,
        top_holder_pct=10.0,
        whale_count=0,
        buy_sell_ratio=1.5,
        age_hours=5.0,
        contract_risk_score=0,
    )
    base.update(overrides)
    return base


class TestEvaluator:
    def test_no_risk_returns_safe(self):
        v = evaluate_protection(**_safe_kwargs())
        assert v.level == LEVEL_SAFE
        assert v.fired_rules == []
        assert v.recommended_actions == []

    def test_contract_rug_is_critical(self):
        v = evaluate_protection(**_safe_kwargs(contract_risk_score=80))
        assert v.level == LEVEL_CRITICAL
        assert any(r.rule == "contract_rug_critical" for r in v.fired_rules)
        assert "halt_content_posts" in v.recommended_actions

    def test_contract_risk_warn_band(self):
        v = evaluate_protection(**_safe_kwargs(contract_risk_score=45))
        assert v.level == LEVEL_WARN
        assert any(r.rule == "contract_risk_elevated" for r in v.fired_rules)

    def test_whale_concentration_warn(self):
        v = evaluate_protection(**_safe_kwargs(top_holder_pct=42))
        assert v.level == LEVEL_WARN
        assert any(r.rule == "whale_concentration_warn" for r in v.fired_rules)

    def test_whale_concentration_critical(self):
        v = evaluate_protection(**_safe_kwargs(top_holder_pct=60))
        assert v.level == LEVEL_CRITICAL
        assert any(r.rule == "whale_concentration_critical" for r in v.fired_rules)

    def test_whale_cluster_critical(self):
        v = evaluate_protection(**_safe_kwargs(whale_count=6))
        assert v.level == LEVEL_CRITICAL
        assert any(r.rule == "whale_cluster_critical" for r in v.fired_rules)

    def test_sell_pressure_critical_only_after_age(self):
        # Young token with bad ratio → NOT critical
        v_young = evaluate_protection(**_safe_kwargs(buy_sell_ratio=0.1, age_hours=0.5))
        assert v_young.level == LEVEL_SAFE
        # Old token with same ratio → critical
        v_old = evaluate_protection(**_safe_kwargs(buy_sell_ratio=0.1, age_hours=10))
        assert v_old.level == LEVEL_CRITICAL
        assert any(r.rule == "sell_pressure_critical" for r in v_old.fired_rules)

    def test_sell_pressure_warn_band(self):
        v = evaluate_protection(**_safe_kwargs(buy_sell_ratio=0.4, age_hours=5))
        assert v.level == LEVEL_WARN
        assert any(r.rule == "sell_pressure_warn" for r in v.fired_rules)

    def test_multiple_rules_escalate_to_critical(self):
        v = evaluate_protection(**_safe_kwargs(top_holder_pct=42, contract_risk_score=80))
        # whale_concentration_warn + contract_rug_critical → overall critical
        assert v.level == LEVEL_CRITICAL
        rules = {r.rule for r in v.fired_rules}
        assert "contract_rug_critical" in rules
        assert "whale_concentration_warn" in rules

    def test_inactive_policy_short_circuits_to_safe(self):
        policy = ProtectionPolicy(token_address=TOKEN, active=False)
        v = evaluate_protection(**_safe_kwargs(policy=policy, top_holder_pct=80, contract_risk_score=80))
        assert v.level == LEVEL_SAFE
        assert v.fired_rules == []

    def test_custom_policy_thresholds_applied(self):
        # Stricter whale threshold: 25% warn, 35% critical
        policy = ProtectionPolicy(
            token_address=TOKEN,
            max_whale_concentration=25,
            critical_whale_concentration=35,
        )
        v = evaluate_protection(**_safe_kwargs(policy=policy, top_holder_pct=30))
        assert v.level == LEVEL_WARN
        v2 = evaluate_protection(**_safe_kwargs(policy=policy, top_holder_pct=40))
        assert v2.level == LEVEL_CRITICAL

    def test_thresholds_returned_with_defaults(self):
        v = evaluate_protection(**_safe_kwargs())
        assert v.thresholds["critical_whale_concentration"] == DEFAULT_POLICY["critical_whale_concentration"]
        assert "max_contract_risk" in v.thresholds


@pytest.fixture
def store(tmp_path: Path) -> ProtectionStore:
    return ProtectionStore(db_path=tmp_path / "protection.db")


class TestStore:
    def test_upsert_creates(self, store: ProtectionStore):
        p = store.upsert_policy(ProtectionPolicy(
            token_address=TOKEN, max_whale_concentration=30,
        ))
        assert p.token_address == TOKEN.lower()
        assert p.max_whale_concentration == 30
        assert p.created_at > 0
        assert p.updated_at > 0

    def test_get_policy_returns_stored_values(self, store: ProtectionStore):
        store.upsert_policy(ProtectionPolicy(
            token_address=TOKEN, active=True,
            max_whale_concentration=28, critical_contract_risk=80,
        ))
        p = store.get_policy(TOKEN)
        assert p is not None
        assert p.max_whale_concentration == 28
        assert p.critical_contract_risk == 80

    def test_upsert_preserves_created_at(self, store: ProtectionStore):
        p1 = store.upsert_policy(ProtectionPolicy(token_address=TOKEN))
        p2 = store.upsert_policy(ProtectionPolicy(
            token_address=TOKEN, max_whale_concentration=22,
        ))
        assert p2.created_at == p1.created_at
        assert p2.updated_at >= p1.updated_at

    def test_list_excludes_inactive_when_requested(self, store: ProtectionStore):
        store.upsert_policy(ProtectionPolicy(token_address=TOKEN, active=True))
        store.upsert_policy(ProtectionPolicy(token_address="0x" + "22" * 20, active=False))
        all_ = store.list_policies(include_inactive=True)
        active = store.list_policies(include_inactive=False)
        assert len(all_) == 2
        assert len(active) == 1
        assert active[0].token_address == TOKEN.lower()

    def test_delete_removes_policy_and_level(self, store: ProtectionStore):
        store.upsert_policy(ProtectionPolicy(token_address=TOKEN))
        store.record_level(
            token_address=TOKEN,
            verdict=evaluate_protection(**_safe_kwargs(top_holder_pct=60)),
        )
        assert store.delete_policy(TOKEN) is True
        assert store.get_policy(TOKEN) is None
        assert store.get_level(TOKEN) == (None, None)

    def test_token_address_normalization(self, store: ProtectionStore):
        store.upsert_policy(ProtectionPolicy(token_address=TOKEN.upper()))
        assert store.get_policy(TOKEN.lower()) is not None
        assert store.get_policy(TOKEN.upper()) is not None

    def test_empty_token_rejected(self, store: ProtectionStore):
        with pytest.raises(ValueError):
            store.upsert_policy(ProtectionPolicy(token_address=""))


class TestLevelTracking:
    def test_record_level_reports_first_transition(self, store: ProtectionStore):
        v = evaluate_protection(**_safe_kwargs(top_holder_pct=60))
        transitioned, prev = store.record_level(token_address=TOKEN, verdict=v, now=1_000)
        assert transitioned is True
        assert prev is None
        assert store.get_level(TOKEN) == (LEVEL_CRITICAL, 1_000)

    def test_same_level_is_not_a_transition(self, store: ProtectionStore):
        v = evaluate_protection(**_safe_kwargs(top_holder_pct=60))
        store.record_level(token_address=TOKEN, verdict=v, now=1_000)
        t, prev = store.record_level(token_address=TOKEN, verdict=v, now=2_000)
        assert t is False
        assert prev == LEVEL_CRITICAL

    def test_level_change_is_a_transition(self, store: ProtectionStore):
        v_critical = evaluate_protection(**_safe_kwargs(top_holder_pct=60))
        v_safe = evaluate_protection(**_safe_kwargs(top_holder_pct=5))
        store.record_level(token_address=TOKEN, verdict=v_critical, now=1_000)
        t, prev = store.record_level(token_address=TOKEN, verdict=v_safe, now=2_000)
        assert t is True
        assert prev == LEVEL_CRITICAL
        assert store.get_level(TOKEN) == (LEVEL_SAFE, 2_000)
