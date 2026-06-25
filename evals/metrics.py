"""Compute all eval metrics from an EvalResult.

Separates measurement from test assertions so metrics can be reused
in both pytest tests and the comparison report.
"""

from __future__ import annotations

from typing import Any

from evals.fixtures import EvalResult, LLMJudge, count_hallucinations, summarize_workspace


def compute_metrics(
    result: EvalResult,
    scenario: dict[str, Any],
    *,
    judge: LLMJudge | None = None,
    run_judge: bool = True,
) -> dict[str, Any]:
    """Populate ``result.metrics`` and ``result.judge_scores`` in-place; return metrics dict."""
    m: dict[str, Any] = {}

    # --- Task success ---
    m["success"] = result.success
    m["current_phase"] = result.current_phase

    # --- Files ---
    expected_files = scenario["expected"].get("files") or []
    test_file_patterns = scenario["expected"].get("test_files") or []
    ws = result.workspace_dir

    found_files = set(result.generated_files)
    if ws and ws.exists():
        found_files |= {p.name for p in ws.rglob("*") if p.is_file()}

    m["required_files_present"] = all(
        any(f.endswith(ef) or ef in f for f in found_files)
        for ef in expected_files
    ) if expected_files else None

    has_test_file = any(
        any(tf in f for f in found_files)
        for tf in (test_file_patterns or ["test_"])
    )
    m["test_file_present"] = has_test_file

    # --- Test results (from quality gate) ---
    tr = result.test_results
    m["test_passed"] = tr.get("passed") if tr else None
    m["lint_ok"] = (tr.get("lint") or {}).get("ok") if tr else None
    passed_n = (tr.get("tests") or {}).get("passed", 0) if tr else 0
    failed_n = (tr.get("tests") or {}).get("failed", 0) if tr else 0
    total_n = passed_n + failed_n
    m["test_pass_rate"] = passed_n / total_n if total_n else None

    # --- Trajectory ---
    m["retry_count"] = result.retry_count
    m["phase_count"] = len(result.phase_history)
    m["guardrail_fail_count"] = sum(
        1 for c in result.guardrail_checks if c.get("status") == "fail"
    )
    m["guardrail_warn_count"] = sum(
        1 for c in result.guardrail_checks if c.get("status") == "warn"
    )

    # --- Cost & latency ---
    m["cost_usd"] = result.cost_usd
    m["within_budget"] = (
        result.cost_usd <= scenario["budget_usd_max"]
        if result.cost_usd is not None
        else None
    )
    m["wall_time_s"] = result.wall_time_s

    # --- Hallucinations ---
    if ws and ws.exists():
        m["hallucination_count"] = count_hallucinations(ws)
    else:
        m["hallucination_count"] = None

    # --- Token efficiency (tokens per file) ---
    state = result.raw.get("state") or {}
    total_tokens = _extract_total_tokens(state)
    m["total_tokens"] = total_tokens
    file_count = max(len(result.generated_files), 1)
    m["tokens_per_file"] = total_tokens / file_count if total_tokens else None

    # --- LLM judge scores ---
    if run_judge and result.success and ws and ws.exists():
        _judge = judge or LLMJudge()
        evidence = summarize_workspace(ws)
        criteria = scenario["expected"].get("acceptance_criteria") or []
        print(f"  [judge] scoring {len(criteria)} criteria + goal alignment for {result.backend}...", flush=True)
        verdicts = _judge.check_all_criteria(criteria, evidence)
        result.judge_scores = {c: v.score for c, v in verdicts.items()}
        m["acceptance_criteria_scores"] = result.judge_scores
        m["acceptance_criteria_mean"] = (
            sum(result.judge_scores.values()) / len(result.judge_scores)
            if result.judge_scores else None
        )
        print(f"  [judge] goal alignment...", flush=True)
        m["goal_alignment"] = _judge.score_goal_alignment(
            scenario["description"], evidence
        )
        print(f"  [judge] done — goal_alignment={m['goal_alignment']:.2f}", flush=True)
    else:
        m["acceptance_criteria_scores"] = {}
        m["acceptance_criteria_mean"] = None
        m["goal_alignment"] = None

    result.metrics = m
    return m


def _extract_total_tokens(state: dict[str, Any]) -> int | None:
    """Sum token counts from LangGraph message metadata."""
    total = 0
    found = False
    for msg in state.get("messages") or []:
        if not isinstance(msg, dict):
            continue
        usage = (msg.get("response_metadata") or {}).get("token_usage") or {}
        if not usage and isinstance(msg, dict):
            usage = msg.get("usage_metadata") or {}
        t = usage.get("total_tokens") or 0
        if t:
            total += t
            found = True
    return total if found else None


def format_scorecard(result: EvalResult) -> str:
    """Human-readable one-page scorecard for a single backend result."""
    m = result.metrics
    lines = [
        f"Backend: {result.backend}",
        f"Scenario: {result.scenario_id}",
        f"Success: {result.success}  Phase: {result.current_phase}",
        "",
        "── Artifacts ──────────────────────────────────",
        f"  Required files present: {m.get('required_files_present')}",
        f"  Test file present:      {m.get('test_file_present')}",
        f"  Files generated:        {len(result.generated_files)}",
        "",
        "── Quality Gate ───────────────────────────────",
        f"  Tests passed:   {m.get('test_passed')}",
        f"  Test pass rate: {_fmt_pct(m.get('test_pass_rate'))}",
        f"  Lint OK:        {m.get('lint_ok')}",
        f"  Hallucinations: {m.get('hallucination_count')}",
        "",
        "── Trajectory ─────────────────────────────────",
        f"  Retries:          {m.get('retry_count')}",
        f"  Phases completed: {m.get('phase_count')}",
        f"  Guardrail fails:  {m.get('guardrail_fail_count')}",
        f"  Guardrail warns:  {m.get('guardrail_warn_count')}",
        "",
        "── Cost & Latency ─────────────────────────────",
        f"  Cost:         {_fmt_cost(m.get('cost_usd'))}",
        f"  Within budget:{m.get('within_budget')}",
        f"  Wall time:    {_fmt_sec(m.get('wall_time_s'))}",
        f"  Total tokens: {m.get('total_tokens')}",
        f"  Tokens/file:  {_fmt_float(m.get('tokens_per_file'))}",
        "",
        "── LLM Judge ──────────────────────────────────",
        f"  Goal alignment:       {_fmt_score(m.get('goal_alignment'))}",
        f"  Acceptance criteria mean: {_fmt_score(m.get('acceptance_criteria_mean'))}",
    ]
    if result.judge_scores:
        for criterion, score in result.judge_scores.items():
            lines.append(f"    [{_fmt_score(score)}] {criterion[:70]}")
    return "\n".join(lines)


def _fmt_pct(v: float | None) -> str:
    return f"{v:.0%}" if v is not None else "n/a"


def _fmt_score(v: float | None) -> str:
    return f"{v:.2f}" if v is not None else "n/a"


def _fmt_float(v: float | None) -> str:
    return f"{v:.0f}" if v is not None else "n/a"


def _fmt_cost(v: float | None) -> str:
    return f"${v:.4f}" if v is not None else "n/a"


def _fmt_sec(v: float | None) -> str:
    return f"{v:.1f}s" if v is not None else "n/a"
