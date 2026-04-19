# DoraHacks Submission — FOUR-LIFE

Paste-ready content for the Four.meme AI Sprint submission form. Edit the bracketed placeholders before submitting.

---

## Project Title

**FOUR-LIFE — The trust + lifecycle layer for Four.meme launches**

## One-line tagline

Deterministic trust grading, protection mode, and signed webhooks for every Four.meme token — so agents know which tokens survive, and can act when they don't.

## Short description (150 chars)

Post-launch lifecycle agent + trust layer for Four.meme. Deterministic badges, protection mode, webhooks, Telegram/Discord alerts, TS + Python SDKs.

---

## Long description

### The problem

Four.meme's Agentic Mode ships thousands of tokens per week. **98.6% die within 72 hours.** Creation is solved — but there's no infrastructure for the *post-launch* lifecycle. No way to grade trust at a glance, no way for agents to react to a token going sideways, no shared language for "this one is surviving."

### What FOUR-LIFE ships

A complete post-launch layer with three public trust primitives and a full operator toolkit:

1. **FOUR-LIFE Certified badge** — Deterministic tier (graduated / graduation_watch / healthy / at_risk / observed) with a full `why[]` rule trace. Computed from raw on-chain metrics + pair-aware graduation targets sourced live from Four.meme's config. **Zero LLM in the trust path** — every grade is reproducible.

2. **Protection Mode** — Per-token defensive thresholds (whale concentration, sell pressure, contract rug signals). Deterministic verdicts (safe / warn / critical). On `critical`, FOUR-LIFE halts content posts, fires a signed webhook, and emits a short-hedge signal via MYX V2.

3. **Creator Ledger** — Every creator wallet ever observed, ranked by deterministic trust tier, with per-launch evidence. Judges can verify the ranking.

Plus an **autonomous lifecycle engine** that manages the full loop:

**THINK** → narrative analysis (DGrid-routed LLM with 3-tier fallback) →
**BIRTH** → launch via Four.meme Agentic Mode + ERC-8004 reputation registration →
**RAISE** → real-time on-chain health monitoring, transparency posts, milestone celebration, whale-defense →
**LEARN** → evaluate outcomes, persist to Unibase memory, improve next launch.

### Built on partner tech

- **DGrid AI Gateway** (bounty target) — every LLM call routes through DGrid. 3-tier fallback (DGrid → Anthropic → OpenAI) so the demo never black-holes. Every LLM-backed response includes an `llm_provider` field for auditability.
- **MYX V2 Perps** (bounty target) — signal layer live by default (AI-generated long/short/hold/close per phase). Execution layer opt-in behind `MYX_EXECUTION_ENABLED` so the demo surface never submits on-chain orders with hardcoded collateral.
- **ERC-8004 / BRC-8004** — agent registered on BSC as **Agent ID 20** ([tx](https://bscscan.com/tx/0x62a1a43d9e782686b833ed44eee7ea95a9ee3370f2f372334dc7bbf85cc14762)). Graduated tokens trigger on-chain reputation attestations via `giveFeedback`.
- **Unibase / Membase** — persistent learning memory across launches.

### Production surface

- **46 API routes** across platform primitives, webhooks, protection, notifications, creators, contract, identity, radar, DGrid, MYX
- **7 public web pages**: landing, radar, creators, webhooks docs, embed docs, dashboard, agent card
- **3 SDKs**: TypeScript (`@gudman/four-life-sdk`), Python (`four-life`), Chrome extension
- **2 event channels**: signed HMAC webhooks + Telegram/Discord fan-out
- **275 Python tests + 32 Python SDK tests + 9 TS SDK tests** — 316 total, all passing
- **Fully deployed**: https://four-life.gudman.xyz

### Why this wins

Other agents do creation → dump → repeat. FOUR-LIFE is the first Four.meme agent that **stays with the token after launch** — and the first trust layer agents can actually *trust*, because every grade is reproducible from raw data with no LLM in the path.

---

## Links

- **Live product:** https://four-life.gudman.xyz
- **Graduation Radar:** https://four-life.gudman.xyz/radar
- **Creator Ledger:** https://four-life.gudman.xyz/creators
- **Webhooks Docs:** https://four-life.gudman.xyz/webhooks
- **OpenAPI Spec:** https://four-life.gudman.xyz/docs
- **ERC-8004 Agent Card:** https://four-life.gudman.xyz/.well-known/agent-registration.json
- **Source:** https://github.com/Ridwannurudeen/four-life
- **Demo video:** [PASTE YOUTUBE/LOOM LINK]

## Install

```bash
# Python
pip install four-life

# TypeScript / JavaScript
npm install @gudman/four-life-sdk
```

```python
from four_life import FourLife
fl = FourLife()
badge = fl.get_badge("0x72b0a042e19871c046c1bd31e5b5ad3770c94444")
print(badge["badge"]["tier"])  # "observed" | "healthy" | "graduation_watch" | ...
```

## Why this scores against the judging rubric

| Criterion | Weight | How FOUR-LIFE delivers |
|---|---|---|
| **Innovation** — originality and depth of AI application | 30% | Deterministic trust path with **zero LLM in grading** is a deliberate AI-architecture choice (not absence of AI). 3-tier LLM fallback (DGrid → Anthropic → OpenAI) keeps demos honest. Pair-aware graduation targets pulled live from Four.meme's `/public/config` show platform-native depth most submissions skip. THINK → BIRTH → RAISE → LEARN is a real autonomous loop, not a one-shot inference. |
| **Technical Implementation** — code quality and demo stability | 30% | 316 tests passing across Python core + TS SDK + Python SDK. 46 API routes, 7 web pages, 3 SDKs (TS / Python / Chrome MV3 extension). Real on-chain integrations: ERC-8004 Agent ID 20 verifiable on BscScan, MYX V2 Pool read directly from chain, BNB Chain RPC monitoring. Production stack: nginx + Let's Encrypt + systemd, signed-HMAC webhooks, per-IP rate limiting, full OpenAPI spec, SQLite persistence. Live and uptime-monitored at four-life.gudman.xyz. |
| **Practical Value** — user impact or commercial potential | 20% | Addresses Four.meme's top operational problem (98.6% of tokens die within 72h). Distribution surface that any Four.meme-adjacent project can adopt today: SDKs (`pip install four-life`, `npm install @gudman/four-life-sdk`), embeddable Certified badge, signed webhooks, Telegram + Discord notifications, Chrome extension. Six platform endpoints turn one-off agent insights into a shared trust primitive. |
| **Presentation** — clarity of pitch and execution capability | 20% | Production-grade landing page with live data. Full demo video walking through Radar → Certified badge → Protection Mode → Webhooks → Operator Checklist. README + OpenAPI docs + per-endpoint examples. SUBMISSION.md tracks every claim back to a verifiable artifact. |

## Bounty claims

### Main prize (FOUR-LIFE autonomous agent)
Directly extends Four.meme's Agentic Mode with the missing post-launch phase. Addresses their #1 problem (token death rate). Uses every piece of partner tech explicitly called out in the hackathon brief.

### MYX V2 integration (technical highlight, not a bounty claim)
The MYX V2 bounty requires launching the agent's own token on Four.meme and seeding **$20,000 of liquidity** to activate a perp pair — outside scope for a solo hackathon submission. We're not claiming this bounty.

What we did build on MYX V2 (so the technical work is visible to judges):
- **On-chain Pool wired**: `MYX_POOL_ADDRESS=0x22cEc08111BBae24D0b80BDA2a6503EaB9BA704b` (the verified MYX V2 Pool on BSC). `getPairIndex(WBNB, USDT)` resolves to `3` directly from chain — no hardcoded constants.
- **Live market data**: 37 perp markets fetched live from `api.myx.finance`.
- **Phase-aware AI signal layer**: `GET /api/myx/signal/{token}` returns long/short/close/hold with confidence per lifecycle phase (NURTURE=monitor, DEFEND=short hedge, ACCELERATE=scale, GRADUATED=close all).
- **Execution layer is implemented and tested** but disabled at submission because (a) MYX V2's BSC Router is an ERC-1967 proxy with unverified implementation we couldn't fork-simulate against in the available time, and (b) the bounty's $20K liquidity requirement makes real activation infeasible.

### DGrid bounty — eligibility + unbeatable audit surface

**Requirement check:**
- ✅ Uses DGrid's AI Gateway API (primary provider in `agent/brain/llm.py` via the OpenAI-compatible SDK)
- ✅ Functional prototype — fully deployed at four-life.gudman.xyz with 10+ live tokens ticking

**What makes our DGrid integration defensible under any audit:**

1. **Dedicated showcase page:** [`/dgrid`](https://four-life.gudman.xyz/dgrid) — live counters, provider share, fallback chain diagram, task-routing map, last 20 calls with per-call latency + token counts, and a **"probe DGrid now"** button judges can click to verify a live DGrid-served call on demand.

2. **Four public audit endpoints:**
   - `GET /api/dgrid/stats` — per-task routing, per-provider counters, per-model usage, token totals, fallback events
   - `GET /api/dgrid/health` — green/amber/red reachability state + last error
   - `GET /api/dgrid/trace?limit=50` — ring-buffer log of every LLM call (success + failure) with provider, model, task, latency, tokens, fallback depth, error
   - `POST /api/dgrid/probe` — force a DGrid-only call with no fallback; returns raw DGrid response + timing

3. **Cost-aware routing** — every task (narrative, content, risk, vision) defaults to `google/gemini-2.5-flash` via DGrid so even a small credit sustains the full judging window. Operators can promote specific tasks to a heavier model via `DGRID_TASK_OVERRIDES=content=anthropic/claude-sonnet-4.5,risk=openai/gpt-4o` — one env var, no code change.

4. **3-tier resilient fallback:** DGrid → Anthropic → OpenAI. If DGrid returns `BALANCE_INSUFFICIENT` / rate-limit / 5xx, the agent transparently degrades and retries DGrid on the next call. Every fallback event is logged with the DGrid error that triggered it — no silent failures.

5. **Per-response provenance:** every public LLM-backed response (`/api/token/{addr}/badge`, operator checklist, risk snapshot, MYX signal, etc.) includes an `llm_provider` field identifying which provider served that specific decision. Audit one response, see exactly which model made the call.

6. **Full trace on the ring buffer:** last 200 calls kept in memory. No sampling, no aggregation — judges see every call, including failures, including which DGrid error caused each fallback.

## Tech stack

- **Agent core:** Python 3.11, FastAPI, asyncio
- **Blockchain:** web3.py, BNB Chain RPCs, ERC-8004 on-chain reputation
- **Persistence:** SQLite (history, webhooks, protection) + Unibase (agent memory) + local JSON (launch records)
- **Frontend:** Next.js 16 + Tailwind + Recharts (static export, served via nginx)
- **SDKs:** TypeScript (zero-dep, browser + Node), Python (httpx, sync + async), Chrome MV3 extension
- **Deployment:** Contabo VPS (Ubuntu), nginx + Let's Encrypt, systemd, single uvicorn worker

## Team

Ridwan Nurudeen ([@gudman](https://github.com/Ridwannurudeen)) — solo builder.

## What's next

- Four.meme native integration (embed the FOUR-LIFE Certified badge on token pages)
- AvengerDAO partnership for rug-pull flagging
- Expand the signal bus to additional DEX venues beyond MYX

---

## Form-filling cheat sheet

| DoraHacks field | Paste |
|---|---|
| Project name | `FOUR-LIFE` |
| Track | **Autonomous Workflows** |
| Is this BUIDL an AI Agent | Yes |
| Tagline | Deterministic trust grading, protection mode, and signed webhooks for every Four.meme token. |
| Repo URL | `https://github.com/Ridwannurudeen/four-life` |
| Demo URL | `https://four-life.gudman.xyz` |
| Video URL | [YOUR_UNLISTED_YOUTUBE_OR_LOOM] |
| License | MIT |
| Description | Paste the "Long description" above |
| Bounty selections | **DGrid only.** MYX V2 not claimed (requires $20K liquidity to activate a perp pair — out of scope for solo hackathon). |
