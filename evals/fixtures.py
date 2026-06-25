"""Shared fixtures and helpers for evals."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic
import structlog

logger = structlog.get_logger(__name__)

_SCENARIOS_DIR = Path(__file__).parent / "scenarios"
_RESULTS_DIR = Path(__file__).parent / "results"


# ---------------------------------------------------------------------------
# Scenario loading
# ---------------------------------------------------------------------------

def load_scenario(scenario_id: str) -> dict[str, Any]:
    path = _SCENARIOS_DIR / f"{scenario_id}.json"
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# EvalResult — normalized output from any backend run
# ---------------------------------------------------------------------------

@dataclass
class EvalResult:
    backend: str
    scenario_id: str
    success: bool
    current_phase: str
    generated_files: list[str] = field(default_factory=list)
    test_results: dict[str, Any] = field(default_factory=dict)
    phase_history: list[dict[str, Any]] = field(default_factory=list)
    guardrail_checks: list[dict[str, Any]] = field(default_factory=list)
    retry_count: int = 0
    cost_usd: float | None = None
    wall_time_s: float | None = None
    workspace_dir: Path | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    # Computed after __post_init__ / after judge runs
    judge_scores: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)


def _resolve_workspace(backend_name: str, raw_result: dict[str, Any]) -> Path | None:
    """Find the actual workspace directory from the backend result."""
    from ai_team.config.settings import get_settings

    try:
        ws_base = Path(get_settings().project.workspace_dir).resolve()
    except Exception:
        ws_base = Path("./workspace").resolve()

    # langgraph: thread_id in raw; crewai: project_id in raw or state
    run_id = (
        raw_result.get("thread_id")
        or raw_result.get("project_id")
        or (raw_result.get("state") or {}).get("project_id")
    )
    if run_id:
        p = ws_base / str(run_id)
        if p.exists():
            return p

    # claude-agent-sdk: workspace path in raw
    ws = raw_result.get("workspace_dir") or raw_result.get("workspace")
    if ws:
        p = Path(ws)
        if p.exists():
            return p.resolve()

    # last-resort: most-recently-modified subdir
    try:
        if ws_base.exists():
            subdirs = sorted(
                (d for d in ws_base.iterdir() if d.is_dir()),
                key=lambda d: d.stat().st_mtime,
                reverse=True,
            )
            if subdirs:
                return subdirs[0]
    except Exception:
        pass

    return None


def eval_result_from_run(
    backend_name: str,
    scenario_id: str,
    raw_result: dict[str, Any],
    *,
    workspace_dir: Path | None = None,
    wall_time_s: float | None = None,
) -> EvalResult:
    """Convert the raw dict from run_demo / backend.run() into EvalResult."""
    state = raw_result.get("state") or {}
    success = raw_result.get("success", False)
    current_phase = state.get("current_phase", "unknown")
    generated_files = [
        f["path"] if isinstance(f, dict) else str(f)
        for f in (state.get("generated_files") or [])
    ]
    test_results = state.get("test_results") or {}
    phase_history = state.get("phase_history") or []
    retry_count = int(state.get("retry_count") or 0)

    # Cost: SDK returns it in raw; crewai/langgraph don't yet track it
    cost_usd = (
        raw_result.get("cost_usd")
        or (state.get("metadata") or {}).get("cost_usd")
    )

    guardrail_checks = state.get("guardrail_checks") or []

    # Resolve actual workspace from result if caller didn't supply one
    ws = workspace_dir or _resolve_workspace(backend_name, raw_result)

    return EvalResult(
        backend=backend_name,
        scenario_id=scenario_id,
        success=success,
        current_phase=current_phase,
        generated_files=generated_files,
        test_results=test_results,
        phase_history=phase_history,
        guardrail_checks=guardrail_checks,
        retry_count=retry_count,
        cost_usd=float(cost_usd) if cost_usd is not None else None,
        wall_time_s=wall_time_s,
        workspace_dir=ws,
        raw=raw_result,
    )


# ---------------------------------------------------------------------------
# LLM Judge
# ---------------------------------------------------------------------------

@dataclass
class JudgeVerdict:
    passed: bool
    score: float
    reason: str


class LLMJudge:
    """Claude-as-judge: checks whether evidence satisfies a criterion."""

    SYSTEM = (
        "You are a strict evaluator. Given a criterion and evidence (code, file listings, "
        "test output), decide whether the criterion is satisfied. "
        'Reply with JSON only: {"passed": true/false, "score": 0.0-1.0, "reason": "one sentence"}'
    )

    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        self._client = anthropic.Anthropic()
        self._model = model

    def check(self, criterion: str, evidence: str) -> JudgeVerdict:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=256,
            system=self.SYSTEM,
            messages=[{
                "role": "user",
                "content": f"Criterion: {criterion}\n\nEvidence:\n{evidence[:4000]}",
            }],
        )
        try:
            data = json.loads(msg.content[0].text)
            return JudgeVerdict(
                passed=bool(data.get("passed", False)),
                score=float(data.get("score", 0.0)),
                reason=str(data.get("reason", "")),
            )
        except Exception as exc:
            logger.warning("llm_judge_parse_error", error=str(exc))
            return JudgeVerdict(passed=False, score=0.0, reason=f"parse error: {exc}")

    def score_goal_alignment(self, goal: str, output_text: str) -> float:
        """0-1 score: how well does output align with the stated goal?"""
        verdict = self.check(
            f"The output fully addresses this goal: {goal}",
            output_text,
        )
        return verdict.score

    def check_all_criteria(
        self, criteria: list[str], evidence: str
    ) -> dict[str, JudgeVerdict]:
        return {c: self.check(c, evidence) for c in criteria}


# ---------------------------------------------------------------------------
# Workspace helpers
# ---------------------------------------------------------------------------

def summarize_workspace(ws: Path, *, max_files: int = 10, max_chars: int = 500) -> str:
    parts: list[str] = []
    for py in sorted(ws.rglob("*.py"))[:max_files]:
        rel = py.relative_to(ws)
        parts.append(f"## {rel}\n{py.read_text(errors='replace')[:max_chars]}")
    if not parts:
        parts.append("(no .py files found)")
    return "\n\n".join(parts)


def run_pytest_in_workspace(ws: Path, *, timeout: int = 120) -> dict[str, Any]:
    conftest = ws / "conftest.py"
    if not conftest.exists():
        conftest.write_text(
            "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent))\n",
            encoding="utf-8",
        )
    result = subprocess.run(
        ["uv", "run", "pytest", "-q", f"--rootdir={ws}", "--no-header", "--tb=short"],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=ws,
    )
    stdout = (result.stdout or "") + (result.stderr or "")
    passed = int(re.search(r"(\d+) passed", stdout).group(1)) if re.search(r"(\d+) passed", stdout) else 0
    failed = int(re.search(r"(\d+) failed", stdout).group(1)) if re.search(r"(\d+) failed", stdout) else 0
    total = passed + failed
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / total if total else 0.0,
        "output": stdout[:2000],
    }


# ---------------------------------------------------------------------------
# Hallucination check
# ---------------------------------------------------------------------------

_HALLUCINATION_PATTERNS = [
    r"\bTODO\b",
    r"\bpass\b\s*#",
    r"NotImplementedError",
    r"raise\s+NotImplementedError",
    r"# placeholder",
    r"# stub",
    r"\.\.\.(?:\s*#.*)?$",
]

def count_hallucinations(workspace: Path) -> int:
    count = 0
    for py in workspace.rglob("*.py"):
        text = py.read_text(errors="replace")
        for pat in _HALLUCINATION_PATTERNS:
            count += len(re.findall(pat, text, re.MULTILINE | re.IGNORECASE))
    return count


# ---------------------------------------------------------------------------
# Save / load comparison report
# ---------------------------------------------------------------------------

def save_comparison_report(results: list[dict[str, Any]], tag: str = "") -> Path:
    from datetime import datetime
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    name = f"comparison_{tag}_{ts}.json" if tag else f"comparison_{ts}.json"
    out = _RESULTS_DIR / name
    out.write_text(json.dumps(results, indent=2, default=str))
    logger.info("eval_report_saved", path=str(out))
    return out
