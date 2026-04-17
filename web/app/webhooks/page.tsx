"use client";

import { useState } from "react";
import Link from "next/link";

const API_BASE = "https://four-life.gudman.xyz";

const EVENTS = [
  {
    name: "badge.tier_changed",
    description: "Fires when a token's FOUR-LIFE Certified tier transitions (e.g. healthy → at_risk).",
    payload: `{
  "id": "evt_xxxx...",
  "type": "badge.tier_changed",
  "created_at": 1776380000,
  "token_address": "0xabc...",
  "from_tier": "healthy",
  "to_tier": "at_risk",
  "at": 1776380000,
  "why": [
    {
      "rule": "whale_extreme",
      "metric": "top_holder_pct",
      "value": 55.2,
      "threshold": 40,
      "operator": ">=",
      "passed": true
    }
  ],
  "metrics": { "curve_progress_pct": 42, "top_holder_pct": 55.2, "..." : "..." },
  "data_source": "live_monitor"
}`,
  },
  {
    name: "protection.level_changed",
    description: "Fires when a token under Protection Mode transitions between safe / warn / critical.",
    payload: `{
  "id": "evt_xxxx...",
  "type": "protection.level_changed",
  "created_at": 1776380000,
  "token_address": "0xabc...",
  "from_level": "safe",
  "to_level": "critical",
  "at": 1776380000,
  "fired_rules": [
    {
      "rule": "contract_rug_critical",
      "metric": "contract_risk_score",
      "value": 80,
      "threshold": 60,
      "severity": "critical"
    }
  ],
  "recommended_actions": ["halt_content_posts", "fire_webhook_alert"],
  "thresholds": { "critical_whale_concentration": 55.0, "..." : "..." }
}`,
  },
];

const VERIFY_JS = `// Node.js / any runtime with crypto
const crypto = require("crypto");

function verifyFourLifeSignature({ secret, body, header, toleranceSeconds = 300 }) {
  const parts = Object.fromEntries(
    header.split(",").map(s => s.split("=").map(x => x.trim())),
  );
  const t = parseInt(parts.t, 10);
  const v1 = parts.v1;
  if (!t || !v1) return false;
  if (Math.abs(Math.floor(Date.now() / 1000) - t) > toleranceSeconds) return false;

  const expected = crypto
    .createHmac("sha256", secret)
    .update(\`\${t}.\${body}\`)
    .digest("hex");

  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(v1));
}

// Express handler
app.post("/webhook", express.raw({ type: "application/json" }), (req, res) => {
  const body = req.body.toString("utf-8");
  const sig = req.headers["x-fourlife-signature"] || "";
  if (!verifyFourLifeSignature({ secret: process.env.WHSEC, body, header: sig })) {
    return res.status(401).send("bad signature");
  }
  const event = JSON.parse(body);
  console.log("received:", event.type, event.token_address);
  res.status(200).send("ok");
});`;

const VERIFY_PY = `# Python (Flask or any framework that gives raw body)
import hmac, hashlib, time

def verify_fourlife_signature(*, secret: str, body: str, header: str, tolerance: int = 300) -> bool:
    parts = dict(seg.split("=", 1) for seg in header.split(",") if "=" in seg)
    try:
        t = int(parts.get("t", ""))
    except ValueError:
        return False
    if abs(int(time.time()) - t) > tolerance:
        return False
    expected = hmac.new(
        secret.encode(), f"{t}.{body}".encode(), hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, parts.get("v1", ""))


@app.post("/webhook")
def webhook():
    body = request.get_data(as_text=True)
    sig = request.headers.get("X-FourLife-Signature", "")
    if not verify_fourlife_signature(secret=WHSEC, body=body, header=sig):
        return ("bad signature", 401)
    event = request.get_json()
    print("received:", event["type"], event["token_address"])
    return ("ok", 200)`;

const SUBSCRIBE_CURL = `# Subscribe — returns the shared secret EXACTLY ONCE
curl -X POST ${API_BASE}/api/webhooks \\
  -H "Authorization: Bearer $API_SECRET" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "https://your-service.example/fourlife-webhook",
    "events": ["badge.tier_changed", "protection.level_changed"],
    "token_filter": null
  }'

# Response contains:
#   "id"     → subscription id (whs_...)
#   "secret" → shared HMAC secret (whsec_...)  ← STORE THIS NOW`;

function CodeBlock({ code, label }: { code: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* ignore */ }
  };
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-white/5 px-3 py-2">
        <div className="text-[11px] uppercase tracking-wider text-white/40">{label}</div>
        <button
          onClick={copy}
          className="text-[11px] text-white/60 hover:text-white bg-white/5 hover:bg-white/10 border border-white/10 rounded px-2 py-0.5 transition-colors"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="px-4 py-3 text-xs overflow-x-auto font-mono leading-relaxed text-white/80">
        {code}
      </pre>
    </div>
  );
}

export default function WebhooksPage() {
  return (
    <div className="min-h-screen bg-[#0f1012] text-white bg-grid">
      <header className="border-b border-white/5 sticky top-0 z-30 bg-[#0f1012]/90 backdrop-blur-md">
        <div className="max-w-5xl mx-auto px-5 py-4 flex items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-2">
            <span className="h-8 w-8 rounded-lg bg-gradient-to-br from-[#6cff32] to-[#00d4ff] flex items-center justify-center font-bold text-black">4</span>
            <div>
              <div className="text-sm font-semibold">FOUR-LIFE</div>
              <div className="text-[10px] text-white/40 uppercase tracking-wider">Webhooks</div>
            </div>
          </Link>
          <div className="flex items-center gap-2">
            <Link href="/radar" className="btn-pill bg-white/5 hover:bg-white/10 border border-white/10 text-xs">Radar</Link>
            <Link href="/creators" className="btn-pill bg-white/5 hover:bg-white/10 border border-white/10 text-xs">Creators</Link>
            <a href={`${API_BASE}/docs`} target="_blank" rel="noopener noreferrer" className="btn-pill bg-transparent hover:bg-white/5 border border-white/10 text-white/70 text-xs">OpenAPI</a>
          </div>
        </div>
      </header>

      <section className="max-w-5xl mx-auto px-5 pt-12 pb-6">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-[#6cff32]/30 bg-[#6cff32]/5 px-3 py-1 mb-4">
            <span className="h-1.5 w-1.5 rounded-full bg-[#6cff32] pulse-ring" />
            <span className="text-[11px] font-medium text-[#6cff32] tracking-wide uppercase">Signed, retryable, auditable</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-3">
            <span className="gradient-text">Webhooks</span> for every FOUR-LIFE event.
          </h1>
          <p className="text-white/60 text-base md:text-lg leading-relaxed">
            Subscribe a URL, get HMAC-signed JSON on every tier transition and protection-level change. Delivery retries on failure (30s / 2m / 15m) and auto-disables after 10 consecutive failures. Same event shape powers Telegram + Discord alerts.
          </p>
        </div>
      </section>

      <section className="max-w-5xl mx-auto px-5 pb-10 space-y-6">
        <h2 className="text-xs uppercase tracking-wider text-white/40">Events</h2>
        {EVENTS.map(ev => (
          <div key={ev.name} className="space-y-2">
            <div className="flex items-baseline gap-3 flex-wrap">
              <code className="font-mono text-sm text-[#6cff32]">{ev.name}</code>
              <span className="text-white/50 text-sm">{ev.description}</span>
            </div>
            <CodeBlock label="example payload" code={ev.payload} />
          </div>
        ))}
      </section>

      <section className="max-w-5xl mx-auto px-5 pb-10 space-y-4">
        <h2 className="text-xs uppercase tracking-wider text-white/40">Subscribe</h2>
        <CodeBlock label="curl" code={SUBSCRIBE_CURL} />
        <div className="text-xs text-white/50">
          The <code className="font-mono text-white/70">secret</code> is returned once and never recoverable. Use it to verify the signature on every delivery. Requires an <code className="font-mono text-white/70">API_SECRET</code> bearer token; set one in the deployment env to lock writes.
        </div>
      </section>

      <section className="max-w-5xl mx-auto px-5 pb-10 space-y-4">
        <h2 className="text-xs uppercase tracking-wider text-white/40">Signature header</h2>
        <div className="card p-4 text-sm space-y-3">
          <div className="font-mono text-white/80">
            X-FourLife-Signature: <span className="text-[#6cff32]">t=</span>&lt;unix_ts&gt;<span className="text-white/40">,</span><span className="text-[#6cff32]">v1=</span>&lt;hex_hmac_sha256&gt;
          </div>
          <div className="text-white/60">
            The HMAC is computed as <code className="font-mono text-white/80">HMAC_SHA256(secret, f&quot;&#123;t&#125;.&#123;raw_body&#125;&quot;)</code>.
          </div>
          <div className="text-white/60">
            Reject deliveries where <code className="font-mono text-white/80">|now - t| &gt; 300</code> seconds to prevent replay attacks.
          </div>
        </div>
      </section>

      <section className="max-w-5xl mx-auto px-5 pb-10 space-y-4">
        <h2 className="text-xs uppercase tracking-wider text-white/40">Verify — Node.js</h2>
        <CodeBlock label="verify-webhook.js" code={VERIFY_JS} />
      </section>

      <section className="max-w-5xl mx-auto px-5 pb-10 space-y-4">
        <h2 className="text-xs uppercase tracking-wider text-white/40">Verify — Python</h2>
        <CodeBlock label="verify_webhook.py" code={VERIFY_PY} />
      </section>

      <section className="max-w-5xl mx-auto px-5 pb-10">
        <h2 className="text-xs uppercase tracking-wider text-white/40 mb-4">Delivery semantics</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { title: "Retry schedule", body: "First attempt immediate. Failures retry after 30s, then 2m, then 15m. 4 attempts total." },
            { title: "Dead-letter", body: "After 4 failed attempts the delivery is marked dead. The event is NOT re-enqueued on subsequent tier changes." },
            { title: "Auto-disable", body: "A subscription with 10 consecutive dead deliveries is auto-disabled. Re-subscribe to resume." },
            { title: "At-least-once", body: "Your handler may receive the same event_id twice if your 2xx response is slow. Dedupe on `id`." },
            { title: "Ordering", body: "Events are delivered in enqueue order per subscription but NOT guaranteed across subscriptions." },
            { title: "Size", body: "Payloads are typically < 2 KB. We do not inline images or heavy context — fetch via /api/token/{addr}/badge if needed." },
          ].map(b => (
            <div key={b.title} className="card p-4">
              <div className="text-sm font-semibold mb-1">{b.title}</div>
              <div className="text-xs text-white/60">{b.body}</div>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-white/5 py-10 px-5 text-center">
        <div className="max-w-3xl mx-auto space-y-3">
          <div className="text-sm text-white/60">
            All events and delivery records are inspectable via <code className="font-mono text-white/80">GET /api/webhooks/&#123;id&#125;/deliveries</code>.
          </div>
          <div className="flex items-center justify-center gap-3 flex-wrap text-xs">
            <Link href="/radar" className="btn-pill bg-[#6cff32] hover:bg-[#6cff32]/90 text-black">Browse the Radar →</Link>
            <a href={`${API_BASE}/docs#/webhooks`} target="_blank" rel="noopener noreferrer" className="btn-pill bg-white/5 hover:bg-white/10 border border-white/10">Full OpenAPI</a>
            <a href="https://github.com/Ridwannurudeen/four-life" target="_blank" rel="noopener noreferrer" className="btn-pill bg-transparent hover:bg-white/5 border border-white/10 text-white/70">GitHub</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
