/**
 * FOUR-LIFE Certified — popup dashboard.
 *
 * Renders four data panes from the public API:
 *   1. Agent status (running / offline, agent_id, active_tokens)
 *   2. Chain counts (DGrid calls chained, MYX decisions chained)
 *   3. Latest on-chain attestation roots (clickable BscScan pills)
 *   4. Top radar entries (live tier chips)
 *
 * Re-fetches every 20s while the popup is open. Fails soft — every panel
 * handles its own null/skeleton state so a single 503 doesn't blank the UI.
 */

(() => {
  "use strict";

  const API = "https://four-life.gudman.xyz";
  const BSCSCAN = "https://bscscan.com/tx/";
  const REFRESH_MS = 20_000;

  // ── Utilities ─────────────────────────────────────────────────────

  const $ = (sel) => document.querySelector(sel);
  const el = (tag, attrs = {}, children = []) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") n.className = v;
      else if (k === "dataset") Object.assign(n.dataset, v);
      else if (k === "text") n.textContent = v;
      else if (k === "html") n.innerHTML = v;
      else n.setAttribute(k, v);
    }
    for (const c of [].concat(children)) {
      if (c == null) continue;
      n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    }
    return n;
  };
  const fmt = (n) => {
    if (n == null || Number.isNaN(n)) return "—";
    const v = Number(n);
    if (v >= 1000) return v.toLocaleString();
    return String(v);
  };
  const short = (s, head = 6, tail = 4) => {
    if (!s || s.length < head + tail + 2) return s || "—";
    return `${s.slice(0, head)}…${s.slice(-tail)}`;
  };

  const fetchJson = async (path) => {
    try {
      const r = await fetch(API + path, { cache: "no-store" });
      if (!r.ok) return null;
      return await r.json();
    } catch { return null; }
  };

  // ── Openers (MV3-safe tab open, avoids popup-close race) ──────────

  const openInTab = (url) => {
    if (!url) return;
    if (chrome?.tabs?.create) chrome.tabs.create({ url });
    else window.open(url, "_blank", "noopener");
  };
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[href]");
    if (!a) return;
    // Dedicated tour link — opens the extension's bundled onboarding page.
    if (a.id === "open-onboarding") {
      e.preventDefault();
      const url = chrome?.runtime?.getURL
        ? chrome.runtime.getURL("onboarding/onboarding.html")
        : "onboarding/onboarding.html";
      openInTab(url);
      window.close();
      return;
    }
    if (a.target === "_blank") {
      e.preventDefault();
      openInTab(a.href);
      window.close();
    }
  });

  // ── Panel renderers ────────────────────────────────────────────────

  const renderStatus = (status) => {
    const rail = $("#status-rail");
    const label = $("#status-label");
    if (!status) {
      rail.dataset.state = "offline";
      label.textContent = "Offline";
      return;
    }
    rail.dataset.state = status.running ? "online" : "offline";
    label.textContent = status.running ? "Agent live" : "Agent down";
    $("#stat-agent-id").textContent = status.agent_id != null ? `#${status.agent_id}` : "—";
    $("#stat-active").textContent = fmt(status.active_tokens);
  };

  const renderChainCounts = (dgridAudit, myxAttest) => {
    $("#stat-dgrid").textContent = fmt(dgridAudit?.num_calls_chained);
    $("#stat-myx").textContent = fmt(myxAttest?.num_signals_chained);
  };

  const renderAttests = (dgridAudit, myxAttest) => {
    const host = $("#attest-pills");
    host.innerHTML = "";
    const rows = [];
    if (dgridAudit?.last_published_txhash) {
      rows.push({
        kind: "DGrid",
        count: dgridAudit.last_published_count,
        label: "LLM calls",
        tx: dgridAudit.last_published_txhash,
      });
    }
    if (myxAttest?.last_published_txhash) {
      rows.push({
        kind: "MYX",
        count: myxAttest.last_published_count,
        label: "decisions",
        tx: myxAttest.last_published_txhash,
      });
    }
    if (rows.length === 0) {
      host.appendChild(el("div", { class: "empty", text: "No on-chain roots yet." }));
      return;
    }
    for (const r of rows) {
      const link = el("a", {
        class: "pill",
        href: BSCSCAN + r.tx,
        target: "_blank",
        rel: "noopener noreferrer",
      }, [
        el("span", { class: "pill-l" }, [
          el("span", { class: "pill-kind", text: r.kind }),
          el("span", { class: "pill-meta", text: `${fmt(r.count)} ${r.label}` }),
        ]),
        el("span", { class: "pill-tx", text: short(r.tx, 8, 6) + " ↗" }),
      ]);
      host.appendChild(link);
    }
  };

  const renderWatchlist = (watchlist) => {
    const host = $("#watch-list");
    const empty = $("#watch-empty");
    const count = $("#watch-count");
    if (!host) return;

    const entries = Object.entries(watchlist || {});
    if (count) count.textContent = String(entries.length);

    if (entries.length === 0) {
      host.innerHTML = "";
      if (empty) host.appendChild(empty);
      return;
    }

    host.innerHTML = "";
    // Sort: most-recent last_seen first. That pushes tokens the poller
    // has actually hit to the top.
    entries.sort((a, b) => (b[1].last_seen_ms || 0) - (a[1].last_seen_ms || 0));

    for (const [addr, data] of entries) {
      const tier = data.tier || "observed";
      const source = data.tier_source || "certified";
      const sym = data.symbol || short(addr, 4, 4);
      const row = el("a", {
        class: "row",
        href: "https://four.meme/en/token/" + addr,
        target: "_blank",
        rel: "noopener noreferrer",
      }, [
        el("span", {
          class: "tier-chip",
          dataset: { tier, source },
          title: source === "certified"
            ? "Certified — full on-chain data"
            : "Radar Estimate — public-ranking heuristic, not a Certified tier",
        }, [
          el("span", { class: "tchip-dot" }),
          el("span", { text: (tier || "").replace("_", " ") }),
        ]),
        el("span", { class: "row-body" }, [
          el("span", { class: "row-sym", text: String(sym).slice(0, 12) }),
          el("span", { class: "row-addr", text: short(addr, 4, 4) }),
        ]),
        el("span", { class: "row-curve", text: "★" }),
      ]);
      host.appendChild(row);
    }
  };

  // Relative-time formatter for activity timestamps. Same UX everyone uses.
  const relTime = (ts) => {
    if (!ts) return "—";
    const age = Math.max(0, Date.now() / 1000 - Number(ts));
    if (age < 60) return `${Math.round(age)}s`;
    if (age < 3600) return `${Math.round(age / 60)}m`;
    if (age < 86_400) return `${Math.round(age / 3600)}h`;
    return `${Math.round(age / 86_400)}d`;
  };

  // Human label per action_type. Maps the backend enum to a short title
  // that fits in the popup row without wrapping.
  const ACTION_LABEL = {
    alert: "Risk alert",
    post_content: "Social post",
    track: "Track started",
    track_token: "Track started",
    birth: "Token launched",
    launch: "Token launched",
    hedge: "Hedge decision",
    myx_decision: "MYX decision",
    think: "Market analysis",
    raise: "Raise step",
    defend: "Defend",
    accelerate: "Accelerate",
  };
  const ACTION_ICON = {
    alert: "!",
    post_content: "X",
    track: "+",
    track_token: "+",
    birth: "★",
    launch: "★",
    hedge: "⚖",
    myx_decision: "⚖",
    think: "◌",
  };

  const renderActivity = (data) => {
    const host = $("#activity-list");
    if (!host) return;
    const items = Array.isArray(data?.actions) ? data.actions.slice(0, 5) : [];
    if (items.length === 0) {
      host.innerHTML = "";
      host.appendChild(el("div", { class: "empty", text: "No agent actions yet." }));
      return;
    }
    host.innerHTML = "";
    for (const a of items) {
      const type = a.action_type || "action";
      const label = ACTION_LABEL[type] || type.replace(/_/g, " ");
      const icon = ACTION_ICON[type] || "·";
      const urg = a.urgency || "normal";
      const addr = a.token_address || "";
      const row = el("div", {
        class: "act",
        dataset: { type, urgency: urg },
      }, [
        el("span", { class: "act-ico", text: icon }),
        el("div", { class: "act-body" }, [
          el("span", { class: "act-title", text: label }),
          el("span", { class: "act-meta", text: short(addr, 4, 4) }),
        ]),
        el("span", { class: "act-time", text: relTime(a.timestamp) }),
      ]);
      host.appendChild(row);
    }
  };

  const renderRadar = (radar) => {
    const host = $("#radar-list");
    host.innerHTML = "";
    const entries = (radar?.radar || []).slice(0, 5);
    if (entries.length === 0) {
      host.appendChild(el("div", { class: "empty", text: "Radar warming up…" }));
      return;
    }
    for (const e of entries) {
      const tier = e.badge_tier || "observed";
      const source = e.tier_source || "certified";
      const curveRaw = Number(e.curve_progress || 0);
      const curve = curveRaw.toFixed(0);
      // Clamp the progress bar width to [0,100] — the curve is a percentage,
      // but the API can return >100 for graduated tokens (bonding curve done).
      const barPct = Math.max(0, Math.min(100, curveRaw));
      const row = el("a", {
        class: "row row-radar",
        href: "https://four.meme/en/token/" + e.token_address,
        target: "_blank",
        rel: "noopener noreferrer",
        style: `--row-curve:${barPct}%`,
      }, [
        // Tier chip with optional "Radar" badge for radar_estimate
        el("span", {
          class: "tier-chip",
          dataset: { tier, source },
          title: source === "certified"
            ? "Certified — full on-chain data"
            : "Radar Estimate — public-ranking heuristic, not a Certified tier",
        }, [
          el("span", { class: "tchip-dot" }),
          el("span", { text: tier.replace("_", " ") }),
        ]),
        el("span", { class: "row-body" }, [
          el("span", { class: "row-sym", text: (e.symbol || "—").slice(0, 12) }),
          el("span", { class: "row-addr", text: short(e.token_address, 4, 4) }),
        ]),
        el("span", { class: "row-curve", text: `${curve}%` }),
      ]);
      host.appendChild(row);
    }
  };

  // ── Orchestrator ───────────────────────────────────────────────────

  // Ask the service worker for the watchlist. Wrapped in a promise so it
  // fits into the same Promise.all pattern as the HTTP fetches below.
  const getWatchlist = () => new Promise((resolve) => {
    if (!chrome?.runtime?.sendMessage) return resolve({});
    try {
      chrome.runtime.sendMessage({ type: "fl:watch:list" }, (resp) => {
        resolve((resp?.ok && resp.watchlist) || {});
      });
    } catch { resolve({}); }
  });

  const refresh = async () => {
    const [status, dgridAudit, myxAttest, radar, actions, watchlist] = await Promise.all([
      fetchJson("/api/status"),
      fetchJson("/api/dgrid/audit"),
      fetchJson("/api/myx/signal-attestation"),
      fetchJson("/api/graduation-radar?limit=5"),
      fetchJson("/api/actions?limit=5"),
      getWatchlist(),
    ]);
    renderStatus(status);
    renderChainCounts(dgridAudit, myxAttest);
    renderAttests(dgridAudit, myxAttest);
    renderWatchlist(watchlist);
    renderRadar(radar);
    renderActivity(actions);
  };

  refresh();
  setInterval(refresh, REFRESH_MS);
})();
