"""Shared test fixtures."""

import os

import pytest

# Set test env vars before any imports.
os.environ.setdefault("PRIVATE_KEY", "0x" + "ab" * 32)
os.environ.setdefault("WALLET_ADDRESS", "0x" + "00" * 20)
# Tests run without API_SECRET set, so require_auth / is_authorized need to
# treat the environment as dev. Otherwise every admin-route test gets 503 and
# is_authorized returns False for dashboard fields, breaking assertions.
os.environ.setdefault("AGENT_ENV", "dev")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
os.environ.setdefault("DGRID_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("FOURMEME_API_BASE", "https://four.meme/meme-api/v1")
os.environ.setdefault("BSC_RPC_URL", "https://bsc-dataseed.binance.org")
# Keep the DGrid attestation chain in-memory only during tests so one test run
# doesn't pollute another or write a stray file into the repo.
os.environ["DGRID_ATTEST_PERSIST"] = "false"
os.environ["MYX_PERSIST"] = "false"


@pytest.fixture(autouse=True)
def _reset_dgrid_singletons():
    """Reset LLM + attestation + MYX singletons between tests so each starts
    from a clean state (no carried-over counters, no prior chain tip)."""
    from agent.brain import attestation as _att
    from agent.brain import llm as _llm
    from agent.myx import store as _myx

    _att.reset_chain_for_tests()
    _llm.reset_llm_for_tests()
    _myx.reset_myx_for_tests()
    yield
    _att.reset_chain_for_tests()
    _llm.reset_llm_for_tests()
    _myx.reset_myx_for_tests()
