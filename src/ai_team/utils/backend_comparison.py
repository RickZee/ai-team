"""Run the same project description through CrewAI and LangGraph; build a comparison report."""

from __future__ import annotations

import os
import time
from pathlib import Path

import structlog
from ai_team.backends.registry import get_backend
from ai_team.core.result import ProjectResult
from ai_team.core.team_profile import TeamProfile, load_team_profile
from ai_team.models.comparison_report import (
    ComparisonReport,
    snapshot_from_project_result,
)
from ai_team.utils.demo_input import load_project_description

logger = structlog.get_logger(__name__)


def _run_one_backend(
    name: str,
    description: str,
    profile: TeamProfile,
    env: str | None,
    *,
    skip_estimate: bool,
    complexity_override: str | None,
) -> tuple[ProjectResult, float]:
    """Return ``ProjectResult`` and wall-clock seconds for one backend."""
    backend = get_backend(name)
    t0 = time.perf_counter()
    try:
        pr = backend.run(
            description,
            profile,
            env=env,
            monitor=None,
            skip_estimate=skip_estimate,
            complexity_override=complexity_override,
        )
    finally:
        dt = time.perf_counter() - t0
    return pr, dt


def compare_backends_on_description(
    *,
    description: str,
    demo_path: Path,
    team: str,
    env: str | None,
    skip_estimate: bool,
    complexity_override: str | None = None,
) -> ComparisonReport:
    """
    Run CrewAI then LangGraph with identical inputs and return a :class:`ComparisonReport`.

    Sets ``AI_TEAM_ENV`` from ``env`` when provided (before each run).
    """
    profile = load_team_profile(team)
    if env is not None:
        os.environ["AI_TEAM_ENV"] = env

    logger.info(
        "backend_comparison_start",
        demo=str(demo_path),
        team=team,
        env=env,
    )

    crewai_result, crewai_dt = _run_one_backend(
        "crewai",
        description,
        profile,
        env,
        skip_estimate=skip_estimate,
        complexity_override=complexity_override,
    )
    lg_result, lg_dt = _run_one_backend(
        "langgraph",
        description,
        profile,
        env,
        skip_estimate=skip_estimate,
        complexity_override=complexity_override,
    )

    logger.info(
        "backend_comparison_done",
        crewai_success=crewai_result.success,
        langgraph_success=lg_result.success,
        crewai_sec=round(crewai_dt, 4),
        langgraph_sec=round(lg_dt, 4),
    )

    return ComparisonReport(
        demo_path=str(demo_path.resolve()),
        description=description,
        env=env,
        team_profile=team,
        crewai=snapshot_from_project_result(
            backend_name="crewai",
            team_profile=team,
            duration_sec=crewai_dt,
            result=crewai_result,
        ),
        langgraph=snapshot_from_project_result(
            backend_name="langgraph",
            team_profile=team,
            duration_sec=lg_dt,
            result=lg_result,
        ),
    )


def compare_backends_for_demo_dir(
    demo_dir: Path,
    *,
    team: str,
    env: str | None,
    skip_estimate: bool,
    complexity_override: str | None = None,
) -> ComparisonReport:
    """Load description from ``demo_dir`` and compare backends."""
    description = load_project_description(demo_dir)
    return compare_backends_on_description(
        description=description,
        demo_path=demo_dir,
        team=team,
        env=env,
        skip_estimate=skip_estimate,
        complexity_override=complexity_override,
    )
