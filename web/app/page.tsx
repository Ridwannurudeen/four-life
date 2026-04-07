"use client";

import { useEffect, useState, useCallback } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "";

interface AgentStatus {
  agent_name: string;
  running: boolean;
  agent_id: number | null;
  wallet: string;
  total_launches: number;
  total_graduations: number;
  graduation_rate: number;
  avg_peak_holders: number;
  active_tokens: number;
  global_learnings: string[];
}

interface Token {
  address: string;
  name: string;
  symbol: string;
  phase: string;
  age_hours: number;
  health_score: number;
  graduation_probability: number;
  unique_buyers: number;
  buy_sell_ratio: number;
  top_holder_pct: number;
  curve_progress: number;
  holder_velocity: number;
  narrative: string;
}

interface Action {
  token_address: string;
  action_type: string;
  content: string;
  urgency: string;
  reasoning: string;
  timestamp: number;
  tweet_id: string | null;
}

interface Concept {
  name: string;
  symbol: string;
  description: string;
  lore: string;
  personality: string;
  meme_angles: string[];
  launch_hook: string;
  narrative: string;
  market_analysis?: {
    trending_narratives: { name: string; strength: number; saturation_level: string }[];
    opportunity_gaps: { name: string; reason: string }[];
    recommended_narrative: { name: string; reasoning: string };
  };
}

/* ── Shared Components ─────────────────────────────────── */

function PhaseTag({ phase }: { phase: string }) {
  const colors: Record<string, string> = {
    nurture: "bg-green-500/20 text-green-400 border-green-500/30",
    defend: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    accelerate: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    graduated: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  };
  return (
    <span className={`px-2 py-0.5 text-xs font-mono border rounded ${colors[phase] || "bg-gray-700 text-gray-300"}`}>
      {phase.toUpperCase()}
    </span>
  );
}

function HealthBar({ score }: { score: number }) {
  const color = score >= 70 ? "bg-green-500" : score >= 40 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="w-full bg-gray-800 rounded-full h-2">
      <div className={`${color} h-2 rounded-full transition-all duration-700`} style={{ width: `${score}%` }} />
    </div>
  );
}

function CurveBar({ progress }: { progress: number }) {
  return (
    <div className="relative w-full bg-gray-800 rounded-full h-4">
      <div
        className="bg-gradient-to-r from-blue-600 to-cyan-400 h-4 rounded-full transition-all duration-700"
        style={{ width: `${Math.min(100, progress)}%` }}
      />
      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-mono text-white/80">
        {progress.toFixed(1)}% / 18 BNB
      </span>
    </div>
  );
}

function StatCard({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: string }) {
  return (
    <div className={`bg-gray-900/80 border rounded-xl p-4 ${accent ? `border-${accent}-500/30` : "border-gray-800"}`}>
      <div className="text-[10px] text-gray-500 uppercase tracking-widest">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${accent ? `text-${accent}-400` : "text-white"}`}>{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  );
}

function Pulse() {
  return <span className="relative flex h-2.5 w-2.5"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" /><span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" /></span>;
}

/* ── Concept Generator ─────────────────────────────────── */

function ConceptPanel() {
  const [concept, setConcept] = useState<Concept | null>(null);
  const [loading, setLoading] = useState(false);
  const [trackAddress, setTrackAddress] = useState("");
  const [trackStatus, setTrackStatus] = useState("");

  const generate = useCallback(async () => {
    setLoading(true);
    setConcept(null);
    try {
      const res = await fetch(`${API}/api/agent/think`, { method: "POST" });
      const data = await res.json();
      if (data.concept) setConcept(data.concept);
    } catch {
      /* ignore */
    }
    setLoading(false);
  }, []);

  const track = useCallback(async () => {
    if (!trackAddress || !concept) return;
    setTrackStatus("Tracking...");
    try {
      const res = await fetch(`${API}/api/agent/track`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token_address: trackAddress,
          name: concept.name,
          symbol: concept.symbol,
          concept,
        }),
      });
      const data = await res.json();
      setTrackStatus(data.status === "tracking" ? "Tracking active!" : data.error || "Error");
    } catch {
      setTrackStatus("Failed");
    }
  }, [trackAddress, concept]);

  return (
    <div className="bg-gray-900/80 border border-gray-800 rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between">
        <div>
          <h2 className="font-bold">AI Concept Generator</h2>
          <p className="text-xs text-gray-500 mt-0.5">Agent analyzes Four.meme market and generates optimal token concepts</p>
        </div>
        <button
          onClick={generate}
          disabled={loading}
          className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg text-sm font-medium transition-colors"
        >
          {loading ? "Thinking..." : "Generate Concept"}
        </button>
      </div>

      {loading && (
        <div className="p-8 text-center">
          <div className="inline-block w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-gray-400 mt-3">Analyzing narratives via DGrid AI Gateway...</p>
        </div>
      )}

      {concept && !loading && (
        <div className="p-5 space-y-5">
          {/* Token identity */}
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3">
                <h3 className="text-xl font-bold text-cyan-400">{concept.name}</h3>
                <span className="text-gray-400 font-mono">${concept.symbol}</span>
              </div>
              <p className="text-sm text-gray-300 mt-1 max-w-xl">{concept.description}</p>
            </div>
            <span className="px-2 py-1 text-xs bg-cyan-900/40 text-cyan-400 border border-cyan-500/20 rounded font-mono">
              {concept.narrative}
            </span>
          </div>

          {/* Lore */}
          <div className="bg-gray-800/50 rounded-lg p-4">
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Origin Lore</div>
            <p className="text-sm text-gray-300 leading-relaxed">{concept.lore}</p>
          </div>

          {/* Launch hook */}
          <div className="bg-cyan-950/30 border border-cyan-500/10 rounded-lg p-4">
            <div className="text-xs text-cyan-500 uppercase tracking-wider mb-2">Launch Hook</div>
            <p className="text-sm text-white font-medium">{concept.launch_hook}</p>
          </div>

          {/* Meme angles */}
          {concept.meme_angles && (
            <div>
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Meme Angles</div>
              <div className="flex flex-wrap gap-2">
                {concept.meme_angles.map((angle, i) => (
                  <span key={i} className="px-3 py-1.5 bg-gray-800 text-gray-300 text-xs rounded-lg">{angle}</span>
                ))}
              </div>
            </div>
          )}

          {/* Market analysis */}
          {concept.market_analysis && (
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Trending Narratives</div>
                <div className="space-y-2">
                  {concept.market_analysis.trending_narratives?.map((n, i) => (
                    <div key={i} className="flex items-center justify-between text-sm">
                      <span className="text-gray-300">{n.name}</span>
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-gray-800 rounded-full h-1.5">
                          <div className="bg-cyan-500 h-1.5 rounded-full" style={{ width: `${n.strength * 10}%` }} />
                        </div>
                        <span className={`text-xs font-mono ${n.saturation_level === "high" ? "text-red-400" : n.saturation_level === "medium" ? "text-yellow-400" : "text-green-400"}`}>
                          {n.saturation_level}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Opportunity Gaps</div>
                <div className="space-y-2">
                  {concept.market_analysis.opportunity_gaps?.map((g, i) => (
                    <div key={i} className="text-sm">
                      <span className="text-green-400 font-medium">{g.name}</span>
                      <p className="text-xs text-gray-500 mt-0.5">{g.reason}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Track token */}
          <div className="bg-gray-800/50 rounded-lg p-4">
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Track This Token</div>
            <p className="text-xs text-gray-500 mb-3">Create this token on four.meme, then paste the contract address below.</p>
            <div className="flex gap-2">
              <input
                type="text"
                value={trackAddress}
                onChange={(e) => setTrackAddress(e.target.value)}
                placeholder="0x... token address from Four.meme"
                className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm font-mono text-white placeholder-gray-600 focus:border-cyan-500 focus:outline-none"
              />
              <button
                onClick={track}
                disabled={!trackAddress}
                className="px-4 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg text-sm font-medium transition-colors"
              >
                Track
              </button>
            </div>
            {trackStatus && <p className="text-xs mt-2 text-cyan-400">{trackStatus}</p>}
          </div>
        </div>
      )}

      {!concept && !loading && (
        <div className="p-8 text-center text-gray-600">
          <p className="text-sm">Click "Generate Concept" to analyze the Four.meme market</p>
          <p className="text-xs mt-1">Powered by DGrid AI Gateway</p>
        </div>
      )}
    </div>
  );
}

/* ── Memory Panel ──────────────────────────────────────── */

interface LaunchRecord {
  name: string;
  symbol: string;
  narrative: string;
  launched_at: number;
  peak_holders: number;
  peak_health_score: number;
  peak_curve_progress: number;
  graduated: boolean;
  what_worked: string[];
  what_failed: string[];
}

function MemoryPanel({ status }: { status: AgentStatus | null }) {
  const [launches, setLaunches] = useState<LaunchRecord[]>([]);

  useEffect(() => {
    fetch(`${API}/api/memory`)
      .then((r) => r.json())
      .then((data) => setLaunches(data.launches || []))
      .catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      {/* Launch History */}
      <div className="bg-gray-900/80 border border-gray-800/50 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-800/50">
          <h2 className="font-bold">Launch History</h2>
          <p className="text-xs text-gray-500 mt-0.5">Every token the agent has created and managed</p>
        </div>
        {launches.length === 0 ? (
          <div className="p-8 text-center text-gray-600 text-sm">No launches recorded yet.</div>
        ) : (
          <div className="divide-y divide-gray-800/50">
            {launches.map((launch, i) => (
              <div key={i} className="p-4 hover:bg-gray-800/20 transition-colors">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <span className="text-lg font-bold">{launch.name}</span>
                    <span className="text-gray-400 font-mono text-sm">${launch.symbol}</span>
                    {launch.graduated ? (
                      <span className="px-2 py-0.5 text-[10px] bg-green-900/40 text-green-400 border border-green-500/20 rounded font-mono">GRADUATED</span>
                    ) : (
                      <span className="px-2 py-0.5 text-[10px] bg-gray-800 text-gray-400 border border-gray-700 rounded font-mono">ACTIVE</span>
                    )}
                  </div>
                  <span className="text-[10px] text-gray-600">
                    {launch.launched_at ? new Date(launch.launched_at * 1000).toLocaleDateString() + " " + new Date(launch.launched_at * 1000).toLocaleTimeString() : "—"}
                  </span>
                </div>
                <div className="grid grid-cols-4 gap-4 text-sm mt-2">
                  <div>
                    <div className="text-[10px] text-gray-600">Narrative</div>
                    <div className="text-cyan-400 text-xs">{launch.narrative || "—"}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-gray-600">Peak Holders</div>
                    <div className="font-mono">{launch.peak_holders}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-gray-600">Peak Health</div>
                    <div className="font-mono">{launch.peak_health_score}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-gray-600">Curve Peak</div>
                    <div className="font-mono">{launch.peak_curve_progress}%</div>
                  </div>
                </div>
                {(launch.what_worked.length > 0 || launch.what_failed.length > 0) && (
                  <div className="mt-3 flex gap-4">
                    {launch.what_worked.map((w, j) => (
                      <span key={j} className="text-[10px] text-green-500">{w}</span>
                    ))}
                    {launch.what_failed.map((f, j) => (
                      <span key={j} className="text-[10px] text-red-400">{f}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Learnings */}
      <div className="bg-gray-900/80 border border-gray-800/50 rounded-xl p-5">
        <h2 className="font-bold mb-4">Agent Learnings</h2>
        {!status || status.global_learnings.length === 0 ? (
          <p className="text-gray-600 text-sm">No learnings yet. The agent evaluates each launch after 72h and extracts patterns.</p>
        ) : (
          <div className="space-y-3">
            {status.global_learnings.map((learning, i) => (
              <div key={i} className="flex gap-3 text-sm">
                <span className="text-gray-700 font-mono shrink-0 w-6 text-right">#{i + 1}</span>
                <span className="text-gray-300">{learning}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Architecture */}
      <div className="bg-gray-900/80 border border-gray-800/50 rounded-xl p-5">
        <h2 className="font-bold mb-2">Architecture</h2>
        <pre className="text-[10px] text-gray-500 font-mono leading-relaxed overflow-x-auto">{`
FOUR-LIFE Agent Loop
--------------------
THINK  ->  Analyze Four.meme market via DGrid AI Gateway
           Detect narrative gaps, trending themes, saturation
           Generate token concept (name, lore, personality, memes)

BIRTH  ->  Create token on Four.meme (via Agentic Mode API)
           Generate artwork (DALL-E), upload, deploy on-chain
           Post launch thread to Twitter/X

RAISE  ->  Monitor health: holders, whales, buy/sell, curve progress
           Phase management: nurture (0-6h) -> defend (6-24h) -> accelerate (24-72h)
           Generate content, celebrate milestones, post transparency updates
           Graduation probability prediction

LEARN  ->  Evaluate outcomes after 72h
           Record what worked/failed per narrative
           Improve strategy for next launch via Unibase memory

Stack: DGrid AI (LLM) | BNB Chain (web3) | ERC-8004 (identity) | Four.meme (launch) | MYX V2 (perps)
        `.trim()}</pre>
      </div>
    </div>
  );
}

/* ── Main Dashboard ────────────────────────────────────── */

export default function Dashboard() {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [tokens, setTokens] = useState<Token[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"overview" | "generate" | "memory">("overview");

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [s, t, a] = await Promise.all([
          fetch(`${API}/api/status`).then((r) => r.json()),
          fetch(`${API}/api/tokens`).then((r) => r.json()),
          fetch(`${API}/api/actions?limit=20`).then((r) => r.json()),
        ]);
        setStatus(s);
        setTokens(t.tokens || []);
        setActions(a.actions || []);
        setError("");
      } catch {
        setError("Agent offline");
      }
    };

    fetchAll();
    const interval = setInterval(fetchAll, 10000);
    return () => clearInterval(interval);
  }, []);

  const startAgent = async () => {
    await fetch(`${API}/api/agent/start`, { method: "POST" });
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Header */}
      <header className="border-b border-gray-800/50 backdrop-blur-sm bg-black/50 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {status?.running ? <Pulse /> : <div className="w-2.5 h-2.5 rounded-full bg-red-500" />}
            <h1 className="text-lg font-bold tracking-tight bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              FOUR-LIFE
            </h1>
            <span className="text-[10px] text-gray-600 font-mono">v1.0.0</span>
          </div>

          <div className="flex items-center gap-3">
            {/* Tabs */}
            <nav className="flex gap-1 bg-gray-900/50 rounded-lg p-0.5">
              {(["overview", "generate", "memory"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    tab === t ? "bg-gray-800 text-white" : "text-gray-500 hover:text-gray-300"
                  }`}
                >
                  {t === "overview" ? "Dashboard" : t === "generate" ? "Generate" : "Memory"}
                </button>
              ))}
            </nav>

            {status?.agent_id && (
              <span className="text-[10px] text-gray-500 font-mono bg-gray-900 px-2 py-1 rounded">ERC-8004 #{status.agent_id}</span>
            )}
            {status?.wallet && (
              <span className="text-[10px] text-gray-600 font-mono">
                {status.wallet.slice(0, 6)}...{status.wallet.slice(-4)}
              </span>
            )}
            <span
              onClick={!status?.running ? startAgent : undefined}
              className={`px-2 py-1 rounded text-[10px] font-mono cursor-pointer ${
                status?.running
                  ? "bg-green-900/30 text-green-400 border border-green-500/20"
                  : "bg-red-900/30 text-red-400 border border-red-500/20 hover:bg-red-900/50"
              }`}
            >
              {status?.running ? "LIVE" : error || "OFFLINE (click to start)"}
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* ── Overview Tab ── */}
        {tab === "overview" && (
          <>
            {/* Hero — always visible */}
            <div className="bg-gradient-to-br from-cyan-950/40 via-gray-900/80 to-blue-950/40 border border-cyan-500/10 rounded-2xl p-8 md:p-10">
              <div className="max-w-3xl">
                <h2 className="text-3xl md:text-4xl font-bold leading-tight">
                  The first AI agent that doesn&apos;t just launch tokens —{" "}
                  <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">it raises them.</span>
                </h2>
                <p className="text-gray-400 mt-4 text-sm leading-relaxed max-w-2xl">
                  FOUR-LIFE autonomously analyzes the Four.meme market, generates optimized token concepts,
                  and manages their entire lifecycle through four phases — THINK, BIRTH, RAISE, and LEARN.
                  Every decision is powered by DGrid AI Gateway. Every identity is verified on-chain via ERC-8004.
                </p>
                <div className="flex flex-wrap gap-3 mt-6">
                  <span className="px-3 py-1.5 bg-cyan-900/30 border border-cyan-500/20 rounded-lg text-xs text-cyan-400">DGrid AI Gateway</span>
                  <span className="px-3 py-1.5 bg-purple-900/30 border border-purple-500/20 rounded-lg text-xs text-purple-400">ERC-8004 Agent #16</span>
                  <span className="px-3 py-1.5 bg-green-900/30 border border-green-500/20 rounded-lg text-xs text-green-400">Four.meme Agentic Mode</span>
                  <span className="px-3 py-1.5 bg-yellow-900/30 border border-yellow-500/20 rounded-lg text-xs text-yellow-400">MYX V2 Perps</span>
                  <span className="px-3 py-1.5 bg-blue-900/30 border border-blue-500/20 rounded-lg text-xs text-blue-400">BNB Chain</span>
                </div>
              </div>
            </div>

            {/* Lifecycle phases */}
            <div className="grid md:grid-cols-4 gap-3">
              {[
                { phase: "THINK", color: "cyan", desc: "Analyzes Four.meme market, detects narrative gaps, generates token concepts with lore and personality" },
                { phase: "BIRTH", color: "blue", desc: "Creates tokens via Agentic Mode, generates artwork, posts launch threads to Twitter/X" },
                { phase: "RAISE", color: "green", desc: "Monitors health, manages nurture/defend/accelerate phases, generates adaptive content" },
                { phase: "LEARN", color: "purple", desc: "Evaluates outcomes, records learnings, improves strategy for next launch via persistent memory" },
              ].map((p) => (
                <div key={p.phase} className={`bg-gray-900/60 border border-${p.color}-500/10 rounded-xl p-4`}>
                  <div className={`text-${p.color}-400 font-bold font-mono text-sm mb-2`}>{p.phase}</div>
                  <p className="text-xs text-gray-500 leading-relaxed">{p.desc}</p>
                </div>
              ))}
            </div>

            {/* Stats */}
            {status && (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <StatCard label="Launches" value={status.total_launches} />
                <StatCard label="Graduations" value={status.total_graduations} accent={status.total_graduations > 0 ? "green" : undefined} />
                <StatCard label="Grad Rate" value={`${status.graduation_rate}%`} />
                <StatCard label="Avg Peak Holders" value={Math.round(status.avg_peak_holders)} />
                <StatCard label="Active Tokens" value={status.active_tokens} accent={status.active_tokens > 0 ? "cyan" : undefined} />
              </div>
            )}

            {/* Active Tokens */}
            <section>
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3">Active Tokens</h2>
              {tokens.length === 0 ? (
                <div className="bg-gray-900/50 border border-gray-800/50 rounded-xl p-8 text-center">
                  <div className="text-gray-500 text-sm">No active tokens yet</div>
                  <p className="text-gray-600 text-xs mt-2">Use the <button onClick={() => setTab("generate")} className="text-cyan-500 hover:underline">Generate</button> tab to create a concept, launch it on four.meme, then track it here.</p>
                </div>
              ) : (
                <div className="grid gap-3">
                  {tokens.map((token) => (
                    <div key={token.address} className="bg-gray-900/80 border border-gray-800/50 rounded-xl p-5">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <h3 className="font-bold text-lg">{token.name}</h3>
                          <span className="text-gray-400 font-mono text-sm">${token.symbol}</span>
                          <PhaseTag phase={token.phase} />
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold">{token.health_score}</div>
                          <div className="text-[10px] text-gray-500">HEALTH</div>
                        </div>
                      </div>

                      <div className="space-y-2 mb-4">
                        <div className="flex items-center justify-between text-xs text-gray-500">
                          <span>Health</span>
                          <span>{token.health_score}/100</span>
                        </div>
                        <HealthBar score={token.health_score} />
                        <div className="flex items-center justify-between text-xs text-gray-500">
                          <span>Bonding Curve</span>
                          <span>{token.graduation_probability}% grad probability</span>
                        </div>
                        <CurveBar progress={token.curve_progress} />
                      </div>

                      <div className="grid grid-cols-3 md:grid-cols-6 gap-3 text-sm">
                        <div><div className="text-[10px] text-gray-600">Holders</div><div className="font-mono font-bold">{token.unique_buyers}</div></div>
                        <div><div className="text-[10px] text-gray-600">Velocity</div><div className="font-mono">{token.holder_velocity}/h</div></div>
                        <div><div className="text-[10px] text-gray-600">Buy/Sell</div><div className={`font-mono ${token.buy_sell_ratio >= 1.5 ? "text-green-400" : token.buy_sell_ratio < 1 ? "text-red-400" : ""}`}>{token.buy_sell_ratio}</div></div>
                        <div><div className="text-[10px] text-gray-600">Top Holder</div><div className={`font-mono ${token.top_holder_pct > 30 ? "text-red-400" : ""}`}>{token.top_holder_pct}%</div></div>
                        <div><div className="text-[10px] text-gray-600">Curve</div><div className="font-mono">{token.curve_progress}%</div></div>
                        <div><div className="text-[10px] text-gray-600">Age</div><div className="font-mono">{token.age_hours.toFixed(1)}h</div></div>
                      </div>

                      <div className="mt-3 text-[10px] text-gray-700 font-mono">
                        {token.address} | {token.narrative}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Decision Log */}
            <section>
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3">Decision Log</h2>
              <div className="bg-gray-900/50 border border-gray-800/50 rounded-xl divide-y divide-gray-800/50">
                {actions.length === 0 ? (
                  <div className="p-8 text-center text-gray-600 text-sm">No actions yet. The agent will log decisions here as it manages tokens.</div>
                ) : (
                  actions.map((action, i) => (
                    <div key={i} className="p-4">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`px-1.5 py-0.5 text-[10px] rounded font-mono ${
                          action.urgency === "high" ? "bg-red-900/50 text-red-400"
                            : action.urgency === "medium" ? "bg-yellow-900/50 text-yellow-400"
                            : "bg-gray-800 text-gray-400"
                        }`}>{action.action_type}</span>
                        <span className="text-[10px] text-gray-600">{new Date(action.timestamp * 1000).toLocaleTimeString()}</span>
                        {action.tweet_id && (
                          <a href={`https://x.com/i/status/${action.tweet_id}`} target="_blank" rel="noopener" className="text-[10px] text-cyan-500 hover:underline">tweet</a>
                        )}
                      </div>
                      <div className="text-sm text-gray-300">{action.content}</div>
                      <div className="text-[10px] text-gray-600 mt-1">{action.reasoning}</div>
                    </div>
                  ))
                )}
              </div>
            </section>
          </>
        )}

        {/* ── Generate Tab ── */}
        {tab === "generate" && <ConceptPanel />}

        {/* ── Memory Tab ── */}
        {tab === "memory" && <MemoryPanel status={status} />}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800/30 px-6 py-4 mt-8">
        <div className="max-w-7xl mx-auto flex items-center justify-between text-[10px] text-gray-700">
          <span>FOUR-LIFE | Autonomous Meme Token Lifecycle Agent</span>
          <div className="flex gap-4">
            <span>Four.meme AI Sprint 2026</span>
            <span>Powered by DGrid AI</span>
            <span>ERC-8004 on BNB Chain</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
