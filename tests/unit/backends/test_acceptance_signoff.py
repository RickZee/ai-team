"""The quality gate, not the QA agent, flips acceptance passes."""

from __future__ import annotations

from pathlib import Path

from ai_team.backends.common.acceptance import apply_quality_gate_acceptance
from ai_team.harness.acceptance import load, write_initial
from ai_team.models.requirements import (
    AcceptanceCriterion,
    MoSCoW,
    RequirementsDocument,
    UserStory,
)


def _requirements() -> RequirementsDocument:
    return RequirementsDocument(
        project_name="calc",
        description="A tiny calculator",
        user_stories=[
            UserStory(
                as_a="caller",
                i_want="add two numbers",
                so_that="the sum is tested",
                acceptance_criteria=[AcceptanceCriterion(description="add(2, 3) returns 5")],
                priority=MoSCoW.MUST,
            )
        ],
    )


def test_passing_gate_marks_criteria_done(tmp_path: Path) -> None:
    write_initial(tmp_path, _requirements(), "run-1")
    apply_quality_gate_acceptance(tmp_path, tests_passed=True, lint_ok=True)
    doc = load(tmp_path)
    assert doc.items
    assert all(item.passes for item in doc.items)
    assert doc.items[0].verifier_identity is not None
    assert doc.items[0].verifier_identity.agent_role == "_harness"
    assert doc.items[0].evidence == ["logs/harness_acceptance.json"]


def test_failing_gate_does_not_mark_criteria_done(tmp_path: Path) -> None:
    write_initial(tmp_path, _requirements(), "run-1")
    apply_quality_gate_acceptance(tmp_path, tests_passed=False)
    doc = load(tmp_path)
    assert all(item.passes is False for item in doc.items)
