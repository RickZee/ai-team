"""Tests for the CrewAI dollar-budget guard (Gap 2).

CrewAI routes LLM calls through LiteLLM. A LiteLLM success callback feeds the
shared spend guard so the per-run budget ceiling (AI_TEAM_RUN_BUDGET_USD) can
abort a runaway crash/retry loop — previously CrewAI had only an *error-count*
budget (MAX_RUN_ERRORS), not a dollar ceiling.

Key property: the abort must survive LiteLLM's callback dispatch. LiteLLM wraps
success callbacks in `except Exception` (treating failures as non-blocking), so
BudgetExceededError subclasses BaseException to bypass that catch and propagate.
"""

from __future__ import annotations

import pytest
from ai_team.core.spend_guard import (
    BudgetExceededError,
    current_spend,
    reset_spend_guard,
)


@pytest.fixture(autouse=True)
def _budget() -> None:
    reset_spend_guard(1.0)


class _FakeUsage:
    def __init__(self, total_tokens: int) -> None:
        self.total_tokens = total_tokens


class _FakeResponse:
    def __init__(self, total_tokens: int = 0) -> None:
        self.usage = _FakeUsage(total_tokens)


def _make_logger():
    """Build the LiteLLM CustomLogger that the registrar installs."""
    # Reset module-level guard so we register fresh, then pull the logger back out
    # of litellm.callbacks for direct invocation.
    import ai_team.config.llm_observability as obs
    from ai_team.config.llm_observability import register_crewai_spend_guard

    obs._SPEND_GUARD_REGISTERED = False
    import litellm

    before = list(getattr(litellm, "callbacks", []))
    register_crewai_spend_guard()
    new = [c for c in litellm.callbacks if c not in before]
    assert new, "spend guard logger was not registered"
    return new[-1]


class TestCrewaiSpendCallback:
    def test_records_response_cost(self) -> None:
        logger = _make_logger()
        logger.log_success_event({"response_cost": 0.20}, _FakeResponse(300), None, None)
        snap = current_spend()
        assert snap["spent_usd"] == pytest.approx(0.20)
        assert snap["total_tokens"] == 300

    def test_missing_cost_is_zero(self) -> None:
        logger = _make_logger()
        logger.log_success_event({}, _FakeResponse(100), None, None)
        assert current_spend()["spent_usd"] == 0.0
        assert current_spend()["total_tokens"] == 100

    def test_malformed_cost_does_not_crash(self) -> None:
        logger = _make_logger()
        logger.log_success_event({"response_cost": "n/a"}, _FakeResponse(0), None, None)
        assert current_spend()["spent_usd"] == 0.0

    def test_abort_raises_base_exception_not_exception(self) -> None:
        """The abort must bypass LiteLLM's `except Exception` non-blocking catch."""
        reset_spend_guard(0.05)
        logger = _make_logger()
        with pytest.raises(BudgetExceededError):
            logger.log_success_event({"response_cost": 0.10}, _FakeResponse(0), None, None)

    def test_register_is_idempotent(self) -> None:
        import ai_team.config.llm_observability as obs
        import litellm

        obs._SPEND_GUARD_REGISTERED = False
        litellm.callbacks = []
        from ai_team.config.llm_observability import register_crewai_spend_guard

        register_crewai_spend_guard()
        count_after_first = len(litellm.callbacks)
        register_crewai_spend_guard()
        assert len(litellm.callbacks) == count_after_first


class TestBudgetExceededSemantics:
    def test_is_base_not_exception(self) -> None:
        assert issubclass(BudgetExceededError, BaseException)
        assert not issubclass(BudgetExceededError, Exception)
