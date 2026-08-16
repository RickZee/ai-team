"""Evidence builders for binary judges (R7.8).

``run_pytest_in_workspace`` and ``summarize_workspace`` live here; ``evals.fixtures``
re-exports them so legacy callers keep working.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from evals.annotate import render_trace_card
from evals.golden import LabelingUnit
from evals.trace.models import Trace

EVIDENCE_CAP = 4000

EvidenceBuilder = Callable[[Trace, LabelingUnit | None], str]
EVIDENCE: dict[str, EvidenceBuilder] = {}


def evidence_builder(name: str) -> Callable[[EvidenceBuilder], EvidenceBuilder]:
    """Register an evidence builder under ``EVIDENCE[name]``."""

    def deco(fn: EvidenceBuilder) -> EvidenceBuilder:
        EVIDENCE[name] = fn
        return fn

    return deco


def _cap(text: str, limit: int = EVIDENCE_CAP) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - len("\n[TRUNCATED]")] + "\n[TRUNCATED]"


def summarize_workspace(ws: Path, *, max_files: int = 10, max_chars: int = 500) -> str:
    """Summarize Python files under a workspace for judge evidence."""
    parts: list[str] = []
    for py in sorted(ws.rglob("*.py"))[:max_files]:
        rel = py.relative_to(ws)
        parts.append(f"## {rel}\n{py.read_text(errors='replace')[:max_chars]}")
    if not parts:
        parts.append("(no .py files found)")
    return "\n\n".join(parts)


def run_pytest_in_workspace(ws: Path, *, timeout: int = 120) -> dict[str, Any]:
    """Run pytest in a workspace and return a compact result dict."""
    import os as _os

    src_dirs = [ws] + [d for d in ws.rglob("src") if d.is_dir()]
    extra_paths = ":".join(str(d) for d in src_dirs)

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
    passed_m = re.search(r"(\d+) passed", stdout)
    failed_m = re.search(r"(\d+) failed", stdout)
    passed = int(passed_m.group(1)) if passed_m else 0
    failed = int(failed_m.group(1)) if failed_m else 0
    total = passed + failed
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / total if total else 0.0,
        "output": stdout[:2000],
    }


@evidence_builder("dev_phase_transcript")
def dev_phase_transcript(trace: Trace, unit: LabelingUnit | None = None) -> str:
    """Transcript of development-phase spans (tool use + LLM + errors)."""
    phase_filter: str | None = None
    if unit is not None and unit.span_id and unit.span_id != "run":
        for span in trace.spans:
            if span.span_id == unit.span_id:
                phase_filter = span.phase
                break

    lines: list[str] = [f"trace_id={trace.trace_id}", f"backend={trace.backend}"]
    for span in trace.spans:
        if phase_filter and span.phase != phase_filter:
            continue
        if span.type not in {
            "phase_start",
            "phase_end",
            "tool_use",
            "tool_result",
            "llm_call",
            "error",
        }:
            continue
        if (
            span.phase
            and "develop" not in span.phase.lower()
            and phase_filter is None
            and span.type in {"tool_use", "tool_result", "llm_call"}
            and span.phase
            not in {
                "development",
                "coding",
                "implementation",
            }
        ):
            continue
        payload_preview = str(span.payload)[:400]
        lines.append(
            f"{span.span_id} type={span.type} phase={span.phase} "
            f"role={span.agent_role} payload={payload_preview}"
        )
    if len(lines) <= 2:
        lines.append("(no development-phase tool/llm spans)")
    return _cap("\n".join(lines))


@evidence_builder("workspace_summary")
def workspace_summary(trace: Trace, unit: LabelingUnit | None = None) -> str:
    """Workspace file summary from artifacts or on-disk workspace_dir."""
    _ = unit
    if trace.workspace_dir:
        ws = Path(trace.workspace_dir)
        if ws.is_dir():
            return _cap(summarize_workspace(ws))
    lines = [f"trace_id={trace.trace_id}", "artifacts:"]
    for art in trace.artifacts[:50]:
        lines.append(f"  {art.kind}\t{art.path}\t{art.size_bytes}")
    if not trace.artifacts:
        lines.append("  (none)")
    return _cap("\n".join(lines))


@evidence_builder("security_report")
def security_report(trace: Trace, unit: LabelingUnit | None = None) -> str:
    """Guardrail and error spans relevant to security review."""
    _ = unit
    lines = [f"trace_id={trace.trace_id}", "security-relevant spans:"]
    for span in trace.spans:
        if span.type not in {"guardrail_check", "error", "tool_use"}:
            continue
        lines.append(f"{span.span_id} {span.type} {span.payload}")
    if len(lines) == 2:
        lines.append("(none)")
    return _cap("\n".join(lines))


@evidence_builder("trace_card")
def trace_card(trace: Trace, unit: LabelingUnit | None = None) -> str:
    """Reuse annotation card so human and judge see the same surface."""
    _ = unit
    return _cap(render_trace_card(trace))
