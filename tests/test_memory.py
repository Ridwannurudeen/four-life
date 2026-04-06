"""Tests for agent memory store."""

import json
import time
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.memory.store import MemoryStore, LaunchRecord, AgentMemory


@pytest.fixture
def tmp_memory_dir(tmp_path):
    """Use a temp dir for memory storage."""
    with patch("agent.memory.store.MEMORY_DIR", tmp_path):
        yield tmp_path


@pytest.fixture
def store(tmp_memory_dir):
    return MemoryStore()


class TestLaunchRecord:
    def test_defaults(self):
        lr = LaunchRecord()
        assert lr.token_address == ""
        assert lr.graduated is False
        assert lr.peak_holders == 0
        assert lr.what_worked == []
        assert lr.what_failed == []

    def test_create_with_values(self):
        lr = LaunchRecord(
            token_address="0xabc",
            name="TestToken",
            symbol="TEST",
            narrative="dog tokens",
            launched_at=time.time(),
        )
        assert lr.name == "TestToken"
        assert lr.symbol == "TEST"
        assert lr.narrative == "dog tokens"


class TestMemoryStore:
    def test_fresh_start(self, store):
        assert store.memory.total_launches == 0
        assert store.memory.total_graduations == 0
        assert store.memory.launches == []

    def test_record_launch(self, store):
        lr = LaunchRecord(
            token_address="0x123",
            name="MoonDog",
            symbol="MDOG",
            narrative="dog tokens",
            launched_at=time.time(),
        )
        store.record_launch(lr)

        assert store.memory.total_launches == 1
        assert len(store.memory.launches) == 1
        assert store.memory.launches[0].name == "MoonDog"

    def test_update_launch(self, store):
        lr = LaunchRecord(token_address="0x456", name="Test", symbol="TST")
        store.record_launch(lr)

        store.update_launch("0x456", peak_holders=500, peak_health_score=78.5)

        updated = store.get_launch("0x456")
        assert updated.peak_holders == 500
        assert updated.peak_health_score == 78.5

    def test_update_launch_graduation(self, store):
        lr = LaunchRecord(token_address="0x789", name="GradToken", symbol="GRAD")
        store.record_launch(lr)

        store.update_launch("0x789", graduated=True, graduation_time=time.time())

        assert store.memory.total_graduations == 1
        assert store.memory.graduation_rate == 1.0

    def test_multiple_launches_stats(self, store):
        for i in range(5):
            lr = LaunchRecord(
                token_address=f"0x{i:040x}",
                name=f"Token{i}",
                symbol=f"T{i}",
                peak_holders=100 * (i + 1),
                launched_at=time.time() - 100000,
            )
            store.record_launch(lr)

        # Graduate 2 of them
        store.update_launch(f"0x{'0' * 39}0", graduated=True)
        store.update_launch(f"0x{'0' * 39}1", graduated=True)

        assert store.memory.total_launches == 5
        assert store.memory.total_graduations == 2
        assert store.memory.graduation_rate == 0.4

    def test_persistence(self, tmp_memory_dir):
        store1 = MemoryStore()
        store1.record_launch(LaunchRecord(
            token_address="0xpersist",
            name="PersistToken",
            symbol="PRST",
        ))
        store1.save()

        # Load fresh
        store2 = MemoryStore()
        assert store2.memory.total_launches == 1
        assert store2.memory.launches[0].name == "PersistToken"

    def test_get_active_launches(self, store):
        # Active launch (recent)
        store.record_launch(LaunchRecord(
            token_address="0xactive",
            name="Active",
            symbol="ACT",
            launched_at=time.time() - 3600,  # 1h ago
        ))
        # Old launch (>72h)
        store.record_launch(LaunchRecord(
            token_address="0xold",
            name="Old",
            symbol="OLD",
            launched_at=time.time() - 300000,  # ~83h ago
        ))
        # Graduated
        store.record_launch(LaunchRecord(
            token_address="0xgrad",
            name="Grad",
            symbol="GRD",
            launched_at=time.time() - 1800,
            graduated=True,
        ))

        active = store.get_active_launches()
        assert len(active) == 1
        assert active[0].name == "Active"

    def test_add_learning(self, store):
        store.add_learning("Dog tokens work best at 14:00 UTC")
        store.add_learning("Avoid launching during weekends")

        assert len(store.memory.global_learnings) == 2
        assert "Dog tokens" in store.memory.global_learnings[0]

    def test_no_duplicate_learnings(self, store):
        store.add_learning("Test learning")
        store.add_learning("Test learning")  # duplicate

        assert len(store.memory.global_learnings) == 1

    def test_get_context_for_ai(self, store):
        store.record_launch(LaunchRecord(
            token_address="0xctx",
            name="ContextToken",
            symbol="CTX",
            narrative="AI agents",
            peak_holders=342,
            peak_health_score=67.5,
            peak_curve_progress=45.2,
        ))
        store.add_learning("AI narratives perform well on weekdays")

        ctx = store.get_context_for_ai()
        assert "Total launches: 1" in ctx
        assert "ContextToken" in ctx
        assert "AI narratives" in ctx
