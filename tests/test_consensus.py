"""Tests for the DGrid multi-model consensus path."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_response(text: str):
    """MagicMock mimicking an OpenAI SDK chat.completions response."""
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = text
    return r


def _make_llm():
    """Build an LLMClient with a mocked DGrid backend."""
    from agent.brain.llm import LLMClient
    with patch("agent.brain.llm.settings") as mock_settings:
        mock_settings.dgrid_api_key = "sk-test-dgrid"
        mock_settings.anthropic_api_key = "sk-ant-test"
        mock_settings.openai_api_key = ""
        mock_settings.dgrid_model = "google/gemini-2.5-flash"
        client = LLMClient()
    client._dgrid = AsyncMock()
    client._dgrid.chat = MagicMock()
    client._dgrid.chat.completions = MagicMock()
    client._dgrid.chat.completions.create = AsyncMock()
    return client


class TestMajorityVote:
    @pytest.mark.asyncio
    async def test_majority_wins(self, monkeypatch):
        from agent.brain import llm as llm_mod
        client = _make_llm()
        monkeypatch.setattr(llm_mod, "_llm", client)

        # 3 models: 2 say "bullish", 1 says "neutral"
        responses = iter([
            _mock_response('{"action": "bullish"}'),
            _mock_response('{"action": "bullish"}'),
            _mock_response('{"action": "neutral"}'),
        ])
        client._dgrid.chat.completions.create.side_effect = lambda **kw: next(responses)

        from agent.brain.consensus import consensus_vote
        result = await consensus_vote(
            [{"role": "user", "content": "q"}],
            models=["m1", "m2", "m3"],
            vote_key="action",
        )
        assert result["final_verdict"] == "bullish"
        assert round(result["confidence"], 2) == round(2 / 3, 2)
        assert result["models_succeeded"] == 3
        assert result["method"] == "majority"
        assert result["tally"] == {"bullish": 2, "neutral": 1}

    @pytest.mark.asyncio
    async def test_all_fail_returns_none(self, monkeypatch):
        from agent.brain import llm as llm_mod
        client = _make_llm()
        monkeypatch.setattr(llm_mod, "_llm", client)

        client._dgrid.chat.completions.create.side_effect = Exception("boom")

        from agent.brain.consensus import consensus_vote
        result = await consensus_vote(
            [{"role": "user", "content": "q"}], models=["m1", "m2"],
        )
        assert result["final_verdict"] is None
        assert result["models_succeeded"] == 0
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_invalid_json_from_one_model_excluded(self, monkeypatch):
        from agent.brain import llm as llm_mod
        client = _make_llm()
        monkeypatch.setattr(llm_mod, "_llm", client)

        responses = iter([
            _mock_response("not json at all"),
            _mock_response('{"action": "hold"}'),
            _mock_response('{"action": "hold"}'),
        ])
        client._dgrid.chat.completions.create.side_effect = lambda **kw: next(responses)

        from agent.brain.consensus import consensus_vote
        result = await consensus_vote(
            [{"role": "user", "content": "q"}],
            models=["m1", "m2", "m3"],
            vote_key="action",
        )
        assert result["final_verdict"] == "hold"
        # m1 parsed failure → 2 of 3 successful
        assert result["models_succeeded"] == 2


class TestMedianVote:
    @pytest.mark.asyncio
    async def test_numeric_votes_take_median(self, monkeypatch):
        from agent.brain import llm as llm_mod
        client = _make_llm()
        monkeypatch.setattr(llm_mod, "_llm", client)

        responses = iter([
            _mock_response('{"score": 10}'),
            _mock_response('{"score": 30}'),
            _mock_response('{"score": 50}'),
        ])
        client._dgrid.chat.completions.create.side_effect = lambda **kw: next(responses)

        from agent.brain.consensus import consensus_vote
        result = await consensus_vote(
            [{"role": "user", "content": "q"}],
            models=["m1", "m2", "m3"],
            vote_key="score",
        )
        assert result["method"] == "median"
        assert result["final_verdict"] == 30
        assert result["models_succeeded"] == 3


class TestTrace:
    @pytest.mark.asyncio
    async def test_per_model_trace_recorded(self, monkeypatch):
        from agent.brain import llm as llm_mod
        client = _make_llm()
        monkeypatch.setattr(llm_mod, "_llm", client)

        responses = iter([
            _mock_response('{"action": "a"}'),
            _mock_response('{"action": "a"}'),
        ])
        client._dgrid.chat.completions.create.side_effect = lambda **kw: next(responses)

        from agent.brain.consensus import consensus_vote
        await consensus_vote(
            [{"role": "user", "content": "q"}],
            models=["m1", "m2"], vote_key="action",
        )

        trace = client.get_trace(limit=10)
        # Each model should have produced one trace entry with task="consensus"
        consensus_entries = [t for t in trace if t["task"] == "consensus"]
        assert len(consensus_entries) == 2
        assert {t["model"] for t in consensus_entries} == {"m1", "m2"}
        assert all(t["provider"] == "dgrid" for t in consensus_entries)
