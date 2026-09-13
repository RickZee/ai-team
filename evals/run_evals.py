"""
CLI to run evals for one or all backends.

Usage:
    AI_TEAM_USE_REAL_LLM=1 uv run python -m evals.run_evals --compare
    AI_TEAM_USE_REAL_LLM=1 uv run python -m evals.run_evals --backend langgraph
    AI_TEAM_USE_REAL_LLM=1 uv run python -m evals.run_evals --all
    AI_TEAM_USE_REAL_LLM=1 uv run python -m evals.run_evals --backend crewai --scenario todo-api-beginner

--compare spawns one subprocess per backend in parallel (not one long sequential session).
Each backend log goes to /tmp/eval_<backend>.log so you can tail them independently.

Phase 4 adds Trace emission, budget enforcement, and k-run support. Trace writing is a
side effect only — the pre-existing console summary format is unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.cost import (
    BudgetLedger,
    load_pricing,
    normalize_cost,
    project_suite_cost,
)
from evals.fixtures import load_scenario
from evals.reliability import cell_summary
from evals.store import TraceExistsError, TraceStore
from evals.trace.builder import TraceBuilder

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FILE_MAP = {
    "crewai": "evals/backends/test_crewai_eval.py",
    "langgraph": "evals/backends/test_langgraph_eval.py",
    "claude-agent-sdk": "evals/backends/test_claude_sdk_eval.py",
}
_RESULTS_DIR = Path(__file__).parent / "results"

# Watchdog constants — do not change (design §6 / Phase 4 constraint).
_COMPLETE_DRAIN_TIMEOUT = 90  # kill N seconds after project_complete
_LOG_FREEZE_TIMEOUT = 120  # kill N seconds after log stops growing (deadlock)

_DEFAULT_BUDGET_USD = 5.00
# Any absolute path containing a workspace or pytest temp dir — no root allowlist
# (R17.4). A host whose temp root is outside /Users|/home|/tmp|/var|/private
# must still resolve the path written in the log.
_WORKSPACE_PATH_RE = re.compile(r"(/(?:[^\s\"']+/)*(?:workspace|pytest-\d+)(?:/[^\s\"']+)*)")


@dataclass
class RunOutcome:
    """Result of one backend subprocess (including watchdog kills)."""

    backend: str
    scenario: str
    exit_code: int
    killed: bool
    wall_time_s: float
    log_path: Path | None
    status: str  # complete | failed | killed | skipped_budget
    trace_id: str | None = None


@dataclass
class SuiteContext:
    """Explicitly threaded suite-run state (no module-level budget singleton)."""

    tier: str
    k: int
    budget: BudgetLedger
    store: TraceStore
    pricing_version: str
    yes: bool
    no_judge: bool
    verbose: bool
    outcomes: list[RunOutcome] = field(default_factory=list)
    cell_outcomes: dict[tuple[str, str], list[bool]] = field(default_factory=dict)
    skipped: list[dict[str, str]] = field(default_factory=list)


def _default_budget_usd() -> float:
    raw = os.environ.get("AI_TEAM_EVAL_BUDGET_USD")
    if raw is None or raw.strip() == "":
        return _DEFAULT_BUDGET_USD
    return float(raw)


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
        # Skip post-run self-improvement LLM report (~400s extra in eval mode)
        "AI_TEAM_SKIP_POST_RUN": "1",
        # Disable ChromaDB memory — embedding API calls block subprocess exit for 3-5 min
        "MEMORY_MEMORY_ENABLED": "false",
    }
    if no_judge:
        env["EVAL_NO_JUDGE"] = "1"
    return env


def _base_cmd(verbose: bool) -> list[str]:
    cmd = ["uv", "run", "pytest", "--tb=short", "-s", "--timeout=1200"]
    if verbose:
        cmd.append("-v")
    return cmd


def _log_path_for(backend: str) -> Path:
    return Path(f"/tmp/eval_{backend.replace('-', '_')}.log")


def _find_workspace(backend: str, log_path: Path | None) -> Path | None:
    """Best-effort workspace discovery after a subprocess finishes."""
    del backend  # discovery is log-driven; do not guess via backend (R17.4)
    candidates: list[Path] = []
    if log_path is not None and log_path.is_file():
        try:
            text = log_path.read_text(errors="replace")
        except OSError:
            text = ""
        for match in _WORKSPACE_PATH_RE.finditer(text):
            p = Path(match.group(1).rstrip(")'\","))
            if p.is_dir():
                candidates.append(p)
        # Prefer dirs that look like run workspaces (have logs/).
        for p in candidates:
            if (p / "logs").is_dir():
                return p
            # Nested project_id under the pytest temp root
            for child in sorted(p.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True):
                if child.is_dir() and (child / "logs").is_dir():
                    return child
        return candidates[0] if candidates else None
    # Do not guess the newest ./workspace/ directory (R17.4). A missing match
    # is an error; a wrong workspace silently assembled from someone else's run
    # is metric_source_drift (FM-008).
    return None


def _emit_trace(
    *,
    backend: str,
    scenario: str,
    ctx: SuiteContext,
    wall_time_s: float,
    killed: bool,
    exit_code: int,
    log_path: Path | None,
) -> str | None:
    """Build + write a Trace for a completed (or killed) backend run.

    Side effect only — failures to write are logged to stderr and ignored for
    the console summary path.
    """
    scenario_path = Path(__file__).parent / "scenarios" / f"{scenario}.json"
    scenario_data: dict[str, Any] = {}
    try:
        scenario_data = load_scenario(scenario)
    except (OSError, json.JSONDecodeError):
        scenario_data = {"id": scenario}

    workspace = _find_workspace(backend, log_path)
    if workspace is None:
        # Still emit a minimal stub so killed / hung runs are not invisible.
        stub = Path(f"/tmp/eval_trace_stub_{backend.replace('-', '_')}")
        stub.mkdir(parents=True, exist_ok=True)
        (stub / "logs").mkdir(exist_ok=True)
        workspace = stub

    if killed:
        status = "killed"
    elif exit_code == 0:
        status = "complete"
    else:
        status = "failed"

    builder = TraceBuilder(
        scenario=scenario_data,
        backend=backend,
        tier=ctx.tier,
        store=ctx.store,
        scenario_path=scenario_path if scenario_path.is_file() else None,
    )
    try:
        trace = builder.from_workspace(
            workspace,
            scenario_id=scenario,
            backend=backend,
            status=status,
            wall_time_s=wall_time_s,
            raw_result={"killed": killed, "exit_code": exit_code},
        )
        cost = normalize_cost(trace)
        trace = trace.model_copy(update={"cost": cost})
        ctx.store.write(trace)
        ctx.budget.record(cost)
        return trace.trace_id
    except TraceExistsError as exc:
        print(f"[trace] skip existing: {exc}", flush=True)
        return None
    except Exception as exc:  # noqa: BLE001 — side effect must not abort suite
        print(f"[trace] failed to emit for {backend}: {exc}", flush=True)
        return None


def _record_cell(ctx: SuiteContext, backend: str, scenario: str, success: bool) -> None:
    key = (backend, scenario)
    ctx.cell_outcomes.setdefault(key, []).append(success)


def _write_partial_report(ctx: SuiteContext, scenario: str) -> Path:
    """Write a partial suite report (including skipped_budget rows)."""
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = _RESULTS_DIR / f"suite_{scenario}_{ts}.json"
    cells = {
        f"{backend}::{scen}": cell_summary(outcomes)
        for (backend, scen), outcomes in ctx.cell_outcomes.items()
    }
    payload = {
        "scenario": scenario,
        "tier": ctx.tier,
        "k": ctx.k,
        "budget_usd": ctx.budget.ceiling_usd,
        "spent_usd": ctx.budget.spent_usd,
        "aborted": ctx.budget.aborted,
        "pricing_table_version": ctx.pricing_version,
        "outcomes": [
            {
                "backend": o.backend,
                "scenario": o.scenario,
                "exit_code": o.exit_code,
                "killed": o.killed,
                "wall_time_s": o.wall_time_s,
                "status": o.status,
                "trace_id": o.trace_id,
            }
            for o in ctx.outcomes
        ],
        "skipped_budget": ctx.skipped,
        "cells": cells,
        "generated_at": ts,
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def _print_cell_summaries(ctx: SuiteContext) -> None:
    """Print reliability cell summaries when k > 1 (additive; not the compare table)."""
    if ctx.k <= 1 or not ctx.cell_outcomes:
        return
    print("\n" + "=" * 70, flush=True)
    print("RELIABILITY CELLS (k-run)", flush=True)
    print("=" * 70, flush=True)
    for (backend, scenario), outcomes in sorted(ctx.cell_outcomes.items()):
        summary = cell_summary(outcomes)
        lo, hi = summary["wilson_ci"]  # type: ignore[misc]
        flaky = " FLAKY" if summary["flaky"] else ""
        print(
            f"  {backend:<20} {scenario:<24} "
            f"pass_rate={summary['pass_rate']:.3f} "
            f"n={summary['n']} "
            f"CI=[{lo:.3f}, {hi:.3f}] "
            f"pass@k={summary['pass_at_k']:.0f} "
            f"pass^k={summary['pass_pow_k']:.0f}{flaky}",
            flush=True,
        )
    print("=" * 70, flush=True)


def _run_single(
    backend: str,
    scenario: str,
    ctx: SuiteContext,
) -> RunOutcome:
    """Run one backend pytest file; emit a Trace afterwards."""
    if ctx.budget.aborted or ctx.budget.crossed():
        ctx.budget.mark_aborted()
        skipped = RunOutcome(
            backend=backend,
            scenario=scenario,
            exit_code=2,
            killed=False,
            wall_time_s=0.0,
            log_path=None,
            status="skipped_budget",
        )
        ctx.skipped.append({"backend": backend, "scenario": scenario, "status": "skipped_budget"})
        ctx.outcomes.append(skipped)
        return skipped

    log_path = _log_path_for(backend)
    cmd = _base_cmd(ctx.verbose) + [_FILE_MAP[backend]]
    t0 = time.time()
    # Stream to console (legacy behaviour) and tee to the per-backend log.
    with log_path.open("w") as log_f:
        proc = subprocess.Popen(
            cmd,
            env=_make_env(scenario, ctx.no_judge),
            cwd=_REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log_f.write(line)
        returncode = proc.wait()
    wall = time.time() - t0
    killed = False
    trace_id = _emit_trace(
        backend=backend,
        scenario=scenario,
        ctx=ctx,
        wall_time_s=wall,
        killed=killed,
        exit_code=returncode,
        log_path=log_path,
    )
    outcome = RunOutcome(
        backend=backend,
        scenario=scenario,
        exit_code=returncode,
        killed=killed,
        wall_time_s=wall,
        log_path=log_path,
        status="complete" if returncode == 0 else "failed",
        trace_id=trace_id,
    )
    ctx.outcomes.append(outcome)
    _record_cell(ctx, backend, scenario, returncode == 0)
    if ctx.budget.crossed():
        ctx.budget.mark_aborted()
    return outcome


def _poll_compare_procs(
    procs: dict[str, tuple[subprocess.Popen[Any], Path]],
) -> tuple[dict[str, int], dict[str, bool]]:
    """Poll parallel backend subprocesses with the legacy watchdogs.

    Watchdog behaviour is preserved byte-for-byte:
    - drain timeout 90 s after ``project_complete``
    - log-freeze timeout 120 s
    - logs at ``/tmp/eval_<backend>.log``
    """
    done: set[str] = set()
    exit_codes: dict[str, int] = {}
    killed: dict[str, bool] = {b: False for b in procs}
    complete_seen_at: dict[str, float] = {}  # when project_complete first seen
    log_last_size: dict[str, int] = {}  # log file size at last poll
    log_frozen_since: dict[str, float] = {}  # when log stopped growing
    complete_drain_timeout = _COMPLETE_DRAIN_TIMEOUT
    log_freeze_timeout = _LOG_FREEZE_TIMEOUT
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
                try:
                    log_text = log_path.read_text(errors="replace")
                    log_size = len(log_text)

                    # Watchdog 1: project_complete seen → drain timeout
                    if "project_complete" in log_text and backend not in complete_seen_at:
                        complete_seen_at[backend] = time.time()
                    if backend in complete_seen_at:
                        drain_elapsed = time.time() - complete_seen_at[backend]
                        if drain_elapsed > complete_drain_timeout:
                            print(
                                f"[compare] {backend} watchdog: project_complete {drain_elapsed:.0f}s ago, killing",
                                flush=True,
                            )
                            proc.kill()
                            done.add(backend)
                            killed[backend] = True
                            log_text = log_path.read_text(errors="replace")
                            eval_passed = " passed in " in log_text and "=====" in log_text
                            exit_codes[backend] = 0 if eval_passed else 1
                            status = (
                                "PASSED" if eval_passed else "FAILED (hang after project_complete)"
                            )
                            print(
                                f"[compare] {backend} {status} after {elapsed:.0f}s",
                                flush=True,
                            )
                            continue

                    # Watchdog 2: log frozen → deadlock kill (score FAILED — run incomplete)
                    prev_size = log_last_size.get(backend, -1)
                    if log_size != prev_size:
                        log_last_size[backend] = log_size
                        log_frozen_since.pop(backend, None)
                    else:
                        frozen_since = log_frozen_since.setdefault(backend, time.time())
                        frozen_elapsed = time.time() - frozen_since
                        if frozen_elapsed > log_freeze_timeout:
                            print(
                                f"[compare] {backend} watchdog: log frozen {frozen_elapsed:.0f}s, killing (deadlock)",
                                flush=True,
                            )
                            proc.kill()
                            done.add(backend)
                            killed[backend] = True
                            exit_codes[backend] = 1  # score FAILED — flow never completed
                            print(
                                f"[compare] {backend} FAILED (deadlock) after {elapsed:.0f}s",
                                flush=True,
                            )
                            continue
                except Exception:
                    pass
                # Show last meaningful log line as heartbeat
                try:
                    lines = log_path.read_text(errors="replace").splitlines()
                    last = next(
                        (line for line in reversed(lines) if line.strip() and "│" not in line),
                        "...",
                    )
                    print(
                        f"[compare] {backend} running ({elapsed:.0f}s) — {last[-80:]}", flush=True
                    )
                except Exception:
                    pass
    return exit_codes, killed


def _run_compare_once(scenario: str, ctx: SuiteContext) -> dict[str, int]:
    """Spawn one subprocess per backend in parallel; stream each to /tmp/eval_<backend>.log."""
    env = _make_env(scenario, ctx.no_judge)
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    backends_to_run = [b for b in _FILE_MAP if not (ctx.budget.aborted or ctx.budget.crossed())]
    for backend in _FILE_MAP:
        if backend not in backends_to_run:
            ctx.skipped.append(
                {"backend": backend, "scenario": scenario, "status": "skipped_budget"}
            )
            ctx.outcomes.append(
                RunOutcome(
                    backend=backend,
                    scenario=scenario,
                    exit_code=2,
                    killed=False,
                    wall_time_s=0.0,
                    log_path=None,
                    status="skipped_budget",
                )
            )

    if not backends_to_run:
        return {}

    procs: dict[str, tuple[subprocess.Popen[Any], Path]] = {}
    started_at = time.time()
    for backend in backends_to_run:
        test_file = _FILE_MAP[backend]
        log_path = _log_path_for(backend)
        cmd = _base_cmd(ctx.verbose) + [test_file]
        print(f"[compare] spawning {backend} → {log_path}", flush=True)
        f = log_path.open("w")
        proc = subprocess.Popen(cmd, env=env, cwd=_REPO_ROOT, stdout=f, stderr=subprocess.STDOUT)
        procs[backend] = (proc, log_path)

    print("[compare] all 3 backends running in parallel", flush=True)
    print("[compare] tail logs:", flush=True)
    for _, log_path in procs.values():
        print(f"  tail -f {log_path}", flush=True)

    exit_codes, killed_map = _poll_compare_procs(procs)
    wall = time.time() - started_at

    for backend, (_proc, log_path) in procs.items():
        rc = exit_codes.get(backend, 1)
        was_killed = killed_map.get(backend, False)
        trace_id = _emit_trace(
            backend=backend,
            scenario=scenario,
            ctx=ctx,
            wall_time_s=wall,
            killed=was_killed,
            exit_code=rc,
            log_path=log_path,
        )
        status = "killed" if was_killed else ("complete" if rc == 0 else "failed")
        ctx.outcomes.append(
            RunOutcome(
                backend=backend,
                scenario=scenario,
                exit_code=rc,
                killed=was_killed,
                wall_time_s=wall,
                log_path=log_path,
                status=status,
                trace_id=trace_id,
            )
        )
        _record_cell(ctx, backend, scenario, rc == 0 and not was_killed)
        if ctx.budget.crossed():
            ctx.budget.mark_aborted()

    return exit_codes


def _run_compare(scenario: str, ctx: SuiteContext) -> int:
    """Run compare mode ``k`` times; emit traces; enforce budget."""
    last_codes: dict[str, int] = {}
    for attempt in range(ctx.k):
        if ctx.budget.aborted or ctx.budget.crossed():
            for backend in _FILE_MAP:
                ctx.skipped.append(
                    {
                        "backend": backend,
                        "scenario": scenario,
                        "status": "skipped_budget",
                        "attempt": str(attempt),
                    }
                )
            break
        if ctx.k > 1:
            print(f"[compare] k-run attempt {attempt + 1}/{ctx.k}", flush=True)
        last_codes = _run_compare_once(scenario, ctx)

    _print_summary(last_codes, scenario)
    _print_cell_summaries(ctx)
    report = _write_partial_report(ctx, scenario)
    if ctx.budget.aborted:
        print(f"[budget] aborted; partial report: {report}", flush=True)
        return 2
    return 0 if last_codes and all(rc == 0 for rc in last_codes.values()) else 1


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


def _confirm_budget_projection(
    projection: float,
    ceiling: float,
    *,
    yes: bool,
) -> bool:
    """Require ``--yes`` (or CI) when projection exceeds 50% of the ceiling (R10.6)."""
    threshold = 0.5 * ceiling
    print(
        f"[budget] projected spend ${projection:.4f} "
        f"(ceiling ${ceiling:.4f}, 50% threshold ${threshold:.4f})",
        flush=True,
    )
    if projection <= threshold:
        return True
    if yes or os.environ.get("CI"):
        print("[budget] proceeding (--yes or CI set)", flush=True)
        return True
    print(
        "[budget] projection exceeds 50% of ceiling; re-run with --yes to proceed",
        flush=True,
    )
    return False


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="AI-Team eval runner")
    parser.add_argument(
        "--backend", choices=list(_FILE_MAP), help="Run evals for a single backend."
    )
    parser.add_argument(
        "--scenario", default="smoke-test", help="Scenario ID (default: smoke-test)."
    )
    parser.add_argument("--all", action="store_true", help="Run all backend evals sequentially.")
    parser.add_argument(
        "--compare", action="store_true", help="Cross-backend comparison (parallel)."
    )
    parser.add_argument("--no-judge", action="store_true", help="Skip LLM judge.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Pass -v to pytest.")
    parser.add_argument(
        "--tier",
        choices=["A", "B", "C"],
        default="B",
        help="Eval tier (default: B). Live runs are B/C; A is fixture replay.",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=1,
        help="Runs per backend × scenario cell (default: 1).",
    )
    parser.add_argument(
        "--budget-usd",
        type=float,
        default=None,
        help="Suite spend ceiling (default: AI_TEAM_EVAL_BUDGET_USD or 5.00).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm live run when projected spend exceeds 50%% of ceiling.",
    )
    args = parser.parse_args(argv)

    if args.k < 1:
        parser.error("--k must be >= 1")

    ceiling = args.budget_usd if args.budget_usd is not None else _default_budget_usd()
    pricing = load_pricing()
    store = TraceStore()
    ctx = SuiteContext(
        tier=args.tier,
        k=args.k,
        budget=BudgetLedger(ceiling_usd=ceiling),
        store=store,
        pricing_version=pricing.version,
        yes=args.yes,
        no_judge=args.no_judge,
        verbose=args.verbose,
    )

    backends = list(_FILE_MAP)
    if args.backend:
        backends = [args.backend]
    projection = project_suite_cost(
        scenario_ids=[args.scenario],
        backends=backends if (args.compare or args.all or args.backend) else list(_FILE_MAP),
        k=args.k,
        pricing=pricing,
        store=store,
    )

    live_tier = args.tier in ("B", "C")
    if (
        live_tier
        and (args.compare or args.all or args.backend)
        and not _confirm_budget_projection(projection, ceiling, yes=args.yes)
    ):
        sys.exit(2)

    if args.compare:
        rc = _run_compare(args.scenario, ctx)
    elif args.all:
        codes: list[int] = []
        for attempt in range(ctx.k):
            if ctx.budget.aborted:
                break
            if ctx.k > 1:
                print(f"[all] k-run attempt {attempt + 1}/{ctx.k}", flush=True)
            for backend in _FILE_MAP:
                outcome = _run_single(backend, args.scenario, ctx)
                if outcome.status != "skipped_budget":
                    codes.append(outcome.exit_code)
                if ctx.budget.aborted:
                    break
        _print_cell_summaries(ctx)
        report = _write_partial_report(ctx, args.scenario)
        if ctx.budget.aborted:
            print(f"[budget] aborted; partial report: {report}", flush=True)
            rc = 2
        else:
            rc = 0 if codes and all(c == 0 for c in codes) else 1
    elif args.backend:
        codes = []
        for attempt in range(ctx.k):
            if ctx.budget.aborted:
                break
            if ctx.k > 1:
                print(
                    f"[backend] {args.backend} k-run attempt {attempt + 1}/{ctx.k}",
                    flush=True,
                )
            outcome = _run_single(args.backend, args.scenario, ctx)
            if outcome.status != "skipped_budget":
                codes.append(outcome.exit_code)
        _print_cell_summaries(ctx)
        report = _write_partial_report(ctx, args.scenario)
        if ctx.budget.aborted:
            print(f"[budget] aborted; partial report: {report}", flush=True)
            rc = 2
        else:
            rc = 0 if codes and all(c == 0 for c in codes) else 1
    else:
        parser.print_help()
        sys.exit(0)

    sys.exit(rc)


if __name__ == "__main__":
    main()
