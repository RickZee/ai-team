"""
Unit tests for cost_estimator: complexity, estimate_run_cost, confirm_and_proceed.
"""

from unittest.mock import MagicMock, patch

import pytest

from ai_team.config.cost_estimator import (
    COMPLEXITY_MULTIPLIERS,
    RETRY_BUFFER,
    RoleCostRow,
    confirm_and_proceed,
    estimate_run_cost,
    get_complexity_from_description,
)
from ai_team.config.models import Environment, ModelPricing, OpenRouterSettings, RoleModelConfig


class TestGetComplexityFromDescription:
    """Tests for get_complexity_from_description."""

    def test_empty_returns_medium(self) -> None:
        assert get_complexity_from_description("") == "medium"
        assert get_complexity_from_description("   ") == "medium"

    def test_short_description_simple(self) -> None:
        short = " ".join(["word"] * 50)
        assert get_complexity_from_description(short) == "simple"

    def test_long_no_keywords_medium(self) -> None:
        long = " ".join(["word"] * 150)
        assert get_complexity_from_description(long) == "medium"

    def test_complex_keywords(self) -> None:
        text = "Build a system with microservices and ML pipelines."
        assert get_complexity_from_description(text) == "complex"

    def test_complex_keyword_kubernetes(self) -> None:
        text = "Deploy on Kubernetes with multi-tenant support."
        assert get_complexity_from_description(text) == "complex"


class TestEstimateRunCost:
    """Tests for estimate_run_cost with mocked OpenRouterSettings."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """OpenRouterSettings mock with get_model_for_role returning fixed pricing."""
        pricing = ModelPricing(1.0, 1.0)  # $1 per M input/output
        config = RoleModelConfig(
            model_id="test/model",
            pricing=pricing,
            temperature=0.7,
            max_tokens=4096,
        )
        s = MagicMock(spec=OpenRouterSettings)
        s.get_model_for_role.return_value = config
        s.max_cost_per_run = 100.0
        s.ai_team_env = Environment.DEV
        s.show_cost_estimate = True
        s.prod_confirm = True
        return s

    def test_returns_rows_and_total(self, mock_settings: MagicMock) -> None:
        rows, total, within = estimate_run_cost(mock_settings, "medium")
        assert len(rows) == len(
            {"manager", "product_owner", "architect", "backend_developer", "frontend_developer", "fullstack_developer", "cloud_engineer", "devops", "qa_engineer"}
        )
        assert all(isinstance(r, RoleCostRow) for r in rows)
        assert total > 0
        assert total == round(total, 4)
        assert within is True

    def test_complexity_multiplier_simple(self, mock_settings: MagicMock) -> None:
        _, total_simple, _ = estimate_run_cost(mock_settings, "simple")
        _, total_medium, _ = estimate_run_cost(mock_settings, "medium")
        # Both totals include same retry buffer; ratio is just complexity multiplier
        mult_s = COMPLEXITY_MULTIPLIERS["simple"]
        mult_m = COMPLEXITY_MULTIPLIERS["medium"]
        expected_ratio = mult_s / mult_m  # 0.5
        assert abs((total_simple / total_medium) - expected_ratio) < 0.01

    def test_within_budget_when_under(self, mock_settings: MagicMock) -> None:
        mock_settings.max_cost_per_run = 1000.0
        _, total, within = estimate_run_cost(mock_settings, "medium")
        assert within is True

    def test_over_budget_when_over(self, mock_settings: MagicMock) -> None:
        mock_settings.max_cost_per_run = 0.001
        _, total, within = estimate_run_cost(mock_settings, "complex")
        assert within is False


class TestConfirmAndProceed:
    """Tests for confirm_and_proceed (DEV auto-confirm; TEST/PROD can require input)."""

    @pytest.fixture
    def dev_settings(self) -> MagicMock:
        s = MagicMock(spec=OpenRouterSettings)
        s.ai_team_env = Environment.DEV
        s.prod_confirm = True
        return s

    @pytest.fixture
    def test_settings(self) -> MagicMock:
        s = MagicMock(spec=OpenRouterSettings)
        s.ai_team_env = Environment.TEST
        s.prod_confirm = True
        return s

    def test_dev_auto_confirms(self, dev_settings: MagicMock) -> None:
        assert confirm_and_proceed(dev_settings, "medium", 1.5) is True

    def test_test_requires_input_default_no(self, test_settings: MagicMock) -> None:
        with patch("ai_team.config.cost_estimator.input", return_value="n"):
            assert confirm_and_proceed(test_settings, "medium", 1.5) is False
        with patch("ai_team.config.cost_estimator.input", return_value=""):
            assert confirm_and_proceed(test_settings, "medium", 1.5) is False

    def test_test_proceeds_on_yes(self, test_settings: MagicMock) -> None:
        with patch("ai_team.config.cost_estimator.input", return_value="y"):
            assert confirm_and_proceed(test_settings, "medium", 1.5) is True
        with patch("ai_team.config.cost_estimator.input", return_value="yes"):
            assert confirm_and_proceed(test_settings, "medium", 1.5) is True

    def test_prod_confirm_false_auto_proceeds(self) -> None:
        s = MagicMock(spec=OpenRouterSettings)
        s.ai_team_env = Environment.PROD
        s.prod_confirm = False
        assert confirm_and_proceed(s, "medium", 1.5) is True
