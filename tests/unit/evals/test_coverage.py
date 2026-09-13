"""Check-liveness and signal-chain coverage tests (``eval-coverage`` R12).

No test here writes under ``evals/`` — every path that persists anything uses
``tmp_path`` (R12.1).
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from evals import coverage
from evals.checks import all_checks
from evals.checks.base import CheckResult
from evals.coverage import (
    EVIDENCE_STARVED_SHARE,
    THIN_DECIDED_FLOOR,
    THIN_NA_SHARE,
    CheckLiveness,
    blocking_signals,
    classify,
    liveness_from_report,
    liveness_from_results,
    liveness_over_corpus,
    load_traces,
    render_markdown,
    render_side_by_side,
    render_signals_markdown,
    signal_chain,
    unreachable_span_types,
)

pytestmark = pytest.mark.eval_unit


def _result(
    check_id: str,
    outcome: str,
    trace_id: str = "t1",
    *,
    fm: str | None = "FM-001",
    text: str = "",
) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        failure_mode_id=fm,
        trace_id=trace_id,
        outcome=outcome,  # type: ignore[arg-type]
        evidence_text=text,
    )


class TestClassify:
    """R2.2 — the verdict rule, including both boundaries (R12.2)."""

    def test_unreachable_wins_over_everything(self) -> None:
        # Even a check deciding freely is reported as unreachable when its
        # mandatory evidence has no producer: that is a code defect, not a state.
        assert classify(n_pass=50, n_fail=50, n_na=0, unreachable=True) == "unreachable"

    def test_no_decisions_is_blind(self) -> None:
        assert classify(n_pass=0, n_fail=0, n_na=50) == "blind"

    def test_errors_are_not_decisions(self) -> None:
        assert classify(n_pass=0, n_fail=0, n_na=0, n_error=50) == "blind"

    def test_one_fixture_pair_is_thin(self) -> None:
        # The eleven-checks case: decided by exactly its own fixtures.
        assert classify(n_pass=1, n_fail=1, n_na=92) == "thin"

    def test_thin_below_decided_floor(self) -> None:
        assert classify(n_pass=THIN_DECIDED_FLOOR - 1, n_fail=0, n_na=0) == "thin"

    def test_live_at_decided_floor(self) -> None:
        assert classify(n_pass=THIN_DECIDED_FLOOR, n_fail=0, n_na=0) == "live"

    def test_thin_above_na_share_despite_many_decisions(self) -> None:
        # 20 decided but 95% abstention — decided enough, saw too little.
        assert classify(n_pass=20, n_fail=0, n_na=380) == "thin"

    def test_live_at_na_share_boundary(self) -> None:
        # Exactly at the threshold is not "more than" it.
        n_na = 90
        n_pass = 10
        assert (n_na / (n_na + n_pass)) == pytest.approx(THIN_NA_SHARE)
        assert classify(n_pass=n_pass, n_fail=0, n_na=n_na) == "live"

    @pytest.mark.parametrize("verdict", ["live", "thin", "blind", "unreachable"])
    def test_every_verdict_reachable(self, verdict: str) -> None:
        cases: dict[str, dict[str, object]] = {
            "live": {"n_pass": 20, "n_fail": 20, "n_na": 0},
            "thin": {"n_pass": 1, "n_fail": 1, "n_na": 0},
            "blind": {"n_pass": 0, "n_fail": 0, "n_na": 1},
            "unreachable": {"n_pass": 0, "n_fail": 0, "n_na": 1, "unreachable": True},
        }
        assert classify(**cases[verdict]) == verdict  # type: ignore[arg-type]


class TestSignalChain:
    """R4 — static generation, correct with no corpus at all (R12.6)."""

    def test_generates_without_a_trace_store(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        rows = signal_chain()
        assert rows, "signal chain must not depend on a corpus"

    def test_human_interrupt_is_unreachable(self) -> None:
        row = next(r for r in signal_chain() if r.span_type == "human_interrupt")
        assert row.parsers == ()
        assert "unreachable_signal" in row.flags
        assert "CHK-interrupt-latency" in row.consumers

    def test_error_span_has_no_producer(self) -> None:
        # builder.py maps an "error" *status*; no parser builds an error *span*.
        row = next(r for r in signal_chain() if r.span_type == "error")
        assert row.parsers == ()
        assert "unreachable_signal" in row.flags

    def test_known_orphans(self) -> None:
        orphans = {r.span_type for r in signal_chain() if "orphan_signal" in r.flags}
        assert orphans == {
            "qa_verdict",
            "regression_check",
            "session_start",
            "subagent_start",
            "subagent_stop",
        }

    def test_orphan_has_a_parser_and_no_consumer(self) -> None:
        for row in signal_chain():
            if "orphan_signal" in row.flags:
                assert row.parsers and not row.consumers

    def test_unreachable_span_types_matches_flags(self) -> None:
        assert unreachable_span_types() == {"error", "human_interrupt"}

    def test_renders_markdown(self) -> None:
        text = render_signals_markdown(signal_chain())
        assert "unreachable_signal" in text
        assert "`human_interrupt`" in text


class TestBlockingSignals:
    """R2.2 — an ``any_of`` group with one live member does not blind a check."""

    def test_sole_unreachable_member_blocks(self) -> None:
        assert blocking_signals("CHK-interrupt-latency") == ("human_interrupt",)

    def test_group_with_a_producible_member_does_not_block(self) -> None:
        # Reads the unreachable `error` type, but llm_call and retry keep it alive.
        assert "error" in coverage._CHECK_SPAN_READS["CHK-provider-error-rate"]
        assert blocking_signals("CHK-provider-error-rate") == ()

    def test_premature_termination_not_blocked(self) -> None:
        assert blocking_signals("CHK-premature-termination") == ()

    def test_unknown_check_is_not_blocked(self) -> None:
        assert blocking_signals("CHK-does-not-exist") == ()


class TestSeedTablesTrackTheRegistry:
    """The seed tables are hand-maintained; they must not drift (design §2.5)."""

    def test_every_registered_check_has_a_reads_entry(self) -> None:
        registered = {c.id for c in all_checks()}
        declared = set(coverage._CHECK_SPAN_READS)
        assert (
            registered == declared
        ), f"missing: {sorted(registered - declared)}; stale: {sorted(declared - registered)}"

    def test_mandatory_is_a_subset_of_reads(self) -> None:
        for check_id, groups in coverage._CHECK_SPAN_MANDATORY.items():
            reads = set(coverage._CHECK_SPAN_READS[check_id])
            for group in groups:
                assert set(group) <= reads, f"{check_id}: {group} not in reads"

    def test_every_read_span_type_is_known(self) -> None:
        known = set(coverage._PRODUCERS)
        for check_id, reads in coverage._CHECK_SPAN_READS.items():
            assert set(reads) <= known, f"{check_id} reads unknown span type"


class TestLivenessFolding:
    def test_counts_and_shares(self) -> None:
        results = [_result("CHK-x", "pass", f"t{i}") for i in range(12)]
        results += [_result("CHK-x", "fail", "tf")]
        results += [_result("CHK-x", "not_applicable", f"n{i}", text="no spans") for i in range(3)]
        report = liveness_from_results(results, corpus_label="synthetic")
        (c,) = report.checks
        assert (c.n_pass, c.n_fail, c.n_na, c.n_decided) == (12, 1, 3, 13)
        assert c.liveness == "live"
        assert c.na_reason_text_top == [("no spans", 3)]

    def test_error_outcomes_never_become_decisions(self) -> None:
        results = [_result("CHK-x", "error", f"t{i}") for i in range(50)]
        report = liveness_from_results(results, corpus_label="synthetic")
        (c,) = report.checks
        assert c.n_error == 50
        assert c.n_decided == 0
        assert c.liveness == "blind"

    def test_rate_text_suppresses_small_denominators(self) -> None:
        assert CheckLiveness(check_id="c", n_pass=0, n_fail=0).rate_text() == "—"
        assert CheckLiveness(check_id="c", n_pass=2, n_fail=1).rate_text() == "n=3"
        assert "n=20" in CheckLiveness(check_id="c", n_pass=10, n_fail=10).rate_text()

    def test_empty_corpus_is_valid_and_starved(self) -> None:
        report = liveness_over_corpus([], corpus_label="empty")
        assert report.n_traces == 0
        assert report.checks == []

    def test_verdict_suffix_only_when_unreachable(self) -> None:
        live = liveness_from_results(
            [_result("CHK-x", "pass", f"t{i}") for i in range(20)],
            corpus_label="s",
        )
        assert live.verdict_suffix() == ""
        blind = liveness_from_results(
            [_result("CHK-interrupt-latency", "not_applicable", f"t{i}") for i in range(5)],
            corpus_label="s",
        )
        assert blind.verdict_suffix() == " (instruments incomplete)"
        assert "instruments incomplete" in blind.verdict_suffix()


class TestEvidenceStarvedStamp:
    """R11.1 — threshold behaviour at both sides (R12.2)."""

    def _report_with_na_share(self, n_na: int, n_decided: int) -> object:
        results = [_result("CHK-x", "pass", f"p{i}") for i in range(n_decided)]
        results += [_result("CHK-x", "not_applicable", f"n{i}") for i in range(n_na)]
        return liveness_from_results(results, corpus_label="s")

    def test_below_threshold_not_stamped(self) -> None:
        report = self._report_with_na_share(n_na=499, n_decided=501)
        assert report.na_share < EVIDENCE_STARVED_SHARE  # type: ignore[attr-defined]
        assert report.evidence_starved is False  # type: ignore[attr-defined]

    def test_above_threshold_stamped(self) -> None:
        report = self._report_with_na_share(n_na=501, n_decided=499)
        assert report.evidence_starved is True  # type: ignore[attr-defined]
        assert "EVIDENCE-STARVED" in report.stamps()  # type: ignore[attr-defined]

    def test_exactly_at_threshold_not_stamped(self) -> None:
        report = self._report_with_na_share(n_na=50, n_decided=50)
        assert report.evidence_starved is False  # type: ignore[attr-defined]

    def test_top_abstainers_named(self) -> None:
        results = [_result("CHK-a", "not_applicable", f"a{i}") for i in range(9)]
        results += [_result("CHK-b", "not_applicable", f"b{i}") for i in range(5)]
        results += [_result("CHK-c", "pass", "c0")]
        report = liveness_from_results(results, corpus_label="s")
        assert report.top_abstainers[0] == ("CHK-a", 9)


class TestFromReport:
    def test_folds_a_report_document(self, tmp_path: Path) -> None:
        doc = {
            "check_results": [
                {
                    "check_id": "CHK-x",
                    "failure_mode_id": "FM-001",
                    "trace_id": f"t{i}",
                    "outcome": "not_applicable",
                    "evidence_text": "no guardrail_check spans",
                }
                for i in range(90)
            ]
            + [
                {
                    "check_id": "CHK-x",
                    "failure_mode_id": "FM-001",
                    "trace_id": "tp",
                    "outcome": "pass",
                    "evidence_text": "",
                },
                {
                    "check_id": "CHK-x",
                    "failure_mode_id": "FM-001",
                    "trace_id": "tf",
                    "outcome": "fail",
                    "evidence_text": "",
                },
            ]
        }
        path = tmp_path / "report.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        report = liveness_from_report(path)
        assert report.corpus_kind == "FIXTURE-ONLY"
        assert report.n_traces == 92
        (c,) = report.checks
        assert c.liveness == "thin"
        assert report.evidence_starved is True

    def test_refuses_a_document_without_check_results(self, tmp_path: Path) -> None:
        path = tmp_path / "report.json"
        path.write_text(json.dumps({"verdict": "pass"}), encoding="utf-8")
        with pytest.raises(ValueError, match="no check_results"):
            liveness_from_report(path)


class TestLoadTraces:
    def test_missing_root_is_empty_not_an_error(self, tmp_path: Path) -> None:
        traces, unloadable = load_traces(tmp_path / "nope")
        assert (traces, unloadable) == ([], 0)

    def test_counts_unloadable_documents(self, tmp_path: Path) -> None:
        (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
        traces, unloadable = load_traces(tmp_path)
        assert traces == []
        assert unloadable == 1


class TestRenderers:
    def test_markdown_names_unreachable_checks(self) -> None:
        report = liveness_from_results(
            [
                _result("CHK-interrupt-latency", "not_applicable", f"t{i}", fm="FM-003")
                for i in range(50)
            ],
            corpus_label="corpus",
        )
        text = render_markdown(report)
        assert "UNREACHABLE" in text
        assert "no parser produces human_interrupt" in text

    def test_markdown_surfaces_errors(self) -> None:
        report = liveness_from_results(
            [_result("CHK-x", "error", f"t{i}") for i in range(7)],
            corpus_label="corpus",
        )
        text = render_markdown(report)
        assert "Checks that raised" in text
        assert "7 of 7 raised" in text

    def test_side_by_side_marks_regressions(self) -> None:
        fixtures = liveness_from_results(
            [_result("CHK-x", "pass", f"p{i}") for i in range(20)],
            corpus_label="fixtures",
            corpus_kind="FIXTURE-ONLY",
        )
        corpus = liveness_from_results(
            [_result("CHK-x", "not_applicable", f"n{i}") for i in range(50)],
            corpus_label="corpus",
        )
        text = render_side_by_side(fixtures, corpus)
        assert "live" in text
        assert "BLIND" in text
        assert "↓" in text

    def test_side_by_side_handles_a_check_absent_from_the_corpus(self) -> None:
        fixtures = liveness_from_results(
            [_result("CHK-only-in-fixtures", "pass", "p0")], corpus_label="fixtures"
        )
        corpus = liveness_from_results([_result("CHK-other", "pass", "p0")], corpus_label="corpus")
        assert "not run" in render_side_by_side(fixtures, corpus)


class TestPurity:
    """Liveness must be computable offline (R12.4)."""

    def test_folding_works_with_sockets_blocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _blocked(*_a: object, **_k: object) -> None:
            raise OSError("network disabled for coverage purity test")

        monkeypatch.setattr(socket.socket, "connect", _blocked)
        monkeypatch.setattr(socket.socket, "connect_ex", lambda *_a, **_k: 1)
        report = liveness_from_results(
            [_result("CHK-x", "pass", f"t{i}") for i in range(12)], corpus_label="s"
        )
        assert report.checks[0].liveness == "live"
        assert signal_chain()


class TestHygiene:
    """R12.1 — nothing in this module writes under tracked eval directories."""

    def test_module_writes_nothing_on_import_or_fold(self) -> None:
        tracked = Path("evals")
        before = {p for p in tracked.rglob("*") if p.is_file()} if tracked.is_dir() else set()
        liveness_from_results([_result("CHK-x", "pass", "t0")], corpus_label="s")
        signal_chain()
        after = {p for p in tracked.rglob("*") if p.is_file()} if tracked.is_dir() else set()
        assert before == after
