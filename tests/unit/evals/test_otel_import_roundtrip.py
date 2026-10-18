"""Our own exports read back without loss; framework spans keep their mapping (R3)."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from evals.trace.models import Span
from evals.trace.otel_export import ExportOptions, export_requests, to_jsonl
from evals.trace.otel_import import import_otlp, kind_counts
from tests.unit.evals.otel_helpers import make_trace, span, tool_pair

pytestmark = pytest.mark.eval_unit

_KINDS = ["llm_call", "qa_verdict", "guardrail_check", "spend_event", "smoke_probe", "retry"]
_ROLES = [None, "architect", "dev", "qa"]
_PHASES = [None, "planning", "development", "testing"]


def _signature(spans: list[Span]) -> list[tuple]:
    return sorted((s.type, s.agent_role or "", s.phase or "", s.t_start) for s in spans)


def _roundtrip(tmp_path: Path, spans: list[Span], **opts) -> list[Span]:
    path = tmp_path / "otel.harness.jsonl"
    path.write_text(to_jsonl(export_requests(make_trace(spans), ExportOptions(**opts))))
    return import_otlp(path)


def test_merged_unpaired_and_phases_come_back_exactly(tmp_path: Path) -> None:
    spans = [
        span("phase_start", 0, phase="development", sid="p0"),
        *tool_pair(1, "write_file"),
        *tool_pair(3, "run_tests", ok=False),
        span("tool_use", 6, role="dev", phase="development", tool="orphan", run_id="r1"),
        span("llm_call", 7, usage={"input_tokens": 3}),
        span("phase_end", 9, phase="development", sid="p1"),
    ]
    assert _signature(_roundtrip(tmp_path, spans)) == _signature(spans)


@pytest.mark.parametrize("seed", range(40))
def test_random_traces_round_trip(tmp_path: Path, seed: int) -> None:
    rng = random.Random(seed)
    spans: list[Span] = []
    for i in range(rng.randint(1, 60)):
        t = rng.randint(0, 120)
        if rng.random() < 0.3:
            pair = tool_pair(
                t,
                rng.choice(["read_file", "write_file", "run_tests"]),
                role=rng.choice(["dev", "qa"]),
                phase=rng.choice(_PHASES[1:]),
            )
            spans.extend(pair if rng.random() < 0.8 else pair[:1])
        else:
            spans.append(
                span(
                    rng.choice(_KINDS),
                    t,
                    role=rng.choice(_ROLES),
                    phase=rng.choice(_PHASES),
                    sid=f"x{i}",
                )
            )
    back = _roundtrip(tmp_path, spans, with_content=bool(seed % 2))
    assert _signature(back) == _signature(spans)
    assert kind_counts(back) == kind_counts(spans)


def test_framework_spans_in_otlp_list_form_map_by_operation(tmp_path: Path) -> None:
    request = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "name": "chat claude",
                                "startTimeUnixNano": "100",
                                "endTimeUnixNano": "200",
                                "attributes": [
                                    {
                                        "key": "gen_ai.operation.name",
                                        "value": {"stringValue": "chat"},
                                    }
                                ],
                            },
                            {
                                "name": "execute_tool x",
                                "startTimeUnixNano": "200",
                                "endTimeUnixNano": "300",
                                "attributes": [
                                    {
                                        "key": "gen_ai.operation.name",
                                        "value": {"stringValue": "execute_tool"},
                                    }
                                ],
                            },
                        ]
                    }
                ]
            }
        ]
    }
    path = tmp_path / "framework.jsonl"
    path.write_text(json.dumps(request) + "\n" + json.dumps(request) + "\n")
    counts = kind_counts(import_otlp(path))
    assert counts == {"llm_call": 2, "tool_use": 2, "tool_result": 2}


def test_root_run_span_is_not_imported(tmp_path: Path) -> None:
    back = _roundtrip(tmp_path, [span("llm_call", 1)])
    assert [s.type for s in back] == ["llm_call"]
