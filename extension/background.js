/**
 * FOUR-LIFE Certified — service worker.
 *
 * Watchlist + Chrome notifications on tier transitions.
 *
 * Architecture:
 *   1. The overlay panel lets users ★ a token → stored in chrome.storage.sync.
 *   2. chrome.alarms fires every POLL_MINUTES minutes.
 *   3. For each watched token we GET /api/token/{addr}/badge.
 *   4. Compare {tier, tier_source} to the last-known pair in storage.
 *      A change in EITHER fires a notification (a certified upgrade from a
 *      prior radar_estimate is a real transition — the provenance changed
 *      even if the tier string is identical).
 *   5. Notification click → opens the token's FOUR-LIFE /radar page so the
 *      user lands on the full rule trace + attestation evidence.
 *
 * Design constraints:
 *   - No hidden trackers, no third-party telemetry, no auth. Everything is
 *     a direct call to four-life.gudman.xyz and storage stays on-device.
 *   - Soft on API: capped at 20 tokens per user (chrome.storage.sync quota
 *     permits ~100KB total; we use <5KB). Silent on fetch failures.
 *   - Never brands a radar_estimate transition as "Certified" in the
 *     notification copy — mirrors the truth-boundary enforced elsewhere.
 */

const API_BASE = "https://four-life.gudman.xyz";
const STORAGE_KEY = "fl:watch";       // { [addr]: { tier, tier_source, last_seen_ms } }
const ALARM_NAME = "fl:watch-poll";
const POLL_MINUTES = 3;                // Chrome alarm minimum is 1; 3 balances responsiveness + quota.
const MAX_WATCHED = 20;                // soft cap
const TIER_LABELS = {
  graduated: "Graduated",
  graduation_watch: "Graduation Watch",
  healthy: "Healthy",
  at_risk: "At Risk",
  observed: "Observed",
};

// ── Storage helpers ────────────────────────────────────────────────────

async function getWatchlist() {
  const { [STORAGE_KEY]: w } = await chrome.storage.sync.get(STORAGE_KEY);
  return (w && typeof w === "object") ? w : {};
}

async function setWatchlist(watchlist) {
  await chrome.storage.sync.set({ [STORAGE_KEY]: watchlist });
}

async function addToWatchlist(address) {
  const addr = (address || "").toLowerCase();
  if (!/^0x[0-9a-f]{40}$/.test(addr)) return { ok: false, reason: "invalid_address" };
  const w = await getWatchlist();
  if (w[addr]) return { ok: true, reason: "already_watching" };
  if (Object.keys(w).length >= MAX_WATCHED) {
    return { ok: false, reason: "limit", limit: MAX_WATCHED };
  }
  // Seed with the CURRENT tier so we don't fire a notification on the very
  // first poll just because storage was empty.
  const current = await fetchBadge(addr);
  w[addr] = {
    tier: current?.tier || null,
    tier_source: current?.tier_source || null,
    label: current?.label || null,
    symbol: current?.symbol || null,
    added_ms: Date.now(),
    last_seen_ms: Date.now(),
  };
  await setWatchlist(w);
  await ensureAlarm();
  return { ok: true, reason: "added" };
}

async function removeFromWatchlist(address) {
  const addr = (address || "").toLowerCase();
  const w = await getWatchlist();
  if (!w[addr]) return { ok: true, reason: "not_watching" };
  delete w[addr];
  await setWatchlist(w);
  return { ok: true, reason: "removed" };
}

// ── Badge fetch ────────────────────────────────────────────────────────

async function fetchBadge(address) {
  try {
    const r = await fetch(`${API_BASE}/api/token/${address}/badge`, {
      method: "GET",
      headers: { Accept: "application/json" },
      credentials: "omit",
      cache: "no-store",
    });
    if (!r.ok) return null;
    const body = await r.json();
    const badge = body?.badge;
    if (!badge) return null;
    return {
      tier: badge.tier || null,
      tier_source: body.tier_source || badge.tier_source || "certified",
      label: badge.label || TIER_LABELS[badge.tier] || null,
      symbol: badge?.metrics_snapshot?.symbol || null,
    };
  } catch { return null; }
}

// ── Transition detection + notification firing ────────────────────────

function transitionKey(prev, curr) {
  // A transition fires when either the tier OR the tier_source changes.
  // A radar_estimate → certified upgrade at the same tier IS a meaningful
  // change (the agent has begun on-chain measurement) — notify.
  if (!prev) return null;
  if (!curr) return null;
  if (prev.tier === curr.tier && prev.tier_source === curr.tier_source) return null;
  return `${prev.tier || "?"}[${prev.tier_source || "?"}] → ${curr.tier}[${curr.tier_source}]`;
}

function notificationTitle(entry, curr) {
  const sym = curr.symbol || entry.symbol || "token";
  return `$${sym} · tier changed`;
}

function notificationMessage(entry, curr) {
  const src = curr.tier_source === "certified" ? "Certified" : "Radar";
  const prevLabel = TIER_LABELS[entry.tier] || entry.tier || "unknown";
  const currLabel = TIER_LABELS[curr.tier] || curr.tier || "unknown";
  return `${prevLabel} → ${currLabel}  ·  ${src}`;
}

async function fireTransitionNotification(address, entry, curr) {
  const notifId = `fl:tier:${address}:${Date.now()}`;
  const title = notificationTitle(entry, curr);
  const message = notificationMessage(entry, curr);
  try {
    await chrome.notifications.create(notifId, {
      type: "basic",
      iconUrl: chrome.runtime.getURL("icons/icon-128.png"),
      title,
      message,
      contextMessage: "FOUR-LIFE Certified",
      priority: 1,
    });
    // Remember the opening URL so the click handler can route correctly.
    const targets = await getClickTargets();
    targets[notifId] = `${API_BASE}/radar/${address}`;
    await chrome.storage.session?.set({ "fl:notif-targets": targets }).catch(() => {});
    // Fallback to sync storage if session storage isn't available.
    if (!chrome.storage.session) {
      await chrome.storage.local.set({ "fl:notif-targets": targets });
    }
  } catch {
    // Notifications can fail on systems with DND or focus-assist on.
    // Silent — nothing to recover.
  }
}

async function getClickTargets() {
  const src = chrome.storage.session || chrome.storage.local;
  const { "fl:notif-targets": t } = await src.get("fl:notif-targets");
  return (t && typeof t === "object") ? t : {};
}

// ── Poller ─────────────────────────────────────────────────────────────

async function pollOnce() {
  const w = await getWatchlist();
  const addrs = Object.keys(w);
  if (addrs.length === 0) return;

  let mutated = false;
  for (const addr of addrs) {
    const curr = await fetchBadge(addr);
    if (!curr) continue;
    const prev = w[addr];
    const change = transitionKey(prev, curr);
    if (change) {
      await fireTransitionNotification(addr, prev, curr);
    }
    // Persist current state (always — so `last_seen_ms` stays fresh even
    // if no transition fired).
    w[addr] = {
      ...prev,
      tier: curr.tier,
      tier_source: curr.tier_source,
      label: curr.label || prev.label,
      symbol: curr.symbol || prev.symbol,
      last_seen_ms: Date.now(),
    };
    mutated = true;
  }
  if (mutated) await setWatchlist(w);
}

async function ensureAlarm() {
  const existing = await chrome.alarms.get(ALARM_NAME);
  if (existing && existing.periodInMinutes === POLL_MINUTES) return;
  await chrome.alarms.clear(ALARM_NAME);
  await chrome.alarms.create(ALARM_NAME, {
    delayInMinutes: 1,           // first fire ~1 min after install / startup
    periodInMinutes: POLL_MINUTES,
  });
}

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_NAME) pollOnce();
});

// ── Lifecycle hooks ────────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener((details) => {
  ensureAlarm();
  // Fresh install → show the 3-step onboarding page. Update / chrome_update /
  // shared_module_update don't reopen the tour — we don't want to re-spam
  // existing users every extension refresh.
  if (details?.reason === "install") {
    try {
      chrome.tabs.create({ url: chrome.runtime.getURL("onboarding/onboarding.html") });
    } catch { /* if tab creation fails (e.g. no permission on some platform) the install still succeeds */ }
  }
});

chrome.runtime.onStartup.addListener(() => {
  ensureAlarm();
});

// ── Notification click routing ────────────────────────────────────────

chrome.notifications.onClicked.addListener(async (notifId) => {
  try {
    const targets = await getClickTargets();
    const url = targets[notifId] || `${API_BASE}/proof`;
    await chrome.tabs.create({ url });
    chrome.notifications.clear(notifId);
    // Housekeeping: clear out the mapping for the clicked notif.
    delete targets[notifId];
    const src = chrome.storage.session || chrome.storage.local;
    await src.set({ "fl:notif-targets": targets });
  } catch { /* best effort */ }
});

// ── Message bridge (content script + popup) ───────────────────────────

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  // async sendResponse requires returning true from the listener.
  (async () => {
    try {
      if (msg?.type === "fl:watch:add") {
        const res = await addToWatchlist(msg.address);
        sendResponse(res);
      } else if (msg?.type === "fl:watch:remove") {
        const res = await removeFromWatchlist(msg.address);
        sendResponse(res);
      } else if (msg?.type === "fl:watch:list") {
        const w = await getWatchlist();
        sendResponse({ ok: true, watchlist: w });
      } else if (msg?.type === "fl:watch:is-watching") {
        const w = await getWatchlist();
        const addr = (msg.address || "").toLowerCase();
        sendResponse({ ok: true, watching: !!w[addr] });
      } else if (msg?.type === "fl:poll-now") {
        await pollOnce();
        sendResponse({ ok: true });
      } else {
        sendResponse({ ok: false, reason: "unknown_message" });
      }
    } catch (e) {
      sendResponse({ ok: false, reason: String(e).slice(0, 120) });
    }
  })();
  return true;
});
