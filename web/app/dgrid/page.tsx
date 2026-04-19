"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

const API = (process.env.NEXT_PUBLIC_API_URL || "https://four-life.gudman.xyz").replace(/\/$/, "");

// ── Types ──────────────────────────────────────────────────────

interface Stats {
  llm_provider: string;
  session_started_at: number;
  uptime_seconds: number;
  providers_configured: { dgrid: boolean; anthropic: boolean; openai: boolean };
  primary_order: string[];
  default_dgrid_model: string;
  task_model_map: Record<string, string>;
  last_provider: string;
  last_model: string;
  last_task: string;
  last_dgrid_error: string | null;
  fallback_events: number;
  total_calls: number;
  dgrid_calls: number;
  dgrid_share: number;
  dgrid_tokens: { prompt: number; completion: number; total: number };
  usage_by_provider: Record<string, number>;
  usage_by_task: Record<string, number>;
  usage_by_model: Record<string, number>;
}

interface Health {
  status: "green" | "amber" | "red";
  dgrid_configured: boolean;
  primary_model: string;
  last_dgrid_success_ts: number | null;
  last_provider: string;
  last_dgrid_error: string | null;
  dgrid_calls: number;
  dgrid_share: number;
  fallback_events: number;
}

interface TraceEntry {
  ts: number;
  provider: "dgrid" | "anthropic" | "openai";
  model: string;
  task: string;
  latency_ms: number;
  fallback_depth: number;
  success: boolean;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  error: string | null;
}

interface ProbeResult {
  ok: boolean;
  provider?: string;
  model?: string;
  latency_ms?: number;
  response?: string;
  error?: string;
  usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
}

interface CompareRow {
  model: string;
  ok: boolean;
  latency_ms: number;
  response?: string;
  error?: string;
  usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
}

interface CompareResult {
  prompt: string;
  results: CompareRow[];
}

// ── Helpers ────────────────────────────────────────────────────

const PROVIDER_STYLE: Record<string, { dot: string; text: string; bg: string; border: string }> = {
  dgrid: { dot: "bg-[#6cff32]", text: "text-[#6cff32]", bg: "bg-[#6cff32]/10", border: "border-[#6cff32]/30" },
  anthropic: { dot: "bg-orange-400", text: "text-orange-300", bg: "bg-orange-500/10", border: "border-orange-500/30" },
  openai: { dot: "bg-[#00d4ff]", text: "text-[#00d4ff]", bg: "bg-[#00d4ff]/10", border: "border-[#00d4ff]/30" },
};

const HEALTH_STYLE: Record<Health["status"], { dot: string; label: string; tint: string }> = {
  green: { dot: "bg-[#6cff32]", label: "DGrid live", tint: "text-[#6cff32]" },
  amber: { dot: "bg-[#ffd641]", label: "DGrid degraded", tint: "text-[#ffd641]" },
  red: { dot: "bg-[#ff494a]", label: "DGrid offline", tint: "text-[#ff494a]" },
};

function ago(ts: number, now: number) {
  const s = Math.max(0, now - ts);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-white/10 bg-white/[0.02] p-6 ${className}`}>{children}</div>;
}

function Pill({ provider }: { provider: string }) {
  const s = PROVIDER_STYLE[provider] || PROVIDER_STYLE.openai;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${s.bg} ${s.text} ${s.border}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {provider}
    </span>
  );
}

function Stat({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: string }) {
  return (
    <div>
      <div className="eyebrow text-white/40 mb-1">{label}</div>
      <div className={`text-2xl font-semibold ${accent || "text-white"}`}>{value}</div>
      {sub && <div className="text-[11px] text-white/40 mt-0.5">{sub}</div>}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────

export default function DGridPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [trace, setTrace] = useState<TraceEntry[]>([]);
  const [probe, setProbe] = useState<ProbeResult | null>(null);
  const [probing, setProbing] = useState(false);
  const [compareInput, setCompareInput] = useState("Describe a meme token launch in 20 words.");
  const [compare, setCompare] = useState<CompareResult | null>(null);
  const [comparing, setComparing] = useState(false);
  const [now, setNow] = useState(Math.floor(Date.now() / 1000));

  const reload = useCallback(async () => {
    try {
      const [s, h, t] = await Promise.all([
        fetch(`${API}/api/dgrid/stats`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${API}/api/dgrid/health`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${API}/api/dgrid/trace?limit=20`).then((r) => (r.ok ? r.json() : null)),
      ]);
      setStats(s);
      setHealth(h);
      setTrace(t?.trace || []);
      setNow(Math.floor(Date.now() / 1000));
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    const initial = setTimeout(reload, 0);
    const iv = setInterval(reload, 10_000);
    return () => {
      clearTimeout(initial);
      clearInterval(iv);
    };
  }, [reload]);

  const runProbe = async () => {
    setProbing(true);
    setProbe(null);
    try {
      const res = await fetch(`${API}/api/dgrid/probe`, { method: "POST" });
      const body: ProbeResult = await res.json();
      setProbe(body);
      reload();
    } catch (e) {
      setProbe({ ok: false, error: String(e) });
    } finally {
      setProbing(false);
    }
  };

  const runCompare = async () => {
    setComparing(true);
    setCompare(null);
    try {
      const res = await fetch(`${API}/api/dgrid/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: compareInput,
          models: [
            "google/gemini-2.5-flash",
            "anthropic/claude-sonnet-4.5",
            "openai/gpt-4o-mini",
          ],
          max_tokens: 120,
        }),
      });
      const body: CompareResult = await res.json();
      setCompare(body);
      reload();
    } catch (e) {
      setCompare({ prompt: compareInput, results: [{ model: "error", ok: false, latency_ms: 0, error: String(e) }] });
    } finally {
      setComparing(false);
    }
  };

  const sharePct = useMemo(() => Math.round((stats?.dgrid_share || 0) * 100), [stats]);
  const healthStyle = health ? HEALTH_STYLE[health.status] : HEALTH_STYLE.red;

  return (
    <main className="max-w-5xl mx-auto px-5 py-14">
      <div className="mb-6">
        <Link href="/" className="text-xs text-white/40 hover:text-white/70">← Home</Link>
      </div>

      {/* Hero */}
      <div className="mb-10 max-w-3xl">
        <div className="eyebrow mb-3">Powered by DGrid AI Gateway</div>
        <h1 className="text-4xl md:text-5xl font-bold mb-3">
          FOUR-LIFE runs on DGrid.
        </h1>
        <p className="text-white/60 leading-relaxed text-lg">
          Every LLM decision the agent makes — narrative analysis, content drafts, risk prose, vision — routes through{" "}
          <span className="text-[#6cff32] font-semibold">DGrid&apos;s unified AI Gateway</span>. One API, one auth, one
          audit trail, across every model. If DGrid ever has a hiccup, a resilient fallback chain keeps the agent
          alive — but DGrid leads.
        </p>
      </div>

      {/* Health rail */}
      <Card className="mb-6">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <span className={`inline-flex h-3 w-3 rounded-full ${healthStyle.dot} ${health?.status === "green" ? "animate-pulse" : ""}`} />
            <div>
              <div className={`text-lg font-semibold ${healthStyle.tint}`}>{healthStyle.label}</div>
              <div className="text-[11px] text-white/40 font-mono">
                primary = {stats?.default_dgrid_model || "—"} · last_provider = {health?.last_provider || "—"}
              </div>
            </div>
          </div>
          <button
            onClick={runProbe}
            disabled={probing}
            className="btn-pill text-xs bg-[#6cff32]/10 text-[#6cff32] border border-[#6cff32]/30 hover:bg-[#6cff32]/20 disabled:opacity-50"
          >
            {probing ? "probing…" : "probe DGrid now →"}
          </button>
        </div>
        {probe && (
          <div className={`mt-4 rounded-lg border px-3 py-2 text-xs ${probe.ok ? "border-[#6cff32]/40 bg-[#6cff32]/5 text-[#6cff32]" : "border-[#ff494a]/40 bg-[#ff494a]/5 text-[#ff494a]"}`}>
            {probe.ok ? (
              <div>
                <span className="font-semibold">DGrid served in {probe.latency_ms}ms</span>
                <span className="ml-2 text-white/60">· {probe.model}</span>
                {probe.response && <span className="ml-2 text-white/40">→ &quot;{probe.response}&quot;</span>}
              </div>
            ) : (
              <div className="break-all">Probe failed: {probe.error}</div>
            )}
          </div>
        )}
      </Card>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <Card>
          <Stat
            label="DGrid share"
            value={`${sharePct}%`}
            sub={`${stats?.dgrid_calls ?? 0} of ${stats?.total_calls ?? 0} calls`}
            accent="text-[#6cff32]"
          />
        </Card>
        <Card>
          <Stat label="Total LLM calls" value={stats?.total_calls ?? "—"} sub="since service boot" />
        </Card>
        <Card>
          <Stat
            label="DGrid tokens"
            value={stats?.dgrid_tokens?.total ?? 0}
            sub={`in: ${stats?.dgrid_tokens?.prompt ?? 0} · out: ${stats?.dgrid_tokens?.completion ?? 0}`}
          />
        </Card>
        <Card>
          <Stat label="Fallback events" value={stats?.fallback_events ?? 0} sub="auto-retried on Anthropic / OpenAI" />
        </Card>
      </div>

      {/* Fallback chain diagram */}
      <Card className="mb-6">
        <div className="eyebrow mb-4">Resilient fallback chain</div>
        <div className="flex items-center gap-3 flex-wrap">
          {(stats?.primary_order || ["dgrid"]).map((p, i, arr) => (
            <div key={p} className="flex items-center gap-3">
              <div className={`rounded-xl border px-3 py-2 ${PROVIDER_STYLE[p]?.bg || ""} ${PROVIDER_STYLE[p]?.border || ""}`}>
                <div className={`text-[10px] uppercase tracking-wide ${PROVIDER_STYLE[p]?.text || ""}`}>
                  {i === 0 ? "primary" : `fallback #${i}`}
                </div>
                <div className={`font-mono font-semibold ${PROVIDER_STYLE[p]?.text || ""}`}>{p}</div>
              </div>
              {i < arr.length - 1 && <span className="text-white/20 text-lg">→</span>}
            </div>
          ))}
        </div>
        <div className="text-[11px] text-white/40 mt-3 max-w-xl">
          Every attempt is recorded — successful or failed. If DGrid errors with BALANCE_INSUFFICIENT, rate limit, or
          any 5xx, we transparently fall back. On the next call we retry DGrid first again.
        </div>
      </Card>

      {/* Task map */}
      <Card className="mb-6">
        <div className="eyebrow mb-4">Task → model routing via DGrid</div>
        <div className="grid md:grid-cols-2 gap-2">
          {Object.entries(stats?.task_model_map || {}).map(([task, model]) => (
            <div key={task} className="flex items-center justify-between gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
              <span className="text-sm text-white/80 capitalize">{task}</span>
              <span className="font-mono text-xs text-[#6cff32]">{model}</span>
            </div>
          ))}
        </div>
        <div className="text-[11px] text-white/40 mt-3">
          Remap via <code className="text-white/60">DGRID_TASK_OVERRIDES=&quot;content=anthropic/claude-sonnet-4.5&quot;</code>.
          All tasks default to the cheapest capable DGrid model for sustained operation.
        </div>
      </Card>

      {/* Side-by-side comparison */}
      <Card className="mb-6">
        <div className="eyebrow mb-3">Side-by-side model comparison via DGrid</div>
        <p className="text-xs text-white/50 mb-4 max-w-2xl">
          One prompt. Three models. One API. This is what judges from DGrid are evaluating: not just
          &quot;did you call our endpoint&quot; but &quot;did you actually use the multi-model value prop.&quot;
        </p>
        <div className="grid md:grid-cols-[1fr_auto] gap-3 mb-4">
          <input
            value={compareInput}
            onChange={(e) => setCompareInput(e.target.value)}
            placeholder="Ask any question…"
            className="bg-black/40 border border-white/10 rounded-lg px-3 py-2 font-mono text-sm focus:outline-none focus:border-[#6cff32]/50 min-w-0"
          />
          <button
            onClick={runCompare}
            disabled={comparing || !compareInput.trim()}
            className="btn-primary px-5 py-2 text-sm disabled:opacity-40 whitespace-nowrap"
          >
            {comparing ? "running 3 models…" : "compare models →"}
          </button>
        </div>
        {compare && (
          <div className="grid md:grid-cols-3 gap-3">
            {compare.results.map((r) => (
              <div
                key={r.model}
                className={`rounded-xl border p-3 ${r.ok ? "border-white/10 bg-white/[0.02]" : "border-[#ff494a]/30 bg-[#ff494a]/5"}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-[11px] text-[#6cff32] truncate">{r.model}</span>
                  <span className="text-[10px] text-white/40 font-mono">{r.latency_ms}ms</span>
                </div>
                <div className="text-xs text-white/80 whitespace-pre-wrap break-words min-h-[4rem]">
                  {r.ok ? r.response : r.error}
                </div>
                {r.usage && (
                  <div className="text-[10px] text-white/30 font-mono mt-2">
                    {r.usage.total_tokens}tok ({r.usage.prompt_tokens} in · {r.usage.completion_tokens} out)
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Live trace */}
      <Card className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="eyebrow">Recent calls</div>
          <div className="text-[11px] text-white/30 font-mono">refreshes every 10s</div>
        </div>
        {trace.length === 0 && <div className="text-xs text-white/40">No calls recorded yet.</div>}
        <div className="space-y-1.5">
          {trace.map((t, i) => (
            <div
              key={i}
              className={`flex items-center justify-between gap-3 rounded-lg border px-3 py-2 text-[11px] ${t.success ? "border-white/5 bg-white/[0.02]" : "border-[#ff494a]/20 bg-[#ff494a]/5"}`}
            >
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <Pill provider={t.provider} />
                <span className="font-mono text-white/70 truncate">{t.model}</span>
                <span className="text-white/30">·</span>
                <span className="text-white/50">{t.task}</span>
                {t.fallback_depth > 0 && (
                  <span className="text-[#ffd641] text-[10px]">↓{t.fallback_depth}</span>
                )}
                {!t.success && t.error && <span className="text-[#ff494a] text-[10px] truncate">{t.error.slice(0, 40)}</span>}
              </div>
              <div className="flex items-center gap-3 text-white/40 text-[10px] font-mono shrink-0">
                <span>{t.latency_ms}ms</span>
                {t.total_tokens > 0 && <span>{t.total_tokens}tok</span>}
                <span>{ago(t.ts, now)}</span>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Resources */}
      <Card className="bg-gradient-to-r from-white/[0.02] to-[#6cff32]/[0.03]">
        <div className="eyebrow mb-3">Integration surface for judges</div>
        <div className="space-y-1 text-xs font-mono text-white/60">
          <div><span className="text-[#00d4ff]">GET</span>  /api/dgrid/stats — per-task routing, fallback counts</div>
          <div><span className="text-[#00d4ff]">GET</span>  /api/dgrid/health — green/amber/red reachability</div>
          <div><span className="text-[#00d4ff]">GET</span>  /api/dgrid/trace?limit=50 — last N calls, no fallback hidden</div>
          <div><span className="text-[#ffd641]">POST</span> /api/dgrid/probe — force a DGrid-only call, verify live</div>
        </div>
        <div className="text-[11px] text-white/40 mt-4">
          Every public response with LLM content carries an <code className="text-white/60">llm_provider</code> field so
          judges can audit <em>which</em> provider served <em>which</em> decision — not just aggregate stats.
        </div>
      </Card>
    </main>
  );
}
