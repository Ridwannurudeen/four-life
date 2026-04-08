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

/* ── Token Scanner (Public Tool) ───────────────────────── */

interface ScanResult {
  token_address: string;
  name: string;
  symbol: string;
  health_score: number;
  graduation_probability: number;
  phase?: string;
  age_hours?: number;
  holders: number;
  holder_velocity?: number;
  buy_sell_ratio?: number;
  top_holder_pct?: number;
  whale_count?: number;
  curve_progress: number;
  buy_volume_bnb?: number;
  sell_volume_bnb?: number;
  volume_bnb?: number;
  risk_factors: string[];
  suggested_action: string;
}

interface RaisePlan {
  phases?: { name: string; actions: string[]; content_suggestions: string[]; risk_checks: string[] }[];
  graduation_strategy?: string;
}

interface HedgeSignal {
  action: string;
  confidence: number;
  reasoning: string;
  size_pct: number;
}

function TokenScanner() {
  const [address, setAddress] = useState("");
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState("");

  const [planLoading, setPlanLoading] = useState(false);
  const [plan, setPlan] = useState<RaisePlan | null>(null);

  const [signalLoading, setSignalLoading] = useState(false);
  const [signal, setSignal] = useState<HedgeSignal | null>(null);

  const scan = useCallback(async () => {
    const addr = address.trim();
    if (!addr || !addr.startsWith("0x")) { setError("Enter a valid BSC token address"); return; }
    setScanning(true);
    setResult(null);
    setPlan(null);
    setSignal(null);
    setError("");
    try {
      const res = await fetch(`${API}/api/health-score/${addr}`);
      if (!res.ok) throw new Error("API error");
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scan failed");
    }
    setScanning(false);
  }, [address]);

  const fetchPlan = useCallback(async () => {
    if (!result) return;
    setPlanLoading(true);
    setPlan(null);
    try {
      const res = await fetch(`${API}/api/raise-plan/${result.token_address}`, { method: "POST" });
      const data = await res.json();
      setPlan(data.plan || null);
    } catch { /* ignore */ }
    setPlanLoading(false);
  }, [result]);

  const fetchSignal = useCallback(async () => {
    if (!result) return;
    setSignalLoading(true);
    setSignal(null);
    try {
      const res = await fetch(`${API}/api/myx/signal/${result.token_address}`);
      const data = await res.json();
      setSignal(data.signal || null);
    } catch { /* ignore */ }
    setSignalLoading(false);
  }, [result]);

  const healthColor = (s: number) => s >= 70 ? "text-green-400" : s >= 40 ? "text-yellow-400" : "text-red-400";
  const healthBg = (s: number) => s >= 70 ? "from-green-500" : s >= 40 ? "from-yellow-500" : "from-red-500";
  const gradColor = (g: number) => g >= 50 ? "text-green-400" : g >= 25 ? "text-yellow-400" : "text-gray-400";
  const signalColor = (a: string) =>
    a === "long" ? "text-green-400 bg-green-900/30 border-green-500/20" :
    a === "short" ? "text-red-400 bg-red-900/30 border-red-500/20" :
    a === "close" ? "text-yellow-400 bg-yellow-900/30 border-yellow-500/20" :
    "text-gray-400 bg-gray-800 border-gray-700";

  return (
    <div className="space-y-5">
      {/* Search Bar */}
      <div className="bg-gradient-to-br from-cyan-950/50 via-gray-900/90 to-blue-950/50 border border-cyan-500/20 rounded-2xl p-6 md:p-8">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <h2 className="text-lg font-bold">Token Health Scanner</h2>
        </div>
        <p className="text-sm text-gray-400 mb-5">
          Paste any Four.meme token address to get an instant AI health assessment, graduation prediction, raise plan, and hedge signal.
        </p>
        <div className="flex gap-3">
          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && scan()}
            placeholder="0x... token address on BSC"
            className="flex-1 bg-black/60 border border-gray-700 rounded-xl px-4 py-3 text-sm font-mono text-white placeholder:text-gray-600 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/20 transition-colors"
          />
          <button
            onClick={scan}
            disabled={scanning}
            className="px-6 py-3 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 disabled:from-gray-700 disabled:to-gray-700 rounded-xl text-sm font-bold transition-all shrink-0"
          >
            {scanning ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Scanning
              </span>
            ) : "Scan"}
          </button>
        </div>
        {error && <p className="text-red-400 text-xs mt-3">{error}</p>}
      </div>

      {/* Scan Results */}
      {result && (
        <div className="space-y-4 animate-in fade-in duration-500">
          {/* Main metrics */}
          <div className="bg-gray-900/80 border border-gray-800/50 rounded-2xl overflow-hidden">
            {/* Header with token info */}
            <div className="bg-gradient-to-r from-gray-800/50 to-transparent px-6 py-5 border-b border-gray-800/50">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-3">
                    <h3 className="text-xl font-bold">{result.name || "Unknown Token"}</h3>
                    {result.symbol && <span className="text-gray-400 font-mono">${result.symbol}</span>}
                    {result.phase && <PhaseTag phase={result.phase} />}
                  </div>
                  <div className="text-[10px] text-gray-600 font-mono mt-1">{result.token_address}</div>
                </div>
                <div className="text-right">
                  <div className={`text-4xl font-black ${healthColor(result.health_score)}`}>{result.health_score}</div>
                  <div className="text-[10px] text-gray-500 uppercase tracking-widest">Health Score</div>
                </div>
              </div>

              {/* Health bar */}
              <div className="mt-4">
                <div className="w-full bg-gray-800 rounded-full h-3 overflow-hidden">
                  <div
                    className={`bg-gradient-to-r ${healthBg(result.health_score)} to-transparent h-3 rounded-full transition-all duration-1000`}
                    style={{ width: `${result.health_score}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Metrics grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-y md:divide-y-0 divide-gray-800/50">
              <div className="p-4 text-center">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">Graduation</div>
                <div className={`text-2xl font-bold mt-1 ${gradColor(result.graduation_probability)}`}>
                  {result.graduation_probability}%
                </div>
              </div>
              <div className="p-4 text-center">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">Holders</div>
                <div className="text-2xl font-bold mt-1 text-white">{result.holders}</div>
              </div>
              <div className="p-4 text-center">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">Bonding Curve</div>
                <div className="text-2xl font-bold mt-1 text-white">{result.curve_progress}%</div>
              </div>
              <div className="p-4 text-center">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">
                  {result.buy_volume_bnb !== undefined ? "Buy Volume" : "Volume"}
                </div>
                <div className="text-2xl font-bold mt-1 text-white">
                  {(result.buy_volume_bnb ?? result.volume_bnb ?? 0).toFixed(2)} BNB
                </div>
              </div>
            </div>

            {/* Detailed metrics (if tracked) */}
            {result.phase && (
              <div className="grid grid-cols-2 md:grid-cols-5 divide-x divide-y md:divide-y-0 divide-gray-800/50 border-t border-gray-800/50">
                <div className="p-3 text-center">
                  <div className="text-[10px] text-gray-600">Buy/Sell Ratio</div>
                  <div className={`font-mono text-sm font-bold ${(result.buy_sell_ratio ?? 0) >= 1.5 ? "text-green-400" : (result.buy_sell_ratio ?? 0) < 1 ? "text-red-400" : "text-white"}`}>
                    {result.buy_sell_ratio?.toFixed(2) ?? "—"}
                  </div>
                </div>
                <div className="p-3 text-center">
                  <div className="text-[10px] text-gray-600">Top Holder</div>
                  <div className={`font-mono text-sm font-bold ${(result.top_holder_pct ?? 0) > 30 ? "text-red-400" : "text-white"}`}>
                    {result.top_holder_pct?.toFixed(1) ?? "—"}%
                  </div>
                </div>
                <div className="p-3 text-center">
                  <div className="text-[10px] text-gray-600">Holder Velocity</div>
                  <div className="font-mono text-sm font-bold text-white">{result.holder_velocity ?? "—"}/h</div>
                </div>
                <div className="p-3 text-center">
                  <div className="text-[10px] text-gray-600">Whales</div>
                  <div className="font-mono text-sm font-bold text-white">{result.whale_count ?? "—"}</div>
                </div>
                <div className="p-3 text-center">
                  <div className="text-[10px] text-gray-600">Age</div>
                  <div className="font-mono text-sm font-bold text-white">{result.age_hours?.toFixed(1) ?? "—"}h</div>
                </div>
              </div>
            )}
          </div>

          {/* Risk factors */}
          {result.risk_factors.length > 0 && (
            <div className="bg-red-950/20 border border-red-500/15 rounded-xl p-4">
              <div className="text-[10px] text-red-400 uppercase tracking-wider font-bold mb-2">Risk Factors</div>
              <div className="space-y-1.5">
                {result.risk_factors.map((r, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm text-red-300/80">
                    <span className="text-red-500 mt-0.5 shrink-0">!</span>
                    <span>{r}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Suggested action */}
          <div className="bg-cyan-950/20 border border-cyan-500/15 rounded-xl p-4">
            <div className="text-[10px] text-cyan-400 uppercase tracking-wider font-bold mb-1">Suggested Action</div>
            <p className="text-sm text-cyan-200/80">{result.suggested_action}</p>
          </div>

          {/* Action buttons */}
          <div className="flex gap-3">
            <button
              onClick={fetchPlan}
              disabled={planLoading}
              className="flex-1 py-3 bg-gradient-to-r from-cyan-900/50 to-blue-900/50 hover:from-cyan-900/70 hover:to-blue-900/70 border border-cyan-500/20 rounded-xl text-sm font-bold text-cyan-300 transition-all disabled:opacity-50"
            >
              {planLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin" />
                  Generating via DGrid AI...
                </span>
              ) : plan ? "Regenerate Raise Plan" : "Generate 72h Raise Plan"}
            </button>
            <button
              onClick={fetchSignal}
              disabled={signalLoading}
              className="flex-1 py-3 bg-gradient-to-r from-yellow-900/40 to-orange-900/40 hover:from-yellow-900/60 hover:to-orange-900/60 border border-yellow-500/20 rounded-xl text-sm font-bold text-yellow-300 transition-all disabled:opacity-50"
            >
              {signalLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-yellow-400/30 border-t-yellow-400 rounded-full animate-spin" />
                  Analyzing via DGrid AI...
                </span>
              ) : signal ? "Refresh MYX Signal" : "Get MYX Hedge Signal"}
            </button>
          </div>

          {/* MYX Hedge Signal */}
          {signal && (
            <div className="bg-gray-900/80 border border-gray-800/50 rounded-xl p-5">
              <div className="flex items-center gap-3 mb-3">
                <h4 className="font-bold text-sm">MYX V2 Hedge Signal</h4>
                <span className={`px-3 py-1 text-xs font-mono font-bold uppercase rounded-lg border ${signalColor(signal.action)}`}>
                  {signal.action}
                </span>
                <span className="text-xs text-gray-500">{(signal.confidence * 100).toFixed(0)}% confidence</span>
                {signal.size_pct > 0 && (
                  <span className="text-xs text-gray-600 font-mono">{(signal.size_pct * 100).toFixed(1)}% size</span>
                )}
              </div>
              <p className="text-sm text-gray-400 leading-relaxed">{signal.reasoning}</p>
              <div className="mt-3 flex gap-2">
                <span className="px-2 py-0.5 text-[10px] bg-gray-800 rounded text-gray-500">BNB/USDT pair</span>
                <span className="px-2 py-0.5 text-[10px] bg-gray-800 rounded text-gray-500">5x leverage</span>
                <span className="px-2 py-0.5 text-[10px] bg-gray-800 rounded text-gray-500">Powered by DGrid AI</span>
              </div>
            </div>
          )}

          {/* Raise Plan */}
          {plan && (
            <div className="bg-gray-900/80 border border-cyan-500/10 rounded-xl p-5">
              <h4 className="font-bold text-cyan-400 mb-4">72-Hour Raise Plan</h4>
              <div className="space-y-4">
                {plan.phases?.map((phase, i) => (
                  <div key={i} className="bg-gray-800/30 rounded-lg p-4">
                    <h5 className="font-bold text-sm text-white mb-3">{phase.name}</h5>
                    <div className="grid md:grid-cols-3 gap-4">
                      <div>
                        <div className="text-[10px] text-cyan-500 uppercase tracking-wider mb-2 font-bold">Actions</div>
                        {phase.actions?.map((a, j) => (
                          <div key={j} className="flex items-start gap-2 text-xs text-gray-300 mb-1.5">
                            <span className="text-cyan-500 mt-0.5 shrink-0">&rarr;</span>
                            <span>{a}</span>
                          </div>
                        ))}
                      </div>
                      <div>
                        <div className="text-[10px] text-blue-400 uppercase tracking-wider mb-2 font-bold">Content</div>
                        {phase.content_suggestions?.map((c, j) => (
                          <div key={j} className="text-xs text-gray-400 mb-1.5">{c}</div>
                        ))}
                      </div>
                      <div>
                        <div className="text-[10px] text-yellow-500 uppercase tracking-wider mb-2 font-bold">Risk Checks</div>
                        {phase.risk_checks?.map((r, j) => (
                          <div key={j} className="flex items-start gap-2 text-xs text-yellow-500/70 mb-1.5">
                            <span className="shrink-0">!</span>
                            <span>{r}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
                {plan.graduation_strategy && (
                  <div className="bg-green-950/20 border border-green-500/10 rounded-lg p-4">
                    <div className="text-[10px] text-green-500 uppercase tracking-wider mb-1 font-bold">Graduation Strategy</div>
                    <p className="text-sm text-green-300">{plan.graduation_strategy}</p>
                  </div>
                )}
              </div>
              <div className="mt-3 text-[10px] text-gray-600 text-right">Powered by DGrid AI Gateway</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
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

/* ── Graduation Radar ──────────────────────────────────── */

interface RadarToken {
  token_address: string;
  name: string;
  symbol: string;
  holders: number;
  curve_progress: number;
  volume_bnb: number;
  increase_pct: number;
  health_score: number;
  graduation_probability: number;
  status: string;
}

function RadarPanel() {
  const [tokens, setTokens] = useState<RadarToken[]>([]);
  const [loading, setLoading] = useState(true);
  const [planToken, setPlanToken] = useState<string | null>(null);
  const [plan, setPlan] = useState<Record<string, unknown> | null>(null);
  const [planLoading, setPlanLoading] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/graduation-radar?limit=20`)
      .then((r) => r.json())
      .then((data) => { setTokens(data.radar || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const generatePlan = useCallback(async (addr: string) => {
    setPlanToken(addr);
    setPlanLoading(true);
    setPlan(null);
    try {
      const res = await fetch(`${API}/api/raise-plan/${addr}`, { method: "POST" });
      const data = await res.json();
      setPlan(data.plan || null);
    } catch { /* ignore */ }
    setPlanLoading(false);
  }, []);

  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-green-950/30 via-gray-900/80 to-cyan-950/30 border border-green-500/10 rounded-2xl p-6">
        <h2 className="text-2xl font-bold">Graduation Radar</h2>
        <p className="text-sm text-gray-400 mt-1">Live Four.meme tokens ranked by graduation probability. Updated every request.</p>
      </div>

      {loading ? (
        <div className="text-center py-12">
          <div className="inline-block w-6 h-6 border-2 border-green-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-gray-400 mt-3">Scanning Four.meme...</p>
        </div>
      ) : (
        <div className="bg-gray-900/50 border border-gray-800/50 rounded-xl overflow-hidden">
          <div className="grid grid-cols-[2fr_1fr_1fr_1fr_1fr_1fr_auto] gap-2 px-4 py-2 text-[10px] text-gray-500 uppercase tracking-wider border-b border-gray-800/50">
            <div>Token</div>
            <div className="text-right">Holders</div>
            <div className="text-right">Curve</div>
            <div className="text-right">Volume</div>
            <div className="text-right">Health</div>
            <div className="text-right">Grad %</div>
            <div></div>
          </div>
          {tokens.map((t, i) => (
            <div key={t.token_address} className={`grid grid-cols-[2fr_1fr_1fr_1fr_1fr_1fr_auto] gap-2 px-4 py-3 items-center ${i % 2 === 0 ? "" : "bg-gray-800/10"} hover:bg-gray-800/30 transition-colors`}>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-gray-600 font-mono text-xs w-5">{i + 1}</span>
                  <span className="font-medium text-sm truncate">{t.name}</span>
                  <span className="text-gray-500 font-mono text-xs">${t.symbol}</span>
                </div>
              </div>
              <div className="text-right font-mono text-sm">{t.holders}</div>
              <div className="text-right">
                <div className="inline-flex items-center gap-1">
                  <div className="w-12 bg-gray-800 rounded-full h-1.5">
                    <div className="bg-green-500 h-1.5 rounded-full" style={{ width: `${Math.min(100, t.curve_progress)}%` }} />
                  </div>
                  <span className="text-xs font-mono">{t.curve_progress}%</span>
                </div>
              </div>
              <div className="text-right font-mono text-xs text-gray-400">{t.volume_bnb} BNB</div>
              <div className="text-right">
                <span className={`font-mono text-sm font-bold ${t.health_score >= 70 ? "text-green-400" : t.health_score >= 40 ? "text-yellow-400" : "text-red-400"}`}>
                  {t.health_score}
                </span>
              </div>
              <div className="text-right">
                <span className={`font-mono text-sm font-bold ${t.graduation_probability >= 50 ? "text-green-400" : t.graduation_probability >= 25 ? "text-yellow-400" : "text-gray-400"}`}>
                  {t.graduation_probability}%
                </span>
              </div>
              <div>
                <button
                  onClick={() => generatePlan(t.token_address)}
                  className="px-2 py-1 text-[10px] bg-cyan-900/30 text-cyan-400 border border-cyan-500/20 rounded hover:bg-cyan-900/50 transition-colors"
                >
                  Plan
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Raise Plan Display */}
      {planToken && (
        <div className="bg-gray-900/80 border border-cyan-500/10 rounded-xl p-5">
          <h3 className="font-bold text-cyan-400 mb-3">72-Hour Raise Plan</h3>
          {planLoading ? (
            <div className="text-center py-6">
              <div className="inline-block w-5 h-5 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-xs text-gray-400 mt-2">Generating plan via DGrid AI...</p>
            </div>
          ) : plan ? (
            <div className="space-y-4">
              {(plan as { phases?: Array<{ name: string; actions: string[]; content_suggestions: string[]; risk_checks: string[] }> }).phases?.map((phase, i) => (
                <div key={i} className="bg-gray-800/30 rounded-lg p-4">
                  <h4 className="font-bold text-sm text-white mb-2">{phase.name}</h4>
                  <div className="grid md:grid-cols-3 gap-3 text-xs">
                    <div>
                      <div className="text-gray-500 uppercase tracking-wider mb-1">Actions</div>
                      {phase.actions?.map((a, j) => <div key={j} className="text-gray-300 mb-1">{a}</div>)}
                    </div>
                    <div>
                      <div className="text-gray-500 uppercase tracking-wider mb-1">Content</div>
                      {phase.content_suggestions?.map((c, j) => <div key={j} className="text-gray-400 mb-1">{c}</div>)}
                    </div>
                    <div>
                      <div className="text-gray-500 uppercase tracking-wider mb-1">Risk Checks</div>
                      {phase.risk_checks?.map((r, j) => <div key={j} className="text-yellow-500/70 mb-1">{r}</div>)}
                    </div>
                  </div>
                </div>
              ))}
              {(plan as { graduation_strategy?: string }).graduation_strategy && (
                <div className="bg-green-950/20 border border-green-500/10 rounded-lg p-3">
                  <div className="text-[10px] text-green-500 uppercase tracking-wider mb-1">Graduation Strategy</div>
                  <p className="text-sm text-green-300">{(plan as { graduation_strategy: string }).graduation_strategy}</p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">Failed to generate plan.</p>
          )}
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
           MYX V2 hedge: AI evaluates perp signals per phase
             NURTURE: monitor only | DEFEND: short BNB/USDT hedge
             ACCELERATE: scale hedge | GRADUATED: close all

LEARN  ->  Evaluate outcomes after 72h
           Record what worked/failed per narrative
           Improve strategy for next launch via Unibase memory

Stack: DGrid AI (LLM) | BNB Chain (web3) | ERC-8004 (identity) | Four.meme (launch) | MYX V2 (perps)
        `.trim()}</pre>
      </div>
    </div>
  );
}

/* ── MYX V2 Perps Panel ───────────────────────────────── */

interface PerpsPortfolio {
  total_active_positions: number;
  total_closed_positions: number;
  total_signals_generated: number;
  tokens_hedged: number;
  token_summaries: {
    token_address: string;
    active_positions: number;
    total_positions: number;
    total_hedged_wei: number;
    signals_generated: number;
    last_signal: { action: string; confidence: number; reasoning: string; size_pct: number } | null;
  }[];
}

interface PerpsPosition {
  pair_index: number;
  is_long: boolean;
  collateral_wei: number;
  size_amount: number;
  open_tx: string;
  opened_at: number;
  reason: string;
  close_tx: string | null;
  closed_at: number | null;
  status: string;
}

function PerpsPanel({ tokens }: { tokens: Token[] }) {
  const [portfolio, setPortfolio] = useState<PerpsPortfolio | null>(null);
  const [positions, setPositions] = useState<Record<string, PerpsPosition[]>>({});
  const [mxStatus, setMxStatus] = useState<{ enabled: boolean; markets_count?: number; reason?: string } | null>(null);
  const [evaluating, setEvaluating] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [s, p] = await Promise.all([
        fetch(`${API}/api/myx/status`).then((r) => r.json()),
        fetch(`${API}/api/myx/portfolio`).then((r) => r.json()),
      ]);
      setMxStatus(s);
      if (p.token_summaries) setPortfolio(p);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchData();
    const iv = setInterval(fetchData, 15000);
    return () => clearInterval(iv);
  }, [fetchData]);

  const fetchPositions = useCallback(async (addr: string) => {
    try {
      const res = await fetch(`${API}/api/myx/positions/${addr}`);
      const data = await res.json();
      if (data.positions) setPositions((prev) => ({ ...prev, [addr]: data.positions }));
    } catch { /* ignore */ }
  }, []);

  const triggerEvaluate = useCallback(async (addr: string) => {
    setEvaluating(addr);
    try {
      const res = await fetch(`${API}/api/myx/evaluate/${addr}`, { method: "POST" });
      const data = await res.json();
      if (data.result) {
        await fetchData();
        await fetchPositions(addr);
      }
    } catch { /* ignore */ }
    setEvaluating(null);
  }, [fetchData, fetchPositions]);

  return (
    <div className="space-y-6">
      {/* MYX Status */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="MYX Status"
          value={mxStatus?.enabled ? "Connected" : "Demo Mode"}
          sub={mxStatus?.enabled ? `${mxStatus.markets_count || 0} markets` : "AI signals active — on-chain execution ready"}
          accent={mxStatus?.enabled ? "green" : "yellow"}
        />
        <StatCard
          label="Active Hedges"
          value={portfolio?.total_active_positions ?? 0}
          accent="yellow"
        />
        <StatCard
          label="Closed Positions"
          value={portfolio?.total_closed_positions ?? 0}
          accent="blue"
        />
        <StatCard
          label="Signals Generated"
          value={portfolio?.total_signals_generated ?? 0}
          sub={`${portfolio?.tokens_hedged ?? 0} tokens tracked`}
          accent="purple"
        />
      </div>

      {/* How it works */}
      <div className="bg-gray-900/80 border border-gray-800/50 rounded-xl p-5">
        <h3 className="font-bold text-sm mb-3">MYX V2 Hedge Strategy</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
          <div className="bg-green-900/20 border border-green-500/20 rounded-lg p-3">
            <div className="font-bold text-green-400 mb-1">NURTURE</div>
            <div className="text-gray-400">Monitor only. Signal tracking, no positions opened.</div>
          </div>
          <div className="bg-yellow-900/20 border border-yellow-500/20 rounded-lg p-3">
            <div className="font-bold text-yellow-400 mb-1">DEFEND</div>
            <div className="text-gray-400">AI evaluates hedge. Short BNB/USDT if health drops below threshold.</div>
          </div>
          <div className="bg-blue-900/20 border border-blue-500/20 rounded-lg p-3">
            <div className="font-bold text-blue-400 mb-1">ACCELERATE</div>
            <div className="text-gray-400">Scale hedge based on momentum. Long if bullish, close if stable.</div>
          </div>
          <div className="bg-purple-900/20 border border-purple-500/20 rounded-lg p-3">
            <div className="font-bold text-purple-400 mb-1">GRADUATED</div>
            <div className="text-gray-400">Auto-close all hedges. Token moved to PancakeSwap.</div>
          </div>
        </div>
      </div>

      {/* Per-token hedge status */}
      <div className="bg-gray-900/80 border border-gray-800/50 rounded-xl p-5">
        <h3 className="font-bold text-sm mb-3">Token Hedges</h3>
        {tokens.length === 0 ? (
          <p className="text-gray-600 text-xs">No active tokens. Launch a token to see hedge activity.</p>
        ) : (
          <div className="space-y-3">
            {tokens.map((token) => {
              const summary = portfolio?.token_summaries?.find((s) => s.token_address === token.address);
              const tokenPositions = positions[token.address] || [];
              return (
                <div key={token.address} className="bg-black/40 border border-gray-800 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <span className="font-mono font-bold text-sm">{token.symbol}</span>
                      <PhaseTag phase={token.phase} />
                      {summary?.active_positions ? (
                        <span className="px-2 py-0.5 text-[10px] bg-yellow-900/30 border border-yellow-500/20 rounded text-yellow-400">
                          {summary.active_positions} active hedge{summary.active_positions > 1 ? "s" : ""}
                        </span>
                      ) : null}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => fetchPositions(token.address)}
                        className="px-3 py-1 text-[10px] bg-gray-800 hover:bg-gray-700 rounded text-gray-300 transition-colors"
                      >
                        View Positions
                      </button>
                      <button
                        onClick={() => triggerEvaluate(token.address)}
                        disabled={evaluating === token.address}
                        className="px-3 py-1 text-[10px] bg-cyan-900/40 hover:bg-cyan-900/60 border border-cyan-500/20 rounded text-cyan-400 transition-colors disabled:opacity-50"
                      >
                        {evaluating === token.address ? "Evaluating..." : "Evaluate Hedge"}
                      </button>
                    </div>
                  </div>

                  {/* Last signal */}
                  {summary?.last_signal && (
                    <div className="bg-gray-900/60 rounded p-3 mb-3">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] text-gray-500 uppercase">Last Signal</span>
                        <span className={`px-2 py-0.5 text-[10px] rounded font-mono ${
                          summary.last_signal.action === "long" ? "bg-green-900/30 text-green-400" :
                          summary.last_signal.action === "short" ? "bg-red-900/30 text-red-400" :
                          summary.last_signal.action === "close" ? "bg-yellow-900/30 text-yellow-400" :
                          "bg-gray-800 text-gray-400"
                        }`}>
                          {summary.last_signal.action.toUpperCase()}
                        </span>
                        <span className="text-[10px] text-gray-500">
                          {(summary.last_signal.confidence * 100).toFixed(0)}% confidence
                        </span>
                      </div>
                      <p className="text-xs text-gray-400">{summary.last_signal.reasoning}</p>
                    </div>
                  )}

                  {/* Positions table */}
                  {tokenPositions.length > 0 && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-[11px]">
                        <thead>
                          <tr className="text-gray-500 text-left border-b border-gray-800">
                            <th className="pb-1 pr-3">Direction</th>
                            <th className="pb-1 pr-3">Collateral</th>
                            <th className="pb-1 pr-3">Size</th>
                            <th className="pb-1 pr-3">Opened</th>
                            <th className="pb-1 pr-3">Status</th>
                            <th className="pb-1">TX</th>
                          </tr>
                        </thead>
                        <tbody>
                          {tokenPositions.map((p, i) => (
                            <tr key={i} className="border-b border-gray-900">
                              <td className={`py-1.5 pr-3 font-mono ${p.is_long ? "text-green-400" : "text-red-400"}`}>
                                {p.is_long ? "LONG" : "SHORT"}
                              </td>
                              <td className="py-1.5 pr-3 text-gray-300">
                                {(p.collateral_wei / 1e18).toFixed(4)} BNB
                              </td>
                              <td className="py-1.5 pr-3 text-gray-300">
                                {(p.size_amount / 1e18).toFixed(4)}
                              </td>
                              <td className="py-1.5 pr-3 text-gray-500">
                                {new Date(p.opened_at * 1000).toLocaleTimeString()}
                              </td>
                              <td className="py-1.5 pr-3">
                                <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                                  p.status === "active" ? "bg-green-900/30 text-green-400" : "bg-gray-800 text-gray-500"
                                }`}>
                                  {p.status}
                                </span>
                              </td>
                              <td className="py-1.5">
                                <a
                                  href={`https://bscscan.com/tx/${p.open_tx}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-cyan-500 hover:underline font-mono"
                                >
                                  {p.open_tx.slice(0, 10)}...
                                </a>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {!summary && !tokenPositions.length && (
                    <p className="text-gray-600 text-xs">No hedge activity yet. AI signals generate in DEFEND phase — on-chain execution activates when MYX contracts are configured.</p>
                  )}
                </div>
              );
            })}
          </div>
        )}
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
  const [tab, setTab] = useState<"overview" | "generate" | "radar" | "perps" | "memory">("overview");

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
    // Auto-start agent on first load
    fetch(`${API}/api/agent/start`, { method: "POST" }).catch(() => {});
    const interval = setInterval(fetchAll, 10000);
    return () => clearInterval(interval);
  }, []);

  const startAgent = async () => {
    await fetch(`${API}/api/agent/start`, { method: "POST" });
    // Re-fetch status immediately
    try {
      const s = await fetch(`${API}/api/status`).then((r) => r.json());
      setStatus(s);
    } catch { /* ignore */ }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Header */}
      <header className="border-b border-gray-800/50 backdrop-blur-sm bg-black/50 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {status?.running ? <Pulse /> : status && !error ? <div className="w-2.5 h-2.5 rounded-full bg-yellow-500 animate-pulse" /> : <div className="w-2.5 h-2.5 rounded-full bg-red-500" />}
            <h1 className="text-lg font-bold tracking-tight bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              FOUR-LIFE
            </h1>
            <span className="text-[10px] text-gray-600 font-mono">v1.0.0</span>
          </div>

          <div className="flex items-center gap-3">
            {/* Tabs */}
            <nav className="flex gap-1 bg-gray-900/50 rounded-lg p-0.5">
              {(["overview", "generate", "radar", "perps", "memory"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    tab === t ? "bg-gray-800 text-white" : "text-gray-500 hover:text-gray-300"
                  }`}
                >
                  {t === "overview" ? "Dashboard" : t === "generate" ? "Generate" : t === "radar" ? "Radar" : t === "perps" ? "MYX Perps" : "Memory"}
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
                  : error
                    ? "bg-red-900/30 text-red-400 border border-red-500/20"
                    : "bg-yellow-900/30 text-yellow-400 border border-yellow-500/20 hover:bg-yellow-900/50"
              }`}
            >
              {status?.running ? "LIVE" : error ? "OFFLINE" : "READY (click to start)"}
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
                  Paste any Four.meme token address below to get an instant AI health check, graduation prediction,
                  72-hour raise plan, and MYX V2 hedge signal. Or let the autonomous agent do it all — analyzing markets,
                  launching tokens, and managing their entire lifecycle via DGrid AI and ERC-8004 identity.
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

            {/* Token Scanner — public tool */}
            <TokenScanner />

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

        {/* ── Radar Tab ── */}
        {tab === "radar" && <RadarPanel />}

        {/* ── MYX Perps Tab ── */}
        {tab === "perps" && <PerpsPanel tokens={tokens} />}

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
