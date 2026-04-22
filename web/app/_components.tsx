"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

// ── useReveal — IntersectionObserver fade-up ──────────────────────────

export function useReveal<T extends HTMLElement = HTMLDivElement>() {
  const ref = useRef<T | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      el.classList.add("in-view");
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add("in-view");
            io.unobserve(e.target);
          }
        }
      },
      { threshold: 0.15, rootMargin: "0px 0px -8% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return ref;
}

// ── Hero live mini-radar (right column anchor) ───────────────────────

interface MiniEntry {
  token_address: string;
  name: string;
  symbol: string;
  curve_progress: number;
  confidence_score: "high" | "medium" | "low";
  graduation_probability: number;
  increase_pct: number;
  // Server-computed — UI never re-derives. "certified" = full on-chain data;
  // "radar_estimate" = heuristic from public-ranking inputs only.
  badge_tier?: Tier;
  tier_source?: "certified" | "radar_estimate";
}

type Tier = "graduated" | "graduation_watch" | "healthy" | "at_risk" | "observed";

// Pure accessor — read the server's tier, default to "observed" only when the
// server hasn't graded the row yet. Do NOT reintroduce UI-side derivation.
function tierOf(e: MiniEntry): Tier {
  return (e.badge_tier as Tier) ?? "observed";
}

const TIER_STYLE: Record<Tier, { label: string; text: string; border: string; bg: string; dot: string }> = {
  graduated:        { label: "Graduated",        text: "text-purple-300", border: "border-purple-500/40", bg: "bg-purple-500/10",  dot: "bg-purple-400" },
  graduation_watch: { label: "Graduation Watch", text: "text-[#00d4ff]",  border: "border-[#00d4ff]/40",  bg: "bg-[#00d4ff]/10",   dot: "bg-[#00d4ff]" },
  healthy:          { label: "Healthy",          text: "text-[#6cff32]",  border: "border-[#6cff32]/40",  bg: "bg-[#6cff32]/10",   dot: "bg-[#6cff32]" },
  at_risk:          { label: "At Risk",          text: "text-[#ff494a]",  border: "border-[#ff494a]/40",  bg: "bg-[#ff494a]/10",   dot: "bg-[#ff494a]" },
  observed:         { label: "Observed",         text: "text-[#ffd641]",  border: "border-[#ffd641]/40",  bg: "bg-[#ffd641]/10",   dot: "bg-[#ffd641]" },
};

function short(addr: string): string {
  if (!addr || addr.length < 10) return addr || "";
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

export function HeroRadar({ entries }: { entries: MiniEntry[] }) {
  const [tickIndex, setTickIndex] = useState(0);

  // Rotate focus across the top 3 every 2.5s
  useEffect(() => {
    if (entries.length <= 3) return;
    const id = setInterval(() => setTickIndex((i) => (i + 1) % Math.max(1, entries.length - 2)), 2500);
    return () => clearInterval(id);
  }, [entries.length]);

  const visible = entries.slice(tickIndex, tickIndex + 3);
  while (visible.length < 3 && entries.length > 0) {
    visible.push(entries[(tickIndex + visible.length) % entries.length]);
  }

  return (
    <div className="live-card p-4 md:p-5 w-full max-w-md ml-auto">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-[#6cff32] pulse-ring" />
          <span className="text-[10px] uppercase tracking-[0.15em] text-[#6cff32] font-semibold">Live</span>
        </div>
        <div className="text-[10px] text-white/40 font-mono tabular">auto · 30s</div>
      </div>

      <div className="text-[11px] uppercase tracking-[0.15em] text-white/40 mb-3">
        FOUR-LIFE Certified — on radar
      </div>

      <div className="space-y-2">
        {visible.length === 0 ? (
          <div className="text-xs text-white/40 py-6 text-center">Connecting to the radar…</div>
        ) : (
          visible.map((e, i) => {
            const tier = tierOf(e);
            const s = TIER_STYLE[tier];
            return (
              <Link
                key={`${e.token_address}-${i}`}
                href={`/radar?token=${e.token_address}`}
                className="flex items-center gap-3 p-3 rounded-lg border border-white/5 bg-black/30 hover:bg-black/50 hover:border-white/10 transition-all group"
              >
                <span className={`inline-flex shrink-0 items-center gap-1.5 h-6 px-2 rounded-full border text-[10px] font-semibold uppercase tracking-wider ${s.bg} ${s.text} ${s.border}`}>
                  <span className={`h-1 w-1 rounded-full ${s.dot}`} />
                  {s.label}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-bold truncate">{e.symbol || "—"}</div>
                  <div className="text-[10px] text-white/35 font-mono truncate">{short(e.token_address)}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-sm font-bold tabular">{e.curve_progress.toFixed(0)}%</div>
                  <div className="text-[9px] uppercase tracking-wider text-white/30">curve</div>
                </div>
              </Link>
            );
          })
        )}
      </div>

      <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between text-[10px] text-white/35">
        <span className="font-mono">/api/graduation-radar</span>
        <Link href="/radar" className="text-[#6cff32] hover:underline">Open full radar →</Link>
      </div>
    </div>
  );
}

// ── Partner logo marks ───────────────────────────────────────────────

function Mark({ children, accent = "#ffffff" }: { children: React.ReactNode; accent?: string }) {
  return (
    <div className="flex items-center gap-2.5 h-10 px-5 rounded-full border border-white/8 bg-white/[0.03] hover:bg-white/[0.06] hover:border-white/15 transition-all">
      <span className="h-2 w-2 rounded-full shrink-0" style={{ background: accent, boxShadow: `0 0 10px ${accent}80` }} />
      <span className="text-xs font-bold tracking-wide text-white/80 whitespace-nowrap">{children}</span>
    </div>
  );
}

function LogoBNB() {
  return (
    <div className="flex items-center gap-2.5 h-10 px-5 rounded-full border border-white/8 bg-white/[0.03] hover:bg-white/[0.06] hover:border-white/15 transition-all whitespace-nowrap">
      <svg viewBox="0 0 64 64" className="h-5 w-5" aria-hidden>
        <g fill="#f3ba2f">
          <path d="M21.3 27.7 32 17l10.7 10.7 6.2-6.2L32 4.6 15.1 21.5z" />
          <path d="M4.6 32 10.8 25.8 17 32l-6.2 6.2z" />
          <path d="M21.3 36.3 32 47l10.7-10.7 6.2 6.2L32 59.4 15.1 42.5z" />
          <path d="M47 32l6.2-6.2L59.4 32l-6.2 6.2z" />
          <path d="M38.3 32 32 25.7 27.1 30.6l-.7.7-1.5 1.4v.1l.7.7 5.7 5.7 6.3-6.3.7-.8z" />
        </g>
      </svg>
      <span className="text-xs font-bold tracking-wide text-white/85">BNB Chain</span>
    </div>
  );
}

function LogoFourMeme() {
  return (
    <div className="flex items-center gap-2.5 h-10 px-5 rounded-full border border-white/8 bg-white/[0.03] hover:bg-white/[0.06] hover:border-white/15 transition-all whitespace-nowrap">
      <div className="h-6 w-6 rounded-md bg-gradient-to-br from-[#6cff32] to-[#34d9a0] flex items-center justify-center font-black text-black text-xs">4</div>
      <span className="text-xs font-bold tracking-wide text-white/85">Four.meme</span>
    </div>
  );
}

function LogoDGrid() {
  return (
    <div className="flex items-center gap-2.5 h-10 px-5 rounded-full border border-white/8 bg-white/[0.03] hover:bg-white/[0.06] hover:border-white/15 transition-all whitespace-nowrap">
      <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden>
        <g stroke="#00d4ff" strokeWidth="1.4" fill="none">
          <circle cx="12" cy="12" r="3" fill="#00d4ff" />
          <circle cx="4" cy="5" r="1.6" />
          <circle cx="20" cy="5" r="1.6" />
          <circle cx="4" cy="19" r="1.6" />
          <circle cx="20" cy="19" r="1.6" />
          <path d="M5.4 6.2 10.4 10.4 M18.6 6.2 13.6 10.4 M5.4 17.8 10.4 13.6 M18.6 17.8 13.6 13.6" strokeLinecap="round" />
        </g>
      </svg>
      <span className="text-xs font-bold tracking-wide text-white/85">DGrid</span>
    </div>
  );
}

function LogoMYX() {
  return (
    <div className="flex items-center gap-2.5 h-10 px-5 rounded-full border border-white/8 bg-white/[0.03] hover:bg-white/[0.06] hover:border-white/15 transition-all whitespace-nowrap">
      <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden>
        <path d="M3 20 L8 4 L12 14 L16 4 L21 20" stroke="#a770ef" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="text-xs font-bold tracking-wide text-white/85">MYX V2</span>
    </div>
  );
}

function LogoERC() {
  return (
    <div className="flex items-center gap-2.5 h-10 px-5 rounded-full border border-white/8 bg-white/[0.03] hover:bg-white/[0.06] hover:border-white/15 transition-all whitespace-nowrap">
      <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden>
        <g fill="none" stroke="#ffd641" strokeWidth="1.5">
          <polygon points="12,2 21,12 12,22 3,12" />
          <line x1="12" y1="2" x2="12" y2="22" />
          <line x1="3" y1="12" x2="21" y2="12" />
        </g>
      </svg>
      <span className="text-xs font-bold tracking-wide text-white/85">ERC-8004</span>
    </div>
  );
}

function LogoUnibase() {
  return (
    <div className="flex items-center gap-2.5 h-10 px-5 rounded-full border border-white/8 bg-white/[0.03] hover:bg-white/[0.06] hover:border-white/15 transition-all whitespace-nowrap">
      <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden>
        <g fill="#ff494a">
          <rect x="3" y="6" width="18" height="3" rx="1" />
          <rect x="3" y="11" width="18" height="3" rx="1" opacity="0.7" />
          <rect x="3" y="16" width="18" height="3" rx="1" opacity="0.4" />
        </g>
      </svg>
      <span className="text-xs font-bold tracking-wide text-white/85">Unibase</span>
    </div>
  );
}

function LogoPython() {
  return (
    <div className="flex items-center gap-2.5 h-10 px-5 rounded-full border border-white/8 bg-white/[0.03] hover:bg-white/[0.06] hover:border-white/15 transition-all whitespace-nowrap">
      <svg viewBox="0 0 32 32" className="h-5 w-5" aria-hidden>
        <defs>
          <linearGradient id="pyA" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#387eb8" />
            <stop offset="1" stopColor="#366994" />
          </linearGradient>
          <linearGradient id="pyB" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#ffe873" />
            <stop offset="1" stopColor="#ffd43b" />
          </linearGradient>
        </defs>
        <path fill="url(#pyA)" d="M15.8 3c-1.4 0-2.8.1-4 .4-3.6.7-4.2 2.1-4.2 4.7v3.6h8.4v1H4.5c-2.6 0-4.9 1.6-5.6 4.6-.8 3.4-.9 5.5 0 9.1.6 2.7 2.1 4.6 4.8 4.6h3v-4.5c0-3 2.6-5.7 5.7-5.7h8.3c2.5 0 4.6-2.1 4.6-4.6v-8.6c0-2.5-2.1-4.4-4.6-4.8-1.6-.3-3.2-.4-4.9-.4zM11 5.5c.9 0 1.6.7 1.6 1.6s-.7 1.7-1.6 1.7-1.7-.8-1.7-1.7.8-1.6 1.7-1.6z" />
        <path fill="url(#pyB)" d="M25.4 12.7v4.4c0 3.1-2.6 5.7-5.7 5.7h-8.4c-2.5 0-4.6 2.2-4.6 4.6v8.6c0 2.5 2.1 3.9 4.6 4.7 3 .9 5.9 1 9.6 0 2.3-.7 4.6-2 4.6-4.7v-3.6H17.1v-1h12.5c2.6 0 3.6-1.8 4.6-4.6 1-2.9 1-5.6 0-9.1-.7-2.6-1.9-4.6-4.6-4.6h-4.2zm-4.8 20.2c.9 0 1.7.7 1.7 1.6s-.8 1.7-1.7 1.7-1.6-.7-1.6-1.7.7-1.6 1.6-1.6z" transform="translate(-4 -4) scale(0.95)" />
      </svg>
      <span className="text-xs font-bold tracking-wide text-white/85">Python</span>
    </div>
  );
}

function LogoTS() {
  return (
    <div className="flex items-center gap-2.5 h-10 px-5 rounded-full border border-white/8 bg-white/[0.03] hover:bg-white/[0.06] hover:border-white/15 transition-all whitespace-nowrap">
      <svg viewBox="0 0 32 32" className="h-5 w-5" aria-hidden>
        <rect width="32" height="32" rx="4" fill="#3178c6" />
        <path fill="#ffffff" d="M18.2 25.4v-3.1c.6.4 1.3.7 2 1 .4.1.7.2 1 .2.3 0 .6 0 .9-.1.3 0 .5-.1.7-.2.2-.1.4-.2.5-.4.1-.2.2-.4.2-.6 0-.3-.1-.5-.2-.7-.2-.2-.4-.4-.6-.5l-1-.4-1.1-.5c-.9-.4-1.6-.8-2-1.4-.4-.5-.6-1.2-.6-2 0-.6.1-1.2.4-1.6.2-.5.6-.9 1-1.2.4-.3.9-.5 1.5-.7.6-.1 1.2-.2 1.8-.2.6 0 1.2 0 1.7.1s.9.2 1.3.3v2.9c-.2-.1-.4-.3-.7-.4s-.5-.2-.8-.3c-.3-.1-.5-.1-.8-.2h-1.3c-.2 0-.5 0-.7.1-.2 0-.4.1-.5.2-.1.1-.3.2-.3.3-.1.1-.1.3-.1.5s0 .4.1.5c.1.2.2.3.4.4l.6.4 1 .4c.5.2 1 .4 1.4.7.4.2.8.5 1.1.8.3.3.6.7.7 1.1.2.4.2.9.2 1.5 0 .7-.1 1.2-.4 1.7-.2.5-.6.8-1 1.1-.4.3-.9.5-1.5.6-.6.1-1.2.2-1.9.2-.7 0-1.3-.1-1.9-.2-.5-.1-1-.3-1.4-.4zm-5.1-11.1h3.9v-2.6H6.3v2.6H10v10.9h3.1z" />
      </svg>
      <span className="text-xs font-bold tracking-wide text-white/85">TypeScript</span>
    </div>
  );
}

export function PartnerMarquee() {
  const items = [
    <LogoBNB key="bnb" />,
    <LogoFourMeme key="fourmeme" />,
    <LogoDGrid key="dgrid" />,
    <LogoMYX key="myx" />,
    <LogoERC key="erc" />,
    <LogoUnibase key="uni" />,
    <LogoPython key="py" />,
    <LogoTS key="ts" />,
    <Mark key="fastapi" accent="#05998b">FastAPI</Mark>,
    <Mark key="nextjs" accent="#ffffff">Next.js</Mark>,
  ];
  const doubled = [...items, ...items.map((el, i) => ({ ...el, key: `dup-${i}` }))];
  return (
    <div className="logo-marquee overflow-hidden py-4">
      <div className="logo-marquee-track">
        {doubled.map((el, i) => (
          <div key={i}>{el}</div>
        ))}
      </div>
    </div>
  );
}
