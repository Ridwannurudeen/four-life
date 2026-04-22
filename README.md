<div align="center">

# FOUR-LIFE

**The trust layer for Four.meme launches.**

Deterministic, auditable, on-chain grading + defense for every meme token on BNB Chain.

[![License](https://img.shields.io/badge/license-MIT-a1a1aa.svg?style=flat-square)](./LICENSE)
[![Tests](https://img.shields.io/badge/tests-365_passing-6cff32.svg?style=flat-square)](#tests)
[![Next.js](https://img.shields.io/badge/next-16.2.4-a1a1aa.svg?style=flat-square)](./web)
[![Live](https://img.shields.io/badge/live-four--life.gudman.xyz-00d4ff.svg?style=flat-square)](https://four-life.gudman.xyz)
[![ERC-8004](https://img.shields.io/badge/ERC--8004-Agent_ID_20-a855f7.svg?style=flat-square)](https://bscscan.com/tx/0x62a1a43d9e782686b833ed44eee7ea95a9ee3370f2f372334dc7bbf85cc14762)

[Live site](https://four-life.gudman.xyz) · [API docs](https://four-life.gudman.xyz/docs) · [DGrid showcase](https://four-life.gudman.xyz/dgrid) · [MYX showcase](https://four-life.gudman.xyz/myx) · [Evidence](https://four-life.gudman.xyz/evidence) · [Agent card](https://four-life.gudman.xyz/.well-known/agent-registration.json)

> **$AUNT** — a Four.meme token **launched end-to-end by the FOUR-LIFE agent** and now under active autonomous management: [token](https://bscscan.com/token/0x568bf737887053ffa8aa4e82d8859ca4a9a14444) · [launch tx](https://bscscan.com/tx/0x80ff903ca947448ec50927b866067b67e5bdd69a667f9d0f1b3af8f0c74869d2) · [Four.meme page](https://four.meme/token/0x568bf737887053ffa8aa4e82d8859ca4a9a14444). Every decision the agent makes is hashed into a Merkle chain and anchored on BNB Chain — [DGrid root](https://bscscan.com/tx/0x047c2f58e77d349f98eac8305080970c391c0e39c378816c22e69fc0d6b18fe9) · [MYX root](https://bscscan.com/tx/0x0d43051c24fd59359317d12ce3137512a1c7cb032528bf813d506545fcf06698).

</div>

---

## The problem

Four.meme ships thousands of tokens per week. **98.6% die within 72 hours.**
Creation is a solved problem — there's no infrastructure for what comes after. No shared trust signal, no defender, no track record.

## What FOUR-LIFE is

An **autonomous, cryptographically-accountable lifecycle agent** for Four.meme — plus a public trust layer anyone can query:

- **FOUR-LIFE Certified** — deterministic 5-tier trust grade computed from raw on-chain metrics with a full `why[]` rule trace. Zero LLM in the trust path. Any auditor can recompute the grade and the answer matches.
- **Protection Mode** — per-token defensive thresholds. Whale concentration, sell pressure, contract rug signals. On critical, the agent halts content posts, fires signed webhooks, and emits a MYX hedge signal.
- **Autonomous lifecycle agent** — continuous THINK → BIRTH → RAISE → LEARN loop. Registered on BNB Chain as **ERC-8004 Agent ID 20**. Has already launched a live Four.meme token ($AUNT) and is managing it end-to-end.
- **Cryptographic accountability** — every LLM call, every signal, every position event is folded into a rolling SHA-256 chain. The tip is published on BNB Chain as a self-transaction. Anyone can re-derive the chain locally and verify the agent's claim of what it did — **zero server trust required**. Three attestation txs on-chain already.
- **Multi-model consensus on high-stakes decisions** — DEFEND-phase hedge decisions fan across 3 DGrid models in parallel; majority vote decides. A capability single-provider agents literally cannot replicate.

No off-chain oracles for trust. No LLM-graded trust scores. Every claim has a tx hash behind it.

---

## Live surfaces

| Page | What it is |
|---|---|
| [`/`](https://four-life.gudman.xyz) | Landing — paste any token address to get graded inline |
| [`/radar`](https://four-life.gudman.xyz/radar) | Live leaderboard of Four.meme tokens with tier pills, filters, per-token drawer |
| [`/evidence`](https://four-life.gudman.xyz/evidence) | Five real tokens graded right now, with why-tables |
| [`/alerts`](https://four-life.gudman.xyz/alerts) | Protection Mode threat feed — every level transition the agent recorded |
| [`/activity`](https://four-life.gudman.xyz/activity) | Agent timeline — every autonomous action, tx hash linked |
| [`/dgrid`](https://four-life.gudman.xyz/dgrid) | DGrid integration showcase — live share %, trace, side-by-side model probe |
| [`/metrics`](https://four-life.gudman.xyz/metrics) | Service reliability — p50 / p95 / p99 latency, error rate, endpoint breakdown |
| [`/docs`](https://four-life.gudman.xyz/docs) | OpenAPI docs (FastAPI / Swagger UI) |

<p align="center">
  <img src="./docs/screenshots/hero.png" alt="FOUR-LIFE landing" width="900" />
  <br/>
  <em>Landing — paste any Four.meme address, get graded inline.</em>
</p>

---

## Why this wins on trust

**Deterministic grading.** Every tier is the output of a rule table, not a model. Here's how a grade looks on the wire:

```jsonc
// GET /api/token/0xd8c1c7b065ec8548093fe237157088b984dc4444/badge
{
  "badge": {
    "tier": "graduation_watch",
    "label": "Graduation Watch",
    "why": [
      { "rule": "curve_advanced",  "metric": "curve_progress_pct", "value": 70.5, "operator": ">=", "threshold": 70,  "passed": true },
      { "rule": "buy_pressure",    "metric": "buy_sell_ratio",     "value": 1.81, "operator": ">=", "threshold": 1.2, "passed": true },
      { "rule": "whale_ok",        "metric": "top_holder_pct",     "value": 14.2, "operator": "<",  "threshold": 30,  "passed": true },
      { "rule": "target_confident","metric": "graduation_confidence","value": "high", "operator": "==","threshold":"high","passed": true }
    ],
    "metrics_snapshot": { /* raw inputs */ }
  },
  "model_version": "four-life-v1.1",
  "last_updated_at": 1776623969
}
```

Recompute it yourself. The answer matches.

**On-chain reputation.** FOUR-LIFE is a registered ERC-8004 agent on BNB Chain (**Agent ID 20**). Every graduated token triggers a reputation attestation via `giveFeedback` on the BRC-8004 registry. The agent card is published at [`/.well-known/agent-registration.json`](https://four-life.gudman.xyz/.well-known/agent-registration.json).

**Pair-aware graduation targets, live from Four.meme.** Thresholds come from Four.meme's own `/public/config` API on a 10-min cache — BNB=18, USD1/USDT/USDC=12000, CAKE=10000, plus every other pair Four.meme defines. If the platform changes a target, FOUR-LIFE updates within 10 minutes. No hardcoded numbers.

---

## Architecture

```
                  ┌──────────────────────────────────┐
                  │            FOUR-LIFE              │
                  │   (autonomous lifecycle agent)    │
                  │                                   │
                  │  THINK ─→ BIRTH ─→ RAISE ─→ LEARN │
                  └──┬───────────────────────────┬───┘
                     │                           │
         ┌───────────▼─────────┐    ┌────────────▼─────────────┐
         │   Trust primitives  │    │   Dispatch + defense      │
         │ • Certified badge   │    │ • Signed HMAC webhooks    │
         │ • Risk snapshot     │    │ • Protection Mode         │
         │ • Creator ledger    │    │ • Telegram / Discord      │
         │ • Graduation radar  │    │ • MYX V2 hedge signal     │
         └───────────┬─────────┘    └────────────┬─────────────┘
                     │                           │
                     ▼                           ▼
          ┌──────────────────────────────────────────┐
          │     DGrid AI Gateway (100% of LLM)       │
          │         └─ Anthropic → OpenAI            │
          │           (resilient fallback)           │
          └────────────────────┬─────────────────────┘
                               │
          ┌────────────────────▼──────────────────────┐
          │          BNB Chain (chainId 56)           │
          │  • Four.meme TokenManager2                │
          │  • BRC-8004 IdentityRegistry (agent ID 20)│
          │  • BRC-8004 ReputationRegistry            │
          │  • MYX V2 Pool (pair-index resolution)    │
          └───────────────────────────────────────────┘
```

<p align="center">
  <img src="./docs/screenshots/radar.png" alt="Graduation Radar" width="900" />
  <br/>
  <em>/radar — live leaderboard of every tracked Four.meme token with its Certified tier and why-table.</em>
</p>

---

## Quick start

Grade any Four.meme token in 3 lines.

**Python** ([`four-life`](https://pypi.org/project/four-life/))

```bash
pip install four-life
```

```python
from four_life import FourLife
fl = FourLife()
print(fl.get_badge("0xd8c1c7b065ec8548093fe237157088b984dc4444")["badge"]["tier"])
# → "graduation_watch"
```

**TypeScript** ([`@gudman/four-life-sdk`](https://www.npmjs.com/package/@gudman/four-life-sdk))

```bash
npm install @gudman/four-life-sdk
```

```ts
import { FourLife } from "@gudman/four-life-sdk";
const fl = new FourLife();
const { badge } = await fl.getBadge("0xd8c1c7b065ec8548093fe237157088b984dc4444");
console.log(badge.tier); // "graduation_watch"
```

**curl** (no SDK needed)

```bash
curl -s https://four-life.gudman.xyz/api/token/0xd8c1c7b065ec8548093fe237157088b984dc4444/badge | jq '.badge | {tier, why: [.why[] | select(.passed)]}'
```

**Embed** — drop a live Certified badge on any page

```html
<script src="https://four-life.gudman.xyz/embed.js?token=0xd8c1c7b065ec8548093fe237157088b984dc4444"></script>
```

---

## API

Every public endpoint returns `confidence_score`, `fallback_used`, `data_sources`, `model_version`, and `last_updated_at` so consumers can audit the response without trusting the label.

### Platform primitives (public, no auth)

| Endpoint | Returns |
|---|---|
| `GET /api/token/{addr}/badge` | Certified tier + full `why[]` rule trace |
| `GET /api/token/{addr}/risk-snapshot` | Evidence-backed risk level, each flag traces to its metric |
| `GET /api/token/{addr}/operator-checklist` | Deterministic 72h action plan, phase-aware |
| `GET /api/token/{addr}/contract-risk` | Bytecode + ABI inspection — mint / blacklist / pause / proxy / ownership |
| `GET /api/token/{addr}/history` | Time-series of tier snapshots |
| `GET /api/graduation-radar?quote_asset=&min_confidence=&sort_by=` | Live filtered leaderboard |
| `GET /api/creator/{wallet}/survival-score` | Launch-survival record for a creator |
| `GET /api/creators/leaderboard` | Creator ledger across every tracked launch |
| `GET /api/platform/cohorts` | Platform analytics (cohorts by age / narrative / quote asset) |

### DGrid integration surface

| Endpoint | Purpose |
|---|---|
| `GET /api/dgrid/stats` | Per-task routing, per-provider counters, fallback events, cost USD, breaker state |
| `GET /api/dgrid/health` | Green/amber/red reachability state |
| `GET /api/dgrid/trace?limit=N` | Ring-buffer log of last 200 calls with chain tip per entry |
| `GET /api/dgrid/leaderboard` | Per-(task, model) rolling stats — success rate, latency, cost/call |
| `GET /api/dgrid/audit` | Current Merkle root + last on-chain publish |
| `GET /api/dgrid/audit/calls` | Full call log paginated, for independent re-derivation |
| `POST /api/dgrid/probe` | Force a single DGrid-only call to verify the gateway on demand |
| `POST /api/dgrid/compare` | Run the same prompt on N models side-by-side via DGrid |
| `POST /api/dgrid/consensus` | Fan one prompt across N DGrid models + vote on JSON field (majority / median) |
| `POST /api/dgrid/chaos` | Toggle simulated DGrid outage — exercises the fallback chain live |
| `POST /api/dgrid/attest` | Publish the Merkle root on BNB Chain as a self-transaction (admin) |

### MYX V2 integration surface

| Endpoint | Purpose |
|---|---|
| `GET /api/myx/status` | Live connection state + 37 perp markets fetched from `api.myx.finance` |
| `GET /api/myx/portfolio` | Per-token hedge summary, signals generated, active positions |
| `GET /api/myx/signals?limit=N` | Unbounded signal history (append-only JSONL, not ring-buffered) |
| `GET /api/myx/audit` | Trade attestation Merkle tip + last publish |
| `GET /api/myx/signal-attestation` | Signal attestation Merkle tip (separate chain from trade events) |
| `GET /api/myx/calldata/{token}` | **Shape-preview unsigned `createIncreaseOrder` tx** the agent would submit against the MYX V2 struct — decode locally against MYX V2's ABI to verify correctness |
| `POST /api/myx/consensus/{token}` | Fire hedge decision across 3 DGrid models — cross-partner flex |
| `POST /api/myx/attest` / `attest-signals` | Publish trade / signal roots on BNB Chain (admin) |

### Webhooks (bearer-authenticated writes)

```
POST   /api/webhooks        # Subscribe — secret returned once
GET    /api/webhooks        # List subscriptions
DELETE /api/webhooks/{id}   # Remove
GET    /api/webhooks/{id}/deliveries   # Attempt history
```

Events: `badge.tier_changed`, `protection.level_changed`.
Signature header: `X-FourLife-Signature: t=<unix>,v1=<hex_hmac_sha256(t + "." + body)>`.
Retry schedule: 30s → 2m → 15m → dead. Auto-disable after 10 consecutive dead deliveries.

### Protection Mode

```
PUT    /api/protection/{addr}   # Upsert policy (bearer-auth)
GET    /api/protection/{addr}   # Policy + live verdict
DELETE /api/protection/{addr}   # Remove
```

A `critical` verdict halts non-safety content posts and fires `protection.level_changed`. All thresholds have conservative defaults — untouched tokens still get baseline protection.

### Identity + reputation

```
GET /api/identity                              # Agent card + every reputation attestation
GET /.well-known/agent-registration.json       # ERC-8004 agent card
```

### Reliability

```
GET /api/metrics   # p50 / p95 / p99 latency, 5xx error rate, top-10 endpoint breakdown
```

Full OpenAPI at [`/docs`](https://four-life.gudman.xyz/docs).

---

## DGrid AI Gateway — the agent's brain

FOUR-LIFE routes every LLM decision through [DGrid](https://dgrid.ai). Production DGrid share is **94.7%**. The integration is built to be defensible under any audit:

- **Circuit breaker** — opens after 3 consecutive DGrid failures with a 30s cooldown. Stops eating latency on a known-bad primary. Half-opens on the next call, closes on first success.
- **Transient retry** — one in-place retry on DGrid 5xx/network errors before falling back. Keeps DGrid share high during blips.
- **3-tier fallback** — DGrid → Anthropic → OpenAI. Every attempt (success or failure) lands in the trace ring buffer so judges can see exactly which provider served which call.
- **Multi-model consensus** — `POST /api/dgrid/consensus` fans one prompt across N DGrid models in parallel and votes. Wired into the DEFEND phase of every token's lifecycle and into MYX high-stakes hedge decisions. Cross-partner flex single-provider agents cannot replicate.
- **Chaos toggle** — `POST /api/dgrid/chaos {enabled: true}` forces DGrid to fail so judges can watch the fallback chain engage live on stage. Deterministic recovery when disabled.
- **Cost tracking** — per-model USD rate table (`agent/brain/cost.py`). Every trace entry carries `cost_usd`; stats roll up by task / model / provider.
- **On-chain Merkle attestation** — every successful DGrid call is hashed into a rolling SHA-256 chain. The tip is published on BNB Chain as a self-transaction with the root in the tx `data` field. **2 DGrid roots already on-chain.** Anyone can download the full call log via `/api/dgrid/audit/calls` and verify locally via `verify_chain()` — zero server trust required.
- **Image routing** — DALL-E via DGrid's image proxy; falls back to raw OpenAI with session-level disable if DGrid returns 404.
- **Per-response provenance** — every public LLM-backed response carries an `llm_provider` field identifying which provider served that specific decision.

<p align="center">
  <img src="./docs/screenshots/dgrid.png" alt="DGrid showcase" width="900" />
  <br/>
  <em>/dgrid — health rail, breaker state, chaos toggle, cost breakdown, leaderboard, consensus demo, attestation cards.</em>
</p>

---

## MYX V2 — perp hedging with DGrid-backed decisions

The agent generates phase-aware hedge signals on MYX V2 and commits every decision to a cryptographic chain — independent of whether the trade executes.

- **Live connection** — 37 perp markets fetched live from `api.myx.finance`. `getPairIndex(WBNB, USDT)` resolves on-chain from the verified MYX V2 Pool `0x22cEc08111BBae24D0b80BDA2a6503EaB9BA704b`.
- **Phase-aware hedging** — NURTURE=monitor, DEFEND=short hedge (consensus-backed), ACCELERATE=scale, GRADUATED=close all.
- **DGrid consensus on DEFEND** — the highest-stakes decision (opening a short when a token shows weakness) fans across 3 DGrid models and takes a majority vote. Consensus metadata (method, tally, per-model verdict) preserved in every signal.
- **Two independent Merkle chains** — (a) **trade attestation** chains every open/close position event; (b) **signal attestation** chains every decision the agent makes. Both publishable on-chain. **1 MYX signal root already on-chain.**
- **Calldata viewer** — `GET /api/myx/calldata/{token}` returns the shape-preview unsigned `createIncreaseOrder((address,uint256,uint8,int256,uint256,bool,uint256,uint256,uint8,uint256))` transaction against the MYX V2 struct. Decode locally to confirm the struct packing is correct. Production orders route through the permissioned broker-signer pattern (`placeOrderWithSalt`) — wire-ready pending MYX broker onboarding.
- **Every production BSC mainnet address wired** — TRADING_ROUTER, ORDER_MANAGER, POSITION_MANAGER, BASE_POOL, QUOTE_POOL, ORACLE, FORWARDER. Sourced from the official MYX SDK (`myx-trade/src/config/address/BSC_MAINET_NET.ts`), hardcoded into our config with full call-flow comments in `agent/myx/client.py`.
- **Signal-only by default — execution pending broker onboarding.** MYX V2 is a permissioned broker architecture: orders flow through a **BrokerSigner** contract issued per integrator by the MYX team. We shipped the complete infrastructure wired to the correct addresses; flipping `MYX_EXECUTION_ENABLED=true` + setting `MYX_BROKER_ADDRESS` is the single change needed to go live. See the MYX showcase at [/myx](https://four-life.gudman.xyz/myx).

---

## Run it locally

```bash
git clone https://github.com/Ridwannurudeen/four-life
cd four-life

# Python agent + API
pip install -r requirements.txt
cp .env.example .env        # fill in keys
python server.py            # API on :8030 — agent loop autostarts

# Frontend (optional — the live site is already deployed)
cd web
npm ci
npm run dev                 # :3000
```

### Required env

Minimum for the agent to run:

```
PRIVATE_KEY=0x...                    # wallet for ERC-8004 registration + attestations
BSC_RPC_URL=https://bsc-rpc.publicnode.com
DGRID_API_KEY=sk-...                 # DGrid gateway
```

Full list in [`.env.example`](./.env.example).

---

## Security

- **Webhook SSRF guard.** User-supplied URLs are validated at registration **and** delivery. Literal private / loopback / link-local / cloud-metadata IPs rejected. DNS resolved and every A/AAAA record checked — DNS rebinding attacks fail at delivery time even if they passed at registration.
- **Bearer-gated writes.** Every state-changing endpoint (`/api/agent/*`, `/api/protection/*`, `/api/webhooks`) requires `Authorization: Bearer $API_SECRET`.
- **Signed webhook deliveries.** HMAC-SHA256 of `t.body`, 5-min timestamp validity window on the receiver side.
- **Public endpoints redact operational internals** — wallet address, agent learnings, per-launch postmortems (`what_worked` / `what_failed`) only surface for authenticated callers.
- **Per-IP rate limits.** 120 req/min public, 30 req/min on write endpoints. `X-RateLimit-Limit` / `X-RateLimit-Remaining` headers on every response.
- **Non-root service user.** systemd unit runs as `fourlife` with `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, and `ReadWritePaths` scoped to `data/`.

---

## Tests

```bash
# Python core + SDK
python -m pytest tests/            # 277 tests
python -m pytest sdk-python/tests  # 32 tests

# TypeScript SDK
cd sdk && npm test                 # 9 tests

# Frontend lint + build
cd web && npm run lint && npm run build
```

**Last green run:** 365 Python / 32 Python SDK / 9 TS SDK tests passing · Next.js build clean · `npm audit` reports 0 vulnerabilities.

New DGrid coverage includes: circuit-breaker state machine, transient retry classification, chaos-injection and recovery, cost-by-model accumulation, attestation-chain determinism + re-derivation + tamper detection, independent verifier, trace ordering, API endpoint shapes (stats / health / leaderboard / audit / audit-calls / chaos / consensus).

New MYX coverage includes: signal-log pagination + token-filter, trade attestation chain (deterministic digest, case-normalized address, parallel evolution vs signal chain), signal attestation chain (distinct genesis, consensus metadata in digest), verifier round-trip + tamper detection + field re-derivation, signal-attestation endpoint, calldata endpoint auth gate.

---

## Ecosystem

Partners FOUR-LIFE is built on or integrates with:

- **[Four.meme](https://four.meme)** — live pair-aware graduation targets, TokenManager2 on BSC
- **[BNB Chain](https://bnbchain.org)** — all on-chain settlement and identity
- **[DGrid AI Gateway](https://dgrid.ai)** — unified LLM routing, every inference tracked
- **[MYX V2](https://myx.finance)** — perp hedge signals tied to lifecycle phases
- **ERC-8004 / BRC-8004** — standardised agent identity + reputation registries
- **Unibase / Membase** — decentralised agent memory

---

## Repository layout

```
four-life/
├── agent/              # Python agent core
│   ├── api.py          # FastAPI app — all public + auth endpoints
│   ├── agent.py        # lifecycle loop (THINK → BIRTH → RAISE → LEARN)
│   ├── badge.py        # deterministic Certified rules
│   ├── brain/          # DGrid-routed LLM client with fallback + trace
│   ├── fourmeme/       # Four.meme API + on-chain monitor
│   ├── identity/       # ERC-8004 agent registration + attestations
│   ├── lifecycle/      # phase engine, content + protection dispatch
│   ├── myx/            # MYX V2 hedge signal + execution client
│   ├── protection.py   # Protection Mode rules + event log
│   ├── security/       # shared risk cache + contract analyzer
│   └── webhooks.py     # HMAC-signed outbound delivery + SSRF guard
├── web/                # Next.js static-export dashboard + landing
│   └── app/            # /, /radar, /dgrid, /alerts, /metrics, /evidence, /activity, /launch/[addr], /dashboard, /docs
├── sdk/                # TypeScript SDK (@gudman/four-life-sdk)
├── sdk-python/         # Python SDK (four-life)
├── extension/          # Chrome MV3 extension
├── tests/              # 277-test Python suite
├── deploy/             # systemd unit, nginx, setup.sh
└── docs/               # screenshots + protocol notes
```

---

## License

MIT — see [LICENSE](./LICENSE).
