"""Binary judge prompt validation and cache (Phase 7.1) — no live API calls."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from evals.golden import LabelingUnit
from evals.judges.base import (
    BinaryJudge,
    Verdict,
    VerdictCache,
    assert_prompt_version_tracks_body,
    cache_key,
    load_judge_spec,
    validate_prompts,
)
from tests.unit.evals.trace_fixtures import base_trace


@pytest.mark.eval_unit
def test_prompt_files_parse_and_version_matches_filename() -> None:
    specs = validate_prompts()
    assert specs
    for spec in specs:
        assert spec.path is not None
        assert Path(spec.path).name == f"{spec.judge_id}.v{spec.version}.md"
        assert len(spec.prompt_hash) == 64


@pytest.mark.eval_unit
def test_prompt_body_change_without_version_bump_fails() -> None:
    path = Path("evals/judges/prompts/fm-001-tool-call-omission.v1.md")
    with pytest.raises(ValueError, match="bump version"):
        assert_prompt_version_tracks_body(path, altered_body="totally new body text\n")


@pytest.mark.eval_unit
def test_cached_verdict_served_with_sockets_blocked(tmp_path: Path) -> None:
    spec = load_judge_spec(Path("evals/judges/prompts/fm-001-tool-call-omission.v1.md"))
    cache = VerdictCache(root=tmp_path / "cache")
    evidence = "trace_id=t\nbackend=crewai\n(no development-phase tool/llm spans)"
    key = cache_key(spec.prompt_hash, spec.model, evidence)
    stored = Verdict(
        judge_id=spec.judge_id,
        prompt_hash=spec.prompt_hash,
        model_id=spec.model,
        provider=spec.provider,
        trace_id="t1",
        labeling_unit_id="u1",
        verdict="pass",
        reason="tools wrote files",
        evidence_quote="backend=crewai",
        evidence_sha256="0" * 64,
        single_vendor=False,
    )
    cache.put(key, stored)

    from evals.judges import evidence as evidence_mod

    original = evidence_mod.EVIDENCE[spec.evidence_builder]
    evidence_mod.EVIDENCE[spec.evidence_builder] = lambda _t, _u: evidence
    try:
        real_socket = socket.socket

        def _no_socket(*_a: object, **_k: object) -> None:
            raise OSError("network blocked")

        socket.socket = _no_socket  # type: ignore[misc, assignment]
        try:
            judge = BinaryJudge(spec, cache=cache, allow_network=False)
            unit = LabelingUnit(
                labeling_unit_id="u1",
                trace_id="t1",
                span_id="run",
                failure_mode_id="FM-001",
            )
            out = judge.judge(unit, base_trace(check_id="judge-cache", outcome="pass"))
            assert out.cached is True
            assert out.verdict == "pass"
        finally:
            socket.socket = real_socket  # type: ignore[misc, assignment]
    finally:
        evidence_mod.EVIDENCE[spec.evidence_builder] = original
