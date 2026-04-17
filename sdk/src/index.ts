/**
 * @gudman/four-life-sdk — TypeScript client for the FOUR-LIFE Certified trust layer.
 *
 * Zero runtime dependencies. Works in browsers, Node 18+, Deno, Bun, edge runtimes.
 *
 * @example
 * ```ts
 * import { FourLife } from "@gudman/four-life-sdk";
 *
 * const fl = new FourLife();
 * const badge = await fl.getBadge("0xabc...");
 * console.log(badge.tier);                // "graduation_watch"
 * console.log(badge.why[0].passed);       // true
 *
 * // Watch a token every 60 seconds
 * const unwatch = fl.watchToken("0xabc...", (b) => {
 *   if (b.tier === "graduated") notifyDiscord(b);
 * });
 * ```
 */

export const DEFAULT_API_BASE = "https://four-life.gudman.xyz";
export const SDK_VERSION = "0.1.0";

// ── Types ────────────────────────────────────────────────────────────

export type Tier = "graduated" | "graduation_watch" | "healthy" | "at_risk" | "observed";

export type Confidence = "high" | "medium" | "low";

export type QuoteAsset = "BNB" | "USD1" | "USDT" | "USDC" | "CAKE" | string;

export interface BadgeRule {
  rule: string;
  metric: string;
  value: string | number | boolean;
  threshold: string | number | boolean;
  operator: string;
  passed: boolean;
}

export interface Badge {
  tier: Tier;
  label: string;
  description: string;
  why: BadgeRule[];
  metrics_snapshot: Record<string, unknown>;
  version: string;
}

export interface BadgeResponse {
  token_address: string;
  badge: Badge;
  data_source: "live_monitor" | "ranking_snapshot" | string;
  model_version: string;
  last_updated_at: number;
  powered_by: string;
}

export interface RiskFlag {
  id: string;
  severity: "critical" | "high" | "medium" | "info" | "low";
  metric: string;
  value: number | string;
  threshold: number | string;
  message: string;
}

export interface RiskSnapshot {
  token_address: string;
  name: string;
  symbol: string;
  quote_asset: QuoteAsset;
  risk_level: string;
  metrics: {
    whale_concentration: number;
    whale_count: number;
    buy_sell_ratio: number;
    holder_velocity: number;
    holder_count: number;
    age_hours: number;
    curve_progress: number;
    phase: string;
  };
  evidence: RiskFlag[];
  confidence_score: Confidence;
  fallback_used: boolean;
  data_sources: string[];
  model_version: string;
  last_updated_at: number;
}

export interface ChecklistItem {
  phase: string;
  priority: "critical" | "high" | "medium" | "low";
  title: string;
  rationale: string;
  metric: string;
  value: unknown;
}

export interface OperatorChecklist {
  token_address: string;
  name: string;
  symbol: string;
  phase: string;
  age_hours: number;
  checklist: ChecklistItem[];
  item_count: number;
  model_version: string;
  last_updated_at: number;
}

export interface RadarEntry {
  token_address: string;
  name: string;
  symbol: string;
  quote_asset: QuoteAsset;
  graduation_target: number;
  graduation_target_unit: string;
  graduation_progress_value: number;
  holders: number;
  curve_progress: number;
  volume_quote: number;
  volume_bnb: number;
  increase_pct: number;
  health_score: number;
  graduation_probability: number;
  holder_velocity: number;
  confidence_score: Confidence;
  status: string;
  fourmeme_url: string;
}

export interface RadarResponse {
  radar: RadarEntry[];
  total_scanned: number;
  filters: { quote_asset: string; min_confidence: string; sort_by: string };
  known_quote_assets: string[];
  model_version: string;
  last_updated_at: number;
  timestamp: number;
  powered_by: string;
}

export interface CreatorEvidence {
  token_address: string;
  symbol: string;
  narrative: string;
  quote_asset: QuoteAsset;
  launched_at: number;
  graduated: boolean;
  peak_curve_progress: number;
  peak_holders: number;
  peak_health_score: number;
}

export interface CreatorSurvival {
  wallet: string;
  tracked: boolean;
  launches_tracked: number;
  graduations: number;
  graduation_rate: number;
  median_peak_curve_progress: number;
  median_peak_holders: number;
  trust_tier: "proven" | "emerging" | "new_creator" | "unproven" | "unknown";
  evidence: CreatorEvidence[];
  note?: string;
  model_version: string;
  last_updated_at: number;
}

export interface ContractRisk {
  token_address: string;
  analyzed_at: number;
  has_mint_function: boolean;
  has_blacklist: boolean;
  is_proxy: boolean;
  has_pause: boolean;
  has_ownership: boolean;
  owner_address: string | null;
  owner_is_renounced: boolean;
  is_verified_on_bscscan: boolean;
  risk_score: number;
  flags: { id: string; severity: string; evidence: string; message: string }[];
  raw_bytecode_hash: string;
  confidence: Confidence;
}

export interface IdentityFeed {
  agent_card: Record<string, unknown>;
  registration: {
    agent_id: number | null;
    wallet: string;
    registry_contract: string;
    tx_hash: string;
    block: number;
    agent_card_uri: string;
  };
  reputation_attestations: {
    token_address: string;
    token_symbol: string;
    token_name: string;
    quote_asset: string;
    graduation_time: number;
    tx_hash: string;
    block: number;
    submitted_at: number;
  }[];
  reputation_summary: {
    attestations_count: number;
    graduations_attested: number;
    last_attestation_tx: string;
  };
  last_updated_at: number;
}

export interface DGridStats {
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
  usage_by_provider: Record<string, number>;
  usage_by_task: Record<string, number>;
  usage_by_model: Record<string, number>;
  last_seen: Record<string, number>;
}

export interface PlatformCohorts {
  launches_tracked: number;
  graduations: number;
  cohorts_by_age: Record<string, number>;
  by_narrative: { narrative: string; launches: number; graduations: number; graduation_rate: number; avg_peak_holders: number }[];
  by_quote_asset: Record<string, number>;
  whale_risk_distribution: Record<string, number>;
  avg_time_to_graduation_hours: number | null;
  model_version: string;
  last_updated_at: number;
  note?: string;
}

// ── Errors ───────────────────────────────────────────────────────────

export class FourLifeError extends Error {
  public readonly status: number | null;
  public readonly body: unknown;
  constructor(message: string, status: number | null = null, body: unknown = null) {
    super(message);
    this.name = "FourLifeError";
    this.status = status;
    this.body = body;
  }
}

// ── Options ──────────────────────────────────────────────────────────

export interface FourLifeOptions {
  /** Base URL for the FOUR-LIFE API. Defaults to https://four-life.gudman.xyz. */
  baseUrl?: string;
  /** Optional bearer token — only needed for write endpoints (trackToken). */
  apiSecret?: string;
  /** Fetch implementation override (for Node < 18 or custom runtimes). */
  fetch?: typeof fetch;
  /** Default per-request timeout in ms. Defaults to 20000. */
  timeoutMs?: number;
}

export interface RadarFilter {
  limit?: number;
  quoteAsset?: QuoteAsset | "all";
  minConfidence?: Confidence;
  sortBy?: "graduation_probability" | "health_score" | "curve_progress" | "holder_velocity";
}

export interface WatchOptions {
  /** Poll interval in ms. Defaults to 60000 (1 min). */
  intervalMs?: number;
  /** Called when the fetch fails. Returning true continues polling; false stops. */
  onError?: (err: unknown) => boolean | void;
}

// ── Client ───────────────────────────────────────────────────────────

/** The main client for the FOUR-LIFE Certified API. */
export class FourLife {
  public readonly baseUrl: string;
  public readonly apiSecret?: string;
  private readonly _fetch: typeof fetch;
  private readonly _timeoutMs: number;

  constructor(opts: FourLifeOptions = {}) {
    this.baseUrl = (opts.baseUrl || DEFAULT_API_BASE).replace(/\/+$/, "");
    this.apiSecret = opts.apiSecret;
    this._fetch = opts.fetch || (typeof fetch !== "undefined" ? fetch : undefined)!;
    if (!this._fetch) {
      throw new FourLifeError("No fetch implementation available — pass opts.fetch on Node < 18.");
    }
    this._timeoutMs = opts.timeoutMs ?? 20_000;
  }

  // ── Internal ─────────────────────────────────────────────────────

  private async _request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this._timeoutMs);

    try {
      const headers = new Headers(init.headers);
      headers.set("Accept", "application/json");
      headers.set("User-Agent", `@gudman/four-life-sdk v${SDK_VERSION}`);
      if (this.apiSecret && !headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${this.apiSecret}`);
      }

      const res = await this._fetch(url, { ...init, headers, signal: controller.signal });
      const text = await res.text();
      let body: unknown = null;
      try { body = text ? JSON.parse(text) : null; } catch { body = text; }

      if (!res.ok) {
        throw new FourLifeError(
          `FOUR-LIFE API ${res.status} at ${path}`,
          res.status,
          body,
        );
      }
      return body as T;
    } catch (err) {
      if (err instanceof FourLifeError) throw err;
      if ((err as Error).name === "AbortError") {
        throw new FourLifeError(`Request timed out after ${this._timeoutMs}ms at ${path}`);
      }
      throw new FourLifeError(`Request failed at ${path}: ${(err as Error).message}`);
    } finally {
      clearTimeout(timeout);
    }
  }

  private _normalizeAddress(addr: string): string {
    if (!addr) throw new FourLifeError("Token/creator address is required");
    if (!addr.startsWith("0x") || addr.length !== 42) {
      throw new FourLifeError(`Invalid address: ${addr}`);
    }
    return addr.toLowerCase();
  }

  // ── Public: badge + health ───────────────────────────────────────

  /** Fetch the FOUR-LIFE Certified badge for a Four.meme token. */
  async getBadge(tokenAddress: string): Promise<BadgeResponse> {
    const addr = this._normalizeAddress(tokenAddress);
    return this._request<BadgeResponse>(`/api/token/${addr}/badge`);
  }

  /** Fetch the risk snapshot for a tracked token. */
  async getRiskSnapshot(tokenAddress: string): Promise<RiskSnapshot> {
    const addr = this._normalizeAddress(tokenAddress);
    return this._request<RiskSnapshot>(`/api/token/${addr}/risk-snapshot`);
  }

  /** Fetch the 72h operator checklist for a tracked token. */
  async getOperatorChecklist(tokenAddress: string): Promise<OperatorChecklist> {
    const addr = this._normalizeAddress(tokenAddress);
    return this._request<OperatorChecklist>(`/api/token/${addr}/operator-checklist`);
  }

  /** Fetch the contract-level rug-risk analysis for a token. */
  async getContractRisk(tokenAddress: string): Promise<ContractRisk> {
    const addr = this._normalizeAddress(tokenAddress);
    return this._request<ContractRisk>(`/api/token/${addr}/contract-risk`);
  }

  /** Fetch the combined health score (same data as badge, with raw metrics). */
  async getHealthScore(tokenAddress: string): Promise<Record<string, unknown>> {
    const addr = this._normalizeAddress(tokenAddress);
    return this._request(`/api/health-score/${addr}`);
  }

  // ── Public: radar + platform ─────────────────────────────────────

  /** Fetch the live Graduation Radar. Returns up to `limit` tokens, filtered/sorted. */
  async getGraduationRadar(filter: RadarFilter = {}): Promise<RadarResponse> {
    const params = new URLSearchParams();
    if (filter.limit !== undefined) params.set("limit", String(filter.limit));
    if (filter.quoteAsset) params.set("quote_asset", filter.quoteAsset);
    if (filter.minConfidence) params.set("min_confidence", filter.minConfidence);
    if (filter.sortBy) params.set("sort_by", filter.sortBy);
    const qs = params.toString();
    return this._request<RadarResponse>(`/api/graduation-radar${qs ? `?${qs}` : ""}`);
  }

  /** Fetch cohort-level platform analytics. */
  async getPlatformCohorts(): Promise<PlatformCohorts> {
    return this._request<PlatformCohorts>("/api/platform/cohorts");
  }

  /** Fetch a creator's survival score. Safe for unknown creators — returns `tracked: false`. */
  async getCreatorScore(wallet: string): Promise<CreatorSurvival> {
    const addr = this._normalizeAddress(wallet);
    return this._request<CreatorSurvival>(`/api/creator/${addr}/survival-score`);
  }

  /** Fetch the ERC-8004 / BRC-8004 identity feed — agent card + attestations. */
  async getIdentity(): Promise<IdentityFeed> {
    return this._request<IdentityFeed>("/api/identity");
  }

  /** Fetch DGrid bounty stats — provider config, usage by task/model, fallback events. */
  async getDGridStats(): Promise<DGridStats> {
    return this._request<DGridStats>("/api/dgrid/stats");
  }

  // ── Public: generated raise plan (LLM-backed) ────────────────────

  /** Generate a 72h raise plan for a token. Uses pair-aware graduation targets. */
  async generateRaisePlan(tokenAddress: string): Promise<Record<string, unknown>> {
    const addr = this._normalizeAddress(tokenAddress);
    return this._request(`/api/raise-plan/${addr}`, { method: "POST" });
  }

  // ── Write endpoints (require apiSecret when deployed) ────────────

  /**
   * Begin lifecycle tracking of a token. Call this after a token is created on Four.meme
   * to have FOUR-LIFE manage its lifecycle (monitoring, content, hedge signals).
   *
   * Requires `apiSecret` on the client if the API is deployed with auth enabled.
   */
  async trackToken(args: {
    tokenAddress: string;
    name?: string;
    symbol?: string;
    quoteAsset?: QuoteAsset;
    creator?: string;
    concept?: Record<string, unknown>;
  }): Promise<{ status: string; token_address: string; name: string; symbol: string; message: string }> {
    const body = {
      token_address: this._normalizeAddress(args.tokenAddress),
      name: args.name ?? "",
      symbol: args.symbol ?? "",
      quote_asset: (args.quoteAsset ?? "BNB").toUpperCase(),
      creator: args.creator ? this._normalizeAddress(args.creator) : undefined,
      concept: args.concept,
    };
    return this._request("/api/agent/track", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  // ── Watchers (long-running polling) ──────────────────────────────

  /**
   * Watch a token's badge, calling `onUpdate` on every successful poll.
   * Returns an `unwatch` function. Polls every 60s by default.
   */
  watchToken(
    tokenAddress: string,
    onUpdate: (badge: BadgeResponse) => void,
    opts: WatchOptions = {},
  ): () => void {
    const interval = opts.intervalMs ?? 60_000;
    let stopped = false;

    const tick = async () => {
      if (stopped) return;
      try {
        const badge = await this.getBadge(tokenAddress);
        if (!stopped) onUpdate(badge);
      } catch (err) {
        const cont = opts.onError ? opts.onError(err) : true;
        if (cont === false) stopped = true;
      }
    };

    void tick();
    const timer = setInterval(() => void tick(), interval);

    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }

  /**
   * Watch the full Graduation Radar. Delivers the entire radar on each tick.
   * Detecting tier changes is the caller's responsibility — compare consecutive snapshots.
   */
  watchRadar(
    filter: RadarFilter,
    onUpdate: (radar: RadarResponse) => void,
    opts: WatchOptions = {},
  ): () => void {
    const interval = opts.intervalMs ?? 60_000;
    let stopped = false;

    const tick = async () => {
      if (stopped) return;
      try {
        const radar = await this.getGraduationRadar(filter);
        if (!stopped) onUpdate(radar);
      } catch (err) {
        const cont = opts.onError ? opts.onError(err) : true;
        if (cont === false) stopped = true;
      }
    };

    void tick();
    const timer = setInterval(() => void tick(), interval);

    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }
}

// Default export for ES module users that prefer it
export default FourLife;
