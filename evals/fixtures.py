"""Shared fixtures and helpers for evals."""

from __future__ import annotations

import json
import os
import re
import statistics
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic
import httpx
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
    current_phase = state.get("current_phase", "unknown")
    # raw_result may not carry "success" (langgraph puts it on ProjectResult, not .raw dict)
    # fall back to phase check so langgraph runs that reach "complete" aren't marked failed
    success = (
        raw_result.get("success")
        if raw_result.get("success") is not None
        else (current_phase == "complete")
    )
    generated_files = [
        f["path"] if isinstance(f, dict) else str(f) for f in (state.get("generated_files") or [])
    ]
    test_results = state.get("test_results") or {}
    phase_history = state.get("phase_history") or []
    retry_count = int(state.get("retry_count") or 0)
    if not retry_count and state.get("retry_counts"):
        retry_count = sum(int(v) for v in state["retry_counts"].values())

    # Cost: SDK returns it in raw; crewai/langgraph don't yet track it
    cost_usd = raw_result.get("cost_usd") or (state.get("metadata") or {}).get("cost_usd")

    guardrail_checks = state.get("guardrail_checks") or []

    # Resolve actual workspace from result if caller didn't supply one
    ws = workspace_dir or _resolve_workspace(backend_name, raw_result)
    run_id = raw_result.get("project_id") or state.get("project_id")
    if ws and run_id:
        nested = ws / str(run_id)
        if nested.is_dir():
            ws = nested

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


def _parse_judge_json(raw_text: str, *, context: str = "") -> JudgeVerdict:
    """Parse a judge's JSON reply, tolerating markdown fences."""
    if not raw_text.strip():
        raise ValueError(f"judge returned empty response ({context})")
    text = raw_text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
        text = text.rstrip("`").strip()
    data = json.loads(text)
    return JudgeVerdict(
        passed=bool(data.get("passed", False)),
        score=float(data.get("score", 0.0)),
        reason=str(data.get("reason", "")),
    )


class LLMJudge:
    """LLM-as-judge: checks whether evidence satisfies a criterion.

    **Provider independence matters here.** This project compares backends, one of
    which (``claude-agent-sdk``) runs on Anthropic models. A judge that is also
    Anthropic introduces a self-preference confound: the judge shares a vendor with
    a contestant. Use :class:`EnsembleJudge` (or set ``AI_TEAM_JUDGE_PROVIDER`` to a
    provider that differs from the backends under test) whenever a published number
    depends on judge output.

    Configuration (env, all optional):
        ``AI_TEAM_JUDGE_PROVIDER`` — ``anthropic`` (default) or ``openrouter``.
        ``AI_TEAM_JUDGE_MODEL``    — model id for that provider.
    """

    SYSTEM = (
        "You are a strict evaluator. Given a criterion and evidence (code, file listings, "
        "test output), decide whether the criterion is satisfied. "
        'Reply with JSON only: {"passed": true/false, "score": 0.0-1.0, "reason": "one sentence"}'
    )

    TIMEOUT_S: int = 60
    DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
    DEFAULT_OPENROUTER_MODEL = "openai/gpt-5.4"

    def __init__(
        self,
        model: str | None = None,
        provider: str | None = None,
    ) -> None:
        self._provider = (provider or os.getenv("AI_TEAM_JUDGE_PROVIDER") or "anthropic").lower()
        env_model = os.getenv("AI_TEAM_JUDGE_MODEL")
        if self._provider == "anthropic":
            self._model = model or env_model or self.DEFAULT_ANTHROPIC_MODEL
            self._client: Any = anthropic.Anthropic(timeout=self.TIMEOUT_S)
        elif self._provider == "openrouter":
            self._model = model or env_model or self.DEFAULT_OPENROUTER_MODEL
            self._client = None  # plain HTTP; see _check_once_openrouter
        else:
            msg = f"Unknown judge provider {self._provider!r}. Use 'anthropic' or 'openrouter'."
            raise ValueError(msg)

    @property
    def identity(self) -> str:
        """Provider/model string, for recording judge provenance alongside scores."""
        return f"{self._provider}:{self._model}"

    def check(self, criterion: str, evidence: str) -> JudgeVerdict:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                return self._check_once(criterion, evidence)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "llm_judge_retry", attempt=attempt + 1, judge=self.identity, error=str(exc)
                )
        logger.warning("llm_judge_error", judge=self.identity, error=str(last_exc))
        return JudgeVerdict(passed=False, score=0.0, reason=f"judge error: {last_exc}")

    def _check_once(self, criterion: str, evidence: str) -> JudgeVerdict:
        prompt = f"Criterion: {criterion}\n\nEvidence:\n{evidence[:4000]}"
        if self._provider == "openrouter":
            return self._check_once_openrouter(prompt)
        return self._check_once_anthropic(prompt)

    def _check_once_anthropic(self, prompt: str) -> JudgeVerdict:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=256,
            system=self.SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            timeout=float(self.TIMEOUT_S),
        )
        raw_text = msg.content[0].text if msg.content else ""
        return _parse_judge_json(raw_text, context=f"stop_reason={msg.stop_reason}")

    def _check_once_openrouter(self, prompt: str) -> JudgeVerdict:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            msg = "OPENROUTER_API_KEY is required for the 'openrouter' judge provider"
            raise ValueError(msg)
        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": self._model,
                "max_tokens": 256,
                "messages": [
                    {"role": "system", "content": self.SYSTEM},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=float(self.TIMEOUT_S),
        )
        response.raise_for_status()
        payload = response.json()
        raw_text = payload["choices"][0]["message"]["content"]
        return _parse_judge_json(raw_text, context="openrouter")

    def score_goal_alignment(self, goal: str, output_text: str) -> float:
        """0-1 score: how well does output align with the stated goal?"""
        verdict = self.check(
            f"The output fully addresses this goal: {goal}",
            output_text,
        )
        return verdict.score

    def check_all_criteria(self, criteria: list[str], evidence: str) -> dict[str, JudgeVerdict]:
        results = {}
        for i, c in enumerate(criteria, 1):
            print(f"    [judge {i}/{len(criteria)}] {c[:60]}...", flush=True)
            results[c] = self.check(c, evidence)
            print(f"    [judge {i}/{len(criteria)}] score={results[c].score:.2f}", flush=True)
        return results


class EnsembleJudge:
    """Runs several :class:`LLMJudge` instances and reports their agreement.

    Use this for any number that gets published. A single-vendor judge cannot be
    distinguished from vendor self-preference; an ensemble drawn from different
    providers can at least *measure* how much the verdict depends on who is asking.

    ``spread`` (max score minus min score) is the number to watch: a criterion where
    judges disagree by more than ``DISAGREEMENT_THRESHOLD`` should not be reported as
    a settled result without human review.
    """

    DISAGREEMENT_THRESHOLD = 0.34

    def __init__(self, judges: list[LLMJudge] | None = None) -> None:
        # Note the `is None` check: an explicitly-passed empty list is a caller error,
        # not a request for the default panel, and must not silently fall back.
        self.judges = self._default_panel() if judges is None else judges
        if not self.judges:
            msg = (
                "EnsembleJudge requires at least one judge. With no judges passed "
                "explicitly, set ANTHROPIC_API_KEY and/or OPENROUTER_API_KEY."
            )
            raise ValueError(msg)

    @staticmethod
    def _default_panel() -> list[LLMJudge]:
        """One judge per provider that has credentials available."""
        panel: list[LLMJudge] = []
        if os.getenv("ANTHROPIC_API_KEY"):
            panel.append(LLMJudge(provider="anthropic"))
        if os.getenv("OPENROUTER_API_KEY"):
            panel.append(LLMJudge(provider="openrouter"))
        return panel

    @property
    def identity(self) -> str:
        return "ensemble[" + ", ".join(j.identity for j in self.judges) + "]"

    @property
    def is_single_vendor(self) -> bool:
        """True when every judge shares one provider — i.e. bias is not controlled."""
        return len({j.identity.split(":", 1)[0] for j in self.judges}) < 2

    def check(self, criterion: str, evidence: str) -> dict[str, Any]:
        """Return the mean verdict plus per-judge detail and an agreement spread."""
        verdicts = {j.identity: j.check(criterion, evidence) for j in self.judges}
        scores = [v.score for v in verdicts.values()]
        spread = max(scores) - min(scores) if len(scores) > 1 else 0.0
        passed_votes = [v.passed for v in verdicts.values()]
        contested = spread > self.DISAGREEMENT_THRESHOLD or len(set(passed_votes)) > 1
        if contested:
            logger.warning(
                "judge_disagreement",
                criterion=criterion[:80],
                spread=round(spread, 3),
                scores={k: round(v.score, 2) for k, v in verdicts.items()},
            )
        return {
            "score": statistics.fmean(scores),
            "passed": sum(passed_votes) > len(passed_votes) / 2,
            "spread": spread,
            "contested": contested,
            "single_vendor": self.is_single_vendor,
            "judges": {k: {"score": v.score, "passed": v.passed} for k, v in verdicts.items()},
        }

    def score_goal_alignment(self, goal: str, output_text: str) -> float:
        return float(
            self.check(f"The output fully addresses this goal: {goal}", output_text)["score"]
        )


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
    # Collect all src-like dirs: ws root + every nested src/ dir.
    # SDK puts files at ws/workspace/src/ so rglob catches it.
    import os as _os

    src_dirs = [ws] + [d for d in ws.rglob("src") if d.is_dir()]
    extra_paths = ":".join(str(d) for d in src_dirs)

    # Write conftest at ws root AND in every src dir that has test files
    # so pytest always finds the sys.path additions regardless of rootdir.
    conftest_body = (
        "import sys\nfrom pathlib import Path\n_here = Path(__file__).parent\n"
    ) + "".join(
        "sys.path.insert(0, str(_here))\n" if d == ws else f'sys.path.insert(0, r"{d}")\n'
        for d in src_dirs
    )
    for candidate in [ws] + [d for d in ws.rglob("src") if d.is_dir()]:
        cf = candidate / "conftest.py"
        if not cf.exists():
            cf.write_text(conftest_body, encoding="utf-8")

    env = {**_os.environ, "PYTHONPATH": extra_paths}
    result = subprocess.run(
        [
            "uv",
            "run",
            "pytest",
            "-q",
            f"--rootdir={ws}",
            "--no-header",
            "--tb=short",
            "--import-mode=importlib",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=ws,
        env=env,
    )
    stdout = (result.stdout or "") + (result.stderr or "")
    passed = (
        int(re.search(r"(\d+) passed", stdout).group(1))
        if re.search(r"(\d+) passed", stdout)
        else 0
    )
    failed = (
        int(re.search(r"(\d+) failed", stdout).group(1))
        if re.search(r"(\d+) failed", stdout)
        else 0
    )
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
