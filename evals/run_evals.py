"""
CLI to run evals for one or all backends.

Usage:
    AI_TEAM_USE_REAL_LLM=1 uv run python -m evals.run_evals --compare
    AI_TEAM_USE_REAL_LLM=1 uv run python -m evals.run_evals --backend langgraph
    AI_TEAM_USE_REAL_LLM=1 uv run python -m evals.run_evals --all
    AI_TEAM_USE_REAL_LLM=1 uv run python -m evals.run_evals --backend crewai --scenario todo-api-beginner

--compare spawns one subprocess per backend in parallel (not one long sequential session).
Each backend log goes to /tmp/eval_<backend>.log so you can tail them independently.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FILE_MAP = {
    "crewai": "evals/backends/test_crewai_eval.py",
    "langgraph": "evals/backends/test_langgraph_eval.py",
    "claude-agent-sdk": "evals/backends/test_claude_sdk_eval.py",
}
_RESULTS_DIR = Path(__file__).parent / "results"


def _load_dotenv() -> dict[str, str]:
    dotenv = _REPO_ROOT / ".env"
    out: dict[str, str] = {}
    if dotenv.exists():
        for line in dotenv.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                out[k.strip()] = v.strip()
    return out


def _make_env(scenario: str, no_judge: bool) -> dict[str, str]:
    dotenv = _load_dotenv()
    # Shell env wins, but skip empty-string values so they don't shadow .env
    shell = {k: v for k, v in os.environ.items() if v}
    env = {
        **dotenv,
        **shell,
        "AI_TEAM_USE_REAL_LLM": "1",
        "EVAL_SCENARIO": scenario,
        # Disable crewai rich/live display — it deadlocks when run in subprocess
        "CREWAI_DISABLE_TELEMETRY": "1",
        "NO_COLOR": "1",
        "TERM": "dumb",
    }
    if no_judge:
        env["EVAL_NO_JUDGE"] = "1"
    return env


def _base_cmd(verbose: bool) -> list[str]:
    cmd = ["uv", "run", "pytest", "--tb=short", "-s", "--timeout=1200"]
    if verbose:
        cmd.append("-v")
    return cmd


def _run_single(backend: str, scenario: str, no_judge: bool, verbose: bool) -> int:
    cmd = _base_cmd(verbose) + [_FILE_MAP[backend]]
    result = subprocess.run(cmd, env=_make_env(scenario, no_judge), cwd=_REPO_ROOT)
    return result.returncode


def _run_compare(scenario: str, no_judge: bool, verbose: bool) -> int:
    """Spawn one subprocess per backend in parallel; stream each to /tmp/eval_<backend>.log."""
    env = _make_env(scenario, no_judge)
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    procs: dict[str, tuple[subprocess.Popen, Path]] = {}
    for backend, test_file in _FILE_MAP.items():
        log_path = Path(f"/tmp/eval_{backend.replace('-', '_')}.log")
        cmd = _base_cmd(verbose) + [test_file]
        print(f"[compare] spawning {backend} → {log_path}", flush=True)
        f = log_path.open("w")
        proc = subprocess.Popen(cmd, env=env, cwd=_REPO_ROOT, stdout=f, stderr=subprocess.STDOUT)
        procs[backend] = (proc, log_path)

    print(f"[compare] all 3 backends running in parallel", flush=True)
    print(f"[compare] tail logs:", flush=True)
    for backend, (_, log_path) in procs.items():
        print(f"  tail -f {log_path}", flush=True)

    # Poll until all done, print status updates
    done: set[str] = set()
    exit_codes: dict[str, int] = {}
    t0 = time.time()
    while len(done) < len(procs):
        time.sleep(10)
        elapsed = time.time() - t0
        for backend, (proc, log_path) in procs.items():
            if backend in done:
                continue
            rc = proc.poll()
            if rc is not None:
                done.add(backend)
                exit_codes[backend] = rc
                status = "PASSED" if rc == 0 else f"FAILED (rc={rc})"
                print(f"[compare] {backend} {status} after {elapsed:.0f}s", flush=True)
            else:
                # Show last meaningful log line as heartbeat
                try:
                    lines = log_path.read_text(errors="replace").splitlines()
                    last = next((l for l in reversed(lines) if l.strip() and "│" not in l), "...")
                    print(f"[compare] {backend} running ({elapsed:.0f}s) — {last[-80:]}", flush=True)
                except Exception:
                    pass

    # Print comparison table from result files
    _print_summary(exit_codes, scenario)
    return 0 if all(rc == 0 for rc in exit_codes.values()) else 1


def _print_summary(exit_codes: dict[str, int], scenario: str) -> None:
    print("\n" + "=" * 70, flush=True)
    print("COMPARISON SUMMARY", flush=True)
    print("=" * 70, flush=True)
    for backend, rc in exit_codes.items():
        status = "✓ PASSED" if rc == 0 else f"✗ FAILED (rc={rc})"
        log = f"/tmp/eval_{backend.replace('-', '_')}.log"
        print(f"  {backend:<20} {status}   log: {log}", flush=True)

    # Load latest comparison JSON if exists
    reports = sorted(_RESULTS_DIR.glob(f"comparison_{scenario}_*.json"), reverse=True)
    if reports:
        try:
            data = json.loads(reports[0].read_text())
            print(f"\nDetailed report: {reports[0]}", flush=True)
            cols = ["backend", "success", "goal_alignment", "wall_time_s", "cost_usd"]
            header = "  ".join(f"{c:<20}" for c in cols)
            print(header, flush=True)
            print("-" * len(header), flush=True)
            for row in data:
                m = row.get("metrics") or {}
                vals = [
                    str(row.get("backend", ""))[:20],
                    str(row.get("success", ""))[:20],
                    f"{m.get('goal_alignment', 'n/a')}"[:20],
                    f"{row.get('wall_time_s') or 'n/a'}"[:20],
                    f"{row.get('cost_usd') or 'n/a'}"[:20],
                ]
                print("  ".join(f"{v:<20}" for v in vals), flush=True)
        except Exception:
            pass
    print("=" * 70, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-Team eval runner")
    parser.add_argument("--backend", choices=list(_FILE_MAP), help="Run evals for a single backend.")
    parser.add_argument("--scenario", default="smoke-test", help="Scenario ID (default: smoke-test).")
    parser.add_argument("--all", action="store_true", help="Run all backend evals sequentially.")
    parser.add_argument("--compare", action="store_true", help="Cross-backend comparison (parallel).")
    parser.add_argument("--no-judge", action="store_true", help="Skip LLM judge.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Pass -v to pytest.")
    args = parser.parse_args()

    if args.compare:
        rc = _run_compare(args.scenario, args.no_judge, args.verbose)
    elif args.all:
        cmd = _base_cmd(args.verbose) + ["evals/backends/"]
        rc = subprocess.run(cmd, env=_make_env(args.scenario, args.no_judge), cwd=_REPO_ROOT).returncode
    elif args.backend:
        rc = _run_single(args.backend, args.scenario, args.no_judge, args.verbose)
    else:
        parser.print_help()
        sys.exit(0)

    sys.exit(rc)


if __name__ == "__main__":
    main()
