"""Unit tests for evals.trace.parsers (task 1.2).

Each parser is exercised with (a) well-formed input, (b) truncated final line
where applicable, (c) invalid JSON, and (d) a missing path — all must return
results + warnings with zero exceptions.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from evals.trace.parsers import (
    parse_audit_jsonl,
    parse_costs_jsonl,
    parse_langgraph_messages,
    parse_phases_jsonl,
    parse_session_json,
    parse_smoke_report,
    scan_workspace_artifacts,
)

pytestmark = pytest.mark.eval_unit

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "parser_samples"


class TestParsePhasesJsonl:
    def test_well_formed(self) -> None:
        spans, warnings = parse_phases_jsonl(FIXTURES / "phases_well_formed.jsonl")
        assert warnings == []
        assert len(spans) == 5
        assert spans[0].span_id == "phases_0000"
        assert spans[0].type == "phase_start"
        assert spans[0].phase == "planning"
        assert spans[1].type == "phase_end"
        assert spans[3].type == "retry"

    def test_truncated_final_line(self) -> None:
        spans, warnings = parse_phases_jsonl(FIXTURES / "phases_truncated.jsonl")
        assert len(spans) == 1
        assert any("truncated" in w for w in warnings)

    def test_invalid_json_line(self) -> None:
        spans, warnings = parse_phases_jsonl(FIXTURES / "phases_invalid.jsonl")
        assert len(spans) == 2
        assert any("invalid JSON" in w for w in warnings)

    def test_missing_file(self) -> None:
        spans, warnings = parse_phases_jsonl(FIXTURES / "does_not_exist.jsonl")
        assert spans == []
        assert any(w.startswith("missing:") for w in warnings)


class TestParseCostsJsonl:
    def test_well_formed(self) -> None:
        spans, cost, warnings = parse_costs_jsonl(FIXTURES / "costs_well_formed.jsonl")
        assert warnings == []
        assert cost is not None
        assert cost.source == "provider_usage"
        assert cost.usd is not None
        assert cost.usd == pytest.approx(0.0123 + 0.0456 + 0.0579)
        assert cost.input_tokens == 300
        assert cost.output_tokens == 130
        types = {s.type for s in spans}
        assert "spend_event" in types
        assert "llm_call" in types
        assert spans[0].span_id.startswith("costs_")

    def test_truncated_final_line(self) -> None:
        spans, cost, warnings = parse_costs_jsonl(FIXTURES / "costs_truncated.jsonl")
        assert len(spans) >= 1
        assert any("truncated" in w for w in warnings)
        assert cost is not None

    def test_invalid_json_line(self) -> None:
        spans, cost, warnings = parse_costs_jsonl(FIXTURES / "costs_invalid.jsonl")
        assert any("invalid JSON" in w for w in warnings)
        assert cost is not None
        assert any(s.type == "spend_event" for s in spans)

    def test_missing_file(self) -> None:
        spans, cost, warnings = parse_costs_jsonl(FIXTURES / "missing_costs.jsonl")
        assert spans == []
        assert cost is None
        assert any(w.startswith("missing:") for w in warnings)


class TestParseAuditJsonl:
    def test_well_formed(self) -> None:
        spans, warnings = parse_audit_jsonl(FIXTURES / "audit_well_formed.jsonl")
        assert warnings == []
        assert [s.type for s in spans] == [
            "tool_use",
            "tool_result",
            "subagent_start",
            "subagent_stop",
            "guardrail_check",
        ]
        assert spans[0].span_id == "audit_0000"

    def test_truncated_final_line(self) -> None:
        spans, warnings = parse_audit_jsonl(FIXTURES / "audit_truncated.jsonl")
        assert len(spans) == 1
        assert any("truncated" in w for w in warnings)

    def test_invalid_json_line(self) -> None:
        spans, warnings = parse_audit_jsonl(FIXTURES / "audit_invalid.jsonl")
        assert len(spans) == 2
        assert any("invalid JSON" in w for w in warnings)

    def test_missing_file(self) -> None:
        spans, warnings = parse_audit_jsonl(FIXTURES / "no_audit.jsonl")
        assert spans == []
        assert any(w.startswith("missing:") for w in warnings)


class TestParseSessionJson:
    def test_well_formed(self) -> None:
        meta, cost, warnings = parse_session_json(FIXTURES / "session_well_formed.json")
        assert warnings == []
        assert meta["session_id"] == "sess-abc"
        assert cost is not None
        assert cost.source == "sdk_reported"
        assert cost.usd == pytest.approx(0.0579)

    def test_truncated_as_invalid(self, tmp_path: Path) -> None:
        path = tmp_path / "session.json"
        path.write_text('{"session_id": "x", "total_cost_usd": ', encoding="utf-8")
        meta, cost, warnings = parse_session_json(path)
        assert meta == {}
        assert cost is None
        assert any("invalid JSON" in w for w in warnings)

    def test_invalid_json_file(self) -> None:
        meta, cost, warnings = parse_session_json(FIXTURES / "session_invalid.json")
        assert meta == {}
        assert cost is None
        assert any("invalid JSON" in w for w in warnings)

    def test_missing_file(self) -> None:
        meta, cost, warnings = parse_session_json(FIXTURES / "no_session.json")
        assert meta == {}
        assert cost is None
        assert any(w.startswith("missing:") for w in warnings)


class TestParseLanggraphMessages:
    def test_well_formed(self) -> None:
        state = {
            "messages": [
                {"role": "user", "content": "hi"},
                {
                    "role": "assistant",
                    "content": "hello",
                    "usage_metadata": {"total_tokens": 40, "input_tokens": 10, "output_tokens": 30},
                },
                {
                    "type": "ai",
                    "content": "more",
                    "response_metadata": {"token_usage": {"total_tokens": 25}},
                },
            ]
        }
        spans, total, warnings = parse_langgraph_messages(state)
        assert total == 65
        assert len(spans) == 2
        assert all(s.type == "llm_call" for s in spans)
        assert spans[0].span_id.startswith("lgmsg_")

    def test_empty_messages_like_truncated(self) -> None:
        spans, total, warnings = parse_langgraph_messages({"messages": []})
        assert spans == []
        assert total is None
        assert warnings == []

    def test_invalid_state(self) -> None:
        spans, total, warnings = parse_langgraph_messages({"messages": "not-a-list"})  # type: ignore[arg-type]
        assert spans == []
        assert total is None
        assert any("not a list" in w for w in warnings)

    def test_missing_messages(self) -> None:
        spans, total, warnings = parse_langgraph_messages({})
        assert spans == []
        assert total is None
        assert any("missing messages" in w for w in warnings)


class TestScanWorkspaceArtifacts:
    def test_well_formed(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_app.py").write_text("def test_ok():\n    assert True\n")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "readme.md").write_text("# doc\n", encoding="utf-8")
        (tmp_path / "logs").mkdir()
        (tmp_path / "logs" / "phases.jsonl").write_text("{}\n", encoding="utf-8")
        (tmp_path / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("other\n", encoding="utf-8")
        # Skipped dirs
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("x", encoding="utf-8")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "a.pyc").write_bytes(b"\x00")

        artifacts, warnings = scan_workspace_artifacts(tmp_path)
        assert warnings == []
        by_path = {a.path: a for a in artifacts}
        assert "src/app.py" in by_path and by_path["src/app.py"].kind == "source"
        assert by_path["tests/test_app.py"].kind == "test"
        assert by_path["docs/readme.md"].kind == "doc"
        assert by_path["logs/phases.jsonl"].kind == "log"
        assert by_path["Dockerfile"].kind == "config"
        assert by_path["pyproject.toml"].kind == "config"
        assert by_path["notes.txt"].kind == "other"
        assert ".git/config" not in by_path
        assert "__pycache__/a.pyc" not in by_path
        expected = hashlib.sha256(b"print('hi')\n").hexdigest()
        assert by_path["src/app.py"].sha256 == expected

    def test_put_blob_callback(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
        seen: list[bytes] = []

        def put_blob(data: bytes) -> str:
            seen.append(data)
            return "custom" + "0" * 58

        artifacts, warnings = scan_workspace_artifacts(tmp_path, put_blob=put_blob)
        assert warnings == []
        assert artifacts[0].sha256.startswith("custom")
        assert seen

    def test_truncation_before_hash(self, tmp_path: Path) -> None:
        big = tmp_path / "src"
        big.mkdir()
        payload = b"a" * (256 * 1024 + 100)
        (big / "huge.py").write_bytes(payload)
        artifacts, warnings = scan_workspace_artifacts(tmp_path)
        assert warnings == []
        art = artifacts[0]
        assert art.size_bytes == len(payload)
        truncated = payload[: 256 * 1024] + b"\n[TRUNCATED at 256KB]"
        assert art.sha256 == hashlib.sha256(truncated).hexdigest()

    def test_missing_workspace(self) -> None:
        artifacts, warnings = scan_workspace_artifacts(FIXTURES / "no_such_workspace")
        assert artifacts == []
        assert any(w.startswith("missing:") for w in warnings)


class TestParseSmokeReport:
    def test_well_formed(self) -> None:
        spans, warnings = parse_smoke_report(FIXTURES / "smoke_well_formed.json")
        assert warnings == []
        assert len(spans) == 3  # overview + 2 probes
        assert all(s.type == "smoke_probe" for s in spans)
        assert spans[0].payload["success"] is True
        assert spans[0].span_id == "smoke_0000"
        assert spans[1].payload["path"] == "/health"

    def test_truncated_as_invalid(self, tmp_path: Path) -> None:
        path = tmp_path / "smoke_results.json"
        path.write_text('{"ran": true, "success":', encoding="utf-8")
        spans, warnings = parse_smoke_report(path)
        assert spans == []
        assert any("invalid JSON" in w for w in warnings)

    def test_invalid_json_file(self) -> None:
        spans, warnings = parse_smoke_report(FIXTURES / "smoke_invalid.json")
        assert spans == []
        assert any("non-object" in w or "invalid JSON" in w for w in warnings)

    def test_missing_file(self) -> None:
        spans, warnings = parse_smoke_report(FIXTURES / "no_smoke.json")
        assert spans == []
        assert any(w.startswith("missing:") for w in warnings)
