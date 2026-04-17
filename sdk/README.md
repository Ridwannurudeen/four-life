# @gudman/four-life-sdk

> TypeScript SDK for the [FOUR-LIFE Certified](https://four-life.gudman.xyz) trust layer — Four.meme token grading, risk snapshots, creator scores, operator checklists.

Zero runtime dependencies. Works in browsers, Node 18+, Deno, Bun, and edge runtimes.

## Install

```bash
npm install @gudman/four-life-sdk
```

## Quick start

```ts
import { FourLife } from "@gudman/four-life-sdk";

const fl = new FourLife();

// Grade any Four.meme token — deterministic, auditable.
const { badge } = await fl.getBadge("0x00ea33ab439c3fad06a6a824f3dbfade01334444");
console.log(badge.tier);           // "graduation_watch"
console.log(badge.label);          // "Graduation Watch"
console.log(badge.why[0].rule);    // "curve_advanced"
console.log(badge.why[0].passed);  // true
```

## What you can do

### Grade a token

```ts
const { badge } = await fl.getBadge(tokenAddress);
// badge.tier: "graduated" | "graduation_watch" | "healthy" | "at_risk" | "observed"
// badge.why[] — full rule trace: rule name, metric, value, threshold, operator, pass/fail
```

### Pull the full risk snapshot

```ts
const snap = await fl.getRiskSnapshot(tokenAddress);
// snap.risk_level: "critical" | "high" | "medium" | "info" | "low"
// snap.evidence[] — every flag with severity, metric, and human-readable message
```

### Check a creator's track record

```ts
const creator = await fl.getCreatorScore(walletAddress);
// creator.trust_tier: "proven" | "emerging" | "new_creator" | "unproven" | "unknown"
// creator.graduation_rate, creator.evidence[] — every launch we've observed
```

### Scan the live radar

```ts
const { radar } = await fl.getGraduationRadar({
  limit: 20,
  quoteAsset: "BNB",
  minConfidence: "high",
  sortBy: "graduation_probability",
});

for (const token of radar) {
  console.log(token.symbol, token.graduation_probability, token.confidence_score);
}
```

### Watch a token or the full radar

```ts
const unwatch = fl.watchToken(tokenAddress, (badge) => {
  if (badge.badge.tier === "at_risk") alertDiscord(badge);
  if (badge.badge.tier === "graduated") celebrate(badge);
});

// Stop later
unwatch();
```

### Get the 72h operator checklist

```ts
const { checklist } = await fl.getOperatorChecklist(tokenAddress);
// Deterministic, phase-aware action items (nurture/defend/accelerate/graduated).
```

### Inspect contract-level rug risk

```ts
const risk = await fl.getContractRisk(tokenAddress);
// risk.risk_score (0-100), risk.flags[] — mint, blacklist, pause, proxy, ownership
```

### Trigger an AI-generated raise plan

```ts
const plan = await fl.generateRaisePlan(tokenAddress);
// 72h phased plan using the actual pair-aware graduation target
```

### Verify on-chain identity (ERC-8004 / BRC-8004)

```ts
const identity = await fl.getIdentity();
// identity.registration.agent_id, identity.reputation_attestations[]
```

### Monitor DGrid gateway usage

```ts
const stats = await fl.getDGridStats();
// stats.usage_by_provider, stats.fallback_events, stats.task_model_map
```

## Configuration

```ts
const fl = new FourLife({
  baseUrl: "https://four-life.gudman.xyz",  // default
  apiSecret: "sk_...",                       // only needed for trackToken()
  timeoutMs: 20_000,                         // per-request timeout
  fetch: customFetch,                        // override for Node < 18
});
```

## Error handling

Every call throws `FourLifeError` on failure:

```ts
import { FourLife, FourLifeError } from "@gudman/four-life-sdk";

try {
  await fl.getBadge(addr);
} catch (err) {
  if (err instanceof FourLifeError) {
    console.log(err.status, err.body);  // HTTP status + parsed body
  }
}
```

## Why FOUR-LIFE Certified?

Every badge is computed from raw on-chain metrics — no LLM in the trust path. Each response includes a `why[]` rule trace so you can verify the grade yourself.

- **Pair-aware graduation targets** — sources live from Four.meme's `/public/config` (BNB → 18, USD1 → 12 000, etc.)
- **Deterministic risk flags** — whale concentration, sell pressure, stalled curve, holder stagnation, contract rug overrides
- **ERC-8004 reputation** — every graduated token produces an on-chain attestation
- **Contract-level rug detection** — mint, blacklist, proxy, pause, ownership, honeypot patterns

## License

MIT — see [LICENSE](./LICENSE).

## Links

- Live site: <https://four-life.gudman.xyz>
- Radar: <https://four-life.gudman.xyz/radar>
- Browser extension: <https://github.com/Ridwannurudeen/four-life/tree/master/extension>
- One-line embed widget: <https://four-life.gudman.xyz/embed>
- Main repo: <https://github.com/Ridwannurudeen/four-life>
