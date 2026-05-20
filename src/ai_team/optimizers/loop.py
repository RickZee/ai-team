"""
KarpathyLoop — autonomous edit → run → measure → keep/revert loop.

Inspired by Andrej Karpathy's demo of running ~700 overnight experiments to
achieve 11%+ speedups on a nanochat training setup for ~$300 in API cost.

Usage (from CLI):
    ai-team optimize ./workspace/todo-api --metric metric.yaml --budget 4.00

Usage (from Python):
    from ai_team.optimizers.loop import KarpathyLoop, LoopConfig
    from ai_team.optimizers.metric import MetricConfig

    result = KarpathyLoop(LoopConfig(
        workspace=Path("./workspace/todo-api"),
        metric=MetricConfig(
            name="test_pass_rate",
            evaluation_command="python -m pytest tests/ --tb=no -q 2>&1 | tail -1",
        ),
        max_experiments=20,
        budget_usd=2.0,
    )).run()
"""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass, field
from pathlib import Path

import structlog
from ai_team.backends.registry import get_backend
from ai_team.core.team_profile import load_team_profile
from ai_team.optimizers.experiment_log import (
    ExperimentRecord,
    append_experiment,
    summarise_experiments,
)
from ai_team.optimizers.git_reset import git_reset_hard
from ai_team.optimizers.metric import MetricConfig, extract_metric
from ai_team.rag.ingestion import TextChunk
from ai_team.rag.pipeline import get_rag_pipeline
from ai_team.tools.git_tools import git_add, git_branch, git_commit, git_diff

logger = structlog.get_logger(__name__)


@dataclass
class LoopConfig:
    workspace: Path
    metric: MetricConfig

    backend_name: str = "claude-agent-sdk"
    team: str = "research-optimizer"

    max_experiments: int = 50
    budget_usd: float = 10.0
    timeout_per_experiment: int = 300
    # Minimum improvement (%) over running best to keep a commit
    min_improvement_pct: float = 0.5
    # Per-experiment caps passed to the backend
    max_budget_per_experiment_usd: float = 1.0
    max_turns_per_experiment: int = 40

    # Optional guidance injected into each iteration's prompt
    strategy: str = ""
    # Git branch that receives winning commits
    branch: str = "optimize/karpathy-loop"
    # Files the optimizer agent is allowed to edit (informational; enforced via prompt)
    editable_files: list[str] = field(default_factory=lambda: ["src/"])


@dataclass
class LoopResult:
    experiments_run: int
    baseline_metric: float | None
    best_metric: float | None
    improvement_pct: float | None
    total_cost_usd: float
    winning_commits: list[str]
    experiment_log_path: Path
    summary: dict


class KarpathyLoop:
    """
    Drives the tight optimization loop.

    Each iteration:
    1. Snapshots the workspace.
    2. Asks the backend agent to propose and apply ONE focused edit.
    3. Measures the target metric.
    4. Commits if improved (above min_improvement_pct), restores otherwise.
    5. Ingests an experiment lesson into RAG for the next iteration.
    """

    def __init__(self, config: LoopConfig) -> None:
        self.cfg = config
        self.backend = get_backend(config.backend_name)
        self.profile = load_team_profile(config.team)
        self._cost_spent: float = 0.0
        self._baseline: float | None = None
        self._best: float | None = None
        self._winning_commits: list[str] = []

    # ── public ────────────────────────────────────────────────────────────

    def run(self) -> LoopResult:
        ws = self.cfg.workspace.resolve()
        logger.info(
            "karpathy_loop.start",
            workspace=str(ws),
            metric=self.cfg.metric.name,
            budget=self.cfg.budget_usd,
            max_experiments=self.cfg.max_experiments,
        )

        self._baseline = extract_metric(self.cfg.metric, ws)
        self._best = self._baseline
        logger.info("karpathy_loop.baseline", value=self._baseline)

        # Create the experiment branch (git_branch enforces type/name pattern)
        try:
            git_branch(str(ws), self.cfg.branch)
        except Exception as exc:
            logger.warning("karpathy_loop.branch_failed", error=str(exc))
            # Non-fatal — loop still works without a dedicated branch

        n = 0
        for n in range(1, self.cfg.max_experiments + 1):
            if self._cost_spent >= self.cfg.budget_usd:
                logger.info("karpathy_loop.budget_exhausted", spent=self._cost_spent)
                break

            logger.info("karpathy_loop.iteration", n=n, best=self._best, spent=self._cost_spent)
            self._run_iteration(n, ws)

        experiments = self._load_experiments(ws)
        summary = summarise_experiments(experiments)
        logger.info("karpathy_loop.done", **summary)

        return LoopResult(
            experiments_run=n,
            baseline_metric=self._baseline,
            best_metric=self._best,
            improvement_pct=self._calc_improvement(),
            total_cost_usd=self._cost_spent,
            winning_commits=self._winning_commits,
            experiment_log_path=ws / "logs" / "experiments.jsonl",
            summary=summary,
        )

    # ── internals ─────────────────────────────────────────────────────────

    def _run_iteration(self, n: int, ws: Path) -> None:
        from ai_team.backends.claude_agent_sdk_backend.workspace_snapshots import (
            restore_workspace_subtrees,
            snapshot_workspace_subtrees,
        )

        tag = f"iter_{n:03d}"
        snapshot_workspace_subtrees(ws, tag=tag)
        t0 = time.monotonic()

        # --- agent edits ---
        description = self._build_prompt(n)
        iter_cost = 0.0
        run_error: str | None = None
        try:
            result = self.backend.run(
                description,
                self.profile,
                workspace_dir=str(ws),
                max_budget_usd=min(
                    self.cfg.max_budget_per_experiment_usd,
                    self.cfg.budget_usd - self._cost_spent,
                ),
                max_turns=self.cfg.max_turns_per_experiment,
                skip_estimate=True,
            )
            iter_cost = result.raw.get("cost_usd") or 0.0
        except Exception as exc:
            run_error = str(exc)
            logger.warning("karpathy_loop.run_error", n=n, error=run_error)
            from ai_team.backends.claude_agent_sdk_backend.workspace_snapshots import (
                restore_workspace_subtrees,
            )

            restore_workspace_subtrees(ws, tag=tag)
            self._record(n, None, False, iter_cost, run_error, tag)
            self._cost_spent += iter_cost
            return

        self._cost_spent += iter_cost
        elapsed = time.monotonic() - t0

        # --- measure ---
        new_metric = extract_metric(self.cfg.metric, ws)
        improved = self._is_improvement(new_metric)

        # --- keep or revert ---
        if improved:
            try:
                git_add(str(ws), ["."])
                sha = git_commit(
                    str(ws),
                    (
                        f"experiment({n}): {self.cfg.metric.name} "
                        f"{self._best:.4f} → {new_metric:.4f}"
                    ),
                )
                self._best = new_metric
                self._winning_commits.append(sha)
                logger.info("karpathy_loop.kept", n=n, metric=new_metric, sha=sha)
            except Exception as exc:
                # git commit failed (e.g. nothing staged) — revert to be safe
                logger.warning("karpathy_loop.commit_failed", n=n, error=str(exc))
                restore_workspace_subtrees(ws, tag=tag)
                improved = False
        else:
            # Restore snapshot; belt-and-suspenders: also hard-reset git index
            from ai_team.backends.claude_agent_sdk_backend.workspace_snapshots import (
                restore_workspace_subtrees,
            )

            restore_workspace_subtrees(ws, tag=tag)
            git_reset_hard(ws)
            logger.info("karpathy_loop.reverted", n=n, metric=new_metric)

        self._ingest_lesson(n, new_metric, improved, elapsed)
        self._record(n, new_metric, improved, iter_cost, None, tag)

    def _build_prompt(self, n: int) -> str:
        rag = get_rag_pipeline()
        context = rag.format_context(rag.retrieve(f"optimize {self.cfg.metric.name}", top_k=5))
        strategy_block = (
            f"\n\nHigh-level strategy hints:\n{self.cfg.strategy}" if self.cfg.strategy else ""
        )
        lessons_block = (
            f"\n\nLessons from prior experiments (retrieved from memory):\n{context}"
            if context.strip()
            else ""
        )
        editable = ", ".join(self.cfg.editable_files)
        best_str = f"{self._best:.4f}" if self._best is not None else "unknown"
        return (
            f"AutoOptimizer iteration {n}.\n\n"
            f"You are an autonomous code optimizer. Your ONLY job this iteration is to:\n"
            f"1. Study the code in {editable}.\n"
            f"2. Form ONE clear hypothesis about how to improve: {self.cfg.metric.name} "
            f"(current best: {best_str}, direction: {self.cfg.metric.direction}).\n"
            f"3. Apply that single focused change.\n"
            f"4. Do NOT change tests, CI config, Dockerfile, or files outside: {editable}.\n"
            f"5. Do NOT add explanatory comments or TODOs — just make the change.\n"
            f"State your hypothesis in one sentence before editing."
            f"{strategy_block}{lessons_block}"
        )

    def _is_improvement(self, new_metric: float | None) -> bool:
        if new_metric is None or self._best is None:
            return False
        if not self.cfg.metric.better(new_metric, self._best):
            return False
        # Require improvement to exceed noise floor
        pct = abs(new_metric - self._best) / max(abs(self._best), 1e-9) * 100
        return pct >= self.cfg.min_improvement_pct

    def _ingest_lesson(self, n: int, metric: float | None, kept: bool, elapsed: float) -> None:
        diff_preview = ""
        with contextlib.suppress(Exception):
            diff_preview = git_diff(str(self.cfg.workspace))[:600]
        outcome = "IMPROVEMENT — kept" if kept else "NO_IMPROVEMENT — reverted"
        chunk = TextChunk(
            text=(
                f"AutoOptimizer experiment {n}: {outcome}. "
                f"metric={metric}, elapsed={elapsed:.1f}s. "
                f"diff_preview: {diff_preview}"
            ),
            source_id=f"karpathy_loop:iter_{n:03d}",
            section="experiment_lesson",
        )
        try:
            get_rag_pipeline().ingest_chunks([chunk])
        except Exception as exc:
            logger.warning("karpathy_loop.rag_ingest_failed", n=n, error=str(exc))

    def _record(
        self,
        n: int,
        metric: float | None,
        kept: bool,
        cost: float,
        error: str | None,
        tag: str,
    ) -> None:
        append_experiment(
            self.cfg.workspace,
            ExperimentRecord(
                iteration=n,
                metric_value=metric,
                baseline=self._baseline,
                kept=kept,
                cost_usd=cost,
                snapshot_tag=tag,
                error=error,
            ),
        )

    def _calc_improvement(self) -> float | None:
        if self._baseline is not None and self._best is not None and self._baseline != 0:
            delta = self._best - self._baseline
            return round(delta / abs(self._baseline) * 100, 2)
        return None

    @staticmethod
    def _load_experiments(ws: Path) -> list[ExperimentRecord]:
        from ai_team.optimizers.experiment_log import load_experiments

        return load_experiments(ws)
