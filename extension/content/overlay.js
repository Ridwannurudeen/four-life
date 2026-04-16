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
    }
    .fl-panel h2 {
      margin: 0 0 4px;
      font-size: 18px;
      font-weight: 700;
      letter-spacing: 0.2px;
    }
    .fl-panel h3 {
      margin: 22px 0 10px;
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: rgba(255,255,255,0.55);
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
    .fl-addr {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 11px;
      color: rgba(255,255,255,0.5);
      margin-top: 6px;
      word-break: break-all;
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

  function renderWhyTable(why) {
    if (!Array.isArray(why) || why.length === 0) {
      return `<div class="fl-empty">No rule trace returned.</div>`;
    }
    const rows = why.map((r) => {
      const passed = r.passed === true;
      return `
        <tr>
          <td>${escapeHtml(r.rule || "")}</td>
          <td><code>${escapeHtml(r.metric || "")}</code></td>
          <td><code>${escapeHtml(formatMetric(r.metric, r.value))}</code></td>
          <td><code>${escapeHtml(r.operator || "")} ${escapeHtml(String(r.threshold))}</code></td>
          <td class="${passed ? "fl-pass" : "fl-fail"}">${passed ? "PASS" : "FAIL"}</td>
        </tr>`;
    }).join("");
    return `
      <table class="fl-table">
        <thead>
          <tr><th>Rule</th><th>Metric</th><th>Value</th><th>Threshold</th><th>Result</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
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

    const header = `
      <div class="fl-evidence-head" style="margin-bottom:10px">
        <span>Overall risk: <span style="color:${levelColor}; text-transform:capitalize">${escapeHtml(level)}</span></span>
      </div>`;

    if (evidence.length === 0) {
      return header + `<div class="fl-empty">No risk flags triggered.</div>`;
    }

    const items = evidence.map((e) => {
      const sev = e.severity || "info";
      const color = SEV_COLORS[sev] || "rgba(255,255,255,0.5)";
      return `
        <div class="fl-evidence-item">
          <div class="fl-evidence-head">
            <span>${escapeHtml(e.name || e.flag || "flag")}</span>
            <span class="fl-sev" style="color:${color}">${escapeHtml(sev)}</span>
          </div>
          <div class="fl-evidence-body">${escapeHtml(e.description || e.detail || e.reason || "")}</div>
        </div>`;
    }).join("");

    return header + items;
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

    wrap.innerHTML = `
      <div class="fl-scrim" id="fl-scrim">
        <div class="fl-panel" role="dialog" aria-label="FOUR-LIFE Certified details">
          <div class="fl-header">
            <span class="fl-tier-chip">
              <span class="fl-tier-dot" style="background:${tierColor(tier)}"></span>
              ${escapeHtml(label)}
            </span>
            <button class="fl-close" id="fl-close" aria-label="Close">×</button>
          </div>
          <h2>FOUR-LIFE Certified</h2>
          <p class="fl-desc">${escapeHtml(desc)}</p>
          <div class="fl-addr">${escapeHtml(address)}</div>

          <h3>Rule trace</h3>
          ${renderWhyTable(why)}

          <h3>Risk evidence</h3>
          ${renderEvidence(risk)}

          <div class="fl-footer">
            <span class="fl-watermark">powered by FOUR-LIFE</span>
            <a class="fl-link" href="${escapeHtml(radarUrl)}" target="_blank" rel="noopener noreferrer">Open operator checklist →</a>
          </div>
        </div>
      </div>`;

    const scrim = root.getElementById("fl-scrim");
    const closeBtn = root.getElementById("fl-close");
    if (scrim) scrim.addEventListener("click", (e) => { if (e.target === scrim) close(); });
    if (closeBtn) closeBtn.addEventListener("click", close);
    document.addEventListener("keydown", onKeyDown);
  }

  window.FourLifeOverlay = { open, close };
})();
