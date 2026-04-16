"""Tests for the historical tier snapshot store — SQLite, deterministic, thread-safe."""

from pathlib import Path

import pytest

from agent.history import HistoryStore, MIN_KEEPALIVE_SECONDS


@pytest.fixture
def store(tmp_path: Path) -> HistoryStore:
    return HistoryStore(db_path=tmp_path / "history.db")


TOKEN = "0xAbC0000000000000000000000000000000000001"
METRICS = {
    "curve_progress_pct": 45.0,
    "phase": "nurture",
    "health_score": 72.0,
    "buy_sell_ratio": 1.4,
    "holder_velocity": 8.0,
    "top_holder_pct": 12.0,
    "age_hours": 3.5,
    "graduation_confidence": "high",
    "unique_buyers": 210,
    "whale_count": 0,
    "contract_risk_score": 0,
}
WHY = [
    {"rule": "buy_pressure", "metric": "buy_sell_ratio", "value": 1.4, "threshold": 1.2, "operator": ">=", "passed": True},
]


class TestRecord:
    def test_first_write_inserts(self, store: HistoryStore) -> None:
        r = store.record(
            token_address=TOKEN, tier="healthy", metrics=METRICS, why=WHY,
            data_source="live_monitor", now=1_000,
        )
        assert r.written is True
        assert r.prev_tier is None
        assert r.tier == "healthy"
        rows = store.history(TOKEN)
        assert len(rows) == 1
        assert rows[0].tier == "healthy"
        assert rows[0].data_source == "live_monitor"
        assert rows[0].metrics["buy_sell_ratio"] == 1.4

    def test_unchanged_tier_within_keepalive_is_skipped(self, store: HistoryStore) -> None:
        store.record(token_address=TOKEN, tier="healthy", metrics=METRICS, why=WHY, now=1_000)
        r = store.record(token_address=TOKEN, tier="healthy", metrics=METRICS, why=WHY, now=1_060)
        assert r.written is False
        assert r.prev_tier == "healthy"
        assert len(store.history(TOKEN)) == 1

    def test_tier_change_always_writes(self, store: HistoryStore) -> None:
        store.record(token_address=TOKEN, tier="healthy", metrics=METRICS, why=WHY, now=1_000)
        r = store.record(token_address=TOKEN, tier="at_risk", metrics=METRICS, why=WHY, now=1_010)
        assert r.written is True
        assert r.prev_tier == "healthy"
        assert r.tier == "at_risk"
        rows = store.history(TOKEN)
        assert [row.tier for row in rows] == ["at_risk", "healthy"]

    def test_keepalive_after_window(self, store: HistoryStore) -> None:
        store.record(token_address=TOKEN, tier="healthy", metrics=METRICS, why=WHY, now=1_000)
        r = store.record(
            token_address=TOKEN, tier="healthy", metrics=METRICS, why=WHY,
            now=1_000 + MIN_KEEPALIVE_SECONDS,
        )
        assert r.written is True
        assert r.prev_tier == "healthy"  # same tier, just keepalive
        assert len(store.history(TOKEN)) == 2

    def test_address_casing_is_normalized(self, store: HistoryStore) -> None:
        store.record(token_address=TOKEN, tier="healthy", metrics=METRICS, why=WHY, now=1_000)
        rows = store.history(TOKEN.upper())
        assert len(rows) == 1
        assert rows[0].token_address == TOKEN.lower()

    def test_empty_address_returns_not_written(self, store: HistoryStore) -> None:
        r = store.record(token_address="", tier="healthy", metrics=METRICS, why=WHY)
        assert r.written is False


class TestQuery:
    def test_history_is_newest_first(self, store: HistoryStore) -> None:
        for ts, tier in [(1_000, "healthy"), (2_000, "at_risk"), (3_000, "graduated")]:
            store.record(token_address=TOKEN, tier=tier, metrics=METRICS, why=WHY, now=ts)
        rows = store.history(TOKEN)
        assert [r.tier for r in rows] == ["graduated", "at_risk", "healthy"]

    def test_history_since_filter(self, store: HistoryStore) -> None:
        for ts, tier in [(1_000, "healthy"), (2_000, "at_risk"), (3_000, "graduated")]:
            store.record(token_address=TOKEN, tier=tier, metrics=METRICS, why=WHY, now=ts)
        rows = store.history(TOKEN, since=2_000)
        assert [r.tier for r in rows] == ["graduated", "at_risk"]

    def test_history_limit(self, store: HistoryStore) -> None:
        for i in range(5):
            store.record(
                token_address=TOKEN,
                tier="healthy" if i % 2 == 0 else "at_risk",
                metrics=METRICS, why=WHY, now=1_000 + i * 1_000,
            )
        assert len(store.history(TOKEN, limit=2)) == 2

    def test_transitions_only_returns_changes(self, store: HistoryStore) -> None:
        tier_seq = [
            (1_000, "observed"),
            (1_400, "observed"),  # keepalive within window → skipped by record
            (2_000, "healthy"),   # change
            (2_400, "healthy"),   # keepalive within window → skipped
            (3_000, "at_risk"),   # change
            (4_000, "at_risk"),   # 1000s gap > keepalive → written, but not a transition
        ]
        for ts, tier in tier_seq:
            store.record(token_address=TOKEN, tier=tier, metrics=METRICS, why=WHY, now=ts)
        transitions = store.transitions(TOKEN)
        tiers = [t.tier for t in transitions]
        assert tiers == ["at_risk", "healthy", "observed"]

    def test_latest_returns_most_recent(self, store: HistoryStore) -> None:
        store.record(token_address=TOKEN, tier="healthy", metrics=METRICS, why=WHY, now=1_000)
        store.record(token_address=TOKEN, tier="at_risk", metrics=METRICS, why=WHY, now=2_000)
        latest = store.latest(TOKEN)
        assert latest is not None
        assert latest.tier == "at_risk"
        assert latest.recorded_at == 2_000

    def test_tokens_with_history_sorted_by_activity(self, store: HistoryStore) -> None:
        a = "0x" + "11" * 20
        b = "0x" + "22" * 20
        store.record(token_address=a, tier="healthy", metrics=METRICS, why=WHY, now=1_000)
        store.record(token_address=b, tier="healthy", metrics=METRICS, why=WHY, now=2_000)
        tokens = store.tokens_with_history()
        assert tokens[0] == b.lower()
        assert tokens[1] == a.lower()


class TestDiff:
    def test_diff_empty_when_no_data(self, store: HistoryStore) -> None:
        d = store.diff(TOKEN, since=1_000)
        assert d["snapshots_count"] == 0
        assert d["tier_changes"] == []
        assert d["first"] is None

    def test_diff_summarizes_tier_changes(self, store: HistoryStore) -> None:
        for ts, tier in [(1_000, "healthy"), (2_000, "at_risk"), (3_000, "graduated")]:
            store.record(token_address=TOKEN, tier=tier, metrics=METRICS, why=WHY, now=ts)
        d = store.diff(TOKEN, since=1_000)
        assert d["snapshots_count"] == 3
        assert len(d["tier_changes"]) == 2
        assert d["tier_changes"][0] == {
            "from": "healthy",
            "to": "at_risk",
            "at": 2_000,
            "why": WHY,
        }
        assert d["tier_changes"][1]["to"] == "graduated"
        assert d["first"]["tier"] == "healthy"
        assert d["last"]["tier"] == "graduated"
        assert d["keepalive_count"] == 1  # 3 snapshots - 2 tier changes

    def test_diff_respects_since_lower_bound(self, store: HistoryStore) -> None:
        for ts, tier in [(1_000, "healthy"), (2_000, "at_risk"), (3_000, "graduated")]:
            store.record(token_address=TOKEN, tier=tier, metrics=METRICS, why=WHY, now=ts)
        d = store.diff(TOKEN, since=2_500)
        assert d["snapshots_count"] == 1
        assert d["tier_changes"] == []  # only one row after 2_500 → no prior tier to compare
        assert d["first"]["tier"] == "graduated"


class TestPersistence:
    def test_store_reopens_cleanly(self, tmp_path: Path) -> None:
        path = tmp_path / "history.db"
        a = HistoryStore(db_path=path)
        a.record(token_address=TOKEN, tier="healthy", metrics=METRICS, why=WHY, now=1_000)
        b = HistoryStore(db_path=path)
        rows = b.history(TOKEN)
        assert len(rows) == 1
        assert rows[0].tier == "healthy"

    def test_metrics_and_why_roundtrip(self, store: HistoryStore) -> None:
        store.record(token_address=TOKEN, tier="healthy", metrics=METRICS, why=WHY, now=1_000)
        row = store.history(TOKEN)[0]
        assert row.metrics == METRICS
        assert row.why == WHY
