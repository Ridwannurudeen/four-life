# FOUR-LIFE — Demo Video Script

**Target length:** 2 minutes 30 seconds
**Tool:** OBS Studio, Loom, or QuickTime (macOS). 1920×1080, 30fps, mic audio on.
**Format:** Screen recording. No camera.
**Voice:** Calm, confident. No filler ("um", "so"). Short sentences. Pause between sections.

---

## Before you hit record

**Open these tabs, in this order, left-to-right:**

1. `https://four-life.gudman.xyz/radar`
2. `https://four-life.gudman.xyz/creators`
3. `https://four-life.gudman.xyz/webhooks`
4. `https://four-life.gudman.xyz/docs`
5. A terminal window — pre-load these three commands (don't run them yet):
   ```
   curl -sS https://four-life.gudman.xyz/api/token/0x72b0a042e19871c046c1bd31e5b5ad3770c94444/badge | jq
   curl -sS https://four-life.gudman.xyz/api/creators/leaderboard | jq
   curl -X PUT -H "Content-Type: application/json" \
     -d '{"max_whale_concentration":25,"critical_contract_risk":50}' \
     https://four-life.gudman.xyz/api/protection/0x72b0a042e19871c046c1bd31e5b5ad3770c94444 | jq
   ```
6. A code editor with `agent/badge.py` open (just the top 30 lines with the rule list).

**Before recording:** close Slack/Discord/iMessage. Turn off notifications. Full-screen the browser.

---

## Section 1 — The Problem (0:00 → 0:15)

**On screen:** Scroll the Four.meme homepage briefly (https://four.meme/ — or a screenshot).

**Narration:**

> "Four dot meme launches thousands of tokens a week. Ninety-eight point six percent die within 72 hours. There's no way to tell, at a glance, which ones are going to make it. That's the problem FOUR-LIFE solves."

**Beat. Pause 1 second.**

---

## Section 2 — The Radar (0:15 → 0:55)

**On screen:** Switch to `/radar`. Let the page load fully (you'll see live tokens with tier pills).

**Narration:**

> "FOUR-LIFE Certified is a deterministic trust tier for every Four dot meme token, computed from raw on-chain metrics. No LLM in the trust path."

**Action:** Hover briefly over the tier-count header cards at the top (Graduated / Watch / Healthy / At Risk / Observed).

> "Tokens get graded continuously. You can filter by quote asset, confidence, and sort by graduation probability."

**Action:** Click any one token row to open the detail drawer.

**Narration:**

> "Every badge comes with a why-table — the exact rule that fired, the metric that produced it, the threshold. Anyone can recompute the grade from raw data. This is the auditable trust layer."

**Action:** Scroll the drawer down to reveal the **Trust Timeline** section. Point (hover cursor) at the step chart.

> "Every re-evaluation is persisted. This chart shows how trust moved over time — healthy to at-risk to graduated — with the exact reason for each transition logged."

**Action:** Close the drawer.

---

## Section 3 — Creator Ledger (0:55 → 1:15)

**On screen:** Switch to `/creators`.

**Narration:**

> "Trust at the token level is one half. The other half is the creator. FOUR-LIFE tracks every wallet that's ever launched, aggregates their survival rate, and ranks them — proven, emerging, new creator, unproven — using the same deterministic tier thresholds."

**Action:** Click any row to expand the evidence. Show the per-launch cards.

> "Click any creator to see every launch they've ever shipped with FOUR-LIFE-tracked metrics. The ledger is auditable end-to-end."

---

## Section 4 — Webhooks + Protection Mode (1:15 → 1:55)

**On screen:** Switch to `/webhooks`.

**Narration:**

> "Every tier transition fires a signed HMAC webhook. Subscribers verify the signature and react — halt trading, post an alert, trigger a hedge. The retry semantics, the verification code in Node and Python, are right here on the page."

**Action:** Scroll once to show the Python verification snippet.

**Beat.** Switch to the terminal.

**Narration:**

> "And on top of that — Protection Mode. You declare defensive thresholds per token. One PUT request."

**Action:** Run the third curl command (`PUT /api/protection/...`). Wait for response.

> "When a token's verdict hits critical, FOUR-LIFE halts content posts, fires a webhook, and recommends a short hedge. Fully deterministic. Fully auditable."

---

## Section 5 — SDK + Close (1:55 → 2:30)

**On screen:** Switch to editor. Paste this block fresh (pre-load in clipboard):

```python
from four_life import FourLife

fl = FourLife()
badge = fl.get_badge("0x72b0a042e19871c046c1bd31e5b5ad3770c94444")
print(badge["badge"]["tier"])
```

**Narration:**

> "Three lines of Python. Or three lines of TypeScript. Live against the real API."

**Action:** Switch back to `/radar` in the browser, let the auto-refresh tick once (you'll see the "Updated Xs ago" counter move).

**Narration (slightly slower, stronger):**

> "FOUR-LIFE is the missing post-launch layer for Four dot meme. The radar is live. The API is live. The webhooks are live. The SDKs are live. This is the trust infrastructure every agent that touches Four dot meme should be using."

**Beat. Pause 1 second.**

> "FOUR-LIFE. Built on BNB Chain. Built on DGrid. Thank you."

**End. Stop recording.**

---

## Recording checklist

- [ ] All 4 browser tabs pre-loaded and warmed up (hit each page once so they're cached)
- [ ] Terminal commands pre-typed, not yet run
- [ ] Mic tested at ~-12 dB peak
- [ ] Screen resolution = 1920×1080 (fit for DoraHacks)
- [ ] Notifications OFF (do-not-disturb mode)
- [ ] Second monitor hidden (or recording region set to primary only)
- [ ] Clock showing in top corner hidden (or in a non-personal state)
- [ ] Cursor is visible (OBS: Sources → Display Capture → "Capture Cursor" ON)

## Post-recording

- Trim dead air at start and end (aim for 2:30 max, 2:15 sweet spot)
- Normalize audio to -16 LUFS (Audacity "Loudness Normalization")
- Export as `.mp4` H.264, ~8 Mbps
- Filename: `four-life-demo.mp4`
- Upload to YouTube **unlisted** (not public — DoraHacks requires a link, not public indexing)
- Or upload to Loom — faster to embed

## If you fumble a section

Don't restart the whole video. Pause recording, re-stage, resume. OBS supports "Pause Recording" cleanly. In post, cut at the pause points.
