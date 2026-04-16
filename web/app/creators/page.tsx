"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

const API = (process.env.NEXT_PUBLIC_API_URL || "https://four-life.gudman.xyz").replace(/\/$/, "");

type TrustTier = "proven" | "emerging" | "new_creator" | "unproven" | "unknown";

interface CreatorEvidence {
  token_address: string;
  symbol: string;
  narrative: string;
  quote_asset: string;
  launched_at: number;
  graduated: boolean;
  peak_curve_progress: number;
  peak_holders: number;
  peak_health_score: number;
}

interface CreatorRow {
  wallet: string;
  launches_tracked: number;
  graduations: number;
  graduation_rate: number;
  median_peak_curve_progress: number;
  median_peak_holders: number;
  trust_tier: TrustTier;
  last_launch_at: number;
  evidence: CreatorEvidence[];
}

interface LeaderboardResponse {
  count: number;
  total_creators: number;
  filters: { sort_by: string; trust_tier: string | null; min_launches: number; limit: number };
  creators: CreatorRow[];
  model_version: string;
  last_updated_at: number;
}

const TIER_STYLE: Record<TrustTier, { bg: string; text: string; border: string; label: string }> = {
  proven: { bg: "bg-purple-500/10", text: "text-purple-300", border: "border-purple-500/40", label: "Proven" },
  emerging: { bg: "bg-[#00d4ff]/10", text: "text-[#00d4ff]", border: "border-[#00d4ff]/40", label: "Emerging" },
  new_creator: { bg: "bg-[#ffd641]/10", text: "text-[#ffd641]", border: "border-[#ffd641]/40", label: "New Creator" },
  unproven: { bg: "bg-white/5", text: "text-white/60", border: "border-white/10", label: "Unproven" },
  unknown: { bg: "bg-white/5", text: "text-white/40", border: "border-white/10", label: "Unknown" },
};

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "trust_tier", label: "Trust tier" },
  { value: "graduation_rate", label: "Graduation rate" },
  { value: "launches", label: "Launches" },
  { value: "median_holders", label: "Median holders" },
  { value: "median_curve", label: "Median curve %" },
  { value: "recent", label: "Most recent launch" },
];

const TIER_FILTERS: { value: string; label: string }[] = [
  { value: "all", label: "All tiers" },
  { value: "proven", label: "Proven" },
  { value: "emerging", label: "Emerging" },
  { value: "new_creator", label: "New creator" },
  { value: "unproven", label: "Unproven" },
];

function shortWallet(addr: string): string {
  if (!addr) return "";
  return addr.slice(0, 6) + "…" + addr.slice(-4);
}

function ago(ts: number): string {
  if (!ts) return "never";
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function TrustBadge({ tier }: { tier: TrustTier }) {
  const s = TIER_STYLE[tier] || TIER_STYLE.unknown;
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${s.bg} ${s.text} ${s.border}`}>
      {s.label}
    </span>
  );
}

function CreatorRowView({ row }: { row: CreatorRow }) {
  const [expanded, setExpanded] = useState(false);
  const pct = Math.round(row.graduation_rate * 100);

  return (
    <>
      <tr
        className="border-b border-white/5 hover:bg-white/[0.02] cursor-pointer transition-colors"
        onClick={() => setExpanded(v => !v)}
      >
        <td className="px-4 py-3 font-mono text-xs text-white/80">
          <div className="flex items-center gap-2">
            <span className="text-white/30">{expanded ? "▾" : "▸"}</span>
            <span>{shortWallet(row.wallet)}</span>
          </div>
        </td>
        <td className="px-4 py-3"><TrustBadge tier={row.trust_tier} /></td>
        <td className="px-4 py-3 text-right font-mono text-sm">{row.launches_tracked}</td>
        <td className="px-4 py-3 text-right font-mono text-sm">
          <span className={row.graduations > 0 ? "text-[#6cff32]" : "text-white/40"}>{row.graduations}</span>
          <span className="text-white/30 text-xs ml-1">/ {row.launches_tracked}</span>
        </td>
        <td className="px-4 py-3 text-right font-mono text-sm">{pct}%</td>
        <td className="px-4 py-3 text-right font-mono text-sm">{row.median_peak_holders}</td>
        <td className="px-4 py-3 text-right font-mono text-sm">{row.median_peak_curve_progress.toFixed(1)}</td>
        <td className="px-4 py-3 text-right text-xs text-white/50">{ago(row.last_launch_at)}</td>
      </tr>
      {expanded && (
        <tr className="border-b border-white/5 bg-black/20">
          <td colSpan={8} className="px-4 py-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between mb-2">
                <div className="text-[11px] uppercase tracking-wider text-white/40">Recent launches</div>
                <div className="text-[11px] font-mono text-white/30">{row.wallet}</div>
              </div>
              {row.evidence.length === 0 ? (
                <div className="text-xs text-white/50">No evidence available.</div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {row.evidence.slice().reverse().map((ev) => (
                    <Link
                      key={ev.token_address}
                      href={`/radar?token=${ev.token_address}`}
                      className="card p-3 text-xs hover:bg-white/[0.04] transition-colors"
                    >
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="font-semibold truncate">{ev.symbol}</span>
                          <span className="text-white/30 text-[10px] font-mono">{ev.quote_asset}</span>
                        </div>
                        {ev.graduated ? (
                          <span className="text-[9px] font-semibold uppercase text-purple-300 bg-purple-500/10 border border-purple-500/30 rounded-full px-1.5 py-0.5">Graduated</span>
                        ) : (
                          <span className="text-[9px] font-semibold uppercase text-white/50 bg-white/5 border border-white/10 rounded-full px-1.5 py-0.5">Active</span>
                        )}
                      </div>
                      <div className="flex items-center justify-between text-white/50">
                        <span>Peak: {ev.peak_curve_progress.toFixed(0)}%</span>
                        <span>{ev.peak_holders} holders</span>
                      </div>
                      <div className="text-[10px] text-white/30 mt-1">{ago(ev.launched_at)}</div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function CreatorsPage() {
  const [data, setData] = useState<LeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState("trust_tier");
  const [tierFilter, setTierFilter] = useState("all");
  const [minLaunches, setMinLaunches] = useState(1);

  const fetchLeaderboard = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        sort_by: sortBy,
        min_launches: String(minLaunches),
        limit: "200",
      });
      if (tierFilter !== "all") params.set("trust_tier", tierFilter);
      const res = await fetch(`${API}/api/creators/leaderboard?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: LeaderboardResponse = await res.json();
      setData(json);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load creators");
    } finally {
      setLoading(false);
    }
  }, [sortBy, tierFilter, minLaunches]);

  useEffect(() => {
    fetchLeaderboard();
    const id = setInterval(fetchLeaderboard, 60_000);
    return () => clearInterval(id);
  }, [fetchLeaderboard]);

  const tierCounts = useMemo(() => {
    const counts: Record<TrustTier, number> = { proven: 0, emerging: 0, new_creator: 0, unproven: 0, unknown: 0 };
    (data?.creators ?? []).forEach(c => { counts[c.trust_tier] = (counts[c.trust_tier] ?? 0) + 1; });
    return counts;
  }, [data]);

  return (
    <div className="min-h-screen bg-[#0f1012] text-white bg-grid">
      <header className="border-b border-white/5 sticky top-0 z-30 bg-[#0f1012]/90 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-5 py-4 flex items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-2 group">
            <span className="h-8 w-8 rounded-lg bg-gradient-to-br from-[#6cff32] to-[#00d4ff] flex items-center justify-center font-bold text-black">4</span>
            <div>
              <div className="text-sm font-semibold">FOUR-LIFE</div>
              <div className="text-[10px] text-white/40 uppercase tracking-wider">Creator Ledger</div>
            </div>
          </Link>
          <div className="flex items-center gap-2">
            {data && (
              <span className="text-[11px] text-white/40 hidden md:block">
                Updated {ago(data.last_updated_at)} · model {data.model_version}
              </span>
            )}
            <Link href="/radar" className="btn-pill bg-white/5 hover:bg-white/10 border border-white/10 text-xs">Radar</Link>
            <Link href="/" className="btn-pill bg-transparent hover:bg-white/5 border border-white/10 text-white/70 text-xs">Dashboard</Link>
          </div>
        </div>
      </header>

      <section className="max-w-7xl mx-auto px-5 pt-12 pb-6">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-[#6cff32]/30 bg-[#6cff32]/5 px-3 py-1 mb-4">
            <span className="h-1.5 w-1.5 rounded-full bg-[#6cff32] pulse-ring" />
            <span className="text-[11px] font-medium text-[#6cff32] tracking-wide uppercase">Deterministic track record</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-3">
            The <span className="gradient-text">creator ledger</span> for Four.meme.
          </h1>
          <p className="text-white/60 text-base md:text-lg leading-relaxed">
            Every creator wallet FOUR-LIFE has observed, ranked by deterministic trust tier. Graduation rate, median peak holders, and full per-launch evidence — so you can tell at a glance whether a wallet ships tokens that survive, or just ships tokens.
          </p>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-5 pb-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          {(["proven", "emerging", "new_creator", "unproven", "unknown"] as TrustTier[]).map(t => {
            const s = TIER_STYLE[t];
            const count = tierCounts[t] ?? 0;
            return (
              <div key={t} className={`card p-3 border ${s.border}`}>
                <div className={`text-[10px] uppercase tracking-wider ${s.text}`}>{s.label}</div>
                <div className="text-2xl font-bold mt-0.5">{count}</div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-5 pb-4">
        <div className="flex flex-wrap gap-2 items-center">
          <label className="text-[11px] text-white/40 uppercase tracking-wider mr-1">Sort</label>
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:border-white/30"
          >
            {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <label className="text-[11px] text-white/40 uppercase tracking-wider mr-1 ml-2">Tier</label>
          <select
            value={tierFilter}
            onChange={e => setTierFilter(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:border-white/30"
          >
            {TIER_FILTERS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <label className="text-[11px] text-white/40 uppercase tracking-wider mr-1 ml-2">Min launches</label>
          <select
            value={String(minLaunches)}
            onChange={e => setMinLaunches(parseInt(e.target.value, 10))}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:border-white/30"
          >
            {[1, 3, 5, 10].map(n => <option key={n} value={n}>{n}+</option>)}
          </select>
          <div className="flex-1" />
          {data && (
            <div className="text-[11px] text-white/40 font-mono">
              {data.count} of {data.total_creators} creators
            </div>
          )}
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-5 pb-16">
        <div className="card overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-white/40 text-sm">Loading creator ledger…</div>
          ) : error ? (
            <div className="p-8 text-center">
              <div className="text-[#ff494a] mb-2 text-sm">Failed to load: {error}</div>
              <button onClick={fetchLeaderboard} className="btn-pill bg-white/5 hover:bg-white/10 border border-white/10 text-xs">Retry</button>
            </div>
          ) : !data || data.creators.length === 0 ? (
            <div className="p-8 text-center text-white/40 text-sm">
              No creators match the current filters. Try relaxing the minimum-launches threshold or clearing the tier filter.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wider text-white/40 border-b border-white/10">
                    <th className="px-4 py-3 text-left font-medium">Wallet</th>
                    <th className="px-4 py-3 text-left font-medium">Trust tier</th>
                    <th className="px-4 py-3 text-right font-medium">Launches</th>
                    <th className="px-4 py-3 text-right font-medium">Graduations</th>
                    <th className="px-4 py-3 text-right font-medium">Grad rate</th>
                    <th className="px-4 py-3 text-right font-medium">Median holders</th>
                    <th className="px-4 py-3 text-right font-medium">Median curve %</th>
                    <th className="px-4 py-3 text-right font-medium">Last launch</th>
                  </tr>
                </thead>
                <tbody>
                  {data.creators.map(row => (
                    <CreatorRowView key={row.wallet} row={row} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div className="text-[11px] text-white/30 mt-3 font-mono">
          Trust tier thresholds: proven = ≥50% graduation rate + ≥250 median holders across ≥3 launches · emerging = ≥25% grad rate OR ≥40% median curve · new_creator = &lt;3 launches · unproven = otherwise. Deterministic, no LLM.
        </div>
      </section>
    </div>
  );
}
