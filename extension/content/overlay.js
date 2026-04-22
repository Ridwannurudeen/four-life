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

  // ── Agent-context fetch ─────────────────────────────────────────────
  // Pulls the live DGrid + MYX attestation state ONCE when the panel opens
  // so we can show the current Merkle tips + BscScan links alongside the
  // per-token rule trace. Cached in-module for 60s so a user clicking
  // multiple tokens in quick succession doesn't hammer the API.
  const API_BASE = "https://four-life.gudman.xyz";
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

    wrap.innerHTML = `
      <div class="fl-scrim" id="fl-scrim">
        <div class="fl-panel" role="dialog" aria-label="${escapeHtml(panelAria)}">
          <div class="fl-header">
            <span class="fl-tier-chip">
              <span class="fl-tier-dot" style="background:${tierColor(tier)}"></span>
              ${escapeHtml(label)}
            </span>
            <div style="display:flex; gap:8px; align-items:center">
              <button class="fl-watch" id="fl-watch" aria-pressed="false" title="Get Chrome notifications when this token's tier transitions">
                <span class="fl-watch-icon">☆</span><span class="fl-watch-label">Watch</span>
              </button>
              <button class="fl-close" id="fl-close" aria-label="Close">×</button>
            </div>
          </div>
          <div class="fl-watch-toast" id="fl-watch-toast" role="status" aria-live="polite"></div>
          <h2>${escapeHtml(headingText)}</h2>
          ${sourceNote}
          <p class="fl-desc">${escapeHtml(desc)}</p>
          <div class="fl-addr">${escapeHtml(address)}</div>

          <div id="fl-agent-ctx-slot"></div>

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
    const toast = root.getElementById("fl-watch-toast");
    if (scrim) scrim.addEventListener("click", (e) => { if (e.target === scrim) close(); });
    if (closeBtn) closeBtn.addEventListener("click", close);
    document.addEventListener("keydown", onKeyDown);

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
  }

  window.FourLifeOverlay = { open, close };
})();
