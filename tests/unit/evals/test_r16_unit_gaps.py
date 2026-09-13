"""Unit coverage gaps from design §7.1 / R16.1 (Phase 11.1)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from evals.alignment import append_validation_log, validation_log_has
from evals.cli import main
from evals.golden import LabelingUnit, assign_split
from evals.judges.base import BinaryJudge, VerdictCache, load_judge_spec
from evals.reliability import pass_at_k, pass_pow_k
from tests.unit.evals.trace_fixtures import base_trace

pytestmark = pytest.mark.eval_unit


def _json_verdict(verdict: str, reason: str, quote: str) -> str:
    import json

    return json.dumps({"verdict": verdict, "reason": reason, "evidence_quote": quote})


def test_assign_split_distribution_over_10k() -> None:
    """~40% test / ~60% dev over ≥10 000 synthetic ids (±2 pp)."""
    n = 10_000
    test_n = sum(1 for i in range(n) if assign_split(f"synth-{i}") == "test")
    rate = test_n / n
    assert 0.38 <= rate <= 0.42, f"test split rate {rate:.4f} outside 40%±2pp"


@pytest.mark.parametrize("k", [1, 3, 5])
def test_pass_at_k_and_pow_k_lengths(k: int) -> None:
    all_true = [True] * k
    all_false = [False] * k
    mixed = [True] + [False] * (k - 1) if k > 1 else [True]
    assert pass_at_k(all_true) == 1.0
    assert pass_pow_k(all_true) == 1.0
    assert pass_at_k(all_false) == 0.0
    assert pass_pow_k(all_false) == 0.0
    if k > 1:
        assert pass_at_k(mixed) == 1.0
        assert pass_pow_k(mixed) == 0.0


def test_binary_judge_ungrounded_quote_is_error(tmp_path: Path) -> None:
    spec = load_judge_spec(Path("evals/judges/prompts/fm-001-tool-call-omission.v1.md"))
    cache = VerdictCache(root=tmp_path / "cache")
    evidence = "tools wrote src/app.py successfully"
    from evals.judges import evidence as evidence_mod

    original = evidence_mod.EVIDENCE[spec.evidence_builder]
    evidence_mod.EVIDENCE[spec.evidence_builder] = lambda _t, _u: evidence
    try:
        judge = BinaryJudge(spec, cache=cache, allow_network=True)
        judge._llm = MagicMock()
        judge._llm._raw_complete.return_value = _json_verdict(
            "pass", "ok", "THIS QUOTE IS NOT IN EVIDENCE"
        )
        unit = LabelingUnit(
            labeling_unit_id="u1",
            trace_id="t1",
            span_id="run",
            failure_mode_id="FM-001",
        )
        out = judge.judge(unit, base_trace(check_id="ungrounded", outcome="pass"))
        assert out.verdict == "error"
        assert out.reason == "ungrounded"
    finally:
        evidence_mod.EVIDENCE[spec.evidence_builder] = original


def test_binary_judge_three_failures_never_fail(tmp_path: Path) -> None:
    spec = load_judge_spec(Path("evals/judges/prompts/fm-001-tool-call-omission.v1.md"))
    cache = VerdictCache(root=tmp_path / "cache")
    evidence = "backend=crewai wrote files"
    from evals.judges import evidence as evidence_mod

    original = evidence_mod.EVIDENCE[spec.evidence_builder]
    evidence_mod.EVIDENCE[spec.evidence_builder] = lambda _t, _u: evidence
    try:
        judge = BinaryJudge(spec, cache=cache, allow_network=True)
        mock_llm = MagicMock()
        mock_llm._raw_complete.side_effect = [
            ValueError("bad json"),
            ValueError("bad json"),
            ValueError("bad json"),
        ]
        judge._llm = mock_llm
        unit = LabelingUnit(
            labeling_unit_id="u2",
            trace_id="t2",
            span_id="run",
            failure_mode_id="FM-001",
        )
        out = judge.judge(unit, base_trace(check_id="retries", outcome="pass"))
        assert out.verdict == "error"
        assert out.verdict != "fail"
        assert "after 3 attempts" in out.reason
        assert mock_llm._raw_complete.call_count == 3
    finally:
        evidence_mod.EVIDENCE[spec.evidence_builder] = original


def test_judge_validate_refuses_retest_without_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_path = tmp_path / "validation_log.jsonl"
    monkeypatch.setattr("evals.alignment.VALIDATION_LOG", log_path)
    # `judge validate --allow-retest` calls write_advisory_alignment(), which defaults to
    # the committed evals/golden/alignment/ directory. Without this redirect the test
    # rewrites a tracked golden record's validated_at on every local run, leaving the
    # working tree dirty and making that record's provenance meaningless.
    monkeypatch.setattr("evals.alignment.ALIGNMENT_DIR", tmp_path / "alignment")

    spec = load_judge_spec(Path("evals/judges/prompts/fm-001-tool-call-omission.v1.md"))
    append_validation_log(spec.judge_id, spec.prompt_hash, log_path=log_path)
    assert validation_log_has(spec.judge_id, spec.prompt_hash, log_path=log_path)

    rc = main(
        [
            "judge",
            "validate",
            "--prompt",
            "evals/judges/prompts/fm-001-tool-call-omission.v1.md",
        ]
    )
    assert rc == 1

    rc2 = main(
        [
            "judge",
            "validate",
            "--prompt",
            "evals/judges/prompts/fm-001-tool-call-omission.v1.md",
            "--allow-retest",
        ]
    )
    assert rc2 == 0
