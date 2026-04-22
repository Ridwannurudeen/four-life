# Four.meme AI Sprint — FOUR-LIFE Submission

Everything below traces to a live URL, BscScan tx, source file, or the running API on `four-life.gudman.xyz`. No placeholders.

---

## Project Title

**FOUR-LIFE — A verifiably-autonomous lifecycle agent for Four.meme**

## One-line tagline

An AI agent that launches meme tokens on Four.meme and manages them post-launch — with every decision committed to a cryptographic chain and anchored on BNB Chain.

## Short description (150 chars)

Autonomous lifecycle agent for Four.meme: trust grading, phase-aware posts, MYX signals, DGrid consensus, on-chain Merkle attestation of every decision.

---

## The problem

**Only 1.34% of Four.meme tokens graduate.** Four.meme's roadmap today is three phases — Agent Skill Framework → Executable Agents → **Agentic Mode** (agents with on-chain identities launching tokens). Agentic Mode solves creation. It does not solve what happens after.

98.6% of tokens die within 72 hours because nothing manages them post-launch. No defense against whale dumps, no phase-aware content cadence, no way to verify what an "autonomous agent" actually did between insider-phase and public-phase graduation.

**FOUR-LIFE is Phase 4: Agent Lifecycle Operations.** The missing layer that turns one-shot launches into operated tokens.

## What FOUR-LIFE is

A production-deployed autonomous agent that runs the full lifecycle of a Four.meme token on BNB mainnet, with every stage anchored on-chain.

1. **Launches tokens on Four.meme** end-to-end — concept generated via DGrid, art via DALL-E (through DGrid), signs the Four.meme create-token tx, registers with the lifecycle engine. Example: **$AUNT (AuntieCoin)** — launched April 20, 2026, [tx `0x80ff903c…`](https://bscscan.com/tx/0x80ff903ca947448ec50927b866067b67e5bdd69a667f9d0f1b3af8f0c74869d2), [token on Four.meme](https://four.meme/en/token/0x568bf737887053ffa8aa4e82d8859ca4a9a14444).
2. **Manages the full lifecycle** — THINK (narrative analysis) → BIRTH (launch) → RAISE (nurture / defend / accelerate) → LEARN (persist outcomes). Two tokens live right now: $AUNT + KICAU. Real insider-phase / public-phase state transitions, not a simulator.
3. **Makes every decision verifiable** — every LLM call + every hedge signal is hashed into rolling Merkle chains; the tips are published on BNB Chain. Anyone can re-derive the chain locally and check our claims. **Lifecycle-wide attestation, not single-action**: we commit to the *sequence* of decisions across the full token life, not just individual trades.
4. **Four cross-partner integrations composed** — DGrid (cost-aware multi-model routing), MYX V2 (signal infrastructure), ERC-8004 (on-chain identity + reputation), Unibase (memory). DGrid's unified gateway enables 3-model consensus voting — a capability a single-provider agent literally cannot replicate.

---

## Truth-boundary — the thing you should check first

**A "Certified" tier is only issued when we have full on-chain data** (buy/sell events, whale distribution, holder velocity). For tokens we can only see via Four.meme's public ranking (no trade-level data), the API returns a **Radar Estimate** with `tier_source: "radar_estimate"` and a distinct version string `four-life-radar-v1`. These two tier-sources never collapse:

- Live badge: `GET /api/token/<addr>/badge` — every response carries `tier_source`.
- Embed widget: a radar_estimate badge displays **"FOUR-LIFE · Radar"**, not Certified, and the modal renders a "Heuristic estimate from public ranking data — not a Certified tier" banner.
- Webhooks + Telegram/Discord: `badge.tier_changed` events include `tier_source`; notifications brand radar_estimate transitions as "Radar Estimate," never "Certified."
- SDK: `Badge.tier_source: "certified" | "radar_estimate"` in TS (v0.2.0) + Python.
- History store: every snapshot row carries `tier_source`; `/api/token/<addr>/diff` exposes `from_source`/`to_source` on every transition so a provenance upgrade is a first-class transition.

This is the integrity line judges should attack. Untracked-token badge response at `/api/token/<any-addr>/badge` is honestly labelled "radar_estimate"; only tokens the agent is actively monitoring on-chain (`$AUNT`, `KICAU`) receive "certified".

---

## Why this wins the DGrid bounty

**DGrid is the agent's brain.** Every LLM task routes through it — narrative analysis, content generation, risk reasoning, vision, consensus voting. DGrid share on production is the first number on `/api/dgrid/stats` — judge this live, not from a claim in this doc.

### DGrid capabilities we shipped (unique / undeniable)

| Capability | What it proves |
|---|---|
| **Circuit breaker + transient retry + multi-provider fallback** (DGrid primary → OpenAI fallback; Anthropic slot wired and activates when `ANTHROPIC_API_KEY` is set) | Production-grade resilience; every fallback event is traced and counted, live on `/api/dgrid/trace` |
| **Multi-model consensus via DGrid** (`/api/dgrid/consensus`) | 3 models vote in parallel on a JSON field — **wired into the DEFEND phase of every token's lifecycle**. Impossible without a unified gateway. |
| **Chaos toggle** (`/api/dgrid/chaos`, admin-authed) | Flip DGrid to fail → fallback chain engages → flip back → breaker resets and next call tries DGrid |
| **On-chain Merkle attestation** | Every successful DGrid call folded into a SHA-256 hash chain. **3 roots published on BNB Chain** (see below). |
| **Independent verifier** | Pure-Python `verify_chain(calls, expected_root, expected_count=…)` + public log at `/api/dgrid/audit/calls` with deterministic `next_offset` / `has_more` pagination. Judges can re-derive the chain without trusting our server. |
| **Log-first attestation invariant** | The audit log entry is durably persisted (fsynced) **before** the chain tip advances. If the log write fails, the chain does not move — `verify_chain` always reconstructs `current_root` from the log. |
| **Cost tracking** | Per-model USD rate table; per-task / per-model breakdown visible on `/dgrid` |
| **Self-optimizing leaderboard** | Rolling per-(task, model) stats — success rate, latency, cost/call — opt-in auto-tune via `DGRID_AUTO_TUNE` |
| **Task-typed routing** | `narrative` / `content` / `risk` / `vision` / `consensus` / `image` each mapped; remappable via `DGRID_TASK_OVERRIDES` env var |

### DGrid on-chain attestations (verifiable right now)

| Tx | Root commits to | BscScan |
|---|---|---|
| DGrid attestation #1 | 15 DGrid calls | [`0xcf42283a…`](https://bscscan.com/tx/0xcf42283acebfc97657e87393684eedee40a21e98ba9c0b6b7480fa6c711a5c7c) |
| DGrid attestation #2 | 25 DGrid calls | [`0x047c2f58…`](https://bscscan.com/tx/0x047c2f58e77d349f98eac8305080970c391c0e39c378816c22e69fc0d6b18fe9) |
| DGrid attestation #3 | 1573 DGrid calls | [`0xab323590…`](https://bscscan.com/tx/0xab323590f4aaa1013960ac77a89a215690ce731f72405c6b10f7bcd75973a636) |

**Verify in 4 steps:** (1) read `current_root` + `num_calls_chained` from `/api/dgrid/audit`; (2) page `/api/dgrid/audit/calls` using `next_offset`/`has_more` until done; (3) call `verify_chain(log, current_root, expected_count=num_calls_chained)` locally; (4) compare against the tx `data` field on BscScan. Four independent paths to the same hash.

### DGrid integration surface

11 dedicated endpoints on [`/dgrid`](https://four-life.gudman.xyz/dgrid):

```
GET  /api/dgrid/stats          — task routing, fallback counts, cost $
GET  /api/dgrid/health         — green/amber/red reachability
GET  /api/dgrid/trace?limit=N  — last N calls with chain tips
GET  /api/dgrid/leaderboard    — per-(task, model) rolling stats
GET  /api/dgrid/audit          — current Merkle root + last publish
GET  /api/dgrid/audit/calls    — full call log for verification
POST /api/dgrid/probe          — force a DGrid-only call
POST /api/dgrid/compare        — N models, same prompt (auth)
POST /api/dgrid/consensus      — N models vote on a JSON field (auth)
POST /api/dgrid/chaos          — toggle simulated DGrid outage (admin)
POST /api/dgrid/attest         — publish Merkle root on BNB Chain (admin)
```

---

## What we built on MYX V2

**A decision-attestation layer for agent hedging on MYX V2, with every production BSC address wired from the official SDK. 452 hedge decisions cryptographically committed on BNB Chain at root [`0xeda29cc6…`](https://bscscan.com/tx/0xeda29cc60bc8ca9bb3b3d8f78cf0200cd39cd50a3b80cbb0f411d25025232026). Order execution is gated behind a one-line env flag pending broker-signer onboarding — the MYX SDK's permissioned architecture requires an integrator broker address issued by the MYX team, which we have publicly requested.**

The framing difference matters: most attempts at "agent trading" hide the decisions and commit only executions. We commit the **decisions** — what the agent decided, how the DGrid consensus voted, and with what inputs — so the cryptographic audit trail is complete even before trades can fire.

### Architecture — reverse-engineered from MYX's official SDK

MYX V2 on BSC mainnet is a **permissioned broker architecture**. Orders don't flow directly to TRADING_ROUTER; they flow through a per-integrator **BrokerSigner** contract issued manually by the MYX team. We confirmed this by reading `github.com/myx-protocol/myx-trade/src/config/address/BSC_MAINET_NET.ts` (their production SDK) and their integration guide which explicitly states `brokerAddress: "Get from MYX team"`.

```
User wallet
   │ approve collateral token
   ▼
TRADING_ROUTER (0xb0c56a23…)  ← approval target
   ▲
   │ placeOrderWithSalt submitted by broker on user's behalf
   │
BrokerSigner  ← issued per integrator by MYX team (permissioned)
   │
   ▼
ORDER_MANAGER (0x8d38a857…) → POSITION_MANAGER (0x04218C23…) → Pools + Oracle
```

### Every production BSC address wired

From `myx-trade/src/config/address/BSC_MAINET_NET.ts`:

| Role | Address |
|---|---|
| TRADING_ROUTER | `0xb0c56a233535971b8903497f98b90Cf53aE77A13` |
| ORDER_MANAGER | `0x8d38a857390E1586481cF8994F4feBc315D0249b` |
| POSITION_MANAGER / POOL_MANAGER | `0x04218C23f89cAA2E4395a7Bd94410057705D1184` |
| BASE_POOL | `0x6a775E908629eFC6357b3d89E5528524a6f378Dd` |
| QUOTE_POOL | `0x73b2dcfdc7dC78a7A51B778E93c09FC173923BcE` |
| ORACLE | `0xAdD60e47D2C5e7d57B1e5a3F9d24dE43933b8A7A` |
| FORWARDER | `0xD0894e09317F455dd698A706bb62D783e95aA7Ad` |
| BROKER_ADDRESS | *pending MYX team onboarding* |

All addresses are hardcoded in `agent/config.py` and wired into `agent/myx/client.py`. The day MYX issues us a broker, flipping `MYX_EXECUTION_ENABLED=true` + `MYX_BROKER_ADDRESS=0x…` is the single change needed.

### What is on-chain for MYX

| Tx | Root commits to | BscScan |
|---|---|---|
| MYX decision attestation #1 | 2 hedge decisions | [`0x0d43051c…`](https://bscscan.com/tx/0x0d43051c24fd59359317d12ce3137512a1c7cb032528bf813d506545fcf06698) |
| MYX decision attestation #2 | 452 hedge decisions | [`0xeda29cc6…`](https://bscscan.com/tx/0xeda29cc60bc8ca9bb3b3d8f78cf0200cd39cd50a3b80cbb0f411d25025232026) |
| MYX decision attestation #3 | 518 hedge decisions | [`0x5c5b9876…`](https://bscscan.com/tx/0x5c5b9876cc85d54e01b69d03ee8709d32370fe64374a02ddf1ac521ddc0437af) |

Three decision-attestation roots prove the agent is continuously making real hedge decisions on MYX via a cryptographic chain — 518 decisions committed on BNB Chain as of the latest publish, each carrying the action, confidence, size %, reasoning hash, and (for consensus-backed decisions) per-model vote metadata.

### MYX capabilities we shipped

| Capability | What it proves |
|---|---|
| **Live connection to MYX V2** — 37 perp markets fetched from `api.myx.finance` | Real integration, not mocked |
| **Phase-aware hedge signals** | Per token, every 5 min: action (long/short/close/hold) + confidence + size_pct + reasoning |
| **DGrid consensus on DEFEND** | 3 DGrid models vote in parallel on every high-stakes hedge decision. 452 such votes already committed on-chain at root `0xeda29cc6…`. |
| **Signal attestation chain** (separate from trade chain) | Cryptographic commitment to every decision, publishable on-chain before execution |
| **Shape-preview calldata** (`/api/myx/calldata/{token}`) | Unsigned `createIncreaseOrder` tx against MYX V2's struct — decode locally to verify struct packing. Production orders route through the broker-signer pattern. |
| **Live consensus demo** (`/api/myx/consensus/{token}`) | Click-button fan-out across 3 DGrid models; returns per-model verdicts + majority vote |
| **On-chain pool read** | `getPairIndex(WBNB, USDT)` resolves live from the verified MYX V2 pool `0x22cEc08111BBae24D0b80BDA2a6503EaB9BA704b` |
| **Signal-only by default** | Execution gated by `MYX_EXECUTION_ENABLED`; safe and explicit until we're onboarded |

### MYX integration surface

13 endpoints on [`/myx`](https://four-life.gudman.xyz/myx):

```
GET  /api/myx/status             — live MYX V2 state + 37 markets
GET  /api/myx/portfolio          — per-token hedge summary
GET  /api/myx/positions/{token}  — position detail
GET  /api/myx/signal/{token}     — one-shot AI signal
GET  /api/myx/signals?limit=N    — unbounded signal history
GET  /api/myx/audit              — trade Merkle tip + last publish
GET  /api/myx/audit/events       — full position event log
GET  /api/myx/signal-attestation — signal Merkle tip + last publish
GET  /api/myx/calldata/{token}   — shape-preview unsigned tx
POST /api/myx/evaluate/{token}   — trigger hedge eval
POST /api/myx/consensus/{token}  — fan decision across 3 DGrid models
POST /api/myx/attest             — publish trade root on BNB Chain (admin)
POST /api/myx/attest-signals     — publish signal root on BNB Chain (admin)
```

### Honest MYX framing — claiming the MYX bounty on decision-attestation depth

Submitting for the MYX bounty on the basis of decision-attestation depth plus production-ready infrastructure. Three things judges can verify independently:

1. **The architecture is correctly reverse-engineered** — every BSC mainnet address in our config matches the official MYX SDK (`TRADING_ROUTER`, `ORDER_MANAGER`, `POSITION_MANAGER`, `POOL_MANAGER`, base + quote pools, oracle, forwarder).
2. **The decision-attestation layer is live** — 452 DEFEND-phase hedge decisions committed to a Merkle chain published on BNB Chain at root `0xeda29cc6…`. Every decision carries the action, confidence, size percent, reasoning hash, and (for consensus-backed decisions) the per-model vote metadata. An independent verifier can paginate `/api/myx/signal-attestation` and fold each digest to reproduce the published root.
3. **The remaining execution gap is a protocol design choice, not a tooling gap** — MYX V2 gates brokers by design (per the official SDK's `brokerAddress: "Get from MYX team"` requirement) and onboarding is a manual conversation with the MYX team. We have reached out publicly on multiple channels. The moment a broker address is issued, `MYX_EXECUTION_ENABLED=true` + `MYX_BROKER_ADDRESS=0x…` unlocks execution — everything downstream is already wired.

We submit this to the MYX bounty on decision-attestation depth: the cryptographic audit trail of every hedge decision the agent has ever made, published on BNB Chain, verifiable by anyone, and independent of when (or whether) orders eventually fire.

---

## Production state (verifiable right now)

- **Live site:** https://four-life.gudman.xyz
- **Agent wallet:** `0x695E492398A51D2Ef5c699818e9616718aaEd1c1` — [BscScan](https://bscscan.com/address/0x695E492398A51D2Ef5c699818e9616718aaEd1c1)
- **ERC-8004 Agent ID 20** — [registration tx](https://bscscan.com/tx/0x62a1a43d9e782686b833ed44eee7ea95a9ee3370f2f372334dc7bbf85cc14762), [agent card](https://four-life.gudman.xyz/.well-known/agent-registration.json)
- **$AUNT launched by agent** — [token](https://bscscan.com/token/0x568bf737887053ffa8aa4e82d8859ca4a9a14444) · [launch tx](https://bscscan.com/tx/0x80ff903ca947448ec50927b866067b67e5bdd69a667f9d0f1b3af8f0c74869d2) · [Four.meme](https://four.meme/en/token/0x568bf737887053ffa8aa4e82d8859ca4a9a14444)
- **6 on-chain attestation txs** (links above): 3 DGrid + 3 MYX decision roots
- **367 tests passing** across agent/badge/consensus/history/MYX/webhooks/protection/notifications/SDK
- **Tech stack:** Python 3.12 / FastAPI / web3.py / viem / Next.js 16 (static export) / nginx + systemd / SQLite + JSONL chains
- **API surface:** 50+ routes across DGrid (11), MYX (13), platform primitives, webhooks, protection, notifications, creators, contract analyzer, identity, radar
- **SDKs:** TypeScript (`@gudman/four-life-sdk` v0.2.0) + Python (`four-life`) + Chrome MV3 extension

---

## Security & integrity guarantees

- **Admin routes** (`/api/agent/*`, `/api/dgrid/{chaos,compare,consensus,attest}`, `/api/myx/attest*`, `/api/history/export.ndjson`, webhook + protection writes) require a bearer `API_SECRET`. Server refuses to boot without one in production (`AGENT_ENV=prod`).
- **Rate limits per real client IP** (not collapsed to loopback) via `proxy_headers` + `forwarded_allow_ips="127.0.0.1"`; separate buckets for public reads, writes, and LLM-burn endpoints.
- **Tight CORS**: `allow_origins` limited to `four-life.gudman.xyz` and `four.meme`. Browser visitors can't weaponize other sites to burn our DGrid credits.
- **Wallet serialization**: on-chain attestation publishing runs under a module-level `asyncio.Lock`, reads nonce with `"pending"`, and awaits `wait_for_transaction_receipt` before recording the tx hash — no ghost hashes can appear in the audit page.
- **Redactor**: error paths strip known secret prefixes (`sk-`, `sk-ant-`, `dgrid_`, `ghp_`, `xox…`, `AIza`, `AKIA`, `hf_`, `gsk_`, `r8_`, `pcsk_`, `SG.`, `CFPAT-`, `dop_v1_`, `sk_live_`, `rk_live_`) plus JWTs (`eyJ…`) before any error reaches a trace / log / public surface.
- **Address validation**: every `/api/token/{addr}/*` path rejects malformed addresses at 400 before touching the DB, preventing free bloat of the history store from garbage keys.

---

## The pitch in one paragraph

FOUR-LIFE is a Four.meme agent where "autonomous" isn't marketing — it's cryptographically provable. The agent launches meme tokens on Four.meme, manages their full lifecycle (posts, defense, hedging), and anchors every decision on BNB Chain via Merkle chains anyone can verify without trusting us. The truth-boundary is honest: a "Certified" tier requires full on-chain data; public-ranking heuristics are returned as "Radar Estimate" with a distinct version string and explicit UI treatment. Five on-chain attestation transactions back the "did the agent actually do what you say?" question with BscScan URLs.

---

## Judging rubric walkthrough

| Criterion | Weight | How FOUR-LIFE delivers |
|---|---|---|
| **Innovation** | 30% | On-chain Merkle attestation of every LLM call across a token's full lifecycle. Multi-model DGrid consensus wired into every DEFEND-phase hedge decision — the unified gateway makes this a single fan-out, not per-provider plumbing. Explicit Certified-vs-Radar-Estimate split with per-surface enforcement (SDK, embed, webhooks, notifications, history) — the trust boundary is enforced, not claimed. |
| **Technical Implementation** | 30% | 367 tests passing. Production-deployed. Real on-chain txs (agent launch, ERC-8004 registration, 6 Merkle attestations). Circuit breaker + multi-provider fallback + chaos-testable. Log-first attestation invariant (no ghost-hash scenario). Wallet-signing serialized + receipt-awaited. Full OpenAPI spec + independent pure-Python verifier. |
| **Practical Value** | 20% | Addresses Four.meme's top operational problem (~98% death rate) with infrastructure Four.meme-adjacent projects can adopt today: SDKs, embeddable badge with honest radar-estimate labelling, signed webhooks, Chrome extension. $AUNT is a real token the agent is managing — not slideware. |
| **Presentation** | 20% | Landing page with live data on every panel. Dedicated showcase pages for DGrid and MYX with live Merkle tips, chaos toggle, consensus demo. Every claim in this document traces to a specific URL, BscScan tx, or source file. |

---

## Install

```bash
pip install four-life                 # Python SDK
npm install @gudman/four-life-sdk     # TS SDK (v0.2.0 — adds tier_source)
```

```python
from four_life import FourLife
fl = FourLife()
resp = fl.get_badge("0x568bf737887053ffa8aa4e82d8859ca4a9a14444")  # $AUNT
print(resp["badge"]["tier"], "—", resp["tier_source"])
# e.g. "observed — certified"
```

---

## Links

- **Live product:** https://four-life.gudman.xyz
- **DGrid showcase:** https://four-life.gudman.xyz/dgrid
- **MYX showcase:** https://four-life.gudman.xyz/myx
- **Graduation Radar:** https://four-life.gudman.xyz/radar
- **Creator Ledger:** https://four-life.gudman.xyz/creators
- **API docs:** https://four-life.gudman.xyz/docs
- **Agent Card:** https://four-life.gudman.xyz/.well-known/agent-registration.json
- **Source:** https://github.com/Ridwannurudeen/four-life
- **Demo video:** _recorded separately — link will be supplied in the DoraHacks submission form_

---

## Team

Ridwan Nurudeen ([@gudman](https://github.com/Ridwannurudeen)) — solo builder.

---

## What's next (post-hackathon, explicitly NOT claimed as shipped)

- **MYX execution** — flip `MYX_EXECUTION_ENABLED=true` once the MYX team issues a broker address. All signal-to-execution infrastructure is already wired.
- **Dedicated X/Twitter account for the agent** — agent already drafts posts via DGrid; needs API credentials to broadcast.
- **Four.meme native badge embed** — so the trust layer reaches users where they transact.
- **Badge API as primitive for other agents** — expose `/api/token/{addr}/badge` + `tier_source` as a signal other Four.meme-adjacent agents can consume.

---

## Form-filling cheat sheet

| DoraHacks field | Value |
|---|---|
| Project name | `FOUR-LIFE` |
| Track | Autonomous Workflows |
| Is this BUIDL an AI Agent | Yes |
| Tagline | Verifiably-autonomous lifecycle agent for Four.meme with on-chain Merkle attestation of every decision |
| Repo URL | `https://github.com/Ridwannurudeen/four-life` |
| Demo URL | `https://four-life.gudman.xyz` |
