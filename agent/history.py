"""Historical tier snapshots — persistent time-series for every token FOUR-LIFE grades.

Each call to `/api/token/{addr}/badge` or `/api/health-score/{addr}` flows through
`HistoryStore.record()`. The store deduplicates by (a) always writing when the tier
changes and (b) writing a keepalive row at most once per `MIN_KEEPALIVE_SECONDS` so a
steady-state token does not spam the DB.

The store is intentionally simple: a single SQLite file at `data/history.db`, one table,
one index. Queries return newest-first lists of dicts ready to serialize through FastAPI.

Deterministic. No LLM. No external services.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


HISTORY_DIR = Path(__file__).parent.parent / "data"
HISTORY_FILE = HISTORY_DIR / "history.db"

# Write a keepalive snapshot at most once per window, even if the tier is unchanged.
# Tier changes always write regardless of this interval.
MIN_KEEPALIVE_SECONDS = 300  # 5 minutes

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_address TEXT NOT NULL,
    tier TEXT NOT NULL,
    risk_level TEXT,
    curve_progress_pct REAL,
    health_score REAL,
    buy_sell_ratio REAL,
    holder_velocity REAL,
    top_holder_pct REAL,
    age_hours REAL,
    unique_buyers INTEGER,
    whale_count INTEGER,
    contract_risk_score INTEGER,
    why_json TEXT,
    metrics_json TEXT,
    data_source TEXT,
    recorded_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_token_time
    ON snapshots (token_address, recorded_at DESC);
"""


@dataclass
class Snapshot:
    token_address: str
    tier: str
    risk_level: str | None
    metrics: dict
    why: list[dict]
    data_source: str | None
    recorded_at: int
    id: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "token_address": self.token_address,
            "tier": self.tier,
            "risk_level": self.risk_level,
            "metrics": self.metrics,
            "why": self.why,
            "data_source": self.data_source,
            "recorded_at": self.recorded_at,
        }


@dataclass
class RecordResult:
    """Outcome of a `HistoryStore.record()` call. A transition occurred when
    `prev_tier is not None and prev_tier != tier`."""
    written: bool
    prev_tier: str | None
    tier: str
    recorded_at: int


class HistoryStore:
    """SQLite-backed tier snapshot store.

    Thread-safe: uses `check_same_thread=False` plus a write lock. Reads are cheap
    under SQLite's shared-cache semantics so they don't need the lock.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else HISTORY_FILE
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def record(
        self,
        *,
        token_address: str,
        tier: str,
        metrics: dict,
        why: list[dict],
        risk_level: str | None = None,
        data_source: str | None = None,
        now: int | None = None,
    ) -> RecordResult:
        """Insert a snapshot if the tier changed, or if MIN_KEEPALIVE_SECONDS has
        elapsed since the last write for this token.

        Returns a RecordResult describing whether a row was written and what the
        previous tier was (None if this was the first snapshot for the token).
        """
        ts = now if now is not None else int(time.time())
        token_key = (token_address or "").lower()
        if not token_key:
            return RecordResult(written=False, prev_tier=None, tier=tier, recorded_at=ts)

        with self._write_lock:
            with self._connect() as conn:
                last = conn.execute(
                    "SELECT tier, recorded_at FROM snapshots "
                    "WHERE token_address = ? ORDER BY recorded_at DESC LIMIT 1",
                    (token_key,),
                ).fetchone()

                prev_tier = last["tier"] if last is not None else None

                if last is not None:
                    tier_unchanged = last["tier"] == tier
                    within_keepalive = (ts - int(last["recorded_at"])) < MIN_KEEPALIVE_SECONDS
                    if tier_unchanged and within_keepalive:
                        return RecordResult(
                            written=False, prev_tier=prev_tier, tier=tier, recorded_at=ts,
                        )

                conn.execute(
                    """
                    INSERT INTO snapshots (
                        token_address, tier, risk_level,
                        curve_progress_pct, health_score, buy_sell_ratio,
                        holder_velocity, top_holder_pct, age_hours,
                        unique_buyers, whale_count, contract_risk_score,
                        why_json, metrics_json, data_source, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        token_key,
                        tier,
                        risk_level,
                        _num(metrics.get("curve_progress_pct")),
                        _num(metrics.get("health_score")),
                        _num(metrics.get("buy_sell_ratio")),
                        _num(metrics.get("holder_velocity")),
                        _num(metrics.get("top_holder_pct")),
                        _num(metrics.get("age_hours")),
                        _int(metrics.get("unique_buyers")),
                        _int(metrics.get("whale_count")),
                        _int(metrics.get("contract_risk_score")),
                        json.dumps(why, separators=(",", ":")),
                        json.dumps(metrics, separators=(",", ":")),
                        data_source,
                        ts,
                    ),
                )
                conn.commit()
        return RecordResult(written=True, prev_tier=prev_tier, tier=tier, recorded_at=ts)

    def history(
        self,
        token_address: str,
        *,
        limit: int = 100,
        since: int | None = None,
    ) -> list[Snapshot]:
        """Return snapshots newest-first. Caps at `limit` rows."""
        token_key = (token_address or "").lower()
        limit = max(1, min(int(limit), 1000))
        query = (
            "SELECT * FROM snapshots WHERE token_address = ?"
            + (" AND recorded_at >= ?" if since is not None else "")
            + " ORDER BY recorded_at DESC LIMIT ?"
        )
        params: list[Any] = [token_key]
        if since is not None:
            params.append(int(since))
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_snapshot(r) for r in rows]

    def transitions(
        self,
        token_address: str,
        *,
        since: int | None = None,
        limit: int = 100,
    ) -> list[Snapshot]:
        """Return only rows where the tier changed from the previous row. Newest-first.

        SQLite doesn't have a LAG() in old versions; we read ordered rows (oldest-first)
        and emit only boundary rows, then reverse.
        """
        token_key = (token_address or "").lower()
        limit = max(1, min(int(limit), 1000))
        query = (
            "SELECT * FROM snapshots WHERE token_address = ?"
            + (" AND recorded_at >= ?" if since is not None else "")
            + " ORDER BY recorded_at ASC"
        )
        params: list[Any] = [token_key]
        if since is not None:
            params.append(int(since))

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        transitions: list[sqlite3.Row] = []
        prev_tier: str | None = None
        for r in rows:
            if r["tier"] != prev_tier:
                transitions.append(r)
                prev_tier = r["tier"]
        transitions = transitions[-limit:]
        transitions.reverse()
        return [_row_to_snapshot(r) for r in transitions]

    def diff(self, token_address: str, *, since: int) -> dict:
        """Summarize what changed since `since`: tier transitions + first/last snapshot.

        Shape: {
          token_address, since, now, first, last,
          tier_changes: [{from, to, at, why}],
          snapshots_count, keepalive_count
        }
        """
        token_key = (token_address or "").lower()
        since = int(since)
        now = int(time.time())

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM snapshots WHERE token_address = ? AND recorded_at >= ? "
                "ORDER BY recorded_at ASC",
                (token_key, since),
            ).fetchall()

        if not rows:
            return {
                "token_address": token_key,
                "since": since,
                "now": now,
                "first": None,
                "last": None,
                "tier_changes": [],
                "snapshots_count": 0,
                "keepalive_count": 0,
            }

        first = _row_to_snapshot(rows[0])
        last = _row_to_snapshot(rows[-1])

        tier_changes: list[dict] = []
        prev_tier: str | None = None
        for r in rows:
            if prev_tier is None:
                prev_tier = r["tier"]
                continue
            if r["tier"] != prev_tier:
                tier_changes.append(
                    {
                        "from": prev_tier,
                        "to": r["tier"],
                        "at": int(r["recorded_at"]),
                        "why": json.loads(r["why_json"]) if r["why_json"] else [],
                    }
                )
                prev_tier = r["tier"]

        return {
            "token_address": token_key,
            "since": since,
            "now": now,
            "first": first.to_dict(),
            "last": last.to_dict(),
            "tier_changes": tier_changes,
            "snapshots_count": len(rows),
            "keepalive_count": len(rows) - len(tier_changes),
        }

    def latest(self, token_address: str) -> Snapshot | None:
        token_key = (token_address or "").lower()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM snapshots WHERE token_address = ? "
                "ORDER BY recorded_at DESC LIMIT 1",
                (token_key,),
            ).fetchone()
        return _row_to_snapshot(row) if row else None

    def tokens_with_history(self, limit: int = 500) -> list[str]:
        """Distinct token addresses with at least one snapshot, newest-activity first."""
        limit = max(1, min(int(limit), 5000))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT token_address, MAX(recorded_at) AS t FROM snapshots "
                "GROUP BY token_address ORDER BY t DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [r["token_address"] for r in rows]


def _row_to_snapshot(row: sqlite3.Row) -> Snapshot:
    return Snapshot(
        id=int(row["id"]),
        token_address=row["token_address"],
        tier=row["tier"],
        risk_level=row["risk_level"],
        metrics=json.loads(row["metrics_json"]) if row["metrics_json"] else {},
        why=json.loads(row["why_json"]) if row["why_json"] else [],
        data_source=row["data_source"],
        recorded_at=int(row["recorded_at"]),
    )


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# Module-level singleton. Consumers can construct their own with a custom path for tests.
_default_store: HistoryStore | None = None
_default_lock = threading.Lock()


def default_store() -> HistoryStore:
    global _default_store
    if _default_store is None:
        with _default_lock:
            if _default_store is None:
                _default_store = HistoryStore()
    return _default_store
