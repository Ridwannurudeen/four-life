# FOUR-LIFE — 90-second Demo Script

**Deadline:** Apr 22 · 23:59 UTC · Four.meme AI Sprint

**One-sentence pitch:** FOUR-LIFE is the autonomous lifecycle agent for Four.meme tokens — grades every token with pure on-chain rules (zero LLM in the trust path) and Merkle-commits every operational LLM decision to BNB Chain.

---

## Before recording

**Open these tabs in this exact order:**
1. `https://four-life.gudman.xyz/` — the landing page
2. `https://four-life.gudman.xyz/radar` — the live radar
3. `https://four-life.gudman.xyz/proof` — the outcome ledger
4. `https://four.meme/en/token/0x568bf737887053ffa8aa4e82d8859ca4a9a14444` — $AUNT token page
5. The FOUR-LIFE Chrome extension — reloaded at v1.5.3, pinned to the toolbar

**Test token (reference throughout):** `$AUNT` at `0x568bf737887053ffa8aa4e82d8859ca4a9a14444`

**Cursor tip:** use a highlighter or the browser zoom (Ctrl+=) for big click targets.

---

## BEAT 1 — 0:00 → 0:20 — The Hook

**Tab:** Landing page (`four-life.gudman.xyz`)

**Voiceover (spoken):**
> "Four.meme launches fifty tokens a day. Only one point three four percent ever graduate. The other ninety-eight percent die silently inside seventy-two hours — from whale rugs, stalled curves, coordinated sells. FOUR-LIFE is Phase 4: the autonomous lifecycle agent that keeps them alive."

**On-screen actions:**
- Point at the eyebrow pill: **`LIVE ON BNB CHAIN · 88 GRADED · 8 CERTIFIED · AGENT ID 20`**
- Scroll past the 1.34% headline
- Briefly reveal the **Architecture diagram** section: `Token → Agent loop → Deterministic Grade + Attested LLM → 5 consumer surfaces`

**Key phrase to hit aloud:** "Phase 4."

---

## BEAT 2 — 0:20 → 0:45 — The Grade

**Tab:** Radar (`four-life.gudman.xyz/radar`)

**Voiceover:**
> "Every Four.meme token shows up here, graded in real time. Eight live-monitored tokens are Certified — that means full on-chain rule trace, no LLM in the trust path. Fifty-two are Radar Estimates from public ranking — labelled differently, never confused."

**On-screen actions:**
- Point at the **tier breakdown strip**: `8 At Risk · 52 Observed`
- Click the first Certified row (`AUNT` or `DOUJIAO`)
- Drawer opens → point at the **rule trace cards** (whale_extreme, sell_pressure, curve_stalled, whale_cluster)
- Hover the **ℹ icon** on any rule → plain-english tooltip appears

**Key phrase:** "Deterministic rule trace — anyone can reproduce the grade from raw on-chain data."

---

## BEAT 3 — 0:45 → 1:15 — The Proof

**Tab:** Proof (`four-life.gudman.xyz/proof`)

**Voiceover:**
> "Here's the agent's record. Thirty-two launches deployed, five graduated — that's fifteen point six percent, more than eleven times the platform average. Every operational LLM call the agent makes — narrative picks, hedge decisions — is hash-chained, and published roots are anchored on BNB Chain. The latest published roots cover one thousand five hundred seventy-three DGrid calls and five hundred eighteen MYX decisions. Six transactions, all verifiable on BscScan."

**On-screen actions:**
- Point at **Section 0 "The ledger"** — the 5 big stat numbers light up live
- Click any of the 4 link cards (agent wallet / ERC-8004 / DGrid root / MYX root) → BscScan opens → close the tab
- Scroll to **Section 5 "Graduated tokens"** — 4 real tokens that reached 100% curve

**Key phrase:** "Provable on-chain. Not a promise — a transaction."

---

## BEAT 4 — 1:15 → 1:30 — The Firewall

**Tab:** Four.meme AUNT page (`four.meme/en/token/0x568bf...4444`)

**Voiceover:**
> "And it's not just a dashboard. Watch this."

**On-screen actions:**
1. Point at the **red pulsing pill** in the top-right → "FOUR-LIFE · At Risk"
2. Click the pill → deep panel slides in from the right
3. Briefly pan down the panel: **health ring · rule trace · contract safety checklist · creator reputation · snapshot sparkline · on-chain attestation strip**
4. Click the **Swap ↗** button in the footer → **block modal appears**
5. Point at the quoted evidence lines + the **Cancel / Override anyway** buttons

**Voiceover close:**
> "Grade, shield, attest. FOUR-LIFE — Phase 4 for every Four.meme launch. Try it: four-life dot gudman dot xyz."

---

## Fallback demo moments (if time allows)

- **Right-click context menu:** select any 0x address anywhere, right-click → "Grade with FOUR-LIFE" → new tab opens with the full rule trace. Proves the extension works beyond the 4 injected sites.
- **Keyboard shortcuts:** press `F` to expand the drawer, `P` to pop into a full browser tab, `W` to watchlist-subscribe for Chrome notifications.
- **Popup dashboard:** click the toolbar icon → live agent state, top radar rows with curve-progress bars, last 5 agent actions.

---

## Do-not-say list (submission-eve honesty)

- Do NOT say "fully autonomous MYX execution" — execution is signal-only; the broker gate is contract-blocked upstream. Say "decision-attestation depth" instead.
- Do NOT call a radar_estimate badge "Certified" — the extension, modal, and notifications all discriminate. Mirror that on camera.
- Do NOT claim the 8 tracked tokens have graduated — they're at_risk/partial_history. The 5 graduations come from historical launches, shown on /proof.

---

## Recording checklist

- [ ] All 5 tabs open in order
- [ ] Chrome at 125% zoom (readable on compressed video)
- [ ] Extension reloaded → confirm `v1.5.3` via devtools `document.getElementById('four-life-certified-host').dataset.flVersion`
- [ ] Screen-recorder set to 1080p 30fps minimum
- [ ] Microphone test — one take, 90 seconds max
- [ ] After recording: set `NEXT_PUBLIC_DEMO_VIDEO_URL=<your-youtube-embed-url>` in the VPS `.env`, `npm run build`, the DemoVideo slot on the landing page will embed it automatically

---

*FOUR-LIFE · Four.meme AI Sprint · BNB Chain · ERC-8004 Agent #20*
