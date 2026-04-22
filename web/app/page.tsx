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
  // Server-computed — the UI never re-derives trust labels. For tokens under
  // live on-chain monitoring this is "certified"; for public-ranking-only
  // tokens this is "radar_estimate" (heuristic, NOT on-chain measured).
  badge_tier: Tier;
  tier_source: "certified" | "radar_estimate";
}

interface LiveMetrics {
  // Total tokens the backend graded on this scan (before limit truncation).
  // Sourced from radar.total_scanned, not radar.length, so the stat doesn't
  // drift when the ?limit= cap changes.
  radarCount: number;
  // Live-monitored tokens — these receive Certified badges (full on-chain
  // rule trace). Separate from radarCount so the headline can show both
  // the breadth of coverage AND the depth of certified grading.
  activeTokens: number;
  creatorsCount: number;
  historyTokensCount: number;
  graduations: number;
  radarSample: RadarEntry[];
}

// ── Live data hook ────────────────────────────────────────────────────

function useLiveMetrics() {
  const [m, setM] = useState<LiveMetrics>({
    radarCount: 0,
    activeTokens: 0,
    creatorsCount: 0,
    historyTokensCount: 0,
    graduations: 0,
    radarSample: [],
  });

  const fetchAll = useCallback(async () => {
    try {
      const [radar, creators, hist, status] = await Promise.all([
        fetch(`${API}/api/graduation-radar?limit=60&min_confidence=low`).then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`${API}/api/creators/leaderboard?limit=500`).then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`${API}/api/history/tokens?limit=500`).then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`${API}/api/status`).then(r => r.ok ? r.json() : null).catch(() => null),
      ]);

      const radarList: RadarEntry[] = (radar?.radar as RadarEntry[] | undefined) || [];
      const gradCount = ((creators?.creators as { graduations: number }[] | undefined) || [])
        .reduce((s, c) => s + (c.graduations || 0), 0);

      setM({
        radarCount: typeof radar?.total_scanned === "number" ? radar.total_scanned : radarList.length,
        activeTokens: typeof status?.active_tokens === "number" ? status.active_tokens : 0,
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
// Trust labels are ALWAYS server-computed — the UI is a pure consumer.
// `tierOf` is a thin typed accessor with a safe default for rows the server
// hasn't graded yet. Do NOT reintroduce client-side derivation — that breaks
// the "Certified from raw on-chain data" guarantee because the frontend
// cannot distinguish radar_estimate inputs from certified ones.

function tierOf(e: RadarEntry): Tier {
  return (e.badge_tier as Tier) ?? "observed";
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
      <div className="text-3xl md:text-4xl font-bold tabular mt-1 text-white">{value}</div>
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
          <Link href="/evidence" className="px-3 py-1.5 rounded-md text-white/70 hover:text-white hover:bg-white/5 transition-colors">Evidence</Link>
          <Link href="/alerts" className="px-3 py-1.5 rounded-md text-white/70 hover:text-white hover:bg-white/5 transition-colors">Alerts</Link>
          <Link href="/activity" className="px-3 py-1.5 rounded-md text-white/70 hover:text-white hover:bg-white/5 transition-colors">Activity</Link>
          <Link href="/dgrid" className="px-3 py-1.5 rounded-md text-[#6cff32] hover:text-white hover:bg-white/5 transition-colors">DGrid</Link>
          <Link href="/myx" className="px-3 py-1.5 rounded-md text-[#ffd641] hover:text-white hover:bg-white/5 transition-colors">MYX</Link>
          <Link href="/metrics" className="px-3 py-1.5 rounded-md text-white/70 hover:text-white hover:bg-white/5 transition-colors">Metrics</Link>
          <a href={`${API}/docs`} target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 rounded-md text-white/70 hover:text-white hover:bg-white/5 transition-colors">API</a>
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
          const tier = tierOf(e);
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
              Live on BNB Chain · {metrics.radarCount > 0 ? `${metrics.radarCount} graded${metrics.activeTokens > 0 ? ` · ${metrics.activeTokens} Certified` : ""}` : "live grading"} · Agent ID 20
            </div>

            <h1 className="display display-xl mb-7">
              Only{" "}
              <span className="gradient-text-anim">1.34%</span>{" "}
              of Four.meme tokens graduate.
              <br className="hidden md:block" />
              FOUR-LIFE is Phase 4.
            </h1>

            <p className="text-white/70 text-lg md:text-2xl leading-[1.45] max-w-2xl mb-4 font-light">
              The autonomous lifecycle agent for Four.meme tokens on BNB Chain.
              Trust grades are deterministic (pure on-chain rules, zero LLM). Operational
              decisions go through an LLM gateway and every call is Merkle-committed on-chain.
            </p>
            <p className="text-white/50 text-sm md:text-base mb-8 max-w-2xl font-mono">
              1,573 DGrid LLM calls + 518 MYX decisions committed to on-chain Merkle roots · 6 attestation txs · $AUNT launched by the agent on Apr 20
            </p>

            <div className="flex flex-wrap gap-2 mb-7 text-[11px] font-mono">
              <a href="https://bscscan.com/tx/0xab323590f4aaa1013960ac77a89a215690ce731f72405c6b10f7bcd75973a636" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-purple-500/40 bg-purple-500/10 text-purple-300 hover:bg-purple-500/20">
                DGrid root · 0xab32…a636 ↗
              </a>
              <a href="https://bscscan.com/tx/0xeda29cc60bc8ca9bb3b3d8f78cf0200cd39cd50a3b80cbb0f411d25025232026" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-[#00d4ff]/40 bg-[#00d4ff]/10 text-[#00d4ff] hover:bg-[#00d4ff]/20">
                MYX root · 0xeda2…2026 ↗
              </a>
              <a href="https://bscscan.com/tx/0x80ff903ca947448ec50927b866067b67e5bdd69a667f9d0f1b3af8f0c74869d2" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-[#6cff32]/40 bg-[#6cff32]/10 text-[#6cff32] hover:bg-[#6cff32]/20">
                $AUNT launch · 0x80ff…69d2 ↗
              </a>
            </div>

            <div className="flex flex-wrap gap-3 mb-5">
              <Link href="/proof" className="btn-primary">See the proof →</Link>
              <Link href="/radar" className="btn-ghost">Open the Radar</Link>
              <a href={GITHUB} target="_blank" rel="noopener noreferrer" className="btn-ghost">GitHub</a>
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

// ── Try it now ────────────────────────────────────────────────────────

interface BadgeWhy {
  rule: string;
  metric: string;
  value: string | number | boolean;
  threshold: string | number | boolean;
  operator: string;
  passed: boolean;
}

interface TryBadge {
  tier: Tier;
  label: string;
  description: string;
  why: BadgeWhy[];
}

interface TryBadgeResponse {
  token_address: string;
  badge: TryBadge;
  last_updated_at: number;
}

const TRY_TIER_STYLE: Record<Tier, { dot: string; text: string; bg: string; border: string }> = {
  graduated: { dot: "bg-purple-400", text: "text-purple-300", bg: "bg-purple-500/10", border: "border-purple-500/40" },
  graduation_watch: { dot: "bg-[#00d4ff]", text: "text-[#00d4ff]", bg: "bg-[#00d4ff]/10", border: "border-[#00d4ff]/40" },
  healthy: { dot: "bg-[#6cff32]", text: "text-[#6cff32]", bg: "bg-[#6cff32]/10", border: "border-[#6cff32]/40" },
  at_risk: { dot: "bg-[#ff494a]", text: "text-[#ff494a]", bg: "bg-[#ff494a]/10", border: "border-[#ff494a]/40" },
  observed: { dot: "bg-[#ffd641]", text: "text-[#ffd641]", bg: "bg-[#ffd641]/10", border: "border-[#ffd641]/40" },
};

const TRY_EXAMPLES = [
  { label: "Graduation Watch", addr: "0xd8c1c7b065ec8548093fe237157088b984dc4444" },
  { label: "Observed", addr: "0x8b630c0e672cac94f27cbe7bf2456e6d53694444" },
];

function TryNow() {
  const [input, setInput] = useState("");
  const [result, setResult] = useState<TryBadgeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const run = useCallback(async (addr: string) => {
    const cleaned = addr.trim().toLowerCase();
    if (!/^0x[a-f0-9]{40}$/.test(cleaned)) {
      setError("Paste a valid 0x… token address.");
      setResult(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/token/${cleaned}/badge`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.error || `Grade unavailable (HTTP ${res.status}). Try /api/agent/track to start watching.`);
        setResult(null);
      } else {
        setResult(await res.json());
      }
    } catch (e) {
      setError(String(e));
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const badge = result?.badge;
  const style = badge ? TRY_TIER_STYLE[badge.tier] : null;

  return (
    <section id="try" className="max-w-7xl mx-auto px-5 pb-16 md:pb-24">
      <div className="rounded-3xl border border-white/10 bg-white/[0.02] overflow-hidden">
        <div className="p-6 md:p-8 border-b border-white/5">
          <div className="eyebrow mb-3">Try it — no signup</div>
          <h2 className="display display-md mb-3">Grade any Four.meme token. Right now.</h2>
          <p className="text-white/55 text-sm md:text-base max-w-2xl">
            Paste an address below. Same endpoint the SDK hits. Same answer the agent uses. Zero LLM in the trust path —
            the rules that fired are shown below the grade.
          </p>
        </div>

        <div className="p-6 md:p-8 grid md:grid-cols-[1fr_auto] gap-3 items-stretch">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") run(input); }}
            placeholder="0x…token_address"
            className="bg-black/40 border border-white/10 rounded-xl px-4 py-3 font-mono text-sm focus:outline-none focus:border-[#6cff32]/50 min-w-0"
          />
          <button
            onClick={() => run(input)}
            disabled={loading || !input.trim()}
            className="btn-primary px-6 py-3 text-sm disabled:opacity-40 whitespace-nowrap"
          >
            {loading ? "grading…" : "Grade →"}
          </button>
        </div>

        <div className="px-6 md:px-8 pb-6 md:pb-8 flex items-center gap-3 flex-wrap text-xs text-white/40">
          <span>Or try an example:</span>
          {TRY_EXAMPLES.map((e) => (
            <button
              key={e.addr}
              onClick={() => { setInput(e.addr); run(e.addr); }}
              className="hover:text-white/80 underline font-mono"
            >
              {e.label}
            </button>
          ))}
        </div>

        {error && (
          <div className="px-6 md:px-8 pb-6 text-xs text-[#ff494a]">{error}</div>
        )}

        {badge && style && (
          <div className={`border-t ${style.border} ${style.bg} p-6 md:p-8`}>
            <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
                  <span className="eyebrow">FOUR-LIFE Certified</span>
                </div>
                <div className={`text-3xl md:text-4xl font-bold ${style.text}`}>{badge.label}</div>
                <p className="text-sm text-white/60 mt-2 max-w-xl">{badge.description}</p>
              </div>
              <Link
                href={`/launch/${result?.token_address}`}
                className="text-xs text-white/60 hover:text-white underline"
              >
                open full page →
              </Link>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="text-white/40 uppercase tracking-wider">
                    <th className="text-left py-2 pr-4">Rule</th>
                    <th className="text-left py-2 pr-4">Metric</th>
                    <th className="text-left py-2 pr-4">Value / Threshold</th>
                    <th className="text-left py-2">Fired</th>
                  </tr>
                </thead>
                <tbody>
                  {(badge.why || []).map((w, i) => (
                    <tr key={i} className="border-t border-white/5">
                      <td className="py-2 pr-4 font-mono">{w.rule}</td>
                      <td className="py-2 pr-4 text-white/60">{w.metric}</td>
                      <td className="py-2 pr-4 font-mono text-white/70">
                        {String(w.value)} {w.operator} {String(w.threshold)}
                      </td>
                      <td className="py-2">
                        <span className={w.passed ? "text-[#6cff32]" : "text-white/40"}>
                          {w.passed ? "✓" : "—"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
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
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatCard
          label="Tokens graded"
          value={formatCompact(metrics.radarCount)}
          hint="scanned this cycle"
        />
        <StatCard
          label="Certified · live"
          value={formatCompact(metrics.activeTokens)}
          hint="full rule-trace grade"
        />
        <StatCard
          label="Creators ranked"
          value={formatCompact(metrics.creatorsCount)}
          hint="deterministic trust tier"
        />
        <StatCard
          label="With history"
          value={formatCompact(metrics.historyTokensCount)}
          hint="tokens with snapshots"
        />
        <StatCard
          label="Graduations"
          value={formatCompact(metrics.graduations)}
          hint="bonding curves completed"
        />
      </div>
    </section>
  );
}

// ── Primitives — 3 big feature cards ─────────────────────────────────

function Primitives() {
  const cards = [
    {
      n: "1",
      eyebrow: "Certified",
      title: "Deterministic badge",
      body: "Five tiers — graduated, watch, healthy, at_risk, observed — computed from on-chain metrics with a full rule trace. Pair-aware graduation targets sourced live from Four.meme.",
      bullets: ["0 LLM calls in trust path", "Reproducible from raw data", "Pair-aware graduation targets"],
      href: "/radar",
      cta: "Explore",
    },
    {
      n: "2",
      eyebrow: "Protection Mode",
      title: "Autonomous defender",
      body: "Declare defensive thresholds per token. On critical verdict, FOUR-LIFE halts content posts, fires a webhook, and emits a short-hedge signal — all deterministically.",
      bullets: ["Whale / contract / sell-pressure rules", "Auto-halt on critical breach", "Level-change webhooks"],
      href: "/alerts",
      cta: "See firings",
    },
    {
      n: "3",
      eyebrow: "Webhooks + SDKs",
      title: "Integration surface",
      body: "Signed HMAC webhooks for every tier and protection transition. Python + TypeScript SDKs. Telegram + Discord fan-out. Build on top in minutes.",
      bullets: ["HMAC-SHA256 signed payloads", "Retry + auto-disable policies", "Sync + async clients"],
      href: "/webhooks",
      cta: "Read the docs",
    },
  ];
  return (
    <section className="max-w-7xl mx-auto px-5 pb-16 md:pb-24">
      <div className="mb-10 max-w-3xl">
        <div className="eyebrow mb-4">Primitives</div>
        <h2 className="display display-lg mb-3">Grade · Shield · Attest.</h2>
        <p className="text-white/55 text-base md:text-lg">
          Every trust grade is computed from raw on-chain metrics with a full{" "}
          <code className="font-mono text-white/80 bg-white/5 px-1.5 py-0.5 rounded">why[]</code> rule trace.
          No LLM is used to decide if a token is safe — anyone can reproduce any grade from the raw data.
          The agent&apos;s operational LLM calls (narrative picks, post content, hedge signals) go through a
          gateway that commits every call to an on-chain Merkle root.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {cards.map((c) => (
          <div key={c.n} className="card p-6 md:p-7 relative">
            <div className="flex items-center gap-2 mb-4">
              <span className="h-8 w-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-white/70 font-bold tabular">{c.n}</span>
              <span className="text-[10px] uppercase tracking-[0.15em] text-white/40">{c.eyebrow}</span>
            </div>
            <h3 className="text-xl font-bold mb-2">{c.title}</h3>
            <p className="text-sm text-white/55 mb-5 leading-relaxed">{c.body}</p>
            <div className="space-y-1.5 text-xs text-white/60 mb-5">
              {c.bullets.map((b) => (
                <div key={b} className="flex items-center gap-2">
                  <span className="text-white/30">—</span><span>{b}</span>
                </div>
              ))}
            </div>
            <Link href={c.href} className="inline-flex items-center gap-1 text-sm text-white/70 hover:text-white hover:gap-2 transition-all">{c.cta} →</Link>
          </div>
        ))}
      </div>
    </section>
  );
}

// ── How it works — 3 steps horizontal ────────────────────────────────

// Demo-video slot. Reads a URL from NEXT_PUBLIC_DEMO_VIDEO_URL at build
// time so the user can drop in a YouTube/Loom embed without editing this
// file. Falls back to a "Demo coming" placeholder with a visual cue so
// the slot still frames the product when the video isn't ready yet.
function DemoVideo() {
  const url = process.env.NEXT_PUBLIC_DEMO_VIDEO_URL || "";
  const hasVideo = /^https?:\/\/(www\.)?(youtube\.com|youtu\.be|loom\.com)\//.test(url);
  return (
    <section className="max-w-5xl mx-auto px-5 py-10 md:py-16">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <div className="eyebrow mb-3">Demo · 90 seconds</div>
          <h2 className="display display-md">The agent, end to end.</h2>
        </div>
        <div className="text-[11px] text-white/35 font-mono hidden md:block">launch → grade → defend → attest</div>
      </div>
      <div className="relative rounded-2xl border border-white/10 bg-black/40 overflow-hidden" style={{ aspectRatio: "16 / 9" }}>
        {hasVideo ? (
          <iframe
            src={url}
            className="absolute inset-0 w-full h-full"
            title="FOUR-LIFE demo walkthrough"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center">
            <div className="relative">
              <div className="h-20 w-20 rounded-full border-2 border-white/15 flex items-center justify-center">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="text-white/50 ml-1" aria-hidden="true">
                  <polygon points="5 3 19 12 5 21 5 3" fill="currentColor"/>
                </svg>
              </div>
              <div className="absolute inset-0 rounded-full border-2 border-[#6cff32]/40 animate-ping"/>
            </div>
            <div className="mt-5 text-sm font-bold text-white">Walkthrough video arriving soon</div>
            <div className="mt-1 text-xs text-white/45 max-w-sm">
              Watch the agent launch a Four.meme token, grade it deterministically,
              defend it through its lifecycle, and commit every decision on-chain.
            </div>
            <div className="mt-4 flex flex-wrap gap-2 justify-center">
              <Link href="/proof" className="text-[11px] px-3 py-1.5 rounded-md border border-white/15 text-white/75 hover:bg-white/5 hover:text-white">
                Watch it live on /proof →
              </Link>
              <Link href="/radar" className="text-[11px] px-3 py-1.5 rounded-md border border-white/15 text-white/75 hover:bg-white/5 hover:text-white">
                Browse the radar →
              </Link>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

// One-image system diagram so a judge who doesn't want to read paragraphs
// can still reconstruct the architecture: Four.meme token → agent THINK/
// RAISE/LEARN loop → two parallel outputs (deterministic grade + attested
// LLM log on BNB Chain) → four consumer surfaces. Inline SVG means it
// renders without a network hop and stays crisp at any zoom.
function Architecture() {
  return (
    <section className="max-w-7xl mx-auto px-5 py-16 md:py-20">
      <div className="mb-10 max-w-3xl">
        <div className="eyebrow mb-4">Architecture · one glance</div>
        <h2 className="display display-lg mb-3">Token in. Proof out.</h2>
        <p className="text-white/55 text-base md:text-lg">
          A Four.meme token enters on the left. The autonomous agent runs a
          three-phase lifecycle loop. Every trust grade is deterministic
          (no LLM); every operational LLM call is committed to an on-chain
          Merkle root. Four consumer surfaces read the same primitives.
        </p>
      </div>

      <div className="rounded-2xl border border-white/10 bg-black/30 p-6 md:p-8 overflow-x-auto">
        <svg viewBox="0 0 1200 400" className="w-full h-auto min-w-[900px]" role="img" aria-label="FOUR-LIFE system diagram">
          <defs>
            <linearGradient id="arrow-grad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#00d4ff"/>
              <stop offset="100%" stopColor="#6cff32"/>
            </linearGradient>
            <marker id="arrow-head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
              <path d="M 0 0 L 10 5 L 0 10 Z" fill="#6cff32"/>
            </marker>
          </defs>

          {/* Column 1 — Input */}
          <g>
            <rect x="20" y="150" width="180" height="100" rx="12" fill="rgba(255,255,255,0.04)" stroke="rgba(255,255,255,0.14)" strokeWidth="1"/>
            <text x="110" y="175" textAnchor="middle" fontSize="11" fontWeight="700" letterSpacing="2" fill="rgba(255,255,255,0.5)">INPUT</text>
            <text x="110" y="205" textAnchor="middle" fontSize="18" fontWeight="800" fill="#fff">Four.meme</text>
            <text x="110" y="228" textAnchor="middle" fontSize="14" fill="rgba(255,255,255,0.7)">token address</text>
          </g>

          {/* Arrow 1 */}
          <line x1="200" y1="200" x2="290" y2="200" stroke="url(#arrow-grad)" strokeWidth="2.5" markerEnd="url(#arrow-head)"/>

          {/* Column 2 — Agent loop */}
          <g>
            <rect x="300" y="90" width="280" height="220" rx="14" fill="rgba(108,255,50,0.04)" stroke="rgba(108,255,50,0.3)" strokeWidth="1.5"/>
            <text x="440" y="115" textAnchor="middle" fontSize="11" fontWeight="700" letterSpacing="2" fill="#6cff32">FOUR-LIFE AGENT · ERC-8004 #20</text>

            {/* THINK / RAISE / LEARN as three pills */}
            {[
              { t: "THINK", x: 320, color: "#00d4ff", body: "Pick narrative" },
              { t: "RAISE", x: 320, color: "#ffd641", body: "Nurture → Defend → Accelerate" },
              { t: "LEARN", x: 320, color: "#a855f7", body: "Post-mortem · update memory" },
            ].map((p, i) => (
              <g key={p.t} transform={`translate(0, ${140 + i * 48})`}>
                <rect x={p.x} y="0" width="240" height="38" rx="8" fill="rgba(255,255,255,0.03)" stroke={`${p.color}60`} strokeWidth="1"/>
                <rect x={p.x} y="0" width="4" height="38" rx="2" fill={p.color}/>
                <text x={p.x + 16} y="16" fontSize="11" fontWeight="800" letterSpacing="1.5" fill={p.color}>{p.t}</text>
                <text x={p.x + 16} y="30" fontSize="11" fill="rgba(255,255,255,0.7)">{p.body}</text>
              </g>
            ))}
          </g>

          {/* Arrow 2a — to grade */}
          <line x1="580" y1="160" x2="700" y2="140" stroke="url(#arrow-grad)" strokeWidth="2.5" markerEnd="url(#arrow-head)"/>
          {/* Arrow 2b — to attestation */}
          <line x1="580" y1="240" x2="700" y2="260" stroke="url(#arrow-grad)" strokeWidth="2.5" markerEnd="url(#arrow-head)"/>

          {/* Column 3 — Parallel outputs */}
          <g>
            <rect x="710" y="75" width="260" height="110" rx="12" fill="rgba(0,212,255,0.05)" stroke="rgba(0,212,255,0.35)" strokeWidth="1"/>
            <text x="840" y="100" textAnchor="middle" fontSize="10" fontWeight="700" letterSpacing="1.8" fill="#00d4ff">DETERMINISTIC GRADE · NO LLM</text>
            <text x="840" y="128" textAnchor="middle" fontSize="16" fontWeight="800" fill="#fff">tier + why[] trace</text>
            <text x="840" y="150" textAnchor="middle" fontSize="12" fill="rgba(255,255,255,0.65)">graduated · watch · healthy</text>
            <text x="840" y="168" textAnchor="middle" fontSize="12" fill="rgba(255,255,255,0.65)">observed · at_risk</text>
          </g>
          <g>
            <rect x="710" y="215" width="260" height="110" rx="12" fill="rgba(168,85,247,0.05)" stroke="rgba(168,85,247,0.35)" strokeWidth="1"/>
            <text x="840" y="240" textAnchor="middle" fontSize="10" fontWeight="700" letterSpacing="1.8" fill="#a855f7">ON-CHAIN ATTESTATION · BNB CHAIN</text>
            <text x="840" y="268" textAnchor="middle" fontSize="16" fontWeight="800" fill="#fff">Merkle-root txs</text>
            <text x="840" y="290" textAnchor="middle" fontSize="12" fill="rgba(255,255,255,0.65)">DGrid LLM calls · MYX decisions</text>
            <text x="840" y="308" textAnchor="middle" fontSize="12" fill="rgba(255,255,255,0.65)">every call committed, verifiable</text>
          </g>

          {/* Arrows 3 — to consumer surfaces */}
          <line x1="970" y1="200" x2="1060" y2="200" stroke="url(#arrow-grad)" strokeWidth="2.5" markerEnd="url(#arrow-head)"/>

          {/* Column 4 — Consumers */}
          <g>
            <rect x="1070" y="100" width="115" height="200" rx="12" fill="rgba(255,255,255,0.04)" stroke="rgba(255,255,255,0.14)" strokeWidth="1"/>
            <text x="1127" y="125" textAnchor="middle" fontSize="10" fontWeight="700" letterSpacing="1.8" fill="rgba(255,255,255,0.5)">CONSUMERS</text>
            {[
              { y: 150, t: "SDK · Py + TS" },
              { y: 180, t: "Extension" },
              { y: 210, t: "/radar /proof" },
              { y: 240, t: "Webhooks" },
              { y: 270, t: "Embeddable" },
            ].map((c) => (
              <g key={c.t}>
                <circle cx="1087" cy={c.y} r="3" fill="#6cff32"/>
                <text x="1097" y={c.y + 4} fontSize="12" fontWeight="600" fill="rgba(255,255,255,0.85)">{c.t}</text>
              </g>
            ))}
          </g>
        </svg>
      </div>

      <p className="text-[11px] text-white/35 mt-4 font-mono text-center">
        Read left→right: a token enters, the agent grades it with pure rules while logging every LLM reasoning step on-chain, and four surfaces consume the same primitives.
      </p>
    </section>
  );
}

function HowItWorks() {
  const steps = [
    {
      n: "01",
      title: "Compute (no LLM)",
      body: "Every trust grade is computed from raw on-chain metrics — holders, whale concentration, buy/sell ratio, curve progress, contract risk — against deterministic thresholds. The rules that fired travel with the verdict so anyone can reproduce the grade.",
    },
    {
      n: "02",
      title: "Persist",
      body: "Every grade is written to a time-series store. Tier changes + keepalive snapshots. Query the history, compute diffs, export NDJSON for backfills.",
    },
    {
      n: "03",
      title: "Dispatch",
      body: "On every transition, fire signed HMAC webhooks and fan out to Telegram + Discord. Subscribers verify, react, and halt trading in real time.",
    },
  ];

  return (
    <section className="relative border-y border-white/5 bg-black/20">
      <div className="max-w-7xl mx-auto px-5 py-16 md:py-24">
        <div className="mb-12 max-w-3xl">
          <div className="eyebrow mb-4">How it works</div>
          <h2 className="display display-lg">Compute. Persist. Dispatch.</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-white/5 rounded-xl overflow-hidden">
          {steps.map((s) => (
            <div key={s.n} className="bg-[#0f1012] p-6 md:p-8 relative">
              <div className="text-5xl md:text-6xl font-bold tabular leading-none mb-4 text-white/20">{s.n}</div>
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
          <h2 className="display display-lg mb-4">One import. Live data.</h2>
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
      title: "Browse the Radar",
      body: "Every live Four.meme token, ranked deterministically. Filter by confidence, sort by graduation odds. Click for the full rule trace.",
      href: "/radar",
      cta: "Open Radar →",
    },
    {
      tag: "Agents",
      title: "Subscribe to webhooks",
      body: "React to tier changes and protection transitions in real time. HMAC-signed, retried, verified. Built for autonomous trading bots.",
      href: "/webhooks",
      cta: "Webhooks docs →",
    },
    {
      tag: "Creators",
      title: "Embed the badge",
      body: "One line of HTML drops a live Certified badge on your Discord, site, or bio. Auto-refresh. No build step. No tracking.",
      href: "/embed",
      cta: "See the widget →",
    },
    {
      tag: "Platforms",
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
        <h2 className="display display-lg">One API. Four audiences.</h2>
        <p className="text-white/55 text-base md:text-lg mt-3">
          Traders read the radar, creators embed the badge, operators subscribe to webhooks,
          and bots trigger off tier transitions. Same deterministic grade across every surface.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {cards.map((c) => {
          const body = (
            <>
              <div className="text-[10px] uppercase tracking-[0.15em] mb-3 text-white/40">{c.tag}</div>
              <h3 className="text-base font-bold mb-2">{c.title}</h3>
              <p className="text-xs text-white/55 mb-4 leading-relaxed">{c.body}</p>
              <div className="inline-flex items-center gap-1 text-xs font-semibold text-white/70 group-hover:text-white group-hover:gap-2 transition-all">{c.cta}</div>
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
    { t: "BNB Chain", body: "Runs on BSC mainnet. Every graduation attestation is on-chain." },
    { t: "Four.meme", body: "Pair-aware graduation targets sourced live from the platform config." },
    { t: "DGrid", body: "Every LLM call routes through DGrid. Multi-provider fallback (DGrid primary → OpenAI) keeps the agent alive during blips." },
    { t: "MYX V2", body: "Perp signals for hedging meme-token exposure through lifecycle phases." },
    { t: "ERC-8004", body: "FOUR-LIFE is a registered agent on BSC (agent ID 20). Reputation attestations per graduation." },
    { t: "Unibase", body: "Agent memory synced across sessions. Every launch outcome improves the next." },
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
              <div className="text-sm font-bold mb-1.5 text-white">{p.t}</div>
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
        <h2 className="display display-xl mb-5">Four.meme should ship this.</h2>
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
        { label: "Evidence", href: "/evidence" },
        { label: "Alerts", href: "/alerts" },
        { label: "Activity", href: "/activity" },
        { label: "DGrid showcase", href: "/dgrid" },
        { label: "Metrics", href: "/metrics" },
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
      <Reveal><DemoVideo /></Reveal>
      <Reveal><TryNow /></Reveal>
      <Reveal><LiveMetricsBand metrics={metrics} /></Reveal>
      <Reveal><Primitives /></Reveal>
      <Reveal><Architecture /></Reveal>
      <Reveal><HowItWorks /></Reveal>
      <Reveal><Developers /></Reveal>
      <Reveal><WhoUses /></Reveal>
      <Reveal><BuiltOn /></Reveal>
      <Reveal><FinalCTA /></Reveal>
      <Footer />
    </div>
  );
}
