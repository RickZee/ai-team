"""Run the labeled guardrail corpus through the real guardrails and score it.

This is the regression harness for guardrail precision. The corpus in
tests/fixtures/guardrail_corpus/ encodes, as data, the false positives that cost real
runs in the journal (QA vocabulary read as scope creep, conftest.py read as production
source, QA quoting code it received). If a future threshold change re-flags any of
them, the FP-rate assertion here fails and the change gets caught before it ships —
instead of being discovered live, one burned run at a time.

The harness also prints a precision/recall line per guardrail so a PR can paste
measured numbers rather than assert "seems better".
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_team.guardrails.behavioral import (
    role_adherence_guardrail,
    scope_control_guardrail,
)
from ai_team.guardrails.corpus_metrics import format_report, score

_CORPUS = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "guardrail_corpus"
    / "behavioral_cases.json"
)


def _load() -> dict:
    return json.loads(_CORPUS.read_text(encoding="utf-8"))


def _fired(status: str) -> bool:
    """A guardrail 'fires' (positive prediction) only on a hard fail. warn/pass = let through."""
    return status == "fail"


def _expected_fire(case: dict) -> bool:
    """Is this case labeled a real violation the guardrail should catch?"""
    if "expect" in case:
        return case["expect"] == "fail"
    # 'expect_not: fail' cases are benign (must not fire); anything else benign too.
    return False


class TestScopeControlCorpus:
    def test_no_false_positive_on_labeled_benign_cases(self) -> None:
        cases = _load()["scope_control"]
        outcomes = []
        false_positives = []
        for c in cases:
            res = scope_control_guardrail(c["output"], c["requirements"])
            fired = _fired(res.status)
            is_real = _expected_fire(c)
            outcomes.append((fired, is_real))
            if fired and not is_real:
                false_positives.append((c["id"], res.message))

        counts = score(outcomes)
        print("\n" + format_report("scope_control", counts))

        assert not false_positives, (
            "scope_control false-flagged benign output (precision regression): "
            + "; ".join(f"{cid}: {msg}" for cid, msg in false_positives)
        )

    def test_catches_labeled_real_scope_creep(self) -> None:
        cases = _load()["scope_control"]
        missed = []
        for c in cases:
            if not _expected_fire(c):
                continue
            res = scope_control_guardrail(c["output"], c["requirements"])
            if not _fired(res.status):
                missed.append(c["id"])
        assert not missed, f"scope_control missed real violations (recall regression): {missed}"

    def test_precision_and_fpr_thresholds(self) -> None:
        cases = _load()["scope_control"]
        outcomes = [
            (_fired(scope_control_guardrail(c["output"], c["requirements"]).status), _expected_fire(c))
            for c in cases
        ]
        counts = score(outcomes)
        # Hard gate: zero false positives on this corpus, perfect recall.
        assert counts.false_positive_rate == 0.0, format_report("scope_control", counts)
        assert counts.recall == 1.0, format_report("scope_control", counts)


class TestRoleAdherenceCorpus:
    def _run(self, case: dict) -> str:
        return role_adherence_guardrail(
            case["output"],
            case["role"],
            is_supervisor=case.get("is_supervisor", False),
        ).status

    def test_benign_cases_are_not_failed(self) -> None:
        cases = _load()["role_adherence"]
        wrongly_failed = []
        for c in cases:
            if "expect_not" not in c or c["expect_not"] != "fail":
                continue
            status = self._run(c)
            if status == "fail":
                wrongly_failed.append((c["id"], c["why"]))
        assert not wrongly_failed, (
            "role_adherence hard-failed a benign case (precision regression): "
            + "; ".join(cid for cid, _ in wrongly_failed)
        )

    def test_real_role_violation_is_caught(self) -> None:
        cases = _load()["role_adherence"]
        missed = []
        for c in cases:
            if c.get("expect") != "fail":
                continue
            if self._run(c) != "fail":
                missed.append(c["id"])
        assert not missed, f"role_adherence missed real violations (recall regression): {missed}"

    def test_supervisor_path_is_advisory_only(self) -> None:
        cases = _load()["role_adherence"]
        supervisor_cases = [c for c in cases if c.get("is_supervisor")]
        assert supervisor_cases, "corpus should exercise the supervisor advisory path"
        for c in supervisor_cases:
            assert self._run(c) != "fail", f"supervisor case {c['id']} should never hard-fail"


class TestCorpusIntegrity:
    def test_every_case_has_a_label_and_rationale(self) -> None:
        data = _load()
        for section in ("scope_control", "role_adherence"):
            for c in data[section]:
                assert "id" in c, f"{section} case missing id"
                assert "why" in c, f"{c.get('id')} missing rationale"
                assert ("expect" in c) or ("expect_not" in c), f"{c['id']} has no label"

    def test_both_guardrails_have_positive_and_negative_cases(self) -> None:
        # A corpus of only-benign or only-violation cases can't measure both errors.
        data = _load()
        scope_labels = {c.get("expect") for c in data["scope_control"]}
        assert "fail" in scope_labels, "scope_control corpus needs at least one real violation"
        assert "pass" in scope_labels, "scope_control corpus needs at least one benign case"

        role_has_violation = any(c.get("expect") == "fail" for c in data["role_adherence"])
        role_has_benign = any(c.get("expect_not") == "fail" for c in data["role_adherence"])
        assert role_has_violation and role_has_benign


if __name__ == "__main__":
    # Print the scorecard without pytest, for a quick manual read.
    data = _load()
    scope_outcomes = [
        (_fired(scope_control_guardrail(c["output"], c["requirements"]).status), _expected_fire(c))
        for c in data["scope_control"]
    ]
    role_outcomes = [
        (
            role_adherence_guardrail(
                c["output"], c["role"], is_supervisor=c.get("is_supervisor", False)
            ).status
            == "fail",
            c.get("expect") == "fail",
        )
        for c in data["role_adherence"]
    ]
    print(format_report("scope_control", score(scope_outcomes)))
    print(format_report("role_adherence", score(role_outcomes)))
