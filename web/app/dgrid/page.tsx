"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

const API = (process.env.NEXT_PUBLIC_API_URL || "https://four-life.gudman.xyz").replace(/\/$/, "");

// ── Types ──────────────────────────────────────────────────────

interface BreakerSnap {
  state: "closed" | "open" | "half_open";
  consecutive_failures: number;
  failure_threshold: number;
  cooldown_seconds: number;
  open_until: number;
  seconds_until_half_open: number;
  times_opened: number;
  last_opened_at: number;
  last_open_reason: string | null;
}

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
  breaker_skips: number;
  transient_retries: number;
  chaos_enabled: boolean;
  breaker: BreakerSnap;
  total_calls: number;
  dgrid_calls: number;
  dgrid_share: number;
  dgrid_tokens: { prompt: number; completion: number; total: number };
  cost_usd: {
    total: number;
    by_provider: Record<string, number>;
    by_task: Record<string, number>;
    by_model: Record<string, number>;
  };
  usage_by_provider: Record<string, number>;
  usage_by_task: Record<string, number>;
  usage_by_model: Record<string, number>;
  trace_count: number;
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
  ts_ms: number;
  seq: number;
  provider: "dgrid" | "anthropic" | "openai";
  model: string;
  task: string;
  latency_ms: number;
  fallback_depth: number;
  success: boolean;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
  cost_tracked: boolean;
  error: string | null;
  call_digest?: string;
  chain_tip?: string;
}

interface ProbeResult {
  ok: boolean;
  provider?: string;
  model?: string;
  latency_ms?: number;
  response?: string;
  error?: string;
  usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
  cost_usd?: number;
}

interface CompareRow {
  model: string;
  ok: boolean;
  latency_ms: number;
  response?: string;
  error?: string;
  usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
  cost_usd?: number;
}

interface CompareResult {
  prompt: string;
  results: CompareRow[];
}

interface LeaderboardRow {
  task: string;
  model: string;
  calls: number;
  successes: number;
  failures: number;
  success_rate: number;
  avg_latency_ms: number;
  cost_usd: number;
  cost_per_call_usd: number;
}

interface LeaderboardResp {
  rows: LeaderboardRow[];
  auto_tune_enabled: boolean;
  current_task_map: Record<string, string>;
}

interface AuditResp {
  current_root: string;
  num_calls_chained: number;
  last_published_root: string | null;
  last_published_txhash: string | null;
  last_published_at: number;
  last_published_count: number;
  unpublished_calls: number;
  genesis: string;
  dgrid_calls_seen_by_client: number;
  full_log_count: number;
  dgrid_images_disabled: boolean;
}

interface ConsensusResult {
  prompt: string;
  models_queried: string[];
  models_succeeded: number;
  vote_key: string;
  method: string;
  final_verdict: unknown;
  confidence: number;
  tally: Record<string, number>;
  results: Array<{
    model: string;
    ok: boolean;
    verdict?: unknown;
    latency_ms: number;
    error?: string;
    usage?: { prompt_tokens: number; completion_tokens: number };
  }>;
  total_latency_ms: number;
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

const BREAKER_STYLE: Record<BreakerSnap["state"], { dot: string; text: string; label: string }> = {
  closed: { dot: "bg-[#6cff32]", text: "text-[#6cff32]", label: "closed · primary path" },
  half_open: { dot: "bg-[#ffd641]", text: "text-[#ffd641]", label: "half-open · probing" },
  open: { dot: "bg-[#ff494a]", text: "text-[#ff494a]", label: "open · skipping DGrid" },
};

function ago(ts: number, now: number) {
  const s = Math.max(0, now - ts);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

function fmtUSD(n: number | undefined, digits = 4) {
  if (n === undefined || n === null) return "$0";
  if (n === 0) return "$0";
  if (n < 0.0001) return `$${n.toExponential(2)}`;
  return `$${n.toFixed(digits)}`;
}

function shortHash(h: string | null | undefined, head = 10, tail = 6) {
  if (!h) return "—";
  if (h.length <= head + tail) return h;
  return `${h.slice(0, head)}…${h.slice(-tail)}`;
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
  const [leaderboard, setLeaderboard] = useState<LeaderboardResp | null>(null);
  const [audit, setAudit] = useState<AuditResp | null>(null);

  const [probe, setProbe] = useState<ProbeResult | null>(null);
  const [probing, setProbing] = useState(false);

  const [compareInput, setCompareInput] = useState("Describe a meme token launch in 20 words.");
  const [compare, setCompare] = useState<CompareResult | null>(null);
  const [comparing, setComparing] = useState(false);

  const [consensusInput, setConsensusInput] = useState(
    "Is the BNB Chain meme token sector bullish over the next 24h? Respond JSON: {\"action\": \"bullish\" | \"bearish\" | \"neutral\"}"
  );
  const [consensus, setConsensus] = useState<ConsensusResult | null>(null);
  const [consensusRunning, setConsensusRunning] = useState(false);

  const [chaosBusy, setChaosBusy] = useState(false);

  const [now, setNow] = useState(Math.floor(Date.now() / 1000));

  const reload = useCallback(async () => {
    try {
      const [s, h, t, lb, au] = await Promise.all([
        fetch(`${API}/api/dgrid/stats`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${API}/api/dgrid/health`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${API}/api/dgrid/trace?limit=20`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${API}/api/dgrid/leaderboard`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${API}/api/dgrid/audit`).then((r) => (r.ok ? r.json() : null)),
      ]);
      setStats(s);
      setHealth(h);
      setTrace(t?.trace || []);
      setLeaderboard(lb);
      setAudit(au);
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
      setCompare({
        prompt: compareInput,
        results: [{ model: "error", ok: false, latency_ms: 0, error: String(e) }],
      });
    } finally {
      setComparing(false);
    }
  };

  const runConsensus = async () => {
    setConsensusRunning(true);
    setConsensus(null);
    try {
      const res = await fetch(`${API}/api/dgrid/consensus`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: consensusInput,
          vote_key: "action",
          max_tokens: 200,
        }),
      });
      const body: ConsensusResult = await res.json();
      setConsensus(body);
      reload();
    } catch (e) {
      /* surface error in UI below */
      setConsensus({
        prompt: consensusInput,
        models_queried: [],
        models_succeeded: 0,
        vote_key: "action",
        method: "none",
        final_verdict: null,
        confidence: 0,
        tally: {},
        results: [],
        total_latency_ms: 0,
      });
    } finally {
      setConsensusRunning(false);
    }
  };

  const toggleChaos = async (enable: boolean) => {
    setChaosBusy(true);
    try {
      await fetch(`${API}/api/dgrid/chaos`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: enable, reason: enable ? "demo" : null }),
      });
      reload();
    } catch {
      /* ignore */
    } finally {
      setChaosBusy(false);
    }
  };

  const sharePct = useMemo(() => Math.round((stats?.dgrid_share || 0) * 100), [stats]);
  const healthStyle = health ? HEALTH_STYLE[health.status] : HEALTH_STYLE.red;
  const breakerStyle = stats?.breaker ? BREAKER_STYLE[stats.breaker.state] : BREAKER_STYLE.closed;

  return (
    <main className="max-w-5xl mx-auto px-5 py-14">
      <div className="mb-6">
        <Link href="/" className="text-xs text-white/40 hover:text-white/70">← Home</Link>
      </div>

      {/* Hero */}
      <div className="mb-10 max-w-3xl">
        <div className="eyebrow mb-3">Powered by DGrid AI Gateway</div>
        <h1 className="text-4xl md:text-5xl font-bold mb-3">FOUR-LIFE runs on DGrid.</h1>
        <p className="text-white/60 leading-relaxed text-lg">
          Every LLM decision the agent makes — narrative, content, risk, vision, consensus, image — routes through{" "}
          <span className="text-[#6cff32] font-semibold">DGrid&apos;s unified AI Gateway</span>. One API, one auth, one
          audit trail, across every model. A circuit breaker + three-tier fallback chain keeps the agent alive even
          when DGrid hiccups — but DGrid always leads.
        </p>
      </div>

      {/* Health + breaker rail */}
      <Card className="mb-6">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3">
              <span className={`inline-flex h-3 w-3 rounded-full ${healthStyle.dot} ${health?.status === "green" ? "animate-pulse" : ""}`} />
              <div>
                <div className={`text-lg font-semibold ${healthStyle.tint}`}>{healthStyle.label}</div>
                <div className="text-[11px] text-white/40 font-mono">
                  primary = {stats?.default_dgrid_model || "—"} · last = {health?.last_provider || "—"}
                </div>
              </div>
            </div>
            <div className="hidden md:block w-px h-8 bg-white/10" />
            <div className="flex items-center gap-3">
              <span className={`inline-flex h-3 w-3 rounded-full ${breakerStyle.dot}`} />
              <div>
                <div className={`text-sm font-semibold ${breakerStyle.text}`}>Breaker · {breakerStyle.label}</div>
                <div className="text-[11px] text-white/40 font-mono">
                  fails {stats?.breaker.consecutive_failures ?? 0}/{stats?.breaker.failure_threshold ?? 3}
                  {" · "}opened {stats?.breaker.times_opened ?? 0}×
                  {stats?.breaker.state === "open" && ` · retry in ${stats.breaker.seconds_until_half_open}s`}
                </div>
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
                {probe.cost_usd !== undefined && <span className="ml-2 text-white/40">· {fmtUSD(probe.cost_usd, 6)}</span>}
              </div>
            ) : (
              <div className="break-all">Probe failed: {probe.error}</div>
            )}
          </div>
        )}
      </Card>

      {/* Core stats */}
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
            label="DGrid $ burn"
            value={fmtUSD(stats?.cost_usd?.by_provider?.dgrid)}
            sub={`total across all: ${fmtUSD(stats?.cost_usd?.total)}`}
            accent="text-[#6cff32]"
          />
        </Card>
        <Card>
          <Stat
            label="Transient retries"
            value={stats?.transient_retries ?? 0}
            sub={`${stats?.fallback_events ?? 0} fallbacks · ${stats?.breaker_skips ?? 0} breaker skips`}
          />
        </Card>
      </div>

      {/* Chaos panel — live demo of fallback resilience */}
      <Card className={`mb-6 ${stats?.chaos_enabled ? "border-[#ff494a]/40 bg-[#ff494a]/[0.04]" : ""}`}>
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="eyebrow mb-1">Chaos mode — live fallback demo</div>
            <div className="text-sm text-white/70">
              {stats?.chaos_enabled ? (
                <span className="text-[#ff494a] font-semibold">DGrid is being forced to fail right now.</span>
              ) : (
                "Deliberately inject DGrid failures to see the fallback chain engage live."
              )}
            </div>
            <div className="text-[11px] text-white/40 mt-1 font-mono">
              circuit breaker trips normally · disabling resets it
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => toggleChaos(true)}
              disabled={chaosBusy || stats?.chaos_enabled}
              className="btn-pill text-xs bg-[#ff494a]/10 text-[#ff494a] border border-[#ff494a]/30 hover:bg-[#ff494a]/20 disabled:opacity-40"
            >
              {chaosBusy ? "…" : "kill DGrid"}
            </button>
            <button
              onClick={() => toggleChaos(false)}
              disabled={chaosBusy || !stats?.chaos_enabled}
              className="btn-pill text-xs bg-[#6cff32]/10 text-[#6cff32] border border-[#6cff32]/30 hover:bg-[#6cff32]/20 disabled:opacity-40"
            >
              {chaosBusy ? "…" : "restore"}
            </button>
          </div>
        </div>
      </Card>

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
          Every attempt is recorded — successful or failed. On transient 5xx we retry DGrid once before falling back. After
          {" "}{stats?.breaker.failure_threshold ?? 3} consecutive failures the circuit breaker opens for{" "}
          {stats?.breaker.cooldown_seconds ?? 30}s, so we stop paying latency on a doomed primary.
        </div>
      </Card>

      {/* On-chain attestation */}
      <Card className="mb-6 bg-gradient-to-br from-white/[0.02] to-[#6cff32]/[0.03]">
        <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
          <div>
            <div className="eyebrow mb-1">On-chain attestation · cryptographic proof of DGrid usage</div>
            <div className="text-xs text-white/60 max-w-xl">
              Every successful DGrid call is folded into a SHA-256 hash chain. The tip is published on BNB Chain as a
              self-transaction — anyone can verify the commitment without trusting us.
            </div>
          </div>
        </div>
        <div className="grid md:grid-cols-2 gap-3">
          <div className="rounded-lg border border-white/10 bg-black/20 p-3">
            <div className="text-[10px] uppercase tracking-wide text-white/40 mb-1">Current Merkle tip</div>
            <div className="font-mono text-xs text-[#6cff32] break-all">{shortHash(audit?.current_root, 24, 20)}</div>
            <div className="text-[10px] text-white/40 font-mono mt-1">
              commits to {audit?.num_calls_chained ?? 0} DGrid calls · {audit?.unpublished_calls ?? 0} unpublished
            </div>
          </div>
          <div className="rounded-lg border border-white/10 bg-black/20 p-3">
            <div className="text-[10px] uppercase tracking-wide text-white/40 mb-1">Last published</div>
            {audit?.last_published_txhash ? (
              <a
                href={`https://bscscan.com/tx/${audit.last_published_txhash}`}
                target="_blank"
                rel="noopener"
                className="font-mono text-xs text-[#00d4ff] hover:text-[#6cff32] break-all"
              >
                {shortHash(audit.last_published_txhash, 16, 10)} ↗
              </a>
            ) : (
              <div className="font-mono text-xs text-white/40">not yet published</div>
            )}
            <div className="text-[10px] text-white/40 font-mono mt-1">
              {audit?.last_published_at ? `${ago(audit.last_published_at, now)} · ` : ""}
              root {shortHash(audit?.last_published_root, 12, 8)}
            </div>
          </div>
        </div>
        <div className="mt-3 text-[11px] text-white/50">
          Full call log ({audit?.full_log_count ?? 0} entries) available at{" "}
          <a
            href={`${API}/api/dgrid/audit/calls?limit=2000`}
            target="_blank"
            rel="noopener"
            className="text-[#00d4ff] hover:text-[#6cff32] font-mono"
          >
            /api/dgrid/audit/calls
          </a>
          {" "}— download + re-derive the chain yourself to verify the root.
        </div>
      </Card>

      {/* Cost breakdown */}
      <Card className="mb-6">
        <div className="eyebrow mb-3">Cost breakdown · USD spent per task / model</div>
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <div className="text-[10px] uppercase tracking-wide text-white/40 mb-2">By task</div>
            <div className="space-y-1">
              {Object.entries(stats?.cost_usd?.by_task || {}).length === 0 ? (
                <div className="text-xs text-white/40">no cost accrued yet</div>
              ) : (
                Object.entries(stats?.cost_usd?.by_task || {})
                  .sort((a, b) => b[1] - a[1])
                  .map(([task, cost]) => (
                    <div key={task} className="flex items-center justify-between text-xs">
                      <span className="text-white/70">{task}</span>
                      <span className="font-mono text-[#6cff32]">{fmtUSD(cost, 6)}</span>
                    </div>
                  ))
              )}
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wide text-white/40 mb-2">By model</div>
            <div className="space-y-1">
              {Object.entries(stats?.cost_usd?.by_model || {}).length === 0 ? (
                <div className="text-xs text-white/40">no cost accrued yet</div>
              ) : (
                Object.entries(stats?.cost_usd?.by_model || {})
                  .sort((a, b) => b[1] - a[1])
                  .map(([model, cost]) => (
                    <div key={model} className="flex items-center justify-between text-xs">
                      <span className="font-mono text-white/70 truncate mr-2">{model}</span>
                      <span className="font-mono text-[#6cff32] whitespace-nowrap">{fmtUSD(cost, 6)}</span>
                    </div>
                  ))
              )}
            </div>
          </div>
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

      {/* Leaderboard */}
      <Card className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <div className="eyebrow">Self-optimizing leaderboard · per (task, model)</div>
          <div className="text-[11px] text-white/40 font-mono">
            auto-tune: {leaderboard?.auto_tune_enabled ? "on" : "off"}
          </div>
        </div>
        {(leaderboard?.rows?.length || 0) === 0 ? (
          <div className="text-xs text-white/40">waiting for calls — leaderboard is empty until the router sees traffic</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead className="text-left text-white/40 uppercase">
                <tr>
                  <th className="py-1 pr-3">task</th>
                  <th className="py-1 pr-3">model</th>
                  <th className="py-1 pr-3 text-right">calls</th>
                  <th className="py-1 pr-3 text-right">success</th>
                  <th className="py-1 pr-3 text-right">avg latency</th>
                  <th className="py-1 pr-3 text-right">$/call</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {leaderboard?.rows?.map((r, i) => (
                  <tr key={`${r.task}-${r.model}-${i}`} className="border-t border-white/5">
                    <td className="py-1.5 pr-3 text-white/80">{r.task}</td>
                    <td className="py-1.5 pr-3 text-[#6cff32] truncate max-w-[200px]">{r.model}</td>
                    <td className="py-1.5 pr-3 text-white/70 text-right">{r.calls}</td>
                    <td className="py-1.5 pr-3 text-white/70 text-right">{(r.success_rate * 100).toFixed(0)}%</td>
                    <td className="py-1.5 pr-3 text-white/70 text-right">{Math.round(r.avg_latency_ms)}ms</td>
                    <td className="py-1.5 pr-3 text-white/70 text-right">{fmtUSD(r.cost_per_call_usd, 6)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Consensus demo */}
      <Card className="mb-6">
        <div className="eyebrow mb-3">Multi-model consensus via DGrid · flagship capability</div>
        <p className="text-xs text-white/50 mb-4 max-w-2xl">
          Fan a decision out to 3 DGrid models in parallel and vote. This is the defining DGrid-only behavior: one API,
          one auth, three models, one vote. FOUR-LIFE uses this for the DEFEND phase of every token&apos;s lifecycle.
        </p>
        <div className="grid md:grid-cols-[1fr_auto] gap-3 mb-4">
          <textarea
            value={consensusInput}
            onChange={(e) => setConsensusInput(e.target.value)}
            rows={2}
            className="bg-black/40 border border-white/10 rounded-lg px-3 py-2 font-mono text-xs focus:outline-none focus:border-[#6cff32]/50 min-w-0 resize-none"
          />
          <button
            onClick={runConsensus}
            disabled={consensusRunning || !consensusInput.trim()}
            className="btn-primary px-5 py-2 text-sm disabled:opacity-40 whitespace-nowrap"
          >
            {consensusRunning ? "voting…" : "run consensus →"}
          </button>
        </div>
        {consensus && (
          <div>
            <div className="mb-4 rounded-xl border border-[#6cff32]/30 bg-[#6cff32]/[0.04] p-4">
              <div className="text-[10px] uppercase tracking-wide text-[#6cff32] mb-1">Final verdict · {consensus.method}</div>
              <div className="flex items-baseline gap-3 flex-wrap">
                <span className="text-2xl font-bold text-white">
                  {consensus.final_verdict === null ? "—" : String(consensus.final_verdict)}
                </span>
                <span className="text-xs text-white/50 font-mono">
                  confidence {(consensus.confidence * 100).toFixed(0)}% · {consensus.models_succeeded}/{consensus.models_queried.length} models
                  · {consensus.total_latency_ms}ms total
                </span>
              </div>
              {Object.keys(consensus.tally).length > 0 && (
                <div className="mt-2 flex gap-2 flex-wrap text-[11px] font-mono">
                  {Object.entries(consensus.tally).map(([verdict, count]) => (
                    <span key={verdict} className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5">
                      <span className="text-white/60">{verdict}</span>
                      <span className="text-[#6cff32] ml-1">×{count}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div className="grid md:grid-cols-3 gap-3">
              {consensus.results.map((r) => (
                <div
                  key={r.model}
                  className={`rounded-xl border p-3 ${r.ok ? "border-white/10 bg-white/[0.02]" : "border-[#ff494a]/30 bg-[#ff494a]/5"}`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-[11px] text-[#6cff32] truncate mr-2">{r.model}</span>
                    <span className="text-[10px] text-white/40 font-mono whitespace-nowrap">{r.latency_ms}ms</span>
                  </div>
                  <div className="text-xs whitespace-pre-wrap break-words min-h-[3rem]">
                    {r.ok ? (
                      <span className="text-white/80">
                        verdict: <span className="text-[#6cff32] font-mono">{String(r.verdict)}</span>
                      </span>
                    ) : (
                      <span className="text-[#ff494a]">{r.error}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* Side-by-side comparison */}
      <Card className="mb-6">
        <div className="eyebrow mb-3">Side-by-side model comparison via DGrid</div>
        <p className="text-xs text-white/50 mb-4 max-w-2xl">
          One prompt. Three models. One API. Demonstrates the core DGrid value prop without the voting layer.
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
                <div className="text-[10px] text-white/30 font-mono mt-2 flex justify-between">
                  {r.usage ? (
                    <span>{r.usage.prompt_tokens + r.usage.completion_tokens}tok</span>
                  ) : <span />}
                  {r.cost_usd !== undefined && <span>{fmtUSD(r.cost_usd, 6)}</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Live trace */}
      <Card className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="eyebrow">Recent calls</div>
          <div className="text-[11px] text-white/30 font-mono">refreshes every 10s · {stats?.trace_count ?? 0} in ring</div>
        </div>
        {trace.length === 0 && <div className="text-xs text-white/40">No calls recorded yet.</div>}
        <div className="space-y-1.5">
          {trace.map((t) => (
            <div
              key={t.seq}
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
                {t.chain_tip && (
                  <span className="text-[#6cff32]/60 text-[10px] font-mono" title={`chain tip: ${t.chain_tip}`}>
                    ⛓{t.chain_tip.slice(0, 6)}
                  </span>
                )}
                {!t.success && t.error && (
                  <span className="text-[#ff494a] text-[10px] truncate">{t.error.slice(0, 40)}</span>
                )}
              </div>
              <div className="flex items-center gap-3 text-white/40 text-[10px] font-mono shrink-0">
                <span>{t.latency_ms}ms</span>
                {t.total_tokens > 0 && <span>{t.total_tokens}tok</span>}
                {t.cost_usd > 0 && <span className="text-[#6cff32]/70">{fmtUSD(t.cost_usd, 6)}</span>}
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
          <div><span className="text-[#00d4ff]">GET</span>  /api/dgrid/stats — per-task routing, fallback counts, cost $</div>
          <div><span className="text-[#00d4ff]">GET</span>  /api/dgrid/health — green/amber/red reachability</div>
          <div><span className="text-[#00d4ff]">GET</span>  /api/dgrid/trace?limit=N — last N calls, with chain tip + cost</div>
          <div><span className="text-[#00d4ff]">GET</span>  /api/dgrid/leaderboard — per-(task,model) rolling stats</div>
          <div><span className="text-[#00d4ff]">GET</span>  /api/dgrid/audit — current Merkle root + last on-chain txhash</div>
          <div><span className="text-[#00d4ff]">GET</span>  /api/dgrid/audit/calls — full call log for independent Merkle verification</div>
          <div><span className="text-[#ffd641]">POST</span> /api/dgrid/probe — force a DGrid-only call, verify live</div>
          <div><span className="text-[#ffd641]">POST</span> /api/dgrid/compare — N models, same prompt, side-by-side</div>
          <div><span className="text-[#ffd641]">POST</span> /api/dgrid/consensus — N models vote on a JSON field</div>
          <div><span className="text-[#ff494a]">POST</span> /api/dgrid/chaos — (admin) toggle simulated DGrid outage</div>
          <div><span className="text-[#ff494a]">POST</span> /api/dgrid/attest — (admin) publish Merkle root on BNB Chain</div>
        </div>
        <div className="text-[11px] text-white/40 mt-4">
          Every public response with LLM content carries an <code className="text-white/60">llm_provider</code> field so
          judges can audit <em>which</em> provider served <em>which</em> decision — not just aggregate stats.
        </div>
      </Card>
    </main>
  );
}
