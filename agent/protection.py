"""Protection mode — let a token owner declare defensive thresholds and have FOUR-LIFE
enforce them deterministically.

A `ProtectionPolicy` per token configures when FOUR-LIFE should *suppress* content
actions (e.g. stop tweeting the bag) and fire a `protection.level_changed` webhook so
the owner or integrators can react. The policy is evaluated in pure code from raw
metrics + contract-risk score — no LLM. Every verdict includes the list of rules that
fired, so the outcome is fully auditable.

Levels, highest first:
  - critical : at least one critical-severity rule fired. FOUR-LIFE halts non-safety
               posts, fires a webhook, and recommends a short hedge (if MYX is enabled).
  - warn     : a watch-list metric crossed a soft threshold. Still posts, but
               transparency is forced as the next post.
  - safe     : no rule fired.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


PROTECTION_DIR = Path(__file__).parent.parent / "data"
PROTECTION_FILE = PROTECTION_DIR / "protection.db"


LEVEL_SAFE = "safe"
LEVEL_WARN = "warn"
LEVEL_CRITICAL = "critical"

# Ordering for max(...) style aggregation
_LEVEL_RANK = {LEVEL_SAFE: 0, LEVEL_WARN: 1, LEVEL_CRITICAL: 2}

# Default thresholds if a policy leaves them unset. Chosen to be conservative — a
# token at these values is in real trouble, not just wobbling.
DEFAULT_POLICY = {
    "max_whale_concentration": 40.0,  # top_holder_pct ≥ → warn
    "critical_whale_concentration": 55.0,  # top_holder_pct ≥ → critical
    "min_buy_sell_ratio_after_hours": (2.0, 0.5),  # (age_hours, ratio) → warn below
    "critical_buy_sell_ratio": 0.25,  # buy_sell_ratio < and age > 2h → critical
    "max_contract_risk": 40,  # ≥ → warn
    "critical_contract_risk": 60,  # ≥ → critical (matches badge rug override)
    "max_whale_count": 3,  # ≥ → warn
    "critical_whale_count": 5,  # ≥ → critical
}


SCHEMA = """
CREATE TABLE IF NOT EXISTS protection_policies (
    token_address TEXT PRIMARY KEY,
    active INTEGER NOT NULL DEFAULT 1,
    config_json TEXT NOT NULL,
    created_by TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS protection_levels (
    token_address TEXT PRIMARY KEY,
    level TEXT NOT NULL,
    fired_rules_json TEXT NOT NULL,
    recorded_at INTEGER NOT NULL
);
"""


@dataclass
class ProtectionPolicy:
    token_address: str
    active: bool = True
    # Thresholds — None means "use default"
    max_whale_concentration: float | None = None
    critical_whale_concentration: float | None = None
    critical_buy_sell_ratio: float | None = None
    max_contract_risk: int | None = None
    critical_contract_risk: int | None = None
    max_whale_count: int | None = None
    critical_whale_count: int | None = None
    created_by: str | None = None
    created_at: int = 0
    updated_at: int = 0

    def effective(self) -> dict:
        """Return thresholds with defaults filled in."""
        out = dict(DEFAULT_POLICY)
        if self.max_whale_concentration is not None:
            out["max_whale_concentration"] = self.max_whale_concentration
        if self.critical_whale_concentration is not None:
            out["critical_whale_concentration"] = self.critical_whale_concentration
        if self.critical_buy_sell_ratio is not None:
            out["critical_buy_sell_ratio"] = self.critical_buy_sell_ratio
        if self.max_contract_risk is not None:
            out["max_contract_risk"] = self.max_contract_risk
        if self.critical_contract_risk is not None:
            out["critical_contract_risk"] = self.critical_contract_risk
        if self.max_whale_count is not None:
            out["max_whale_count"] = self.max_whale_count
        if self.critical_whale_count is not None:
            out["critical_whale_count"] = self.critical_whale_count
        return out

    def to_dict(self) -> dict:
        return {
            "token_address": self.token_address,
            "active": self.active,
            "thresholds": self.effective(),
            "overrides": {
                k: v for k, v in asdict(self).items()
                if k in (
                    "max_whale_concentration", "critical_whale_concentration",
                    "critical_buy_sell_ratio", "max_contract_risk",
                    "critical_contract_risk", "max_whale_count", "critical_whale_count",
                ) and v is not None
            },
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class FiredRule:
    rule: str
    metric: str
    value: float | int
    threshold: float | int
    operator: str
    severity: str  # "warn" | "critical"
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProtectionVerdict:
    token_address: str
    level: str
    fired_rules: list[FiredRule] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    thresholds: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "token_address": self.token_address,
            "level": self.level,
            "fired_rules": [r.to_dict() for r in self.fired_rules],
            "recommended_actions": list(self.recommended_actions),
            "thresholds": self.thresholds,
        }


def _upgrade(level: str, target: str) -> str:
    return target if _LEVEL_RANK[target] > _LEVEL_RANK[level] else level


def evaluate_protection(
    *,
    token_address: str,
    policy: ProtectionPolicy | None,
    top_holder_pct: float,
    whale_count: int,
    buy_sell_ratio: float,
    age_hours: float,
    contract_risk_score: int,
) -> ProtectionVerdict:
    """Evaluate a token against its protection policy. Pure — no I/O, no LLM.

    If `policy` is None, evaluates against DEFAULT_POLICY so untouched tokens still
    benefit from baseline protection.
    """
    active_policy = policy if policy and policy.active else ProtectionPolicy(
        token_address=token_address,
    )
    if policy and not policy.active:
        return ProtectionVerdict(
            token_address=token_address,
            level=LEVEL_SAFE,
            fired_rules=[],
            recommended_actions=[],
            thresholds=active_policy.effective(),
        )

    t = active_policy.effective()
    level = LEVEL_SAFE
    fired: list[FiredRule] = []

    # Contract rug — highest priority, evaluated first
    if contract_risk_score >= t["critical_contract_risk"]:
        level = _upgrade(level, LEVEL_CRITICAL)
        fired.append(FiredRule(
            rule="contract_rug_critical",
            metric="contract_risk_score",
            value=int(contract_risk_score),
            threshold=int(t["critical_contract_risk"]),
            operator=">=",
            severity="critical",
            message="Contract-level rug signals present (mint+blacklist, proxy+pause, etc).",
        ))
    elif contract_risk_score >= t["max_contract_risk"]:
        level = _upgrade(level, LEVEL_WARN)
        fired.append(FiredRule(
            rule="contract_risk_elevated",
            metric="contract_risk_score",
            value=int(contract_risk_score),
            threshold=int(t["max_contract_risk"]),
            operator=">=",
            severity="warn",
            message="Contract has elevated rug-risk markers.",
        ))

    # Whale concentration
    if top_holder_pct >= t["critical_whale_concentration"]:
        level = _upgrade(level, LEVEL_CRITICAL)
        fired.append(FiredRule(
            rule="whale_concentration_critical",
            metric="top_holder_pct",
            value=round(top_holder_pct, 2),
            threshold=float(t["critical_whale_concentration"]),
            operator=">=",
            severity="critical",
            message=f"Single-holder concentration {top_holder_pct:.1f}% exceeds critical threshold.",
        ))
    elif top_holder_pct >= t["max_whale_concentration"]:
        level = _upgrade(level, LEVEL_WARN)
        fired.append(FiredRule(
            rule="whale_concentration_warn",
            metric="top_holder_pct",
            value=round(top_holder_pct, 2),
            threshold=float(t["max_whale_concentration"]),
            operator=">=",
            severity="warn",
            message=f"Single-holder concentration {top_holder_pct:.1f}% above warning threshold.",
        ))

    # Whale cluster count
    if whale_count >= t["critical_whale_count"]:
        level = _upgrade(level, LEVEL_CRITICAL)
        fired.append(FiredRule(
            rule="whale_cluster_critical",
            metric="whale_count",
            value=int(whale_count),
            threshold=int(t["critical_whale_count"]),
            operator=">=",
            severity="critical",
            message=f"{whale_count} whale-sized holders (>5%) detected — coordinated exit risk.",
        ))
    elif whale_count >= t["max_whale_count"]:
        level = _upgrade(level, LEVEL_WARN)
        fired.append(FiredRule(
            rule="whale_cluster_warn",
            metric="whale_count",
            value=int(whale_count),
            threshold=int(t["max_whale_count"]),
            operator=">=",
            severity="warn",
            message=f"{whale_count} whale-sized holders above warning threshold.",
        ))

    # Sell pressure (only meaningful past the first 2h)
    warn_age, warn_ratio = t["min_buy_sell_ratio_after_hours"]
    if age_hours >= 2 and buy_sell_ratio > 0 and buy_sell_ratio < t["critical_buy_sell_ratio"]:
        level = _upgrade(level, LEVEL_CRITICAL)
        fired.append(FiredRule(
            rule="sell_pressure_critical",
            metric="buy_sell_ratio",
            value=round(buy_sell_ratio, 2),
            threshold=float(t["critical_buy_sell_ratio"]),
            operator="<",
            severity="critical",
            message=f"Sell pressure critical: buy/sell ratio {buy_sell_ratio:.2f} after {age_hours:.1f}h.",
        ))
    elif age_hours >= warn_age and buy_sell_ratio > 0 and buy_sell_ratio < warn_ratio:
        level = _upgrade(level, LEVEL_WARN)
        fired.append(FiredRule(
            rule="sell_pressure_warn",
            metric="buy_sell_ratio",
            value=round(buy_sell_ratio, 2),
            threshold=float(warn_ratio),
            operator="<",
            severity="warn",
            message=f"Sell pressure warning: buy/sell ratio {buy_sell_ratio:.2f}.",
        ))

    recommended: list[str] = []
    if level == LEVEL_CRITICAL:
        recommended = ["halt_content_posts", "fire_webhook_alert", "short_hedge_if_enabled"]
    elif level == LEVEL_WARN:
        recommended = ["force_transparency_post", "fire_webhook_alert"]

    return ProtectionVerdict(
        token_address=token_address,
        level=level,
        fired_rules=fired,
        recommended_actions=recommended,
        thresholds=t,
    )


# ── Store ─────────────────────────────────────────────────────────────


class ProtectionStore:
    """Persistent per-token protection policy + last-known verdict level."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else PROTECTION_FILE
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

    # ── Policies ─────────────────────────────────────────────────

    def upsert_policy(self, policy: ProtectionPolicy) -> ProtectionPolicy:
        """Create or update the policy for a token."""
        token_key = policy.token_address.lower()
        if not token_key:
            raise ValueError("token_address is required")
        now_ts = int(time.time())
        config = {
            "active": bool(policy.active),
            "max_whale_concentration": policy.max_whale_concentration,
            "critical_whale_concentration": policy.critical_whale_concentration,
            "critical_buy_sell_ratio": policy.critical_buy_sell_ratio,
            "max_contract_risk": policy.max_contract_risk,
            "critical_contract_risk": policy.critical_contract_risk,
            "max_whale_count": policy.max_whale_count,
            "critical_whale_count": policy.critical_whale_count,
        }
        with self._write_lock:
            with self._connect() as conn:
                existing = conn.execute(
                    "SELECT created_at FROM protection_policies WHERE token_address = ?",
                    (token_key,),
                ).fetchone()
                created_at = int(existing["created_at"]) if existing else now_ts
                conn.execute(
                    """
                    INSERT INTO protection_policies
                        (token_address, active, config_json, created_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(token_address) DO UPDATE SET
                        active = excluded.active,
                        config_json = excluded.config_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        token_key,
                        1 if policy.active else 0,
                        json.dumps(config, separators=(",", ":")),
                        policy.created_by,
                        created_at,
                        now_ts,
                    ),
                )
                conn.commit()
        return ProtectionPolicy(
            token_address=token_key,
            active=policy.active,
            max_whale_concentration=policy.max_whale_concentration,
            critical_whale_concentration=policy.critical_whale_concentration,
            critical_buy_sell_ratio=policy.critical_buy_sell_ratio,
            max_contract_risk=policy.max_contract_risk,
            critical_contract_risk=policy.critical_contract_risk,
            max_whale_count=policy.max_whale_count,
            critical_whale_count=policy.critical_whale_count,
            created_by=policy.created_by,
            created_at=created_at,
            updated_at=now_ts,
        )

    def get_policy(self, token_address: str) -> ProtectionPolicy | None:
        token_key = (token_address or "").lower()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM protection_policies WHERE token_address = ?",
                (token_key,),
            ).fetchone()
        if not row:
            return None
        return _row_to_policy(row)

    def list_policies(self, *, include_inactive: bool = True) -> list[ProtectionPolicy]:
        query = "SELECT * FROM protection_policies"
        if not include_inactive:
            query += " WHERE active = 1"
        query += " ORDER BY updated_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query).fetchall()
        return [_row_to_policy(r) for r in rows]

    def delete_policy(self, token_address: str) -> bool:
        token_key = (token_address or "").lower()
        with self._write_lock:
            with self._connect() as conn:
                cur = conn.execute(
                    "DELETE FROM protection_policies WHERE token_address = ?",
                    (token_key,),
                )
                conn.execute(
                    "DELETE FROM protection_levels WHERE token_address = ?",
                    (token_key,),
                )
                conn.commit()
                return cur.rowcount > 0

    # ── Last-known levels (for transition detection) ─────────────

    def get_level(self, token_address: str) -> tuple[str | None, int | None]:
        """Return the last recorded (level, recorded_at) for a token, or (None, None)."""
        token_key = (token_address or "").lower()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT level, recorded_at FROM protection_levels WHERE token_address = ?",
                (token_key,),
            ).fetchone()
        if not row:
            return (None, None)
        return (row["level"], int(row["recorded_at"]))

    def record_level(
        self,
        *,
        token_address: str,
        verdict: ProtectionVerdict,
        now: int | None = None,
    ) -> tuple[bool, str | None]:
        """Record a verdict. Returns (transitioned, prev_level). A transition means
        the level is different from the last-known level for this token."""
        token_key = (token_address or "").lower()
        ts = now if now is not None else int(time.time())
        with self._write_lock:
            with self._connect() as conn:
                prev = conn.execute(
                    "SELECT level FROM protection_levels WHERE token_address = ?",
                    (token_key,),
                ).fetchone()
                prev_level = prev["level"] if prev else None
                transitioned = prev_level != verdict.level
                conn.execute(
                    """
                    INSERT INTO protection_levels (token_address, level, fired_rules_json, recorded_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(token_address) DO UPDATE SET
                        level = excluded.level,
                        fired_rules_json = excluded.fired_rules_json,
                        recorded_at = excluded.recorded_at
                    """,
                    (
                        token_key,
                        verdict.level,
                        json.dumps([r.to_dict() for r in verdict.fired_rules], separators=(",", ":")),
                        ts,
                    ),
                )
                conn.commit()
        return (transitioned, prev_level)


def _row_to_policy(row: sqlite3.Row) -> ProtectionPolicy:
    cfg = json.loads(row["config_json"]) if row["config_json"] else {}
    return ProtectionPolicy(
        token_address=row["token_address"],
        active=bool(row["active"]),
        max_whale_concentration=cfg.get("max_whale_concentration"),
        critical_whale_concentration=cfg.get("critical_whale_concentration"),
        critical_buy_sell_ratio=cfg.get("critical_buy_sell_ratio"),
        max_contract_risk=cfg.get("max_contract_risk"),
        critical_contract_risk=cfg.get("critical_contract_risk"),
        max_whale_count=cfg.get("max_whale_count"),
        critical_whale_count=cfg.get("critical_whale_count"),
        created_by=row["created_by"],
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
    )


# Module-level singleton
_default_store: ProtectionStore | None = None
_default_lock = threading.Lock()


def default_store() -> ProtectionStore:
    global _default_store
    if _default_store is None:
        with _default_lock:
            if _default_store is None:
                _default_store = ProtectionStore()
    return _default_store
