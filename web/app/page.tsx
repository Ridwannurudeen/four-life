"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

const API = (process.env.NEXT_PUBLIC_API_URL || "https://four-life.gudman.xyz").replace(/\/$/, "");
const EMBED_URL = "https://four-life.gudman.xyz/embed.js";

// Three curated token addresses used as live-badge demos on the landing.
// The widget auto-fallbacks if any of these go cold.
const DEMO_TOKENS: { addr: string; label: string }[] = [
  { addr: "0x00ea33ab439c3fad06a6a824f3dbfade01334444", label: "Graduation Watch sample" },
  { addr: "0x72b0a042e19871c046c1bd31e5b5ad3770c94444", label: "Observed sample" },
  { addr: "0xc5f692f3b484e76518b72191b9a11bed06284444", label: "Early-stage sample" },
];

// ── Live tier-summary pulled from the Radar endpoint ───────────────

interface TierCounts {
  graduated: number;
  graduation_watch: number;
  healthy: number;
  at_risk: number;
  observed: number;
}

function deriveTier(entry: { curve_progress: number; confidence_score: string; increase_pct: number }): keyof TierCounts {
  if (entry.curve_progress >= 100) return "graduated";
  if (entry.curve_progress >= 70 && entry.confidence_score === "high" && entry.increase_pct >= 0) return "graduation_watch";
  if (entry.increase_pct <= -50) return "at_risk";
  return "observed";
}

function useTierCounts() {
  const [counts, setCounts] = useState<TierCounts | null>(null);
  const [total, setTotal] = useState(0);

  const fetchCounts = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/graduation-radar?limit=60&min_confidence=low`);
      if (!r.ok) return;
      const data = await r.json();
      const c: TierCounts = { graduated: 0, graduation_watch: 0, healthy: 0, at_risk: 0, observed: 0 };
      for (const e of data.radar || []) c[deriveTier(e)] += 1;
      setCounts(c);
      setTotal((data.radar || []).length);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchCounts();
    const id = setInterval(fetchCounts, 45_000);
    return () => clearInterval(id);
  }, [fetchCounts]);

  return { counts, total };
}

// ── Live embed widget slot (mounts the real embed.js) ──────────────

function WidgetSlot({ token, size = "md" }: { token: string; size?: "sm" | "md" | "lg" }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    const ensureScript = () =>
      new Promise<void>((resolve) => {
        if ((window as unknown as { FourLife?: unknown }).FourLife) return resolve();
        const existing = document.querySelector<HTMLScriptElement>("script[data-fl-loader]");
        if (existing) { existing.addEventListener("load", () => resolve()); return; }
        const s = document.createElement("script");
        s.src = EMBED_URL;
        s.async = true;
        s.setAttribute("data-fl-loader", "1");
        s.addEventListener("load", () => resolve());
        document.head.appendChild(s);
      });

    let inst: { destroy?: () => void } | null = null;
    ensureScript().then(() => {
      const FL = (window as unknown as {
        FourLife?: { mount: (o: { target: Element; token: string; size?: string }) => { destroy?: () => void } };
      }).FourLife;
      if (FL && ref.current) {
        while (ref.current.firstChild) ref.current.removeChild(ref.current.firstChild);
        inst = FL.mount({ target: ref.current, token, size });
      }
    });
    return () => { if (inst?.destroy) inst.destroy(); };
  }, [token, size]);

  return <div ref={ref} />;
}

// ── Helper UI ──────────────────────────────────────────────────────

function Copyable({ text, className = "" }: { text: string; className?: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard?.writeText(text); setOk(true); setTimeout(() => setOk(false), 1400); }}
      className={`relative card p-0 text-left w-full group ${className}`}
    >
      <pre className="p-4 text-[11px] md:text-xs text-[#a7f7b5] font-mono whitespace-pre-wrap leading-relaxed break-all">{text}</pre>
      <span className="absolute top-2 right-2 text-[10px] px-2.5 py-1 rounded-full border border-white/10 bg-white/5 text-white/70 font-semibold uppercase tracking-wider group-hover:bg-white/10">
        {ok ? "Copied" : "Copy"}
      </span>
    </button>
  );
}

// ── Page ───────────────────────────────────────────────────────────

export default function Landing() {
  const { counts, total } = useTierCounts();

  return (
    <div className="min-h-screen bg-[#0f1012] text-white bg-grid">
      {/* Nav */}
      <header className="border-b border-white/5 sticky top-0 z-30 bg-[#0f1012]/90 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-5 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <span className="h-8 w-8 rounded-lg bg-gradient-to-br from-[#6cff32] to-[#00d4ff] flex items-center justify-center font-bold text-black">4</span>
            <div>
              <div className="text-sm font-semibold">FOUR-LIFE</div>
              <div className="text-[10px] text-white/40 uppercase tracking-wider">Certified</div>
            </div>
          </Link>
          <nav className="flex items-center gap-1.5">
            <Link href="/radar" className="btn-pill bg-transparent hover:bg-white/5 border border-white/10 text-xs">Radar</Link>
            <Link href="/embed" className="btn-pill bg-transparent hover:bg-white/5 border border-white/10 text-xs">Embed</Link>
            <Link href="/dashboard" className="btn-pill bg-transparent hover:bg-white/5 border border-white/10 text-xs hidden md:inline-flex">Dashboard</Link>
            <a href="https://github.com/Ridwannurudeen/four-life" target="_blank" rel="noopener noreferrer" className="btn-pill bg-white/5 hover:bg-white/10 border border-white/10 text-xs">GitHub</a>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-5 pt-16 md:pt-24 pb-10 md:pb-16">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-[#6cff32]/30 bg-[#6cff32]/5 px-3 py-1 mb-6">
            <span className="h-1.5 w-1.5 rounded-full bg-[#6cff32] pulse-ring" />
            <span className="text-[11px] font-medium text-[#6cff32] tracking-wide uppercase">Live on BNB Chain</span>
          </div>
          <h1 className="text-4xl md:text-6xl font-bold tracking-tight leading-[1.05] mb-6">
            The <span className="gradient-text">trust layer</span><br className="hidden md:block" /> Four.meme is missing.
          </h1>
          <p className="text-white/65 text-base md:text-xl leading-relaxed max-w-2xl mb-4">
            98.6% of meme tokens die within 72 hours. FOUR-LIFE grades every live Four.meme launch with a deterministic Certified tier, backed by a full audit trail — from pair-aware graduation targets to contract-level rug detection.
          </p>
          <p className="text-white/45 text-sm md:text-base leading-relaxed max-w-2xl mb-8">
            Not another launch bot. The survival, trust, and discovery primitive the platform is built to embed.
          </p>

          <div className="flex flex-wrap gap-2 mb-10">
            <Link href="/radar" className="btn-pill bg-[#6cff32] hover:bg-[#6cff32]/90 text-black">Browse the Radar →</Link>
            <Link href="/embed" className="btn-pill bg-white/5 hover:bg-white/10 border border-white/10">Embed the badge</Link>
            <a href={`${API}/api/identity`} target="_blank" rel="noopener noreferrer" className="btn-pill bg-transparent hover:bg-white/5 border border-white/10 text-white/70">ERC-8004 identity →</a>
          </div>

          {/* Live badges — actual widget running on the landing */}
          <div className="card p-5 md:p-6">
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-xs uppercase tracking-wider text-white/40">Live on Four.meme right now</div>
                <div className="text-[11px] text-white/30 mt-0.5">Auto-refreshes every 60s · click any badge for the rule trace</div>
              </div>
              <div className="text-[10px] text-white/30 hidden md:block">Powered by the real /embed.js widget</div>
            </div>
            <div className="flex flex-wrap gap-3">
              {DEMO_TOKENS.map((d) => (
                <div key={d.addr} className="flex flex-col gap-1.5">
                  <WidgetSlot token={d.addr} size="md" />
                  <div className="text-[10px] text-white/30 font-mono">{d.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Live tier counts */}
      <section className="max-w-6xl mx-auto px-5 pb-10">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs uppercase tracking-wider text-white/40">Live tier distribution</h2>
          {total > 0 && <span className="text-[11px] text-white/30">{total} tokens scanned</span>}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          {[
            { key: "graduated", label: "Graduated", color: "border-purple-500/40 text-purple-300" },
            { key: "graduation_watch", label: "Watch", color: "border-[#00d4ff]/40 text-[#00d4ff]" },
            { key: "healthy", label: "Healthy", color: "border-[#6cff32]/40 text-[#6cff32]" },
            { key: "observed", label: "Observed", color: "border-[#ffd641]/40 text-[#ffd641]" },
            { key: "at_risk", label: "At Risk", color: "border-[#ff494a]/40 text-[#ff494a]" },
          ].map((t) => (
            <div key={t.key} className={`card p-4 border ${t.color}`}>
              <div className="text-[11px] uppercase tracking-wider opacity-70">{t.label}</div>
              <div className="text-2xl font-bold mt-0.5">{counts ? (counts[t.key as keyof TierCounts] ?? 0) : "—"}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Why this exists */}
      <section className="max-w-6xl mx-auto px-5 py-16">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <div className="text-6xl md:text-7xl font-bold gradient-text leading-none mb-2">98.6%</div>
            <div className="text-sm text-white/50">of meme tokens die within 72 hours of launch. Four.meme&apos;s Agentic Mode handles creation. Nothing after.</div>
          </div>
          <div>
            <div className="text-6xl md:text-7xl font-bold gradient-text leading-none mb-2">0</div>
            <div className="text-sm text-white/50">LLM calls in the trust path. Every Certified tier is computed from raw on-chain metrics. Fully deterministic, fully auditable.</div>
          </div>
          <div>
            <div className="text-6xl md:text-7xl font-bold gradient-text leading-none mb-2">&lt;2s</div>
            <div className="text-sm text-white/50">from visiting a four.meme token page to seeing the Certified tier — with the browser extension installed.</div>
          </div>
        </div>
      </section>

      {/* CTA ladder — how to use FOUR-LIFE */}
      <section className="max-w-6xl mx-auto px-5 pb-16">
        <h2 className="text-2xl md:text-3xl font-bold mb-8">Three ways to use it today.</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {/* 1. Radar */}
          <div className="card p-6 flex flex-col">
            <div className="text-[11px] uppercase tracking-wider text-[#6cff32] mb-2">1 · As a trader</div>
            <h3 className="text-lg font-semibold mb-2">Browse the Certified Radar</h3>
            <p className="text-sm text-white/60 mb-4 flex-1">Every active Four.meme token, ranked with filters for quote asset, confidence, and sort key. Click any token for the full rule trace.</p>
            <Link href="/radar" className="btn-pill bg-[#6cff32] hover:bg-[#6cff32]/90 text-black text-center">Open Radar →</Link>
          </div>

          {/* 2. Extension */}
          <div className="card p-6 flex flex-col">
            <div className="text-[11px] uppercase tracking-wider text-[#00d4ff] mb-2">2 · On every page you visit</div>
            <h3 className="text-lg font-semibold mb-2">Install the browser extension</h3>
            <p className="text-sm text-white/60 mb-4 flex-1">The Certified badge appears directly on every four.meme/token/* page. Full rule trace on click. Shadow-DOM isolated.</p>
            <a
              href="https://github.com/Ridwannurudeen/four-life/tree/master/extension"
              target="_blank" rel="noopener noreferrer"
              className="btn-pill bg-white/5 hover:bg-white/10 border border-white/10 text-center"
            >
              Get the extension →
            </a>
          </div>

          {/* 3. Embed */}
          <div className="card p-6 flex flex-col">
            <div className="text-[11px] uppercase tracking-wider text-[#ffd641] mb-2">3 · As a creator</div>
            <h3 className="text-lg font-semibold mb-2">Embed the trust badge</h3>
            <p className="text-sm text-white/60 mb-4 flex-1">One line of HTML. Drops a live Certified pill on your Discord, site, or bio link-tree. Updates every 60 seconds.</p>
            <Link href="/embed" className="btn-pill bg-[#ffd641] hover:bg-[#ffd641]/90 text-black text-center">See the widget →</Link>
          </div>
        </div>
      </section>

      {/* One-line install */}
      <section className="max-w-4xl mx-auto px-5 pb-16">
        <div className="text-[11px] uppercase tracking-wider text-white/40 mb-2">Drop the widget anywhere — one line</div>
        <Copyable
          text={`<script src="https://four-life.gudman.xyz/embed.js?token=YOUR_TOKEN_ADDRESS"></script>`}
        />
        <div className="text-[11px] text-white/30 mt-2 text-center">
          No build step. No dependencies. No tracking. Works from any origin, any CSP.
        </div>
      </section>

      {/* How the badge works */}
      <section className="max-w-6xl mx-auto px-5 py-16 border-t border-white/5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-10 items-start">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-white/40 mb-3">How it works</div>
            <h2 className="text-2xl md:text-3xl font-bold mb-4">Deterministic. Auditable. Fully reproducible.</h2>
            <p className="text-white/60 text-sm md:text-base leading-relaxed mb-4">
              Every Certified badge is computed from the token&apos;s raw on-chain metrics — holders, whale concentration, buy/sell ratio, holder velocity, curve progress, contract risk score. Pair-aware graduation targets source live from Four.meme&apos;s own config (BNB → 18 BNB, USD1 → 12 000 USD1, ...).
            </p>
            <p className="text-white/60 text-sm md:text-base leading-relaxed mb-4">
              There are zero LLM calls in the trust path. Each response includes a <code className="font-mono bg-white/10 px-1.5 py-0.5 rounded text-[#6cff32]">why[]</code> array listing every rule that fired, with exact metric values, operators, thresholds, and pass/fail state. You can reproduce any badge from the raw data.
            </p>
            <div className="flex flex-wrap gap-2">
              <a href={`${API}/api/token/${DEMO_TOKENS[0].addr}/badge`} target="_blank" rel="noopener noreferrer" className="btn-pill bg-white/5 hover:bg-white/10 border border-white/10 text-xs">Inspect a badge →</a>
              <a href={`${API}/api/dgrid/stats`} target="_blank" rel="noopener noreferrer" className="btn-pill bg-transparent hover:bg-white/5 border border-white/10 text-white/70 text-xs">DGrid stats</a>
              <a href={`${API}/api/platform/cohorts`} target="_blank" rel="noopener noreferrer" className="btn-pill bg-transparent hover:bg-white/5 border border-white/10 text-white/70 text-xs">Platform cohorts</a>
            </div>
          </div>
          <div className="card p-5 text-xs md:text-sm font-mono text-white/80 overflow-x-auto">
            <div className="text-white/40 mb-2">GET /api/token/.../badge → badge.why[]</div>
            <pre className="text-[11px] md:text-[12px] leading-relaxed">
{`{ rule: "curve_advanced",
  metric: "curve_progress_pct",
  value: 74.43,
  threshold: 70,
  operator: ">=",
  passed: true },
{ rule: "buy_pressure",
  metric: "buy_sell_ratio",
  value: 2.00,
  threshold: 1.2,
  operator: ">=",
  passed: true },
{ rule: "whale_ok",
  metric: "top_holder_pct",
  value: 0.0,
  threshold: 30,
  operator: "<",
  passed: true },
{ rule: "target_confident",
  metric: "graduation_confidence",
  value: "high",
  threshold: "high",
  operator: "==",
  passed: true }`}
            </pre>
            <div className="text-white/30 text-[10px] mt-3">↑ the exact response that produces the &quot;Graduation Watch&quot; tier</div>
          </div>
        </div>
      </section>

      {/* Partner-tech strip */}
      <section className="max-w-6xl mx-auto px-5 py-16 border-t border-white/5">
        <h2 className="text-xs uppercase tracking-wider text-white/40 mb-6">Built on the Four.meme AI Sprint stack</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { t: "Four.meme", body: "Live token stream, pair configs, Agentic Mode creation pipeline — all consumed via the public API.", cta: null },
            { t: "DGrid AI Gateway", body: "All LLM calls route through DGrid with task-specific model selection (Gemini / Claude / GPT-4o).", cta: { href: `${API}/api/dgrid/stats`, label: "Usage stats →" } },
            { t: "MYX V2", body: "Signal-layer perp integration for hedging meme-token exposure. Execution mode opt-in for safety.", cta: null },
            { t: "ERC-8004 / BRC-8004", body: "FOUR-LIFE registers on the BNB BRC-8004 registry; reputation attestations posted on each graduation.", cta: { href: `${API}/api/identity`, label: "Agent card →" } },
            { t: "Unibase / Membase", body: "Agent memory synced for cross-session learning — graduation outcomes improve future launch strategy.", cta: null },
            { t: "BscScan", body: "Anti-rug contract analyzer: mint, blacklist, pause, proxy, ownable, honeypot detection.", cta: null },
          ].map((p) => (
            <div key={p.t} className="card p-4">
              <div className="text-sm font-semibold mb-1">{p.t}</div>
              <div className="text-xs text-white/50 mb-2">{p.body}</div>
              {p.cta && (
                <a href={p.cta.href} target="_blank" rel="noopener noreferrer" className="text-[11px] text-[#6cff32] hover:underline">{p.cta.label}</a>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Closing CTA */}
      <section className="max-w-4xl mx-auto px-5 py-16 text-center border-t border-white/5">
        <h2 className="text-3xl md:text-4xl font-bold mb-4">
          Four.meme should ship this.
        </h2>
        <p className="text-white/60 text-sm md:text-base mb-6 max-w-2xl mx-auto">
          FOUR-LIFE Certified is a drop-in primitive. Platform embed. Creator embed. Trader radar. Zero trust cost. Open source.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <Link href="/radar" className="btn-pill bg-[#6cff32] hover:bg-[#6cff32]/90 text-black">Open the Radar</Link>
          <a href="https://github.com/Ridwannurudeen/four-life" target="_blank" rel="noopener noreferrer" className="btn-pill bg-white/5 hover:bg-white/10 border border-white/10">Read the code</a>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-10 px-5 text-center">
        <div className="max-w-3xl mx-auto space-y-2">
          <div className="text-xs text-white/40">
            Built for the Four.meme AI Sprint Hackathon on BNB Chain.
          </div>
          <div className="flex items-center justify-center gap-3 flex-wrap text-[11px] text-white/40">
            <Link href="/radar" className="hover:text-white">Radar</Link><span>·</span>
            <Link href="/embed" className="hover:text-white">Embed</Link><span>·</span>
            <Link href="/dashboard" className="hover:text-white">Dashboard</Link><span>·</span>
            <a href="https://github.com/Ridwannurudeen/four-life" target="_blank" rel="noopener noreferrer" className="hover:text-white">GitHub</a><span>·</span>
            <a href={`${API}/api/identity`} target="_blank" rel="noopener noreferrer" className="hover:text-white">ERC-8004</a><span>·</span>
            <a href={`${API}/api/dgrid/stats`} target="_blank" rel="noopener noreferrer" className="hover:text-white">DGrid Stats</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
