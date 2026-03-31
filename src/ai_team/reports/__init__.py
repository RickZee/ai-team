"""Run reports and structured outputs (manager self-improvement, etc.)."""

from ai_team.reports.manager_self_improvement import (
    build_manager_self_improvement_report,
    render_manager_self_improvement_markdown,
    try_generate_manager_narrative_summary,
    write_manager_self_improvement_report,
)

__all__ = [
    "build_manager_self_improvement_report",
    "render_manager_self_improvement_markdown",
    "try_generate_manager_narrative_summary",
    "write_manager_self_improvement_report",
]
