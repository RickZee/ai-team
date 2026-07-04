"""Run the smoke demo N times per backend and emit a variance table.

Single-run comparisons at smoke scale are anecdotes — same-config variance
observed on 2026-07-03 was 6m50s -> 10m41s (CrewAI) and clean-complete ->
HITL-escalation (LangGraph) within one hour. This script produces the n>=5
evidence COMPARISON_RESULTS.md tables should be built from.

Usage:
    uv run python scripts/run_smoke_batch.py --n 5
    uv run python scripts/run_smoke_batch.py --n 3 --backends langgraph,claude-agent-sdk

Each run goes through scripts/run_demo.py (which already applies the CrewAI
hard-kill wrapper). Wall-clock is measured here; tests and spend are read
back from the run's output bundle (state.json / logs/costs.jsonl). Results
land in output/smoke_batch_<timestamp>.json plus a markdown table on stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEMO = "demos/00_smoke_test"
RUNS_DIR = REPO / "output" / "runs"

# Generous per-run ceilings from measured baselines (see memory/journal):
# claude-sdk ~3m, crewai 7-11m, langgraph 9-23m (incl. HITL wait, which the
# CLI path answers via hitl_default_answer, so no operator stall here).
TIMEOUTS = {"claude-agent-sdk": 900, "crewai": 1500, "langgraph": 1800}


def _existing_run_ids() -> set[str]:
    if not RUNS_DIR.is_dir():
        return set()
    return {p.name for p in RUNS_DIR.iterdir() if p.is_dir()}


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _tests_from_state(state: dict | None) -> tuple[int | None, int | None, bool | None]:
    """Normalize the THREE test_results schemas seen in the wild.

    CrewAI writes flat counts {'total','passed','failed',...}; LangGraph
    writes {'passed': bool, 'tests': {'ok': bool, ...}}; the Claude SDK's
    generated test_results.json nests counts under 'summary'
    ({'summary': {'total','passed','failed'}, 'tests': [...]}). See
    COMPARISON_RESULTS 2026-07-03 finding #3 — this normalization gap is
    itself one of the findings.
    """
    if not state:
        return None, None, None
    tr = (state.get("state") or state).get("test_results")
    if not isinstance(tr, dict):
        return None, None, None
    if isinstance(tr.get("summary"), dict):
        tr = tr["summary"]
    if isinstance(tr.get("passed"), bool):
        ok = bool(tr.get("passed"))
        return None, None, ok
    passed = tr.get("passed")
    failed = tr.get("failed")
    ok = failed == 0 and (passed or 0) > 0
    return passed, failed, ok


def _spend_from_costs(costs_path: Path) -> float | None:
    if not costs_path.exists():
        return None
    spent = None
    for line in costs_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "spent_usd" in row:
            spent = row["spent_usd"]
    return spent


def run_once(backend: str, index: int) -> dict:
    before = _existing_run_ids()
    cmd = [
        sys.executable,
        "scripts/run_demo.py",
        DEMO,
        "--backend",
        backend,
        "--team",
        "smoke",
        "--skip-estimate",
        "--timeout",
        str(TIMEOUTS[backend]),
    ]
    # Guardrail tools (ruff, pytest) are invoked as bare commands by the
    # flows; a detached shell may not have .venv/bin on PATH — langgraph's
    # lint gate then fails with "Command not found: ruff" (seen in the first
    # shakedown) even though the generated code was green.
    env = {**os.environ, "PATH": f"{REPO / '.venv' / 'bin'}:{os.environ.get('PATH', '')}"}
    t0 = time.monotonic()
    proc = subprocess.run(
        cmd,
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=TIMEOUTS[backend] + 120,
    )
    wall = round(time.monotonic() - t0, 1)

    new_ids = sorted(_existing_run_ids() - before)
    run_id = new_ids[-1] if new_ids else None
    state = _read_json(RUNS_DIR / run_id / "state.json") if run_id else None
    run_meta = _read_json(RUNS_DIR / run_id / "run.json") if run_id else None
    passed, failed, ok = _tests_from_state(state)
    spend = _spend_from_costs(RUNS_DIR / run_id / "logs" / "costs.jsonl") if run_id else None

    return {
        "backend": backend,
        "index": index,
        "run_id": run_id,
        "exit_code": proc.returncode,
        "wall_seconds": wall,
        "tests_passed": passed,
        "tests_failed": failed,
        "tests_ok": ok,
        "spent_usd": spend,
        "final_status": ((run_meta or {}).get("extra") or {}).get("final_status"),
        "stderr_tail": proc.stderr[-500:] if proc.returncode != 0 else None,
    }


def variance_row(backend: str, rows: list[dict]) -> str:
    walls = [r["wall_seconds"] for r in rows if r["wall_seconds"] is not None]
    green = sum(1 for r in rows if r["tests_ok"])
    spends = [r["spent_usd"] for r in rows if r["spent_usd"] is not None]

    def fmt(sec: float) -> str:
        return f"{int(sec // 60)}m{int(sec % 60):02d}s"

    wall_s = (
        f"{fmt(min(walls))} / {fmt(statistics.median(walls))} / {fmt(max(walls))}" if walls else "—"
    )
    spend_s = f"${min(spends):.3f}–${max(spends):.3f}" if spends else "—"
    return f"| {backend} | {green}/{len(rows)} | {wall_s} | {spend_s} |"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=5, help="Runs per backend (default 5).")
    ap.add_argument(
        "--backends",
        default="claude-agent-sdk,langgraph,crewai",
        help="Comma-separated backend list.",
    )
    args = ap.parse_args()
    backends = [b.strip() for b in args.backends.split(",") if b.strip()]

    results: list[dict] = []
    for backend in backends:
        for i in range(1, args.n + 1):
            print(f"[{backend} {i}/{args.n}] running…", flush=True)
            try:
                row = run_once(backend, i)
            except subprocess.TimeoutExpired:
                row = {
                    "backend": backend,
                    "index": i,
                    "run_id": None,
                    "exit_code": None,
                    "wall_seconds": None,
                    "tests_ok": False,
                    "error": "outer timeout",
                }
            results.append(row)
            print(
                f"[{backend} {i}/{args.n}] exit={row.get('exit_code')} "
                f"wall={row.get('wall_seconds')}s tests_ok={row.get('tests_ok')}",
                flush=True,
            )

    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out_path = REPO / "output" / f"smoke_batch_{stamp}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("\n| Backend | Green | Wall min/median/max | Spend range |")
    print("|---|---|---|---|")
    for backend in backends:
        rows = [r for r in results if r["backend"] == backend]
        print(variance_row(backend, rows))
    print(f"\nRaw results: {out_path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
