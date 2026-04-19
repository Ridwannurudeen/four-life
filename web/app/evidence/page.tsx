"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

const API = (process.env.NEXT_PUBLIC_API_URL || "https://four-life.gudman.xyz").replace(/\/$/, "");

// Tokens hand-picked to span the tier distribution. The page fetches live
// FOUR-LIFE data for each — the grades are NOT baked in. Judges who load
// the page hours or days later will see what the agent sees right now,
// which is the point of "deterministic and reproducible."
const FEATURED: { address: string; pitch: string }[] = [
  { address: "0xd8c1c7b065ec8548093fe237157088b984dc4444", pitch: "70%+ curve, watched for graduation." },
  { address: "0x857eb8346b88c23fae2f1f6043413935b6744444", pitch: "Mid-curve — holder velocity + buy pressure decide the fork." },
  { address: "0x33f0022c15394a13a6997ed163896b519d554444", pitch: "Trust-graded even when the curve is still below 50%." },
  { address: "0x8b630c0e672cac94f27cbe7bf2456e6d53694444", pitch: "Still in nurture — the observed tier carries signal too." },
  { address: "0xae7500a58857f04de0c63c633d408c618f3a4444", pitch: "Low curve, still healthy — age + buy ratio matter." },
];

type Tier = "graduated" | "graduation_watch" | "healthy" | "at_risk" | "observed";

interface BadgeWhy {
  rule: string;
  metric: string;
  value: string | number | boolean;
  threshold: string | number | boolean;
  operator: string;
  passed: boolean;
}

interface Badge {
  tier: Tier;
  label: string;
  description: string;
  why: BadgeWhy[];
  metrics_snapshot: Record<string, unknown>;
  version: string;
}

interface BadgeResponse {
  token_address: string;
  badge: Badge;
  data_source: string;
  model_version: string;
  last_updated_at: number;
}

interface TokenPayload {
  health: {
    address: string;
    name: string;
    symbol: string;
    phase: string;
    age_hours: number;
    health_score: number;
    graduation_probability: number;
    unique_buyers: number;
    buy_sell_ratio: number;
    top_holder_pct: number;
    whale_count: number;
    curve_progress: number;
    holder_velocity: number;
  };
}

interface Case {
  address: string;
  pitch: string;
  badge: Badge | null;
  health: TokenPayload["health"] | null;
}

const TIER_STYLE: Record<Tier, { bg: string; text: string; border: string; dot: string }> = {
  graduated: { bg: "bg-purple-500/10", text: "text-purple-300", border: "border-purple-500/40", dot: "bg-purple-400" },
  graduation_watch: { bg: "bg-[#00d4ff]/10", text: "text-[#00d4ff]", border: "border-[#00d4ff]/40", dot: "bg-[#00d4ff]" },
  healthy: { bg: "bg-[#6cff32]/10", text: "text-[#6cff32]", border: "border-[#6cff32]/40", dot: "bg-[#6cff32]" },
  at_risk: { bg: "bg-[#ff494a]/10", text: "text-[#ff494a]", border: "border-[#ff494a]/40", dot: "bg-[#ff494a]" },
  observed: { bg: "bg-[#ffd641]/10", text: "text-[#ffd641]", border: "border-[#ffd641]/40", dot: "bg-[#ffd641]" },
};

function short(addr: string) {
  return addr.slice(0, 6) + "…" + addr.slice(-4);
}

function fmt(n: number | undefined | null, d = 2): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: d });
}

function BadgePill({ tier, label }: { tier: Tier; label: string }) {
  const s = TIER_STYLE[tier];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold tracking-wide ${s.bg} ${s.text} ${s.border}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      <span className="uppercase">{label}</span>
    </span>
  );
}

function WhyTable({ why }: { why: BadgeWhy[] }) {
  if (!why?.length) return null;
  return (
    <table className="w-full text-[11px] mt-3">
      <thead>
        <tr className="text-white/30 uppercase tracking-wider">
          <th className="text-left py-1.5 pr-3">Rule</th>
          <th className="text-left py-1.5 pr-3">Metric</th>
          <th className="text-left py-1.5 pr-3">Value / Threshold</th>
          <th className="text-left py-1.5">Fired</th>
        </tr>
      </thead>
      <tbody>
        {why.map((w, i) => (
          <tr key={i} className="border-t border-white/5">
            <td className="py-1.5 pr-3 font-mono">{w.rule}</td>
            <td className="py-1.5 pr-3 text-white/60">{w.metric}</td>
            <td className="py-1.5 pr-3 font-mono text-white/70">
              {String(w.value)} {w.operator} {String(w.threshold)}
            </td>
            <td className="py-1.5">
              <span className={w.passed ? "text-[#6cff32]" : "text-white/40"}>
                {w.passed ? "✓" : "—"}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function EvidencePage() {
  const [cases, setCases] = useState<Case[]>(
    FEATURED.map((f) => ({ address: f.address, pitch: f.pitch, badge: null, health: null })),
  );
  const [updatedAt, setUpdatedAt] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const next: Case[] = await Promise.all(
        FEATURED.map(async (f) => {
          try {
            const [b, t] = await Promise.all([
              fetch(`${API}/api/token/${f.address}/badge`).then((r) => (r.ok ? r.json() : null)),
              fetch(`${API}/api/tokens/${f.address}`).then((r) => (r.ok ? r.json() : null)),
            ]);
            return {
              address: f.address,
              pitch: f.pitch,
              badge: (b as BadgeResponse | null)?.badge ?? null,
              health: (t as TokenPayload | null)?.health ?? null,
            };
          } catch {
            return { address: f.address, pitch: f.pitch, badge: null, health: null };
          }
        }),
      );
      if (!cancelled) {
        setCases(next);
        setUpdatedAt(Math.floor(Date.now() / 1000));
      }
    }
    const initial = setTimeout(load, 0);
    const iv = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearTimeout(initial);
      clearInterval(iv);
    };
  }, []);

  const distribution = useMemo(() => {
    const counts: Partial<Record<Tier, number>> = {};
    cases.forEach((c) => {
      const t = c.badge?.tier;
      if (t) counts[t] = (counts[t] || 0) + 1;
    });
    return counts;
  }, [cases]);

  return (
    <main className="max-w-5xl mx-auto px-5 py-14">
      <div className="mb-10">
        <Link href="/" className="text-xs text-white/40 hover:text-white/70">← Home</Link>
      </div>

      <div className="mb-10 max-w-3xl">
        <div className="eyebrow mb-3">Evidence panel</div>
        <h1 className="text-4xl md:text-5xl font-bold mb-4">
          What FOUR-LIFE is seeing, right now.
        </h1>
        <p className="text-white/60 text-lg leading-relaxed">
          Five live Four.meme tokens, graded deterministically from on-chain metrics. Every grade comes with the
          exact rule that fired and the threshold it cleared — recompute yourself and the answer matches. Zero LLM in
          the trust path.
        </p>
      </div>

      <div className="mb-10 flex items-center gap-2 flex-wrap text-xs text-white/50">
        <span className="eyebrow">Tier distribution</span>
        {(Object.keys(TIER_STYLE) as Tier[]).map((t) => (
          <span key={t} className="flex items-center gap-1.5">
            <span className={`h-1.5 w-1.5 rounded-full ${TIER_STYLE[t].dot}`} />
            <span className="uppercase text-[10px] tracking-wide">{t.replace("_", " ")}</span>
            <span className="font-mono">{distribution[t] || 0}</span>
          </span>
        ))}
        {updatedAt > 0 && (
          <span className="text-white/30 ml-auto">
            updated {new Date(updatedAt * 1000).toLocaleTimeString()}
          </span>
        )}
      </div>

      <div className="space-y-5">
        {cases.map((c) => (
          <div key={c.address} className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
            <div className="flex items-start justify-between gap-4 flex-wrap mb-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  {c.badge && <BadgePill tier={c.badge.tier} label={c.badge.label} />}
                  {c.health?.name && (
                    <span className="text-base font-semibold">{c.health.name}</span>
                  )}
                  {c.health?.symbol && (
                    <span className="text-white/40 text-xs">${c.health.symbol}</span>
                  )}
                </div>
                <p className="text-xs text-white/50 mb-2 max-w-xl">{c.pitch}</p>
                <div className="flex items-center gap-3 text-[11px] text-white/40">
                  <a
                    href={`https://bscscan.com/address/${c.address}`}
                    target="_blank"
                    rel="noreferrer"
                    className="font-mono hover:text-white/70"
                  >
                    {short(c.address)} ↗
                  </a>
                  <Link href={`/launch/${c.address}`} className="text-[#00d4ff] hover:underline">
                    full page →
                  </Link>
                  <a
                    href={`https://four.meme/token/${c.address}`}
                    target="_blank"
                    rel="noreferrer"
                    className="hover:text-white/70"
                  >
                    four.meme ↗
                  </a>
                </div>
              </div>
              {c.health && (
                <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs text-white/60">
                  <span>curve</span><span className="font-mono text-right">{fmt(c.health.curve_progress, 1)}%</span>
                  <span>holders</span><span className="font-mono text-right">{fmt(c.health.unique_buyers, 0)}</span>
                  <span>top holder</span><span className="font-mono text-right">{fmt(c.health.top_holder_pct, 1)}%</span>
                  <span>buy/sell</span><span className="font-mono text-right">{fmt(c.health.buy_sell_ratio, 2)}</span>
                </div>
              )}
            </div>
            {c.badge && <WhyTable why={c.badge.why} />}
            {!c.badge && (
              <p className="text-xs text-white/40 italic">Grade loading — if this persists, the token isn&apos;t tracked yet.</p>
            )}
          </div>
        ))}
      </div>

      <div className="mt-12 rounded-2xl border border-white/10 bg-white/[0.02] p-6">
        <div className="eyebrow mb-2">What you just saw</div>
        <p className="text-sm text-white/70 leading-relaxed max-w-3xl">
          Every grade above is auditable. Hit{" "}
          <code className="text-[#00d4ff]">GET /api/token/&lt;addr&gt;/badge</code> and you get the same tier, the same
          rules, the same metric snapshot. No proprietary scoring black box. No &quot;the model decided.&quot; A threshold
          fired or it didn&apos;t, and we show you which one.
        </p>
      </div>
    </main>
  );
}
