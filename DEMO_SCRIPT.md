# FOUR-LIFE Demo Video Script — 2 min 30 s

Target: 2:30. Upload as **unlisted YouTube** so DoraHacks judges can watch without spam.

**Recording setup**
- Screen: OBS or Loom at 1920×1080. Cursor highlight on.
- Audio: any decent USB mic. Quiet room. No music.
- Tabs pre-loaded (in order): `/` → `/dgrid` → BscScan attestation tx → `/myx` → BscScan $AUNT tx → `four.meme/token/0x568bf…`
- Keep BscScan in a second tab so you can click the attestation link live.

**Tone:** direct, confident, "here's what we shipped". No apologies, no hedging. Assume the judge is smart and skimming.

---

## Segment 1 — Hook (0:00 – 0:15)

**On-screen:** Homepage `/`.
**Voice:**
> "98.6% of Four.meme tokens die within 72 hours. That's because creation is solved — nothing manages them after launch. We built FOUR-LIFE: an autonomous agent that launches meme tokens and manages their full lifecycle, with every decision cryptographically anchored on BNB Chain."

---

## Segment 2 — The live token (0:15 – 0:35)

**On-screen:** Switch to Four.meme tab → https://four.meme/token/0x568bf737887053ffa8aa4e82d8859ca4a9a14444 (AUNT page).
**Voice:**
> "This is AUNT — AuntieCoin — a real Four.meme token launched end-to-end by the agent. The agent generated the concept via DGrid narrative analysis, generated the art via DALL-E through DGrid, signed the create-token transaction, and is now managing AUNT's lifecycle autonomously."

**On-screen:** Switch to BscScan → https://bscscan.com/tx/0x80ff903ca947448ec50927b866067b67e5bdd69a667f9d0f1b3af8f0c74869d2
**Voice:**
> "Here's the on-chain launch transaction from the agent's wallet. Not a mockup."

---

## Segment 3 — DGrid bounty (0:35 – 1:20)

**On-screen:** Open `/dgrid`. Scroll slowly so judges see: health rail, stats (94% share, cost, transient retries), chaos panel, fallback chain diagram, attestation card, cost breakdown, leaderboard, consensus demo, recent calls.
**Voice:**
> "DGrid is the agent's brain. 94% of all LLM traffic routes through DGrid. We built four capabilities single-provider agents can't replicate."

**On-screen:** Click **"probe DGrid now →"** button. Green toast appears with latency.
**Voice:**
> "One — live provability. Any judge can click this button and get a DGrid-served response on demand."

**On-screen:** Scroll to chaos panel. Click **"kill DGrid"**.
**Voice:**
> "Two — live resilience. I'm forcing DGrid to fail right now. Watch the breaker trip."

**On-screen:** Health rail flips red, breaker shows "open". Wait 5 seconds so viewers see it.

**On-screen:** Click **"restore"**. Breaker goes back to closed.
**Voice:**
> "And back. DGrid recovers on the next call. The fallback chain kept the agent alive the entire time."

**On-screen:** Scroll to **Multi-model consensus**. Type a prompt (or use default) and click **"run consensus →"**. Wait for the 3-model card.
**Voice:**
> "Three — consensus. Same prompt, three DGrid models vote in parallel. Majority wins. This is wired into every token's DEFEND phase — high-stakes decisions never trust a single model. Single-provider integrations literally cannot write this code."

**On-screen:** Scroll to **On-chain attestation** card. Click the bscscan link.
**Voice:**
> "Four — cryptographic accountability. Every DGrid call is folded into a Merkle chain. The tip is published on BNB Chain. Here's the transaction — the root sits in the tx data field. Anyone can download our call log, re-derive the chain locally, and verify the root matches. Zero server trust required."

---

## Segment 4 — MYX V2 (1:20 – 1:50)

**On-screen:** Open `/myx`.
**Voice:**
> "MYX V2 perps. The agent generates phase-aware hedge signals — short when a token shows weakness, long on momentum, close on graduation. Every signal is cryptographically committed in a separate Merkle chain from trades."

**On-screen:** Point at live signal feed (AUNT + KICAU signals scrolling).
**Voice:**
> "Real signals, firing every five minutes. The DEFEND-phase signals fan across three DGrid models and vote — the DGrid × MYX synergy we just showed, wired into real decisions."

**On-screen:** Scroll to **Live consensus demo** section. Click the AUNT button. Wait for verdict.
**Voice:**
> "Click — three models vote on whether to hedge AUNT right now. There's the verdict with per-model breakdown."

**On-screen:** Scroll to **Signal attestation** card. Click the bscscan link.
**Voice:**
> "And here's the signal attestation published on BNB Chain. The agent's thinking — not just its trades — committed on-chain."

---

## Segment 5 — Why this wins (1:50 – 2:20)

**On-screen:** Back to `/` homepage, hover over the feature cards.
**Voice:**
> "What we shipped: a production-deployed autonomous agent with a real Four.meme token under management, three on-chain attestation transactions anyone can verify, 365 passing tests, and a cross-partner capability — DGrid consensus on MYX decisions — that can only exist because DGrid unifies every model behind one API."

> "FOUR-LIFE is the first Four.meme agent where 'autonomous' isn't marketing. It's cryptographically provable, anchored on-chain, and every claim traces back to a BscScan URL."

---

## Segment 6 — CTA (2:20 – 2:30)

**On-screen:** Homepage with URL visible in address bar.
**Voice:**
> "Live at four-life.gudman.xyz. Code on GitHub. Everything you just saw is live right now."

---

## Recording checklist

- [ ] **Clear the browser cache** and hard-reload each tab before recording (Ctrl+Shift+R) so the latest build renders
- [ ] **Dry-run once** before recording. Time it. If over 2:45, cut the chaos recovery wait from 5s to 3s
- [ ] **Click everything in advance** to warm up DGrid / MYX caches so live API calls return fast
- [ ] **Turn off notifications** on your machine before recording
- [ ] **Record at 1920×1080** minimum — judges watch on laptops, text needs to be legible
- [ ] **Upload unlisted** to YouTube or as a Loom with public link
- [ ] **Add timestamps in description:**
  - 0:00 The problem
  - 0:15 $AUNT — agent launched this on Four.meme
  - 0:35 DGrid: probe, chaos, consensus, on-chain attestation
  - 1:20 MYX V2: consensus-backed signals + signal attestation
  - 1:50 Why this wins
  - 2:20 CTA

## Post-record

1. Paste video URL into `SUBMISSION.md` (replace `[PASTE_VIDEO_URL_BEFORE_SUBMITTING]`)
2. Paste video URL into DoraHacks form Video field
3. Run the live smoke test one last time: `python scripts/live_smoke_test.py`
4. Submit — **only after I've reviewed the form draft with you**.

## Emergency fallback (if something misbehaves mid-record)

- **Chaos doesn't trip visibly in 5s:** stop recording, hard-reload, try again. Usually trips in ~3s.
- **Consensus returns an error:** pick a different token or retry. Gemini occasionally truncates even with our 1500-token budget (rare).
- **`/api/dgrid/probe` 503s:** DGrid is down or out of credit. Check balance at dgrid.ai. If low, top up $5 and retry.
- **Breaker stuck open:** POST `/api/dgrid/chaos {enabled: false}` via curl to reset, or just click restore twice.

## One-liner to anchor the pitch

> "The first Four.meme agent where autonomous isn't marketing — it's cryptographically provable."
