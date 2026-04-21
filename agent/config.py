from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Wallet
    private_key: str = Field(default="", alias="PRIVATE_KEY")
    wallet_address: str = Field(default="", alias="WALLET_ADDRESS")

    # Four.meme
    fourmeme_api_base: str = Field(default="https://four.meme/meme-api/v1", alias="FOURMEME_API_BASE")

    # BNB Chain
    bsc_rpc_url: str = Field(default="https://bsc-dataseed.binance.org", alias="BSC_RPC_URL")
    bsc_wss_url: str = Field(default="wss://bsc-rpc.publicnode.com", alias="BSC_WSS_URL")

    # AI
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    dgrid_api_key: str = Field(default="", alias="DGRID_API_KEY")
    dgrid_model: str = Field(default="google/gemini-2.5-flash", alias="DGRID_MODEL")
    # Remap specific tasks to stronger (more expensive) DGrid models when
    # credits allow. Format: "content=anthropic/claude-sonnet-4.5,risk=openai/gpt-4o".
    # Default empty — every task uses dgrid_model (cheap + fast).
    dgrid_task_overrides: str = Field(default="", alias="DGRID_TASK_OVERRIDES")
    # Opt-in: publish the DGrid attestation Merkle root on BNB Chain as a
    # self-transaction. Costs ~0.0001 BNB per publish. Off by default.
    dgrid_attest_onchain: bool = Field(default=False, alias="DGRID_ATTEST_ONCHAIN")
    # Opt-in: let the router auto-rotate TASK_MODEL_MAP based on per-(task,
    # model) performance (success rate, latency, cost). Off by default so the
    # demo routing stays deterministic.
    dgrid_auto_tune: bool = Field(default=False, alias="DGRID_AUTO_TUNE")

    # Twitter
    twitter_bearer_token: str = Field(default="", alias="TWITTER_BEARER_TOKEN")
    twitter_consumer_key: str = Field(default="", alias="TWITTER_CONSUMER_KEY")
    twitter_consumer_secret: str = Field(default="", alias="TWITTER_CONSUMER_SECRET")
    twitter_access_token: str = Field(default="", alias="TWITTER_ACCESS_TOKEN")
    twitter_access_token_secret: str = Field(default="", alias="TWITTER_ACCESS_TOKEN_SECRET")

    # ERC-8004
    identity_registry: str = Field(
        default="0xfA09B3397fAC75424422C4D28b1729E3D4f659D7",
        alias="IDENTITY_REGISTRY",
    )
    reputation_registry: str = Field(
        default="0x17860530385Bdde7992c4Da71B9ec7791E474C08",
        alias="REPUTATION_REGISTRY",
    )

    # Unibase
    membase_account: str = Field(default="", alias="MEMBASE_ACCOUNT")
    membase_id: str = Field(default="four-life-agent", alias="MEMBASE_ID")

    # Bitquery
    bitquery_api_key: str = Field(default="", alias="BITQUERY_API_KEY")

    # BscScan (contract verification + ABI lookup)
    bscscan_api_key: str = Field(default="", alias="BSCSCAN_API_KEY")

    # MYX V2 — BSC mainnet production addresses (reverse-engineered from the
    # myx-trade SDK at src/config/address/BSC_MAINET_NET.ts)
    myx_router_address: str = Field(
        default="0xb0c56a233535971b8903497f98b90Cf53aE77A13",  # TRADING_ROUTER
        alias="MYX_ROUTER_ADDRESS",
    )
    myx_pool_address: str = Field(
        default="0x22cEc08111BBae24D0b80BDA2a6503EaB9BA704b",  # market+pair registry
        alias="MYX_POOL_ADDRESS",
    )
    myx_order_manager: str = Field(
        default="0x8d38a857390E1586481cF8994F4feBc315D0249b",
        alias="MYX_ORDER_MANAGER",
    )
    myx_position_manager: str = Field(
        default="0x04218C23f89cAA2E4395a7Bd94410057705D1184",
        alias="MYX_POSITION_MANAGER",
    )
    myx_base_pool: str = Field(
        default="0x6a775E908629eFC6357b3d89E5528524a6f378Dd",
        alias="MYX_BASE_POOL",
    )
    myx_quote_pool: str = Field(
        default="0x73b2dcfdc7dC78a7A51B778E93c09FC173923BcE",
        alias="MYX_QUOTE_POOL",
    )
    myx_oracle: str = Field(
        default="0xAdD60e47D2C5e7d57B1e5a3F9d24dE43933b8A7A",
        alias="MYX_ORACLE",
    )
    myx_forwarder: str = Field(
        default="0xD0894e09317F455dd698A706bb62D783e95aA7Ad",
        alias="MYX_FORWARDER",
    )
    # MYX V2 is a permissioned broker architecture: orders flow through a
    # BrokerSigner contract issued per-integrator by the MYX team (see SDK
    # guide: "brokerAddress: Get from MYX team"). Without this, our
    # placeOrderWithSalt call has no target. Empty by default; populate
    # once MYX onboards us.
    myx_broker_address: str = Field(default="", alias="MYX_BROKER_ADDRESS")
    # Execution requires real oracle pricing + production-sized collateral. Default OFF so
    # the hackathon demo surface stays in "signal_only" mode until deliberately enabled.
    myx_execution_enabled: bool = Field(default=False, alias="MYX_EXECUTION_ENABLED")

    # Agent config
    agent_name: str = Field(default="FOUR-LIFE", alias="AGENT_NAME")
    agent_description: str = Field(
        default="Autonomous meme token lifecycle agent on Four.meme",
        alias="AGENT_DESCRIPTION",
    )
    min_launch_interval_hours: int = Field(default=24, alias="MIN_LAUNCH_INTERVAL_HOURS")
    max_concurrent_tokens: int = Field(default=3, alias="MAX_CONCURRENT_TOKENS")
    # Autostart the agent lifecycle loop when the API boots. Default True so the
    # deployed service is genuinely autonomous — set AGENT_AUTOSTART=false in
    # tests or for maintenance mode.
    agent_autostart: bool = Field(default=True, alias="AGENT_AUTOSTART")

    # API auth
    api_secret: str = Field(default="", alias="API_SECRET")

    # Notifications (Telegram + Discord alerts on tier/protection transitions)
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    discord_webhook_url: str = Field(default="", alias="DISCORD_WEBHOOK_URL")


settings = Settings()
