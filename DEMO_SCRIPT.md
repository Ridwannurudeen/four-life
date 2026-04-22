# FOUR-LIFE Demo Scripts

Two scripts:

- **A. 90-second live-presentation script** — the 4-beat cut for stage / Zoom judging sessions (launch → certify → react → prove).
- **B. 2:30 video script** — the uploaded demo on DoraHacks. Richer, covers DGrid + MYX + why-it-wins.

Pick A if you have ≤2 min with judges. Always upload B alongside the submission.

---

## A. 90-second live-presentation script — 4 beats

**Tone:** direct, confident. Every sentence should add a fact. No hedging.

### Beat 1 — LAUNCH (0:00 – 0:20)

**On-screen:** Switch to Four.meme → https://four.meme/en/token/0x568bf737887053ffa8aa4e82d8859ca4a9a14444
**Say:**
> "$AUNT is a real Four.meme token. An autonomous agent launched it — generated the narrative via DGrid, created the art via DALL-E through DGrid, signed the create-token transaction on BNB Chain, and is now managing the token's lifecycle. Here's the launch tx on BscScan — `0x80ff903c…`. Not a mockup."

### Beat 2 — CERTIFY / FLAG (0:20 – 0:45)

**On-screen:** Open `https://four-life.gudman.xyz/api/token/0x568bf737887053ffa8aa4e82d8859ca4a9a14444/badge` in a browser tab or curl terminal.
**Say:**
> "For every Four.meme token, FOUR-LIFE issues a Certified tier — deterministic, derived from raw on-chain data, with a why-array trace. But the truth-boundary is strict: tokens we can only see via public ranking get `tier_source: radar_estimate` and a distinct version. A Certified tier is never issued from heuristics. You can call `/api/token/<any-address>/badge` and the source is labelled honestly."

**On-screen (optional):** hit `/api/token/0x<random>/badge` to show `tier_source: radar_estimate`, then `/api/token/0x568bf…/badge` to show `tier_source: certified`.

### Beat 3 — REACT (0:45 – 1:05)

**On-screen:** Open `/dgrid` page. Click **"kill DGrid"** (chaos toggle).
**Say:**
> "Every LLM call routes through DGrid — narrative, content, risk, consensus. I'm forcing DGrid to fail right now. The circuit breaker trips, the fallback chain engages, the agent keeps working through Anthropic → OpenAI. Click restore. Breaker resets, DGrid is back. Judges can demonstrate resilience live, on stage."

### Beat 4 — PROVE (1:05 – 1:30)

**On-screen:** Scroll to On-chain attestation card. Click the `0xab323590…` BscScan link.
**Say:**
> "Every DGrid call is hashed and folded into a Merkle chain. The tip is published on BNB Chain as a self-transaction — this one commits to 1,573 LLM calls. Five on-chain roots in total across DGrid and MYX. Any judge can download `/api/dgrid/audit/calls`, call `verify_chain()` locally, and confirm the root matches the on-chain data. Zero server trust. That's why I can say 'autonomous' without asking you to take my word for it."

---

## B. 2:30 video script

Target: **2:30**. Upload as **unlisted YouTube** so DoraHacks judges can watch without spam.

**Recording setup**
- Screen: OBS or Loom at 1920×1080. Cursor highlight on.
- Audio: any decent USB mic. Quiet room. No music.
- Tabs pre-loaded (in order): `/` → `/dgrid` → BscScan attestation tx → `/myx` → BscScan $AUNT launch tx → `four.meme/en/token/0x568bf…`
- Keep BscScan in a second tab so you can click the attestation link live.

**Tone:** direct, confident, "here's what we shipped". No apologies, no hedging.

---

### Segment 1 — Hook (0:00 – 0:15)

**On-screen:** Homepage `/`.
**Voice:**
> "~98% of Four.meme tokens die within 72 hours. Creation is solved — nothing manages them after launch. We built FOUR-LIFE: an autonomous agent that launches meme tokens and manages their full lifecycle, with every decision cryptographically anchored on BNB Chain."

---

### Segment 2 — The live token (0:15 – 0:35)

**On-screen:** Switch to Four.meme tab → https://four.meme/en/token/0x568bf737887053ffa8aa4e82d8859ca4a9a14444 (AUNT page).
**Voice:**
> "This is AUNT — AuntieCoin — a real Four.meme token the agent launched end-to-end. The agent generated the concept via DGrid narrative analysis, generated the art via DALL-E through DGrid, signed the create-token transaction, and is now managing AUNT's lifecycle autonomously."

**On-screen:** Switch to BscScan → https://bscscan.com/tx/0x80ff903ca947448ec50927b866067b67e5bdd69a667f9d0f1b3af8f0c74869d2
**Voice:**
> "Here's the on-chain launch transaction from the agent's wallet. Not a mockup."

---

### Segment 3 — Truth-boundary (0:35 – 0:55)

**On-screen:** Hit `/api/token/0x568bf…/badge` in a terminal or browser. Highlight `tier_source: certified`. Then hit `/api/token/0x<random>/badge`. Highlight `tier_source: radar_estimate`.
**Voice:**
> "FOUR-LIFE Certified is only issued when we have full on-chain data. Tokens visible only via public ranking get a separate Radar Estimate with a distinct version string. The embed widget, webhooks, and notifications all brand Radar Estimate transitions as 'Radar Estimate' — never as 'Certified'. The integrity line is enforced at every surface."

---

### Segment 4 — DGrid bounty (0:55 – 1:35)

**On-screen:** Open `/dgrid`. Scroll slowly so judges see: health rail, stats (share + cost + retries), chaos panel, fallback chain diagram, attestation card, leaderboard, consensus demo.
**Voice:**
> "DGrid is the agent's brain. Every LLM task routes through it — narrative, content, risk, consensus, vision, image. We built four capabilities single-provider agents can't replicate."

**On-screen:** Click **"probe DGrid now"**. Green toast with latency.
**Voice:**
> "One — live provability. Any judge can click this button and get a DGrid-served response on demand."

**On-screen:** Click **"kill DGrid"**. Health rail flips red, breaker opens.
**Voice:**
> "Two — live resilience. DGrid fails, the breaker trips, fallback chain engages. The agent keeps working."

**On-screen:** Click **"restore"**. Breaker back to closed.
**Voice:**
> "And back. DGrid recovers on the next call."

**On-screen:** Scroll to **Multi-model consensus**. Run it. Verdict card with 3 models.
**Voice:**
> "Three — consensus. Same prompt, three DGrid models vote in parallel. This is wired into every token's DEFEND phase — high-stakes decisions never trust a single model. Single-provider integrations literally cannot write this."

**On-screen:** Scroll to **On-chain attestation** card. Click `0xab323590…`.
**Voice:**
> "Four — cryptographic accountability. Every DGrid call is folded into a Merkle chain. The tip is published on BNB Chain. This transaction commits to 1,573 LLM calls. Anyone can download the call log, re-derive the chain, and verify the root."

---

### Segment 5 — MYX V2 (1:35 – 2:00)

**On-screen:** Open `/myx`.
**Voice:**
> "MYX V2 perp signals. Phase-aware — short when a token shows weakness, long on momentum, close on graduation. Every signal cryptographically committed in a chain separate from trades."

**On-screen:** Point at live signal feed (AUNT + KICAU signals scrolling). Click consensus button.
**Voice:**
> "DEFEND-phase signals fan across three DGrid models and vote — the DGrid × MYX synergy wired into real decisions. Signal attestation root 2 on-chain: `0xeda29cc6…`. MYX V2 is a permissioned-broker architecture, so execution is off by design until MYX onboards us — but the signal layer is fully shipped and attested."

---

### Segment 6 — Why this wins (2:00 – 2:20)

**On-screen:** Back to `/`.
**Voice:**
> "What we shipped: a production-deployed autonomous agent with a real Four.meme token under management, five on-chain attestation transactions anyone can verify, 367 passing tests, a strict Certified-vs-Radar-Estimate truth boundary enforced at every surface, and a cross-partner capability — DGrid consensus on MYX decisions — that can only exist because DGrid unifies every model behind one API."

> "FOUR-LIFE is the first Four.meme agent where 'autonomous' isn't marketing. It's cryptographically provable, and every claim traces back to a BscScan URL."

---

### Segment 7 — CTA (2:20 – 2:30)

**On-screen:** Homepage with URL visible in address bar.
**Voice:**
> "Live at four-life.gudman.xyz. Source on GitHub. Everything you just saw is running right now."

---

## Recording checklist

- [ ] Clear browser cache + hard-reload each tab (Ctrl+Shift+R) so the latest build renders
- [ ] Dry-run once before recording. Time it. If over 2:45, cut the chaos recovery wait
- [ ] Click everything in advance to warm DGrid / MYX caches so live API calls return fast
- [ ] Turn off system notifications
- [ ] Record at 1920×1080 minimum
- [ ] Upload unlisted to YouTube or Loom
- [ ] Add timestamps in description:
  - 0:00 Hook
  - 0:15 $AUNT — agent-launched Four.meme token
  - 0:35 Truth-boundary — Certified vs Radar Estimate
  - 0:55 DGrid: probe, chaos, consensus, on-chain attestation
  - 1:35 MYX V2: signals + signal attestation
  - 2:00 Why this wins
  - 2:20 CTA

## Post-record

1. Upload video, copy URL
2. Paste video URL into DoraHacks form Video field
3. Run live smoke test one last time: `python scripts/live_smoke_test.py`
4. Submit — **only after the form draft is reviewed with you**

## Emergency fallback (if something misbehaves mid-record)

- **Chaos doesn't trip visibly in 5 s:** stop recording, hard-reload, retry. Usually trips in ~3 s.
- **Consensus returns an error:** pick a different token or retry. Gemini occasionally truncates even with our 600-token budget (rare).
- **`/api/dgrid/probe` 503s:** DGrid is down or out of credit. Check balance. If low, top up $5 and retry.
- **Breaker stuck open:** POST `/api/dgrid/chaos {enabled: false}` with the admin bearer to reset, or click restore twice.

## One-liner to anchor the pitch

> "The first Four.meme agent where 'autonomous' isn't marketing — it's cryptographically provable."
