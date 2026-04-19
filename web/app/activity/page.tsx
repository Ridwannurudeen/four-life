"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

const API = (process.env.NEXT_PUBLIC_API_URL || "https://four-life.gudman.xyz").replace(/\/$/, "");

// ── Types ──────────────────────────────────────────────────────

interface Action {
  token_address: string;
  action_type: string;
  content: string;
  urgency: string;
  reasoning: string;
  timestamp: number;
  tweet_id: string | null;
}

interface Attestation {
  token_address: string;
  token_symbol: string;
  token_name: string;
  graduation_time: number;
  tx_hash: string;
  block_number: number;
  submitted_at: number;
  value: number;
  tag1: string;
  tag2: string;
  feedback_uri: string;
}

interface IdentityPayload {
  registration: {
    agent_id: number | null;
    wallet: string;
    tx_hash: string;
    block: number;
    agent_card_uri: string;
  };
  reputation_attestations: Attestation[];
}

interface Token {
  address: string;
  name: string;
  symbol: string;
  phase: string;
  age_hours: number;
  health_score: number;
  unique_buyers: number;
  top_holder_pct: number;
  curve_progress: number;
  holder_velocity: number;
}

interface Status {
  agent_name: string;
  running: boolean;
  agent_id: number | null;
  total_launches: number;
  total_graduations: number;
  active_tokens: number;
  learnings_count: number;
}

// Unified timeline event — every source normalizes into this shape.
type EventKind = "action" | "attestation" | "tracking";

interface TimelineEvent {
  kind: EventKind;
  ts: number;
  title: string;
  subtitle?: string;
  body?: string;
  meta?: { label: string; value: string; href?: string }[];
  tokenAddress?: string;
  tokenSymbol?: string;
}

// ── Helpers ────────────────────────────────────────────────────

function short(addr: string) {
  return addr ? addr.slice(0, 6) + "…" + addr.slice(-4) : "";
}

function ago(ts: number) {
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

const KIND_STYLE: Record<EventKind, { dot: string; label: string; tint: string }> = {
  action: { dot: "bg-[#00d4ff]", label: "LIFECYCLE ACTION", tint: "text-[#00d4ff]" },
  attestation: { dot: "bg-purple-400", label: "ON-CHAIN ATTESTATION", tint: "text-purple-300" },
  tracking: { dot: "bg-[#6cff32]", label: "TRACKING STARTED", tint: "text-[#6cff32]" },
};

// ── Components ─────────────────────────────────────────────────

function StatCard({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <div className="eyebrow text-white/40 mb-1">{label}</div>
      <div className={`text-2xl font-semibold ${accent || "text-white"}`}>{value}</div>
    </div>
  );
}

function EventRow({ ev }: { ev: TimelineEvent }) {
  const s = KIND_STYLE[ev.kind];
  return (
    <div className="relative pl-6">
      <span className={`absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full ${s.dot}`} />
      <span className="absolute left-[4px] top-4 bottom-[-16px] w-px bg-white/10" />

      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className={`eyebrow ${s.tint}`}>{s.label}</span>
            <span className="text-[11px] text-white/30">· {ago(ev.ts)}</span>
          </div>
          <div className="text-sm font-semibold text-white/90">{ev.title}</div>
          {ev.subtitle && <div className="text-xs text-white/50 mt-0.5">{ev.subtitle}</div>}
          {ev.body && (
            <div className="text-xs text-white/70 mt-2 bg-black/20 rounded-lg px-3 py-2 max-w-2xl whitespace-pre-wrap">
              {ev.body}
            </div>
          )}
          {ev.meta && ev.meta.length > 0 && (
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[11px] text-white/50">
              {ev.meta.map((m, i) => (
                <span key={i} className="flex gap-1">
                  <span className="text-white/30">{m.label}</span>
                  {m.href ? (
                    <a href={m.href} target="_blank" rel="noreferrer" className="font-mono text-[#00d4ff] hover:underline">
                      {m.value}
                    </a>
                  ) : (
                    <span className="font-mono">{m.value}</span>
                  )}
                </span>
              ))}
            </div>
          )}
        </div>
        {ev.tokenAddress && (
          <Link
            href={`/launch/${ev.tokenAddress}`}
            className="text-[10px] text-white/40 hover:text-white/80 font-mono shrink-0"
          >
            {ev.tokenSymbol ? `$${ev.tokenSymbol}` : short(ev.tokenAddress)} →
          </Link>
        )}
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────

export default function ActivityPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [actions, setActions] = useState<Action[]>([]);
  const [identity, setIdentity] = useState<IdentityPayload | null>(null);
  const [tokens, setTokens] = useState<Token[]>([]);
  const [updatedAt, setUpdatedAt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [s, a, i, t] = await Promise.all([
          fetch(`${API}/api/status`).then((r) => r.json()).catch(() => null),
          fetch(`${API}/api/actions?limit=50`).then((r) => r.json()).catch(() => null),
          fetch(`${API}/api/identity`).then((r) => r.json()).catch(() => null),
          fetch(`${API}/api/tokens`).then((r) => r.json()).catch(() => null),
        ]);
        if (cancelled) return;
        setStatus(s);
        setActions(a?.actions || []);
        setIdentity(i);
        setTokens(t?.tokens || []);
        setUpdatedAt(Math.floor(Date.now() / 1000));
      } catch {
        /* ignore — keep previous values */
      }
    };
    const initial = setTimeout(load, 0);
    const iv = setInterval(load, 15000);
    return () => {
      cancelled = true;
      clearTimeout(initial);
      clearInterval(iv);
    };
  }, []);

  // Merge all sources into one reverse-chronological timeline.
  const timeline = useMemo<TimelineEvent[]>(() => {
    const events: TimelineEvent[] = [];

    for (const a of actions) {
      const tok = tokens.find((t) => t.address.toLowerCase() === a.token_address.toLowerCase());
      events.push({
        kind: "action",
        ts: a.timestamp,
        title: a.action_type.replace(/_/g, " "),
        subtitle: a.reasoning || undefined,
        body: a.content || undefined,
        meta: [
          ...(a.urgency ? [{ label: "urgency", value: a.urgency }] : []),
          ...(a.tweet_id ? [{ label: "tweet", value: a.tweet_id }] : []),
        ],
        tokenAddress: a.token_address,
        tokenSymbol: tok?.symbol,
      });
    }

    for (const att of identity?.reputation_attestations || []) {
      if (!att.tx_hash) continue;
      events.push({
        kind: "attestation",
        ts: att.submitted_at,
        title: `Graduation attestation · ${att.token_symbol || short(att.token_address)}`,
        subtitle: `On-chain reputation record via BRC-8004 · value +${att.value}`,
        meta: [
          { label: "tx", value: short(att.tx_hash), href: `https://bscscan.com/tx/${att.tx_hash}` },
          { label: "block", value: String(att.block_number) },
          { label: "pair", value: att.tag2 },
        ],
        tokenAddress: att.token_address,
        tokenSymbol: att.token_symbol,
      });
    }

    // Every tracked token implies a "started tracking" event. We don't have a
    // separate timestamp for it yet, so age_hours back-dates from updatedAt
    // (the last refresh time) — good enough for a visible "watching N tokens"
    // rail. `updatedAt` is part of the memo deps so this is pure.
    const refNow = updatedAt || Math.floor(new Date("2026-04-19").getTime() / 1000);
    for (const t of tokens) {
      const startedAt = Math.floor(refNow - t.age_hours * 3600);
      events.push({
        kind: "tracking",
        ts: startedAt,
        title: `Started tracking · ${t.name} ($${t.symbol})`,
        subtitle: `Phase: ${t.phase} · curve ${t.curve_progress.toFixed(1)}% · ${t.unique_buyers} buyers`,
        meta: [
          { label: "top holder", value: `${t.top_holder_pct.toFixed(1)}%` },
          { label: "velocity", value: `${t.holder_velocity.toFixed(1)}/h` },
        ],
        tokenAddress: t.address,
        tokenSymbol: t.symbol,
      });
    }

    return events.sort((a, b) => b.ts - a.ts).slice(0, 80);
  }, [actions, identity, tokens, updatedAt]);

  const reg = identity?.registration;

  return (
    <main className="max-w-5xl mx-auto px-5 py-14">
      <div className="mb-6">
        <Link href="/" className="text-xs text-white/40 hover:text-white/70">← Home</Link>
      </div>

      <div className="mb-8 max-w-3xl">
        <div className="eyebrow mb-3">Agent activity</div>
        <h1 className="text-4xl md:text-5xl font-bold mb-3">What the agent is doing, right now.</h1>
        <p className="text-white/60 leading-relaxed">
          FOUR-LIFE runs a continuous lifecycle loop — track, monitor, defend, attest.
          Every decision is visible here, every on-chain action is linked to its transaction.
          The agent does not need to tweet to prove it is working.
        </p>
      </div>

      {/* Status rail */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-10">
        <StatCard
          label="State"
          value={status?.running ? "LIVE" : "OFFLINE"}
          accent={status?.running ? "text-[#6cff32]" : "text-[#ff494a]"}
        />
        <StatCard label="Agent ID" value={status?.agent_id ? `#${status.agent_id}` : "—"} accent="text-purple-300" />
        <StatCard label="Active tokens" value={status?.active_tokens ?? "—"} />
        <StatCard label="Attestations" value={identity?.reputation_attestations?.filter((a) => a.tx_hash).length ?? 0} />
        <StatCard label="Learnings" value={status?.learnings_count ?? 0} />
      </div>

      {reg?.tx_hash && (
        <div className="mb-10 rounded-2xl border border-white/10 bg-white/[0.02] p-5">
          <div className="eyebrow mb-2">ERC-8004 registration</div>
          <div className="flex items-center gap-3 flex-wrap text-sm text-white/70">
            <span>Agent ID <span className="font-mono text-purple-300">#{reg.agent_id}</span></span>
            <span className="text-white/30">·</span>
            <a
              href={`https://bscscan.com/tx/${reg.tx_hash}`}
              target="_blank"
              rel="noreferrer"
              className="font-mono text-[#00d4ff] hover:underline"
            >
              {short(reg.tx_hash)} ↗
            </a>
            <span className="text-white/30">·</span>
            <a
              href={reg.agent_card_uri}
              target="_blank"
              rel="noreferrer"
              className="text-[11px] text-white/50 hover:text-white/80"
            >
              agent card
            </a>
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="mb-4 flex items-center justify-between">
        <div className="eyebrow">Timeline</div>
        {updatedAt > 0 && (
          <div className="text-[11px] text-white/30">
            updated {new Date(updatedAt * 1000).toLocaleTimeString()} · refreshes every 15s
          </div>
        )}
      </div>

      <div className="space-y-5">
        {timeline.length === 0 && (
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 text-center text-white/40 text-sm">
            No events yet. The agent is warming up.
          </div>
        )}
        {timeline.map((ev, i) => (
          <EventRow key={`${ev.kind}-${ev.ts}-${i}`} ev={ev} />
        ))}
      </div>

      <div className="mt-12 rounded-2xl border border-white/10 bg-white/[0.02] p-6">
        <div className="eyebrow mb-2">For integrators</div>
        <p className="text-sm text-white/70 leading-relaxed max-w-3xl mb-3">
          The same events are available via API. Pull the live stream from your own dashboard without scraping.
        </p>
        <div className="space-y-1 text-xs font-mono text-white/60">
          <div><span className="text-[#00d4ff]">GET</span> /api/actions?limit=50</div>
          <div><span className="text-[#00d4ff]">GET</span> /api/identity</div>
          <div><span className="text-[#00d4ff]">GET</span> /api/tokens</div>
          <div><span className="text-[#00d4ff]">POST</span> /api/webhooks — signed HMAC event subscriptions</div>
        </div>
      </div>
    </main>
  );
}
