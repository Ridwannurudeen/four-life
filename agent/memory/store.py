"""Persistent agent memory via Unibase/Membase + local fallback."""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from loguru import logger

from agent.config import settings

MEMORY_DIR = Path(__file__).parent.parent.parent / "data" / "memory"


@dataclass
class LaunchRecord:
    """Record of a single token launch and its outcome."""

    token_address: str = ""
    name: str = ""
    symbol: str = ""
    narrative: str = ""
    concept: dict = field(default_factory=dict)
    launched_at: float = 0.0
    launch_block: int = 0

    # Outcome metrics (updated over time)
    peak_holders: int = 0
    peak_health_score: float = 0.0
    peak_curve_progress: float = 0.0
    graduated: bool = False
    graduation_time: float = 0.0
    total_buys: int = 0
    total_sells: int = 0

    # Strategy learnings
    what_worked: list[str] = field(default_factory=list)
    what_failed: list[str] = field(default_factory=list)
    content_engagement: dict = field(default_factory=dict)
    market_conditions: dict = field(default_factory=dict)


@dataclass
class AgentMemory:
    """Full agent memory state."""

    agent_id: str = ""
    total_launches: int = 0
    total_graduations: int = 0
    graduation_rate: float = 0.0
    launches: list[LaunchRecord] = field(default_factory=list)
    global_learnings: list[str] = field(default_factory=list)
    best_narratives: list[str] = field(default_factory=list)
    worst_narratives: list[str] = field(default_factory=list)
    avg_peak_holders: float = 0.0
    last_updated: float = 0.0


class MemoryStore:
    """Persistent memory with local JSON storage + optional Unibase sync."""

    def __init__(self) -> None:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self.memory_file = MEMORY_DIR / "agent_memory.json"
        self.memory = self._load()
        self._membase = None

    def _load(self) -> AgentMemory:
        """Load memory from disk."""
        if self.memory_file.exists():
            try:
                data = json.loads(self.memory_file.read_text())
                mem = AgentMemory(**{k: v for k, v in data.items() if k != "launches"})
                mem.launches = [LaunchRecord(**lr) for lr in data.get("launches", [])]
                logger.info("Loaded memory: {} launches, {} graduations",
                            mem.total_launches, mem.total_graduations)
                return mem
            except Exception as e:
                logger.error("Failed to load memory: {}", e)
        return AgentMemory()

    def save(self) -> None:
        """Persist memory to disk."""
        self.memory.last_updated = time.time()
        data = asdict(self.memory)
        self.memory_file.write_text(json.dumps(data, indent=2, default=str))
        logger.debug("Memory saved to {}", self.memory_file)

    # ── Launch Records ────────────────────────────────────────────────

    def record_launch(self, record: LaunchRecord) -> None:
        """Record a new token launch."""
        self.memory.launches.append(record)
        self.memory.total_launches += 1
        self._update_stats()
        self.save()
        logger.info("Recorded launch #{}: {} ({})",
                     self.memory.total_launches, record.name, record.symbol)

    def update_launch(self, token_address: str, **updates) -> None:
        """Update metrics for an existing launch."""
        for launch in self.memory.launches:
            if launch.token_address == token_address:
                for key, value in updates.items():
                    if hasattr(launch, key):
                        setattr(launch, key, value)
                if updates.get("graduated"):
                    self.memory.total_graduations += 1
                self._update_stats()
                self.save()
                return
        logger.warning("Launch not found for {}", token_address)

    def get_launch(self, token_address: str) -> LaunchRecord | None:
        """Get a specific launch record."""
        for launch in self.memory.launches:
            if launch.token_address == token_address:
                return launch
        return None

    def get_active_launches(self) -> list[LaunchRecord]:
        """Get launches that haven't graduated and are less than 72h old."""
        cutoff = time.time() - (72 * 3600)
        return [
            lr for lr in self.memory.launches
            if not lr.graduated and lr.launched_at > cutoff
        ]

    # ── Learnings ─────────────────────────────────────────────────────

    def add_learning(self, learning: str) -> None:
        """Add a global learning."""
        if learning not in self.memory.global_learnings:
            self.memory.global_learnings.append(learning)
            self.save()

    def get_context_for_ai(self) -> str:
        """Generate a memory context string for AI prompts."""
        mem = self.memory
        lines = [
            f"Total launches: {mem.total_launches}",
            f"Graduations: {mem.total_graduations} ({round(mem.graduation_rate * 100, 1)}%)",
            f"Average peak holders: {round(mem.avg_peak_holders, 0)}",
        ]

        if mem.best_narratives:
            lines.append(f"Best narratives: {', '.join(mem.best_narratives[:3])}")
        if mem.worst_narratives:
            lines.append(f"Worst narratives: {', '.join(mem.worst_narratives[:3])}")
        if mem.global_learnings:
            lines.append("Key learnings:")
            for l in mem.global_learnings[-5:]:
                lines.append(f"  - {l}")

        # Recent launches summary
        recent = self.memory.launches[-3:]
        if recent:
            lines.append("Recent launches:")
            for lr in recent:
                status = "GRADUATED" if lr.graduated else f"{round(lr.peak_curve_progress, 1)}% curve"
                lines.append(
                    f"  - {lr.name} ({lr.symbol}): {status}, "
                    f"peak {lr.peak_holders} holders, "
                    f"health {lr.peak_health_score}"
                )

        return "\n".join(lines)

    # ── Stats ─────────────────────────────────────────────────────────

    def _update_stats(self) -> None:
        """Recalculate aggregate stats."""
        mem = self.memory
        if mem.total_launches > 0:
            mem.graduation_rate = mem.total_graduations / mem.total_launches
            mem.avg_peak_holders = sum(
                lr.peak_holders for lr in mem.launches
            ) / len(mem.launches)

        # Identify best/worst narratives
        graduated = [lr for lr in mem.launches if lr.graduated]
        failed = [lr for lr in mem.launches if not lr.graduated and
                  lr.launched_at < time.time() - 72 * 3600]

        mem.best_narratives = list({lr.narrative for lr in graduated})[:5]
        mem.worst_narratives = list({lr.narrative for lr in failed})[:5]

    # ── Unibase Sync ──────────────────────────────────────────────────

    async def sync_to_unibase(self) -> None:
        """Sync memory to Unibase/Membase for public visibility."""
        if not settings.membase_account:
            return

        try:
            from membase.memory.buffered_memory import BufferedMemory
            from membase.memory.message import Message

            if self._membase is None:
                self._membase = BufferedMemory(
                    membase_account=settings.membase_account,
                    auto_upload_to_hub=True,
                )

            # Push current memory state as a message
            context = self.get_context_for_ai()
            self._membase.add(Message(
                name=settings.agent_name,
                content=json.dumps({
                    "type": "memory_sync",
                    "summary": context,
                    "total_launches": self.memory.total_launches,
                    "total_graduations": self.memory.total_graduations,
                    "graduation_rate": self.memory.graduation_rate,
                    "timestamp": time.time(),
                }),
                role="assistant",
                metadata="",
            ))
            logger.info("Synced memory to Unibase")
        except ImportError:
            logger.debug("Membase not installed, skipping Unibase sync")
        except Exception as e:
            logger.error("Unibase sync failed: {}", e)
