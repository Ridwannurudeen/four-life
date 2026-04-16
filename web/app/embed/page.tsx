"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

const SAMPLE_TOKEN = "0x00ea33ab439c3fad06a6a824f3dbfade01334444";
const EMBED_URL = "https://four-life.gudman.xyz/embed.js";

const SNIPPETS: { label: string; code: string }[] = [
  {
    label: "HTML (anywhere on a page)",
    code: `<script src="${EMBED_URL}?token=${SAMPLE_TOKEN}"></script>`,
  },
  {
    label: "With attributes (size + chain link)",
    code: `<script src="${EMBED_URL}"
  data-token="${SAMPLE_TOKEN}"
  data-size="lg"
  data-chain-link="true"></script>`,
  },
  {
    label: "Programmatic mount (after page load)",
    code: `<script src="${EMBED_URL}"></script>
<div id="fl-badge"></div>
<script>
  FourLife.mount({
    target: document.getElementById("fl-badge"),
    token: "${SAMPLE_TOKEN}",
    size: "md",
  });
<\/script>`,
  },
];

type Tier = "graduated" | "graduation_watch" | "healthy" | "at_risk" | "observed";

const TIER_EXAMPLES: { tier: Tier; label: string; description: string; token: string }[] = [
  {
    tier: "graduation_watch",
    label: "Graduation Watch",
    description: "Curve past 70%, buys outpacing sells, healthy distribution.",
    token: SAMPLE_TOKEN,
  },
  {
    tier: "healthy",
    label: "Healthy",
    description: "Clean distribution, rising holders, positive buy pressure after 1h.",
    token: "0x72b0a042e19871c046c1bd31e5b5ad3770c94444",
  },
  {
    tier: "observed",
    label: "Observed",
    description: "Tracked but not enough signal yet to trust-grade.",
    token: "0xc5f692f3b484e76518b72191b9a11bed06284444",
  },
];

function Snippet({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="relative card p-0 overflow-hidden">
      <pre className="p-4 text-xs md:text-sm text-[#a7f7b5] font-mono whitespace-pre-wrap leading-relaxed">
        {code}
      </pre>
      <button
        onClick={() => {
          navigator.clipboard?.writeText(code);
          setCopied(true);
          setTimeout(() => setCopied(false), 1400);
        }}
        className="absolute top-2 right-2 text-[10px] px-2.5 py-1 rounded-full border border-white/10 bg-white/5 hover:bg-white/10 text-white/70 font-semibold uppercase tracking-wider"
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

function LiveBadgeSlot({ token, size = "md", chainLink = false }: { token: string; size?: "sm" | "md" | "lg"; chainLink?: boolean }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    // Ensure embed.js is loaded once, then mount programmatically
    const ensureScript = () =>
      new Promise<void>((resolve) => {
        if ((window as unknown as { FourLife?: unknown }).FourLife) return resolve();
        const existing = document.querySelector<HTMLScriptElement>('script[data-fl-loader]');
        if (existing) {
          existing.addEventListener("load", () => resolve());
          return;
        }
        const s = document.createElement("script");
        s.src = EMBED_URL;
        s.async = true;
        s.setAttribute("data-fl-loader", "1");
        s.addEventListener("load", () => resolve());
        document.head.appendChild(s);
      });

    let instance: { destroy?: () => void } | null = null;
    ensureScript().then(() => {
      const FL = (window as unknown as {
        FourLife?: { mount: (o: { target: Element; token: string; size?: string; chainLink?: boolean }) => { destroy?: () => void } };
      }).FourLife;
      if (FL && ref.current) {
        // Clear any previous child from a re-render
        while (ref.current.firstChild) ref.current.removeChild(ref.current.firstChild);
        instance = FL.mount({ target: ref.current, token, size, chainLink });
      }
    });

    return () => {
      if (instance?.destroy) instance.destroy();
    };
  }, [token, size, chainLink]);

  return <div ref={ref} />;
}

export default function EmbedDocsPage() {
  return (
    <div className="min-h-screen bg-[#0f1012] text-white bg-grid">
      {/* Header */}
      <header className="border-b border-white/5 sticky top-0 z-30 bg-[#0f1012]/90 backdrop-blur-md">
        <div className="max-w-5xl mx-auto px-5 py-4 flex items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-2">
            <span className="h-8 w-8 rounded-lg bg-gradient-to-br from-[#6cff32] to-[#00d4ff] flex items-center justify-center font-bold text-black">4</span>
            <div>
              <div className="text-sm font-semibold">FOUR-LIFE</div>
              <div className="text-[10px] text-white/40 uppercase tracking-wider">Embed Widget</div>
            </div>
          </Link>
          <div className="flex items-center gap-2">
            <Link href="/radar" className="btn-pill bg-white/5 hover:bg-white/10 border border-white/10 text-xs">Radar</Link>
            <a
              href="https://github.com/Ridwannurudeen/four-life"
              target="_blank" rel="noopener noreferrer"
              className="btn-pill bg-transparent hover:bg-white/5 border border-white/10 text-white/70 text-xs"
            >
              GitHub
            </a>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-5 pt-16 pb-10">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-[#00d4ff]/30 bg-[#00d4ff]/5 px-3 py-1 mb-5">
            <span className="h-1.5 w-1.5 rounded-full bg-[#00d4ff]" />
            <span className="text-[11px] font-medium text-[#00d4ff] tracking-wide uppercase">One-line install</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
            Drop a <span className="gradient-text">live trust badge</span> anywhere.
          </h1>
          <p className="text-white/60 text-base md:text-lg leading-relaxed mb-6">
            A single <code className="font-mono bg-white/10 px-1.5 py-0.5 rounded text-[#6cff32]">&lt;script&gt;</code> tag.
            The FOUR-LIFE Certified tier renders in place — auto-refreshes every 60 seconds, click for the full rule trace.
            No build step. No dependencies. No tracking. Works in any HTML page, Discord-embeddable landing, or creator project site.
          </p>

          {/* Live hero preview */}
          <div className="card p-5 flex items-center gap-5 flex-wrap">
            <div className="text-xs uppercase tracking-wider text-white/40">Live preview</div>
            <LiveBadgeSlot token={SAMPLE_TOKEN} size="md" />
            <div className="text-[11px] text-white/40 font-mono truncate">{SAMPLE_TOKEN}</div>
          </div>
        </div>
      </section>

      {/* Install snippets */}
      <section className="max-w-5xl mx-auto px-5 pb-12">
        <h2 className="text-xs uppercase tracking-wider text-white/40 mb-4">Install</h2>
        <div className="grid grid-cols-1 md:grid-cols-1 gap-3">
          {SNIPPETS.map((s) => (
            <div key={s.label}>
              <div className="text-[11px] text-white/50 mb-1.5">{s.label}</div>
              <Snippet code={s.code} />
            </div>
          ))}
        </div>
      </section>

      {/* Tier gallery */}
      <section className="max-w-5xl mx-auto px-5 pb-12">
        <h2 className="text-xs uppercase tracking-wider text-white/40 mb-4">What each tier looks like</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {TIER_EXAMPLES.map((ex) => (
            <div key={ex.token} className="card p-5 flex flex-col gap-3">
              <LiveBadgeSlot token={ex.token} size="md" />
              <div>
                <div className="text-sm font-semibold mb-1">{ex.label}</div>
                <div className="text-xs text-white/50">{ex.description}</div>
              </div>
              <div className="text-[10px] font-mono text-white/30 truncate">{ex.token}</div>
            </div>
          ))}
        </div>
        <div className="text-[11px] text-white/40 mt-3">
          Tiers update live from the API. Actual tier depends on current metrics — expect variation as the market moves.
        </div>
      </section>

      {/* Attributes */}
      <section className="max-w-5xl mx-auto px-5 pb-12">
        <h2 className="text-xs uppercase tracking-wider text-white/40 mb-4">Attributes</h2>
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-white/5">
              <tr className="text-left text-[10px] uppercase tracking-wider text-white/50">
                <th className="px-4 py-2">Attribute</th>
                <th className="px-4 py-2">Values</th>
                <th className="px-4 py-2">Default</th>
                <th className="px-4 py-2">Purpose</th>
              </tr>
            </thead>
            <tbody className="text-xs">
              {[
                ["data-token", "0x… (or ?token=0x…)", "—", "Four.meme token address (required)"],
                ["data-size", "sm | md | lg", "md", "Pill size"],
                ["data-theme", "dark | light", "dark", "Color scheme"],
                ["data-chain-link", "true | false", "false", "Link pill to four.meme/token/…"],
                ["data-modal", "true | false", "true", "Open rule-trace modal on click"],
              ].map((row) => (
                <tr key={row[0]} className="border-t border-white/5">
                  <td className="px-4 py-2 font-mono text-[#6cff32]">{row[0]}</td>
                  <td className="px-4 py-2 font-mono text-white/70">{row[1]}</td>
                  <td className="px-4 py-2 font-mono text-white/40">{row[2]}</td>
                  <td className="px-4 py-2 text-white/60">{row[3]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Where to use it */}
      <section className="max-w-5xl mx-auto px-5 pb-16">
        <h2 className="text-xs uppercase tracking-wider text-white/40 mb-4">Drop it anywhere</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { title: "Creator landing page", body: "Show a live trust badge above your fold. Updates every 60s." },
            { title: "Discord server description", body: "Host a one-pager with the embed; pin the link in your server." },
            { title: "X / Twitter bio link-tree", body: "Any link-tree page that allows custom HTML works." },
            { title: "GitHub README (via iframe)", body: "Wrap the script inside an iframe on a static host and link to it." },
            { title: "Project docs", body: "Show your project's current trust grade next to the token address." },
            { title: "Third-party dashboards", body: "Any page where you control a <script> tag — aggregator dashboards welcome." },
          ].map((b) => (
            <div key={b.title} className="card p-4">
              <div className="text-sm font-semibold mb-1">{b.title}</div>
              <div className="text-xs text-white/50">{b.body}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Footer CTA */}
      <footer className="border-t border-white/5 py-10 px-5 text-center">
        <div className="max-w-3xl mx-auto space-y-3">
          <div className="text-sm text-white/60">
            Every badge is deterministic and auditable — click any widget to see the exact rules that fired.
          </div>
          <div className="flex items-center justify-center gap-3 flex-wrap text-xs">
            <Link href="/radar" className="btn-pill bg-[#6cff32] hover:bg-[#6cff32]/90 text-black">Browse the Radar →</Link>
            <a href="https://github.com/Ridwannurudeen/four-life" target="_blank" rel="noopener noreferrer" className="btn-pill bg-white/5 hover:bg-white/10 border border-white/10">GitHub</a>
            <a href="https://four-life.gudman.xyz/api/identity" target="_blank" rel="noopener noreferrer" className="btn-pill bg-transparent hover:bg-white/5 border border-white/10 text-white/70">ERC-8004</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
