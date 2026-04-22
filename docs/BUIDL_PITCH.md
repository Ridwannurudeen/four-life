# DoraHacks BUIDL 43235 — Pitch drafts

Copy-paste ready text for the BUIDL fields. Three lengths below — pick the one that fits the DoraHacks form field.

---

## Short (tagline — ≤200 chars)

Verifiably-autonomous lifecycle agent for Four.meme. Launches tokens, manages the full lifecycle, and anchors every LLM call + hedge signal on BNB Chain. Five attestation txs you can verify now.

---

## Medium (≤500 chars)

Four.meme's Agentic Mode creates tokens — then ~98% die within 72h because nothing manages them after launch. FOUR-LIFE is the Phase-4 lifecycle agent: launches tokens on Four.meme end-to-end, manages them via a THINK → BIRTH → RAISE → LEARN loop, hedges on MYX, and commits every decision to on-chain Merkle chains. 5 attestation txs live. 367 tests. Real token ($AUNT) under management. Judges verify claims by BscScan, not trust.

---

## Full pitch (≤1500 chars — replaces the current BUIDL pitch)

**~98% of Four.meme tokens die in the first 72 hours.** Creation is solved; lifecycle is not. Four.meme's Agentic Mode launches — FOUR-LIFE is the missing Phase 4: an autonomous agent that manages a token's full post-launch lifecycle and cryptographically commits every decision on BNB Chain.

What's live on `four-life.gudman.xyz`:

- **Real token under management.** $AUNT — launched on Four.meme end-to-end by the agent (concept via DGrid, art via DALL-E, signed create-token tx). Launch tx `0x80ff903c…`.
- **Strict truth-boundary.** "FOUR-LIFE Certified" is only issued when we have full on-chain data. Public-ranking tokens get a "Radar Estimate" with `tier_source: "radar_estimate"` and a distinct version. Embed, webhooks, notifications, and SDK all enforce the split — never pretend a heuristic is Certified.
- **DGrid is the brain.** Every LLM call routes through it. Three-model consensus voting wired into every token's DEFEND phase — a capability single-provider agents literally cannot replicate. Circuit breaker + multi-provider fallback (DGrid primary → OpenAI; Anthropic slot activates when configured) + chaos toggle + on-chain cost accounting.
- **Five on-chain attestation txs.** 3 DGrid roots (committing 1,573 LLM calls) + 2 MYX signal roots (452 signals). Anyone can page `/api/dgrid/audit/calls`, run `verify_chain()` locally, and confirm each root.
- **MYX V2 signal infrastructure.** Every production BSC address wired. Phase-aware hedge signals attested on-chain. Signal-only by honest design — execution waits on MYX broker onboarding.

367 tests. ERC-8004 Agent ID 20. Every claim traces to a BscScan URL or source file.

**FOUR-LIFE is the first Four.meme agent where "autonomous" isn't marketing — it's cryptographically provable.**

---

## DoraHacks form fields cheat sheet

| Field | Value |
|---|---|
| Project name | `FOUR-LIFE` |
| Tagline | *(use Short above)* |
| Track | Autonomous Workflows |
| Is this BUIDL an AI Agent | Yes |
| Repo URL | `https://github.com/Ridwannurudeen/four-life` |
| Demo URL | `https://four-life.gudman.xyz` |
| Description | *(use Full above)* |
| Video URL | *(paste after recording per `DEMO_SCRIPT.md`)* |

---

## Rationale (not submission copy — internal notes)

**The positioning that anchors every version of the pitch:**

- Four.meme solved creation (Agentic Mode). FOUR-LIFE is the lifecycle layer — Phase 4: Agent Lifecycle Operations.
- The differentiator isn't "AI agent for meme tokens" (generic) — it's **on-chain cryptographic attestation of every decision in a token's life**, from insider-phase launch through public-phase graduation.
- The concrete proof: 1,573 LLM calls + 452 MYX signals committed to Merkle chains published on BNB Chain. 5 BscScan tx hashes anyone can click.

**One-liner to use in spoken judging:**

> "The first Four.meme agent where 'autonomous' isn't marketing — it's cryptographically provable."
