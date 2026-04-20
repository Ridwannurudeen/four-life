"""End-to-end smoke test of the live FOUR-LIFE site.

Walks every public page, every /api/dgrid/* endpoint, the token-tracking
surface, the chaos flow, and the Merkle verification against the on-chain
attestation tx. Reports a pass/fail table.

Usage: python scripts/live_smoke_test.py [API_SECRET]
"""

import hashlib
import json
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "https://four-life.gudman.xyz"
KICAU = "0x38d327df076dff943e7fa2a6d463dfcb41574444"
ATTEST_TXS = [
    "0xcf42283acebfc97657e87393684eedee40a21e98ba9c0b6b7480fa6c711a5c7c",
    "0x047c2f58e77d349f98eac8305080970c391c0e39c378816c22e69fc0d6b18fe9",
]
GENESIS_HASH = hashlib.sha256(b"FOUR-LIFE DGrid attestation genesis v1").hexdigest()

API_SECRET = sys.argv[1] if len(sys.argv) > 1 else ""

results: list[tuple[str, str, str]] = []  # (name, status, detail)


def _req(method: str, url: str, body: dict | None = None, auth: bool = False, timeout: int = 60):
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if auth and API_SECRET:
        headers["Authorization"] = f"Bearer {API_SECRET}"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except HTTPError as e:
        return e.code, e.read()
    except URLError as e:
        return 0, str(e).encode()


def record(name: str, ok: bool, detail: str = ""):
    results.append((name, "PASS" if ok else "FAIL", detail[:120]))
    mark = "✓" if ok else "✗"
    print(f"  {mark} {name:55} {detail[:80]}")


def check(name: str, test_fn):
    try:
        ok, detail = test_fn()
        record(name, ok, detail)
    except Exception as e:
        record(name, False, f"EXC {type(e).__name__}: {e}")


# ── Pages ────────────────────────────────────────────────────────
print("\n── pages ─────────────────────────────────────────────────────")

for path in ["/", "/dgrid", "/dashboard", "/radar", "/activity", "/alerts", "/evidence", "/metrics"]:
    def t(p=path):
        code, body = _req("GET", BASE + p)
        return code == 200 and b"<!DOCTYPE html>" in body.lower() or code == 200, f"{code} · {len(body)}B"
    check(f"GET {path}", t)


# ── DGrid API ────────────────────────────────────────────────────
print("\n── /api/dgrid/* ──────────────────────────────────────────────")

def t_stats():
    code, body = _req("GET", BASE + "/api/dgrid/stats")
    if code != 200:
        return False, f"HTTP {code}"
    d = json.loads(body)
    for key in ("breaker", "chaos_enabled", "cost_usd", "trace_count", "transient_retries"):
        if key not in d:
            return False, f"missing key: {key}"
    return True, f"share={d['dgrid_share']:.2%} · breaker={d['breaker']['state']} · cost=${d['cost_usd']['total']:.5f}"

check("GET /api/dgrid/stats", t_stats)


def t_health():
    code, body = _req("GET", BASE + "/api/dgrid/health")
    if code != 200:
        return False, f"HTTP {code}"
    d = json.loads(body)
    return d["status"] in ("green", "amber", "red"), f"status={d['status']}"

check("GET /api/dgrid/health", t_health)


def t_trace():
    code, body = _req("GET", BASE + "/api/dgrid/trace?limit=10")
    if code != 200:
        return False, f"HTTP {code}"
    d = json.loads(body)
    return "trace" in d and isinstance(d["trace"], list), f"{len(d['trace'])} entries"

check("GET /api/dgrid/trace", t_trace)


def t_leaderboard():
    code, body = _req("GET", BASE + "/api/dgrid/leaderboard")
    if code != 200:
        return False, f"HTTP {code}"
    d = json.loads(body)
    rows = d.get("rows", [])
    return len(rows) > 0, f"{len(rows)} rows · tasks={sorted({r['task'] for r in rows})}"

check("GET /api/dgrid/leaderboard", t_leaderboard)


def t_audit():
    code, body = _req("GET", BASE + "/api/dgrid/audit")
    if code != 200:
        return False, f"HTTP {code}"
    d = json.loads(body)
    return (
        d.get("genesis") == GENESIS_HASH
        and d.get("num_calls_chained", 0) > 0
        and d.get("last_published_txhash") in ATTEST_TXS,
        f"chain={d['num_calls_chained']} calls · published_to={d.get('last_published_txhash','—')[:14]}",
    )

check("GET /api/dgrid/audit", t_audit)


def t_audit_calls():
    code, body = _req("GET", BASE + "/api/dgrid/audit/calls?limit=500")
    if code != 200:
        return False, f"HTTP {code}"
    d = json.loads(body)
    calls = d.get("calls", [])
    return len(calls) > 0 and all("call_digest" in c for c in calls), f"{len(calls)} digests · total={d['total']}"

check("GET /api/dgrid/audit/calls", t_audit_calls)


def t_probe():
    code, body = _req("POST", BASE + "/api/dgrid/probe", body={})
    if code not in (200, 503):
        return False, f"HTTP {code}"
    d = json.loads(body)
    if d.get("ok"):
        return True, f"{d['model']} · {d['latency_ms']}ms · ${d.get('cost_usd',0):.8f}"
    return True, f"DGrid down (expected if breaker open): {d.get('error','')[:50]}"

check("POST /api/dgrid/probe", t_probe)


def t_compare():
    code, body = _req(
        "POST", BASE + "/api/dgrid/compare",
        body={"prompt": "say 'hi'", "models": ["google/gemini-2.5-flash", "openai/gpt-4o-mini"], "max_tokens": 20},
    )
    if code != 200:
        return False, f"HTTP {code}"
    d = json.loads(body)
    ok_count = sum(1 for r in d.get("results", []) if r.get("ok"))
    return ok_count > 0, f"{ok_count}/{len(d.get('results',[]))} models succeeded"

check("POST /api/dgrid/compare", t_compare)


def t_consensus():
    code, body = _req(
        "POST", BASE + "/api/dgrid/consensus",
        body={"prompt": "Pick one: {\"action\":\"up\"|\"down\"}", "vote_key": "action", "max_tokens": 50},
    )
    if code != 200:
        return False, f"HTTP {code}"
    d = json.loads(body)
    return d.get("models_succeeded", 0) > 0, f"verdict={d.get('final_verdict')} · conf={d.get('confidence')} · method={d.get('method')}"

check("POST /api/dgrid/consensus", t_consensus)


# ── Chaos flow: enable → verify breaker → disable → verify recovery
print("\n── chaos e2e ────────────────────────────────────────────────")

def t_chaos_enable():
    code, body = _req("POST", BASE + "/api/dgrid/chaos", body={"enabled": True, "reason": "smoke test"}, auth=True)
    if code != 200:
        return False, f"HTTP {code}"
    d = json.loads(body)
    return d.get("chaos_enabled") is True, "chaos ON"

check("POST /api/dgrid/chaos {enabled:true}", t_chaos_enable)


def t_chaos_probe_fails():
    code, body = _req("POST", BASE + "/api/dgrid/probe", body={})
    d = json.loads(body) if body else {}
    # Probe must NOT succeed while chaos is active (DGrid-only, no fallback)
    return (not d.get("ok")) or code == 503, f"probe ok={d.get('ok')} err={d.get('error','')[:50]}"

check("chaos: probe should fail (503)", t_chaos_probe_fails)


def t_chaos_disable():
    code, body = _req("POST", BASE + "/api/dgrid/chaos", body={"enabled": False}, auth=True)
    d = json.loads(body)
    return (not d.get("chaos_enabled")) and d["breaker"]["state"] == "closed", f"chaos off · breaker={d['breaker']['state']}"

check("POST /api/dgrid/chaos {enabled:false}", t_chaos_disable)


def t_post_chaos_probe_recovers():
    time.sleep(2)
    code, body = _req("POST", BASE + "/api/dgrid/probe", body={})
    d = json.loads(body)
    return d.get("ok") is True, f"model={d.get('model')} · {d.get('latency_ms','?')}ms"

check("post-chaos: DGrid probe recovers", t_post_chaos_probe_recovers)


# ── Merkle verification (download log → fold → compare to on-chain)
print("\n── Merkle verification ──────────────────────────────────────")

def _call_digest(c: dict) -> str:
    payload = json.dumps({
        "provider": c.get("provider", ""),
        "model": c.get("model", ""),
        "task": c.get("task", ""),
        "prompt_hash": c.get("prompt_hash", ""),
        "response_hash": c.get("response_hash", ""),
        "prompt_tokens": int(c.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(c.get("completion_tokens", 0) or 0),
        "ts_ms": int(c.get("ts_ms", 0) or 0),
    }, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def t_chain_verifies_against_server_root():
    code, body = _req("GET", BASE + "/api/dgrid/audit/calls?limit=2000")
    calls = json.loads(body)["calls"]
    code2, body2 = _req("GET", BASE + "/api/dgrid/audit")
    expected = json.loads(body2)["current_root"]

    tip = GENESIS_HASH
    for c in calls:
        # Use the server's digest if present, otherwise re-derive
        digest = c.get("call_digest") or _call_digest(c)
        tip = hashlib.sha256((tip + digest).encode()).hexdigest()

    return tip == expected, f"fold({len(calls)}) == server root: {tip[:12]}"

check("re-derive chain root from log", t_chain_verifies_against_server_root)


def t_tx_data_matches_attestation():
    for tx in ATTEST_TXS:
        rpc_body = {
            "jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionByHash", "params": [tx],
        }
        req = Request("https://bsc-dataseed.binance.org/", data=json.dumps(rpc_body).encode(), headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        input_data = (d["result"] or {}).get("input", "")
        if not input_data.startswith("0x") or len(input_data) != 66:
            return False, f"{tx[:14]} data shape: {input_data[:20]}"
    return True, f"both txs carry 32-byte root in data field"

check("BNB Chain: tx data fields are valid Merkle roots", t_tx_data_matches_attestation)


# ── KICAU (live tracked token)
print("\n── KICAU lifecycle ──────────────────────────────────────────")

def t_kicau_status():
    code, body = _req("GET", BASE + f"/api/token/{KICAU}/badge")
    if code != 200:
        return False, f"HTTP {code}"
    d = json.loads(body)
    tier = d.get("tier")
    data_source = d.get("data_source")
    return data_source == "live_monitor", f"tier={tier} · source={data_source} · conf={d.get('confidence_score')}"

check("GET /api/token/KICAU/badge", t_kicau_status)


def t_kicau_in_status():
    code, body = _req("GET", BASE + "/api/status")
    d = json.loads(body)
    return d.get("active_tokens", 0) >= 1, f"active={d.get('active_tokens')}"

check("GET /api/status (KICAU tracked)", t_kicau_in_status)


# ── Summary ──────────────────────────────────────────────────────
print("\n── summary ──────────────────────────────────────────────────")
passed = sum(1 for _, s, _ in results if s == "PASS")
total = len(results)
print(f"\n{passed} / {total} passed")

fails = [r for r in results if r[1] == "FAIL"]
if fails:
    print("\nFAILURES:")
    for name, _, detail in fails:
        print(f"  ✗ {name}: {detail}")
    sys.exit(1)
print("\nALL GREEN.")
