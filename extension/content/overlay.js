// FOUR-LIFE Certified — overlay panel.
// Rendered inside the same Shadow DOM the pill uses. Opens on pill click.

(() => {
  const SEV_COLORS = {
    critical: "#ef4444",
    high: "#f97316",
    medium: "#eab308",
    low: "#22c55e",
    info: "#38bdf8",
  };

  const OVERLAY_CSS = `
    .fl-scrim {
      position: fixed; inset: 0;
      background: rgba(0,0,0,0.55);
      z-index: 2147483646;
      display: flex;
      align-items: flex-start;
      justify-content: flex-end;
      padding: 0;
      backdrop-filter: blur(4px);
      animation: fl-fade 140ms ease-out;
    }
    @keyframes fl-fade { from { opacity: 0; } to { opacity: 1; } }
    @keyframes fl-slide { from { transform: translateX(24px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
    .fl-panel {
      width: 460px;
      max-width: 96vw;
      height: 100vh;
      overflow-y: auto;
      background: #0b0b0e;
      color: #f5f5f7;
      border-left: 1px solid rgba(255,255,255,0.08);
      padding: 22px 22px 40px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      font-size: 13px;
      line-height: 1.5;
      animation: fl-slide 180ms ease-out;
      transition: width 220ms ease-out, max-width 220ms ease-out;
    }
    /* Maximized drawer — toggled by the ⛶ button. Caps at 1100px on
       wide monitors so the card columns don't stretch into awkward
       single-line rows; clamps to 95vw on anything narrower. */
    .fl-panel.fl-maximized {
      width: min(1100px, 95vw);
      max-width: 95vw;
    }

    /* Resize bar — persistent vertical handle on the panel's left edge.
       Universal sidebar convention (Rabby / Phantom / VS Code). Clicking
       it toggles the panel between drawer and maximized. Hover shows a
       chevron arrow that points the direction it'll grow. This sits on
       every panel open regardless of whether the icon button renders. */
    .fl-resize-bar {
      position: absolute;
      left: 0;
      top: 0;
      bottom: 0;
      width: 16px;
      cursor: ew-resize;
      display: flex;
      align-items: center;
      justify-content: center;
      background: transparent;
      border: none;
      padding: 0;
      z-index: 3;
      transition: background 0.15s;
    }
    .fl-resize-bar::before {
      content: "";
      position: absolute;
      left: 7px;
      top: 35%;
      bottom: 35%;
      width: 2px;
      border-radius: 1px;
      background: rgba(255,255,255,0.25);
      transition: background 0.15s, box-shadow 0.15s;
    }
    .fl-resize-bar:hover { background: rgba(255,255,255,0.04); }
    .fl-resize-bar:hover::before {
      background: #00d4ff;
      box-shadow: 0 0 10px rgba(0,212,255,0.5);
    }
    .fl-resize-bar .fl-resize-arrow {
      position: relative;
      color: rgba(255,255,255,0.55);
      font-size: 14px;
      line-height: 1;
      opacity: 0;
      transition: opacity 0.15s;
      pointer-events: none;
    }
    .fl-resize-bar:hover .fl-resize-arrow { opacity: 1; color: #00d4ff; }
    /* Flip the arrow glyph based on panel state so the user sees the
       direction the panel will grow. Drawer → ← (grow leftward); max → →. */
    .fl-panel.fl-maximized .fl-resize-arrow::before { content: "→"; }
    .fl-panel:not(.fl-maximized) .fl-resize-arrow::before { content: "←"; }
    .fl-panel { position: relative; }
    /* Expand/collapse toggle — matches the Watch button's shape so it
       reads as a peer, not a hidden icon. Visible on every panel open. */
    .fl-max {
      background: transparent;
      border: 1px solid rgba(255,255,255,0.1);
      color: rgba(255,255,255,0.7);
      border-radius: 8px;
      height: 30px;
      padding: 0 10px;
      cursor: pointer;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.02em;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-family: inherit;
      transition: color 0.12s, border-color 0.12s, background 0.12s;
    }
    .fl-max:hover { color: #fff; border-color: rgba(255,255,255,0.25); }
    .fl-max[aria-pressed="true"] {
      color: #00d4ff;
      border-color: rgba(0, 212, 255, 0.4);
      background: rgba(0, 212, 255, 0.08);
    }
    .fl-max svg { display: block; flex-shrink: 0; }
    /* Swap glyphs based on panel state: expand icon when restored,
       collapse icon when maximized. Label swaps via data-* so both
       are always sized even during transition. */
    .fl-max[aria-pressed="false"] .fl-max-collapse,
    .fl-max[aria-pressed="true"]  .fl-max-expand { display: none; }
    .fl-panel h2 {
      margin: 0 0 4px;
      font-size: 18px;
      font-weight: 700;
      letter-spacing: 0.2px;
    }
    .fl-panel h3 {
      margin: 22px 0 10px;
      font-size: 10.5px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: rgba(255,255,255,0.45);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .fl-panel h3::before {
      content: "";
      width: 3px; height: 12px;
      background: linear-gradient(180deg, #00d4ff, #6cff32);
      border-radius: 2px;
    }
    .fl-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 14px;
    }
    .fl-close {
      background: transparent;
      border: 1px solid rgba(255,255,255,0.1);
      color: rgba(255,255,255,0.7);
      border-radius: 8px;
      width: 30px; height: 30px;
      cursor: pointer;
      font-size: 16px;
      line-height: 1;
    }
    .fl-close:hover { color: #fff; border-color: rgba(255,255,255,0.25); }

    /* Watch toggle — star button in the header that subscribes the token
       for Chrome notifications on tier transitions. Active state is gold. */
    .fl-watch {
      background: transparent;
      border: 1px solid rgba(255,255,255,0.1);
      color: rgba(255,255,255,0.55);
      border-radius: 8px;
      height: 30px;
      padding: 0 10px;
      cursor: pointer;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.02em;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: color 0.12s, border-color 0.12s, background 0.12s;
    }
    .fl-watch:hover { color: #fff; border-color: rgba(255,255,255,0.25); }
    .fl-watch[aria-pressed="true"] {
      color: #ffd641;
      border-color: rgba(255, 214, 65, 0.45);
      background: rgba(255, 214, 65, 0.08);
    }
    .fl-watch-toast {
      position: absolute;
      top: 52px;
      right: 22px;
      padding: 7px 12px;
      background: rgba(10,10,14,0.96);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 8px;
      color: #fff;
      font-size: 11.5px;
      font-weight: 500;
      opacity: 0;
      transform: translateY(-4px);
      transition: opacity 0.15s ease-out, transform 0.15s ease-out;
      pointer-events: none;
    }
    .fl-watch-toast[data-visible="true"] {
      opacity: 1;
      transform: translateY(0);
    }
    .fl-tier-chip {
      display: inline-flex; align-items: center; gap: 8px;
      padding: 6px 12px;
      border-radius: 999px;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.08);
      font-weight: 600;
      text-transform: capitalize;
      font-size: 12px;
    }
    .fl-tier-dot { width: 8px; height: 8px; border-radius: 50%; }
    .fl-desc {
      color: rgba(255,255,255,0.75);
      margin: 10px 0 0;
    }
    /* Heuristic-only banner — only renders when tier_source==="radar_estimate"
       so visitors never see "Certified" visuals over a public-ranking estimate. */
    .fl-source-note {
      margin: 10px 0 0;
      padding: 8px 10px;
      border-radius: 8px;
      background: rgba(255, 214, 65, 0.12);
      border: 1px solid rgba(255, 214, 65, 0.4);
      color: #ffd641;
      font-size: 11px;
      line-height: 1.4;
    }
    .fl-addr {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 10.5px;
      color: rgba(255,255,255,0.4);
      margin-top: 12px;
      padding: 6px 10px;
      background: rgba(255,255,255,0.025);
      border: 1px solid rgba(255,255,255,0.06);
      border-radius: 6px;
      word-break: break-all;
      letter-spacing: 0.02em;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .fl-addr-val { flex: 1; min-width: 0; word-break: break-all; }
    .fl-copy {
      background: transparent;
      border: 1px solid rgba(255,255,255,0.1);
      color: rgba(255,255,255,0.6);
      border-radius: 6px;
      padding: 3px 8px;
      font-size: 10px;
      font-weight: 600;
      cursor: pointer;
      font-family: inherit;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      flex-shrink: 0;
      transition: color 0.12s, border-color 0.12s, background 0.12s;
    }
    .fl-copy:hover { color: #fff; border-color: rgba(255,255,255,0.25); }
    .fl-copy[data-copied="true"] {
      color: #6cff32;
      border-color: rgba(108,255,50,0.4);
      background: rgba(108,255,50,0.08);
    }
    table.fl-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 6px;
      font-size: 12px;
    }
    table.fl-table th, table.fl-table td {
      text-align: left;
      padding: 8px 10px;
      border-bottom: 1px solid rgba(255,255,255,0.06);
      vertical-align: top;
    }
    table.fl-table th {
      color: rgba(255,255,255,0.55);
      font-weight: 500;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.6px;
    }
    table.fl-table td code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 11px;
      color: rgba(255,255,255,0.85);
    }
    .fl-pass { color: #22c55e; font-weight: 600; }
    .fl-fail { color: #ef4444; font-weight: 600; }
    .fl-evidence-item {
      padding: 10px 12px;
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 10px;
      margin-bottom: 8px;
      background: rgba(255,255,255,0.02);
    }
    .fl-evidence-head {
      display: flex; justify-content: space-between; gap: 12px;
      margin-bottom: 4px;
      font-weight: 600;
    }
    .fl-sev {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      padding: 2px 8px;
      border-radius: 999px;
      background: rgba(255,255,255,0.06);
    }
    .fl-evidence-body { color: rgba(255,255,255,0.75); font-size: 12px; }
    .fl-empty {
      color: rgba(255,255,255,0.5);
      font-style: italic;
      padding: 10px 0;
    }
    .fl-footer {
      position: sticky;
      bottom: 0;
      margin: 24px -22px -40px;
      padding: 14px 22px 18px;
      border-top: 1px solid rgba(255,255,255,0.08);
      background: linear-gradient(180deg, rgba(11,11,14,0.85), #0b0b0e);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      z-index: 2;
    }
    .fl-link {
      color: #fff;
      background: linear-gradient(135deg, #f59e0b, #ef4444);
      padding: 8px 14px;
      border-radius: 8px;
      text-decoration: none;
      font-weight: 600;
      font-size: 12px;
    }
    .fl-link:hover { filter: brightness(1.1); }
    .fl-watermark {
      color: rgba(255,255,255,0.35);
      font-size: 11px;
    }

    /* Agent-context strip — shows WHO graded this token + links to
       the live on-chain attestation evidence. Proves the verdict isn't
       a black box: the grading agent has an ERC-8004 identity and its
       decisions are committed to public Merkle roots on BNB Chain. */
    .fl-agent-ctx {
      margin-top: 16px;
      padding: 12px 14px;
      border: 1px solid rgba(0, 212, 255, 0.18);
      background: linear-gradient(135deg, rgba(0,212,255,0.04), rgba(108,255,50,0.02));
      border-radius: 10px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      font-size: 11px;
    }
    .fl-agent-ctx .fl-k {
      font-size: 9px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: rgba(255,255,255,0.5);
      font-weight: 600;
      margin-bottom: 3px;
    }
    .fl-agent-ctx .fl-v { font-weight: 600; }
    .fl-agent-ctx a {
      color: #00d4ff;
      font-family: ui-monospace, Menlo, Consolas, monospace;
      text-decoration: none;
      font-size: 10.5px;
    }
    .fl-agent-ctx a:hover { text-decoration: underline; }

    /* Action buttons — the footer gets 3 actions (share, open-on-FOUR-LIFE,
       view attestation on BscScan) instead of the old single CTA. Each is
       a real user verb, not decoration. */
    .fl-actions {
      display: flex;
      gap: 8px;
      margin-top: 4px;
      flex-wrap: wrap;
    }
    .fl-action {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 12px;
      border-radius: 8px;
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08);
      color: #fff;
      font-size: 11.5px;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
      transition: background 0.12s, border-color 0.12s;
    }
    .fl-action:hover { background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.18); }
    .fl-action.primary {
      background: linear-gradient(135deg, #00d4ff, #6cff32);
      color: #0b0b0e;
      border-color: transparent;
    }
    .fl-action.primary:hover { filter: brightness(1.08); background: linear-gradient(135deg, #00d4ff, #6cff32); }

    /* Deployer reputation card — shows creator wallet + aggregated track record
       from /api/creator/{wallet}/survival-score. Unknown devs surface as
       "Unknown dev" explicitly so we never imply a non-existent history. */
    .fl-creator {
      margin-top: 16px;
      padding: 12px 14px;
      border: 1px solid rgba(255,255,255,0.08);
      background: rgba(255,255,255,0.02);
      border-radius: 10px;
    }
    .fl-creator-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }
    .fl-creator-head .fl-k {
      font-size: 9px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: rgba(255,255,255,0.5);
      font-weight: 600;
      margin-bottom: 3px;
    }
    .fl-creator-addr {
      font-family: ui-monospace, Menlo, Consolas, monospace;
      font-size: 11.5px;
      color: #00d4ff;
      text-decoration: none;
      font-weight: 600;
    }
    .fl-creator-addr:hover { text-decoration: underline; }
    .fl-creator-tier {
      text-transform: capitalize;
      font-size: 10.5px;
      font-weight: 700;
      letter-spacing: 0.04em;
      padding: 4px 9px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.2);
      background: rgba(255,255,255,0.03);
      white-space: nowrap;
      flex-shrink: 0;
    }
    .fl-creator-stats {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      margin-bottom: 10px;
    }
    .fl-creator-stat {
      text-align: center;
      padding: 8px 6px;
      background: rgba(255,255,255,0.03);
      border-radius: 8px;
    }
    .fl-creator-stat-v {
      font-size: 16px;
      font-weight: 700;
      color: #fff;
      line-height: 1.1;
    }
    .fl-creator-stat-k {
      font-size: 9.5px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: rgba(255,255,255,0.5);
      margin-top: 3px;
    }
    .fl-creator-note {
      font-size: 11.5px;
      color: rgba(255,255,255,0.55);
      font-style: italic;
    }
    .fl-creator-link {
      display: inline-block;
      margin-top: 4px;
      color: #00d4ff;
      font-size: 11px;
      font-weight: 600;
      text-decoration: none;
    }
    .fl-creator-link:hover { text-decoration: underline; }

    /* ── Hero verdict block ─────────────────────────────────────────────
       Replaces the old small tier-chip + heading pair. Big tier-color
       radial glow backdrop, massive tier label, then a row of stat chips
       for the headline metrics that matter to a trader seeing this once. */
    .fl-hero {
      position: relative;
      margin: 2px 0 14px;
      padding: 20px 18px 18px;
      border-radius: 14px;
      border: 1px solid rgba(255,255,255,0.08);
      background: #0f0f14;
      overflow: hidden;
      isolation: isolate;
    }
    .fl-hero::before {
      content: "";
      position: absolute;
      top: -40%; left: -20%;
      width: 80%; height: 140%;
      background: radial-gradient(ellipse at center, var(--fl-tier-color, rgba(255,255,255,0.08)), transparent 62%);
      opacity: 0.35;
      filter: blur(14px);
      z-index: -1;
      pointer-events: none;
    }
    .fl-hero-kicker {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      color: rgba(255,255,255,0.55);
      font-weight: 700;
      margin-bottom: 10px;
    }
    .fl-hero-kicker-dot {
      width: 7px; height: 7px; border-radius: 50%;
      background: var(--fl-tier-color, #fff);
      box-shadow: 0 0 10px var(--fl-tier-color, rgba(255,255,255,0.3));
    }
    .fl-hero-label {
      font-size: 30px;
      font-weight: 800;
      letter-spacing: -0.02em;
      line-height: 1.05;
      margin: 0;
      color: #fff;
      text-transform: capitalize;
    }
    .fl-hero-sub {
      margin: 4px 0 14px;
      font-size: 12px;
      color: rgba(255,255,255,0.6);
      line-height: 1.5;
    }
    .fl-hero-chips {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      margin-top: 6px;
    }
    /* Certified mode gets a dedicated ring widget beside the chip stack.
       Grid: ring | 2 stacked chips. Radar mode keeps 3 equal chips. */
    .fl-hero.fl-hero-certified .fl-hero-chips {
      grid-template-columns: 116px 1fr;
      gap: 10px;
      align-items: stretch;
    }
    .fl-hero.fl-hero-certified .fl-hero-chip-stack {
      display: grid;
      grid-template-rows: 1fr 1fr;
      gap: 8px;
    }
    .fl-health-ring {
      position: relative;
      padding: 8px;
      border-radius: 10px;
      background: rgba(255,255,255,0.025);
      border: 1px solid rgba(255,255,255,0.06);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .fl-health-ring svg { display: block; width: 100px; height: 100px; transform: rotate(-90deg); }
    .fl-health-ring .fl-ring-bg {
      fill: none;
      stroke: rgba(255,255,255,0.08);
      stroke-width: 8;
    }
    .fl-health-ring .fl-ring-fg {
      fill: none;
      stroke: var(--fl-tier-color, #00d4ff);
      stroke-width: 8;
      stroke-linecap: round;
      stroke-dasharray: var(--fl-ring-len, 0) 999;
      filter: drop-shadow(0 0 6px color-mix(in srgb, var(--fl-tier-color, #00d4ff) 40%, transparent));
      transition: stroke-dasharray 420ms cubic-bezier(0.2, 0.6, 0.2, 1);
    }
    .fl-health-ring .fl-ring-center {
      position: absolute;
      inset: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
    }
    .fl-health-ring .fl-ring-v {
      font-size: 22px;
      font-weight: 800;
      color: #fff;
      line-height: 1;
      font-variant-numeric: tabular-nums;
      letter-spacing: -0.02em;
    }
    .fl-health-ring .fl-ring-k {
      font-size: 8.5px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: rgba(255,255,255,0.5);
      margin-top: 4px;
      font-weight: 600;
    }

    /* Contract-safety checklist — renders the /contract-risk response
       as a scannable list of ✓ (safe) / ✗ (risky) / ? (unknown) rows. */
    .fl-contract {
      margin-top: 16px;
      padding: 12px 14px;
      border: 1px solid rgba(255,255,255,0.08);
      background: rgba(255,255,255,0.02);
      border-radius: 10px;
    }
    .fl-contract-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
      font-size: 9.5px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: rgba(255,255,255,0.5);
      font-weight: 700;
    }
    .fl-contract-score {
      font-size: 10.5px;
      font-weight: 700;
      color: var(--fl-contract-color, #6cff32);
      letter-spacing: 0;
      text-transform: none;
    }
    .fl-contract-list {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 4px 14px;
    }
    .fl-contract-row {
      display: flex;
      align-items: center;
      gap: 7px;
      font-size: 11.5px;
      color: rgba(255,255,255,0.85);
      line-height: 1.35;
      padding: 3px 0;
    }
    .fl-contract-ico {
      width: 14px; height: 14px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .fl-contract-row[data-st="ok"] .fl-contract-ico { color: #6cff32; }
    .fl-contract-row[data-st="bad"] .fl-contract-ico { color: #ef4444; }
    .fl-contract-row[data-st="warn"] .fl-contract-ico { color: #ffd641; }
    .fl-contract-row[data-st="unknown"] {
      color: rgba(255,255,255,0.4);
    }
    .fl-contract-row[data-st="unknown"] .fl-contract-ico { color: rgba(255,255,255,0.3); }

    /* Rule tooltip — small ℹ trigger on each rule card opens a positioned
       hover popover with plain-english explanation. Works on hover (desktop)
       and touch (pointerdown keeps it open until another tap). */
    .fl-rule-info {
      position: relative;
      width: 16px; height: 16px;
      flex-shrink: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      background: rgba(255,255,255,0.07);
      color: rgba(255,255,255,0.55);
      font-size: 10px;
      font-weight: 800;
      font-style: italic;
      font-family: Georgia, serif;
      margin-left: 5px;
      cursor: help;
      line-height: 1;
    }
    .fl-rule-info:hover { background: rgba(255,255,255,0.14); color: #fff; }
    .fl-rule-tip {
      position: absolute;
      top: calc(100% + 8px);
      right: 0;
      width: 260px;
      padding: 10px 12px;
      background: #151519;
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 8px;
      color: rgba(255,255,255,0.85);
      font-size: 11px;
      line-height: 1.5;
      box-shadow: 0 8px 24px rgba(0,0,0,0.5);
      opacity: 0;
      transform: translateY(-4px);
      pointer-events: none;
      transition: opacity 140ms, transform 140ms;
      z-index: 10;
      text-transform: none;
      letter-spacing: 0.01em;
      font-weight: 400;
    }
    .fl-rule-info:hover .fl-rule-tip,
    .fl-rule-info:focus .fl-rule-tip,
    .fl-rule-info[data-open="true"] .fl-rule-tip {
      opacity: 1;
      transform: translateY(0);
      pointer-events: auto;
    }
    /* Left-align the tooltip for rules near the left edge of the panel
       where the default right-anchored tip would overflow. Not used by
       default — opt-in by adding data-tip-side="left". */
    .fl-rule-info[data-tip-side="left"] .fl-rule-tip { right: auto; left: 0; }

    /* Snapshot-history card — SVG sparkline of curve_progress over time
       plus a strip of tier-transition dots aligned to the same x-axis.
       Shows how the token has evolved under FOUR-LIFE's grading. */
    .fl-spark {
      margin-top: 16px;
      padding: 12px 14px;
      border: 1px solid rgba(255,255,255,0.08);
      background: rgba(255,255,255,0.02);
      border-radius: 10px;
    }
    .fl-spark-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
      font-size: 9.5px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: rgba(255,255,255,0.5);
      font-weight: 700;
    }
    .fl-spark-range {
      color: rgba(255,255,255,0.4);
      font-size: 10px;
      font-weight: 500;
      letter-spacing: 0.04em;
      text-transform: none;
    }
    .fl-spark-svg {
      width: 100%;
      height: 60px;
      display: block;
    }
    .fl-spark-line {
      fill: none;
      stroke: url(#fl-spark-grad);
      stroke-width: 2;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .fl-spark-fill {
      fill: url(#fl-spark-fill-grad);
      opacity: 0.55;
    }
    .fl-spark-axis {
      display: flex;
      justify-content: space-between;
      font-size: 9.5px;
      color: rgba(255,255,255,0.35);
      font-family: ui-monospace, Menlo, Consolas, monospace;
      margin-top: 2px;
    }
    .fl-spark-ticks {
      display: flex;
      gap: 3px;
      margin-top: 10px;
      padding-top: 9px;
      border-top: 1px dashed rgba(255,255,255,0.07);
    }
    .fl-spark-tick {
      flex: 1;
      height: 6px;
      border-radius: 2px;
      background: rgba(255,255,255,0.08);
      transition: background 0.15s;
    }
    .fl-spark-tick[data-tier="healthy"] { background: #6cff32; }
    .fl-spark-tick[data-tier="graduation_watch"] { background: #00d4ff; }
    .fl-spark-tick[data-tier="graduated"] { background: #a855f7; }
    .fl-spark-tick[data-tier="observed"] { background: #eab308; }
    .fl-spark-tick[data-tier="at_risk"] { background: #ef4444; }
    .fl-spark-legend {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 12px;
      margin-top: 8px;
      font-size: 10px;
      color: rgba(255,255,255,0.45);
    }
    .fl-spark-legend span {
      display: inline-flex; align-items: center; gap: 5px;
      text-transform: capitalize;
    }
    .fl-spark-legend i {
      width: 7px; height: 7px; border-radius: 2px;
      background: rgba(255,255,255,0.3);
    }
    .fl-hero-chip {
      padding: 9px 10px;
      border-radius: 9px;
      background: rgba(255,255,255,0.035);
      border: 1px solid rgba(255,255,255,0.06);
    }
    .fl-hero-chip-v {
      font-size: 16px;
      font-weight: 700;
      letter-spacing: -0.01em;
      line-height: 1.1;
      color: #fff;
      font-variant-numeric: tabular-nums;
    }
    .fl-hero-chip-k {
      font-size: 9.5px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: rgba(255,255,255,0.45);
      margin-top: 3px;
      font-weight: 600;
    }

    /* ── Rule trace cards ───────────────────────────────────────────────
       Replaces the debugger-looking <table>. Each rule becomes a scannable
       card: circular pass/fail icon on the left, human rule name on top,
       metric vs threshold on bottom. */
    .fl-rules { display: flex; flex-direction: column; gap: 6px; }
    .fl-rule {
      display: grid;
      grid-template-columns: 32px 1fr auto;
      gap: 10px;
      align-items: center;
      padding: 10px 12px;
      border-radius: 10px;
      background: rgba(255,255,255,0.025);
      border: 1px solid rgba(255,255,255,0.06);
      transition: background 0.12s, border-color 0.12s;
    }
    .fl-rule:hover { background: rgba(255,255,255,0.04); border-color: rgba(255,255,255,0.1); }
    .fl-rule-ico {
      width: 26px; height: 26px;
      border-radius: 50%;
      display: inline-flex; align-items: center; justify-content: center;
      font-weight: 800;
      font-size: 13px;
    }
    .fl-rule[data-passed="true"] .fl-rule-ico {
      background: rgba(108,255,50,0.12);
      color: #6cff32;
      box-shadow: inset 0 0 0 1px rgba(108,255,50,0.3);
    }
    .fl-rule[data-passed="false"] .fl-rule-ico {
      background: rgba(239,68,68,0.12);
      color: #ef4444;
      box-shadow: inset 0 0 0 1px rgba(239,68,68,0.3);
    }
    .fl-rule-body { min-width: 0; }
    .fl-rule-name {
      font-size: 12.5px;
      font-weight: 600;
      color: #fff;
      margin-bottom: 2px;
      text-transform: capitalize;
    }
    .fl-rule-meta {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 10.5px;
      color: rgba(255,255,255,0.55);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .fl-rule-meta .fl-rule-op { color: rgba(255,255,255,0.4); padding: 0 4px; }
    .fl-rule-verdict {
      font-size: 9.5px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      padding: 4px 8px;
      border-radius: 999px;
      white-space: nowrap;
    }
    .fl-rule[data-passed="true"] .fl-rule-verdict {
      background: rgba(108,255,50,0.12);
      color: #6cff32;
    }
    .fl-rule[data-passed="false"] .fl-rule-verdict {
      background: rgba(239,68,68,0.12);
      color: #ef4444;
    }

    /* ── Risk evidence cards ────────────────────────────────────────────
       Severity-coded cards with a colored left border + severity SVG icon.
       Replaces the word-colored text approach. */
    .fl-risk-summary {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      border-radius: 10px;
      background: rgba(255,255,255,0.025);
      border: 1px solid rgba(255,255,255,0.06);
      margin-bottom: 8px;
      font-size: 12px;
    }
    .fl-risk-summary-ico { flex-shrink: 0; }
    .fl-risk-summary-k {
      color: rgba(255,255,255,0.55);
      text-transform: uppercase;
      font-size: 10px;
      letter-spacing: 0.1em;
      font-weight: 700;
      margin-right: 6px;
    }
    .fl-risk-summary-v {
      font-weight: 700;
      text-transform: capitalize;
    }
    .fl-risk {
      position: relative;
      padding: 11px 12px 11px 14px;
      border-radius: 10px;
      background: rgba(255,255,255,0.025);
      border: 1px solid rgba(255,255,255,0.06);
      margin-bottom: 6px;
      display: grid;
      grid-template-columns: 18px 1fr auto;
      gap: 10px;
      align-items: flex-start;
    }
    .fl-risk::before {
      content: "";
      position: absolute;
      left: 0; top: 8px; bottom: 8px;
      width: 3px;
      border-radius: 2px;
      background: var(--fl-sev-color, rgba(255,255,255,0.4));
    }
    .fl-risk-ico {
      color: var(--fl-sev-color, rgba(255,255,255,0.5));
      flex-shrink: 0;
      margin-top: 1px;
    }
    .fl-risk-body { min-width: 0; }
    .fl-risk-name {
      font-size: 12.5px;
      font-weight: 600;
      color: #fff;
      margin-bottom: 2px;
    }
    .fl-risk-desc {
      font-size: 11.5px;
      color: rgba(255,255,255,0.65);
      line-height: 1.45;
    }
    .fl-risk-sev {
      font-size: 9.5px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      padding: 4px 8px;
      border-radius: 999px;
      white-space: nowrap;
      background: color-mix(in srgb, var(--fl-sev-color, #fff) 14%, transparent);
      color: var(--fl-sev-color, rgba(255,255,255,0.8));
    }
  `;

  function tierColor(tier) {
    if (tier === "at_risk") return "#ef4444";
    if (tier === "observed") return "#eab308";
    return "#22c55e";
  }

  function formatMetric(metric, value) {
    if (typeof value === "number") {
      // Keep 2 decimals for floats, no decimals for ints
      if (Number.isInteger(value)) return String(value);
      return value.toFixed(2);
    }
    return String(value);
  }

  // Map the machine rule name to a short human-readable title. Keeps the
  // card body scannable — "whale_extreme" becomes "Whale extreme".
  function humanRuleName(rule) {
    if (!rule) return "rule";
    return String(rule).replace(/_/g, " ");
  }

  // Plain-english rationale for each deterministic rule. Shown in the ℹ
  // tooltip on every rule card so users learn WHY the threshold exists,
  // not just whether it tripped. Keyed by rule name from agent/badge.py.
  const RULE_EXPLAIN = {
    whale_extreme: "Single holder owning more than 40% of supply is an extreme rug risk — one sell wipes the chart.",
    whale_cluster: "Three or more wallets with large positions often coordinate exits. Clusters dump together.",
    sell_pressure: "Buy/sell ratio below 0.6 means sellers outpace buyers. Momentum is leaking out.",
    curve_stalled: "Bonding-curve progress under 5% means no organic demand arriving — the token isn't moving toward graduation.",
    graduation_watch: "Curve progress is above the threshold where Four.meme tokens historically graduate. High probability of migrating to PancakeSwap.",
    healthy: "Combined signal — rising buyers, no whale concentration, steady curve — passes every structural check.",
    at_risk: "At least one critical structural failure: whale concentration, stalled curve, or sustained sell pressure.",
    observed: "Default tier before enough data accumulates for a confident grade.",
    radar_estimate_cap: "This tier came from Four.meme's public ranking data only — the on-chain inputs required for Healthy or At Risk weren't measured.",
    holder_velocity: "Unique buyers joining per hour. Real organic growth runs 5+/hr; dead tokens run 0.",
    graduated: "Bonding curve completed — token has migrated to open DEX trading.",
  };
  function explainRule(rule) {
    if (!rule) return "";
    return RULE_EXPLAIN[rule] || `Deterministic rule in FOUR-LIFE's trust grade for this metric.`;
  }

  // Render the SVG health-score ring. Circumference = 2πr = 2π·38 ≈ 238.76.
  // stroke-dasharray is set to (score/100 * circumference) so the arc fills
  // proportionally. Animated via CSS transition on --fl-ring-len.
  function healthRingHtml(score) {
    const safe = Math.max(0, Math.min(100, typeof score === "number" ? score : 0));
    const circumference = 238.76;
    const len = (safe / 100) * circumference;
    const display = typeof score === "number" ? Math.round(score) : "—";
    return `
      <div class="fl-health-ring" aria-label="Health score ${display}">
        <svg viewBox="0 0 100 100" aria-hidden="true">
          <circle class="fl-ring-bg" cx="50" cy="50" r="38"/>
          <circle class="fl-ring-fg" cx="50" cy="50" r="38" style="--fl-ring-len:${len.toFixed(2)}"/>
        </svg>
        <div class="fl-ring-center">
          <div class="fl-ring-v">${escapeHtml(String(display))}</div>
          <div class="fl-ring-k">Health</div>
        </div>
      </div>`;
  }

  // Fetch + render contract-safety checklist. Data is cached for 10 min
  // on the server so hammering it from the overlay is safe. Module-level
  // cache de-dupes rapid panel toggles for the same token.
  const _contractCache = new Map();
  async function fetchContractRisk(address) {
    if (!address) return null;
    const key = address.toLowerCase();
    if (_contractCache.has(key)) return _contractCache.get(key);
    try {
      const r = await fetch(`${API_BASE}/api/token/${key}/contract-risk`, { cache: "no-store" });
      if (!r.ok) { _contractCache.set(key, null); return null; }
      const data = await r.json();
      _contractCache.set(key, data);
      return data;
    } catch {
      _contractCache.set(key, null);
      return null;
    }
  }

  const CHECK_OK_SVG = `<svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 10 9 15 16 6"/></svg>`;
  const CHECK_BAD_SVG = `<svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="5" x2="15" y2="15"/><line x1="15" y1="5" x2="5" y2="15"/></svg>`;
  const CHECK_UNKNOWN_SVG = `<svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="7"/><line x1="10" y1="14" x2="10" y2="10"/><circle cx="10" cy="7" r="0.8" fill="currentColor"/></svg>`;

  // Snapshot-history fetcher + sparkline. Pulls the last 30 snapshots so
  // we have enough points for a meaningful line without overwhelming the
  // panel. Module-level cache for 60s so re-opening the panel doesn't
  // re-fetch on every click.
  const _historyCache = new Map();
  async function fetchHistory(address) {
    if (!address) return null;
    const key = address.toLowerCase();
    const cached = _historyCache.get(key);
    const now = Date.now();
    if (cached && (now - cached.at) < 60_000) return cached.data;
    try {
      const r = await fetch(`${API_BASE}/api/token/${key}/history?limit=30`, { cache: "no-store" });
      if (!r.ok) { _historyCache.set(key, { data: null, at: now }); return null; }
      const data = await r.json();
      _historyCache.set(key, { data, at: now });
      return data;
    } catch {
      _historyCache.set(key, { data: null, at: now });
      return null;
    }
  }

  function formatRelative(ts) {
    if (!ts) return "—";
    const ageSec = Math.max(0, (Date.now() / 1000) - Number(ts));
    if (ageSec < 60) return `${Math.round(ageSec)}s ago`;
    if (ageSec < 3600) return `${Math.round(ageSec / 60)}m ago`;
    if (ageSec < 86_400) return `${Math.round(ageSec / 3600)}h ago`;
    return `${Math.round(ageSec / 86_400)}d ago`;
  }

  function historySparklineHtml(history) {
    if (!history || !Array.isArray(history.snapshots)) return "";
    // The API returns newest-first; reverse for left-to-right time axis.
    const snaps = history.snapshots.slice().reverse();
    if (snaps.length < 2) return "";
    const W = 420, H = 60, PAD_X = 2, PAD_Y = 4;
    const xs = snaps.map((s, i) => PAD_X + (i / (snaps.length - 1)) * (W - 2 * PAD_X));
    const ys = snaps.map((s) => {
      const v = Math.max(0, Math.min(100, Number(s?.metrics?.curve_progress_pct ?? 0)));
      return H - PAD_Y - (v / 100) * (H - 2 * PAD_Y);
    });
    const linePts = xs.map((x, i) => `${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");
    const fillPts = `${xs[0].toFixed(1)},${H} ${linePts} ${xs[xs.length - 1].toFixed(1)},${H}`;
    // Tick row — one tile per snapshot, colored by the tier at that point.
    const ticks = snaps.map((s) => `<div class="fl-spark-tick" data-tier="${escapeHtml(s.tier || "")}" title="${escapeHtml((s.tier || "").replace("_", " "))} · ${escapeHtml(formatRelative(s.recorded_at || s.timestamp))}"></div>`).join("");
    const firstTs = snaps[0]?.recorded_at || snaps[0]?.timestamp;
    const lastTs = snaps[snaps.length - 1]?.recorded_at || snaps[snaps.length - 1]?.timestamp;
    const tiersSeen = Array.from(new Set(snaps.map(s => s.tier).filter(Boolean)));
    const legendColors = { healthy: "#6cff32", graduation_watch: "#00d4ff", graduated: "#a855f7", observed: "#eab308", at_risk: "#ef4444" };
    const legendHtml = tiersSeen.map(t => `<span><i style="background:${legendColors[t] || "rgba(255,255,255,0.3)"}"></i>${escapeHtml(t.replace("_", " "))}</span>`).join("");
    return `
      <div class="fl-spark" role="region" aria-label="Snapshot history">
        <div class="fl-spark-head">
          <span>Snapshot history · ${snaps.length}</span>
          <span class="fl-spark-range">${escapeHtml(formatRelative(firstTs))} → now</span>
        </div>
        <svg class="fl-spark-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="fl-spark-grad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#00d4ff"/>
              <stop offset="100%" stop-color="#6cff32"/>
            </linearGradient>
            <linearGradient id="fl-spark-fill-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#00d4ff" stop-opacity="0.35"/>
              <stop offset="100%" stop-color="#00d4ff" stop-opacity="0"/>
            </linearGradient>
          </defs>
          <polygon class="fl-spark-fill" points="${fillPts}"/>
          <polyline class="fl-spark-line" points="${linePts}"/>
        </svg>
        <div class="fl-spark-axis"><span>Curve progress %</span><span>${history.count || snaps.length} pts</span></div>
        <div class="fl-spark-ticks" aria-label="Tier transitions">${ticks}</div>
        ${legendHtml ? `<div class="fl-spark-legend">${legendHtml}</div>` : ""}
      </div>`;
  }

  function contractSafetyHtml(cr) {
    if (!cr || cr.error) return "";
    // Build the 6 checks. Each row is {ok: true|false|null (unknown), label}.
    // "ok" means safe (green ✓); "bad" means risky (red ✗); null means
    // unknown (muted ? icon).
    const rows = [
      { st: cr.is_verified_on_bscscan ? "ok" : "bad", label: cr.is_verified_on_bscscan ? "Source verified on BscScan" : "Source unverified on BscScan" },
      { st: cr.has_mint_function === false ? "ok" : cr.has_mint_function === true ? "bad" : "unknown", label: cr.has_mint_function === true ? "Has mint function" : cr.has_mint_function === false ? "No mint function" : "Mint status unknown" },
      { st: cr.has_blacklist === false ? "ok" : cr.has_blacklist === true ? "bad" : "unknown", label: cr.has_blacklist === true ? "Has blacklist" : cr.has_blacklist === false ? "No blacklist" : "Blacklist unknown" },
      { st: cr.has_pause === false ? "ok" : cr.has_pause === true ? "bad" : "unknown", label: cr.has_pause === true ? "Has pause function" : cr.has_pause === false ? "No pause function" : "Pause unknown" },
      { st: cr.is_proxy === false ? "ok" : cr.is_proxy === true ? "warn" : "unknown", label: cr.is_proxy === true ? "Upgradable proxy" : cr.is_proxy === false ? "Not a proxy" : "Proxy status unknown" },
      { st: cr.owner_is_renounced === true ? "ok" : cr.has_ownership === false ? "ok" : cr.owner_is_renounced === false ? "warn" : "unknown", label: cr.owner_is_renounced === true ? "Ownership renounced" : cr.has_ownership === false ? "No owner role" : cr.owner_is_renounced === false ? "Owner still controls" : "Ownership unknown" },
    ];
    const iconFor = (st) => st === "ok" ? CHECK_OK_SVG : st === "bad" || st === "warn" ? CHECK_BAD_SVG : CHECK_UNKNOWN_SVG;
    const score = typeof cr.risk_score === "number" ? cr.risk_score : null;
    // risk_score: 0 = clean, higher = riskier. Color threshold matches
    // the evidence severity bands used elsewhere.
    const scoreColor = score === null ? "#6cff32"
      : score >= 50 ? "#ef4444"
      : score >= 20 ? "#ffd641"
      : "#6cff32";
    return `
      <div class="fl-contract" style="--fl-contract-color:${scoreColor}" role="region" aria-label="Contract safety">
        <div class="fl-contract-head">
          <span>Contract safety</span>
          ${score === null ? "" : `<span class="fl-contract-score">Risk ${score}/100</span>`}
        </div>
        <div class="fl-contract-list">
          ${rows.map(r => `<div class="fl-contract-row" data-st="${r.st}"><span class="fl-contract-ico">${iconFor(r.st)}</span>${escapeHtml(r.label)}</div>`).join("")}
        </div>
      </div>`;
  }

  function renderWhyTable(why) {
    if (!Array.isArray(why) || why.length === 0) {
      return `<div class="fl-empty">No rule trace returned.</div>`;
    }
    const cards = why.map((r) => {
      const passed = r.passed === true;
      const valueStr = formatMetric(r.metric, r.value);
      const thresholdStr = String(r.threshold ?? "");
      const opStr = r.operator || "";
      const explain = explainRule(r.rule);
      return `
        <div class="fl-rule" data-passed="${passed ? "true" : "false"}">
          <span class="fl-rule-ico" aria-hidden="true">${passed ? "✓" : "✗"}</span>
          <div class="fl-rule-body">
            <div class="fl-rule-name">${escapeHtml(humanRuleName(r.rule))}<span class="fl-rule-info" tabindex="0" role="button" aria-label="What does this rule mean?">i<span class="fl-rule-tip">${escapeHtml(explain)}</span></span></div>
            <div class="fl-rule-meta"><code>${escapeHtml(r.metric || "")}</code> = <code>${escapeHtml(valueStr)}</code><span class="fl-rule-op">${escapeHtml(opStr)}</span><code>${escapeHtml(thresholdStr)}</code></div>
          </div>
          <span class="fl-rule-verdict">${passed ? "Pass" : "Fail"}</span>
        </div>`;
    }).join("");
    return `<div class="fl-rules">${cards}</div>`;
  }

  // Inline SVG severity icon. Two glyphs cover the risk-level spectrum:
  // a warning triangle for critical/high, an info circle otherwise.
  function severityIcon(sev) {
    const triangle = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`;
    const info = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;
    return (sev === "critical" || sev === "high") ? triangle : info;
  }

  function renderEvidence(risk) {
    if (!risk?.ok || !risk.body) {
      const status = risk?.status;
      if (status === 404) {
        return `<div class="fl-empty">Token not yet tracked by the FOUR-LIFE monitor — evidence becomes available after the first monitoring cycle.</div>`;
      }
      return `<div class="fl-empty">Risk snapshot unavailable.</div>`;
    }
    const body = risk.body;
    const evidence = Array.isArray(body.evidence) ? body.evidence : [];
    const level = body.risk_level || "unknown";
    const levelColor = SEV_COLORS[level] || "rgba(255,255,255,0.5)";

    const summary = `
      <div class="fl-risk-summary" style="--fl-sev-color:${levelColor}">
        <span class="fl-risk-summary-ico" style="color:${levelColor}">${severityIcon(level)}</span>
        <span class="fl-risk-summary-k">Overall risk</span>
        <span class="fl-risk-summary-v" style="color:${levelColor}">${escapeHtml(level)}</span>
      </div>`;

    if (evidence.length === 0) {
      return summary + `<div class="fl-empty">No risk flags triggered.</div>`;
    }

    const items = evidence.map((e) => {
      const sev = e.severity || "info";
      const color = SEV_COLORS[sev] || "rgba(255,255,255,0.5)";
      const name = e.name || e.flag || "flag";
      const desc = e.description || e.detail || e.reason || "";
      return `
        <div class="fl-risk" style="--fl-sev-color:${color}">
          <span class="fl-risk-ico" aria-hidden="true">${severityIcon(sev)}</span>
          <div class="fl-risk-body">
            <div class="fl-risk-name">${escapeHtml(name)}</div>
            ${desc ? `<div class="fl-risk-desc">${escapeHtml(desc)}</div>` : ""}
          </div>
          <span class="fl-risk-sev">${escapeHtml(sev)}</span>
        </div>`;
    }).join("");

    return summary + items;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function close() {
    const root = window.FourLife?.getShadowRoot?.();
    if (!root) return;
    const wrap = root.getElementById("overlay-wrap");
    if (wrap) wrap.innerHTML = "";
    document.removeEventListener("keydown", onKeyDown);
  }

  // Keyboard shortcuts for the open panel. Fires only while an overlay
  // is mounted. We guard against firing inside form inputs so the page's
  // own search fields keep working. Modifier keys bypass us entirely.
  function onKeyDown(e) {
    if (e.key === "Escape") { close(); return; }
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    const tag = (e.target?.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || e.target?.isContentEditable) return;
    const root = window.FourLife?.getShadowRoot?.();
    if (!root) return;
    const key = e.key.toLowerCase();
    if (key === "f") {
      const btn = root.getElementById("fl-max");
      if (btn) { e.preventDefault(); btn.click(); }
    } else if (key === "w") {
      const btn = root.getElementById("fl-watch");
      if (btn) { e.preventDefault(); btn.click(); }
    } else if (key === "c") {
      const btn = root.getElementById("fl-copy");
      if (btn) { e.preventDefault(); btn.click(); }
    } else if (key === "s") {
      const a = root.querySelector('.fl-action[data-action="share"]');
      if (a) { e.preventDefault(); a.click(); }
    }
  }

  // ── Agent-context fetch ─────────────────────────────────────────────
  // Pulls the live DGrid + MYX attestation state ONCE when the panel opens
  // so we can show the current Merkle tips + BscScan links alongside the
  // per-token rule trace. Cached in-module for 60s so a user clicking
  // multiple tokens in quick succession doesn't hammer the API.
  const API_BASE = "https://four-life.gudman.xyz";

  // ── Creator survival-score fetch ────────────────────────────────────
  // The badge response now carries the deploying wallet; we combine it with
  // /api/creator/{wallet}/survival-score to show dev reputation in the
  // panel. Cached per-wallet in-module for the panel's lifetime.
  const _creatorCache = new Map();
  async function fetchCreatorScore(wallet) {
    if (!wallet) return null;
    const key = wallet.toLowerCase();
    if (_creatorCache.has(key)) return _creatorCache.get(key);
    try {
      const r = await fetch(`${API_BASE}/api/creator/${key}/survival-score`, { cache: "no-store" });
      if (!r.ok) { _creatorCache.set(key, null); return null; }
      const data = await r.json();
      _creatorCache.set(key, data);
      return data;
    } catch {
      _creatorCache.set(key, null);
      return null;
    }
  }

  function creatorSectionHtml(creator, score) {
    if (!creator) return "";
    const short = (a) => a ? a.slice(0, 6) + "…" + a.slice(-4) : "—";
    const tracked = !!(score && score.tracked);
    // Map trust_tier string → visible chip color. Values match api.py
    // _creator_trust_tier: proven / emerging / new_creator / unproven / unknown.
    const tierColorMap = {
      proven: "#6cff32",
      emerging: "#00d4ff",
      new_creator: "#ffd641",
      unproven: "#ff9640",
      unknown: "rgba(255,255,255,0.4)",
    };
    const tier = (score?.trust_tier || "unknown").toLowerCase();
    const tierColor = tierColorMap[tier] || tierColorMap.unknown;
    const gradRatePct = score ? Math.round((score.graduation_rate || 0) * 100) : 0;

    if (!tracked) {
      // Creator exists but we have no track record yet — don't invent one.
      return `
        <div class="fl-creator" role="region" aria-label="Deployer reputation">
          <div class="fl-creator-head">
            <div>
              <div class="fl-k">Deployer</div>
              <a href="https://bscscan.com/address/${escapeHtml(creator)}" target="_blank" rel="noopener noreferrer" class="fl-creator-addr">${escapeHtml(short(creator))} ↗</a>
            </div>
            <span class="fl-creator-tier" style="color:${escapeHtml(tierColor)};border-color:${escapeHtml(tierColor)}33">Unknown dev</span>
          </div>
          <div class="fl-creator-note">No prior FOUR-LIFE-tracked launches from this wallet.</div>
        </div>`;
    }

    return `
      <div class="fl-creator" role="region" aria-label="Deployer reputation">
        <div class="fl-creator-head">
          <div>
            <div class="fl-k">Deployer</div>
            <a href="https://bscscan.com/address/${escapeHtml(creator)}" target="_blank" rel="noopener noreferrer" class="fl-creator-addr">${escapeHtml(short(creator))} ↗</a>
          </div>
          <span class="fl-creator-tier" style="color:${escapeHtml(tierColor)};border-color:${escapeHtml(tierColor)}33">${escapeHtml(String(score.trust_tier || "unknown").replace("_", " "))}</span>
        </div>
        <div class="fl-creator-stats">
          <div class="fl-creator-stat">
            <div class="fl-creator-stat-v">${escapeHtml(String(score.launches_tracked || 0))}</div>
            <div class="fl-creator-stat-k">launches tracked</div>
          </div>
          <div class="fl-creator-stat">
            <div class="fl-creator-stat-v">${escapeHtml(String(score.graduations || 0))}</div>
            <div class="fl-creator-stat-k">graduated</div>
          </div>
          <div class="fl-creator-stat">
            <div class="fl-creator-stat-v">${gradRatePct}%</div>
            <div class="fl-creator-stat-k">grad rate</div>
          </div>
        </div>
        <a href="${API_BASE}/creators/${escapeHtml(creator)}" target="_blank" rel="noopener noreferrer" class="fl-creator-link">Full deployer ledger on FOUR-LIFE →</a>
      </div>`;
  }

  let _agentCtxCache = null;
  let _agentCtxCachedAt = 0;
  async function fetchAgentContext() {
    const now = Date.now();
    if (_agentCtxCache && (now - _agentCtxCachedAt) < 60_000) return _agentCtxCache;
    try {
      const [dgrid, myx] = await Promise.all([
        fetch(API_BASE + "/api/dgrid/audit", { cache: "no-store" }).then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(API_BASE + "/api/myx/signal-attestation", { cache: "no-store" }).then(r => r.ok ? r.json() : null).catch(() => null),
      ]);
      _agentCtxCache = {
        dgrid_tx: dgrid?.last_published_txhash || null,
        dgrid_count: dgrid?.last_published_count || 0,
        myx_tx: myx?.last_published_txhash || null,
        myx_count: myx?.last_published_count || 0,
      };
      _agentCtxCachedAt = now;
      return _agentCtxCache;
    } catch { return null; }
  }

  function agentContextHtml(ctx) {
    if (!ctx) return "";
    const short = (h) => h ? h.slice(0, 8) + "…" + h.slice(-4) : "—";
    const dgridCell = ctx.dgrid_tx
      ? `<a href="https://bscscan.com/tx/${escapeHtml(ctx.dgrid_tx)}" target="_blank" rel="noopener noreferrer">${escapeHtml(short(ctx.dgrid_tx))} ↗</a>`
      : `<span class="fl-v">—</span>`;
    const myxCell = ctx.myx_tx
      ? `<a href="https://bscscan.com/tx/${escapeHtml(ctx.myx_tx)}" target="_blank" rel="noopener noreferrer">${escapeHtml(short(ctx.myx_tx))} ↗</a>`
      : `<span class="fl-v">—</span>`;
    return `
      <div class="fl-agent-ctx" role="region" aria-label="Agent attestation context">
        <div>
          <div class="fl-k">DGrid root · ${ctx.dgrid_count} calls</div>
          ${dgridCell}
        </div>
        <div>
          <div class="fl-k">MYX root · ${ctx.myx_count} decisions</div>
          ${myxCell}
        </div>
      </div>`;
  }

  function open({ address, badge, risk, radarUrl }) {
    const root = window.FourLife?.getShadowRoot?.();
    if (!root) return;
    const wrap = root.getElementById("overlay-wrap");
    if (!wrap) return;

    // Ensure our overlay stylesheet exists (only once)
    if (!root.getElementById("fl-overlay-style")) {
      const s = document.createElement("style");
      s.id = "fl-overlay-style";
      s.textContent = OVERLAY_CSS;
      root.appendChild(s);
    }

    const b = badge?.body?.badge;
    const tier = b?.tier || "observed";
    const label = b?.label || "Observed";
    const desc = b?.description || "";
    const why = b?.why || [];
    // Truth-boundary: same discriminator as the pill. Modal heading must NOT
    // say "Certified" for a radar_estimate badge — judges inspecting the
    // panel would see heuristic data under a Certified headline otherwise.
    const tierSource = badge?.body?.tier_source || b?.tier_source || "certified";
    const isCertified = tierSource === "certified";
    const headingText = isCertified
      ? "FOUR-LIFE Certified"
      : "FOUR-LIFE Radar Estimate";
    const sourceNote = isCertified
      ? ""
      : `<div class="fl-source-note" role="note">
          Heuristic grade from Four.meme's public ranking — not a Certified tier. Track this token on FOUR-LIFE to upgrade it to on-chain measurement.
        </div>`;
    const panelAria = isCertified
      ? "FOUR-LIFE Certified details"
      : "FOUR-LIFE Radar Estimate details";

    // Pre-build share-to-X composer URL — composed lazily so we don't
    // have to re-fetch anything on click.
    const shareText = isCertified
      ? `FOUR-LIFE Certified — ${label} on $${(b?.metrics_snapshot?.symbol || "").toString().slice(0, 10) || "token"} ${address.slice(0, 8)}… verified on BNB Chain. ` +
        `Deterministic rule trace, no LLM in the trust path.\n\nRadar: https://four-life.gudman.xyz/radar/${address}`
      : `FOUR-LIFE Radar — ${label} estimate on $${(b?.metrics_snapshot?.symbol || "").toString().slice(0, 10) || "token"} ${address.slice(0, 8)}… ` +
        `Heuristic grade from public-ranking data. Upgrade to Certified by tracking it on FOUR-LIFE.\n\n${API_BASE}/radar/${address}`;
    const shareUrl = "https://twitter.com/intent/tweet?text=" + encodeURIComponent(shareText);
    const proofUrl = `${API_BASE}/proof`;
    const agentUrl = `https://bscscan.com/address/0x695E492398A51D2Ef5c699818e9616718aaEd1c1`;
    // One-click PancakeSwap deep link with the token pre-selected as the
    // output currency. Safer than dropping users on a generic swap page.
    const swapUrl = `https://pancakeswap.finance/swap?outputCurrency=${address}`;

    // Headline metrics surfaced in the hero. Pulls from metrics_snapshot
    // so the hero stays honest about what's measured vs what's missing.
    // Radar-estimate badges get a different chip set because their
    // health/age/whale inputs are approximated, not measured.
    const ms = b?.metrics_snapshot || {};
    const heroTierColor = tierColor(tier);
    const formatChip = (v, digits = 0) => {
      if (v === null || v === undefined || Number.isNaN(v)) return "—";
      if (typeof v !== "number") return String(v);
      if (Number.isInteger(v) && digits === 0) return v.toLocaleString();
      return v.toFixed(digits);
    };
    const curvePct = typeof ms.curve_progress_pct === "number" ? ms.curve_progress_pct : null;
    const heroKicker = isCertified
      ? `<span class="fl-hero-kicker-dot"></span>FOUR-LIFE Certified · ${escapeHtml((ms.phase || "").replace(/_/g, " ") || "live")}`
      : `<span class="fl-hero-kicker-dot"></span>FOUR-LIFE Radar Estimate`;

    let heroChipsHtml;
    if (isCertified) {
      const healthScore = typeof ms.health_score === "number" ? ms.health_score : null;
      const ageHours = typeof ms.age_hours === "number" ? ms.age_hours : null;
      const ageStr = ageHours === null ? "—"
        : ageHours < 1 ? `${Math.round(ageHours * 60)}m`
        : ageHours < 48 ? `${ageHours.toFixed(1)}h`
        : `${(ageHours / 24).toFixed(1)}d`;
      // Certified hero: animated health ring on the left, 2 chips stacked right.
      heroChipsHtml = `
        ${healthRingHtml(healthScore)}
        <div class="fl-hero-chip-stack">
          <div class="fl-hero-chip">
            <div class="fl-hero-chip-v">${curvePct === null ? "—" : `${formatChip(curvePct, 1)}%`}</div>
            <div class="fl-hero-chip-k">Curve</div>
          </div>
          <div class="fl-hero-chip">
            <div class="fl-hero-chip-v">${ageStr}</div>
            <div class="fl-hero-chip-k">Age</div>
          </div>
        </div>`;
    } else {
      const holders = typeof ms.unique_buyers === "number" ? ms.unique_buyers : null;
      const gradConf = (ms.graduation_confidence || "—").toString();
      heroChipsHtml = `
        <div class="fl-hero-chip">
          <div class="fl-hero-chip-v">${curvePct === null ? "—" : `${formatChip(curvePct, 1)}%`}</div>
          <div class="fl-hero-chip-k">Curve</div>
        </div>
        <div class="fl-hero-chip">
          <div class="fl-hero-chip-v">${holders === null ? "—" : formatChip(holders, 0)}</div>
          <div class="fl-hero-chip-k">Holders</div>
        </div>
        <div class="fl-hero-chip">
          <div class="fl-hero-chip-v" style="text-transform:capitalize;font-size:14px">${escapeHtml(gradConf)}</div>
          <div class="fl-hero-chip-k">Grad confidence</div>
        </div>`;
    }

    wrap.innerHTML = `
      <div class="fl-scrim" id="fl-scrim">
        <div class="fl-panel" role="dialog" aria-label="${escapeHtml(panelAria)}">
          <button class="fl-resize-bar" id="fl-resize-bar" type="button" aria-label="Toggle panel width" title="Expand / shrink panel (F)">
            <span class="fl-resize-arrow" aria-hidden="true"></span>
          </button>
          <div class="fl-header">
            <span style="font-size:10px;text-transform:uppercase;letter-spacing:0.16em;color:rgba(255,255,255,0.4);font-weight:700">FOUR-LIFE</span>
            <div style="display:flex; gap:8px; align-items:center">
              <button class="fl-watch" id="fl-watch" aria-pressed="false" title="Watch for tier transitions (W)">
                <span class="fl-watch-icon">☆</span><span class="fl-watch-label">Watch</span>
              </button>
              <button class="fl-max" id="fl-max" aria-pressed="false" aria-label="Maximize panel" title="Maximize (F)">
                <svg class="fl-max-expand" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 10V4h6"/><path d="M20 14v6h-6"/><path d="M4 4l7 7"/><path d="M20 20l-7-7"/></svg>
                <svg class="fl-max-collapse" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 4v6H4"/><path d="M14 20v-6h6"/><path d="M10 10L3 3"/><path d="M14 14l7 7"/></svg>
                <span class="fl-max-label">Expand</span>
              </button>
              <button class="fl-close" id="fl-close" aria-label="Close" title="Close (Esc)">×</button>
            </div>
          </div>
          <div class="fl-watch-toast" id="fl-watch-toast" role="status" aria-live="polite"></div>

          <div class="fl-hero ${isCertified ? "fl-hero-certified" : ""}" style="--fl-tier-color:${heroTierColor}">
            <div class="fl-hero-kicker">${heroKicker}</div>
            <h2 class="fl-hero-label">${escapeHtml(label)}</h2>
            <p class="fl-hero-sub">${escapeHtml(desc)}</p>
            <div class="fl-hero-chips">${heroChipsHtml}</div>
          </div>

          ${sourceNote}
          <div class="fl-addr">
            <span class="fl-addr-val">${escapeHtml(address)}</span>
            <button class="fl-copy" id="fl-copy" type="button" aria-label="Copy token address" data-copied="false" title="Copy address (C)">Copy</button>
          </div>

          <div id="fl-agent-ctx-slot"></div>
          <div id="fl-creator-slot"></div>
          <div id="fl-contract-slot"></div>
          <div id="fl-history-slot"></div>

          <h3>Rule trace</h3>
          ${renderWhyTable(why)}

          <h3>Risk evidence</h3>
          ${renderEvidence(risk)}

          <div class="fl-footer">
            <div class="fl-actions">
              <a class="fl-action primary" href="${escapeHtml(shareUrl)}" target="_blank" rel="noopener noreferrer" data-action="share" title="Share verdict to X (S)">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                Share verdict
              </a>
              <a class="fl-action" href="${escapeHtml(swapUrl)}" target="_blank" rel="noopener noreferrer" title="Open on PancakeSwap">Swap ↗</a>
              <a class="fl-action" href="${escapeHtml(radarUrl)}" target="_blank" rel="noopener noreferrer">FOUR-LIFE</a>
              <a class="fl-action" href="${escapeHtml(proofUrl)}" target="_blank" rel="noopener noreferrer">/proof</a>
              <a class="fl-action" href="${escapeHtml(agentUrl)}" target="_blank" rel="noopener noreferrer">Agent ↗</a>
            </div>
          </div>
        </div>
      </div>`;

    const scrim = root.getElementById("fl-scrim");
    const closeBtn = root.getElementById("fl-close");
    const watchBtn = root.getElementById("fl-watch");
    const maxBtn = root.getElementById("fl-max");
    const copyBtn = root.getElementById("fl-copy");
    const panel = wrap.querySelector(".fl-panel");
    const toast = root.getElementById("fl-watch-toast");
    if (scrim) scrim.addEventListener("click", (e) => { if (e.target === scrim) close(); });
    if (closeBtn) closeBtn.addEventListener("click", close);
    document.addEventListener("keydown", onKeyDown);

    // Copy-address — falls back to the legacy execCommand path if the
    // clipboard API is blocked by the host page's permissions policy.
    if (copyBtn) {
      copyBtn.addEventListener("click", async () => {
        let ok = false;
        try {
          if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(address);
            ok = true;
          }
        } catch {}
        if (!ok) {
          try {
            const ta = document.createElement("textarea");
            ta.value = address;
            ta.style.position = "fixed";
            ta.style.left = "-9999px";
            document.body.appendChild(ta);
            ta.select();
            ok = document.execCommand("copy");
            document.body.removeChild(ta);
          } catch {}
        }
        copyBtn.dataset.copied = ok ? "true" : "false";
        copyBtn.textContent = ok ? "Copied" : "Failed";
        clearTimeout(copyBtn._t);
        copyBtn._t = setTimeout(() => {
          copyBtn.dataset.copied = "false";
          copyBtn.textContent = "Copy";
        }, 1800);
      });
    }

    // Maximize toggle — swaps the panel between 460px (drawer) and
    // min(1100px, 95vw) (wide). We persist the choice for the current
    // browsing session via sessionStorage so opening a new token after
    // maximizing keeps the user's last preference. Falls back gracefully
    // if sessionStorage is blocked (private mode, certain MV3 contexts).
    const SS_KEY = "fl-panel-maximized";
    let isMaximized = false;
    try { isMaximized = sessionStorage.getItem(SS_KEY) === "1"; } catch {}
    const applyMaximized = (m) => {
      if (!panel || !maxBtn) return;
      panel.classList.toggle("fl-maximized", m);
      maxBtn.setAttribute("aria-pressed", m ? "true" : "false");
      maxBtn.setAttribute("aria-label", m ? "Restore panel" : "Maximize panel");
      maxBtn.setAttribute("title", m ? "Restore (F)" : "Maximize (F)");
      const lbl = maxBtn.querySelector(".fl-max-label");
      if (lbl) lbl.textContent = m ? "Shrink" : "Expand";
    };
    applyMaximized(isMaximized);
    if (maxBtn) {
      maxBtn.addEventListener("click", () => {
        isMaximized = !isMaximized;
        try { sessionStorage.setItem(SS_KEY, isMaximized ? "1" : "0"); } catch {}
        applyMaximized(isMaximized);
      });
    }
    // Secondary path: the persistent resize bar on the panel's left edge.
    // Same toggle behavior as maxBtn — having two triggers is intentional
    // so the affordance is impossible to miss regardless of which one the
    // user sees first.
    const resizeBar = root.getElementById("fl-resize-bar");
    if (resizeBar) {
      resizeBar.addEventListener("click", () => {
        isMaximized = !isMaximized;
        try { sessionStorage.setItem(SS_KEY, isMaximized ? "1" : "0"); } catch {}
        applyMaximized(isMaximized);
      });
    }

    // Watch-toggle wiring — talks to the service worker via chrome.runtime
    // messages. Unavailable in standalone dev contexts (no extension host);
    // gracefully no-ops in that case.
    if (watchBtn && chrome?.runtime?.sendMessage) {
      const setBtnState = (watching) => {
        watchBtn.setAttribute("aria-pressed", watching ? "true" : "false");
        const icon = watchBtn.querySelector(".fl-watch-icon");
        const lbl = watchBtn.querySelector(".fl-watch-label");
        if (icon) icon.textContent = watching ? "★" : "☆";
        if (lbl) lbl.textContent = watching ? "Watching" : "Watch";
        watchBtn.title = watching
          ? "You will get a Chrome notification when this tier transitions. Click to stop watching."
          : "Get Chrome notifications when this token's tier transitions";
      };
      const showToast = (msg) => {
        if (!toast) return;
        toast.textContent = msg;
        toast.dataset.visible = "true";
        clearTimeout(showToast._t);
        showToast._t = setTimeout(() => { toast.dataset.visible = "false"; }, 2400);
      };

      // Initial state check.
      chrome.runtime.sendMessage({ type: "fl:watch:is-watching", address }, (resp) => {
        if (resp?.ok) setBtnState(!!resp.watching);
      });

      watchBtn.addEventListener("click", () => {
        chrome.runtime.sendMessage({ type: "fl:watch:is-watching", address }, (resp) => {
          const isWatching = !!(resp?.ok && resp.watching);
          const msgType = isWatching ? "fl:watch:remove" : "fl:watch:add";
          chrome.runtime.sendMessage({ type: msgType, address }, (r) => {
            if (!r?.ok) {
              showToast(r?.reason === "limit"
                ? `Watchlist full (${r.limit}). Remove one to add another.`
                : "Couldn't update watchlist.");
              return;
            }
            if (msgType === "fl:watch:add") {
              if (r.reason === "already_watching") {
                setBtnState(true);
                showToast("Already watching.");
              } else {
                setBtnState(true);
                showToast("Watching. Chrome will notify on tier changes.");
              }
            } else {
              setBtnState(false);
              showToast("Removed from watchlist.");
            }
          });
        });
      });
    }

    // Fire agent-context fetch lazily — fills the slot when ready; doesn't
    // block the panel render if the API is slow.
    fetchAgentContext().then((ctx) => {
      const slot = root.getElementById("fl-agent-ctx-slot");
      if (slot && ctx) slot.innerHTML = agentContextHtml(ctx);
    });

    // Creator track record — only fires when the badge response carried a
    // creator wallet. Untracked devs still get a card ("Unknown dev") so the
    // absence of history is itself a surfaced signal.
    const creatorAddr = (badge?.body?.creator || "").toLowerCase();
    if (creatorAddr) {
      fetchCreatorScore(creatorAddr).then((score) => {
        const slot = root.getElementById("fl-creator-slot");
        if (slot) slot.innerHTML = creatorSectionHtml(creatorAddr, score);
      });
    }

    // Contract safety — fire in parallel. Response cached server-side for
    // 10min so this is cheap on repeat panel opens. Fills the slot when
    // ready; stays hidden if the RPC/BscScan scan fails.
    fetchContractRisk(address).then((cr) => {
      const slot = root.getElementById("fl-contract-slot");
      if (slot && cr && !cr.error) slot.innerHTML = contractSafetyHtml(cr);
    });

    // Snapshot history — sparkline of curve progress + tier-transition
    // strip. Only renders when there are ≥2 snapshots so we don't show
    // a misleading single-point "chart".
    fetchHistory(address).then((hist) => {
      const slot = root.getElementById("fl-history-slot");
      if (slot && hist && Array.isArray(hist.snapshots) && hist.snapshots.length >= 2) {
        slot.innerHTML = historySparklineHtml(hist);
      }
    });
  }

  window.FourLifeOverlay = { open, close };
})();
