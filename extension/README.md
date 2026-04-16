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

- `activeTab` — so the popup can open the Radar link.
- Host permissions for `https://four.meme/*` (where the content script runs) and `https://four-life.gudman.xyz/*` (where the API lives).

No tracking, no analytics, no third-party calls.

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
