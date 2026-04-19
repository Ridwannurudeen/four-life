"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

const API = (process.env.NEXT_PUBLIC_API_URL || "https://four-life.gudman.xyz").replace(/\/$/, "");

// ── Types ──────────────────────────────────────────────────────

type Level = "safe" | "warn" | "critical";

interface FiredRule {
  id: string;
  metric: string;
  value: string | number | boolean;
  threshold: string | number | boolean;
  operator: string;
  severity: string;
  message: string;
}

interface AlertEvent {
  id: number;
  token_address: string;
  from_level: Level | null;
  to_level: Level;
  fired_rules: FiredRule[];
  recorded_at: number;
  name: string | null;
  symbol: string | null;
  current_phase: string | null;
  current_top_holder_pct: number | null;
}

interface AlertsResponse {
  count: number;
  events: AlertEvent[];
}

// ── Helpers ────────────────────────────────────────────────────

const LEVEL_STYLE: Record<Level, { dot: string; text: string; bg: string; border: string; label: string }> = {
  safe: { dot: "bg-[#6cff32]", text: "text-[#6cff32]", bg: "bg-[#6cff32]/10", border: "border-[#6cff32]/30", label: "Safe" },
  warn: { dot: "bg-[#ffd641]", text: "text-[#ffd641]", bg: "bg-[#ffd641]/10", border: "border-[#ffd641]/30", label: "Warn" },
  critical: { dot: "bg-[#ff494a]", text: "text-[#ff494a]", bg: "bg-[#ff494a]/10", border: "border-[#ff494a]/30", label: "Critical" },
};

const SEVERITY_STYLE: Record<string, string> = {
  critical: "text-[#ff494a] border-[#ff494a]/30 bg-[#ff494a]/10",
  high: "text-[#ff494a] border-[#ff494a]/30 bg-[#ff494a]/10",
  medium: "text-[#ffd641] border-[#ffd641]/30 bg-[#ffd641]/10",
  info: "text-[#00d4ff] border-[#00d4ff]/30 bg-[#00d4ff]/10",
  low: "text-white/50 border-white/10 bg-white/[0.02]",
};

function short(addr: string) {
  return addr.slice(0, 6) + "…" + addr.slice(-4);
}

function ago(ts: number) {
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function LevelPill({ level }: { level: Level }) {
  const s = LEVEL_STYLE[level];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${s.bg} ${s.text} ${s.border}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}

// ── Page ───────────────────────────────────────────────────────

export default function AlertsPage() {
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [filter, setFilter] = useState<"" | "warn" | "critical">("");
  const [updatedAt, setUpdatedAt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const qs = filter ? `?limit=80&min_level=${filter}` : "?limit=80";
        const res = await fetch(`${API}/api/alerts${qs}`);
        if (!res.ok) return;
        const data: AlertsResponse = await res.json();
        if (!cancelled) {
          setEvents(data.events || []);
          setUpdatedAt(Math.floor(Date.now() / 1000));
        }
      } catch {
        /* ignore */
      }
    };
    const initial = setTimeout(load, 0);
    const iv = setInterval(load, 15_000);
    return () => {
      cancelled = true;
      clearTimeout(initial);
      clearInterval(iv);
    };
  }, [filter]);

  const counts = useMemo(() => {
    const c: Record<Level, number> = { safe: 0, warn: 0, critical: 0 };
    events.forEach((e) => { c[e.to_level] = (c[e.to_level] || 0) + 1; });
    return c;
  }, [events]);

  return (
    <main className="max-w-5xl mx-auto px-5 py-14">
      <div className="mb-6">
        <Link href="/" className="text-xs text-white/40 hover:text-white/70">← Home</Link>
      </div>

      <div className="mb-8 max-w-3xl">
        <div className="eyebrow mb-3">Threat feed</div>
        <h1 className="text-4xl md:text-5xl font-bold mb-3">Protection Mode, live.</h1>
        <p className="text-white/60 leading-relaxed">
          Every token FOUR-LIFE watches runs through a deterministic defense layer. Whale concentration, sell
          pressure, stalled curves, contract rug signals — the moment any rule fires and the verdict transitions,
          it lands here with the exact metric and threshold that triggered it.
        </p>
      </div>

      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          {([
            { k: "", label: "All" },
            { k: "warn", label: "Warn+" },
            { k: "critical", label: "Critical only" },
          ] as const).map((opt) => (
            <button
              key={opt.k}
              onClick={() => setFilter(opt.k as typeof filter)}
              className={`btn-pill text-[11px] border ${filter === opt.k ? "bg-white/10 text-white border-white/20" : "text-white/50 border-white/10 hover:border-white/30"}`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3 text-xs text-white/50">
          <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-[#ff494a]" /> {counts.critical || 0}</span>
          <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-[#ffd641]" /> {counts.warn || 0}</span>
          <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-[#6cff32]" /> {counts.safe || 0}</span>
          {updatedAt > 0 && <span className="text-white/30">· refreshes 15s</span>}
        </div>
      </div>

      {events.length === 0 && (
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 text-center text-white/50 text-sm">
          No Protection Mode firings recorded yet. Every token transition lands here the moment the verdict changes.
        </div>
      )}

      <div className="space-y-3">
        {events.map((ev) => (
          <div key={ev.id} className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
            <div className="flex items-start justify-between gap-4 flex-wrap mb-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  {ev.from_level && <LevelPill level={ev.from_level} />}
                  <span className="text-white/30">→</span>
                  <LevelPill level={ev.to_level} />
                </div>
                <div className="text-sm font-semibold">
                  {ev.name || short(ev.token_address)}
                  {ev.symbol && <span className="text-white/40 text-xs ml-2">${ev.symbol}</span>}
                </div>
                <div className="flex items-center gap-3 text-[11px] text-white/40 mt-1 flex-wrap">
                  <a
                    href={`https://bscscan.com/address/${ev.token_address}`}
                    target="_blank"
                    rel="noreferrer"
                    className="font-mono hover:text-white/70"
                  >
                    {short(ev.token_address)} ↗
                  </a>
                  <Link href={`/launch/${ev.token_address}`} className="text-[#00d4ff] hover:underline">
                    live grade →
                  </Link>
                  {ev.current_phase && <span>phase: {ev.current_phase}</span>}
                </div>
              </div>
              <div className="text-[11px] text-white/40 font-mono shrink-0">{ago(ev.recorded_at)}</div>
            </div>

            {ev.fired_rules.length > 0 && (
              <div className="space-y-1">
                {ev.fired_rules.map((r, i) => (
                  <div
                    key={i}
                    className={`rounded-lg border px-3 py-2 text-[11px] ${SEVERITY_STYLE[r.severity] || SEVERITY_STYLE.low}`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-0.5 flex-wrap">
                      <span className="font-semibold uppercase tracking-wider">{r.id}</span>
                      <span className="font-mono text-[10px] text-white/40">
                        {String(r.value)} {r.operator} {String(r.threshold)}
                      </span>
                    </div>
                    <div className="text-white/80">{r.message}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-10 rounded-2xl border border-white/10 bg-white/[0.02] p-6">
        <div className="eyebrow mb-2">For integrators</div>
        <p className="text-sm text-white/70 leading-relaxed max-w-2xl mb-3">
          Subscribe to these events directly via signed HMAC webhooks — no polling needed. See{" "}
          <Link href="/webhooks" className="text-[#00d4ff] hover:underline">webhook docs</Link>.
        </p>
        <div className="text-xs font-mono text-white/60">
          <span className="text-[#00d4ff]">GET</span> /api/alerts?min_level=critical
        </div>
      </div>
    </main>
  );
}
