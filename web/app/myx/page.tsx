"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

const API = (process.env.NEXT_PUBLIC_API_URL || "https://four-life.gudman.xyz").replace(/\/$/, "");

// ── Types ──────────────────────────────────────────────────────

interface MYXMarket {
  contract_index: number;
  ticker_id: string;
  base_currency: string;
  target_currency: string;
  last_price: number;
  index_price: number;
  product_type: string;
  open_interest_in_usd: number;
}

interface MYXStatus {
  enabled: boolean;
  execution_mode: "executable" | "signal_only" | "disabled";
  markets_count: number;
  markets: MYXMarket[];
  reason?: string;
}

interface ConsensusMeta {
  method?: string;
  confidence?: number;
  tally?: Record<string, number>;
  models_queried?: string[];
  models_succeeded?: number;
}

interface MYXSignal {
  ts_ms: number;
  token_address: string;
  phase: string;
  action: "long" | "short" | "close" | "hold";
  confidence: number;
  size_pct: number;
  reasoning: string;
  execution_mode: string;
  health_score?: number;
  active_positions: number;
  consensus?: ConsensusMeta | null;
  signal_digest?: string;
  chain_tip?: string;
}

interface SignalAttestation {
  current_root: string;
  num_signals_chained: number;
  last_published_root: string | null;
  last_published_txhash: string | null;
  last_published_at: number;
  unpublished_signals: number;
  genesis: string;
  signal_log_count: number;
}

interface MYXSignalsResponse {
  count: number;
  total_ever: number;
  signals: MYXSignal[];
}

interface MYXAudit {
  current_root: string;
  num_events_chained: number;
  last_published_root: string | null;
  last_published_txhash: string | null;
  last_published_at: number;
  last_published_count: number;
  unpublished_events: number;
  genesis: string;
  position_log_count: number;
  execution_enabled: boolean;
}

interface MYXTokenSummary {
  token_address: string;
  active_positions: number;
  total_positions: number;
  total_hedged_wei: number;
  signals_generated: number;
  last_signal: MYXSignal | null;
}

interface MYXPortfolio {
  execution_mode: string;
  total_active_positions: number;
  total_closed_positions: number;
  total_signals_generated: number;
  tokens_hedged: number;
  token_summaries: MYXTokenSummary[];
}

// ── Helpers ────────────────────────────────────────────────────

const ACTION_STYLE: Record<string, { dot: string; text: string; bg: string; border: string }> = {
  long: { dot: "bg-[#6cff32]", text: "text-[#6cff32]", bg: "bg-[#6cff32]/10", border: "border-[#6cff32]/30" },
  short: { dot: "bg-[#ff494a]", text: "text-[#ff494a]", bg: "bg-[#ff494a]/10", border: "border-[#ff494a]/30" },
  close: { dot: "bg-[#00d4ff]", text: "text-[#00d4ff]", bg: "bg-[#00d4ff]/10", border: "border-[#00d4ff]/30" },
  hold: { dot: "bg-white/50", text: "text-white/60", bg: "bg-white/[0.04]", border: "border-white/10" },
};

const PHASE_STYLE: Record<string, string> = {
  nurture: "text-[#00d4ff]",
  defend: "text-[#ffd641]",
  accelerate: "text-[#6cff32]",
  graduated: "text-white/60",
};

function ago(tsMs: number, nowMs: number): string {
  const s = Math.max(0, Math.floor((nowMs - tsMs) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

function shortAddr(a: string | null | undefined, head = 6, tail = 4): string {
  if (!a) return "—";
  if (a.length <= head + tail) return a;
  return `${a.slice(0, head)}…${a.slice(-tail)}`;
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-white/10 bg-white/[0.02] p-6 ${className}`}>{children}</div>;
}

function ActionPill({ action }: { action: string }) {
  const s = ACTION_STYLE[action] || ACTION_STYLE.hold;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${s.bg} ${s.text} ${s.border}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {action}
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

function Skel({ w = "w-16", h = "h-5" }: { w?: string; h?: string }) {
  return <span className={`inline-block ${h} ${w} rounded bg-white/10 animate-pulse align-middle`} />;
}

function StatSkeleton({ label }: { label: string }) {
  return (
    <div>
      <div className="eyebrow text-white/40 mb-1">{label}</div>
      <div className="text-2xl font-semibold"><Skel w="w-20" h="h-7" /></div>
      <div className="mt-1"><Skel w="w-28" h="h-3" /></div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────

export default function MYXPage() {
  // Seeded with last-known-good state so the pre-render never shows
  // "MYX offline" / "No markets loaded" before client hydration. The
  // useEffect below replaces this with live data on mount.
  const [status, setStatus] = useState<MYXStatus | null>({
    enabled: true,
    execution_mode: "signal_only",
    markets_count: 37,
    markets: [],
  });
  const [signals, setSignals] = useState<MYXSignal[]>([]);
  const [audit, setAudit] = useState<MYXAudit | null>(null);
  const [signalAttest, setSignalAttest] = useState<SignalAttestation | null>(null);
  const [portfolio, setPortfolio] = useState<MYXPortfolio | null>(null);
  const [nowMs, setNowMs] = useState(Date.now());
  const [filterToken, setFilterToken] = useState<string>("");
  const [consensusBusy, setConsensusBusy] = useState(false);
  const [consensusResult, setConsensusResult] = useState<MYXSignal | null>(null);
  const [loaded, setLoaded] = useState(false);

  const reload = useCallback(async () => {
    try {
      const tokenQ = filterToken ? `&token_address=${filterToken}` : "";
      const [st, sg, au, sa, pf] = await Promise.all([
        fetch(`${API}/api/myx/status`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${API}/api/myx/signals?limit=30${tokenQ}`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${API}/api/myx/audit`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${API}/api/myx/signal-attestation`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${API}/api/myx/portfolio`).then((r) => (r.ok ? r.json() : null)),
      ]);
      setStatus(st);
      setSignals((sg as MYXSignalsResponse)?.signals || []);
      setAudit(au);
      setSignalAttest(sa);
      setPortfolio(pf);
      setNowMs(Date.now());
    } catch {
      /* ignore */
    } finally {
      setLoaded(true);
    }
  }, [filterToken]);

  const runConsensus = async (tokenAddress: string) => {
    setConsensusBusy(true);
    setConsensusResult(null);
    try {
      const res = await fetch(`${API}/api/myx/consensus/${tokenAddress}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force: true }),
      });
      const body = await res.json();
      const sig = body?.signal || null;
      setConsensusResult(sig);
      reload();
    } catch {
      /* surface via busy=false */
    } finally {
      setConsensusBusy(false);
    }
  };

  useEffect(() => {
    const initial = setTimeout(reload, 0);
    const iv = setInterval(reload, 10_000);
    return () => {
      clearTimeout(initial);
      clearInterval(iv);
    };
  }, [reload]);

  const connectionHealthy = status?.enabled && (status?.markets_count || 0) > 0;
  const execMode = status?.execution_mode || "disabled";
  const tokenSet = useMemo(() => {
    return Array.from(new Set(signals.map((s) => s.token_address)));
  }, [signals]);

  return (
    <main className="max-w-5xl mx-auto px-5 py-14">
      <div className="mb-6">
        <Link href="/" className="text-xs text-white/40 hover:text-white/70">← Home</Link>
      </div>

      {/* Hero */}
      <div className="mb-10 max-w-3xl">
        <div className="eyebrow mb-3">Powered by MYX V2 Perps</div>
        <h1 className="text-4xl md:text-5xl font-bold mb-3">
          FOUR-LIFE hedges on MYX.
        </h1>
        <p className="text-white/60 leading-relaxed text-lg">
          Every lifecycle decision the agent makes flows into a perpetual position on{" "}
          <span className="text-[#6cff32] font-semibold">MYX V2</span> — LONG when a token
          gains momentum, SHORT to defend against dumps, CLOSE when phase transitions make
          the position stale. Signals are generated via DGrid, positions are executed
          on BNB Chain, and every trade is folded into a cryptographically verifiable
          Merkle chain anchored on-chain.
        </p>
      </div>

      {/* Health rail */}
      <Card className="mb-6">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3">
              <span className={`inline-flex h-3 w-3 rounded-full ${connectionHealthy ? "bg-[#6cff32] animate-pulse" : "bg-[#ff494a]"}`} />
              <div>
                <div className={`text-lg font-semibold ${connectionHealthy ? "text-[#6cff32]" : "text-[#ff494a]"}`}>
                  {connectionHealthy ? "MYX live" : "MYX offline"}
                </div>
                <div className="text-[11px] text-white/40 font-mono">
                  markets = {status?.markets_count ?? "—"} · exec_mode = {execMode}
                </div>
              </div>
            </div>
            <div className="hidden md:block w-px h-8 bg-white/10" />
            <div>
              <div className={`text-sm font-semibold ${execMode === "executable" ? "text-[#6cff32]" : "text-[#ffd641]"}`}>
                {execMode === "executable" ? "EXECUTING · real perp orders" : "SIGNAL ONLY · safety mode"}
              </div>
              <div className="text-[11px] text-white/40 mt-0.5">
                {execMode === "executable"
                  ? "Position caps + liquidation guards active"
                  : "Flip MYX_EXECUTION_ENABLED=true on VPS to execute"}
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <Card>
          {loaded ? (
            <Stat
              label="Total signals"
              value={portfolio?.total_signals_generated ?? "—"}
              sub="across all tracked tokens"
              accent="text-[#6cff32]"
            />
          ) : (
            <StatSkeleton label="Total signals" />
          )}
        </Card>
        <Card>
          {loaded ? (
            <Stat
              label="Active positions"
              value={portfolio?.total_active_positions ?? 0}
              sub={`${portfolio?.total_closed_positions ?? 0} closed`}
            />
          ) : (
            <StatSkeleton label="Active positions" />
          )}
        </Card>
        <Card>
          {loaded ? (
            <Stat
              label="Tokens hedged"
              value={portfolio?.tokens_hedged ?? 0}
              sub="getting live MYX signals"
            />
          ) : (
            <StatSkeleton label="Tokens hedged" />
          )}
        </Card>
        <Card>
          {loaded ? (
            <Stat
              label="Attested trades"
              value={audit?.num_events_chained ?? 0}
              sub={`${audit?.unpublished_events ?? 0} unpublished`}
            />
          ) : (
            <StatSkeleton label="Attested trades" />
          )}
        </Card>
      </div>

      {/* Phase → action diagram */}
      <Card className="mb-6">
        <div className="eyebrow mb-4">Phase-triggered hedging logic</div>
        <div className="grid md:grid-cols-4 gap-3 text-xs">
          <div className="rounded-xl border border-[#00d4ff]/30 bg-[#00d4ff]/5 p-3">
            <div className="text-[#00d4ff] uppercase tracking-wide text-[10px] mb-1">nurture</div>
            <div className="text-white/80">Monitor only</div>
            <div className="text-white/40 text-[10px] mt-1">signals persisted, no orders</div>
          </div>
          <div className="rounded-xl border border-[#ffd641]/30 bg-[#ffd641]/5 p-3">
            <div className="text-[#ffd641] uppercase tracking-wide text-[10px] mb-1">defend</div>
            <div className="text-white/80">SHORT on weakness</div>
            <div className="text-white/40 text-[10px] mt-1">whale concentration / sell pressure → hedge</div>
          </div>
          <div className="rounded-xl border border-[#6cff32]/30 bg-[#6cff32]/5 p-3">
            <div className="text-[#6cff32] uppercase tracking-wide text-[10px] mb-1">accelerate</div>
            <div className="text-white/80">LONG on momentum</div>
            <div className="text-white/40 text-[10px] mt-1">holder velocity + buy ratio → amplify</div>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
            <div className="text-white/60 uppercase tracking-wide text-[10px] mb-1">graduated</div>
            <div className="text-white/80">CLOSE all</div>
            <div className="text-white/40 text-[10px] mt-1">PancakeSwap migration → unwind</div>
          </div>
        </div>
      </Card>

      {/* Decision attestation — the agent's thinking on-chain, independent of trade execution */}
      <Card className="mb-6 bg-gradient-to-br from-white/[0.02] to-[#00d4ff]/[0.03]">
        <div className="mb-3">
          <div className="eyebrow mb-1">MYX decision attestation · the agent&apos;s thinking on-chain</div>
          <div className="text-xs text-white/60 max-w-2xl">
            Every hedge decision — action, confidence, size %, reasoning hash, and DGrid-consensus
            vote metadata — hashed into a Merkle chain and published on BNB Chain. The cryptographic
            audit trail is complete <em>before</em> any trade fires, making the agent&apos;s decision-making
            reputation verifiable independent of the permissioned broker-signer gate.
          </div>
          <a
            href="https://bscscan.com/tx/0x5c5b9876cc85d54e01b69d03ee8709d32370fe64374a02ddf1ac521ddc0437af"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 mt-3 px-2.5 py-1 rounded-full border border-[#00d4ff]/40 bg-[#00d4ff]/10 text-[#00d4ff] hover:bg-[#00d4ff]/20 text-[11px] font-mono"
          >
            518 decisions committed · latest root 0x5c5b9876…37af ↗
          </a>
        </div>
        <div className="grid md:grid-cols-2 gap-3">
          <div className="rounded-lg border border-white/10 bg-black/20 p-3">
            <div className="text-[10px] uppercase tracking-wide text-white/40 mb-1">Signal chain tip</div>
            <div className="font-mono text-xs text-[#00d4ff] break-all">
              {loaded ? (signalAttest ? shortAddr(signalAttest.current_root, 24, 20) : "—") : <Skel w="w-64" h="h-4" />}
            </div>
            <div className="text-[10px] text-white/40 font-mono mt-1">
              {loaded ? (
                <>{signalAttest?.num_signals_chained ?? 0} signals chained · {signalAttest?.unpublished_signals ?? 0} unpublished</>
              ) : (
                <Skel w="w-48" h="h-3" />
              )}
            </div>
          </div>
          <div className="rounded-lg border border-white/10 bg-black/20 p-3">
            <div className="text-[10px] uppercase tracking-wide text-white/40 mb-1">Last published</div>
            {loaded ? (
              signalAttest?.last_published_txhash ? (
                <a
                  href={`https://bscscan.com/tx/${signalAttest.last_published_txhash}`}
                  target="_blank"
                  rel="noopener"
                  className="font-mono text-xs text-[#00d4ff] hover:text-[#6cff32] break-all"
                >
                  {shortAddr(signalAttest.last_published_txhash, 16, 10)} ↗
                </a>
              ) : (
                <div className="font-mono text-xs text-white/40">not yet published</div>
              )
            ) : (
              <Skel w="w-40" h="h-4" />
            )}
            <div className="text-[10px] text-white/40 font-mono mt-1">
              {loaded ? (
                <>
                  {signalAttest?.last_published_at ? `${ago(signalAttest.last_published_at * 1000, nowMs)} · ` : ""}
                  root {shortAddr(signalAttest?.last_published_root, 12, 8)}
                </>
              ) : (
                <Skel w="w-56" h="h-3" />
              )}
            </div>
          </div>
        </div>
      </Card>

      {/* Live consensus demo — fan hedge decision across 3 DGrid models */}
      <Card className="mb-6">
        <div className="eyebrow mb-3">Live consensus demo · DGrid × MYX synergy</div>
        <p className="text-xs text-white/50 mb-4 max-w-2xl">
          Click any tracked token to fan the current hedge prompt across 3 DGrid models in parallel.
          Majority vote decides the action. 452 DEFEND-phase signals attested on-chain at root{" "}
          <a href="https://bscscan.com/tx/0xeda29cc60bc8ca9bb3b3d8f78cf0200cd39cd50a3b80cbb0f411d25025232026" target="_blank" rel="noopener noreferrer" className="text-[#00d4ff] hover:underline font-mono">0xeda29cc6</a>.
        </p>
        <div className="flex gap-2 flex-wrap">
          {(portfolio?.token_summaries || []).map((t) => (
            <button
              key={t.token_address}
              onClick={() => runConsensus(t.token_address)}
              disabled={consensusBusy}
              className="btn-pill text-xs bg-[#6cff32]/10 text-[#6cff32] border border-[#6cff32]/30 hover:bg-[#6cff32]/20 disabled:opacity-40 font-mono"
            >
              {consensusBusy ? "voting…" : `consensus for ${shortAddr(t.token_address)} →`}
            </button>
          ))}
          {loaded && (portfolio?.token_summaries || []).length === 0 && (
            <div className="text-xs text-white/40">No tracked tokens yet.</div>
          )}
          {!loaded && (
            <div className="flex gap-2 flex-wrap">
              <Skel w="w-48" h="h-7" />
              <Skel w="w-48" h="h-7" />
              <Skel w="w-48" h="h-7" />
            </div>
          )}
        </div>
        {consensusResult && (
          <div className="mt-4 rounded-xl border border-[#6cff32]/30 bg-[#6cff32]/[0.04] p-4">
            <div className="flex items-baseline gap-3 flex-wrap mb-2">
              <ActionPill action={String(consensusResult.action)} />
              <span className="text-xl font-bold text-white">{consensusResult.action}</span>
              <span className="text-xs text-white/60 font-mono">
                confidence {Math.round((consensusResult.confidence || 0) * 100)}%
                {consensusResult.consensus?.method && ` · ${consensusResult.consensus.method}`}
                {typeof consensusResult.consensus?.confidence === "number" &&
                  ` · vote agreement ${Math.round(consensusResult.consensus.confidence * 100)}%`}
              </span>
            </div>
            {consensusResult.consensus?.tally && (
              <div className="flex gap-2 flex-wrap text-[11px] font-mono mb-2">
                {Object.entries(consensusResult.consensus.tally).map(([v, c]) => (
                  <span key={v} className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5">
                    <span className="text-white/60">{v}</span>
                    <span className="text-[#6cff32] ml-1">×{c}</span>
                  </span>
                ))}
              </div>
            )}
            {consensusResult.reasoning && (
              <div className="text-xs text-white/70 italic">&ldquo;{consensusResult.reasoning}&rdquo;</div>
            )}
          </div>
        )}
      </Card>

      {/* On-chain attestation */}
      <Card className="mb-6 bg-gradient-to-br from-white/[0.02] to-[#6cff32]/[0.03]">
        <div className="mb-3">
          <div className="eyebrow mb-1">Trade attestation · cryptographic proof of perp activity</div>
          <div className="text-xs text-white/60 max-w-2xl">
            Every position open + close is hashed into a rolling SHA-256 chain. The tip
            can be published on BNB Chain as a self-transaction — independent verifiers
            can download the event log and re-derive the chain locally.
          </div>
        </div>
        <div className="grid md:grid-cols-2 gap-3">
          <div className="rounded-lg border border-white/10 bg-black/20 p-3">
            <div className="text-[10px] uppercase tracking-wide text-white/40 mb-1">Current Merkle tip</div>
            <div className="font-mono text-xs text-[#6cff32] break-all">
              {loaded ? (audit ? shortAddr(audit.current_root, 24, 20) : "—") : <Skel w="w-64" h="h-4" />}
            </div>
            <div className="text-[10px] text-white/40 font-mono mt-1">
              {loaded ? (
                <>{audit?.num_events_chained ?? 0} trade events · {audit?.unpublished_events ?? 0} unpublished</>
              ) : (
                <Skel w="w-48" h="h-3" />
              )}
            </div>
          </div>
          <div className="rounded-lg border border-white/10 bg-black/20 p-3">
            <div className="text-[10px] uppercase tracking-wide text-white/40 mb-1">Last published</div>
            {loaded ? (
              audit?.last_published_txhash ? (
                <a
                  href={`https://bscscan.com/tx/${audit.last_published_txhash}`}
                  target="_blank"
                  rel="noopener"
                  className="font-mono text-xs text-[#00d4ff] hover:text-[#6cff32] break-all"
                >
                  {shortAddr(audit.last_published_txhash, 16, 10)} ↗
                </a>
              ) : (
                <div className="font-mono text-xs text-white/40">not yet published</div>
              )
            ) : (
              <Skel w="w-40" h="h-4" />
            )}
            <div className="text-[10px] text-white/40 font-mono mt-1">
              {loaded ? (
                <>
                  {audit?.last_published_at ? `${ago(audit.last_published_at * 1000, nowMs)} · ` : ""}
                  root {shortAddr(audit?.last_published_root, 12, 8)}
                </>
              ) : (
                <Skel w="w-56" h="h-3" />
              )}
            </div>
          </div>
        </div>
        <div className="mt-3 text-[11px] text-white/50">
          Full event log available at{" "}
          <a
            href={`${API}/api/myx/audit/events?limit=2000`}
            target="_blank"
            rel="noopener"
            className="text-[#00d4ff] hover:text-[#6cff32] font-mono"
          >
            /api/myx/audit/events
          </a>
          {" "}— download + re-derive to verify the root.
        </div>
      </Card>

      {/* Live signal feed */}
      <Card className="mb-6">
        <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
          <div>
            <div className="eyebrow">Live signal feed · agent decisions on MYX</div>
            <div className="text-[11px] text-white/40 mt-1">
              refreshes every 10s · {signals.length} shown · {(status as MYXStatus | null) ? null : ""}
            </div>
          </div>
          {tokenSet.length > 1 && (
            <div className="flex items-center gap-2 text-[11px]">
              <button
                onClick={() => setFilterToken("")}
                className={`rounded-full px-2.5 py-1 ${!filterToken ? "bg-[#6cff32]/10 text-[#6cff32] border border-[#6cff32]/30" : "text-white/50 border border-white/10"}`}
              >
                all
              </button>
              {tokenSet.slice(0, 3).map((addr) => (
                <button
                  key={addr}
                  onClick={() => setFilterToken(addr)}
                  className={`rounded-full px-2.5 py-1 font-mono ${filterToken === addr ? "bg-[#6cff32]/10 text-[#6cff32] border border-[#6cff32]/30" : "text-white/50 border border-white/10"}`}
                >
                  {shortAddr(addr)}
                </button>
              ))}
            </div>
          )}
        </div>
        {loaded && signals.length === 0 && (
          <div className="text-xs text-white/40">No signals yet — agent generates one every 5 min per tracked token.</div>
        )}
        {!loaded && (
          <div className="space-y-1.5">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center justify-between gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
                <Skel w="w-64" h="h-4" />
                <Skel w="w-14" h="h-3" />
              </div>
            ))}
          </div>
        )}
        <div className="space-y-1.5">
          {signals.map((s, i) => (
            <div
              key={`${s.ts_ms}-${i}`}
              className="flex items-center justify-between gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-[11px]"
            >
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <ActionPill action={s.action} />
                <span className="font-mono text-white/70">{shortAddr(s.token_address)}</span>
                <span className="text-white/30">·</span>
                <span className={`${PHASE_STYLE[s.phase] || "text-white/50"} uppercase text-[10px]`}>{s.phase}</span>
                <span className="text-white/30">·</span>
                <span className="text-white/60">{Math.round((s.confidence || 0) * 100)}% conf</span>
                {s.consensus && (
                  <span className="inline-flex items-center gap-1 rounded-full border border-[#6cff32]/30 bg-[#6cff32]/10 text-[#6cff32] px-1.5 py-0 text-[9px] font-semibold uppercase tracking-wide">
                    consensus ×{s.consensus.models_succeeded ?? "?"}
                  </span>
                )}
                {s.chain_tip && (
                  <span className="text-[#00d4ff]/60 text-[10px] font-mono" title={`signal chain tip: ${s.chain_tip}`}>
                    ⛓{s.chain_tip.slice(0, 6)}
                  </span>
                )}
                {s.reasoning && <span className="text-white/40 truncate hidden md:inline">· {s.reasoning.slice(0, 80)}</span>}
              </div>
              <div className="text-white/40 text-[10px] font-mono shrink-0">{ago(s.ts_ms, nowMs)}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* Per-token summary */}
      {(portfolio?.token_summaries || []).length > 0 && (
        <Card className="mb-6">
          <div className="eyebrow mb-4">Per-token hedge summary</div>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead className="text-left text-white/40 uppercase">
                <tr>
                  <th className="py-1 pr-3">token</th>
                  <th className="py-1 pr-3 text-right">signals</th>
                  <th className="py-1 pr-3 text-right">active pos</th>
                  <th className="py-1 pr-3 text-right">total pos</th>
                  <th className="py-1 pr-3">last action</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {portfolio!.token_summaries.map((t) => (
                  <tr key={t.token_address} className="border-t border-white/5">
                    <td className="py-1.5 pr-3 text-white/80">{shortAddr(t.token_address, 8, 6)}</td>
                    <td className="py-1.5 pr-3 text-white/70 text-right">{t.signals_generated}</td>
                    <td className="py-1.5 pr-3 text-white/70 text-right">{t.active_positions}</td>
                    <td className="py-1.5 pr-3 text-white/70 text-right">{t.total_positions}</td>
                    <td className="py-1.5 pr-3">
                      {t.last_signal ? <ActionPill action={t.last_signal.action} /> : <span className="text-white/30">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Markets */}
      <Card className="mb-6">
        <div className="eyebrow mb-4">MYX markets available for hedging · {status?.markets_count ?? 0} perp pairs</div>
        {!loaded ? (
          <div className="grid md:grid-cols-3 gap-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 flex items-center justify-between">
                <Skel w="w-20" h="h-3" />
                <Skel w="w-16" h="h-3" />
              </div>
            ))}
          </div>
        ) : (status?.markets || []).length === 0 ? (
          <div className="text-xs text-white/40">No markets loaded. MYX may be offline.</div>
        ) : (
          <div className="grid md:grid-cols-3 gap-2 text-[11px]">
            {status!.markets.slice(0, 12).map((m) => (
              <div
                key={m.ticker_id}
                className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 flex items-center justify-between"
              >
                <span className="font-mono text-white/80">{m.ticker_id}</span>
                <span className="text-[#6cff32] font-mono">${(m.last_price || 0).toFixed(4)}</span>
              </div>
            ))}
          </div>
        )}
        {(status?.markets_count || 0) > 12 && (
          <div className="text-[11px] text-white/40 mt-3">+{(status!.markets_count || 0) - 12} more markets available</div>
        )}
      </Card>

      {/* Integration surface */}
      <Card className="bg-gradient-to-r from-white/[0.02] to-[#6cff32]/[0.03]">
        <div className="eyebrow mb-3">MYX integration API surface</div>
        <div className="space-y-1 text-xs font-mono text-white/60">
          <div><span className="text-[#00d4ff]">GET</span>  /api/myx/status — live MYX V2 connection + 37 market list</div>
          <div><span className="text-[#00d4ff]">GET</span>  /api/myx/signals?limit=N — persistent signal log (all-time)</div>
          <div><span className="text-[#00d4ff]">GET</span>  /api/myx/portfolio — per-token hedge summary</div>
          <div><span className="text-[#00d4ff]">GET</span>  /api/myx/positions/&#123;token&#125; — position detail by token</div>
          <div><span className="text-[#00d4ff]">GET</span>  /api/myx/audit — Merkle chain tip + last published tx</div>
          <div><span className="text-[#00d4ff]">GET</span>  /api/myx/audit/events — full event log for independent verification</div>
          <div><span className="text-[#00d4ff]">GET</span>  /api/myx/signal-attestation — Merkle commitment over every signal</div>
          <div><span className="text-[#00d4ff]">GET</span>  /api/myx/calldata/&#123;token&#125; — exact unsigned tx we&apos;d submit (BscScan-verifiable)</div>
          <div><span className="text-[#ffd641]">POST</span> /api/myx/consensus/&#123;token&#125; — fan hedge decision across 3 DGrid models</div>
          <div><span className="text-[#ffd641]">POST</span> /api/myx/evaluate/&#123;token&#125; — trigger a hedge eval now</div>
          <div><span className="text-[#ffd641]">GET</span>  /api/myx/signal/&#123;token&#125; — one-shot AI signal for a token</div>
          <div><span className="text-[#ff494a]">POST</span> /api/myx/attest — publish trade Merkle root on BNB Chain (admin)</div>
          <div><span className="text-[#ff494a]">POST</span> /api/myx/attest-signals — publish signal Merkle root on BNB Chain (admin)</div>
        </div>
      </Card>
    </main>
  );
}
