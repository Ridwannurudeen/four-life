"""Shared test fixtures."""

import os

import pytest

# Set test env vars before any imports.
os.environ.setdefault("PRIVATE_KEY", "0x" + "ab" * 32)
os.environ.setdefault("WALLET_ADDRESS", "0x" + "00" * 20)
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
os.environ.setdefault("DGRID_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("FOURMEME_API_BASE", "https://four.meme/meme-api/v1")
os.environ.setdefault("BSC_RPC_URL", "https://bsc-dataseed.binance.org")
# Keep the DGrid attestation chain in-memory only during tests so one test run
# doesn't pollute another or write a stray file into the repo.
os.environ["DGRID_ATTEST_PERSIST"] = "false"


@pytest.fixture(autouse=True)
def _reset_dgrid_singletons():
    """Reset LLM + attestation singletons between tests so each test starts
    from a clean state (no carried-over counters, no prior chain tip)."""
    from agent.brain import attestation as _att
    from agent.brain import llm as _llm

    _att.reset_chain_for_tests()
    _llm.reset_llm_for_tests()
    yield
    _att.reset_chain_for_tests()
    _llm.reset_llm_for_tests()
