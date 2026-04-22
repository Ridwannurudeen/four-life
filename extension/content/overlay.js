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
    .fl-max {
      background: transparent;
      border: 1px solid rgba(255,255,255,0.1);
      color: rgba(255,255,255,0.7);
      border-radius: 8px;
      width: 30px; height: 30px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0;
    }
    .fl-max:hover { color: #fff; border-color: rgba(255,255,255,0.25); }
    .fl-max svg { display: block; }
    /* Swap glyphs based on panel state: expand icon when restored,
       collapse icon when maximized. Visible SVGs are controlled via
       aria-pressed on the button. */
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
      margin-top: 24px;
      padding-top: 16px;
      border-top: 1px solid rgba(255,255,255,0.06);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
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

  function renderWhyTable(why) {
    if (!Array.isArray(why) || why.length === 0) {
      return `<div class="fl-empty">No rule trace returned.</div>`;
    }
    const cards = why.map((r) => {
      const passed = r.passed === true;
      const valueStr = formatMetric(r.metric, r.value);
      const thresholdStr = String(r.threshold ?? "");
      const opStr = r.operator || "";
      return `
        <div class="fl-rule" data-passed="${passed ? "true" : "false"}">
          <span class="fl-rule-ico" aria-hidden="true">${passed ? "✓" : "✗"}</span>
          <div class="fl-rule-body">
            <div class="fl-rule-name">${escapeHtml(humanRuleName(r.rule))}</div>
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

  function onKeyDown(e) {
    if (e.key === "Escape") close();
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
      heroChipsHtml = `
        <div class="fl-hero-chip">
          <div class="fl-hero-chip-v">${healthScore === null ? "—" : formatChip(healthScore, 0)}</div>
          <div class="fl-hero-chip-k">Health</div>
        </div>
        <div class="fl-hero-chip">
          <div class="fl-hero-chip-v">${curvePct === null ? "—" : `${formatChip(curvePct, 1)}%`}</div>
          <div class="fl-hero-chip-k">Curve</div>
        </div>
        <div class="fl-hero-chip">
          <div class="fl-hero-chip-v">${ageStr}</div>
          <div class="fl-hero-chip-k">Age</div>
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
          <div class="fl-header">
            <span style="font-size:10px;text-transform:uppercase;letter-spacing:0.16em;color:rgba(255,255,255,0.4);font-weight:700">FOUR-LIFE</span>
            <div style="display:flex; gap:8px; align-items:center">
              <button class="fl-watch" id="fl-watch" aria-pressed="false" title="Get Chrome notifications when this token's tier transitions">
                <span class="fl-watch-icon">☆</span><span class="fl-watch-label">Watch</span>
              </button>
              <button class="fl-max" id="fl-max" aria-pressed="false" aria-label="Maximize panel" title="Maximize">
                <svg class="fl-max-expand" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 10V4h6"/><path d="M20 14v6h-6"/><path d="M4 4l7 7"/><path d="M20 20l-7-7"/></svg>
                <svg class="fl-max-collapse" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 4v6H4"/><path d="M14 20v-6h6"/><path d="M10 10L3 3"/><path d="M14 14l7 7"/></svg>
              </button>
              <button class="fl-close" id="fl-close" aria-label="Close">×</button>
            </div>
          </div>
          <div class="fl-watch-toast" id="fl-watch-toast" role="status" aria-live="polite"></div>

          <div class="fl-hero" style="--fl-tier-color:${heroTierColor}">
            <div class="fl-hero-kicker">${heroKicker}</div>
            <h2 class="fl-hero-label">${escapeHtml(label)}</h2>
            <p class="fl-hero-sub">${escapeHtml(desc)}</p>
            <div class="fl-hero-chips">${heroChipsHtml}</div>
          </div>

          ${sourceNote}
          <div class="fl-addr">${escapeHtml(address)}</div>

          <div id="fl-agent-ctx-slot"></div>
          <div id="fl-creator-slot"></div>

          <h3>Rule trace</h3>
          ${renderWhyTable(why)}

          <h3>Risk evidence</h3>
          ${renderEvidence(risk)}

          <div class="fl-footer">
            <div class="fl-actions">
              <a class="fl-action primary" href="${escapeHtml(shareUrl)}" target="_blank" rel="noopener noreferrer" data-action="share">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                Share verdict
              </a>
              <a class="fl-action" href="${escapeHtml(radarUrl)}" target="_blank" rel="noopener noreferrer">Open on FOUR-LIFE</a>
              <a class="fl-action" href="${escapeHtml(proofUrl)}" target="_blank" rel="noopener noreferrer">/proof</a>
              <a class="fl-action" href="${escapeHtml(agentUrl)}" target="_blank" rel="noopener noreferrer">Agent wallet ↗</a>
            </div>
          </div>
        </div>
      </div>`;

    const scrim = root.getElementById("fl-scrim");
    const closeBtn = root.getElementById("fl-close");
    const watchBtn = root.getElementById("fl-watch");
    const maxBtn = root.getElementById("fl-max");
    const panel = wrap.querySelector(".fl-panel");
    const toast = root.getElementById("fl-watch-toast");
    if (scrim) scrim.addEventListener("click", (e) => { if (e.target === scrim) close(); });
    if (closeBtn) closeBtn.addEventListener("click", close);
    document.addEventListener("keydown", onKeyDown);

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
      maxBtn.setAttribute("title", m ? "Restore" : "Maximize");
    };
    applyMaximized(isMaximized);
    if (maxBtn) {
      maxBtn.addEventListener("click", () => {
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
  }

  window.FourLifeOverlay = { open, close };
})();
