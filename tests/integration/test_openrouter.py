"""Integration tests for OpenRouter config, LLM factory, and cost estimation.

Gated tests (run with AI_TEAM_USE_REAL_LLM=1): LLM factory instance, OpenRouter
connectivity, env switching, cost estimation, embedder stays local.
Non-gated tests always run: model config structure, pricing completeness,
token budgets completeness.
"""

from __future__ import annotations

import os
import pytest
import httpx

from ai_team.config.cost_estimator import (
    COMPLEXITY_MULTIPLIERS,
    estimate_run_cost,
    get_complexity_from_description,
)
from ai_team.config.llm_factory import create_llm_for_role, get_embedder_config
from ai_team.config.models import (
    ENV_MODELS,
    ROLE_TOKEN_BUDGETS,
    Environment,
    OpenRouterSettings,
)


# -----------------------------------------------------------------------------
# Non-gated tests (always run)
# -----------------------------------------------------------------------------


class TestModelConfigStructure:
    """Verify all roles have configs in all environments."""

    def test_model_config_structure(self) -> None:
        """All roles have configs in all envs."""
        expected_roles = set(ROLE_TOKEN_BUDGETS.keys())
        for env in Environment:
            role_configs = ENV_MODELS[env]
            assert set(role_configs.keys()) == expected_roles, (
                f"Environment {env.value}: role set mismatch"
            )
            for role in expected_roles:
                config = role_configs[role]
                assert config.model_id.startswith("openrouter/"), (
                    f"{env.value}/{role}: model_id must be openrouter/..."
                )
                assert config.temperature >= 0 and config.temperature <= 2
                assert config.max_tokens > 0


class TestPricingDataCompleteness:
    """All models have pricing entries."""

    def test_pricing_data_completeness(self) -> None:
        """All models have pricing entries."""
        settings = OpenRouterSettings(OPENROUTER_API_KEY="dummy-for-structure-test")
        for env in Environment:
            for role, config in ENV_MODELS[env].items():
                cost = config.pricing.estimate(1_000, 1_000)
                assert cost >= 0, f"{env.value}/{role}: pricing must be non-negative"
                assert isinstance(cost, float), f"{env.value}/{role}: estimate must return float"


class TestTokenBudgetsCompleteness:
    """All roles have token budgets."""

    def test_token_budgets_completeness(self) -> None:
        """All roles have token budgets."""
        dev_roles = set(ENV_MODELS[Environment.DEV].keys())
        budget_roles = set(ROLE_TOKEN_BUDGETS.keys())
        assert budget_roles == dev_roles, (
            "ROLE_TOKEN_BUDGETS must have same roles as ENV_MODELS"
        )
        for role, budget in ROLE_TOKEN_BUDGETS.items():
            assert "input" in budget and "output" in budget
            assert budget["input"] > 0 and budget["output"] > 0


# -----------------------------------------------------------------------------
# Gated tests (AI_TEAM_USE_REAL_LLM=1)
# -----------------------------------------------------------------------------


@pytest.mark.real_llm
class TestOpenRouterGated:
    """Tests that require AI_TEAM_USE_REAL_LLM=1 (and optionally OPENROUTER_API_KEY)."""

    def test_llm_factory_creates_valid_instance(
        self,
        use_real_llm: bool,
    ) -> None:
        """create_llm_for_role() returns a CrewAI LLM with correct model_id and base_url."""
        if not use_real_llm:
            pytest.skip("Set AI_TEAM_USE_REAL_LLM=1 to run")
        settings = OpenRouterSettings(
            OPENROUTER_API_KEY=os.environ.get("OPENROUTER_API_KEY", "dummy"),
            OPENROUTER_API_BASE=os.environ.get(
                "OPENROUTER_API_BASE", "https://openrouter.ai/api/v1"
            ),
        )
        role = "backend_developer"
        llm = create_llm_for_role(role, settings)
        role_config = settings.get_model_for_role(role)
        assert llm is not None
        assert getattr(llm, "model", None) == role_config.model_id, (
            "LLM model must match role config model_id"
        )
        # Factory sets base via env; LiteLLM uses OPENROUTER_API_BASE
        assert os.environ.get("OPENROUTER_API_BASE") == settings.openrouter_api_base
        assert os.environ.get("OPENROUTER_API_KEY") == settings.openrouter_api_key

    def test_openrouter_connectivity(
        self,
        use_real_llm: bool,
    ) -> None:
        """Minimal completion call to verify OpenRouter API key works (free-tier model)."""
        if not use_real_llm:
            pytest.skip("Set AI_TEAM_USE_REAL_LLM=1 to run")
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key or api_key == "dummy":
            pytest.skip("Set OPENROUTER_API_KEY to run OpenRouter connectivity test")
        base = os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
        url = f"{base.rstrip('/')}/chat/completions"
        payload = {
            "model": "stepfun/step-3.5-flash:free",
            "messages": [{"role": "user", "content": "Reply with one word: OK"}],
            "max_tokens": 10,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        except httpx.RequestError as e:
            pytest.skip(f"OpenRouter request failed: {e}")
        assert resp.status_code == 200, (
            f"OpenRouter API returned {resp.status_code}: {resp.text[:500]}"
        )
        data = resp.json()
        choices = data.get("choices", [])
        assert len(choices) >= 1, "OpenRouter must return at least one choice"
        content = choices[0].get("message", {}).get("content", "")
        assert isinstance(content, str), "Choice content must be a string (may be empty for some free-tier models)"

    def test_env_switching(
        self,
        use_real_llm: bool,
    ) -> None:
        """Switching AI_TEAM_ENV changes model assignments."""
        if not use_real_llm:
            pytest.skip("Set AI_TEAM_USE_REAL_LLM=1 to run")
        dev_manager = ENV_MODELS[Environment.DEV]["manager"].model_id
        prod_manager = ENV_MODELS[Environment.PROD]["manager"].model_id
        test_manager = ENV_MODELS[Environment.TEST]["manager"].model_id
        assert dev_manager != prod_manager, (
            "DEV and PROD must use different models for manager"
        )
        assert dev_manager != test_manager or test_manager != prod_manager, (
            "At least two environments must use different manager models"
        )
        assert "openrouter/" in dev_manager and "openrouter/" in prod_manager

    def test_cost_estimation(
        self,
        use_real_llm: bool,
    ) -> None:
        """Estimate output matches expected ranges."""
        if not use_real_llm:
            pytest.skip("Set AI_TEAM_USE_REAL_LLM=1 to run")
        settings = OpenRouterSettings(OPENROUTER_API_KEY="dummy")
        for complexity in ("simple", "medium", "complex"):
            rows, total_with_buffer, within_budget = estimate_run_cost(
                settings, complexity  # type: ignore[arg-type]
            )
            assert len(rows) == len(ROLE_TOKEN_BUDGETS)
            assert total_with_buffer > 0
            assert total_with_buffer < 500.0, "Sanity: total cost should be under $500"
            mult = COMPLEXITY_MULTIPLIERS[complexity]
            assert mult in (0.5, 1.0, 2.0)
            for r in rows:
                assert r.cost_usd >= 0
                assert r.input_tokens > 0 and r.output_tokens > 0
                assert r.model_id.startswith("openrouter/")
        assert isinstance(within_budget, bool)

    def test_embedder_uses_openrouter(
        self,
        use_real_llm: bool,
    ) -> None:
        """get_embedder_config() returns OpenRouter-backed embedder (openai provider)."""
        if not use_real_llm:
            pytest.skip("Set AI_TEAM_USE_REAL_LLM=1 to run")
        config = get_embedder_config()
        assert config.get("provider") == "openai"
        assert "config" in config
        assert "model_name" in config["config"]
        assert "openrouter" in config["config"]["model_name"].lower()


# -----------------------------------------------------------------------------
# Helpers used by cost / complexity (non-gated, quick checks)
# -----------------------------------------------------------------------------


class TestComplexityHelper:
    """Quick sanity on complexity inference (no real LLM)."""

    def test_get_complexity_from_description(self) -> None:
        """get_complexity_from_description returns simple/medium/complex."""
        assert get_complexity_from_description("") == "medium"
        assert get_complexity_from_description("short") == "simple"
        assert get_complexity_from_description("microservices and Kubernetes") == "complex"
