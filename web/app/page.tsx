"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { HeroRadar, PartnerMarquee, useReveal } from "./_components";

const API = (process.env.NEXT_PUBLIC_API_URL || "https://four-life.gudman.xyz").replace(/\/$/, "");
const GITHUB = "https://github.com/Ridwannurudeen/four-life";
const NPM_PKG = "@gudman/four-life-sdk";
const PYPI_PKG = "four-life";

// ── Types ─────────────────────────────────────────────────────────────

type Tier = "graduated" | "graduation_watch" | "healthy" | "at_risk" | "observed";

interface RadarEntry {
  token_address: string;
  name: string;
  symbol: string;
  quote_asset: string;
  curve_progress: number;
  increase_pct: number;
  confidence_score: "high" | "medium" | "low";
  graduation_probability: number;
  health_score: number;
}

interface LiveMetrics {
  radarCount: number;
  creatorsCount: number;
  historyTokensCount: number;
  graduations: number;
  radarSample: RadarEntry[];
}

// ── Live data hook ────────────────────────────────────────────────────

function useLiveMetrics() {
  const [m, setM] = useState<LiveMetrics>({
    radarCount: 0,
    creatorsCount: 0,
    historyTokensCount: 0,
    graduations: 0,
    radarSample: [],
  });

  const fetchAll = useCallback(async () => {
    try {
      const [radar, creators, hist] = await Promise.all([
        fetch(`${API}/api/graduation-radar?limit=60&min_confidence=low`).then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`${API}/api/creators/leaderboard?limit=500`).then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`${API}/api/history/tokens?limit=500`).then(r => r.ok ? r.json() : null).catch(() => null),
      ]);

      const radarList: RadarEntry[] = (radar?.radar as RadarEntry[] | undefined) || [];
      const gradCount = ((creators?.creators as { graduations: number }[] | undefined) || [])
        .reduce((s, c) => s + (c.graduations || 0), 0);

      setM({
        radarCount: radarList.length,
        creatorsCount: creators?.total_creators ?? 0,
        historyTokensCount: hist?.count ?? 0,
        graduations: gradCount,
        radarSample: radarList.slice(0, 14),
      });
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    const initial = setTimeout(fetchAll, 0);
    const id = setInterval(fetchAll, 30_000);
    return () => {
      clearTimeout(initial);
      clearInterval(id);
    };
  }, [fetchAll]);

  return m;
}

// ── Helpers ───────────────────────────────────────────────────────────

function deriveTier(e: RadarEntry): Tier {
  if (e.curve_progress >= 100) return "graduated";
  if (e.curve_progress >= 70 && e.confidence_score === "high" && e.increase_pct >= 0) return "graduation_watch";
  if (e.increase_pct <= -50) return "at_risk";
  if (e.curve_progress >= 25) return "healthy";
  return "observed";
}

const TIER_COLOR: Record<Tier, { bg: string; text: string; border: string; label: string }> = {
  graduated: { bg: "bg-purple-500/10", text: "text-purple-300", border: "border-purple-500/40", label: "Graduated" },
  graduation_watch: { bg: "bg-[#00d4ff]/10", text: "text-[#00d4ff]", border: "border-[#00d4ff]/40", label: "Graduation Watch" },
  healthy: { bg: "bg-[#6cff32]/10", text: "text-[#6cff32]", border: "border-[#6cff32]/40", label: "Healthy" },
  at_risk: { bg: "bg-[#ff494a]/10", text: "text-[#ff494a]", border: "border-[#ff494a]/40", label: "At Risk" },
  observed: { bg: "bg-[#ffd641]/10", text: "text-[#ffd641]", border: "border-[#ffd641]/40", label: "Observed" },
};

function shortAddr(a: string) {
  if (!a || a.length < 10) return a;
  return a.slice(0, 6) + "…" + a.slice(-4);
}

function formatCompact(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return (n / 1000).toFixed(n < 10_000 ? 1 : 0) + "K";
  return (n / 1_000_000).toFixed(1) + "M";
}

// ── Code examples ─────────────────────────────────────────────────────

const CODE_PYTHON = `from four_life import FourLife

fl = FourLife()
badge = fl.get_badge("0x72b0a042e19871c046c1bd31e5b5ad3770c94444")
print(badge["badge"]["tier"])         # "healthy"
print(badge["badge"]["why"][0])       # full rule trace`;

const CODE_TS = `import { FourLife } from "@gudman/four-life-sdk";

const fl = new FourLife();
const badge = await fl.getBadge("0x72b0a042e19871c046c1bd31e5b5ad3770c94444");
console.log(badge.badge.tier);        // "healthy"

// Watch for tier changes — one-liner
const unwatch = fl.watchToken("0xabc...", (b) => console.log(b.badge.tier));`;

const CODE_CURL = `curl -sS https://four-life.gudman.xyz/api/token/\\
0x72b0a042e19871c046c1bd31e5b5ad3770c94444/badge | jq

# Subscribe to tier-changed webhooks
curl -X POST https://four-life.gudman.xyz/api/webhooks \\
  -H "Authorization: Bearer $API_SECRET" \\
  -H "Content-Type: application/json" \\
  -d '{"url":"https://you.example/hook","events":["badge.tier_changed"]}'`;

const CODE_WEBHOOK = `from four_life import verify_webhook_signature

def handle(request):
    body = request.get_data(as_text=True)
    sig  = request.headers["X-FourLife-Signature"]
    if not verify_webhook_signature(secret=MY_SECRET, body=body, signature_header=sig):
        return ("bad signature", 401)
    event = request.get_json()   # "badge.tier_changed" or "protection.level_changed"
    react(event)
    return ("ok", 200)`;

// ── Small UI atoms ────────────────────────────────────────────────────

function Copyable({ text, className = "" }: { text: string; className?: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard?.writeText(text); setOk(true); setTimeout(() => setOk(false), 1400); }}
      className={`relative w-full text-left group ${className}`}
    >
      <pre className="code-block p-4 pr-20 text-xs overflow-x-auto whitespace-pre-wrap break-all">{text}</pre>
      <span className="absolute top-3 right-3 text-[10px] px-2.5 py-1 rounded-full border border-white/10 bg-white/5 text-white/70 font-semibold uppercase tracking-wider group-hover:bg-white/10">
        {ok ? "Copied" : "Copy"}
      </span>
    </button>
  );
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="stat-card">
      <div className="text-[10px] uppercase tracking-[0.15em] text-white/40">{label}</div>
      <div className="text-3xl md:text-4xl font-bold tabular mt-1 gradient-text-anim">{value}</div>
      {hint && <div className="text-[11px] text-white/40 mt-1">{hint}</div>}
    </div>
  );
}

// ── Nav ───────────────────────────────────────────────────────────────

function Nav() {
  return (
    <header className="border-b border-white/5 sticky top-0 z-40 bg-[#0f1012]/80 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-5 py-3.5 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5 group">
          <span className="h-9 w-9 rounded-xl bg-gradient-to-br from-[#6cff32] to-[#00d4ff] flex items-center justify-center font-bold text-black text-lg shadow-[0_0_25px_rgba(108,255,50,0.35)] transition-transform group-hover:scale-110">4</span>
          <div>
            <div className="text-sm font-bold tracking-tight">FOUR-LIFE</div>
            <div className="text-[10px] text-white/40 uppercase tracking-[0.15em] -mt-0.5">Certified</div>
          </div>
        </Link>
        <nav className="hidden md:flex items-center gap-1 text-sm">
          <Link href="/radar" className="px-3 py-1.5 rounded-md text-white/70 hover:text-white hover:bg-white/5 transition-colors">Radar</Link>
          <Link href="/creators" className="px-3 py-1.5 rounded-md text-white/70 hover:text-white hover:bg-white/5 transition-colors">Creators</Link>
          <Link href="/webhooks" className="px-3 py-1.5 rounded-md text-white/70 hover:text-white hover:bg-white/5 transition-colors">Webhooks</Link>
          <Link href="/embed" className="px-3 py-1.5 rounded-md text-white/70 hover:text-white hover:bg-white/5 transition-colors">Embed</Link>
          <a href={`${API}/docs`} target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 rounded-md text-white/70 hover:text-white hover:bg-white/5 transition-colors">API Docs</a>
        </nav>
        <div className="flex items-center gap-2">
          <a href={GITHUB} target="_blank" rel="noopener noreferrer" className="btn-ghost hidden sm:inline-flex text-xs" style={{ padding: "8px 16px", fontSize: 13 }}>GitHub</a>
          <Link href="/radar" className="btn-primary text-xs" style={{ padding: "8px 18px", fontSize: 13 }}>Open Radar →</Link>
        </div>
      </div>
    </header>
  );
}

// ── Live ticker (tier-changed feed) ──────────────────────────────────

function LiveTicker({ sample }: { sample: RadarEntry[] }) {
  if (sample.length === 0) return null;
  // Duplicate the list for seamless loop
  const doubled = [...sample, ...sample];
  return (
    <div className="ticker overflow-hidden border-y border-white/5 bg-black/30 py-3">
      <div className="ticker-track">
        {doubled.map((e, i) => {
          const tier = deriveTier(e);
          const c = TIER_COLOR[tier];
          return (
            <Link
              key={`${e.token_address}-${i}`}
              href={`/radar?token=${e.token_address}`}
              className="flex items-center gap-2 text-xs whitespace-nowrap hover:opacity-80 transition-opacity"
            >
              <span className={`inline-flex items-center h-5 px-2 rounded-full border text-[10px] font-semibold uppercase tracking-wider ${c.bg} ${c.text} ${c.border}`}>
                {c.label}
              </span>
              <span className="font-semibold text-white">{e.symbol || "—"}</span>
              <span className="text-white/35 font-mono">{shortAddr(e.token_address)}</span>
              <span className="text-white/40 tabular">{e.curve_progress.toFixed(0)}% curve</span>
              <span className="text-white/20">·</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

// ── Hero ──────────────────────────────────────────────────────────────

function Hero({ metrics }: { metrics: LiveMetrics }) {
  return (
    <section className="relative overflow-hidden">
      <div className="hero-glow" />
      <div className="noise" />
      <div className="relative max-w-7xl mx-auto px-5 pt-14 md:pt-24 pb-12 md:pb-20">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 md:gap-14 items-center">
          <div className="lg:col-span-7">
            <div className="eyebrow mb-6">
              <span className="h-1.5 w-1.5 rounded-full bg-[#6cff32] pulse-ring" />
              Live on BNB Chain · {metrics.radarCount > 0 ? `${metrics.radarCount} tokens graded right now` : "connecting..."}
            </div>

            <h1 className="display display-xl mb-7">
              The{" "}
              <span className="gradient-text-anim">trust layer</span>
              <br className="hidden md:block" />
              Four.meme is missing.
            </h1>

            <p className="text-white/70 text-lg md:text-2xl leading-[1.45] max-w-2xl mb-4 font-light">
              98.6% of meme tokens die within 72 hours. FOUR-LIFE grades every live launch, protects the ones that matter, and fires signed webhooks the moment trust shifts.
            </p>
            <p className="text-white/40 text-sm md:text-base mb-10 max-w-2xl">
              Deterministic badges. Protection mode. Signed webhooks. SDKs. All free. All open-source.
            </p>

            <div className="flex flex-wrap gap-3 mb-5">
              <Link href="/radar" className="btn-primary">Open the Radar →</Link>
              <a href="#install" className="btn-ghost">Install the SDK</a>
              <a href={GITHUB} target="_blank" rel="noopener noreferrer" className="btn-ghost">View on GitHub</a>
            </div>

            <div className="text-[11px] text-white/30 font-mono mt-4 tabular">
              <span className="text-white/50">$</span> pip install four-life{" "}
              <span className="text-white/20">·</span>{" "}
              <span className="text-white/50">$</span> npm install {NPM_PKG}
            </div>
          </div>

          <div className="lg:col-span-5">
            <HeroRadar entries={metrics.radarSample} />
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Live metrics band ─────────────────────────────────────────────────

function LiveMetricsBand({ metrics }: { metrics: LiveMetrics }) {
  return (
    <section className="max-w-7xl mx-auto px-5 pb-16 md:pb-24">
      <div className="flex items-end justify-between mb-6">
        <div>
          <div className="eyebrow mb-3">
            <span className="h-1.5 w-1.5 rounded-full bg-[#6cff32] pulse-ring" />
            Real-time · auto-refresh 30s
          </div>
          <h2 className="display display-md">The network, right now.</h2>
        </div>
        <Link href="/radar" className="hidden md:inline-flex text-sm text-[#6cff32] hover:underline">Browse the radar →</Link>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          label="Tokens graded"
          value={formatCompact(metrics.radarCount)}
          hint="on the live radar"
        />
        <StatCard
          label="Creators ranked"
          value={formatCompact(metrics.creatorsCount)}
          hint="deterministic trust tier"
        />
        <StatCard
          label="With history"
          value={formatCompact(metrics.historyTokensCount)}
          hint="snapshots persisted"
        />
        <StatCard
          label="Graduations"
          value={formatCompact(metrics.graduations)}
          hint="on-chain attestations"
        />
      </div>
    </section>
  );
}

// ── Primitives — 3 big feature cards ─────────────────────────────────

function Primitives() {
  return (
    <section className="max-w-7xl mx-auto px-5 pb-16 md:pb-24">
      <div className="mb-10 max-w-3xl">
        <div className="eyebrow mb-4">Primitives</div>
        <h2 className="display display-lg mb-3">
          Three layers. <span className="gradient-text">One trust model.</span>
        </h2>
        <p className="text-white/55 text-base md:text-lg">
          Every primitive is computed from raw on-chain metrics with a full <code className="font-mono text-[#6cff32] bg-white/5 px-1.5 py-0.5 rounded">why[]</code> trace. No LLM in the trust path. Anyone can reproduce any grade from the raw data.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* 1. Badge */}
        <div className="card p-6 md:p-7 group relative overflow-hidden">
          <div className="absolute top-0 right-0 h-32 w-32 bg-[#6cff32]/8 rounded-full blur-3xl -translate-y-12 translate-x-12" />
          <div className="relative">
            <div className="flex items-center gap-2 mb-4">
              <span className="h-8 w-8 rounded-lg bg-[#6cff32]/10 border border-[#6cff32]/30 flex items-center justify-center text-[#6cff32] font-bold">1</span>
              <span className="text-[10px] uppercase tracking-[0.15em] text-white/40">Certified</span>
            </div>
            <h3 className="text-xl font-bold mb-2">Deterministic badge</h3>
            <p className="text-sm text-white/55 mb-5 leading-relaxed">
              Five tiers — graduated, watch, healthy, at_risk, observed — computed from on-chain metrics with a full rule trace. Pair-aware graduation targets sourced live from Four.meme.
            </p>
            <div className="space-y-1.5 text-xs text-white/60 mb-5">
              {["0 LLM calls in trust path", "Reproducible from raw data", "Pair-aware graduation targets"].map(b => (
                <div key={b} className="flex items-center gap-2">
                  <span className="text-[#6cff32]">✓</span><span>{b}</span>
                </div>
              ))}
            </div>
            <Link href="/radar" className="inline-flex items-center gap-1 text-sm text-[#6cff32] hover:gap-2 transition-all">Explore →</Link>
          </div>
        </div>

        {/* 2. Protection */}
        <div className="card p-6 md:p-7 group relative overflow-hidden">
          <div className="absolute top-0 right-0 h-32 w-32 bg-[#ff494a]/8 rounded-full blur-3xl -translate-y-12 translate-x-12" />
          <div className="relative">
            <div className="flex items-center gap-2 mb-4">
              <span className="h-8 w-8 rounded-lg bg-[#ff494a]/10 border border-[#ff494a]/30 flex items-center justify-center text-[#ff494a] font-bold">2</span>
              <span className="text-[10px] uppercase tracking-[0.15em] text-white/40">Protection Mode</span>
            </div>
            <h3 className="text-xl font-bold mb-2">Autonomous defender</h3>
            <p className="text-sm text-white/55 mb-5 leading-relaxed">
              Declare defensive thresholds per token. On critical verdict, FOUR-LIFE halts content posts, fires a webhook, and emits a short-hedge signal — all deterministically.
            </p>
            <div className="space-y-1.5 text-xs text-white/60 mb-5">
              {["Whale / contract / sell-pressure rules", "Auto-halt on critical breach", "Level-change webhooks"].map(b => (
                <div key={b} className="flex items-center gap-2">
                  <span className="text-[#ff494a]">◆</span><span>{b}</span>
                </div>
              ))}
            </div>
            <a href={`${API}/api/protection`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm text-[#ff494a] hover:gap-2 transition-all">View policies →</a>
          </div>
        </div>

        {/* 3. Webhooks + SDK */}
        <div className="card p-6 md:p-7 group relative overflow-hidden">
          <div className="absolute top-0 right-0 h-32 w-32 bg-[#00d4ff]/8 rounded-full blur-3xl -translate-y-12 translate-x-12" />
          <div className="relative">
            <div className="flex items-center gap-2 mb-4">
              <span className="h-8 w-8 rounded-lg bg-[#00d4ff]/10 border border-[#00d4ff]/30 flex items-center justify-center text-[#00d4ff] font-bold">3</span>
              <span className="text-[10px] uppercase tracking-[0.15em] text-white/40">Webhooks + SDKs</span>
            </div>
            <h3 className="text-xl font-bold mb-2">Integration surface</h3>
            <p className="text-sm text-white/55 mb-5 leading-relaxed">
              Signed HMAC webhooks for every tier and protection transition. Python + TypeScript SDKs. Telegram + Discord fan-out. Build on top in minutes.
            </p>
            <div className="space-y-1.5 text-xs text-white/60 mb-5">
              {["HMAC-SHA256 signed payloads", "Retry + auto-disable policies", "Sync + async clients"].map(b => (
                <div key={b} className="flex items-center gap-2">
                  <span className="text-[#00d4ff]">▸</span><span>{b}</span>
                </div>
              ))}
            </div>
            <Link href="/webhooks" className="inline-flex items-center gap-1 text-sm text-[#00d4ff] hover:gap-2 transition-all">Read the docs →</Link>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── How it works — 3 steps horizontal ────────────────────────────────

function HowItWorks() {
  const steps = [
    {
      n: "01",
      title: "Compute",
      body: "Every token grade is computed from raw on-chain metrics — holders, whale concentration, buy/sell ratio, curve progress, contract risk — against deterministic thresholds. No LLM.",
      color: "text-[#6cff32]",
    },
    {
      n: "02",
      title: "Persist",
      body: "Every grade is written to a time-series store. Tier changes + keepalive snapshots. Query the history, compute diffs, export NDJSON for backfills.",
      color: "text-[#00d4ff]",
    },
    {
      n: "03",
      title: "Dispatch",
      body: "On every transition, fire signed HMAC webhooks and fan out to Telegram + Discord. Subscribers verify, react, and halt trading in real time.",
      color: "text-[#ffd641]",
    },
  ];

  return (
    <section className="relative border-y border-white/5 bg-black/20">
      <div className="max-w-7xl mx-auto px-5 py-16 md:py-24">
        <div className="mb-12 max-w-3xl">
          <div className="eyebrow mb-4">How it works</div>
          <h2 className="display display-lg">
            Compute. Persist. <span className="gradient-text">Dispatch.</span>
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-white/5 rounded-xl overflow-hidden">
          {steps.map((s) => (
            <div key={s.n} className="bg-[#0f1012] p-6 md:p-8 relative">
              <div className={`text-5xl md:text-6xl font-bold tabular leading-none mb-4 ${s.color}`}>{s.n}</div>
              <h3 className="text-lg md:text-xl font-bold mb-2">{s.title}</h3>
              <p className="text-sm text-white/55 leading-relaxed">{s.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Developer section with tabbed code ───────────────────────────────

const TABS: { id: string; label: string; code: string; lang: string }[] = [
  { id: "python", label: "Python", code: CODE_PYTHON, lang: "python" },
  { id: "ts", label: "TypeScript", code: CODE_TS, lang: "typescript" },
  { id: "curl", label: "curl", code: CODE_CURL, lang: "bash" },
  { id: "webhook", label: "Verify webhook", code: CODE_WEBHOOK, lang: "python" },
];

function Developers() {
  const [tab, setTab] = useState("python");
  const active = useMemo(() => TABS.find(t => t.id === tab) || TABS[0], [tab]);

  return (
    <section id="install" className="max-w-7xl mx-auto px-5 py-16 md:py-24">
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-10 items-start">
        <div className="lg:col-span-2">
          <div className="eyebrow mb-4">Developers</div>
          <h2 className="display display-lg mb-4">
            One import. <span className="gradient-text">Live data.</span>
          </h2>
          <p className="text-white/55 text-base md:text-lg leading-relaxed mb-6">
            Parallel SDKs for Python and TypeScript, covering every endpoint. Sync or async. Zero config. Write custom agents, alert bots, or treasury guards in minutes.
          </p>
          <div className="space-y-2 mb-6">
            {[
              { k: "pip install four-life", v: "PyPI" },
              { k: `npm install ${NPM_PKG}`, v: "npm" },
              { k: `curl ${API}/api/token/<addr>/badge`, v: "HTTP" },
            ].map((x) => (
              <div key={x.k} className="flex items-center justify-between gap-3 rounded-lg bg-[#0b0c0e] border border-white/5 px-4 py-2.5">
                <code className="text-xs md:text-sm font-mono text-[#a7f7b5] truncate">{x.k}</code>
                <span className="text-[10px] uppercase tracking-wider text-white/30">{x.v}</span>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            <a href={`${API}/docs`} target="_blank" rel="noopener noreferrer" className="btn-ghost" style={{ fontSize: 12, padding: "8px 16px" }}>OpenAPI spec →</a>
            <Link href="/webhooks" className="btn-ghost" style={{ fontSize: 12, padding: "8px 16px" }}>Webhooks reference →</Link>
          </div>
        </div>

        <div className="lg:col-span-3">
          <div className="card overflow-hidden">
            <div className="flex items-center gap-2 border-b border-white/5 px-4 py-3 bg-black/30">
              <div className="flex gap-1.5 mr-2">
                <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f56]" />
                <span className="h-2.5 w-2.5 rounded-full bg-[#ffbd2e]" />
                <span className="h-2.5 w-2.5 rounded-full bg-[#27c93f]" />
              </div>
              <div className="flex items-center gap-1 ml-2 overflow-x-auto">
                {TABS.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setTab(t.id)}
                    className={`tab ${tab === t.id ? "active" : ""}`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
              <div className="flex-1" />
              <span className="text-[10px] uppercase tracking-wider text-white/30 hidden md:inline">{active.lang}</span>
            </div>
            <Copyable text={active.code} className="" />
          </div>
          <div className="text-[11px] text-white/30 mt-3 text-center">
            Every SDK method returns typed objects. Webhook signature verification is built in.
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Who uses it — 4 audience cards ───────────────────────────────────

function WhoUses() {
  const cards = [
    {
      tag: "Traders",
      color: "text-[#6cff32]",
      title: "Browse the Radar",
      body: "Every live Four.meme token, ranked deterministically. Filter by confidence, sort by graduation odds. Click for the full rule trace.",
      href: "/radar",
      cta: "Open Radar →",
    },
    {
      tag: "Agents",
      color: "text-[#00d4ff]",
      title: "Subscribe to webhooks",
      body: "React to tier changes and protection transitions in real time. HMAC-signed, retried, verified. Built for autonomous trading bots.",
      href: "/webhooks",
      cta: "Webhooks docs →",
    },
    {
      tag: "Creators",
      color: "text-[#ffd641]",
      title: "Embed the badge",
      body: "One line of HTML drops a live Certified badge on your Discord, site, or bio. Auto-refresh. No build step. No tracking.",
      href: "/embed",
      cta: "See the widget →",
    },
    {
      tag: "Platforms",
      color: "text-[#a770ef]",
      title: "Drop in on token pages",
      body: "The badge belongs next to every Four.meme token address. A composable trust primitive — embed the widget, consume the API, fork the SDKs.",
      href: GITHUB,
      cta: "Fork it →",
      external: true,
    },
  ];

  return (
    <section className="max-w-7xl mx-auto px-5 py-16 md:py-24">
      <div className="mb-10 max-w-3xl">
        <div className="eyebrow mb-4">Who it&apos;s for</div>
        <h2 className="display display-lg">
          Four roles. <span className="gradient-text">One primitive.</span>
        </h2>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {cards.map((c) => {
          const body = (
            <>
              <div className={`text-[10px] uppercase tracking-[0.15em] mb-3 ${c.color}`}>{c.tag}</div>
              <h3 className="text-base font-bold mb-2">{c.title}</h3>
              <p className="text-xs text-white/55 mb-4 leading-relaxed">{c.body}</p>
              <div className={`inline-flex items-center gap-1 text-xs font-semibold ${c.color} group-hover:gap-2 transition-all`}>{c.cta}</div>
            </>
          );
          return c.external ? (
            <a key={c.tag} href={c.href} target="_blank" rel="noopener noreferrer" className="card p-5 group flex flex-col">
              {body}
            </a>
          ) : (
            <Link key={c.tag} href={c.href} className="card p-5 group flex flex-col">
              {body}
            </Link>
          );
        })}
      </div>
    </section>
  );
}

// ── Built on — partner strip ─────────────────────────────────────────

function BuiltOn() {
  const partners = [
    { t: "BNB Chain", body: "Runs on BSC mainnet. Every graduation attestation is on-chain.", accent: "text-[#f3ba2f]" },
    { t: "Four.meme", body: "Pair-aware graduation targets sourced live from the platform config.", accent: "text-[#6cff32]" },
    { t: "DGrid", body: "Every LLM call routes through DGrid with 3-tier fallback (DGrid → Anthropic → OpenAI).", accent: "text-[#00d4ff]" },
    { t: "MYX V2", body: "Perp signals for hedging meme-token exposure through lifecycle phases.", accent: "text-[#a770ef]" },
    { t: "ERC-8004 / BRC-8004", body: "FOUR-LIFE is a registered agent on BSC. Reputation attestations per graduation.", accent: "text-[#ffd641]" },
    { t: "Unibase", body: "Agent memory synced across sessions. Every launch outcome improves the next.", accent: "text-[#ff494a]" },
  ];
  return (
    <section className="border-y border-white/5 bg-black/20">
      <div className="max-w-7xl mx-auto px-5 py-16 md:py-20">
        <div className="mb-10 max-w-3xl">
          <div className="eyebrow mb-4">Built on</div>
          <h2 className="display display-md">The Four.meme AI Sprint stack.</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {partners.map(p => (
            <div key={p.t} className="card p-5">
              <div className={`text-sm font-bold mb-1.5 ${p.accent}`}>{p.t}</div>
              <div className="text-xs text-white/55 leading-relaxed">{p.body}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Final CTA ─────────────────────────────────────────────────────────

function FinalCTA() {
  return (
    <section className="relative overflow-hidden">
      <div className="hero-glow" />
      <div className="relative max-w-4xl mx-auto px-5 py-20 md:py-28 text-center">
        <div className="eyebrow mb-5 mx-auto">Ship it</div>
        <h2 className="display display-xl mb-5">
          <span className="gradient-text-anim">Four.meme should ship this.</span>
        </h2>
        <p className="text-white/55 text-base md:text-xl max-w-2xl mx-auto mb-8">
          Drop-in platform primitive. Creator widget. Trader radar. Autonomous defender. Zero trust cost. Open source.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link href="/radar" className="btn-primary">Open the Radar →</Link>
          <a href={GITHUB} target="_blank" rel="noopener noreferrer" className="btn-ghost">Read the code</a>
          <a href={`${API}/docs`} target="_blank" rel="noopener noreferrer" className="btn-ghost">Explore the API</a>
        </div>
      </div>
    </section>
  );
}

// ── Footer ────────────────────────────────────────────────────────────

function Footer() {
  const cols: { title: string; links: { label: string; href: string; external?: boolean }[] }[] = [
    {
      title: "Product",
      links: [
        { label: "Radar", href: "/radar" },
        { label: "Creators", href: "/creators" },
        { label: "Webhooks", href: "/webhooks" },
        { label: "Embed widget", href: "/embed" },
        { label: "Dashboard", href: "/dashboard" },
      ],
    },
    {
      title: "Developers",
      links: [
        { label: `Python SDK — ${PYPI_PKG}`, href: "https://pypi.org/project/four-life/", external: true },
        { label: `TypeScript SDK — ${NPM_PKG}`, href: `https://www.npmjs.com/package/${NPM_PKG}`, external: true },
        { label: "OpenAPI docs", href: `${API}/docs`, external: true },
        { label: "GitHub", href: GITHUB, external: true },
      ],
    },
    {
      title: "On-chain",
      links: [
        { label: "ERC-8004 agent card", href: `${API}/.well-known/agent-registration.json`, external: true },
        { label: "Identity + attestations", href: `${API}/api/identity`, external: true },
        { label: "DGrid stats", href: `${API}/api/dgrid/stats`, external: true },
        { label: "Platform cohorts", href: `${API}/api/platform/cohorts`, external: true },
      ],
    },
    {
      title: "Status",
      links: [
        { label: "Live health", href: `${API}/api/status`, external: true },
        { label: "Notifications status", href: `${API}/api/notifications/status`, external: true },
        { label: "Radar bot", href: `${API}/api/radar-bot/status`, external: true },
      ],
    },
  ];

  return (
    <footer className="border-t border-white/5">
      <div className="max-w-7xl mx-auto px-5 pt-16 pb-10">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-10 mb-10">
          <div className="col-span-2">
            <Link href="/" className="flex items-center gap-2.5 mb-4">
              <span className="h-9 w-9 rounded-xl bg-gradient-to-br from-[#6cff32] to-[#00d4ff] flex items-center justify-center font-bold text-black text-lg">4</span>
              <div>
                <div className="text-sm font-bold">FOUR-LIFE</div>
                <div className="text-[10px] text-white/40 uppercase tracking-[0.15em] -mt-0.5">Certified</div>
              </div>
            </Link>
            <p className="text-xs text-white/50 leading-relaxed max-w-sm mb-4">
              The trust, protection, and dispatch layer for Four.meme launches on BNB Chain. Deterministic by design.
            </p>
            <div className="flex items-center gap-2 text-[10px] text-white/40">
              <span className="h-1.5 w-1.5 rounded-full bg-[#6cff32] pulse-ring" />
              All systems operational
            </div>
          </div>
          {cols.map(col => (
            <div key={col.title}>
              <div className="text-[10px] uppercase tracking-[0.15em] text-white/40 mb-3">{col.title}</div>
              <ul className="space-y-2">
                {col.links.map(l => (
                  <li key={l.label}>
                    {l.external ? (
                      <a href={l.href} target="_blank" rel="noopener noreferrer" className="text-xs text-white/60 hover:text-white transition-colors">{l.label}</a>
                    ) : (
                      <Link href={l.href} className="text-xs text-white/60 hover:text-white transition-colors">{l.label}</Link>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="divider-fine mb-6" />

        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 text-[11px] text-white/35">
          <div>© 2026 FOUR-LIFE — Built for the Four.meme AI Sprint on BNB Chain. MIT.</div>
          <div className="flex items-center gap-4">
            <span>Model: v1.1.0</span>
            <span className="text-white/20">·</span>
            <a href={GITHUB} target="_blank" rel="noopener noreferrer" className="hover:text-white">Source on GitHub</a>
          </div>
        </div>
      </div>
    </footer>
  );
}

// ── Page ──────────────────────────────────────────────────────────────

function Reveal({ children, className = "", delay = 0 }: { children: React.ReactNode; className?: string; delay?: 0 | 1 | 2 | 3 | 4 }) {
  const ref = useReveal<HTMLDivElement>();
  const delayClass = delay > 0 ? ` reveal-delay-${delay}` : "";
  return (
    <div ref={ref} className={`reveal${delayClass} ${className}`}>
      {children}
    </div>
  );
}

export default function Landing() {
  const metrics = useLiveMetrics();

  return (
    <div className="min-h-screen bg-[#0f1012] text-white bg-grid">
      <Nav />
      <Hero metrics={metrics} />

      {/* Partner logo marquee — "built on / integrates with" */}
      <Reveal className="border-y border-white/5 bg-black/30">
        <div className="max-w-7xl mx-auto">
          <div className="px-5 pt-5 pb-1 flex items-center justify-between">
            <div className="text-[10px] uppercase tracking-[0.18em] text-white/35">Built on · Integrates with</div>
            <div className="text-[10px] uppercase tracking-[0.15em] text-white/25 hidden md:block tabular">Mainnet live</div>
          </div>
          <PartnerMarquee />
        </div>
      </Reveal>

      <LiveTicker sample={metrics.radarSample} />
      <Reveal><LiveMetricsBand metrics={metrics} /></Reveal>
      <Reveal><Primitives /></Reveal>
      <Reveal><HowItWorks /></Reveal>
      <Reveal><Developers /></Reveal>
      <Reveal><WhoUses /></Reveal>
      <Reveal><BuiltOn /></Reveal>
      <Reveal><FinalCTA /></Reveal>
      <Footer />
    </div>
  );
}
