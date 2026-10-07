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


def _run(
    root: Path,
    name: str,
    messages: list[dict[str, object]] | None,
    logged_tokens: int | None,
) -> Path:
    run_dir = root / name
    (run_dir / "logs").mkdir(parents=True)
    if messages is not None:
        (run_dir / "state.json").write_text(json.dumps({"messages": messages}), encoding="utf-8")
    if logged_tokens is not None:
        row = {"kind": "run_total", "spent_usd": 0.01, "total_tokens": logged_tokens}
        (run_dir / "logs" / "costs.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    return run_dir


def _msg(role: str, tokens_in: int, tokens_out: int) -> dict[str, object]:
    return {
        "name": role,
        "usage_metadata": {"input_tokens": tokens_in, "output_tokens": tokens_out},
    }


def test_batch_sums_kept_runs_and_says_why_others_were_skipped(tmp_path: Path) -> None:
    from ai_team.harness.role_cost import format_batch_report, report_runs

    kept_a = _run(tmp_path, "a", [_msg("qa_engineer", 80, 2), _msg("architect", 8, 10)], 100)
    kept_b = _run(tmp_path, "b", [_msg("qa_engineer", 40, 1), _msg("architect", 4, 5)], 50)
    thin = _run(tmp_path, "thin", [_msg("architect", 10, 10)], 1000)
    no_state = _run(tmp_path, "killed", None, 500)
    no_total = _run(tmp_path, "no-total", [_msg("qa_engineer", 1, 1)], None)

    report = report_runs([kept_a, kept_b, thin, no_state, no_total], min_coverage=0.9)

    assert report.included == ("a", "b")
    assert report.skipped["thin"].startswith("messages cover 2%")
    assert report.skipped["killed"] == "no state.json"
    assert report.skipped["no-total"] == "no run_total in logs/costs.jsonl"
    qa, architect = report.roles
    assert (qa.role, qa.input_tokens, qa.output_tokens, qa.runs) == ("qa_engineer", 120, 3, 2)
    assert architect.total_tokens == 27
    assert round(qa.median_run_share, 2) == 0.82

    text = format_batch_report(report)
    assert "runs given 5, kept 2" in text
    assert "82.0%" in text  # 123 of 150 kept tokens
    assert "40.0" in text  # QA reads 40 tokens per token written
    assert "skipped 1: no state.json" in text
    assert "skipped 1: messages cover too little" in text


def test_script_reads_run_ids_from_a_batch_file(tmp_path: Path, capsys) -> None:
    import importlib.util

    runs = tmp_path / "runs"
    _run(runs, "r1", [_msg("qa_engineer", 9, 1)], 10)
    _run(runs, "r2", None, 10)
    batch = tmp_path / "batch.json"
    batch.write_text(json.dumps({"runs": [{"run_id": "r1"}, {"run_id": "r2"}]}), encoding="utf-8")

    spec = importlib.util.spec_from_file_location(
        "role_cost_script", Path(__file__).parents[3] / "scripts" / "role_cost.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.main(["--batch", str(batch), "--runs-root", str(runs)]) == 0
    out = capsys.readouterr().out
    assert "runs given 2, kept 1" in out
    assert "qa_engineer" in out
