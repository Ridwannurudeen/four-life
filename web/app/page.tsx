"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8030";

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
      <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${score}%` }} />
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wider">{label}</div>
      <div className="text-2xl font-bold text-white mt-1">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </div>
  );
}

export default function Dashboard() {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [tokens, setTokens] = useState<Token[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [error, setError] = useState("");

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

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-green-500 animate-pulse" />
            <h1 className="text-xl font-bold tracking-tight">FOUR-LIFE</h1>
            <span className="text-xs text-gray-500 font-mono">v1.0.0</span>
          </div>
          <div className="flex items-center gap-4 text-sm">
            {status?.agent_id && (
              <span className="text-gray-400 font-mono">ERC-8004 #{status.agent_id}</span>
            )}
            {status?.wallet && (
              <span className="text-gray-500 font-mono">
                {status.wallet.slice(0, 6)}...{status.wallet.slice(-4)}
              </span>
            )}
            <span className={`px-2 py-1 rounded text-xs font-mono ${
              status?.running ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"
            }`}>
              {status?.running ? "LIVE" : error || "OFFLINE"}
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Stats Grid */}
        {status && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <StatCard label="Launches" value={status.total_launches} />
            <StatCard label="Graduations" value={status.total_graduations} />
            <StatCard label="Grad Rate" value={`${status.graduation_rate}%`} />
            <StatCard label="Avg Peak Holders" value={Math.round(status.avg_peak_holders)} />
            <StatCard label="Active Tokens" value={status.active_tokens} />
          </div>
        )}

        {/* Active Tokens */}
        <section>
          <h2 className="text-lg font-bold mb-4">Active Tokens</h2>
          {tokens.length === 0 ? (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center text-gray-500">
              No active tokens. Agent is analyzing market for opportunities...
            </div>
          ) : (
            <div className="grid gap-4">
              {tokens.map((token) => (
                <div key={token.address} className="bg-gray-900 border border-gray-800 rounded-lg p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <h3 className="font-bold text-lg">{token.name}</h3>
                      <span className="text-gray-400 font-mono">${token.symbol}</span>
                      <PhaseTag phase={token.phase} />
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold">{token.health_score}</div>
                      <div className="text-xs text-gray-500">Health Score</div>
                    </div>
                  </div>

                  <HealthBar score={token.health_score} />

                  <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mt-4 text-sm">
                    <div>
                      <div className="text-gray-500">Holders</div>
                      <div className="font-mono">{token.unique_buyers}</div>
                    </div>
                    <div>
                      <div className="text-gray-500">Velocity</div>
                      <div className="font-mono">{token.holder_velocity}/h</div>
                    </div>
                    <div>
                      <div className="text-gray-500">Buy/Sell</div>
                      <div className="font-mono">{token.buy_sell_ratio}</div>
                    </div>
                    <div>
                      <div className="text-gray-500">Top Holder</div>
                      <div className="font-mono">{token.top_holder_pct}%</div>
                    </div>
                    <div>
                      <div className="text-gray-500">Curve</div>
                      <div className="font-mono">{token.curve_progress}%</div>
                    </div>
                    <div>
                      <div className="text-gray-500">Grad Prob</div>
                      <div className="font-mono">{token.graduation_probability}%</div>
                    </div>
                  </div>

                  <div className="mt-3 text-xs text-gray-600">
                    {token.address} | {token.age_hours}h old | {token.narrative}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Decision Log */}
        <section>
          <h2 className="text-lg font-bold mb-4">Decision Log</h2>
          <div className="bg-gray-900 border border-gray-800 rounded-lg divide-y divide-gray-800">
            {actions.length === 0 ? (
              <div className="p-8 text-center text-gray-500">No actions yet.</div>
            ) : (
              actions.map((action, i) => (
                <div key={i} className="p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`px-1.5 py-0.5 text-xs rounded font-mono ${
                      action.urgency === "high"
                        ? "bg-red-900/50 text-red-400"
                        : action.urgency === "medium"
                        ? "bg-yellow-900/50 text-yellow-400"
                        : "bg-gray-800 text-gray-400"
                    }`}>
                      {action.action_type}
                    </span>
                    <span className="text-xs text-gray-600">
                      {new Date(action.timestamp * 1000).toLocaleTimeString()}
                    </span>
                    {action.tweet_id && (
                      <a
                        href={`https://x.com/i/status/${action.tweet_id}`}
                        target="_blank"
                        rel="noopener"
                        className="text-xs text-blue-500 hover:underline"
                      >
                        view tweet
                      </a>
                    )}
                  </div>
                  <div className="text-sm text-gray-300">{action.content}</div>
                  <div className="text-xs text-gray-600 mt-1">{action.reasoning}</div>
                </div>
              ))
            )}
          </div>
        </section>

        {/* Learnings */}
        {status && status.global_learnings.length > 0 && (
          <section>
            <h2 className="text-lg font-bold mb-4">Agent Memory</h2>
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
              <div className="space-y-2">
                {status.global_learnings.map((learning, i) => (
                  <div key={i} className="text-sm text-gray-400 flex gap-2">
                    <span className="text-gray-600 font-mono shrink-0">#{i + 1}</span>
                    {learning}
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 px-6 py-4 mt-8">
        <div className="max-w-7xl mx-auto flex items-center justify-between text-xs text-gray-600">
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
