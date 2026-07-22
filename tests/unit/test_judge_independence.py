"""Judge-independence tests.

This project compares orchestration backends, one of which (``claude-agent-sdk``)
runs on Anthropic models. An LLM judge that shares a vendor with a contestant cannot
rule out self-preference bias, so the eval layer has to (a) let the judge provider be
chosen independently of the backends under test and (b) make single-vendor scoring
visible rather than silent.
"""

from __future__ import annotations

import pytest

from evals.fixtures import EnsembleJudge, JudgeVerdict, LLMJudge, _parse_judge_json


class _StubJudge:
    """Minimal stand-in for LLMJudge that returns a fixed score."""

    def __init__(self, identity: str, score: float, passed: bool = True) -> None:
        self.identity = identity
        self._verdict = JudgeVerdict(passed=passed, score=score, reason="stub")

    def check(self, criterion: str, evidence: str) -> JudgeVerdict:  # noqa: ARG002
        return self._verdict


class TestJudgeProviderSelection:
    def test_defaults_to_anthropic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AI_TEAM_JUDGE_PROVIDER", raising=False)
        monkeypatch.delenv("AI_TEAM_JUDGE_MODEL", raising=False)
        assert LLMJudge().identity.startswith("anthropic:")

    def test_provider_is_env_configurable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AI_TEAM_JUDGE_PROVIDER", "openrouter")
        monkeypatch.delenv("AI_TEAM_JUDGE_MODEL", raising=False)
        assert LLMJudge().identity.startswith("openrouter:")

    def test_model_is_env_configurable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AI_TEAM_JUDGE_PROVIDER", "openrouter")
        monkeypatch.setenv("AI_TEAM_JUDGE_MODEL", "some/other-model")
        assert LLMJudge().identity == "openrouter:some/other-model"

    def test_explicit_argument_beats_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AI_TEAM_JUDGE_PROVIDER", "anthropic")
        assert LLMJudge(provider="openrouter").identity.startswith("openrouter:")

    def test_unknown_provider_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown judge provider"):
            LLMJudge(provider="not-a-provider")

    def test_openrouter_without_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        judge = LLMJudge(provider="openrouter")
        # check() swallows errors into a failed verdict; assert it does not silently pass.
        verdict = judge.check("criterion", "evidence")
        assert verdict.passed is False
        assert "OPENROUTER_API_KEY" in verdict.reason


class TestEnsembleAgreement:
    def test_reports_mean_and_spread(self) -> None:
        ensemble = EnsembleJudge([_StubJudge("a:1", 0.9), _StubJudge("b:2", 0.5)])
        out = ensemble.check("c", "e")
        assert out["score"] == pytest.approx(0.7)
        assert out["spread"] == pytest.approx(0.4)

    def test_flags_disagreement_as_contested(self) -> None:
        ensemble = EnsembleJudge([_StubJudge("a:1", 1.0), _StubJudge("b:2", 0.2)])
        assert ensemble.check("c", "e")["contested"] is True

    def test_close_scores_are_not_contested(self) -> None:
        ensemble = EnsembleJudge([_StubJudge("a:1", 0.80), _StubJudge("b:2", 0.75)])
        assert ensemble.check("c", "e")["contested"] is False

    def test_split_pass_vote_is_contested_even_when_scores_are_close(self) -> None:
        # Scores agree numerically but the boolean verdicts disagree — still contested.
        ensemble = EnsembleJudge(
            [_StubJudge("a:1", 0.55, passed=True), _StubJudge("b:2", 0.52, passed=False)]
        )
        assert ensemble.check("c", "e")["contested"] is True

    def test_detects_single_vendor_panel(self) -> None:
        ensemble = EnsembleJudge([_StubJudge("anthropic:x", 0.9), _StubJudge("anthropic:y", 0.9)])
        assert ensemble.is_single_vendor is True
        assert ensemble.check("c", "e")["single_vendor"] is True

    def test_detects_cross_vendor_panel(self) -> None:
        ensemble = EnsembleJudge([_StubJudge("anthropic:x", 0.9), _StubJudge("openrouter:y", 0.9)])
        assert ensemble.is_single_vendor is False
        assert ensemble.check("c", "e")["single_vendor"] is False

    def test_records_every_judge_for_provenance(self) -> None:
        ensemble = EnsembleJudge([_StubJudge("anthropic:x", 0.9), _StubJudge("openrouter:y", 0.4)])
        judges = ensemble.check("c", "e")["judges"]
        assert set(judges) == {"anthropic:x", "openrouter:y"}

    def test_empty_panel_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one judge"):
            EnsembleJudge([])


class TestJudgeJsonParsing:
    def test_parses_plain_json(self) -> None:
        v = _parse_judge_json('{"passed": true, "score": 0.8, "reason": "ok"}')
        assert (v.passed, v.score) == (True, 0.8)

    def test_strips_markdown_fences(self) -> None:
        v = _parse_judge_json('```json\n{"passed": false, "score": 0.1, "reason": "no"}\n```')
        assert (v.passed, v.score) == (False, 0.1)

    def test_empty_response_raises(self) -> None:
        with pytest.raises(ValueError, match="empty response"):
            _parse_judge_json("   ")
