"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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

interface BadgeWhy {
  rule: string;
  metric: string;
  value: string | number | boolean;
  threshold: string | number | boolean;
  operator: string;
  passed: boolean;
}

interface Badge {
  tier: "graduated" | "graduation_watch" | "healthy" | "at_risk" | "observed";
  label: string;
  description: string;
  why: BadgeWhy[];
  metrics_snapshot: Record<string, unknown>;
  version: string;
}

interface RadarEntry {
  token_address: string;
  name: string;
  symbol: string;
  quote_asset: string;
  graduation_target: number;
  graduation_target_unit: string;
  graduation_progress_value: number;
  holders: number;
  curve_progress: number;
  volume_quote: number;
  volume_bnb: number;
  increase_pct: number;
  health_score: number;
  graduation_probability: number;
  holder_velocity: number;
  confidence_score: "low" | "medium" | "high";
  status: string;
  fourmeme_url: string;
}

interface RadarResponse {
  radar: RadarEntry[];
  total_scanned: number;
  filters: { quote_asset: string; min_confidence: string; sort_by: string };
  known_quote_assets: string[];
  model_version: string;
  last_updated_at: number;
  timestamp: number;
  powered_by: string;
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

interface ChecklistItem {
  phase: string;
  priority: "critical" | "high" | "medium" | "low";
  title: string;
  rationale: string;
  metric: string;
  value: unknown;
}

interface BadgeResponse {
  token_address: string;
  badge: Badge;
  data_source: string;
  model_version: string;
  last_updated_at: number;
}

interface HistorySnapshot {
  id: number;
  token_address: string;
  tier: Badge["tier"];
  risk_level: string | null;
  metrics: Record<string, unknown>;
  why: BadgeWhy[];
  data_source: string | null;
  recorded_at: number;
}

interface HistoryResponse {
  token_address: string;
  count: number;
  snapshots: HistorySnapshot[];
}

// ── Helpers ────────────────────────────────────────────────────

const TIER_STYLE: Record<Badge["tier"], { bg: string; text: string; border: string; dot: string; label: string }> = {
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

function ago(ts: number) {
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

// Derive a badge tier from radar entry metrics (mirrors the backend rule; used before
// we fetch the full /badge endpoint so cards show tier instantly).
function tierFromEntry(e: RadarEntry): Badge["tier"] {
  if (e.curve_progress >= 100) return "graduated";
  if (e.curve_progress >= 70 && e.confidence_score === "high" && e.increase_pct >= 0) return "graduation_watch";
  if (e.increase_pct < -50) return "at_risk";
  return "observed";
}

// ── Components ─────────────────────────────────────────────────

function BadgePill({ tier, label, size = "md" }: { tier: Badge["tier"]; label?: string; size?: "sm" | "md" }) {
  const s = TIER_STYLE[tier];
  const pad = size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-[11px]";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-semibold tracking-wide ${pad} ${s.bg} ${s.text} ${s.border}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      <span className="uppercase">{label || s.label}</span>
    </span>
  );
}

function ConfidenceChip({ level }: { level: string }) {
  const map: Record<string, string> = {
    high: "bg-[#6cff32]/10 text-[#6cff32] border-[#6cff32]/30",
    medium: "bg-[#ffd641]/10 text-[#ffd641] border-[#ffd641]/30",
    low: "bg-white/5 text-white/40 border-white/10",
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${map[level] || map.low}`}>
      {level.toUpperCase()} CONF
    </span>
  );
}

function Progress({ value, max = 100 }: { value: number; max?: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="progress-track h-1.5 w-full">
      <div className="progress-fill h-full bg-gradient-to-r from-[#6cff32] to-[#00d4ff]" style={{ width: `${pct}%` }} />
    </div>
  );
}

function TokenCard({ entry, onSelect }: { entry: RadarEntry; onSelect: () => void }) {
  const tier = tierFromEntry(entry);
  return (
    <button
      onClick={onSelect}
      className="card group p-5 text-left w-full flex flex-col gap-4 hover:-translate-y-0.5 transition-transform duration-200 cursor-pointer"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-base font-semibold truncate">{entry.name || "Unnamed"}</span>
            <span className="text-xs text-white/40">{entry.symbol}</span>
          </div>
          <div className="flex items-center gap-2">
            <BadgePill tier={tier} />
            <ConfidenceChip level={entry.confidence_score} />
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-xl font-bold gradient-text">{entry.graduation_probability.toFixed(0)}%</div>
          <div className="text-[10px] uppercase tracking-wide text-white/40">Grad prob</div>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between text-[11px] text-white/50 mb-1">
          <span>Curve progress</span>
          <span className="font-mono text-white/80">
            {entry.graduation_progress_value > 0
              ? `${entry.graduation_progress_value.toFixed(2)} / ${entry.graduation_target} ${entry.quote_asset}`
              : `${entry.curve_progress.toFixed(1)}%`}
          </span>
        </div>
        <Progress value={entry.curve_progress} />
      </div>

      <div className="grid grid-cols-3 gap-2 text-[11px]">
        <div>
          <div className="text-white/40">Holders</div>
          <div className="font-semibold">{entry.holders.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-white/40">Health</div>
          <div className="font-semibold">{entry.health_score.toFixed(0)}</div>
        </div>
        <div>
          <div className="text-white/40">24h Δ</div>
          <div className={`font-semibold ${entry.increase_pct > 0 ? "text-[#6cff32]" : entry.increase_pct < 0 ? "text-[#ff494a]" : "text-white/60"}`}>
            {entry.increase_pct > 0 ? "+" : ""}{entry.increase_pct.toFixed(1)}%
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between text-[10px] text-white/30">
        <span className="font-mono">{short(entry.token_address)}</span>
        <span className="text-white/40 group-hover:text-[#6cff32] transition-colors">Open →</span>
      </div>
    </button>
  );
}

function WhyTable({ why }: { why: BadgeWhy[] }) {
  return (
    <div className="rounded-lg border border-white/10 overflow-hidden">
      <div className="grid grid-cols-12 gap-2 bg-white/5 px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-white/50">
        <div className="col-span-3">Rule</div>
        <div className="col-span-3">Metric</div>
        <div className="col-span-2">Value</div>
        <div className="col-span-1 text-center">Op</div>
        <div className="col-span-2">Threshold</div>
        <div className="col-span-1 text-right">Pass</div>
      </div>
      {why.map((r, i) => (
        <div
          key={i}
          className={`grid grid-cols-12 gap-2 px-3 py-2 text-xs border-t border-white/5 ${r.passed ? "" : "opacity-60"}`}
        >
          <div className="col-span-3 font-mono text-white/80">{r.rule}</div>
          <div className="col-span-3 text-white/60">{r.metric}</div>
          <div className="col-span-2 font-mono">{String(r.value)}</div>
          <div className="col-span-1 text-center text-white/40">{r.operator}</div>
          <div className="col-span-2 font-mono text-white/60">{String(r.threshold)}</div>
          <div className="col-span-1 text-right">
            {r.passed ? <span className="text-[#6cff32]">✓</span> : <span className="text-[#ff494a]">✗</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

// Trust axis: higher = more trustworthy. at_risk sits below observed on purpose.
const TIER_ORDINAL: Record<Badge["tier"], number> = {
  at_risk: 0,
  observed: 1,
  healthy: 2,
  graduation_watch: 3,
  graduated: 4,
};

const TIER_LINE_COLOR = "#6cff32";

function formatClockShort(ts: number): string {
  const d = new Date(ts * 1000);
  const hh = d.getHours().toString().padStart(2, "0");
  const mm = d.getMinutes().toString().padStart(2, "0");
  const mo = (d.getMonth() + 1).toString().padStart(2, "0");
  const da = d.getDate().toString().padStart(2, "0");
  return `${mo}/${da} ${hh}:${mm}`;
}

function TimelineSection({ snapshots }: { snapshots: HistorySnapshot[] }) {
  const chartData = useMemo(() => {
    const ordered = [...snapshots].sort((a, b) => a.recorded_at - b.recorded_at);
    return ordered.map((s) => ({
      t: s.recorded_at,
      label: formatClockShort(s.recorded_at),
      ordinal: TIER_ORDINAL[s.tier] ?? 1,
      tier: s.tier,
    }));
  }, [snapshots]);

  const transitions = useMemo(() => {
    const ordered = [...snapshots].sort((a, b) => a.recorded_at - b.recorded_at);
    const out: { from: Badge["tier"]; to: Badge["tier"]; at: number; why: BadgeWhy[] }[] = [];
    let prev: Badge["tier"] | null = null;
    for (const s of ordered) {
      if (prev !== null && s.tier !== prev) {
        out.push({ from: prev, to: s.tier, at: s.recorded_at, why: s.why });
      }
      prev = s.tier;
    }
    return out.reverse(); // newest first
  }, [snapshots]);

  if (snapshots.length === 0) {
    return (
      <section>
        <h3 className="text-xs uppercase tracking-wider text-white/40 mb-3">Trust Timeline</h3>
        <div className="card p-3 text-xs text-white/50">
          No snapshots yet — a timeline will build up as FOUR-LIFE re-evaluates this token.
        </div>
      </section>
    );
  }

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs uppercase tracking-wider text-white/40">Trust Timeline</h3>
        <div className="text-[10px] text-white/30 font-mono">{snapshots.length} snapshots</div>
      </div>

      <div className="card p-3 mb-3" style={{ height: 160 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
            <CartesianGrid strokeDasharray="2 4" stroke="rgba(255,255,255,0.06)" />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 10, fill: "rgba(255,255,255,0.4)" }}
              tickLine={false}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              minTickGap={24}
            />
            <YAxis
              type="number"
              domain={[-0.2, 4.2]}
              ticks={[0, 1, 2, 3, 4]}
              tick={{ fontSize: 9, fill: "rgba(255,255,255,0.4)" }}
              tickFormatter={(v) => {
                const entry = (Object.entries(TIER_ORDINAL) as [Badge["tier"], number][]).find(
                  ([, n]) => n === v,
                );
                return entry ? TIER_STYLE[entry[0]].label : "";
              }}
              tickLine={false}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              width={110}
            />
            <Tooltip
              contentStyle={{
                background: "#0f1012",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 8,
                fontSize: 11,
              }}
              labelStyle={{ color: "rgba(255,255,255,0.6)" }}
              formatter={(_v, _n, p: { payload?: { tier: Badge["tier"] } }) =>
                p?.payload?.tier ? [TIER_STYLE[p.payload.tier].label, "Tier"] : ["", ""]
              }
            />
            <Line
              type="stepAfter"
              dataKey="ordinal"
              stroke={TIER_LINE_COLOR}
              strokeWidth={2}
              dot={{ r: 3, fill: TIER_LINE_COLOR, strokeWidth: 0 }}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {transitions.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[10px] uppercase tracking-wider text-white/30">Transitions</div>
          {transitions.slice(0, 8).map((t, i) => (
            <div key={i} className="card px-3 py-2 text-xs">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`rounded-full border px-1.5 py-0.5 text-[9px] font-semibold uppercase ${TIER_STYLE[t.from].border} ${TIER_STYLE[t.from].text}`}>
                    {TIER_STYLE[t.from].label}
                  </span>
                  <span className="text-white/30">→</span>
                  <span className={`rounded-full border px-1.5 py-0.5 text-[9px] font-semibold uppercase ${TIER_STYLE[t.to].border} ${TIER_STYLE[t.to].text}`}>
                    {TIER_STYLE[t.to].label}
                  </span>
                </div>
                <div className="text-[10px] text-white/40 font-mono shrink-0">{ago(t.at)}</div>
              </div>
              {t.why.length > 0 && (
                <div className="text-[10px] text-white/50 mt-1 truncate">
                  {t.why.filter(w => w.passed).slice(0, 2).map(w => w.rule).join(" · ") || "—"}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function DetailDrawer({
  entry,
  onClose,
}: {
  entry: RadarEntry;
  onClose: () => void;
}) {
  const [badge, setBadge] = useState<BadgeResponse | null>(null);
  const [risk, setRisk] = useState<RiskSnapshot | null>(null);
  const [checklist, setChecklist] = useState<ChecklistItem[] | null>(null);
  const [history, setHistory] = useState<HistorySnapshot[]>([]);
  const [tracking, setTracking] = useState(false);

  useEffect(() => {
    const a = entry.token_address;
    setBadge(null); setRisk(null); setChecklist(null); setHistory([]); setTracking(false);
    // The /badge and /risk-snapshot calls record snapshots server-side, so we kick off
    // /history slightly after to include the freshly-written row on first open.
    fetch(`${API}/api/token/${a}/badge`).then(r => r.json()).then(setBadge).catch(() => {});
    fetch(`${API}/api/token/${a}/risk-snapshot`).then(r => r.ok ? r.json() : null).then(d => { if (d && d.evidence) setRisk(d); }).catch(() => {});
    fetch(`${API}/api/token/${a}/operator-checklist`).then(r => r.ok ? r.json() : null).then(d => { if (d && d.checklist) setChecklist(d.checklist); }).catch(() => {});
    const tid = window.setTimeout(() => {
      fetch(`${API}/api/token/${a}/history?limit=100`)
        .then(r => r.ok ? r.json() as Promise<HistoryResponse> : null)
        .then(d => { if (d?.snapshots) setHistory(d.snapshots); })
        .catch(() => {});
    }, 250);
    return () => window.clearTimeout(tid);
  }, [entry.token_address]);

  const track = useCallback(async () => {
    setTracking(true);
    try {
      await fetch(`${API}/api/agent/track`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token_address: entry.token_address,
          name: entry.name,
          symbol: entry.symbol,
          quote_asset: entry.quote_asset,
        }),
      });
    } finally {
      setTracking(false);
    }
  }, [entry]);

  const tier = badge?.badge?.tier ?? tierFromEntry(entry);
  const shareUrl = `https://four-life.gudman.xyz/radar?token=${entry.token_address}`;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
      />
      <div className="relative w-full max-w-xl h-full bg-[#0f1012] border-l border-white/10 overflow-y-auto">
        <div className="sticky top-0 z-10 bg-[#0f1012]/95 backdrop-blur-sm border-b border-white/10 px-5 py-4 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold truncate max-w-[240px]">{entry.name}</h2>
              <span className="text-xs text-white/40">{entry.symbol}</span>
            </div>
            <div className="text-[11px] font-mono text-white/30 mt-1">{entry.token_address}</div>
          </div>
          <button onClick={onClose} className="text-white/40 hover:text-white transition-colors p-2">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M5 5L15 15M5 15L15 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
          </button>
        </div>

        <div className="px-5 py-5 space-y-6">
          {/* Badge section */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <BadgePill tier={tier} size="md" />
              <ConfidenceChip level={entry.confidence_score} />
            </div>
            <p className="text-sm text-white/70 mb-4">{badge?.badge?.description || TIER_STYLE[tier]?.label}</p>
            {badge?.badge?.why && <WhyTable why={badge.badge.why} />}
          </section>

          {/* Risk snapshot */}
          {risk && (
            <section>
              <h3 className="text-xs uppercase tracking-wider text-white/40 mb-3">Risk Snapshot</h3>
              <div className="grid grid-cols-4 gap-2 mb-3">
                <div className="card p-2.5 text-center">
                  <div className="text-[10px] text-white/40 uppercase">Risk Level</div>
                  <div className="text-sm font-semibold uppercase mt-0.5">{risk.risk_level}</div>
                </div>
                <div className="card p-2.5 text-center">
                  <div className="text-[10px] text-white/40 uppercase">Top Holder</div>
                  <div className="text-sm font-semibold mt-0.5">{risk.metrics.whale_concentration.toFixed(1)}%</div>
                </div>
                <div className="card p-2.5 text-center">
                  <div className="text-[10px] text-white/40 uppercase">Whales</div>
                  <div className="text-sm font-semibold mt-0.5">{risk.metrics.whale_count}</div>
                </div>
                <div className="card p-2.5 text-center">
                  <div className="text-[10px] text-white/40 uppercase">Buy/Sell</div>
                  <div className="text-sm font-semibold mt-0.5">{risk.metrics.buy_sell_ratio.toFixed(2)}</div>
                </div>
              </div>
              {risk.evidence.length > 0 && (
                <div className="space-y-2">
                  {risk.evidence.map((ev, i) => (
                    <div key={i} className={`rounded-lg border px-3 py-2 text-xs ${SEVERITY_STYLE[ev.severity] || SEVERITY_STYLE.low}`}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold uppercase tracking-wide text-[10px]">{ev.severity}</span>
                        <span className="font-mono text-white/50">{ev.metric}: {String(ev.value)}</span>
                      </div>
                      <div>{ev.message}</div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* Trust timeline */}
          <TimelineSection snapshots={history} />

          {/* Operator checklist */}
          {checklist && checklist.length > 0 && (
            <section>
              <h3 className="text-xs uppercase tracking-wider text-white/40 mb-3">72h Operator Checklist</h3>
              <div className="space-y-2">
                {checklist.map((it, i) => (
                  <div key={i} className="card p-3">
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <div className="text-sm font-semibold">{it.title}</div>
                      <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${SEVERITY_STYLE[it.priority] || SEVERITY_STYLE.low}`}>
                        {it.priority}
                      </span>
                    </div>
                    <div className="text-xs text-white/60 mb-1">{it.rationale}</div>
                    <div className="text-[10px] text-white/40">Phase: {it.phase}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Actions */}
          <section className="flex flex-col gap-2 pt-2">
            <a
              href={entry.fourmeme_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-pill bg-white/5 hover:bg-white/10 border border-white/10 text-center"
            >
              Open on four.meme →
            </a>
            <button
              onClick={track}
              disabled={tracking}
              className="btn-pill bg-[#6cff32] hover:bg-[#6cff32]/90 text-black disabled:opacity-50"
            >
              {tracking ? "Tracking…" : "Track with FOUR-LIFE"}
            </button>
            <button
              onClick={() => { navigator.clipboard?.writeText(shareUrl); }}
              className="btn-pill bg-transparent hover:bg-white/5 border border-white/10 text-white/60"
            >
              Copy shareable link
            </button>
          </section>

          {/* Meta */}
          <section className="pt-4 border-t border-white/5 text-[11px] text-white/30 font-mono space-y-1">
            <div>Quote asset: {entry.quote_asset}</div>
            <div>Target: {entry.graduation_target} {entry.quote_asset}</div>
            <div>Model: {badge?.model_version || "—"}</div>
            <div>Source: {badge?.data_source || "—"}</div>
          </section>
        </div>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────

export default function RadarPage() {
  const [data, setData] = useState<RadarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [quote, setQuote] = useState<string>("all");
  const [minConf, setMinConf] = useState<string>("low");
  const [sortBy, setSortBy] = useState<string>("graduation_probability");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<RadarEntry | null>(null);

  const fetchRadar = useCallback(async () => {
    try {
      const url = `${API}/api/graduation-radar?limit=60&quote_asset=${encodeURIComponent(quote)}&min_confidence=${encodeURIComponent(minConf)}&sort_by=${encodeURIComponent(sortBy)}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: RadarResponse = await res.json();
      setData(json);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load radar");
    } finally {
      setLoading(false);
    }
  }, [quote, minConf, sortBy]);

  useEffect(() => {
    fetchRadar();
    const id = setInterval(fetchRadar, 30_000);
    return () => clearInterval(id);
  }, [fetchRadar]);

  // Deep-link support: ?token=0x… opens the drawer
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const addr = params.get("token");
    if (addr && data) {
      const found = data.radar.find(r => r.token_address.toLowerCase() === addr.toLowerCase());
      if (found) setSelected(found);
    }
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = search.toLowerCase();
    if (!q) return data.radar;
    return data.radar.filter(
      r =>
        r.name?.toLowerCase().includes(q) ||
        r.symbol?.toLowerCase().includes(q) ||
        r.token_address.toLowerCase().includes(q),
    );
  }, [data, search]);

  const tierCounts = useMemo(() => {
    const counts = { graduated: 0, graduation_watch: 0, healthy: 0, at_risk: 0, observed: 0 };
    filtered.forEach(e => { counts[tierFromEntry(e)] += 1; });
    return counts;
  }, [filtered]);

  return (
    <div className="min-h-screen bg-[#0f1012] text-white bg-grid">
      {/* Header */}
      <header className="border-b border-white/5 sticky top-0 z-30 bg-[#0f1012]/90 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-5 py-4 flex items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-2 group">
            <span className="h-8 w-8 rounded-lg bg-gradient-to-br from-[#6cff32] to-[#00d4ff] flex items-center justify-center font-bold text-black">4</span>
            <div>
              <div className="text-sm font-semibold">FOUR-LIFE</div>
              <div className="text-[10px] text-white/40 uppercase tracking-wider">Certified Radar</div>
            </div>
          </Link>
          <div className="flex items-center gap-2">
            {data && (
              <span className="text-[11px] text-white/40 hidden md:block">
                Updated {ago(data.last_updated_at)} · model {data.model_version}
              </span>
            )}
            <Link href="/creators" className="btn-pill bg-white/5 hover:bg-white/10 border border-white/10 text-xs">Creators</Link>
            <a
              href="https://github.com/Ridwannurudeen/four-life"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-pill bg-transparent hover:bg-white/5 border border-white/10 text-white/70 text-xs"
            >
              GitHub
            </a>
            <Link href="/" className="btn-pill bg-white/5 hover:bg-white/10 border border-white/10 text-xs">Dashboard</Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-5 pt-12 pb-6">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-[#6cff32]/30 bg-[#6cff32]/5 px-3 py-1 mb-4">
            <span className="h-1.5 w-1.5 rounded-full bg-[#6cff32] pulse-ring" />
            <span className="text-[11px] font-medium text-[#6cff32] tracking-wide uppercase">Live — auto-refresh 30s</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-3">
            The <span className="gradient-text">trust layer</span> for Four.meme launches.
          </h1>
          <p className="text-white/60 text-base md:text-lg leading-relaxed">
            Every active Four.meme token, graded deterministically. FOUR-LIFE Certified tiers are computed from raw on-chain metrics with a full rule trace — no LLM in the trust path. Pair-aware graduation targets sourced live from Four.meme&apos;s config.
          </p>
        </div>
      </section>

      {/* Tier summary */}
      <section className="max-w-7xl mx-auto px-5 pb-2">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          {(Object.keys(TIER_STYLE) as Badge["tier"][]).map(tier => (
            <div key={tier} className={`card p-3 border ${TIER_STYLE[tier].border}`}>
              <div className="flex items-center justify-between">
                <BadgePill tier={tier} size="sm" />
                <span className="text-lg font-bold">{tierCounts[tier]}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Filters */}
      <section className="max-w-7xl mx-auto px-5 pt-6 pb-4">
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            placeholder="Search name, symbol, or address…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="flex-1 min-w-[240px] card px-4 py-2 text-sm bg-[#1a1b1f] border-white/10 focus:border-[#6cff32]/40 outline-none"
          />
          <select
            value={quote}
            onChange={e => setQuote(e.target.value)}
            className="card px-3 py-2 text-sm bg-[#1a1b1f] border-white/10 cursor-pointer"
          >
            <option value="all">All quote assets</option>
            {(data?.known_quote_assets || ["BNB", "USD1", "USDT", "USDC"]).map(a => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
          <select
            value={minConf}
            onChange={e => setMinConf(e.target.value)}
            className="card px-3 py-2 text-sm bg-[#1a1b1f] border-white/10 cursor-pointer"
          >
            <option value="low">Any confidence</option>
            <option value="medium">Medium+</option>
            <option value="high">High only</option>
          </select>
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value)}
            className="card px-3 py-2 text-sm bg-[#1a1b1f] border-white/10 cursor-pointer"
          >
            <option value="graduation_probability">Sort: graduation probability</option>
            <option value="health_score">Sort: health score</option>
            <option value="curve_progress">Sort: curve progress</option>
            <option value="holder_velocity">Sort: holder velocity</option>
          </select>
        </div>
      </section>

      {/* Grid */}
      <section className="max-w-7xl mx-auto px-5 pb-20">
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="shimmer h-48 rounded-2xl" />
            ))}
          </div>
        )}

        {error && !data && (
          <div className="card p-8 text-center">
            <div className="text-[#ff494a] font-semibold mb-2">Couldn&apos;t reach the FOUR-LIFE API</div>
            <div className="text-sm text-white/50 mb-4">{error}</div>
            <button onClick={fetchRadar} className="btn-pill bg-white/5 hover:bg-white/10 border border-white/10">Retry</button>
          </div>
        )}

        {data && filtered.length === 0 && (
          <div className="card p-8 text-center">
            <div className="font-semibold mb-1">No tokens match your filters</div>
            <div className="text-sm text-white/50">Try broadening confidence or quote asset.</div>
          </div>
        )}

        {data && filtered.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 animate-fade-up">
            {filtered.map(e => (
              <TokenCard key={e.token_address} entry={e} onSelect={() => setSelected(e)} />
            ))}
          </div>
        )}
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-10 px-5 text-center">
        <div className="max-w-3xl mx-auto text-sm text-white/40 space-y-2">
          <div>
            FOUR-LIFE Certified is deterministic, auditable, and open-source. Every badge includes the exact rules that fired.
          </div>
          <div className="flex items-center justify-center gap-3 pt-2 text-[11px]">
            <a href="https://github.com/Ridwannurudeen/four-life" target="_blank" rel="noopener noreferrer" className="hover:text-white">GitHub</a>
            <span>·</span>
            <a href={`${API}/api/dgrid/stats`} target="_blank" rel="noopener noreferrer" className="hover:text-white">DGrid Stats</a>
            <span>·</span>
            <a href={`${API}/api/identity`} target="_blank" rel="noopener noreferrer" className="hover:text-white">ERC-8004 Identity</a>
            <span>·</span>
            <a href={`${API}/api/platform/cohorts`} target="_blank" rel="noopener noreferrer" className="hover:text-white">Cohorts</a>
          </div>
        </div>
      </footer>

      {selected && <DetailDrawer entry={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
