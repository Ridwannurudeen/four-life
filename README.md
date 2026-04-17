# FOUR-LIFE

**The AI growth operator for Four.meme launches.**

FOUR-LIFE helps Four.meme tokens survive after launch: it analyzes narratives, predicts graduation probability, creates token lore and content, monitors holder and curve health, posts transparent updates, and learns from every launch. Think of it as the post-launch lifecycle layer that Four.meme is missing.

Built for the [Four.meme AI Sprint Hackathon](https://dorahacks.io/hackathon/fourmemeaisprint) on BNB Chain.

## What Makes FOUR-LIFE Different

Every AI agent on Four.meme today does the same thing: create → dump → repeat. FOUR-LIFE is the agent that **stays with the token after launch** — nurturing community, defending against FUD, accelerating toward graduation, and learning from every cycle.

### The Lifecycle

| Phase | Duration | What FOUR-LIFE Does |
|-------|----------|-------------------|
| **THINK** | Pre-launch | Analyzes narratives, detects trends, picks optimal timing, generates concept |
| **BIRTH** | Launch | Creates token via Agentic Mode, generates artwork + lore, posts launch thread |
| **RAISE** | 0-72h+ | Monitors health, generates content, celebrates milestones, defends against dumps |
| **LEARN** | Post-72h | Evaluates outcomes, records learnings, improves strategy for next launch |

### Key Features

- **Narrative Intelligence** — Scans Four.meme + social trends to find unsaturated narrative gaps
- **Real-Time Health Monitoring** — Tracks holder velocity, whale concentration, buy/sell pressure, bonding curve progress
- **Graduation Probability** — ML-based prediction of whether a token will reach the 18 BNB threshold
- **Adaptive Content** — AI generates memes, updates, and transparency posts that match each token's personality
- **Persistent Memory** — Learns from every launch via Unibase. Each cycle is better than the last.
- **On-Chain Identity** — ERC-8004 registered agent with verifiable track record on BNB Chain
- **MYX V2 Perp Integration** — Creates derivative markets for launched tokens (MYX bounty)
- **DGrid AI Gateway** — All AI inference routed through DGrid's unified API (DGrid bounty)

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  FOUR-LIFE Agent                 │
├──────────┬──────────┬──────────┬────────────────┤
│  Brain   │Lifecycle │ Memory   │   Identity     │
│ Narrative│ Monitor  │ Unibase  │  ERC-8004      │
│ Strategy │ Nurture  │ Local    │  Reputation    │
│ Content  │ Defend   │ Sync     │  Agent Card    │
│          │Accelerate│          │                │
├──────────┴──────────┴──────────┴────────────────┤
│              Four.meme Integration               │
│        API Client  │  TokenManager2 Chain        │
├──────────────────────┬──────────────────────────┤
│    MYX V2 Perps     │    Twitter/X Social       │
├──────────────────────┴──────────────────────────┤
│           DGrid AI Gateway (LLM Calls)           │
├─────────────────────────────────────────────────┤
│              BNB Chain (Chain ID: 56)             │
└─────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Core | Python 3.11+ |
| AI | DGrid AI Gateway (Claude Sonnet, GPT-4) |
| Blockchain | web3.py, BNB Chain RPCs |
| Token Launch | Four.meme Agentic Mode API |
| Derivatives | MYX V2 Permissionless Perps |
| Memory | Unibase/Membase (decentralized) + local JSON |
| Identity | ERC-8004 (BRC8004 on BSC) |
| Social | Tweepy (Twitter/X API v2) |
| Image Gen | DALL-E 3 |
| Dashboard | Next.js 14 + Tailwind + Recharts |
| API | FastAPI |

## Quick Start

```bash
# Clone
git clone https://github.com/Ridwannurudeen/four-life.git
cd four-life

# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your keys

# Run the agent
python main.py

# Or run the API server (for dashboard)
python server.py
```

## API Endpoints

### Platform Primitives (no auth — designed for Four.meme to embed directly)

| Endpoint | Description |
|----------|-------------|
| `GET /api/health-score/{token}` | Pair-aware health score with confidence, deterministic risk flags, and a Certified badge |
| `GET /api/graduation-radar?quote_asset=&min_confidence=&sort_by=` | Radar of active tokens, filterable by quote asset, confidence, and sort key |
| `GET /api/token/{token}/badge` | **FOUR-LIFE Certified** — deterministic trust tier (observed/healthy/at_risk/graduation_watch/graduated) with the exact rules that fired |
| `GET /api/token/{token}/risk-snapshot` | Evidence-backed risk snapshot: each risk level traces to the metric that produced it |
| `GET /api/token/{token}/operator-checklist` | Deterministic 72h operator checklist tailored to the token's current phase |
| `GET /api/token/{token}/history?limit=&since=&transitions_only=` | Historical tier snapshots (time-series) for a token |
| `GET /api/token/{token}/diff?since=` | Summary of what changed for a token since a given timestamp (tier transitions + first/last snapshot) |
| `GET /api/history/tokens` | Distinct tokens with at least one recorded snapshot |
| `GET /api/history/export.ndjson` | Full history store as newline-delimited JSON (supports `?since=` and `?token_address=`) |
| `GET /api/creator/{wallet}/survival-score` | Aggregate launch-survival performance for a creator wallet (launches, graduations, trust tier) |
| `GET /api/creators/leaderboard?sort_by=&trust_tier=&min_launches=&limit=` | Creator ledger across every FOUR-LIFE-tracked launch |
| `GET /api/platform/cohorts` | Platform analytics: cohorts by age/narrative/quote asset, whale-risk distribution, avg time-to-graduation |
| `POST /api/raise-plan/{token}` | AI-generated 72-hour raise plan (uses the actual pair-aware graduation target) |
| `GET /.well-known/agent-registration.json` | ERC-8004 / BRC-8004 agent card |

### Webhooks (bearer-auth on writes)

| Endpoint | Description |
|----------|-------------|
| `POST /api/webhooks` | Create a subscription. Returns the shared HMAC secret **exactly once**. |
| `GET /api/webhooks` | List active (or all) subscriptions. |
| `DELETE /api/webhooks/{id}` | Delete a subscription. |
| `GET /api/webhooks/{id}/deliveries` | Recent delivery attempts (status, http_status, retry counts). |

Events: `badge.tier_changed`, `protection.level_changed`. Signature header is `X-FourLife-Signature: t=<unix_ts>,v1=<hex_hmac_sha256(t + "." + body)>`. Retry schedule: 30s, 2m, 15m — then dead. Auto-disable after 10 consecutive dead deliveries. See the signed-payload recipe at [/webhooks](https://four-life.gudman.xyz/webhooks).

### Protection Mode (per-token defensive thresholds)

| Endpoint | Description |
|----------|-------------|
| `PUT /api/protection/{token}` | Create or update a token's protection policy (bearer-auth). |
| `GET /api/protection/{token}` | Read policy + current live verdict (safe / warn / critical). |
| `DELETE /api/protection/{token}` | Remove a policy (bearer-auth). |
| `GET /api/protection` | List every configured policy. |

A `critical` verdict halts non-safety content posts and fires `protection.level_changed` through the webhook + notification pipeline. All rule thresholds have conservative defaults — untouched tokens still get baseline protection.

### Notifications (Telegram + Discord)

| Endpoint | Description |
|----------|-------------|
| `GET /api/notifications/status` | Which channels are currently configured (never reveals secrets). |
| `POST /api/notifications/test` | Send a synthetic event to every enabled channel (bearer-auth). |

Configure via `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` and/or `DISCORD_WEBHOOK_URL`. Notifications fan-out on tier transitions and protection-level changes.

Every public endpoint returns `confidence_score`, `fallback_used`, `data_sources`, `model_version`, and `last_updated_at` so judges and Four.meme can audit the response without trusting the label.

### Agent Dashboard APIs

| Endpoint | Description |
|----------|-------------|
| `GET /api/status` | Agent status, wallet, track record |
| `GET /api/tokens` | All tracked tokens with health scores |
| `GET /api/tokens/{address}` | Detailed token health + actions |
| `GET /api/memory` | Agent memory, learnings, launch history |
| `GET /api/actions` | Recent lifecycle actions log |
| `POST /api/agent/think` | Run one THINK cycle; returns degraded mode explicitly when LLM is unavailable |
| `POST /api/agent/track` | Track an existing token (accepts `quote_asset` for pair-aware graduation target) |
| `POST /api/agent/start` / `/stop` | Agent loop control |
| `GET /api/myx/status` | MYX connection status + execution mode |
| `GET /api/myx/portfolio` | Hedge portfolio summary (includes `execution_mode`) |
| `GET /api/myx/positions/{token}` | All hedge positions for a token |
| `GET /api/myx/signal/{token}` | AI-generated trading signal for a token |
| `POST /api/myx/evaluate/{token}` | Manually trigger hedge evaluation |

## Pair-Aware Graduation Targets

FOUR-LIFE sources graduation thresholds live from Four.meme's `/public/config` API and caches them for 10 minutes. Each quote asset has its own target:

| Quote Asset | Target | Source |
|-------------|--------|--------|
| BNB  | 18 BNB      | Four.meme config (live) |
| USD1 | 12,000 USD1 | Four.meme config (live) |
| USDT | 12,000 USDT | Four.meme config (live) |
| USDC | 12,000 USDC | Four.meme config (live) |
| CAKE | 10,000 CAKE | Four.meme config (live) |
| ...  | ...         | Four.meme config (live) |

Unknown quote assets return `confidence: "low"` with no fabricated number. The `/api/health-score`, `/api/graduation-radar`, and `/api/raise-plan` endpoints all agree on the same target for a token.

## FOUR-LIFE Certified

A deterministic public trust layer for Four.meme launches.

| Tier | Meaning |
|------|---------|
| `graduated` | Reached the bonding-curve graduation threshold |
| `graduation_watch` | Strong buy pressure, healthy distribution, curve past 70% |
| `healthy` | Clean distribution, rising holders, buys outpacing sells after 1h |
| `at_risk` | Meaningful risk signal: whale concentration, sell pressure, or stalled curve |
| `observed` | Tracked, but not enough signal yet to trust-grade |

Badge assignment is fully reproducible from raw metrics — every response includes a `why[]` array listing the exact rule, metric value, threshold, and pass/fail state. No LLM. Judges and Four.meme can recompute the tier independently.

## Bounty Integrations

### DGrid AI Gateway (DGrid bounty)
All LLM calls (narrative analysis, content generation, strategy decisions, raise-plan generation) route through DGrid's unified OpenAI-compatible API. If DGrid returns a balance/rate-limit/5xx error, FOUR-LIFE transparently falls back to Anthropic so the live demo never black-holes. Every LLM-backed response includes an `llm_provider` field identifying which provider served the call.

### MYX V2 (MYX bounty)
FOUR-LIFE integrates MYX V2 as the perp layer for hedging meme-token exposure.

**Signal layer (live by default):** AI analyses token health each phase and emits long/short/close/hold signals with confidence scores. Exposed at `GET /api/myx/signal/{token}`. Default response mode is `execution_mode: "signal_only"`.

**Execution layer (opt-in):** Set `MYX_EXECUTION_ENABLED=true` + provide `MYX_ROUTER_ADDRESS` and `MYX_POOL_ADDRESS` to let the hedge manager submit on-chain orders. Phase-based behavior: monitor in nurture, hedge in defend, scale in accelerate, close on graduation. BNB/USDT correlation hedging on existing MYX pairs until permissionless pair creation goes live.

The demo surface ships in signal-only mode so judges never see hardcoded-price orders being submitted.

### Identity (ERC-8004 / BRC-8004)
FOUR-LIFE registers with the external BRC-8004 IdentityRegistry + ReputationRegistry on BSC:

- IdentityRegistry: `0xfA09B3397fAC75424422C4D28b1729E3D4f659D7`
- ReputationRegistry: `0x17860530385Bdde7992c4Da71B9ec7791E474C08`

The agent card is published at `/.well-known/agent-registration.json`. FOUR-LIFE does not deploy its own registry contracts.

## License

MIT
