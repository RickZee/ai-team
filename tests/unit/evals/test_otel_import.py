"""OTLP import counts kinds, and the builder keeps harness spans when both exist."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from evals.cli import main as evals_main
from evals.trace.builder import TraceBuilder
from evals.trace.otel_import import import_otlp, kind_counts

ROOT = Path(__file__).resolve().parents[3] / "evals" / "fixtures" / "otel"


def test_strands_fixture_counts() -> None:
    counts = kind_counts(import_otlp(ROOT / "strands.jsonl"))
    assert counts["llm_call"] == 1
    assert counts["tool_use"] == 1
    assert counts["tool_result"] == 1
    assert counts["agent"] == 1
    assert counts["other"] == 1


def test_agent_framework_fixture_counts() -> None:
    counts = kind_counts(import_otlp(ROOT / "agent_framework.jsonl"))
    assert counts["llm_call"] == 2
    assert counts["tool_use"] == 1
    assert counts["tool_result"] == 1
    assert counts["agent"] == 1
    assert counts["other"] == 1


def test_import_otel_cli(capsys) -> None:
    code = evals_main(["trace", "import-otel", str(ROOT / "strands.jsonl")])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["other"] == 1


def test_two_readers_prefer_harness_on_mismatch(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "otel.jsonl").write_text(
        (ROOT / "agent_framework.jsonl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "run.json").write_text(
        json.dumps(
            {
                "backend": "langgraph",
                "project_id": "two",
                "started_at": now.isoformat(),
                "workspace_dir": str(tmp_path),
                "output_dir": str(tmp_path),
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "logs" / "audit.jsonl").write_text(
        json.dumps(
            {
                "type": "tool_use",
                "tool": "write_file",
                "timestamp": now.isoformat(),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    trace = TraceBuilder(backend="langgraph", scenario={"id": "two"}).from_workspace(tmp_path)
    otel_count = kind_counts(import_otlp(ROOT / "agent_framework.jsonl"))
    otel_total = sum(otel_count.values())
    assert trace.raw_result["second_reader"]["span_count"] == otel_total
    assert trace.raw_result["second_reader"]["preferred"] == "harness"
    assert trace.raw_result["second_reader"]["harness_span_count"] == len(trace.spans)
    assert (
        trace.raw_result["second_reader"]["span_count"]
        > trace.raw_result["second_reader"]["harness_span_count"]
    )
