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
      position: relative;
    }
    .fl-pill[data-state="ok"] .fl-dot::after {
      content: "";
      position: absolute;
      inset: -4px;
      border-radius: 50%;
      background: inherit;
      opacity: 0;
      animation: fl-pulse 2.2s ease-out infinite;
      pointer-events: none;
    }
    @keyframes fl-pulse {
      0%   { opacity: 0.55; transform: scale(0.8); }
      70%  { opacity: 0;    transform: scale(2.2); }
      100% { opacity: 0;    transform: scale(2.2); }
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
  // Supports every site the manifest injects us into. Each pattern is tied
  // to a specific host + path shape so we don't false-match arbitrary hex
  // strings that happen to appear on some unrelated page.
  //
  // `kind` distinguishes how to interpret the matched hex:
  //   - "token": the 0x address IS the token; done.
  //   - "pair" : the 0x address is a LP-pair contract; need one API hop
  //              (DEXScreener) to resolve the base token before we can
  //              call our own /api/token/... endpoint.
  const URL_PATTERNS = [
    // four.meme/[en/]token/0x... (existing)
    { host: /(?:^|\.)four\.meme$/i, re: /\/token\/(0x[0-9a-fA-F]{40})(?:[/?#]|$)/, kind: "token" },
    // bscscan.com/token/0x...
    { host: /(?:^|\.)bscscan\.com$/i, re: /\/token\/(0x[0-9a-fA-F]{40})(?:[/?#]|$)/, kind: "token" },
    // pancakeswap.finance/info/tokens/0x... (v2 + v3)
    { host: /(?:^|\.)pancakeswap\.finance$/i, re: /\/info\/(?:v\d+\/)?tokens?\/(0x[0-9a-fA-F]{40})(?:[/?#]|$)/, kind: "token" },
    // pancakeswap.finance/swap?outputCurrency=0x...
    { host: /(?:^|\.)pancakeswap\.finance$/i, re: /[?&]outputCurrency=(0x[0-9a-fA-F]{40})(?:[&#]|$)/, kind: "token" },
    // dexscreener.com/bsc/<pair_address> — the URL holds the PAIR contract,
    // not the token. We resolve it via DEXScreener's public API before
    // calling our own badge endpoint. BSC-only; other chains out of scope.
    { host: /(?:^|\.)dexscreener\.com$/i, re: /\/bsc\/(0x[0-9a-fA-F]{40})(?:[/?#]|$)/, kind: "pair" },
  ];
  function extractSourceRef(url) {
    let host = "";
    try { host = new URL(url).hostname; } catch { return null; }
    for (const { host: hre, re, kind } of URL_PATTERNS) {
      if (!hre.test(host)) continue;
      const m = re.exec(url);
      if (m && m[1]) return { kind, address: m[1].toLowerCase() };
    }
    return null;
  }

  // Legacy shim: callers that just want the token address (not the pair).
  // Returns null for pair-URL pages — the caller must use resolveTokenAddress.
  function extractTokenAddress(url) {
    const ref = extractSourceRef(url);
    return (ref && ref.kind === "token") ? ref.address : null;
  }

  // Cache pair → token resolutions for this session so SPA navigation
  // within DEXScreener (same pair, different tabs) doesn't re-hit the API.
  const _pairCache = new Map();

  async function resolvePairToToken(pairAddress) {
    const key = pairAddress.toLowerCase();
    if (_pairCache.has(key)) return _pairCache.get(key);
    try {
      const r = await fetch(`https://api.dexscreener.com/latest/dex/pairs/bsc/${key}`, {
        method: "GET",
        headers: { Accept: "application/json" },
        credentials: "omit",
        mode: "cors",
        cache: "no-store",
      });
      if (!r.ok) { _pairCache.set(key, null); return null; }
      const body = await r.json();
      // DEXScreener returns { pair: {...} } or { pairs: [{...}] }. The base
      // token is the thing users are looking at; the quote token is usually
      // WBNB/USDT. We grade the base.
      const pair = body?.pair || (body?.pairs && body.pairs[0]) || null;
      const base = pair?.baseToken?.address;
      const resolved = base ? base.toLowerCase() : null;
      _pairCache.set(key, resolved);
      return resolved;
    } catch {
      _pairCache.set(key, null);
      return null;
    }
  }

  // Single entry-point the orchestrator uses: resolve any URL to a token
  // address, doing the DEXScreener hop transparently when needed.
  async function resolveTokenAddress(url) {
    const ref = extractSourceRef(url);
    if (!ref) return null;
    if (ref.kind === "token") return ref.address;
    if (ref.kind === "pair") return await resolvePairToToken(ref.address);
    return null;
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

  // Bump on every extension release that touches the shadow DOM or CSS.
  // If a reused host has a different version tag, we tear it down and
  // rebuild with the fresh stylesheet so extension reloads without a
  // hard tab refresh still pick up new UI.
  const HOST_VERSION = "1.4.2";

  // ── Shadow DOM host ────────────────────────────────────────────────
  function ensureHost() {
    let host = document.getElementById(HOST_ID);
    if (host && host.shadowRoot) {
      if (host.dataset.flVersion === HOST_VERSION) return host;
      // Stale host from a previous extension version — rebuild.
      host.remove();
      host = null;
    }

    host = document.createElement("div");
    host.id = HOST_ID;
    host.dataset.flVersion = HOST_VERSION;
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
  function renderPill({ state, tier, label, address, tier_source }) {
    const host = ensureHost();
    if (!host || !host.shadowRoot) return;
    const root = host.shadowRoot.getElementById("pill-wrap");
    if (!root) return;

    const color = state === "loading"
      ? "#9ca3af"
      : state === "error"
        ? "#6b7280"
        : state === "not_tracked"
          ? "#6b7280"
          : TIER_COLORS[tier] || "#9ca3af";

    const displayLabel = state === "loading"
      ? "analyzing…"
      : state === "error"
        ? "unavailable"
        : state === "not_tracked"
          ? "Not a Four.meme launch"
          : label || TIER_FALLBACK_LABEL[tier] || "Observed";

    root.innerHTML = "";

    // Truth-boundary: the API distinguishes "certified" (full on-chain data)
    // from "radar_estimate" (heuristic from public ranking). Brand must reflect
    // which one — the extension MUST NOT label a radar_estimate badge as
    // "Certified" on Four.meme's own token pages.
    const tierSource = tier_source || "certified";
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

    // API returned 404 with a body like {badge: null, reason: "..."} →
    // the token isn't a Four.meme launch (or isn't in the ranking snapshot).
    // Render a distinct "not-tracked" state instead of a generic error so
    // BscScan / PancakeSwap visitors seeing ANY ERC-20 get an honest
    // message rather than a misleading "unavailable".
    if (badgeRes.status === 404 || (badgeRes.body && badgeRes.body.badge === null)) {
      renderPill({ state: "not_tracked", address });
      return;
    }
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
  // Handles both the direct-token case (resolves synchronously) and the
  // DEXScreener pair case (resolves via one DEXScreener API hop, ~200ms).
  // Shows the loading pill immediately on pair pages so users don't see a
  // blank top-right while the resolver runs.
  async function handleUrlChange() {
    const ref = extractSourceRef(location.href);
    if (!ref) { tearDown(); return; }

    // For pair URLs (DEXScreener), show a loading pill BEFORE the resolver
    // hop completes so the user sees we're doing something. For token URLs
    // we skip the pre-render since startPolling → refresh will show loading.
    if (ref.kind === "pair") {
      renderPill({ state: "loading", address: ref.address });
    }

    const addr = await resolveTokenAddress(location.href);
    if (!addr) {
      // Pair page but the pair isn't in DEXScreener's BSC dataset — hide.
      tearDown();
      return;
    }
    if (addr !== currentAddress) startPolling(addr);
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
