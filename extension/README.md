# FOUR-LIFE Certified — Browser Extension

Injects the **FOUR-LIFE Certified** trust badge and deterministic risk snapshot onto every `four.meme/token/{address}` page. Anyone browsing Four.meme sees the grade instantly, without leaving the page.

The badge is fully auditable: every tier assignment comes with the exact rule trace (metric, value, threshold, pass/fail) returned by the FOUR-LIFE API.

---

## What it does

1. Detects `https://four.meme/token/0x…` pages and extracts the token address.
2. Calls:
   - `GET https://four-life.gudman.xyz/api/token/{address}/badge`
   - `GET https://four-life.gudman.xyz/api/token/{address}/risk-snapshot`
3. Renders a pill in the top-right of the page showing the tier (green / yellow / red).
4. Clicking the pill opens a side panel with:
   - Tier label + description
   - Full rule trace (`why[]`)
   - Risk evidence list
   - Link to the full operator checklist at `/radar/{address}`
5. Polls every 60s so the badge updates as metrics change.

---

## Load in Chrome / Edge

1. Open `chrome://extensions` (or `edge://extensions`).
2. Toggle **Developer mode** (top-right).
3. Click **Load unpacked**.
4. Select this `extension/` folder.
5. Visit any token page, e.g. `https://four.meme/token/0x…`.

The badge pill appears within ~1–2 seconds. Click it to open the detail panel.

---

## Permissions

The manifest requests exactly four permissions and four host permissions. Every one is load-bearing — nothing is requested speculatively.

| Permission | Why |
|---|---|
| `activeTab` | Lets the popup route clicks to the user's current tab. |
| `storage` | Watchlist persistence via `chrome.storage.sync` (syncs across devices). |
| `alarms` | Wakes the service worker every 3 min to poll watched tokens for tier changes. |
| `notifications` | Fires Chrome notifications when a watched token's tier transitions. |

Host permissions:

- `https://four.meme/*` — content script injects the trust badge on token pages.
- `https://bscscan.com/*` — same content script on `/token/0x...` pages.
- `https://pancakeswap.finance/*` — same content script on `/info/tokens/...` + `/swap?outputCurrency=...`.
- `https://four-life.gudman.xyz/*` — public API (badge, risk-snapshot, attestation).

No tracking, no analytics, no third-party calls. Watchlist stays on-device; `chrome.storage.sync` means it rides your own Google account's encrypted sync — we never see it.

---

## Files

```
extension/
├── manifest.json          # MV3 manifest
├── background.js          # Minimal service worker
├── content/
│   ├── inject.js          # Content script — detects page, fetches badge, renders pill
│   ├── overlay.js         # Side-panel rendering
│   └── styles.css         # Placeholder (real styles live in Shadow DOM)
├── popup/
│   ├── popup.html         # Extension icon popup
│   ├── popup.css
│   └── popup.js
├── icons/
│   ├── icon-16.png
│   ├── icon-48.png
│   └── icon-128.png
└── README.md
```

All visible UI renders inside a Shadow DOM attached to a single host element, so Four.meme's own CSS cannot leak in or out.
