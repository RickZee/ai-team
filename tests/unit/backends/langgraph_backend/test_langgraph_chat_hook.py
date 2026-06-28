"""Tests for the httpx response hook in langgraph_chat (G5).

This hook does two safety-relevant jobs on every OpenRouter chat completion:
1. Meters cost/tokens into the per-run spend guard (so a runaway crash/retry
   loop is aborted before it burns money).
2. Normalises tool_call ``function.arguments`` from dict → JSON string (deepseek
   quirk that otherwise breaks the OpenAI SDK).

The spend *tracker* is covered by test_spend_guard.py. These tests cover the
*hook that feeds it* against the real OpenRouter wire shapes — the gap that, if
the response schema drifts, would silently record $0 and never fire the guard.
"""

from __future__ import annotations

import json

import httpx
import pytest
from ai_team.backends.langgraph_backend.graphs.langgraph_chat import (
    _fix_chat_completion_response,
    _record_spend_from_body,
)
from ai_team.backends.langgraph_backend.graphs.spend_guard import (
    BudgetExceededError,
    current_spend,
    reset_spend_guard,
)


@pytest.fixture(autouse=True)
def _budget() -> None:
    reset_spend_guard(1.0)


# A faithful slice of a real OpenRouter chat-completion body (from a live run).
def _completion_body(
    *,
    cost: float | None = 0.00094375,
    total_tokens: int = 1546,
    nested_cost: float | None = None,
    tool_call_args: object | None = None,
) -> dict:
    usage: dict = {"total_tokens": total_tokens}
    if cost is not None:
        usage["cost"] = cost
    if nested_cost is not None:
        usage["cost_details"] = {"upstream_inference_cost": nested_cost}
    message: dict = {"role": "assistant", "content": "ok"}
    if tool_call_args is not None:
        message["tool_calls"] = [
            {"id": "c1", "type": "function", "function": {"name": "file_writer", "arguments": tool_call_args}}
        ]
    return {
        "id": "gen-1",
        "model": "deepseek/deepseek-chat-v3-0324",
        "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
        "usage": usage,
    }


def _make_response(body: dict, url: str = "https://openrouter.ai/api/v1/chat/completions") -> httpx.Response:
    req = httpx.Request("POST", url)
    return httpx.Response(200, json=body, request=req)


class TestRecordSpendShapes:
    def test_top_level_cost_recorded(self) -> None:
        _record_spend_from_body(_completion_body(cost=0.25, total_tokens=1000))
        snap = current_spend()
        assert snap["spent_usd"] == pytest.approx(0.25)
        assert snap["total_tokens"] == 1000

    def test_nested_cost_details_fallback(self) -> None:
        _record_spend_from_body(_completion_body(cost=None, nested_cost=0.30))
        assert current_spend()["spent_usd"] == pytest.approx(0.30)

    def test_missing_cost_records_zero_but_tracks_tokens(self) -> None:
        _record_spend_from_body(_completion_body(cost=None, total_tokens=500))
        snap = current_spend()
        assert snap["spent_usd"] == 0.0
        assert snap["total_tokens"] == 500
        assert snap["calls"] == 1

    def test_malformed_cost_does_not_crash(self) -> None:
        _record_spend_from_body(_completion_body(cost="not-a-number"))  # type: ignore[arg-type]
        assert current_spend()["spent_usd"] == 0.0

    def test_no_usage_block(self) -> None:
        _record_spend_from_body({"choices": []})
        assert current_spend()["calls"] == 1
        assert current_spend()["spent_usd"] == 0.0


class TestHookEndToEnd:
    def test_hook_meters_spend(self) -> None:
        resp = _make_response(_completion_body(cost=0.10, total_tokens=200))
        _fix_chat_completion_response(resp)
        assert current_spend()["spent_usd"] == pytest.approx(0.10)

    def test_hook_aborts_when_budget_exceeded(self) -> None:
        reset_spend_guard(0.05)
        resp = _make_response(_completion_body(cost=0.10))
        with pytest.raises(BudgetExceededError):
            _fix_chat_completion_response(resp)

    def test_hook_ignores_non_completion_urls(self) -> None:
        resp = _make_response(_completion_body(cost=0.10), url="https://openrouter.ai/api/v1/models")
        _fix_chat_completion_response(resp)
        assert current_spend()["calls"] == 0

    def test_hook_survives_malformed_json_body(self) -> None:
        req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        resp = httpx.Response(200, content=b"not json", request=req)
        _fix_chat_completion_response(resp)  # must not raise
        assert current_spend()["calls"] == 0

    def test_hook_normalises_dict_tool_call_args(self) -> None:
        # deepseek quirk: function.arguments arrives as a dict, not a JSON string.
        resp = _make_response(_completion_body(tool_call_args={"path": "a.py", "content": "x"}))
        _fix_chat_completion_response(resp)
        body = json.loads(resp.content)
        args = body["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
        assert isinstance(args, str)
        assert json.loads(args) == {"path": "a.py", "content": "x"}

    def test_hook_leaves_string_tool_call_args_untouched(self) -> None:
        original = json.dumps({"path": "a.py"})
        resp = _make_response(_completion_body(tool_call_args=original))
        _fix_chat_completion_response(resp)
        body = json.loads(resp.content)
        args = body["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
        assert args == original

    def test_hook_meters_before_aborting_on_tool_call_body(self) -> None:
        # Even a response that also needs arg-fixing must meter spend first.
        reset_spend_guard(0.05)
        resp = _make_response(_completion_body(cost=0.10, tool_call_args={"path": "a.py"}))
        with pytest.raises(BudgetExceededError):
            _fix_chat_completion_response(resp)
        assert current_spend()["spent_usd"] == pytest.approx(0.10)
