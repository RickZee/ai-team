"""Trace → OTLP export: mapping, merges, parents, content gating, ids (otel-observability R1, R2)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from evals.trace.otel_export import (
    CONTENT_LIMIT,
    SCHEMA_URL,
    SENSITIVE_SUBSTR,
    SPAN_SPECS,
    ExportOptions,
    export_requests,
    export_spans,
    to_jsonl,
)
from tests.unit.evals.otel_helpers import attrs, make_trace, span, tool_pair

pytestmark = pytest.mark.eval_unit

REPO = Path(__file__).resolve().parents[3]


def _by_type(spans: list[dict]) -> dict[str, dict]:
    return {attrs(s)["ai_team.span.type"]: s for s in spans}


@pytest.mark.parametrize(
    "kind", sorted(set(SPAN_SPECS) - {"tool_result", "subagent_stop", "session_end"})
)
def test_each_mapping_row_writes_both_naming_schemes(kind: str) -> None:
    op, oi_kind = SPAN_SPECS[kind]
    out = _by_type(export_spans(make_trace([span(kind, 1, role="qa")])))[kind]
    a = attrs(out)
    assert a["openinference.span.kind"] == oi_kind
    assert a.get("gen_ai.operation.name") == op


def test_unknown_types_are_chain_spans() -> None:
    a = attrs(_by_type(export_spans(make_trace([span("smoke_probe", 1)])))["smoke_probe"])
    assert a["openinference.span.kind"] == "CHAIN"
    assert "gen_ai.operation.name" not in a


def test_llm_call_carries_model_and_tokens_in_both_schemes() -> None:
    s = span("llm_call", 1, model="claude-x", usage={"input_tokens": 1000, "output_tokens": 500})
    a = attrs(_by_type(export_spans(make_trace([s])))["llm_call"])
    assert a["llm.model_name"] == a["gen_ai.request.model"] == "claude-x"
    assert a["llm.token_count.prompt"] == a["gen_ai.usage.input_tokens"] == 1000
    assert a["llm.token_count.completion"] == a["gen_ai.usage.output_tokens"] == 500
    assert "ai_team.tokens_missing" not in a


def test_llm_call_without_usage_is_flagged_and_model_comes_from_session() -> None:
    trace = make_trace([span("llm_call", 1)], model_ids={"manager": "m-1"})
    a = attrs(_by_type(export_spans(trace))["llm_call"])
    assert a["ai_team.tokens_missing"] is True
    assert a["llm.model_name"] == "m-1"


def test_tool_pair_becomes_one_span_with_a_duration() -> None:
    out = export_spans(make_trace(tool_pair(10, "write_file")))
    assert len(out) == 2  # root + one merged span
    merged = out[1]
    a = attrs(merged)
    assert a["ai_team.span.merged"] == ["tool_use", "tool_result"]
    assert a["tool.name"] == a["gen_ai.tool.name"] == "write_file"
    assert int(merged["endTimeUnixNano"]) - int(merged["startTimeUnixNano"]) == 1_000_000_000


def test_tool_pairs_match_on_tool_role_and_phase_not_order() -> None:
    spans = [
        *tool_pair(10, "read_file", role="architect")[:1],
        *tool_pair(11, "write_file", role="dev"),
        *tool_pair(10, "read_file", role="architect")[1:],
    ]
    out = export_spans(make_trace(spans))
    names = sorted(s["name"] for s in out[1:])
    assert names == ["execute_tool read_file", "execute_tool write_file"]


def test_unpaired_spans_are_kept_and_flagged() -> None:
    out = export_spans(make_trace([span("tool_use", 1, tool="x", run_id="r1")]))
    a = attrs(out[1])
    assert a["ai_team.unpaired"] is True
    assert "ai_team.span.merged" not in a


def test_failed_tool_result_sets_error_status() -> None:
    out = export_spans(make_trace(tool_pair(1, "run_tests", ok=False)))
    assert out[1]["status"]["code"] == 2


def test_parents_phase_under_run_tool_under_phase_and_agent() -> None:
    spans = [
        span("phase_start", 0, phase="development", sid="p0"),
        span("subagent_start", 1, role="dev", phase="development", sid="a0"),
        *tool_pair(2, "write_file", role="dev"),
        span("subagent_stop", 5, role="dev", phase="development", sid="a1"),
        span("phase_end", 9, phase="development", sid="p1"),
    ]
    out = export_spans(make_trace(spans))
    root = out[0]
    by = _by_type(out[1:])
    assert by["phase_start"]["parentSpanId"] == root["spanId"]
    assert by["subagent_start"]["parentSpanId"] == by["phase_start"]["spanId"]
    assert by["tool_use"]["parentSpanId"] == by["subagent_start"]["spanId"]


def test_content_off_keeps_size_and_hash_only() -> None:
    out = export_spans(make_trace(tool_pair(1, "run_tests", summary="12 passed")))
    a = attrs(out[1])
    assert "ai_team.summary" not in a and "output.value" not in a
    assert a["ai_team.summary.bytes"] == len("12 passed")
    assert len(a["ai_team.summary.sha256"]) == 64


def test_content_on_is_cut_to_the_limit() -> None:
    long_text = "x" * (CONTENT_LIMIT + 100)
    out = export_spans(
        make_trace(tool_pair(1, "run_tests", summary=long_text)), ExportOptions(with_content=True)
    )
    a = attrs(out[1])
    assert len(a["ai_team.summary"]) == CONTENT_LIMIT
    assert a["ai_team.truncated"] is True
    assert a["output.value"] == long_text[:CONTENT_LIMIT]


@pytest.mark.parametrize("with_content", [False, True])
def test_sensitive_values_are_never_exported(with_content: bool) -> None:
    pair = tool_pair(1, "read_file", summary="contents of .env: KEY=abc", path="config/credentials")
    out = export_spans(make_trace(pair), ExportOptions(with_content=with_content))
    body = json.dumps(out)
    assert "KEY=abc" not in body
    assert "config/credentials" not in body
    assert attrs(out[1])["ai_team.summary"] == "[redacted]"


def test_sensitive_list_matches_the_ui_guard() -> None:
    src = (REPO / "src/ai_team/ui/artifacts/service.py").read_text(encoding="utf-8")
    match = re.search(r"_SENSITIVE_SUBSTR = (\(.*?\))", src)
    assert match, "ui sensitive list moved; update evals/trace/otel_export.py too"
    assert tuple(eval(match.group(1), {})) == SENSITIVE_SUBSTR  # noqa: S307 - literal tuple


def test_ids_do_not_shift_when_an_earlier_span_is_added() -> None:
    base = tool_pair(10, "write_file") + [span("qa_verdict", 20, role="qa")]
    before = {
        attrs(s)["ai_team.span.type"]: s["spanId"] for s in export_spans(make_trace(base))[1:]
    }
    after_spans = export_spans(make_trace([span("smoke_probe", 1)] + base))
    after = {attrs(s)["ai_team.span.type"]: s["spanId"] for s in after_spans[1:]}
    assert before["tool_use"] == after["tool_use"]
    assert before["qa_verdict"] == after["qa_verdict"]


def test_repeats_get_distinct_ids() -> None:
    out = export_spans(make_trace([span("qa_verdict", 1, sid="a"), span("qa_verdict", 1, sid="b")]))
    assert len({s["spanId"] for s in out}) == 3


def test_same_run_gives_identical_bytes_even_with_a_new_trace_id() -> None:
    spans = tool_pair(1, "write_file") + [span("llm_call", 3, usage={"input_tokens": 5})]
    opts = ExportOptions(run_id="run-1")
    one = to_jsonl(export_requests(make_trace(spans, trace_id="a__b__c__1111"), opts))
    two = to_jsonl(export_requests(make_trace(spans, trace_id="a__b__c__2222"), opts))
    assert one == two


def test_resource_and_schema_url() -> None:
    req = export_requests(
        make_trace([span("llm_call", 1)]), ExportOptions(run_id="run-1", model_tier="local")
    )[0]
    rs = req["resourceSpans"][0]
    res = attrs(rs["resource"])
    assert res == {
        "service.name": "ai-team.langgraph",
        "openinference.project.name": "ai-team",
        "ai_team.backend": "langgraph",
        "ai_team.run_id": "run-1",
        "ai_team.source": "harness",
        "ai_team.model_tier": "local",
    }
    assert rs["schemaUrl"] == SCHEMA_URL
    assert rs["scopeSpans"][0]["schemaUrl"] == SCHEMA_URL


def test_large_traces_are_sent_in_batches() -> None:
    spans = [span("qa_verdict", i, sid=f"q{i}") for i in range(1100)]
    reqs = export_requests(make_trace(spans))
    sizes = [len(r["resourceSpans"][0]["scopeSpans"][0]["spans"]) for r in reqs]
    assert sizes == [512, 512, 77]  # 1,100 spans + the root


def test_root_span_reflects_failed_runs() -> None:
    out = export_spans(make_trace([span("error", 1)], status="failed"))
    assert out[0]["status"]["code"] == 2
    assert attrs(out[0])["ai_team.span.type"] == "run"
