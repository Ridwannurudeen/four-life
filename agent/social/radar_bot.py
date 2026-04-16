"""FOUR-LIFE Radar Bot — broadcasts Certified tier transitions to X.

Polls the /api/graduation-radar endpoint every 5 minutes, diffs each token's
current tier against last-seen state, and posts deterministic alert templates
for transitions worth sharing: observed -> healthy, healthy -> graduation_watch,
any -> graduated, any -> at_risk.

Rate-limited, dedup'd, and defensive against X API outages.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import httpx
from loguru import logger

from agent.config import settings
from agent.social.twitter import TwitterClient


API_BASE = "https://four-life.gudman.xyz"
RADAR_BASE = "https://four-life.gudman.xyz/radar"
FOURMEME_BASE = "https://four.meme/token"

STATE_DIR = Path(__file__).parent.parent.parent / "data"
STATE_FILE = STATE_DIR / "radar_bot_state.json"
STATUS_FILE = STATE_DIR / "radar_bot_status.json"

TICK_INTERVAL_SECONDS = 300   # 5 minutes
ERROR_PAUSE_SECONDS = 600     # 10 minutes on X API error
MAX_POSTS_PER_HOUR = 6
POST_WINDOW_SECONDS = 3600
TWEET_LIMIT = 280


TIER_RANK = {"observed": 0, "healthy": 1, "graduation_watch": 2, "graduated": 3, "at_risk": -1}


def derive_tier(entry: dict) -> str:
    """Derive a tier for a radar entry using the same rules as the backend badge.

    Kept in sync with agent.badge.compute_badge; used before we fetch the
    heavier per-token /badge endpoint so the bot can decide whether to ask.
    """
    curve = float(entry.get("curve_progress", 0))
    conf = entry.get("confidence_score", "low")
    increase = float(entry.get("increase_pct", 0))
    if curve >= 100:
        return "graduated"
    if curve >= 70 and conf == "high" and increase >= 0:
        return "graduation_watch"
    # Ranking-based detection is coarse — we only flag at_risk on strong
    # negative momentum; the authoritative at_risk comes from /badge.
    if increase <= -50:
        return "at_risk"
    return "observed"


# ── State ────────────────────────────────────────────────────────────


@dataclass
class BotState:
    last_seen_tier: dict[str, str] = field(default_factory=dict)
    posted_transitions: dict[str, float] = field(default_factory=dict)   # "addr:tier" -> timestamp
    recent_post_times: list[float] = field(default_factory=list)
    last_tick_at: float = 0.0
    last_posted_at: float = 0.0
    last_error_at: float = 0.0
    last_error_message: str = ""
    pause_until: float = 0.0
    transitions_24h: int = 0
    transitions_log: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path = STATE_FILE) -> "BotState":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text())
            return cls(**data)
        except Exception as e:
            logger.error("Failed to load radar bot state: {}", e)
            return cls()

    def save(self, path: Path = STATE_FILE) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "last_seen_tier": self.last_seen_tier,
            "posted_transitions": self.posted_transitions,
            "recent_post_times": self.recent_post_times[-50:],
            "last_tick_at": self.last_tick_at,
            "last_posted_at": self.last_posted_at,
            "last_error_at": self.last_error_at,
            "last_error_message": self.last_error_message,
            "pause_until": self.pause_until,
            "transitions_24h": self.transitions_24h,
            "transitions_log": self.transitions_log[-200:],
        }
        path.write_text(json.dumps(data, indent=2, default=str))

    def write_status(self, running: bool, dedup_cache_size: int) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(json.dumps({
            "running": running,
            "last_tick_at": self.last_tick_at,
            "last_posted_at": self.last_posted_at,
            "posts_last_hour": self.posts_last_hour(),
            "tier_transitions_last_24h": self.transitions_24h,
            "dedup_cache_size": dedup_cache_size,
            "pause_until": self.pause_until,
            "last_error_at": self.last_error_at,
            "last_error_message": self.last_error_message[:200] if self.last_error_message else "",
        }, indent=2))

    def posts_last_hour(self) -> int:
        cutoff = time.time() - POST_WINDOW_SECONDS
        return sum(1 for t in self.recent_post_times if t >= cutoff)

    def prune(self) -> None:
        """Remove entries older than 24h from recent_post_times and transitions_24h."""
        cutoff_24h = time.time() - 86400
        self.transitions_log = [t for t in self.transitions_log if t.get("at", 0) >= cutoff_24h]
        self.transitions_24h = len(self.transitions_log)
        cutoff_hour = time.time() - POST_WINDOW_SECONDS
        self.recent_post_times = [t for t in self.recent_post_times if t >= cutoff_hour]


# ── Templates ────────────────────────────────────────────────────────


def _fmt_num(v: float, digits: int = 2) -> str:
    return f"{v:.{digits}f}".rstrip("0").rstrip(".") or "0"


def _trim(text: str, limit: int = TWEET_LIMIT) -> str:
    if len(text) <= limit:
        return text
    # Aggressively trim: drop lines from the middle, keep header + link at the end.
    return text[: limit - 1] + "…"


def tweet_for_transition(transition: str, entry: dict) -> Optional[str]:
    """Render the tweet for a specific tier transition. Returns None if not postable."""
    symbol = (entry.get("symbol") or entry.get("name") or "?").strip()[:20]
    addr = entry.get("token_address", "")
    curve = float(entry.get("curve_progress", 0))
    holders = int(entry.get("holders", 0))
    quote = entry.get("quote_asset", "BNB")
    target = entry.get("graduation_target", 0)
    top_holder = float(entry.get("top_holder_pct", 0)) if entry.get("top_holder_pct") is not None else 0
    buy_sell = float(entry.get("buy_sell_ratio", 0)) if entry.get("buy_sell_ratio") is not None else 0
    health = float(entry.get("health_score", 0))
    radar_link = f"{RADAR_BASE}?token={addr}" if addr else RADAR_BASE

    if transition == "graduated":
        text = (
            f"🎓 ${symbol} just graduated on @fourmeme_official\n\n"
            f"{_fmt_num(target)} {quote} raised · {holders} holders\n\n"
            f"FOUR-LIFE Certified: Graduated\n"
            f"{radar_link}"
        )
    elif transition == "graduation_watch":
        text = (
            f"⚡ ${symbol} is now on Graduation Watch\n\n"
            f"Curve {curve:.0f}% · holders {holders}"
            + (f" · buy/sell {_fmt_num(buy_sell, 2)}" if buy_sell > 0 else "")
            + f"\n\nFOUR-LIFE Certified: Graduation Watch\n"
            f"{radar_link}"
        )
    elif transition == "at_risk":
        evidence_bits = []
        if top_holder >= 20:
            evidence_bits.append(f"top holder {top_holder:.0f}%")
        if buy_sell and buy_sell < 1:
            evidence_bits.append(f"b/s {_fmt_num(buy_sell, 2)}")
        if curve < 10:
            evidence_bits.append(f"curve {curve:.0f}%")
        evidence = " · ".join(evidence_bits) or "multiple risk signals"
        text = (
            f"🚨 ${symbol} flagged At Risk by FOUR-LIFE Certified\n\n"
            f"{evidence}\n\n"
            f"Full rule trace: {radar_link}"
        )
    elif transition == "healthy":
        text = (
            f"🌱 ${symbol} reached Healthy on FOUR-LIFE Certified\n\n"
            f"{holders} holders · health {health:.0f}/100"
            + (f" · top holder {top_holder:.0f}%" if top_holder > 0 else "")
            + f"\n\n{radar_link}"
        )
    else:
        return None

    return _trim(text)


# ── Bot ──────────────────────────────────────────────────────────────


class RadarBot:
    def __init__(
        self,
        twitter: TwitterClient | None = None,
        http: httpx.AsyncClient | None = None,
        api_base: str = API_BASE,
        state: BotState | None = None,
    ) -> None:
        self.twitter = twitter if twitter is not None else TwitterClient()
        self._http = http
        self._owns_http = http is None
        self.api_base = api_base.rstrip("/")
        self.state = state or BotState.load()
        self._running = False

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=20)
        return self._http

    async def close(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def fetch_radar(self) -> list[dict]:
        client = await self._client()
        url = f"{self.api_base}/api/graduation-radar?limit=60&min_confidence=high"
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json().get("radar", [])

    def _detect_transitions(self, entries: Iterable[dict]) -> list[dict]:
        """Return a list of {entry, old_tier, new_tier, transition} dicts."""
        out = []
        for e in entries:
            addr = (e.get("token_address") or "").lower()
            if not addr:
                continue
            new_tier = derive_tier(e)
            old_tier = self.state.last_seen_tier.get(addr)

            transition = None
            # First sighting at an already-interesting tier counts as a transition.
            if old_tier is None:
                if new_tier in ("graduated", "graduation_watch", "at_risk"):
                    transition = new_tier
            elif new_tier != old_tier:
                if new_tier == "graduated":
                    transition = "graduated"
                elif new_tier == "graduation_watch" and TIER_RANK.get(old_tier, 0) < TIER_RANK["graduation_watch"]:
                    transition = "graduation_watch"
                elif new_tier == "healthy" and TIER_RANK.get(old_tier, 0) < TIER_RANK["healthy"]:
                    transition = "healthy"
                elif new_tier == "at_risk" and old_tier != "at_risk":
                    transition = "at_risk"

            if transition:
                out.append({
                    "entry": e,
                    "old_tier": old_tier,
                    "new_tier": new_tier,
                    "transition": transition,
                })
        return out

    def _can_post(self) -> bool:
        if time.time() < self.state.pause_until:
            return False
        return self.state.posts_last_hour() < MAX_POSTS_PER_HOUR

    def _already_posted(self, addr: str, transition: str) -> bool:
        return f"{addr.lower()}:{transition}" in self.state.posted_transitions

    def _mark_posted(self, addr: str, transition: str) -> None:
        key = f"{addr.lower()}:{transition}"
        now = time.time()
        self.state.posted_transitions[key] = now
        self.state.recent_post_times.append(now)
        self.state.last_posted_at = now

    async def tick(self) -> dict:
        """Run one poll + diff + post cycle. Returns summary dict."""
        self.state.last_tick_at = time.time()

        try:
            entries = await self.fetch_radar()
        except Exception as e:
            self.state.last_error_at = time.time()
            self.state.last_error_message = f"fetch_radar failed: {e}"
            self.state.pause_until = time.time() + ERROR_PAUSE_SECONDS
            self.state.prune()
            self.state.save()
            self.state.write_status(self._running, len(self.state.posted_transitions))
            logger.error("Radar fetch failed: {}", e)
            return {"transitions": 0, "posted": 0, "error": str(e)}

        transitions = self._detect_transitions(entries)
        posted_count = 0

        for t in transitions:
            entry = t["entry"]
            addr = (entry.get("token_address") or "").lower()
            transition = t["transition"]

            if self._already_posted(addr, transition):
                continue
            if not self._can_post():
                logger.info("Rate limit reached — {} pending transitions deferred", len(transitions) - posted_count)
                break

            text = tweet_for_transition(transition, entry)
            if not text:
                continue

            try:
                tweet_id = self.twitter.post_tweet(text)
            except Exception as e:
                self.state.last_error_at = time.time()
                self.state.last_error_message = f"twitter.post_tweet failed: {e}"
                self.state.pause_until = time.time() + ERROR_PAUSE_SECONDS
                logger.error("Twitter post failed: {}", e)
                break

            self._mark_posted(addr, transition)
            posted_count += 1
            self.state.transitions_log.append({
                "at": time.time(),
                "token_address": addr,
                "symbol": entry.get("symbol", ""),
                "transition": transition,
                "tweet_id": tweet_id,
            })

        # Update last-seen map after processing so a failed post doesn't prevent retry next tick.
        for e in entries:
            addr = (e.get("token_address") or "").lower()
            if addr:
                self.state.last_seen_tier[addr] = derive_tier(e)

        self.state.prune()
        self.state.save()
        self.state.write_status(self._running, len(self.state.posted_transitions))
        return {
            "transitions": len(transitions),
            "posted": posted_count,
            "posts_last_hour": self.state.posts_last_hour(),
        }

    async def run_forever(self) -> None:
        self._running = True
        logger.info("FOUR-LIFE Radar Bot started — polling {} every {}s", self.api_base, TICK_INTERVAL_SECONDS)
        self.state.write_status(True, len(self.state.posted_transitions))
        while self._running:
            try:
                summary = await self.tick()
                logger.info("Tick complete: {}", summary)
            except Exception as e:
                logger.error("Unhandled tick error: {}", e)
                self.state.last_error_at = time.time()
                self.state.last_error_message = str(e)
                self.state.save()
            await asyncio.sleep(TICK_INTERVAL_SECONDS)

    def stop(self) -> None:
        self._running = False


async def start_radar_bot() -> None:
    bot = RadarBot()
    try:
        await bot.run_forever()
    finally:
        await bot.close()


def main() -> None:
    try:
        asyncio.run(start_radar_bot())
    except KeyboardInterrupt:
        logger.info("Radar bot stopped by user")


if __name__ == "__main__":
    main()
