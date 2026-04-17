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
- **ERC-8004 / BRC-8004** — agent registered on BSC. Graduated tokens trigger on-chain reputation attestations.
- **Unibase / Membase** — persistent learning memory across launches.

### Production surface

- **46 API routes** across platform primitives, webhooks, protection, notifications, creators, contract, identity, radar, DGrid, MYX
- **7 public web pages**: landing, radar, creators, webhooks docs, embed docs, dashboard, agent card
- **3 SDKs**: TypeScript (`@gudman/four-life-sdk`), Python (`four-life`), Chrome extension
- **2 event channels**: signed HMAC webhooks + Telegram/Discord fan-out
- **275 Python tests + 32 Python SDK tests + 8 TS SDK tests** — 315 total, all passing
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

## Bounty claims

### Main prize (FOUR-LIFE autonomous agent)
Directly extends Four.meme's Agentic Mode with the missing post-launch phase. Addresses their #1 problem (token death rate). Uses every piece of partner tech explicitly called out in the hackathon brief.

### MYX V2 bounty
- Signal layer live (default): `GET /api/myx/signal/{token}` returns AI-generated long/short/close/hold with confidence per lifecycle phase.
- Execution layer ready: phase-based (NURTURE=monitor, DEFEND=short hedge, ACCELERATE=scale, GRADUATED=close all). Opt-in via `MYX_EXECUTION_ENABLED=true`.
- Fully-tested hedge manager with MYX V2 permissionless-pair awareness.

### DGrid bounty
- **Every LLM call** in the agent (narrative analysis, content generation, strategy decisions, raise-plan generation) routes through DGrid's unified OpenAI-compatible API.
- 3-tier fallback: DGrid → Anthropic → OpenAI. If DGrid returns balance/rate-limit/5xx, FOUR-LIFE transparently falls back.
- `/api/dgrid/stats` endpoint exposes per-task/per-model routing, fallback events, and usage counters for auditability.
- Every response includes an `llm_provider` field identifying which provider served the call.

## Tech stack

- **Agent core:** Python 3.11, FastAPI, asyncio
- **Blockchain:** web3.py, BNB Chain RPCs, ERC-8004 on-chain reputation
- **Persistence:** SQLite (history, webhooks, protection) + Unibase (agent memory) + local JSON (launch records)
- **Frontend:** Next.js 16 + Tailwind + Recharts (static export, served via nginx)
- **SDKs:** TypeScript (zero-dep, browser + Node), Python (httpx, sync + async), Chrome MV3 extension
- **Deployment:** Contabo VPS (Ubuntu), nginx + Let's Encrypt, systemd, single uvicorn worker

## Team

[YOUR NAME] — Solo builder.

## What's next

- Four.meme native integration (embed the FOUR-LIFE Certified badge on token pages)
- AvengerDAO partnership for rug-pull flagging
- Expand the signal bus to additional DEX venues beyond MYX

---

## Form-filling cheat sheet

| DoraHacks field | Paste |
|---|---|
| Project name | `FOUR-LIFE` |
| Track | AI Sprint |
| Tagline | Deterministic trust grading, protection mode, and signed webhooks for every Four.meme token. |
| Repo URL | `https://github.com/Ridwannurudeen/four-life` |
| Demo URL | `https://four-life.gudman.xyz` |
| Video URL | [YOUR_UNLISTED_YOUTUBE_OR_LOOM] |
| Description | Paste the "Long description" above |
| Bounty selections | DGrid + MYX V2 (check both) |
