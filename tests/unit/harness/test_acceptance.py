"""Acceptance list: identity, writer, evidence, demotion, concurrent writes."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from ai_team.harness.acceptance import (
    ACCEPTANCE_FILENAME,
    AcceptanceError,
    VerifierIdentity,
    demote,
    is_acceptance_target,
    item_id,
    load,
    mark_passing,
    normalize_for_id,
    status,
    write_initial,
    write_initial_from_any,
)
from ai_team.models.requirements import (
    AcceptanceCriterion,
    MoSCoW,
    RequirementsDocument,
    UserStory,
)


def _req(*criteria: str) -> RequirementsDocument:
    return RequirementsDocument(
        project_name="todo",
        description="A todo API",
        user_stories=[
            UserStory(
                as_a="user",
                i_want="list todos",
                so_that="I can see work",
                acceptance_criteria=[AcceptanceCriterion(description=c) for c in criteria],
                priority=MoSCoW.MUST,
            )
        ],
    )


def _identity() -> VerifierIdentity:
    return VerifierIdentity(agent_role="qa_engineer", session_id="s1", subagent_id="qa-1")


def test_id_stable_across_whitespace_and_punctuation_spacing() -> None:
    a = item_id("Given a user,  when they list todos, then they see items.", ["step 1"])
    b = item_id("Given a user, when they list todos, then they see items.", ["step 1"])
    c = item_id("Given a user ,when they list todos ,then they see items.", ["step 1"])
    assert a == b == c
    assert normalize_for_id("Hello,  world") == normalize_for_id("Hello, world")


def test_id_changes_on_semantic_edit() -> None:
    base = item_id("list todos", ["GET /todos returns 200"])
    assert item_id("list tasks", ["GET /todos returns 200"]) != base
    assert item_id("list todos", ["GET /todos returns 201"]) != base


def test_write_initial_and_status(tmp_path: Path) -> None:
    doc = write_initial(tmp_path, _req("GET /todos returns 200"), "run-1")
    assert (tmp_path / ACCEPTANCE_FILENAME).is_file()
    assert len(doc.items) >= 1
    st = status(tmp_path)
    assert st.total >= 1
    assert st.passing == 0
    assert st.next_item is not None
    log = (tmp_path / "logs" / "acceptance.jsonl").read_text(encoding="utf-8")
    assert "write_initial" in log


def test_write_initial_refuses_overwrite(tmp_path: Path) -> None:
    write_initial(tmp_path, _req("a"), "run-1")
    with pytest.raises(AcceptanceError, match="already exists"):
        write_initial(tmp_path, _req("b"), "run-1")


def test_mark_passing_rejects_empty_and_missing_evidence(tmp_path: Path) -> None:
    doc = write_initial(tmp_path, _req("GET /todos returns 200"), "run-1")
    iid = doc.items[0].id
    with pytest.raises(AcceptanceError, match="evidence"):
        mark_passing(tmp_path, iid, evidence=[], verified_by="smoke", identity=_identity())
    with pytest.raises(AcceptanceError, match="missing"):
        mark_passing(
            tmp_path,
            iid,
            evidence=["docs/nope.json"],
            verified_by="smoke",
            identity=_identity(),
        )


def test_mark_passing_accepts_existing_evidence(tmp_path: Path) -> None:
    doc = write_initial(tmp_path, _req("GET /todos returns 200"), "run-1")
    ev = tmp_path / "docs" / "smoke_results.json"
    ev.parent.mkdir()
    ev.write_text("{}", encoding="utf-8")
    updated = mark_passing(
        tmp_path,
        doc.items[0].id,
        evidence=["docs/smoke_results.json"],
        verified_by="smoke",
        identity=_identity(),
    )
    assert updated.items[0].passes is True
    assert updated.items[0].verifier_identity is not None
    assert updated.items[0].verifier_identity.agent_role == "qa_engineer"
    assert status(tmp_path).passing == 1


def test_demote_refuses_without_reason(tmp_path: Path) -> None:
    doc = write_initial(tmp_path, _req("GET /todos returns 200"), "run-1")
    ev = tmp_path / "docs" / "e.json"
    ev.parent.mkdir()
    ev.write_text("{}", encoding="utf-8")
    mark_passing(
        tmp_path,
        doc.items[0].id,
        evidence=["docs/e.json"],
        verified_by="test",
        identity=_identity(),
    )
    with pytest.raises(AcceptanceError, match="reason"):
        demote(tmp_path, doc.items[0].id, session_id="s2", reason="  ")
    demoted = demote(tmp_path, doc.items[0].id, session_id="s2", reason="regression")
    assert demoted.items[0].passes is False
    assert demoted.items[0].demotions[-1].reason == "regression"


def test_concurrent_writers_no_torn_file(tmp_path: Path) -> None:
    doc = write_initial(tmp_path, _req("one", "two"), "run-1")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "docs" / "b.json").write_text("{}", encoding="utf-8")
    ids = [i.id for i in doc.items[:2]]
    errors: list[BaseException] = []

    def _mark(iid: str, ev: str) -> None:
        try:
            mark_passing(tmp_path, iid, evidence=[ev], verified_by="test", identity=_identity())
        except BaseException as exc:  # noqa: BLE001 — collect for assertion
            errors.append(exc)

    t1 = threading.Thread(target=_mark, args=(ids[0], "docs/a.json"))
    t2 = threading.Thread(target=_mark, args=(ids[1], "docs/b.json"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert errors == []
    loaded = load(tmp_path)
    text = (tmp_path / ACCEPTANCE_FILENAME).read_text(encoding="utf-8")
    # File must be valid JSON (not torn) and both items passing.
    assert text.strip().startswith("{")
    assert sum(1 for i in loaded.items if i.passes) == 2


def test_write_initial_from_any_dict(tmp_path: Path) -> None:
    result = write_initial_from_any(
        tmp_path,
        {"acceptance_criteria": ["boot returns 200", "create todo persists"]},
        "run-lg",
    )
    assert result is not None
    assert len(result.items) >= 1


def test_is_acceptance_target_variants(tmp_path: Path) -> None:
    write_initial(tmp_path, _req("x"), "run-1")
    assert is_acceptance_target(tmp_path, "ACCEPTANCE.json")
    assert is_acceptance_target(tmp_path, "./ACCEPTANCE.json")
    assert is_acceptance_target(tmp_path, str(tmp_path / "ACCEPTANCE.json"))
    link = tmp_path / "docs" / "alias.json"
    link.parent.mkdir(exist_ok=True)
    link.symlink_to(tmp_path / "ACCEPTANCE.json")
    assert is_acceptance_target(tmp_path, str(link))
    assert not is_acceptance_target(tmp_path, "docs/requirements.md")
