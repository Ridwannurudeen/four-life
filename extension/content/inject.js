// FOUR-LIFE Certified — content script.
// Detects four.meme/token/{address}, fetches the Certified badge + risk snapshot,
// and renders a pill into a Shadow DOM host so Four.meme's CSS never touches us.

(() => {
  const API_BASE = "https://four-life.gudman.xyz";
  const RADAR_URL = (addr) => `${API_BASE}/radar/${addr}`;
  const POLL_MS = 60_000;
  const HOST_ID = "four-life-certified-host";

  const TIER_COLORS = {
    graduated: "#22c55e",
    graduation_watch: "#22c55e",
    healthy: "#22c55e",
    observed: "#eab308",
    at_risk: "#ef4444",
  };

  const SHADOW_CSS = `
    :host, * { box-sizing: border-box; }
    .fl-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 14px;
      border-radius: 999px;
      background: rgba(17, 17, 20, 0.92);
      color: #f5f5f7;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      font-size: 13px;
      font-weight: 600;
      letter-spacing: 0.2px;
      border: 1px solid rgba(255,255,255,0.08);
      box-shadow: 0 6px 20px rgba(0,0,0,0.35);
      cursor: pointer;
      transition: transform 120ms ease, background 120ms ease, border-color 120ms ease;
      backdrop-filter: blur(10px);
    }
    .fl-pill:hover { transform: translateY(-1px); border-color: rgba(255,255,255,0.18); }
    .fl-pill[data-state="loading"], .fl-pill[data-state="error"] { cursor: default; opacity: 0.85; }
    .fl-dot {
      width: 9px; height: 9px; border-radius: 50%;
      box-shadow: 0 0 0 3px rgba(255,255,255,0.06);
    }
    .fl-brand { color: #ffffff; letter-spacing: 0.5px; }
    .fl-sep { color: rgba(255,255,255,0.35); }
    .fl-tag { color: rgba(255,255,255,0.85); text-transform: capitalize; font-weight: 500; }
  `;

  const TIER_FALLBACK_LABEL = {
    graduated: "Graduated",
    graduation_watch: "Graduation Watch",
    healthy: "Healthy",
    observed: "Observed",
    at_risk: "At Risk",
  };

  let currentAddress = null;
  let pollTimer = null;
  let lastBadgeState = null;
  let lastRiskState = null;

  // ── Address extraction ─────────────────────────────────────────────
  function extractTokenAddress(url) {
    // Four.meme token page: https://four.meme/token/0x<40-hex>
    const match = /\/token\/(0x[0-9a-fA-F]{40})(?:[/?#]|$)/.exec(url);
    return match ? match[1].toLowerCase() : null;
  }

  // ── API calls ──────────────────────────────────────────────────────
  async function fetchJson(path, address) {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "GET",
      headers: { Accept: "application/json" },
      credentials: "omit",
      mode: "cors",
      cache: "no-store",
    });
    if (!res.ok) {
      return { ok: false, status: res.status, body: null, address };
    }
    const body = await res.json().catch(() => null);
    return { ok: true, status: res.status, body, address };
  }

  async function loadBadge(address) {
    try {
      return await fetchJson(`/api/token/${address}/badge`, address);
    } catch (err) {
      return { ok: false, status: 0, body: null, address, error: err };
    }
  }

  async function loadRiskSnapshot(address) {
    try {
      return await fetchJson(`/api/token/${address}/risk-snapshot`, address);
    } catch (err) {
      return { ok: false, status: 0, body: null, address, error: err };
    }
  }

  // ── Shadow DOM host ────────────────────────────────────────────────
  function ensureHost() {
    let host = document.getElementById(HOST_ID);
    if (host && host.shadowRoot) return host;

    host = document.createElement("div");
    host.id = HOST_ID;
    host.style.position = "fixed";
    host.style.top = "16px";
    host.style.right = "16px";
    host.style.zIndex = "2147483646";
    host.style.pointerEvents = "none";

    const shadow = host.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = SHADOW_CSS;
    shadow.appendChild(style);

    const pillWrap = document.createElement("div");
    pillWrap.id = "pill-wrap";
    pillWrap.style.pointerEvents = "auto";
    shadow.appendChild(pillWrap);

    const overlayWrap = document.createElement("div");
    overlayWrap.id = "overlay-wrap";
    overlayWrap.style.pointerEvents = "auto";
    shadow.appendChild(overlayWrap);

    // Insert when body is ready
    if (document.body) {
      document.body.appendChild(host);
    } else {
      document.addEventListener("DOMContentLoaded", () => document.body.appendChild(host), { once: true });
    }
    return host;
  }

  // ── Pill rendering ─────────────────────────────────────────────────
  function renderPill({ state, tier, label, address }) {
    const host = ensureHost();
    if (!host || !host.shadowRoot) return;
    const root = host.shadowRoot.getElementById("pill-wrap");
    if (!root) return;

    const color = state === "loading"
      ? "#9ca3af"
      : state === "error"
        ? "#6b7280"
        : TIER_COLORS[tier] || "#9ca3af";

    const displayLabel = state === "loading"
      ? "analyzing…"
      : state === "error"
        ? "unavailable"
        : label || TIER_FALLBACK_LABEL[tier] || "Observed";

    root.innerHTML = "";

    // Truth-boundary: the API distinguishes "certified" (full on-chain data)
    // from "radar_estimate" (heuristic from public ranking). Brand must reflect
    // which one — the extension MUST NOT label a radar_estimate badge as
    // "Certified" on Four.meme's own token pages.
    const tierSource = opts.tier_source || "certified";
    const isCertified = tierSource === "certified";
    const ariaPrefix = isCertified ? "FOUR-LIFE Certified" : "FOUR-LIFE Radar Estimate";

    const pill = document.createElement("button");
    pill.type = "button";
    pill.className = "fl-pill";
    pill.setAttribute("data-state", state);
    pill.setAttribute("data-tier-source", tierSource);
    pill.setAttribute("aria-label", `${ariaPrefix}: ${displayLabel}`);

    const dot = document.createElement("span");
    dot.className = "fl-dot";
    dot.style.backgroundColor = color;

    const brand = document.createElement("span");
    brand.className = "fl-brand";
    brand.textContent = "FOUR-LIFE";

    const sep = document.createElement("span");
    sep.className = "fl-sep";
    sep.textContent = isCertified ? "·" : "· Radar ·";

    const tag = document.createElement("span");
    tag.className = "fl-tag";
    tag.textContent = displayLabel;

    pill.appendChild(dot);
    pill.appendChild(brand);
    pill.appendChild(sep);
    pill.appendChild(tag);

    pill.addEventListener("click", () => {
      if (state === "loading" || state === "error" || !address) return;
      window.FourLifeOverlay?.open({
        address,
        badge: lastBadgeState,
        risk: lastRiskState,
        radarUrl: RADAR_URL(address),
      });
    });

    root.appendChild(pill);
  }

  // ── Orchestrator ───────────────────────────────────────────────────
  async function refresh(address) {
    if (address !== currentAddress) return; // page changed mid-flight

    renderPill({ state: "loading", address });

    const [badgeRes, riskRes] = await Promise.all([
      loadBadge(address),
      loadRiskSnapshot(address),
    ]);

    if (address !== currentAddress) return; // page changed during fetch

    lastBadgeState = badgeRes;
    lastRiskState = riskRes;

    if (!badgeRes.ok || !badgeRes.body?.badge) {
      renderPill({ state: "error", address });
      return;
    }

    const badge = badgeRes.body.badge;
    // Pull tier_source from the top-level field (where the API stamps it for
    // every response) with a fallback to the badge sub-object and finally
    // "certified" for graceful degradation on older API versions.
    const tierSource =
      badgeRes.body.tier_source ||
      badge.tier_source ||
      "certified";
    renderPill({
      state: "ready",
      tier: badge.tier,
      label: badge.label,
      tier_source: tierSource,
      address,
    });
  }

  function startPolling(address) {
    stopPolling();
    currentAddress = address;
    refresh(address);
    pollTimer = setInterval(() => {
      if (currentAddress) refresh(currentAddress);
    }, POLL_MS);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function tearDown() {
    stopPolling();
    currentAddress = null;
    const host = document.getElementById(HOST_ID);
    if (host) host.remove();
  }

  // ── SPA navigation handling ────────────────────────────────────────
  function handleUrlChange() {
    const addr = extractTokenAddress(location.href);
    if (addr) {
      if (addr !== currentAddress) startPolling(addr);
    } else {
      tearDown();
    }
  }

  // Content scripts run in an isolated world, so monkey-patching
  // history.pushState here wouldn't catch page-originated SPA navs.
  // Poll location.href instead — cheap and reliable.
  let lastHref = location.href;
  setInterval(() => {
    if (location.href !== lastHref) {
      lastHref = location.href;
      handleUrlChange();
    }
  }, 500);
  window.addEventListener("popstate", handleUrlChange);

  // Boot
  handleUrlChange();

  // Expose minimal hook so overlay.js can find the shadow host
  window.FourLife = {
    getShadowRoot() {
      const host = document.getElementById(HOST_ID);
      return host ? host.shadowRoot : null;
    },
  };

})();
