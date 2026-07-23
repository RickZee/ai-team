"""Run a demo N times per backend and emit a variance table with confidence intervals.

Single-run comparisons are anecdotes — same-config variance observed on 2026-07-03
was 6m50s -> 10m41s (CrewAI) and clean-complete -> HITL-escalation (LangGraph)
within one hour. This script produces the n>=5 evidence that comparison tables
should be built from, and refuses to hand you a ranking the numbers can't support.

Three things it forces you to be honest about:
    * --team smoke-claude pins one model across backends (framework comparison);
      the default mixed-model profile is flagged as confounded.
    * --demo demos/02_todo_app runs a real build; the default smoke demo is a
      canary and is flagged as not-a-verdict.
    * verdicts print only when the Wilson intervals on green-rate do not overlap
      (see scripts/batch_stats.py); otherwise it says "no significant difference".

Usage:
    uv run python scripts/run_smoke_batch.py --n 5                       # canary, confounded
    uv run python scripts/run_smoke_batch.py --n 5 --team smoke-claude   # model-controlled
    uv run python scripts/run_smoke_batch.py --n 5 --demo demos/02_todo_app --team smoke-claude
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from batch_stats import (  # noqa: E402
    bootstrap_median_ci,
    verdict_is_supported,
    wilson_interval,
)

REPO = Path(__file__).resolve().parent.parent
DEMO = "demos/00_smoke_test"
RUNS_DIR = REPO / "output" / "runs"

# Generous per-run ceilings from measured baselines (see memory/journal):
# claude-sdk ~3m, crewai 7-11m, langgraph 9-23m (incl. HITL wait, which the
# CLI path answers via hitl_default_answer, so no operator stall here).
TIMEOUTS = {"claude-agent-sdk": 900, "crewai": 1500, "langgraph": 1800}

# The smoke demo (add(a,b) + pytest) is a *canary*, not a benchmark: passing it
# says the pipeline is wired, not that a backend can build software. Framework
# verdicts must come from a harder tier. Multiplier scales the per-run ceilings
# for heavier demos (full build + deploy).
TIER_TIMEOUT_MULTIPLIER = {"demos/00_smoke_test": 1.0, "demos/02_todo_app": 3.0}


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


def run_once(backend: str, index: int, team: str = "smoke", demo: str = DEMO) -> dict:
    before = _existing_run_ids()
    timeout = int(TIMEOUTS[backend] * TIER_TIMEOUT_MULTIPLIER.get(demo, 1.0))
    cmd = [
        sys.executable,
        "scripts/run_demo.py",
        demo,
        "--backend",
        backend,
        "--team",
        team,
        "--skip-estimate",
        "--timeout",
        str(timeout),
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
        timeout=timeout + 120,
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


def _fmt_seconds(sec: float) -> str:
    return f"{int(sec // 60)}m{int(sec % 60):02d}s"


def backend_stats(rows: list[dict]) -> dict:
    """Green-rate and wall-clock summaries, each with a 95% interval."""
    walls = [r["wall_seconds"] for r in rows if r["wall_seconds"] is not None]
    green = sum(1 for r in rows if r["tests_ok"])
    spends = [r["spent_usd"] for r in rows if r["spent_usd"] is not None]
    return {
        "n": len(rows),
        "green": green,
        "green_ci": wilson_interval(green, len(rows)),
        "walls": walls,
        "wall_ci": bootstrap_median_ci(walls) if walls else None,
        "spends": spends,
    }


def variance_row(backend: str, rows: list[dict]) -> str:
    st = backend_stats(rows)
    walls, wall_ci = st["walls"], st["wall_ci"]
    wall_s = (
        f"{_fmt_seconds(min(walls))} / {_fmt_seconds(statistics.median(walls))} / "
        f"{_fmt_seconds(max(walls))}"
        if walls
        else "—"
    )
    wall_ci_s = (
        f"{_fmt_seconds(wall_ci.low)}–{_fmt_seconds(wall_ci.high)}" if wall_ci is not None else "—"
    )
    spends = st["spends"]
    spend_s = f"${min(spends):.3f}–${max(spends):.3f}" if spends else "—"
    return (
        f"| {backend} | {st['green']}/{st['n']} | {st['green_ci'].as_pct()} | "
        f"{wall_s} | {wall_ci_s} | {spend_s} |"
    )


def verdict_section(backends: list[str], results: list[dict]) -> list[str]:
    """Pairwise green-rate comparisons, stating only what the intervals support."""
    lines = ["", "### Pairwise verdicts (95% Wilson intervals on green-rate)", ""]
    stats = {b: backend_stats([r for r in results if r["backend"] == b]) for b in backends}
    any_supported = False
    for i, a in enumerate(backends):
        for b in backends[i + 1 :]:
            ia, ib = stats[a]["green_ci"], stats[b]["green_ci"]
            if verdict_is_supported(ia, ib):
                any_supported = True
                better, worse = (a, b) if ia.point > ib.point else (b, a)
                lines.append(
                    f"- **{better} > {worse}** — intervals do not overlap "
                    f"({stats[better]['green_ci'].as_pct()} vs {stats[worse]['green_ci'].as_pct()})."
                )
            else:
                lines.append(
                    f"- {a} vs {b}: **no significant difference at this n** — "
                    f"{ia.as_pct()} overlaps {ib.as_pct()}."
                )
    if not any_supported:
        n_now = max((stats[b]["n"] for b in backends), default=0)
        lines += [
            "",
            f"> No pairwise verdict is statistically supported at n={n_now}. "
            "Report these as observations, not rankings.",
        ]
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=5, help="Runs per backend (default 5).")
    ap.add_argument(
        "--backends",
        default="claude-agent-sdk,langgraph,crewai",
        help="Comma-separated backend list.",
    )
    ap.add_argument(
        "--team",
        default="smoke",
        help=(
            "Team profile. Default 'smoke' runs each backend's own tier model "
            "(mixed-model: results confound framework with model). Use "
            "'smoke-claude' to pin every role to one Claude model — the "
            "same-model control required for framework-vs-framework verdicts."
        ),
    )
    ap.add_argument(
        "--demo",
        default=DEMO,
        help=(
            f"Demo to run (default {DEMO}). The smoke demo is a CANARY — passing it "
            "proves the pipeline is wired, not that a backend can build software. "
            "Use demos/02_todo_app (a real full-stack build) for verdicts you intend "
            "to generalize."
        ),
    )
    args = ap.parse_args()
    backends = [b.strip() for b in args.backends.split(",") if b.strip()]

    is_canary = args.demo == "demos/00_smoke_test"
    if is_canary:
        print(
            "NOTE: demos/00_smoke_test is a canary (add(a,b) + one pytest). Green here "
            "means 'pipeline wired', not 'backend can build software'. Do not generalize "
            "a framework verdict from it — use --demo demos/02_todo_app.\n",
            flush=True,
        )

    same_model = args.team.endswith("-claude") or args.team == "full-claude"
    if not same_model:
        print(
            "WARNING: team profile "
            f"'{args.team}' is mixed-model. Any framework-vs-framework verdict "
            "from this batch is confounded with model choice. Use "
            "--team smoke-claude for a model-controlled comparison.\n",
            flush=True,
        )

    results: list[dict] = []
    for backend in backends:
        for i in range(1, args.n + 1):
            print(f"[{backend} {i}/{args.n}] running…", flush=True)
            try:
                row = run_once(backend, i, team=args.team, demo=args.demo)
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

    now = datetime.now(UTC)
    stamp = now.strftime("%Y%m%d_%H%M%S")
    out_path = REPO / "output" / f"smoke_batch_{stamp}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Wrap results with provenance so a table can never be read without knowing
    # whether it was model-controlled and when it was produced.
    bundle = {
        "generated_at_utc": now.isoformat(),
        "team": args.team,
        "same_model": same_model,
        "demo": args.demo,
        "is_canary": is_canary,
        "n_per_backend": args.n,
        "backends": backends,
        "runs": results,
    }
    out_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    kind = "SAME-MODEL (framework comparison valid)" if same_model else "MIXED-MODEL (confounded)"
    tier = "CANARY demo (not a verdict)" if is_canary else f"demo={args.demo}"
    print(f"\n**{kind}** — {tier}, team={args.team}, n={args.n}, {now.date().isoformat()}")
    print("\n| Backend | Green | Green 95% CI | Wall min/median/max | Median 95% CI | Spend range |")
    print("|---|---|---|---|---|---|")
    for backend in backends:
        rows = [r for r in results if r["backend"] == backend]
        print(variance_row(backend, rows))
    for line in verdict_section(backends, results):
        print(line)
    if not same_model:
        print(
            "\n> Mixed-model batch: the verdicts above compare framework+model bundles, "
            "not frameworks. Re-run with --team smoke-claude before ranking frameworks."
        )
    print(f"\nRaw results: {out_path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
