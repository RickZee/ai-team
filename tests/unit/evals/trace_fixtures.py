"""Builders for synthetic Trace fixtures used by check unit tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from evals.provenance import Provenance
from evals.trace.models import SCHEMA_VERSION, Artifact, CostRecord, Span, Trace

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "traces"

OutcomeWanted = Literal["fail", "pass", "na"]


def _prov(**kwargs: Any) -> Provenance:
    base: dict[str, Any] = {
        "git_sha": "deadbeef",
        "git_dirty": False,
        "python_version": "3.12.0",
        "platform": "test",
        "harness_version": "0.1.0",
        "taxonomy_version": "1.0.0",
        "pricing_table_version": "unset",
        "scenario_content_sha256": "b" * 64,
        "model_ids": {"fullstack_developer": "test-model"},
        "tier": "A",
    }
    base.update(kwargs)
    return Provenance(**base)


def base_trace(
    *,
    check_id: str,
    outcome: OutcomeWanted,
    spans: list[Span] | None = None,
    artifacts: list[Artifact] | None = None,
    status: str = "complete",
    backend: str = "crewai",
    cost_usd: float | None = 0.01,
    warnings: list[str] | None = None,
    raw_result: dict[str, Any] | None = None,
    workspace_dir: str | None = None,
    scenario_id: str = "smoke-test",
) -> Trace:
    """Construct a minimal Trace with a stable id for fixtures."""
    t0 = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
    tid = f"{check_id}__{outcome}__fixture"
    return Trace(
        schema_version=SCHEMA_VERSION,
        trace_id=tid,
        scenario_id=scenario_id,
        backend=backend,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        started_at=t0,
        ended_at=t0 + timedelta(minutes=5),
        spans=spans or [],
        artifacts=artifacts or [],
        cost=CostRecord(
            usd=cost_usd,
            input_tokens=100,
            output_tokens=50,
            source="provider_usage",
        ),
        provenance=_prov(),
        warnings=warnings or [],
        raw_result=raw_result or {},
        workspace_dir=workspace_dir,
    )


def _span(
    i: int,
    typ: str,
    *,
    phase: str | None = None,
    agent_role: str | None = None,
    payload: dict[str, Any] | None = None,
    t_offset_s: float = 0,
    duration_s: float | None = 0,
) -> Span:
    t0 = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC) + timedelta(seconds=t_offset_s)
    t_end = None if duration_s is None else t0 + timedelta(seconds=duration_s)
    return Span(
        span_id=f"span_{i:04d}",
        type=typ,  # type: ignore[arg-type]
        t_start=t0,
        t_end=t_end,
        phase=phase,
        agent_role=agent_role,
        payload=payload or {},
    )


def build_for_check(check_id: str, outcome: OutcomeWanted) -> Trace:
    """Build the canonical fail/pass/na fixture for *check_id*."""
    builders = {
        "CHK-tool-call-emitted": _tool_call,
        "CHK-phase-repeat-bounded": _phase_repeat,
        "CHK-listener-self-trigger": _listener,
        "CHK-interrupt-latency": _interrupt,
        "CHK-workspace-isolation": _isolation,
        "CHK-guardrail-fp-budget": _guardrail,
        "CHK-runtime-smoke-present": _smoke,
        "CHK-spend-ceiling": _spend,
        "CHK-metric-source-agreement": _metrics,
        "CHK-provider-error-rate": _provider,
        "CHK-gate-env-fidelity": _gate_env,
        "CHK-required-artifacts": _required,
        "CHK-hallucination-density": _hallucination,
    }
    return builders[check_id](outcome)


def _tool_call(outcome: OutcomeWanted) -> Trace:
    if outcome == "na":
        return base_trace(
            check_id="CHK-tool-call-emitted",
            outcome=outcome,
            spans=[_span(0, "phase_start", phase="planning")],
            warnings=["no audit log for backend=crewai; tool-level checks skipped"],
        )
    if outcome == "fail":
        return base_trace(
            check_id="CHK-tool-call-emitted",
            outcome=outcome,
            spans=[
                _span(0, "phase_start", phase="development", agent_role="fullstack_developer"),
                _span(
                    1,
                    "phase_end",
                    phase="development",
                    agent_role="fullstack_developer",
                    payload={"output": "```python\ndef add(a,b): return a+b\n```\nShall I save?"},
                    t_offset_s=10,
                ),
            ],
            artifacts=[],
        )
    return base_trace(
        check_id="CHK-tool-call-emitted",
        outcome=outcome,
        spans=[
            _span(0, "phase_start", phase="development", agent_role="fullstack_developer"),
            _span(
                1,
                "tool_use",
                phase="development",
                payload={"tool": "file_writer", "path": "calc.py"},
                t_offset_s=5,
            ),
            _span(2, "phase_end", phase="development", t_offset_s=10),
        ],
        artifacts=[
            Artifact(path="calc.py", size_bytes=40, sha256="a" * 64, kind="source"),
        ],
    )


def _phase_repeat(outcome: OutcomeWanted) -> Trace:
    if outcome == "na":
        return base_trace(
            check_id="CHK-phase-repeat-bounded",
            outcome=outcome,
            spans=[_span(0, "llm_call", payload={"tokens": 1})],
        )
    if outcome == "fail":
        spans = [
            _span(
                i,
                "phase_start",
                phase="development",
                agent_role="fullstack_developer",
                t_offset_s=float(i),
            )
            for i in range(6)
        ]
        return base_trace(
            check_id="CHK-phase-repeat-bounded",
            outcome=outcome,
            spans=spans,
            raw_result={"scenario": {"max_phase_repeats": 4}},
        )
    spans = [
        _span(
            i,
            "phase_start",
            phase="development",
            agent_role="fullstack_developer",
            t_offset_s=float(i),
        )
        for i in range(2)
    ]
    return base_trace(check_id="CHK-phase-repeat-bounded", outcome=outcome, spans=spans)


def _listener(outcome: OutcomeWanted) -> Trace:
    if outcome == "na":
        return base_trace(
            check_id="CHK-listener-self-trigger",
            outcome=outcome,
            backend="langgraph",
        )
    if outcome == "fail":
        return base_trace(
            check_id="CHK-listener-self-trigger",
            outcome=outcome,
            raw_result={"listener_self_triggers": ["retry_development"]},
        )
    return base_trace(check_id="CHK-listener-self-trigger", outcome=outcome)


def _interrupt(outcome: OutcomeWanted) -> Trace:
    if outcome == "na":
        return base_trace(
            check_id="CHK-interrupt-latency",
            outcome=outcome,
            spans=[_span(0, "phase_start", phase="planning")],
        )
    if outcome == "fail":
        return base_trace(
            check_id="CHK-interrupt-latency",
            outcome=outcome,
            spans=[
                _span(
                    0,
                    "human_interrupt",
                    payload={"surfaced_at": "2026-08-01T14:10:00+00:00"},
                    duration_s=None,
                ),
            ],
            raw_result={"scenario": {"max_interrupt_latency_s": 60}},
        )
    return base_trace(
        check_id="CHK-interrupt-latency",
        outcome=outcome,
        spans=[
            _span(
                0,
                "human_interrupt",
                payload={"surfaced_at": "2026-08-01T12:00:30+00:00"},
                duration_s=30,
            ),
        ],
    )


def _isolation(outcome: OutcomeWanted) -> Trace:
    if outcome == "na":
        return base_trace(
            check_id="CHK-workspace-isolation",
            outcome=outcome,
            workspace_dir="/tmp/ws-a",
        )
    if outcome == "fail":
        return base_trace(
            check_id="CHK-workspace-isolation",
            outcome=outcome,
            workspace_dir="/tmp/shared",
            raw_result={"suite_workspace_dirs": ["/tmp/shared", "/tmp/shared", "/tmp/other"]},
        )
    return base_trace(
        check_id="CHK-workspace-isolation",
        outcome=outcome,
        workspace_dir="/tmp/ws-a",
        raw_result={"suite_workspace_dirs": ["/tmp/ws-a", "/tmp/ws-b", "/tmp/ws-c"]},
    )


def _guardrail(outcome: OutcomeWanted) -> Trace:
    arts = [Artifact(path="tests/test_app.py", size_bytes=10, sha256="c" * 64, kind="test")]
    if outcome == "na":
        return base_trace(
            check_id="CHK-guardrail-fp-budget",
            outcome=outcome,
            spans=[_span(0, "phase_start", phase="testing")],
            artifacts=arts,
        )
    if outcome == "fail":
        return base_trace(
            check_id="CHK-guardrail-fp-budget",
            outcome=outcome,
            spans=[
                _span(
                    0,
                    "guardrail_check",
                    payload={"outcome": "fail", "rule": "scope_relevance"},
                ),
            ],
            artifacts=arts,
            status="complete",
        )
    return base_trace(
        check_id="CHK-guardrail-fp-budget",
        outcome=outcome,
        spans=[
            _span(0, "guardrail_check", payload={"outcome": "pass", "rule": "scope_relevance"}),
        ],
        artifacts=arts,
        status="complete",
    )


def _smoke(outcome: OutcomeWanted) -> Trace:
    if outcome == "na":
        return base_trace(
            check_id="CHK-runtime-smoke-present",
            outcome=outcome,
            status="failed",
            spans=[_span(0, "smoke_probe", payload={"success": False, "ran": True})],
        )
    if outcome == "fail":
        return base_trace(
            check_id="CHK-runtime-smoke-present",
            outcome=outcome,
            status="complete",
            spans=[],
        )
    return base_trace(
        check_id="CHK-runtime-smoke-present",
        outcome=outcome,
        status="complete",
        spans=[_span(0, "smoke_probe", payload={"success": True, "ran": True})],
    )


def _spend(outcome: OutcomeWanted) -> Trace:
    if outcome == "na":
        return base_trace(
            check_id="CHK-spend-ceiling",
            outcome=outcome,
            cost_usd=None,
            spans=[],
            raw_result={"scenario": {}},
        )
    if outcome == "fail":
        return base_trace(
            check_id="CHK-spend-ceiling",
            outcome=outcome,
            cost_usd=1.5,
            raw_result={"scenario": {"budget_usd_max": 0.5}},
        )
    return base_trace(
        check_id="CHK-spend-ceiling",
        outcome=outcome,
        cost_usd=0.1,
        raw_result={"scenario": {"budget_usd_max": 0.5}},
    )


def _metrics(outcome: OutcomeWanted) -> Trace:
    arts = [
        Artifact(path="a.py", size_bytes=1, sha256="d" * 64, kind="source"),
        Artifact(path="b.py", size_bytes=1, sha256="e" * 64, kind="source"),
    ]
    if outcome == "na":
        return base_trace(check_id="CHK-metric-source-agreement", outcome=outcome, artifacts=arts)
    if outcome == "fail":
        return base_trace(
            check_id="CHK-metric-source-agreement",
            outcome=outcome,
            artifacts=arts,
            cost_usd=1.0,
            raw_result={"event_metrics": {"file_count": 0, "cost_usd": 1.0}},
        )
    return base_trace(
        check_id="CHK-metric-source-agreement",
        outcome=outcome,
        artifacts=arts,
        cost_usd=1.0,
        raw_result={"event_metrics": {"file_count": 2, "cost_usd": 1.0}},
    )


def _provider(outcome: OutcomeWanted) -> Trace:
    if outcome == "na":
        return base_trace(
            check_id="CHK-provider-error-rate",
            outcome=outcome,
            spans=[_span(0, "phase_start", phase="planning")],
        )
    if outcome == "fail":
        return base_trace(
            check_id="CHK-provider-error-rate",
            outcome=outcome,
            spans=[
                _span(
                    0,
                    "error",
                    payload={"status_code": 400, "message": "provider rejected tool id"},
                ),
                _span(1, "error", payload={"status_code": 400, "message": "again"}, t_offset_s=1),
            ],
            raw_result={"scenario": {"max_provider_errors": 0}},
        )
    return base_trace(
        check_id="CHK-provider-error-rate",
        outcome=outcome,
        spans=[_span(0, "llm_call", payload={"status_code": 200})],
        raw_result={"scenario": {"max_provider_errors": 0}},
    )


def _gate_env(outcome: OutcomeWanted) -> Trace:
    if outcome == "na":
        return base_trace(
            check_id="CHK-gate-env-fidelity",
            outcome=outcome,
            spans=[_span(0, "error", payload={"message": "AssertionError"})],
        )
    if outcome == "fail":
        return base_trace(
            check_id="CHK-gate-env-fidelity",
            outcome=outcome,
            spans=[
                _span(
                    0,
                    "error",
                    payload={"message": "ModuleNotFoundError: No module named 'flask_sqlalchemy'"},
                ),
            ],
            raw_result={"requirements_txt": "flask==3.0\nflask_sqlalchemy==3.1\n"},
        )
    return base_trace(
        check_id="CHK-gate-env-fidelity",
        outcome=outcome,
        spans=[
            _span(
                0,
                "error",
                payload={"message": "ModuleNotFoundError: No module named 'totally_missing'"},
            ),
        ],
        raw_result={"requirements_txt": "flask==3.0\n"},
    )


def _required(outcome: OutcomeWanted) -> Trace:
    if outcome == "na":
        return base_trace(
            check_id="CHK-required-artifacts",
            outcome=outcome,
            scenario_id="unknown-scenario-no-expected",
            raw_result={"scenario": {}},
        )
    if outcome == "fail":
        return base_trace(
            check_id="CHK-required-artifacts",
            outcome=outcome,
            artifacts=[],
            raw_result={"scenario": {"expected": {"files": ["calc.py"]}}},
        )
    return base_trace(
        check_id="CHK-required-artifacts",
        outcome=outcome,
        artifacts=[Artifact(path="calc.py", size_bytes=10, sha256="f" * 64, kind="source")],
        raw_result={"scenario": {"expected": {"files": ["calc.py"]}}},
    )


def _hallucination(outcome: OutcomeWanted) -> Trace:
    if outcome == "na":
        return base_trace(check_id="CHK-hallucination-density", outcome=outcome)
    if outcome == "fail":
        return base_trace(
            check_id="CHK-hallucination-density",
            outcome=outcome,
            raw_result={"hallucination_count": 5, "max_hallucinations": 0},
        )
    return base_trace(
        check_id="CHK-hallucination-density",
        outcome=outcome,
        raw_result={"hallucination_count": 0, "max_hallucinations": 0},
    )


ALL_CHECK_IDS = [
    "CHK-tool-call-emitted",
    "CHK-phase-repeat-bounded",
    "CHK-listener-self-trigger",
    "CHK-interrupt-latency",
    "CHK-workspace-isolation",
    "CHK-guardrail-fp-budget",
    "CHK-runtime-smoke-present",
    "CHK-spend-ceiling",
    "CHK-metric-source-agreement",
    "CHK-provider-error-rate",
    "CHK-gate-env-fidelity",
    "CHK-required-artifacts",
    "CHK-hallucination-density",
]


def dump_all_fixtures(out_dir: Path | None = None) -> list[Path]:
    """Write all fail/pass/na fixture JSON files; return paths written."""
    dest = out_dir or FIXTURES_DIR
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for check_id in ALL_CHECK_IDS:
        for outcome in ("fail", "pass", "na"):
            trace = build_for_check(check_id, outcome)  # type: ignore[arg-type]
            path = dest / f"{check_id}__{outcome}.json"
            path.write_text(
                json.dumps(trace.model_dump(mode="json"), indent=2) + "\n",
                encoding="utf-8",
            )
            written.append(path)
    return written


def load_fixture(check_id: str, outcome: OutcomeWanted) -> Trace:
    """Load a fixture from disk, falling back to in-memory build."""
    path = FIXTURES_DIR / f"{check_id}__{outcome}.json"
    if path.is_file():
        return Trace.model_validate_json(path.read_text(encoding="utf-8"))
    return build_for_check(check_id, outcome)
