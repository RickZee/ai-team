"""Per-role token report."""

from __future__ import annotations

import json
from pathlib import Path

from ai_team.harness.role_cost import format_report, report_run


def test_string_messages_sum_by_role(tmp_path: Path) -> None:
    message = (
        "content='hi' response_metadata={'token_usage': "
        "{'completion_tokens': 10, 'prompt_tokens': 40, 'total_tokens': 50}} "
        "name='qa_engineer'"
    )
    other = (
        "content='plan' response_metadata={'token_usage': "
        "{'completion_tokens': 5, 'prompt_tokens': 5, 'total_tokens': 10}} "
        "name='architect'"
    )
    (tmp_path / "state.json").write_text(
        json.dumps({"messages": [message, other]}),
        encoding="utf-8",
    )
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "costs.jsonl").write_text(
        json.dumps({"kind": "run_total", "spent_usd": 0.02}) + "\n",
        encoding="utf-8",
    )
    report = report_run(tmp_path)
    assert report.roles[0].role == "qa_engineer"
    assert report.roles[0].input_tokens == 40
    assert report.roles[0].output_tokens == 10
    assert report.spent_usd == 0.02
    text = format_report(report)
    assert "83.3%" in text
    assert "0.0167" in text
    assert "by tokens" in text


def test_mapping_messages_are_counted(tmp_path: Path) -> None:
    (tmp_path / "state.json").write_text(
        json.dumps(
            {
                "messages": [
                    {
                        "name": "backend_developer",
                        "usage_metadata": {"input_tokens": 3, "output_tokens": 1},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    report = report_run(tmp_path)
    assert report.roles[0].total_tokens == 4
    assert report.spent_usd is None
