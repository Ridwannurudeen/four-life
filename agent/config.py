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

    # MYX V2
    myx_router_address: str = Field(default="", alias="MYX_ROUTER_ADDRESS")
    myx_pool_address: str = Field(default="", alias="MYX_POOL_ADDRESS")
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
