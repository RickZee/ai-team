"""Risk-class guardrail dispatch and evidence bundle."""

from __future__ import annotations

from types import SimpleNamespace

from ai_team.harness.guardrail_risk import build_guardrail_evidence, should_run


def test_low_skips_scope_customer_visible_runs_it() -> None:
    assert should_run("scope", "low") is False
    assert should_run("secrets", "low") is True
    assert should_run("scope", "customer-visible") is True
    assert should_run("code_quality", "customer-visible") is True


def test_evidence_lists_override() -> None:
    events = [
        SimpleNamespace(
            name="scope", status="skipped", message="profile override", category="behavioral"
        )
    ]
    bundle = build_guardrail_evidence(
        policy_version="1",
        events=events,
        overrides=["scope:skipped"],
        permission_set=["read_file"],
    )
    assert bundle["overrides"] == ["scope:skipped"]
    assert bundle["checks"][0]["name"] == "scope"
