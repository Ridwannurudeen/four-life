# FOUR-LIFE

**The AI growth operator for Four.meme launches.**

FOUR-LIFE helps Four.meme tokens survive after launch: it analyzes narratives, predicts graduation probability, creates token lore and content, monitors holder and curve health, posts transparent updates, and learns from every launch. Think of it as the post-launch lifecycle layer that Four.meme is missing.

Built for the [Four.meme AI Sprint Hackathon](https://dorahacks.io/hackathon/fourmemeaisprint) on BNB Chain.

## What Makes FOUR-LIFE Different

Every AI agent on Four.meme today does the same thing: create → dump → repeat. FOUR-LIFE is the agent that **stays with the token after launch** — nurturing community, defending against FUD, accelerating toward graduation, and learning from every cycle.

### The Lifecycle

| Phase | Duration | What FOUR-LIFE Does |
|-------|----------|-------------------|
| **THINK** | Pre-launch | Analyzes narratives, detects trends, picks optimal timing, generates concept |
| **BIRTH** | Launch | Creates token via Agentic Mode, generates artwork + lore, posts launch thread |
| **RAISE** | 0-72h+ | Monitors health, generates content, celebrates milestones, defends against dumps |
| **LEARN** | Post-72h | Evaluates outcomes, records learnings, improves strategy for next launch |

### Key Features

- **Narrative Intelligence** — Scans Four.meme + social trends to find unsaturated narrative gaps
- **Real-Time Health Monitoring** — Tracks holder velocity, whale concentration, buy/sell pressure, bonding curve progress
- **Graduation Probability** — ML-based prediction of whether a token will reach the 18 BNB threshold
- **Adaptive Content** — AI generates memes, updates, and transparency posts that match each token's personality
- **Persistent Memory** — Learns from every launch via Unibase. Each cycle is better than the last.
- **On-Chain Identity** — ERC-8004 registered agent with verifiable track record on BNB Chain
- **MYX V2 Perp Integration** — Creates derivative markets for launched tokens (MYX bounty)
- **DGrid AI Gateway** — All AI inference routed through DGrid's unified API (DGrid bounty)

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  FOUR-LIFE Agent                 │
├──────────┬──────────┬──────────┬────────────────┤
│  Brain   │Lifecycle │ Memory   │   Identity     │
│ Narrative│ Monitor  │ Unibase  │  ERC-8004      │
│ Strategy │ Nurture  │ Local    │  Reputation    │
│ Content  │ Defend   │ Sync     │  Agent Card    │
│          │Accelerate│          │                │
├──────────┴──────────┴──────────┴────────────────┤
│              Four.meme Integration               │
│        API Client  │  TokenManager2 Chain        │
├──────────────────────┬──────────────────────────┤
│    MYX V2 Perps     │    Twitter/X Social       │
├──────────────────────┴──────────────────────────┤
│           DGrid AI Gateway (LLM Calls)           │
├─────────────────────────────────────────────────┤
│              BNB Chain (Chain ID: 56)             │
└─────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Core | Python 3.11+ |
| AI | DGrid AI Gateway (Claude Sonnet, GPT-4) |
| Blockchain | web3.py, BNB Chain RPCs |
| Token Launch | Four.meme Agentic Mode API |
| Derivatives | MYX V2 Permissionless Perps |
| Memory | Unibase/Membase (decentralized) + local JSON |
| Identity | ERC-8004 (BRC8004 on BSC) |
| Social | Tweepy (Twitter/X API v2) |
| Image Gen | DALL-E 3 |
| Dashboard | Next.js 14 + Tailwind + Recharts |
| API | FastAPI |

## Quick Start

```bash
# Clone
git clone https://github.com/Ridwannurudeen/four-life.git
cd four-life

# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your keys

# Run the agent
python main.py

# Or run the API server (for dashboard)
python server.py
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
### Public Integration APIs (no auth required)

| Endpoint | Description |
|----------|-------------|
| `GET /api/health-score/{token}` | Health score, graduation probability, risk factors for any Four.meme token |
| `GET /api/graduation-radar` | Ranks active Four.meme tokens by graduation probability |
| `POST /api/raise-plan/{token}` | AI-generated 72-hour lifecycle plan for a token |
| `GET /.well-known/agent-registration.json` | ERC-8004 agent card |

### Agent Dashboard APIs

| Endpoint | Description |
|----------|-------------|
| `GET /api/status` | Agent status, wallet, track record |
| `GET /api/tokens` | All tracked tokens with health scores |
| `GET /api/tokens/{address}` | Detailed token health + actions |
| `GET /api/memory` | Agent memory, learnings, launch history |
| `GET /api/actions` | Recent lifecycle actions log |
| `POST /api/agent/think` | Run one THINK cycle, generate concept |
| `POST /api/agent/track` | Track an existing token for lifecycle management |
| `POST /api/agent/start` | Start agent loop |
| `POST /api/agent/stop` | Stop agent loop |

## Bounty Integrations

### MYX V2 ($5K Bounty)
After launching a token on Four.meme, FOUR-LIFE creates a corresponding perpetual trading pair on MYX V2, seeds liquidity, and provides AI-powered trading intelligence across spot + derivatives.

### DGrid AI ($5K Bounty)
All LLM calls (narrative analysis, content generation, strategy decisions) are routed through DGrid's unified AI Gateway API.

## License

MIT
