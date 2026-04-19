"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const API = (process.env.NEXT_PUBLIC_API_URL || "https://four-life.gudman.xyz").replace(/\/$/, "");

// ── Types ──────────────────────────────────────────────────────

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

interface RiskFlag {
  id: string;
  severity: "critical" | "high" | "medium" | "info" | "low";
  metric: string;
  value: number | string;
  threshold: number | string;
  message: string;
}

interface RiskSnapshot {
  token_address: string;
  name: string;
  symbol: string;
  quote_asset: string;
  risk_level: string;
  metrics: {
    whale_concentration: number;
    whale_count: number;
    buy_sell_ratio: number;
    holder_velocity: number;
    holder_count: number;
    age_hours: number;
    curve_progress: number;
    phase: string;
  };
  evidence: RiskFlag[];
  confidence_score: string;
  fallback_used: boolean;
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
    unique_sellers: number;
    buy_sell_ratio: number;
    top_holder_pct: number;
    whale_count: number;
    curve_progress: number;
    holder_velocity: number;
    buy_volume_bnb: number;
    sell_volume_bnb: number;
  };
}

interface HistorySnapshot {
  id: number;
  token_address: string;
  tier: Tier;
  risk_level: string | null;
  metrics: {
    curve_progress_pct: number;
    health_score: number;
    buy_sell_ratio: number;
    holder_velocity: number;
    top_holder_pct: number;
    age_hours: number;
    unique_buyers: number;
  };
  recorded_at: number;
}

interface HistoryResponse {
  token_address: string;
  count: number;
  snapshots: HistorySnapshot[];
}

// ── Helpers ────────────────────────────────────────────────────

const TIER_STYLE: Record<Tier, { bg: string; text: string; border: string; dot: string; label: string }> = {
  graduated: { bg: "bg-purple-500/10", text: "text-purple-300", border: "border-purple-500/40", dot: "bg-purple-400", label: "Graduated" },
  graduation_watch: { bg: "bg-[#00d4ff]/10", text: "text-[#00d4ff]", border: "border-[#00d4ff]/40", dot: "bg-[#00d4ff]", label: "Graduation Watch" },
  healthy: { bg: "bg-[#6cff32]/10", text: "text-[#6cff32]", border: "border-[#6cff32]/40", dot: "bg-[#6cff32]", label: "Healthy" },
  at_risk: { bg: "bg-[#ff494a]/10", text: "text-[#ff494a]", border: "border-[#ff494a]/40", dot: "bg-[#ff494a]", label: "At Risk" },
  observed: { bg: "bg-[#ffd641]/10", text: "text-[#ffd641]", border: "border-[#ffd641]/40", dot: "bg-[#ffd641]", label: "Observed" },
};

const SEVERITY_STYLE: Record<string, string> = {
  critical: "text-[#ff494a] bg-[#ff494a]/10 border-[#ff494a]/30",
  high: "text-[#ff494a] bg-[#ff494a]/10 border-[#ff494a]/30",
  medium: "text-[#ffd641] bg-[#ffd641]/10 border-[#ffd641]/30",
  info: "text-[#00d4ff] bg-[#00d4ff]/10 border-[#00d4ff]/30",
  low: "text-white/60 bg-white/5 border-white/10",
};

function short(addr: string) {
  if (!addr) return "";
  return addr.slice(0, 6) + "…" + addr.slice(-4);
}

function fmt(n: number | undefined, d = 2): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: d });
}

// Extract token address from either pathname (`/launch/0x...`) or `?token=0x...`.
function useTokenAddress(): string | null {
  const [token, setToken] = useState<string | null>(null);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const resolve = () => {
      const parts = window.location.pathname.split("/").filter(Boolean);
      const last = parts[parts.length - 1];
      if (last && /^0x[a-f0-9]{40}$/i.test(last)) {
        setToken(last.toLowerCase());
        return;
      }
      const qp = new URLSearchParams(window.location.search).get("token");
      if (qp && /^0x[a-f0-9]{40}$/i.test(qp)) setToken(qp.toLowerCase());
    };
    const t = setTimeout(resolve, 0);
    return () => clearTimeout(t);
  }, []);
  return token;
}

// ── Components ─────────────────────────────────────────────────

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-white/10 bg-white/[0.03] p-6 ${className}`}>
      {children}
    </div>
  );
}

function BadgeHero({ badge }: { badge: Badge }) {
  const s = TIER_STYLE[badge.tier];
  return (
    <div className={`relative overflow-hidden rounded-2xl border ${s.border} ${s.bg} p-8`}>
      <div className="flex items-center gap-3 mb-3">
        <span className={`h-2 w-2 rounded-full ${s.dot}`} />
        <span className="eyebrow">FOUR-LIFE Certified</span>
      </div>
      <div className={`text-4xl md:text-5xl font-bold ${s.text} mb-3`}>{badge.label}</div>
      <p className="text-sm text-white/70 max-w-xl">{badge.description}</p>
    </div>
  );
}

function WhyTable({ why }: { why: BadgeWhy[] }) {
  if (!why?.length) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-white/40 uppercase tracking-wider">
            <th className="text-left py-2 pr-4">Rule</th>
            <th className="text-left py-2 pr-4">Metric</th>
            <th className="text-left py-2 pr-4">Value</th>
            <th className="text-left py-2 pr-4">Threshold</th>
            <th className="text-left py-2">Fired</th>
          </tr>
        </thead>
        <tbody>
          {why.map((w, i) => (
            <tr key={i} className="border-t border-white/5">
              <td className="py-2 pr-4 font-mono">{w.rule}</td>
              <td className="py-2 pr-4 text-white/60">{w.metric}</td>
              <td className="py-2 pr-4 font-mono">{String(w.value)}</td>
              <td className="py-2 pr-4 font-mono text-white/60">
                {w.operator} {String(w.threshold)}
              </td>
              <td className="py-2">
                <span className={`inline-flex items-center gap-1 ${w.passed ? "text-[#6cff32]" : "text-white/40"}`}>
                  {w.passed ? "✓" : "—"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Metric({ label, value, unit }: { label: string; value: string | number; unit?: string }) {
  return (
    <div>
      <div className="eyebrow text-white/40 mb-1">{label}</div>
      <div className="text-xl font-semibold">
        {value}
        {unit && <span className="text-sm text-white/50 font-normal ml-1">{unit}</span>}
      </div>
    </div>
  );
}

// Encode tier as numeric so we can chart transitions over time.
const TIER_RANK: Record<Tier, number> = {
  at_risk: 1,
  observed: 2,
  healthy: 3,
  graduation_watch: 4,
  graduated: 5,
};

const TIER_RANK_LABEL = ["", "At Risk", "Observed", "Healthy", "Grad Watch", "Graduated"];

function HistoryChart({ snapshots }: { snapshots: HistorySnapshot[] }) {
  if (!snapshots || snapshots.length === 0) {
    return (
      <p className="text-sm text-white/50">
        No history yet. FOUR-LIFE records a snapshot on every tier transition and every hour — come back soon.
      </p>
    );
  }
  // Oldest -> newest for the chart
  const rows = [...snapshots]
    .sort((a, b) => a.recorded_at - b.recorded_at)
    .map((s) => ({
      ts: s.recorded_at * 1000,
      tierRank: TIER_RANK[s.tier] ?? 2,
      tier: s.tier,
      curve: s.metrics?.curve_progress_pct ?? 0,
      health: s.metrics?.health_score ?? 0,
    }));

  const fmtTime = (t: number) => {
    const d = new Date(t);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  };

  return (
    <div className="space-y-4">
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis
              dataKey="ts"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={fmtTime}
              tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }}
              stroke="rgba(255,255,255,0.1)"
            />
            <YAxis
              domain={[1, 5]}
              ticks={[1, 2, 3, 4, 5]}
              tickFormatter={(v) => TIER_RANK_LABEL[v] || ""}
              tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }}
              stroke="rgba(255,255,255,0.1)"
              width={90}
            />
            <Tooltip
              contentStyle={{ background: "#0f1012", border: "1px solid rgba(255,255,255,0.1)", fontSize: 11 }}
              labelFormatter={(v) => new Date(v as number).toLocaleString()}
              formatter={(v, _, p) =>
                p?.dataKey === "tierRank"
                  ? [TIER_RANK_LABEL[v as number] || "", "Tier"]
                  : [v as number, "Tier rank"]
              }
            />
            <Line type="stepAfter" dataKey="tierRank" stroke="#6cff32" strokeWidth={2} dot={{ r: 3, fill: "#6cff32" }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="text-[10px] text-white/40 font-mono">
        {rows.length} snapshot{rows.length === 1 ? "" : "s"} · oldest {fmtTime(rows[0].ts)} · newest {fmtTime(rows[rows.length - 1].ts)}
      </div>
    </div>
  );
}

function RiskEvidence({ risk }: { risk: RiskSnapshot }) {
  if (!risk?.evidence?.length) {
    return (
      <p className="text-sm text-white/50">
        No risk flags above threshold. This token isn&apos;t showing concentration, sell-pressure, or stall signals.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {risk.evidence.map((f, i) => (
        <div key={i} className={`rounded-lg border px-3 py-2 text-xs ${SEVERITY_STYLE[f.severity] || SEVERITY_STYLE.low}`}>
          <div className="flex items-center justify-between gap-3 mb-1">
            <span className="font-semibold uppercase tracking-wider">{f.severity}</span>
            <span className="font-mono text-[10px] text-white/50">{f.metric}</span>
          </div>
          <div className="text-white/80">{f.message}</div>
        </div>
      ))}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────

export default function LaunchPage() {
  const token = useTokenAddress();
  const [badge, setBadge] = useState<BadgeResponse | null>(null);
  const [risk, setRisk] = useState<RiskSnapshot | null>(null);
  const [info, setInfo] = useState<TokenPayload | null>(null);
  const [history, setHistory] = useState<HistorySnapshot[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [b, r, t, h] = await Promise.all([
          fetch(`${API}/api/token/${token}/badge`).then((r) => (r.ok ? r.json() : null)),
          fetch(`${API}/api/token/${token}/risk-snapshot`).then((r) => (r.ok ? r.json() : null)),
          fetch(`${API}/api/tokens/${token}`).then((r) => (r.ok ? r.json() : null)),
          fetch(`${API}/api/token/${token}/history?limit=100`).then((r) => (r.ok ? r.json() : null)),
        ]);
        if (cancelled) return;
        if (!b && !r && !t) {
          setError("Token not found in FOUR-LIFE. Ask the agent to start tracking it.");
        }
        setBadge(b);
        setRisk(r);
        setInfo(t);
        setHistory(((h as HistoryResponse | null)?.snapshots) || []);
      } catch (e) {
        if (!cancelled) setError(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    const timer = setTimeout(load, 0);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [token]);

  if (!token) {
    return (
      <main className="max-w-3xl mx-auto px-5 py-16">
        <h1 className="text-2xl font-bold mb-3">FOUR-LIFE Certified — Token Page</h1>
        <p className="text-white/60 mb-6">
          Share a live trust grade for any Four.meme token. Use URL pattern:
        </p>
        <code className="block bg-black/40 rounded-lg p-4 text-sm text-[#6cff32] mb-6">
          four-life.gudman.xyz/launch/0x&lt;your-token-address&gt;
        </code>
        <Link href="/radar" className="text-[#00d4ff] hover:underline">← Browse the Radar</Link>
      </main>
    );
  }

  return (
    <main className="max-w-5xl mx-auto px-5 py-12">
      <div className="mb-6">
        <Link href="/radar" className="text-xs text-white/40 hover:text-white/70">← Back to Radar</Link>
      </div>

      <div className="mb-2 flex items-center gap-3">
        <h1 className="text-3xl md:text-4xl font-bold">
          {info?.health?.name || "Loading…"}
        </h1>
        {info?.health?.symbol && (
          <span className="text-white/40 text-lg">${info.health.symbol}</span>
        )}
      </div>
      <div className="mb-8 flex items-center gap-3 flex-wrap">
        <a
          href={`https://bscscan.com/address/${token}`}
          target="_blank"
          rel="noreferrer"
          className="font-mono text-xs text-white/50 hover:text-white/80"
        >
          {short(token)} ↗ BscScan
        </a>
        <a
          href={`https://four.meme/token/${token}`}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-[#00d4ff] hover:underline"
        >
          View on Four.meme ↗
        </a>
      </div>

      {loading && <div className="text-white/50 text-sm">Fetching live grade…</div>}

      {error && (
        <Card>
          <p className="text-sm text-white/70">{error}</p>
        </Card>
      )}

      {badge?.badge && (
        <div className="space-y-6">
          <BadgeHero badge={badge.badge} />

          <Card>
            <div className="eyebrow mb-4">Live metrics</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Metric label="Phase" value={info?.health?.phase || "—"} />
              <Metric label="Holders" value={fmt(risk?.metrics?.holder_count, 0)} />
              <Metric label="Curve progress" value={fmt(info?.health?.curve_progress, 1)} unit="%" />
              <Metric label="Top holder" value={fmt(info?.health?.top_holder_pct, 1)} unit="%" />
              <Metric label="Buy/sell ratio" value={fmt(info?.health?.buy_sell_ratio, 2)} />
              <Metric label="Holder velocity" value={fmt(info?.health?.holder_velocity, 1)} unit="/h" />
              <Metric label="Whale count" value={fmt(info?.health?.whale_count, 0)} />
              <Metric label="Age" value={fmt(info?.health?.age_hours, 1)} unit="h" />
            </div>
          </Card>

          <Card>
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
              <div className="eyebrow">Why this grade</div>
              <div className="text-[11px] text-white/40">
                Deterministic rules. No LLM in trust path. Version {badge.badge.version || "1.0"}.
              </div>
            </div>
            <WhyTable why={badge.badge.why} />
          </Card>

          {risk && (
            <Card>
              <div className="eyebrow mb-4">Risk evidence</div>
              <RiskEvidence risk={risk} />
            </Card>
          )}

          <Card>
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
              <div className="eyebrow">Tier history</div>
              <div className="text-[11px] text-white/40">
                Every tick the agent decides: should the tier change? Every transition is on this timeline.
              </div>
            </div>
            <HistoryChart snapshots={history} />
          </Card>

          <Card className="bg-gradient-to-r from-white/[0.02] to-white/[0.05]">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div>
                <div className="eyebrow mb-1">Embed this badge</div>
                <div className="text-xs text-white/60">
                  Add the Certified badge to any dashboard or landing page — recomputed live from on-chain data.
                </div>
              </div>
              <Link
                href="/embed"
                className="btn-primary text-xs px-4 py-2"
              >
                Embed docs →
              </Link>
            </div>
          </Card>
        </div>
      )}
    </main>
  );
}
