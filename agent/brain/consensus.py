"""Multi-model consensus via DGrid.

For high-stakes agent decisions (DEFEND hedge, ACCELERATE spend, GRADUATION
call), we fan out to several DGrid models in parallel and vote on the result.
A single-provider integration cannot do this cleanly — DGrid's unified auth
and OpenAI-compatible surface is what makes it one function call.

Vote semantics:
- Each model returns a JSON object.
- We extract ``vote_key`` from each response.
- If every extracted value is numeric, the final verdict is the **median**.
- Otherwise we take the **majority** (with ties broken by first-model order).
- ``confidence`` is the share of participating models that agreed with the
  final verdict (1.0 for median since numeric results always aggregate).

Every per-model call is recorded in the LLM client's trace ring buffer under
task='consensus' so the transparency story stays intact.
"""

import asyncio
import time
from collections import Counter

from loguru import logger

from agent.brain.llm import get_llm


DEFAULT_CONSENSUS_MODELS = [
    "google/gemini-2.5-flash",
    "anthropic/claude-haiku-4.5",
    "openai/gpt-4o-mini",
]


async def consensus_vote(
    messages: list[dict],
    *,
    models: list[str] | None = None,
    vote_key: str = "action",
    max_tokens: int = 400,
    temperature: float = 0.4,
    json_mode: bool = True,
) -> dict:
    """Run ``messages`` against each model in parallel via DGrid, vote on
    ``vote_key``. Returns a structured result with per-model verdicts.

    Fails soft: if every model errors, ``final_verdict`` is None and
    ``models_succeeded`` is 0. Callers should treat that as "no consensus —
    fall back to your deterministic rule."
    """
    llm = get_llm()
    if not llm.dgrid_configured:
        return {
            "error": "DGrid not configured",
            "models_queried": [], "models_succeeded": 0,
            "final_verdict": None, "confidence": 0.0,
            "tally": {}, "results": [],
        }

    chosen = models or DEFAULT_CONSENSUS_MODELS
    t0 = time.perf_counter()
    prompt_h = llm._prompt_hash(messages)

    async def one(model: str) -> dict:
        call_t0 = time.perf_counter()
        try:
            text, usage = await llm._dgrid_chat_raw(
                messages, max_tokens, temperature, json_mode=json_mode, model=model,
            )
            latency_ms = int((time.perf_counter() - call_t0) * 1000)
            if json_mode:
                try:
                    parsed = llm._parse_json(text)
                except Exception as parse_err:
                    llm._record_trace(
                        provider="dgrid", model=model, task="consensus",
                        latency_ms=latency_ms, fallback_depth=0, success=False,
                        error=f"parse: {llm._redact(str(parse_err))[:150]}",
                        prompt_hash=prompt_h,
                    )
                    return {
                        "model": model, "ok": False, "latency_ms": latency_ms,
                        "error": f"invalid JSON: {str(parse_err)[:120]}",
                    }
            else:
                parsed = {"raw": text}
            verdict = parsed.get(vote_key) if isinstance(parsed, dict) else None
            llm._record_usage("dgrid", model, "consensus")
            llm._record_trace(
                provider="dgrid", model=model, task="consensus",
                latency_ms=latency_ms, fallback_depth=0, success=True, usage=usage,
                prompt_hash=prompt_h, response_hash=llm._response_hash(text),
            )
            return {
                "model": model, "ok": True, "latency_ms": latency_ms,
                "verdict": verdict, "full_response": parsed, "usage": usage,
            }
        except Exception as e:
            latency_ms = int((time.perf_counter() - call_t0) * 1000)
            redacted = llm._redact(str(e))[:200]
            llm._record_trace(
                provider="dgrid", model=model, task="consensus",
                latency_ms=latency_ms, fallback_depth=0, success=False, error=redacted,
            )
            return {"model": model, "ok": False, "latency_ms": latency_ms, "error": redacted}

    results = await asyncio.gather(*[one(m) for m in chosen])
    total_ms = int((time.perf_counter() - t0) * 1000)

    # Tally
    ok_results = [r for r in results if r.get("ok")]
    votes = [r["verdict"] for r in ok_results if r.get("verdict") is not None]
    final_verdict = None
    confidence = 0.0
    tally: dict[str, int] = {}
    method = "none"

    if votes:
        # Numeric path: if every vote is a number, take the median.
        numeric = []
        all_numeric = True
        for v in votes:
            try:
                numeric.append(float(v))
            except (TypeError, ValueError):
                all_numeric = False
                break
        if all_numeric and numeric:
            numeric.sort()
            mid = len(numeric) // 2
            if len(numeric) % 2 == 0:
                final_verdict = (numeric[mid - 1] + numeric[mid]) / 2
            else:
                final_verdict = numeric[mid]
            confidence = 1.0
            tally = {str(round(v, 6)): 1 for v in numeric}
            method = "median"
        else:
            counter = Counter(str(v) for v in votes)
            verdict_str, top_count = counter.most_common(1)[0]
            # Preserve original type for string verdicts.
            for v in votes:
                if str(v) == verdict_str:
                    final_verdict = v
                    break
            confidence = round(top_count / len(votes), 4)
            tally = dict(counter)
            method = "majority"

    logger.info(
        "Consensus: {} → {} (conf={}, {}/{} models ok)",
        vote_key, final_verdict, confidence,
        len(ok_results), len(chosen),
    )
    return {
        "models_queried": chosen,
        "models_succeeded": len(ok_results),
        "vote_key": vote_key,
        "method": method,
        "final_verdict": final_verdict,
        "confidence": confidence,
        "tally": tally,
        "results": results,
        "total_latency_ms": total_ms,
    }
