"""Cryptographic attestation of DGrid LLM usage.

Every DGrid call is reduced to a deterministic digest (provider/model/task/
prompt-hash/response-hash/token-counts/timestamp) and folded into a rolling
SHA-256 hash chain. The chain's current head (``tip``) is the Merkle-equivalent
commitment to every call the agent has ever made.

Periodically we publish the tip on BNB Chain as a self-transaction with the
root encoded in the transaction's data field. Anyone with the txhash can
verify the root; anyone with the /api/dgrid/trace log can reconstruct the
chain and prove each call's inclusion.

This gives judges a non-repudiable answer to "did FOUR-LIFE actually use
DGrid?" — the answer is on-chain and independently verifiable.

Design choices:
- Hash chain instead of a full Merkle tree — simpler, equivalent for append-
  only audit. Each published root commits to every call that came before.
- Persisted to disk so the chain survives restarts (genesis resets would
  invalidate prior attestations).
- On-chain publish is opt-in via DGRID_ATTEST_ONCHAIN — by default we compute
  the chain but do not submit, to avoid spending BNB on every call.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional

GENESIS_HASH = hashlib.sha256(b"FOUR-LIFE DGrid attestation genesis v1").hexdigest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class AttestationChain:
    """Rolling SHA-256 hash chain of DGrid call digests.

    Not thread-safe; expects serial appends from one event-loop. If the agent
    ever grows to multiple workers, switch to a Redis-backed chain with an atomic
    append op.
    """

    def __init__(self, persist_path: Optional[Path] = None) -> None:
        self._tip: str = GENESIS_HASH
        self._count: int = 0
        self._persist_path = persist_path
        self._last_root: str | None = None
        self._last_txhash: str | None = None
        self._last_attest_ts: int = 0
        self._last_attest_count: int = 0
        self._load()

    @staticmethod
    def call_digest(
        *,
        provider: str,
        model: str,
        task: str,
        prompt_hash: str,
        response_hash: str,
        prompt_tokens: int,
        completion_tokens: int,
        ts_ms: int,
    ) -> str:
        """Deterministic digest of one DGrid call. Inputs are normalized so
        re-hashing the same call anywhere produces the same digest."""
        payload = json.dumps(
            {
                "provider": provider,
                "model": model,
                "task": task,
                "prompt_hash": prompt_hash,
                "response_hash": response_hash,
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "ts_ms": int(ts_ms),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return sha256_hex(payload)

    def peek_next_tip(self, digest: str) -> str:
        """Return the tip that *would* result from folding ``digest`` into the
        chain — without actually advancing. Used by callers that must durably
        persist the audit-log entry BEFORE committing the chain forward, so the
        log and the chain can't diverge on a partial write."""
        return sha256_hex((self._tip + digest).encode())

    def commit_tip(self, new_tip: str) -> str:
        """Advance the chain to ``new_tip`` (which the caller must have obtained
        from ``peek_next_tip``). Increments count and persists. Returns the new tip."""
        self._tip = new_tip
        self._count += 1
        self._save()
        return self._tip

    def append(self, digest: str) -> str:
        """Fold ``digest`` into the chain. Returns the new tip.

        NOTE: direct append is convenient but does not coordinate with the
        append-only audit log. Callers that maintain an audit log should use
        ``peek_next_tip`` + ``commit_tip`` with a log-write in between, so the
        chain only advances once the log entry is durably persisted."""
        new_tip = self.peek_next_tip(digest)
        return self.commit_tip(new_tip)

    def record_attestation(self, root: str, txhash: str, count: int) -> None:
        """Mark that ``root`` (committing to ``count`` calls) was published in ``txhash``."""
        self._last_root = root
        self._last_txhash = txhash
        self._last_attest_ts = int(time.time())
        self._last_attest_count = int(count)
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
            "num_calls_chained": self._count,
            "last_published_root": self._last_root,
            "last_published_txhash": self._last_txhash,
            "last_published_at": self._last_attest_ts,
            "last_published_count": self._last_attest_count,
            "unpublished_calls": max(0, self._count - self._last_attest_count),
            "genesis": GENESIS_HASH,
        }

    def _save(self) -> None:
        if not self._persist_path:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "tip": self._tip,
                "count": self._count,
                "last_root": self._last_root,
                "last_txhash": self._last_txhash,
                "last_attest_ts": self._last_attest_ts,
                "last_attest_count": self._last_attest_count,
            }
            self._persist_path.write_text(json.dumps(data))
        except Exception:
            # Persistence is best-effort — disk full shouldn't break LLM calls.
            pass

    def _load(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            data = json.loads(self._persist_path.read_text())
            self._tip = data.get("tip", GENESIS_HASH)
            self._count = int(data.get("count", 0))
            self._last_root = data.get("last_root")
            self._last_txhash = data.get("last_txhash")
            self._last_attest_ts = int(data.get("last_attest_ts", 0))
            self._last_attest_count = int(data.get("last_attest_count", 0))
        except Exception:
            # Corrupt file -> reset to genesis. Safer than refusing to boot.
            pass


def verify_chain(
    calls: list[dict],
    expected_root: str,
    *,
    expected_count: int | None = None,
) -> bool:
    """Independent verifier — fold every ``call_digest`` in ``calls`` (in
    order) into the genesis-seeded chain and return True iff the final tip
    equals ``expected_root``.

    Pass ``expected_count`` (e.g. ``num_calls_chained`` from
    ``/api/dgrid/audit``) to also assert the caller isn't silently truncating
    the chain — e.g. fetching one page of ``/api/dgrid/audit/calls`` and
    forgetting to paginate. Without the count check a short prefix would
    produce a different tip and return False without saying why.

    Judges can call this with the full output of ``/api/dgrid/audit/calls``
    and the ``current_root`` + ``num_calls_chained`` from ``/api/dgrid/audit``
    to prove the server's claim. No server-side trust required — the digests,
    expected root, and expected count are the only inputs.
    """
    if expected_count is not None and len(calls) != int(expected_count):
        return False
    tip = GENESIS_HASH
    for call in calls:
        digest = call.get("call_digest")
        if not digest:
            # Re-derive from the raw fields — lets callers verify even if
            # the API only gave them the primitive inputs.
            digest = AttestationChain.call_digest(
                provider=str(call.get("provider", "")),
                model=str(call.get("model", "")),
                task=str(call.get("task", "")),
                prompt_hash=str(call.get("prompt_hash", "")),
                response_hash=str(call.get("response_hash", "")),
                prompt_tokens=int(call.get("prompt_tokens", 0) or 0),
                completion_tokens=int(call.get("completion_tokens", 0) or 0),
                ts_ms=int(call.get("ts_ms", 0) or 0),
            )
        tip = sha256_hex((tip + digest).encode())
    return tip == expected_root


async def publish_root_onchain(root_hex: str) -> str:
    """Publish ``root_hex`` to BNB Chain as a self-transaction with the root in
    the tx data field. Returns the txhash.

    Opt-in: this function is only called when DGRID_ATTEST_ONCHAIN=true and a
    wallet private key is configured. Costs ~0.0001 BNB per attestation.
    """
    from web3 import Web3
    from eth_account import Account
    from agent.config import settings

    if not settings.private_key or not settings.wallet_address:
        raise RuntimeError("on-chain attestation requires PRIVATE_KEY + WALLET_ADDRESS")

    # Strip 0x, ensure 64 hex chars
    root_clean = root_hex.removeprefix("0x")
    if len(root_clean) != 64:
        raise ValueError(f"expected 64-hex root, got {len(root_clean)}")

    w3 = Web3(Web3.HTTPProvider(settings.bsc_rpc_url))
    acct = Account.from_key(settings.private_key)
    if acct.address.lower() != settings.wallet_address.lower():
        raise RuntimeError("PRIVATE_KEY does not match WALLET_ADDRESS")

    nonce = w3.eth.get_transaction_count(acct.address)
    gas_price = w3.eth.gas_price

    tx = {
        "nonce": nonce,
        "to": acct.address,  # self-tx — metadata anchor, no value movement
        "value": 0,
        "gas": 25_000,
        "gasPrice": gas_price,
        "data": "0x" + root_clean,
        "chainId": 56,
    }
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return "0x" + tx_hash.hex().removeprefix("0x")


class AttestationLog:
    """Append-only JSONL log of every DGrid call that contributes to the chain.

    The rolling ring buffer in the LLM client keeps only the last 200 calls for
    the live dashboard. That's fine for recent activity, but a judge who wants
    to verify the Merkle root for the full call history needs access to every
    digest. This log is that history — one line per call, append-only, so it
    can grow to millions of entries without losing the dashboard's responsiveness.

    Fields per line: ``{seq, ts_ms, provider, model, task, prompt_hash,
    response_hash, prompt_tokens, completion_tokens, call_digest, chain_tip}``.

    Reconstruct the chain: seed with ``GENESIS_HASH``, fold each
    ``call_digest`` in file order, expect the final hash to equal the last
    entry's ``chain_tip`` (and the ``current_root`` returned by ``/api/dgrid/audit``).
    """

    def __init__(self, persist_path: Optional[Path] = None) -> None:
        self._persist_path = persist_path
        # When persistence is disabled (tests), keep entries in-memory so the
        # endpoint still returns real data.
        self._in_memory: list[dict] = []

    def append(self, entry: dict) -> bool:
        """Durably append ``entry``. Returns True iff the entry is persisted
        where a restart-surviving reconstruction can find it.

        When ``persist_path`` is set we try to write the JSONL line to disk.
        On failure we still keep the entry in-memory (so the process doesn't
        lose it for the remainder of its life), but we return False so the
        caller knows the chain-tip corresponding to this entry is NOT durably
        recoverable from disk. Callers that treat the log as a Merkle witness
        must use that return value to decide whether to advance the chain."""
        if self._persist_path:
            try:
                self._persist_path.parent.mkdir(parents=True, exist_ok=True)
                with self._persist_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, separators=(",", ":"), sort_keys=True) + "\n")
                return True
            except Exception:
                # Keep in-memory copy for debugging / live dashboard, but signal
                # the caller that this entry is not durably recoverable.
                self._in_memory.append(entry)
                return False
        self._in_memory.append(entry)
        return True

    def read_range(self, offset: int, limit: int) -> list[dict]:
        """Return entries [offset, offset+limit) in insertion order."""
        offset = max(0, int(offset))
        limit = max(0, int(limit))
        if limit == 0:
            return []
        if self._persist_path and self._persist_path.exists():
            out: list[dict] = []
            try:
                with self._persist_path.open("r", encoding="utf-8") as f:
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
        if self._persist_path and self._persist_path.exists():
            try:
                with self._persist_path.open("r", encoding="utf-8") as f:
                    return sum(1 for line in f if line.strip())
            except Exception:
                return 0
        return len(self._in_memory)

    def clear_for_tests(self) -> None:
        self._in_memory.clear()
        if self._persist_path and self._persist_path.exists():
            try:
                self._persist_path.unlink()
            except Exception:
                pass


# Singletons — persisted to data/dgrid_attestation.json + data/dgrid_calls.jsonl
# by default. Disable persistence by setting DGRID_ATTEST_PERSIST=false (used
# by the test suite).
_chain: AttestationChain | None = None
_log: AttestationLog | None = None


def _persist_enabled() -> bool:
    return os.getenv("DGRID_ATTEST_PERSIST", "true").lower() not in ("false", "0", "no")


def _default_chain_path() -> Path | None:
    return Path("data/dgrid_attestation.json") if _persist_enabled() else None


def _default_log_path() -> Path | None:
    return Path("data/dgrid_calls.jsonl") if _persist_enabled() else None


def get_chain() -> AttestationChain:
    global _chain
    if _chain is None:
        _chain = AttestationChain(persist_path=_default_chain_path())
    return _chain


def get_log() -> AttestationLog:
    global _log
    if _log is None:
        _log = AttestationLog(persist_path=_default_log_path())
    return _log


def reset_chain_for_tests() -> None:
    """Test-only: reset the chain + log singletons so each test starts fresh."""
    global _chain, _log
    _chain = None
    _log = None
