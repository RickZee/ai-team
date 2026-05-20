#!/usr/bin/env python3
"""
Agentic eval harness — runs real LLM pipeline on demo fixtures and asserts behavior.

Usage:
    uv run python scripts/eval_smoke.py                        # run demo 00 (default)
    uv run python scripts/eval_smoke.py --demo 01              # demo 01
    uv run python scripts/eval_smoke.py --demo 00 01           # multiple demos
    uv run python scripts/eval_smoke.py --backend langgraph    # different backend
    uv run python scripts/eval_smoke.py --team smoke           # override team profile
    uv run python scripts/eval_smoke.py --json                 # machine-readable output

Exit code 0 = all evals passed. Non-zero = at least one failed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMOS_DIR = REPO_ROOT / "demos"
WORKSPACE_DIR = REPO_ROOT / "workspace"


# ---------------------------------------------------------------------------
# Check primitives
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def check_phase_complete(state: dict) -> CheckResult:
    phase = state.get("current_phase", "")
    passed = phase == "complete"
    return CheckResult("phase==complete", passed, f"phase={phase!r}")


def check_no_loop(state: dict, run_id: str) -> CheckResult:
    """project_complete log line must appear exactly once."""
    log_dir = REPO_ROOT / "output" / "runs" / run_id / "logs"
    audit = log_dir / "audit.jsonl"
    if not audit.exists():
        # Try finding any jsonl log with project_complete event
        count = 0
        for logf in log_dir.glob("*.jsonl"):
            try:
                for line in logf.read_text().splitlines():
                    if "project_complete" in line:
                        count += 1
            except Exception:
                pass
        if count == 0:
            return CheckResult("no_completion_loop", True, "no audit.jsonl, no loop detected")
        return CheckResult(
            "no_completion_loop",
            count == 1,
            f"project_complete appeared {count}x (want 1)",
        )
    count = sum(
        1
        for line in audit.read_text().splitlines()
        if line.strip() and "project_complete" in line
    )
    return CheckResult(
        "no_completion_loop",
        count == 1,
        f"project_complete appeared {count}x (want 1)",
    )


def check_artifacts_exist(state: dict, run_id: str, expected_artifact_hints: list[str]) -> list[CheckResult]:
    """Check generated_files in state contain expected name fragments."""
    generated = state.get("generated_files") or []
    generated_paths = [f.get("path", "") if isinstance(f, dict) else str(f) for f in generated]
    results = []
    for hint in expected_artifact_hints:
        found = any(hint.lower() in p.lower() for p in generated_paths)
        results.append(CheckResult(
            f"artifact:{hint}",
            found,
            f"generated_files={[p for p in generated_paths]}" if not found else "",
        ))
    return results


def _materialize_workspace(run_id: str, state: dict) -> Path:
    """Write generated_files from state to a temp dir under workspace for pytest."""
    import tempfile
    ws_base = WORKSPACE_DIR / run_id / "_eval_materialized"
    ws_base.mkdir(parents=True, exist_ok=True)
    generated = state.get("generated_files") or []
    for f in generated:
        if not isinstance(f, dict):
            continue
        rel = f.get("path", "")
        content = f.get("content", "")
        if not rel or not content:
            continue
        dest = ws_base / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return ws_base


def check_workspace_tests_pass(run_id: str, state: dict | None = None) -> CheckResult:
    """Run pytest on generated files. Materializes from state if workspace is empty."""
    ws = WORKSPACE_DIR / run_id
    if not ws.exists():
        return CheckResult("workspace_tests_pass", False, f"workspace not found: {ws}")

    test_files = list(ws.rglob("test_*.py")) + list(ws.rglob("*_test.py"))
    # If workspace empty and state provided, materialize files first
    if not test_files and state:
        ws = _materialize_workspace(run_id, state)
        test_files = list(ws.rglob("test_*.py")) + list(ws.rglob("*_test.py"))

    if not test_files:
        return CheckResult("workspace_tests_pass", False, "no test files in workspace")

    # Build PYTHONPATH: include ws root, ws/src, and any immediate subdirs with src/
    pythonpath_parts = [str(ws), str(ws / "src")]
    for child in ws.iterdir():
        if child.is_dir() and (child / "src").is_dir():
            pythonpath_parts.append(str(child / "src"))
        elif child.is_dir():
            pythonpath_parts.append(str(child))
    env = {**os.environ, "PYTHONPATH": ":".join(pythonpath_parts)}

    try:
        cmd = [
            sys.executable, "-m", "pytest", str(ws),
            "--tb=short", "-q", "--no-header",
            f"--rootdir={ws}",
            "--ignore-glob=**/node_modules/**",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env, cwd=str(ws))
        passed = r.returncode == 0
        out = (r.stdout + r.stderr)
        # Extract last 3 lines for summary
        lines = [l for l in out.splitlines() if l.strip()]
        detail = "\n".join(lines[-3:]) if not passed else (lines[-1] if lines else "")
        return CheckResult("workspace_tests_pass", passed, detail)
    except subprocess.TimeoutExpired:
        return CheckResult("workspace_tests_pass", False, "pytest timed out after 60s")
    except Exception as e:
        return CheckResult("workspace_tests_pass", False, str(e))


def check_cost_under(state: dict, threshold_usd: float) -> CheckResult:
    cost = state.get("total_cost_usd")
    if cost is None:
        return CheckResult("cost_under_threshold", True, "cost not tracked (skip)")
    passed = cost <= threshold_usd
    return CheckResult("cost_under_threshold", passed, f"cost=${cost:.4f}, threshold=${threshold_usd:.2f}")


def check_has_generated_files(state: dict) -> CheckResult:
    files = state.get("generated_files") or []
    passed = len(files) > 0
    return CheckResult("has_generated_files", passed, f"{len(files)} file(s) generated")


def check_no_errors(state: dict) -> CheckResult:
    errors = state.get("errors") or []
    passed = len(errors) == 0
    detail = "; ".join(e.get("message", str(e))[:100] for e in errors[:3]) if errors else ""
    return CheckResult("no_errors_in_state", passed, detail)


# ---------------------------------------------------------------------------
# Demo-specific check sets
# ---------------------------------------------------------------------------

DEMO_CHECKS: dict[str, dict[str, Any]] = {
    "00": {
        "artifact_hints": ["calc", "add"],
        "content_checks": {
            "def add": "generated code must define add()",
            "def test_": "generated tests must have at least one test function",
        },
        "cost_threshold_usd": 0.50,
    },
    "01": {
        "artifact_hints": ["app", "test"],
        "content_checks": {},
        "cost_threshold_usd": 1.00,
    },
    "02": {
        "artifact_hints": ["main", "test"],  # todo logic lands in main.py or similar
        "content_checks": {},
        "cost_threshold_usd": 2.00,
    },
    "03": {
        "artifact_hints": ["test"],
        "content_checks": {},
        "cost_threshold_usd": 2.00,
    },
    "04": {
        "artifact_hints": ["app", "test"],
        "content_checks": {},
        "cost_threshold_usd": 2.00,
    },
    "05": {
        "artifact_hints": ["service", "gateway"],
        "content_checks": {},
        "cost_threshold_usd": 3.00,
    },
}


def check_content(state: dict, run_id: str, content_checks: dict[str, str]) -> list[CheckResult]:
    """Search for expected strings across all generated file contents in state."""
    results = []
    generated = state.get("generated_files") or []
    all_content = "\n".join(
        f.get("content", "") if isinstance(f, dict) else "" for f in generated
    )
    # Also search workspace files
    ws = WORKSPACE_DIR / run_id
    if ws.exists():
        for py_file in ws.rglob("*.py"):
            try:
                all_content += "\n" + py_file.read_text()
            except Exception:
                pass
    for needle, label in content_checks.items():
        found = needle in all_content
        results.append(CheckResult(f"content:{needle!r}", found, label if not found else ""))
    return results


# ---------------------------------------------------------------------------
# Eval runner
# ---------------------------------------------------------------------------

@dataclass
class EvalResult:
    demo: str
    backend: str
    team: str
    duration_seconds: float
    checks: list[CheckResult] = field(default_factory=list)
    run_id: str = ""
    error: str = ""

    @property
    def passed(self) -> bool:
        return not self.error and all(c.passed for c in self.checks)

    @property
    def failed_checks(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]


def run_demo_eval(
    demo_id: str,
    backend: str,
    team: str | None,
    skip_estimate: bool,
    timeout_seconds: int,
) -> EvalResult:
    demo_dir = DEMOS_DIR / f"{demo_id}_*"
    matches = sorted(DEMOS_DIR.glob(f"{demo_id}_*"))
    if not matches:
        return EvalResult(demo_id, backend, team or "auto", 0, error=f"Demo dir not found: {demo_id}_*")
    demo_path = matches[0]

    # Resolve team from input.json if not overridden
    actual_team = team
    if actual_team is None:
        try:
            inp = json.loads((demo_path / "input.json").read_text())
            actual_team = inp.get("team_profile", "smoke")
        except Exception:
            actual_team = "smoke"

    cmd = [
        "uv", "run", "python", "scripts/run_demo.py",
        str(demo_path),
        "--backend", backend,
        "--team", actual_team,
    ]
    if skip_estimate:
        cmd.append("--skip-estimate")

    env = {**os.environ, "AI_TEAM_ENV": "dev"}

    t0 = time.monotonic()
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
            cwd=str(REPO_ROOT),
        )
        duration = time.monotonic() - t0
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - t0
        return EvalResult(demo_id, backend, actual_team, duration, error=f"Timed out after {timeout_seconds}s")
    except Exception as e:
        duration = time.monotonic() - t0
        return EvalResult(demo_id, backend, actual_team, duration, error=str(e))

    # Parse result JSON from stdout
    try:
        result = json.loads(r.stdout)
    except Exception:
        snippet = r.stderr[-800:] if r.stderr else r.stdout[-800:]
        return EvalResult(demo_id, backend, actual_team, duration, error=f"No JSON output. stderr: {snippet}")

    state = result.get("state") or {}
    run_id = state.get("project_id", "")

    demo_cfg = DEMO_CHECKS.get(demo_id, {})
    artifact_hints = demo_cfg.get("artifact_hints", [])
    content_checks = demo_cfg.get("content_checks", {})
    cost_threshold = demo_cfg.get("cost_threshold_usd", 2.00)

    checks: list[CheckResult] = [
        check_phase_complete(state),
        check_has_generated_files(state),
        check_no_errors(state),
        check_cost_under(state, cost_threshold),
    ]
    if run_id:
        checks.append(check_no_loop(state, run_id))
    checks.extend(check_artifacts_exist(state, run_id, artifact_hints))
    if run_id:
        checks.extend(check_content(state, run_id, content_checks))
    if run_id:
        checks.append(check_workspace_tests_pass(run_id, state=state))

    return EvalResult(demo_id, backend, actual_team, duration, checks=checks, run_id=run_id)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
SKIP = "\033[33m~\033[0m"


def print_report(results: list[EvalResult], *, use_json: bool) -> None:
    if use_json:
        out = []
        for r in results:
            d = {
                "demo": r.demo,
                "backend": r.backend,
                "team": r.team,
                "passed": r.passed,
                "duration_seconds": round(r.duration_seconds, 1),
                "run_id": r.run_id,
                "error": r.error,
                "checks": [asdict(c) for c in r.checks],
            }
            out.append(d)
        print(json.dumps(out, indent=2))
        return

    print()
    for r in results:
        status = PASS if r.passed else FAIL
        print(f"{status} demo {r.demo}  backend={r.backend}  team={r.team}  {r.duration_seconds:.0f}s  run={r.run_id or '—'}")
        if r.error:
            print(f"   ERROR: {r.error}")
        for c in r.checks:
            sym = PASS if c.passed else FAIL
            detail = f"  ({c.detail})" if c.detail else ""
            print(f"   {sym} {c.name}{detail}")
    print()
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    print(f"{'All passed' if passed == total else f'{passed}/{total} passed'} ({total - passed} failed)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Agentic eval harness for ai-team demos.")
    parser.add_argument("--demo", nargs="+", default=["00"], metavar="N",
                        help="Demo ID(s) to run, e.g. 00 01 (default: 00)")
    parser.add_argument("--backend", default="crewai",
                        choices=("crewai", "langgraph", "claude-agent-sdk"),
                        help="Backend (default: crewai)")
    parser.add_argument("--team", default=None,
                        help="Team profile override (default: from input.json or 'smoke')")
    parser.add_argument("--timeout", type=int, default=1200,
                        help="Per-demo timeout seconds (default: 1200). Smoke profile phases sum to 780s; set higher for full team.")
    parser.add_argument("--skip-estimate", action="store_true", default=True,
                        help="Skip cost estimate prompt (default: True)")
    parser.add_argument("--json", action="store_true", dest="use_json",
                        help="Output machine-readable JSON")
    args = parser.parse_args()

    results = []
    for demo_id in args.demo:
        demo_id = demo_id.zfill(2)
        if not args.use_json:
            print(f"Running demo {demo_id} ({args.backend}/{args.team or 'auto'})...", flush=True)
        r = run_demo_eval(
            demo_id=demo_id,
            backend=args.backend,
            team=args.team,
            skip_estimate=args.skip_estimate,
            timeout_seconds=args.timeout,
        )
        results.append(r)

    print_report(results, use_json=args.use_json)
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
