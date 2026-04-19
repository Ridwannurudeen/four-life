"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API = (process.env.NEXT_PUBLIC_API_URL || "https://four-life.gudman.xyz").replace(/\/$/, "");

interface Metrics {
  uptime_seconds: number;
  total_requests: number;
  error_rate_5xx: number;
  latency_ms: {
    samples: number;
    p50: number;
    p95: number;
    p99: number;
    max: number;
    avg: number;
  };
  status_counts: Record<string, number>;
  endpoints: {
    path: string;
    count: number;
    p50_ms: number;
    p95_ms: number;
  }[];
}

function fmtUptime(s: number): string {
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function Stat({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
      <div className="eyebrow text-white/40 mb-1">{label}</div>
      <div className={`text-2xl font-semibold ${accent || "text-white"}`}>{value}</div>
      {sub && <div className="text-[11px] text-white/40 mt-1">{sub}</div>}
    </div>
  );
}

function statusBand(status: string): string {
  const s = parseInt(status, 10);
  if (s >= 500) return "text-[#ff494a]";
  if (s >= 400) return "text-[#ffd641]";
  if (s >= 300) return "text-[#00d4ff]";
  return "text-[#6cff32]";
}

export default function MetricsPage() {
  const [m, setM] = useState<Metrics | null>(null);
  const [updatedAt, setUpdatedAt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch(`${API}/api/metrics`);
        if (!res.ok) return;
        const data: Metrics = await res.json();
        if (!cancelled) {
          setM(data);
          setUpdatedAt(Math.floor(Date.now() / 1000));
        }
      } catch {
        /* ignore */
      }
    };
    const initial = setTimeout(load, 0);
    const iv = setInterval(load, 10_000);
    return () => {
      cancelled = true;
      clearTimeout(initial);
      clearInterval(iv);
    };
  }, []);

  const errPct = m ? (m.error_rate_5xx * 100).toFixed(2) : "—";
  const errAccent = m && m.error_rate_5xx > 0.01 ? "text-[#ff494a]" : "text-[#6cff32]";

  return (
    <main className="max-w-5xl mx-auto px-5 py-14">
      <div className="mb-6">
        <Link href="/" className="text-xs text-white/40 hover:text-white/70">← Home</Link>
      </div>

      <div className="mb-10 max-w-3xl">
        <div className="eyebrow mb-3">Reliability</div>
        <h1 className="text-4xl md:text-5xl font-bold mb-3">Service metrics, first-party.</h1>
        <p className="text-white/60 leading-relaxed">
          Latency percentiles, error rate, endpoint breakdown — sampled from the live traffic the agent itself serves.
          No external telemetry vendor, no extrapolation. The same middleware that rate-limits requests captures
          these numbers.
        </p>
      </div>

      {!m && <div className="text-sm text-white/50">loading…</div>}

      {m && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <Stat label="Uptime" value={fmtUptime(m.uptime_seconds)} sub="since last service restart" accent="text-[#6cff32]" />
            <Stat label="Requests served" value={m.total_requests.toLocaleString()} sub={`${m.latency_ms.samples} samples in window`} />
            <Stat label="5xx error rate" value={`${errPct}%`} sub={`threshold <1%`} accent={errAccent} />
            <Stat label="p95 latency" value={`${m.latency_ms.p95} ms`} sub={`avg ${m.latency_ms.avg}ms · max ${m.latency_ms.max}ms`} />
          </div>

          <div className="grid md:grid-cols-2 gap-3 mb-6">
            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
              <div className="eyebrow mb-4">Latency percentiles</div>
              <div className="space-y-3">
                {[
                  { label: "p50", value: m.latency_ms.p50 },
                  { label: "p95", value: m.latency_ms.p95 },
                  { label: "p99", value: m.latency_ms.p99 },
                  { label: "max", value: m.latency_ms.max },
                ].map((row) => (
                  <div key={row.label}>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-white/60 uppercase tracking-wide">{row.label}</span>
                      <span className="font-mono font-semibold">{row.value} ms</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-[#6cff32] to-[#00d4ff]"
                        style={{ width: `${Math.min(100, (row.value / Math.max(m.latency_ms.max, 1)) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
              <div className="eyebrow mb-4">Status codes</div>
              <div className="space-y-2">
                {Object.entries(m.status_counts)
                  .sort(([a], [b]) => parseInt(a, 10) - parseInt(b, 10))
                  .map(([status, count]) => (
                    <div key={status} className="flex items-center justify-between text-xs">
                      <span className={`font-mono font-semibold ${statusBand(status)}`}>HTTP {status}</span>
                      <span className="text-white/60 font-mono">{count.toLocaleString()}</span>
                    </div>
                  ))}
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <div className="eyebrow">Top endpoints</div>
              <div className="text-[11px] text-white/30 font-mono">refreshes 10s</div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-white/40 uppercase tracking-wider">
                    <th className="text-left py-2 pr-4">Path</th>
                    <th className="text-right py-2 pr-4">Requests</th>
                    <th className="text-right py-2 pr-4">p50</th>
                    <th className="text-right py-2">p95</th>
                  </tr>
                </thead>
                <tbody>
                  {m.endpoints.map((ep) => (
                    <tr key={ep.path} className="border-t border-white/5">
                      <td className="py-2 pr-4 font-mono text-white/70">{ep.path}</td>
                      <td className="py-2 pr-4 text-right font-mono">{ep.count.toLocaleString()}</td>
                      <td className="py-2 pr-4 text-right font-mono text-white/60">{ep.p50_ms} ms</td>
                      <td className="py-2 text-right font-mono text-white/60">{ep.p95_ms} ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {updatedAt > 0 && (
            <div className="text-[11px] text-white/30 font-mono text-right">
              refreshed {new Date(updatedAt * 1000).toLocaleTimeString()} · every request also returns X-Response-Time-Ms
            </div>
          )}
        </>
      )}
    </main>
  );
}
