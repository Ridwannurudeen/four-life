"""Persistent MYX signal + position log.

Complements the in-memory HedgeState by writing every signal and every position
transition to disk, so the frontend dashboard can show an unbounded history
(HedgeState is a 200-entry ring) and a judge can replay every trade decision
the agent has ever made on MYX.

Two append-only JSONL files:
- ``data/myx_signals.jsonl`` — one row per generated signal (action, confidence,
  reasoning, phase, token_address, ts_ms)
- ``data/myx_positions.jsonl`` — one row per position open / close with tx hash,
  collateral, size, price, reason, outcome

We also maintain a SHA-256 chain over the position events so the Merkle-style
proof-of-use story that worked for DGrid applies to MYX trades too — a single
on-chain root commits to every perp action the agent has taken.

Disabled via ``MYX_PERSIST=false`` in the test environment.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional


MYX_GENESIS = hashlib.sha256(b"FOUR-LIFE MYX trade attestation genesis v1").hexdigest()
MYX_SIGNAL_GENESIS = hashlib.sha256(b"FOUR-LIFE MYX signal attestation genesis v1").hexdigest()


def _persist_enabled() -> bool:
    return os.getenv("MYX_PERSIST", "true").lower() not in ("false", "0", "no")


def _default_path(name: str) -> Optional[Path]:
    if not _persist_enabled():
        return None
    return Path(f"data/{name}")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class MYXSignalLog:
    """Append-only signal log. Reads paginate from disk; unbounded history."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path
        self._in_memory: list[dict] = []

    def append(self, entry: dict) -> None:
        if self._path:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, separators=(",", ":"), sort_keys=True) + "\n")
                return
            except Exception:
                pass
        self._in_memory.append(entry)

    def read_range(self, offset: int, limit: int) -> list[dict]:
        offset = max(0, int(offset))
        limit = max(0, int(limit))
        if limit == 0:
            return []
        if self._path and self._path.exists():
            out: list[dict] = []
            try:
                with self._path.open("r", encoding="utf-8") as f:
                    for i, line in enumerate(f):
                        if i < offset:
                            continue
                        if len(out) >= limit:
                            break
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            out.append(json.loads(line))
                        except Exception:
                            continue
                return out
            except Exception:
                return []
        return self._in_memory[offset : offset + limit]

    def count(self) -> int:
        if self._path and self._path.exists():
            try:
                with self._path.open("r", encoding="utf-8") as f:
                    return sum(1 for line in f if line.strip())
            except Exception:
                return 0
        return len(self._in_memory)

    def tail(self, n: int = 50, token_address: str | None = None) -> list[dict]:
        """Return the last ``n`` entries (newest first). Filter by token_address if given."""
        total = self.count()
        if total == 0:
            return []
        # Simple approach: read the last chunk of the file
        rows = self.read_range(max(0, total - max(n * 4, 200)), max(n * 4, 200))
        if token_address:
            rows = [r for r in rows if r.get("token_address", "").lower() == token_address.lower()]
        rows.reverse()
        return rows[:n]

    def clear_for_tests(self) -> None:
        self._in_memory.clear()
        if self._path and self._path.exists():
            try:
                self._path.unlink()
            except Exception:
                pass


class MYXAttestationChain:
    """SHA-256 hash chain over MYX position events (open/close) for cryptographic
    proof of trading activity.

    Mirrors the DGrid attestation chain design. The tip is the commitment to every
    trade; it can be published on BNB Chain via a self-tx so anyone can verify
    the agent's trading history without trusting our server.
    """

    def __init__(self, persist_path: Optional[Path] = None) -> None:
        self._tip: str = MYX_GENESIS
        self._count: int = 0
        self._path = persist_path
        self._last_root: str | None = None
        self._last_txhash: str | None = None
        self._last_at: int = 0
        self._last_count: int = 0
        self._load()

    @staticmethod
    def event_digest(
        *,
        kind: str,  # "open" or "close"
        token_address: str,
        pair_index: int,
        is_long: bool,
        collateral_wei: int,
        size_amount: int,
        tx_hash: str,
        ts_ms: int,
    ) -> str:
        payload = json.dumps(
            {
                "kind": kind,
                "token_address": token_address.lower(),
                "pair_index": int(pair_index),
                "is_long": bool(is_long),
                "collateral_wei": str(int(collateral_wei)),
                "size_amount": str(int(size_amount)),
                "tx_hash": tx_hash.lower(),
                "ts_ms": int(ts_ms),
            },
            sort_keys=True, separators=(",", ":"),
        ).encode()
        return sha256_hex(payload)

    def append(self, digest: str) -> str:
        self._tip = sha256_hex((self._tip + digest).encode())
        self._count += 1
        self._save()
        return self._tip

    def record_attestation(self, root: str, txhash: str, count: int) -> None:
        self._last_root = root
        self._last_txhash = txhash
        self._last_at = int(time.time())
        self._last_count = int(count)
        self._save()

    @property
    def tip(self) -> str:
        return self._tip

    @property
    def count(self) -> int:
        return self._count

    def snapshot(self) -> dict:
        return {
            "current_root": self._tip,
            "num_events_chained": self._count,
            "last_published_root": self._last_root,
            "last_published_txhash": self._last_txhash,
            "last_published_at": self._last_at,
            "last_published_count": self._last_count,
            "unpublished_events": max(0, self._count - self._last_count),
            "genesis": MYX_GENESIS,
        }

    def _save(self) -> None:
        if not self._path:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "tip": self._tip, "count": self._count,
                "last_root": self._last_root, "last_txhash": self._last_txhash,
                "last_at": self._last_at, "last_count": self._last_count,
            }
            self._path.write_text(json.dumps(data))
        except Exception:
            pass

    def _load(self) -> None:
        if not self._path or not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self._tip = data.get("tip", MYX_GENESIS)
            self._count = int(data.get("count", 0))
            self._last_root = data.get("last_root")
            self._last_txhash = data.get("last_txhash")
            self._last_at = int(data.get("last_at", 0))
            self._last_count = int(data.get("last_count", 0))
        except Exception:
            pass


class MYXSignalAttestationChain:
    """Parallel Merkle chain over every signal (not just executed trades).

    Gives us cryptographic proof the agent made N decisions even before any
    execution happens — critical when execution is gated on router verification
    but we still want to anchor the agent's thinking on-chain.

    Design mirrors MYXAttestationChain but uses a different genesis so the two
    chains are distinguishable and publishable separately.
    """

    def __init__(self, persist_path: Optional[Path] = None) -> None:
        self._tip: str = MYX_SIGNAL_GENESIS
        self._count: int = 0
        self._path = persist_path
        self._last_root: str | None = None
        self._last_txhash: str | None = None
        self._last_at: int = 0
        self._last_count: int = 0
        self._load()

    @staticmethod
    def signal_digest(
        *,
        token_address: str,
        phase: str,
        action: str,
        confidence: float,
        size_pct: float,
        reasoning_hash: str,
        ts_ms: int,
        consensus_method: str | None = None,
        consensus_confidence: float | None = None,
    ) -> str:
        """Deterministic digest of one signal. Reasoning text is hashed (not
        raw) so the digest stays bounded and the on-chain root doesn't leak
        prompt content."""
        payload = json.dumps(
            {
                "token_address": token_address.lower(),
                "phase": phase,
                "action": action,
                "confidence": float(round(confidence, 4)),
                "size_pct": float(round(size_pct, 4)),
                "reasoning_hash": reasoning_hash,
                "ts_ms": int(ts_ms),
                "consensus_method": consensus_method or "",
                "consensus_confidence": float(round(consensus_confidence or 0.0, 4)),
            },
            sort_keys=True, separators=(",", ":"),
        ).encode()
        return sha256_hex(payload)

    def append(self, digest: str) -> str:
        self._tip = sha256_hex((self._tip + digest).encode())
        self._count += 1
        self._save()
        return self._tip

    def record_attestation(self, root: str, txhash: str, count: int) -> None:
        self._last_root = root
        self._last_txhash = txhash
        self._last_at = int(time.time())
        self._last_count = int(count)
        self._save()

    @property
    def tip(self) -> str:
        return self._tip

    @property
    def count(self) -> int:
        return self._count

    def snapshot(self) -> dict:
        return {
            "current_root": self._tip,
            "num_signals_chained": self._count,
            "last_published_root": self._last_root,
            "last_published_txhash": self._last_txhash,
            "last_published_at": self._last_at,
            "last_published_count": self._last_count,
            "unpublished_signals": max(0, self._count - self._last_count),
            "genesis": MYX_SIGNAL_GENESIS,
        }

    def _save(self) -> None:
        if not self._path:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "tip": self._tip, "count": self._count,
                "last_root": self._last_root, "last_txhash": self._last_txhash,
                "last_at": self._last_at, "last_count": self._last_count,
            }
            self._path.write_text(json.dumps(data))
        except Exception:
            pass

    def _load(self) -> None:
        if not self._path or not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self._tip = data.get("tip", MYX_SIGNAL_GENESIS)
            self._count = int(data.get("count", 0))
            self._last_root = data.get("last_root")
            self._last_txhash = data.get("last_txhash")
            self._last_at = int(data.get("last_at", 0))
            self._last_count = int(data.get("last_count", 0))
        except Exception:
            pass


def verify_myx_chain(events: list[dict], expected_root: str) -> bool:
    """Independent verifier for the MYX attestation chain.

    Given a list of position events (with ``event_digest`` pre-computed, or the
    raw fields needed to re-compute), fold into the genesis-seeded chain and
    check the final tip equals ``expected_root``.
    """
    tip = MYX_GENESIS
    for ev in events:
        digest = ev.get("event_digest")
        if not digest:
            digest = MYXAttestationChain.event_digest(
                kind=str(ev.get("kind", "")),
                token_address=str(ev.get("token_address", "")),
                pair_index=int(ev.get("pair_index", 0) or 0),
                is_long=bool(ev.get("is_long", False)),
                collateral_wei=int(ev.get("collateral_wei", 0) or 0),
                size_amount=int(ev.get("size_amount", 0) or 0),
                tx_hash=str(ev.get("tx_hash", "")),
                ts_ms=int(ev.get("ts_ms", 0) or 0),
            )
        tip = sha256_hex((tip + digest).encode())
    return tip == expected_root


def verify_myx_signal_chain(signals: list[dict], expected_root: str) -> bool:
    """Independent verifier for the MYX signal attestation chain. Same pattern
    as verify_myx_chain but folds signal_digest-shaped inputs."""
    tip = MYX_SIGNAL_GENESIS
    for s in signals:
        digest = s.get("signal_digest")
        if not digest:
            digest = MYXSignalAttestationChain.signal_digest(
                token_address=str(s.get("token_address", "")),
                phase=str(s.get("phase", "")),
                action=str(s.get("action", "")),
                confidence=float(s.get("confidence", 0) or 0),
                size_pct=float(s.get("size_pct", 0) or 0),
                reasoning_hash=str(s.get("reasoning_hash", "")),
                ts_ms=int(s.get("ts_ms", 0) or 0),
                consensus_method=s.get("consensus_method"),
                consensus_confidence=s.get("consensus_confidence"),
            )
        tip = sha256_hex((tip + digest).encode())
    return tip == expected_root


# Singletons
_signal_log: MYXSignalLog | None = None
_position_log: MYXSignalLog | None = None
_chain: MYXAttestationChain | None = None
_signal_chain: MYXSignalAttestationChain | None = None


def get_signal_log() -> MYXSignalLog:
    global _signal_log
    if _signal_log is None:
        _signal_log = MYXSignalLog(path=_default_path("myx_signals.jsonl"))
    return _signal_log


def get_position_log() -> MYXSignalLog:
    global _position_log
    if _position_log is None:
        _position_log = MYXSignalLog(path=_default_path("myx_positions.jsonl"))
    return _position_log


def get_myx_chain() -> MYXAttestationChain:
    global _chain
    if _chain is None:
        _chain = MYXAttestationChain(persist_path=_default_path("myx_attestation.json"))
    return _chain


def get_myx_signal_chain() -> MYXSignalAttestationChain:
    global _signal_chain
    if _signal_chain is None:
        _signal_chain = MYXSignalAttestationChain(persist_path=_default_path("myx_signal_attestation.json"))
    return _signal_chain


def reset_myx_for_tests() -> None:
    global _signal_log, _position_log, _chain, _signal_chain
    _signal_log = None
    _position_log = None
    _chain = None
    _signal_chain = None
