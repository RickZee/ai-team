"""Build-contract store, round ceiling, and negotiation escalation (R11)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from ai_team.flows.error_handling import escalate_contract_negotiation
from ai_team.flows.state import ProjectState
from ai_team.harness.contracts import (
    MAX_ROUNDS,
    BuildContract,
    ContractReview,
    ContractRoundCeilingError,
    negotiate,
    require_accepted,
    review_contract,
    write_contract,
)


def test_round_trip_and_ceiling(tmp_path: Path) -> None:
    first = BuildContract(
        item_id="abc",
        round=1,
        approach="write flask app",
        testable_behaviors=["GET /todos 200"],
        files_to_touch=["src/app.py"],
    )
    write_contract(tmp_path, first)
    review_contract(tmp_path, "abc", verdict="rejected", reasons=["too vague"])
    second = BuildContract(
        item_id="abc",
        round=2,
        approach="write flask app with tests",
        testable_behaviors=["GET /todos 200"],
        files_to_touch=["src/app.py"],
    )
    write_contract(tmp_path, second)
    with pytest.raises(ContractRoundCeilingError):
        write_contract(
            tmp_path,
            BuildContract(item_id="abc", round=3, approach="again"),
        )
    assert MAX_ROUNDS == 2


def test_negotiate_escalates_after_two_rejections(tmp_path: Path) -> None:
    calls: list[tuple[str, list[str]]] = []

    def propose(rnd: int) -> BuildContract:
        return BuildContract(item_id="it", round=rnd, approach=f"try {rnd}")

    def review(contract: BuildContract) -> ContractReview:
        del contract
        return ContractReview(
            verdict="rejected",
            reasons=["no"],
            reviewed_at=datetime.now(UTC),
        )

    def escalate(item_id: str, reasons: list[str]) -> None:
        calls.append((item_id, reasons))

    assert negotiate(tmp_path, "it", propose=propose, review=review, escalate=escalate) is None
    assert calls == [("it", ["no"])]
    assert require_accepted(tmp_path, "it") is False


def test_escalate_goes_through_error_handling() -> None:
    state = ProjectState(project_id="p", project_description="d")
    result = escalate_contract_negotiation(state, "item-1", ["too vague", "no tests"])
    assert result["action"] in {"retry", "retry_with_feedback", "escalate"}
    assert "contract" in json.dumps(result, default=str).lower() or any(
        "contract" in str(e).lower() for e in state.errors
    )


def test_accepted_round_trip(tmp_path: Path) -> None:
    write_contract(
        tmp_path,
        BuildContract(item_id="ok", round=1, approach="ok", files_to_touch=["src/app.py"]),
    )
    review_contract(tmp_path, "ok", verdict="accepted", reasons=[])
    assert require_accepted(tmp_path, "ok") is True
