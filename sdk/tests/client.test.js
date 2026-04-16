// Tests for @four-life/sdk. Runs against a local mock — no live network.
// Execute with: cd sdk && npm run build && npm test
import { test } from "node:test";
import assert from "node:assert/strict";

// Import the built dist (run `npm run build` first).
import { FourLife, FourLifeError, DEFAULT_API_BASE, SDK_VERSION } from "../dist/index.js";

function mockFetch(routes) {
  return async (url, init) => {
    const pathAndQuery = url.replace(DEFAULT_API_BASE, "");
    const route = routes[pathAndQuery] ?? routes[pathAndQuery.split("?")[0]];
    if (!route) {
      return new Response(JSON.stringify({ error: "not mocked", url }), { status: 500 });
    }
    if (typeof route === "function") return route(url, init);
    return new Response(JSON.stringify(route.body), {
      status: route.status ?? 200,
      headers: { "Content-Type": "application/json" },
    });
  };
}

test("constructs with defaults", () => {
  const fl = new FourLife({ fetch: mockFetch({}) });
  assert.equal(fl.baseUrl, DEFAULT_API_BASE);
  assert.ok(typeof SDK_VERSION === "string");
});

test("rejects invalid token addresses", async () => {
  const fl = new FourLife({ fetch: mockFetch({}) });
  await assert.rejects(() => fl.getBadge(""), FourLifeError);
  await assert.rejects(() => fl.getBadge("not-an-address"), FourLifeError);
  await assert.rejects(() => fl.getBadge("0xtooshort"), FourLifeError);
});

test("getBadge parses the response", async () => {
  const sample = {
    token_address: "0xabc" + "0".repeat(37),
    badge: {
      tier: "graduation_watch",
      label: "Graduation Watch",
      description: "test",
      why: [{ rule: "curve_advanced", metric: "curve_progress_pct", value: 75, threshold: 70, operator: ">=", passed: true }],
      metrics_snapshot: {},
      version: "four-life-certified-v1",
    },
    data_source: "live_monitor",
    model_version: "four-life-v1.1",
    last_updated_at: 1700000000,
    powered_by: "FOUR-LIFE",
  };
  const fl = new FourLife({
    fetch: mockFetch({
      [`/api/token/${sample.token_address}/badge`]: { body: sample },
    }),
  });
  const r = await fl.getBadge(sample.token_address);
  assert.equal(r.badge.tier, "graduation_watch");
  assert.equal(r.badge.why[0].passed, true);
});

test("getGraduationRadar encodes filters", async () => {
  let capturedUrl = "";
  const fl = new FourLife({
    fetch: async (url) => {
      capturedUrl = String(url);
      return new Response(JSON.stringify({
        radar: [], total_scanned: 0, filters: {}, known_quote_assets: [], model_version: "v1", last_updated_at: 0, timestamp: 0, powered_by: "",
      }), { status: 200 });
    },
  });
  await fl.getGraduationRadar({ limit: 30, quoteAsset: "BNB", minConfidence: "high", sortBy: "health_score" });
  assert.match(capturedUrl, /limit=30/);
  assert.match(capturedUrl, /quote_asset=BNB/);
  assert.match(capturedUrl, /min_confidence=high/);
  assert.match(capturedUrl, /sort_by=health_score/);
});

test("trackToken sends POST with auth + body", async () => {
  let captured = { url: "", body: "", authz: "" };
  const fl = new FourLife({
    apiSecret: "sk_test",
    fetch: async (url, init) => {
      captured.url = String(url);
      captured.body = String(init.body);
      const h = new Headers(init.headers);
      captured.authz = h.get("Authorization") ?? "";
      return new Response(JSON.stringify({ status: "tracking", token_address: "0x1", name: "", symbol: "", message: "" }), { status: 200 });
    },
  });
  await fl.trackToken({
    tokenAddress: "0x" + "a".repeat(40),
    name: "Test",
    symbol: "T",
    quoteAsset: "usd1",
  });
  assert.match(captured.url, /\/api\/agent\/track$/);
  assert.equal(captured.authz, "Bearer sk_test");
  const parsed = JSON.parse(captured.body);
  assert.equal(parsed.name, "Test");
  assert.equal(parsed.quote_asset, "USD1"); // normalized uppercase
});

test("FourLifeError carries status + body", async () => {
  const fl = new FourLife({
    fetch: async () => new Response(JSON.stringify({ error: "nope" }), { status: 404 }),
  });
  try {
    await fl.getBadge("0x" + "1".repeat(40));
    assert.fail("should have thrown");
  } catch (err) {
    assert.ok(err instanceof FourLifeError);
    assert.equal(err.status, 404);
    assert.deepEqual(err.body, { error: "nope" });
  }
});

test("watchToken polls and returns unwatch function", async () => {
  const addr = "0x" + "9".repeat(40);
  let calls = 0;
  const fl = new FourLife({
    fetch: async () => {
      calls++;
      return new Response(JSON.stringify({
        token_address: addr,
        badge: { tier: "healthy", label: "Healthy", description: "", why: [], metrics_snapshot: {}, version: "v1" },
        data_source: "live_monitor", model_version: "v1", last_updated_at: 0, powered_by: "",
      }), { status: 200 });
    },
  });
  const seen = [];
  const unwatch = fl.watchToken(addr, (b) => { seen.push(b.badge.tier); }, { intervalMs: 20 });
  await new Promise((r) => setTimeout(r, 75));
  unwatch();
  await new Promise((r) => setTimeout(r, 50));
  const afterUnwatch = seen.length;
  await new Promise((r) => setTimeout(r, 60));
  assert.equal(seen.length, afterUnwatch, "no polls after unwatch");
  assert.ok(calls >= 2, "polled at least twice");
  assert.ok(seen.every((t) => t === "healthy"));
});

test("timeout aborts slow requests", async () => {
  const fl = new FourLife({
    timeoutMs: 50,
    fetch: async (_url, init) =>
      new Promise((resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          const err = new Error("aborted");
          err.name = "AbortError";
          reject(err);
        });
        // never resolves on its own
      }),
  });
  await assert.rejects(() => fl.getBadge("0x" + "c".repeat(40)), FourLifeError);
});
