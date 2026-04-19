# FOUR-LIFE — Demo Video Script (3:00, story-structured)

**Target length:** 3 minutes flat (±5s)
**Tool:** OBS Studio or Loom. 1920×1080, 30fps, mic on.
**Voice:** Calm, confident. Short sentences. Pause between sections. No filler words.
**Format:** Screen recording. No camera.

The video is organized as a **story with stakes**, not a feature tour. Every section advances a narrative:
*Four.meme has a problem → FOUR-LIFE grades it deterministically → the agent acts on-chain → anyone can verify and integrate.*

---

## Before you hit record

Open tabs left-to-right in this order (all must load cleanly first):

1. `https://four.meme` — the homepage, briefly shown as the cold open
2. `https://four-life.gudman.xyz/radar?min_confidence=high` — the Radar
3. `https://four-life.gudman.xyz/launch/0xd8c1c7b065ec8548093fe237157088b984dc4444` — a live token Certified page
4. `https://four-life.gudman.xyz/evidence` — the evidence panel
5. `https://four-life.gudman.xyz/docs` — OpenAPI
6. `https://four-life.gudman.xyz/dashboard` — the operator view
7. `https://bscscan.com/tx/0x62a1a43d9e782686b833ed44eee7ea95a9ee3370f2f372334dc7bbf85cc14762` — the ERC-8004 registration tx (Agent ID 20)
8. Terminal pre-loaded with (do **not** run yet):
   ```bash
   curl -s https://four-life.gudman.xyz/api/token/0xd8c1c7b065ec8548093fe237157088b984dc4444/badge | jq '.badge | {tier, label, why: [.why[] | {rule, value, threshold, passed}]}'
   ```

**Before recording:** close Slack/Discord/iMessage. Turn off OS notifications. Full-screen the browser.

---

## Section 1 — The 98.6% problem (0:00 → 0:20)

**On screen:** Fast pan across the Four.meme homepage. Don't linger.

> "Four dot meme launches thousands of tokens every week.
> Ninety-eight point six percent of them are dead within seventy-two hours.
> Creation is a solved problem. Everything after launch is not."

**Beat. Pause one second.**

---

## Section 2 — FOUR-LIFE Certified (0:20 → 0:50)

**On screen:** Switch to `/radar?min_confidence=high`. Let the live tokens render. Brief hover on the tier count bar at the top.

> "FOUR-LIFE Certified grades every Four dot meme token on-chain.
> Graduated. Graduation Watch. Healthy. At Risk. Observed.
> Computed from raw on-chain metrics. Zero LLM in the trust path."

**Action:** Scroll slowly past three or four rows so the tier pills and confidence chips read.

> "Graduation targets come from Four dot meme's own config — eighteen BNB, twelve thousand USD1. If they change, FOUR-LIFE updates within ten minutes."

---

## Section 3 — Deterministic proof (0:50 → 1:35)

**On screen:** Click the top row — opens `/launch/0xd8c1...` in the same tab (or switch to pre-loaded tab).

> "Every grade comes with a why-table. The exact rule that fired. The metric that triggered it. The threshold it cleared."

**Action:** Scroll slowly through the why-table, letting judges read one or two rows.

> "This is the part that matters for agents that need to *trust* a signal. Vibes don't grade trust. Math does."

**Action:** Switch to terminal. Run the pre-loaded curl command.

> "Anyone can hit the API and recompute. The response matches byte-for-byte. Auditable, reproducible, versioned."

---

## Section 4 — The agent acts (1:35 → 2:15)

**On screen:** Go to `/dashboard` (unlocked with API_SECRET), Overview tab.

> "FOUR-LIFE doesn't just grade. It *acts*."

**Action:** Show the status bar — `LIVE`, ERC-8004 Agent ID 20, active tokens count.

> "The agent runs a continuous lifecycle loop — track, monitor, defend, attest.
> Protection Mode fires signed HMAC webhooks on critical transitions.
> Graduations trigger on-chain reputation attestations through ERC-8004."

**Action:** Switch to the BscScan tab showing the Agent ID 20 registration tx.

> "The agent is registered on BNB Chain as Agent ID twenty. Every action it takes — every reputation attestation it submits — is verifiable, on-chain, permanent."

---

## Section 5 — Distribution surface (2:15 → 2:40)

**On screen:** Quick cuts — 3-4 seconds each — no narration, just label overlays.

- `/evidence` — *"Five live tokens, graded deterministically. Anyone can audit."*
- `/launch/<addr>` — *"One shareable page per token. Creators integrate with zero friction."*
- Embed docs page (`/embed`) — *"One script tag. Live badge anywhere."*
- `/docs` OpenAPI — *"46 endpoints. TypeScript + Python SDKs."*

> "FOUR-LIFE is infrastructure, not a dashboard. SDKs, webhooks, badges, extension — every Four dot meme project can integrate in under ten minutes."

---

## Section 6 — Close (2:40 → 3:00)

**On screen:** Return to the home page at `four-life.gudman.xyz`.

> "FOUR-LIFE Certified.
> The trust layer for every Four dot meme launch.
> Deterministic. On-chain. Auditable.
> Live now at four-life dot gudman dot xyz."

**Last frame:** Hold on the landing page for two full seconds. Fade.

---

## Recording checklist

- [ ] Test audio level — speak at regular volume, peak no higher than -6 dB
- [ ] Unlock `/dashboard` with API_SECRET in localStorage before recording
- [ ] Verify the Certified page at `/launch/0xd8c1...` actually loads with the badge + why-table (agent needs to have processed at least one tick on that token)
- [ ] Verify `/evidence` shows at least 3 cases with grades (not "loading…")
- [ ] Do a timed dry run before the real take. If you're under 2:45 or over 3:10, adjust narration speed.

## Post-recording

- [ ] Export as MP4, 1080p, H.264. File size target: < 80 MB for YouTube upload.
- [ ] Upload **unlisted** to YouTube (not public — the hackathon submission is the first reveal).
- [ ] Paste the YouTube URL into `SUBMISSION.md` → Video URL field, and into the DoraHacks form.
- [ ] Save the `.mp4` to Google Drive as a backup (DoraHacks URLs occasionally break).
