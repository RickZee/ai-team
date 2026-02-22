"""
Unit tests for token_tracker: record, total_cost, summary, save_report, hook registration.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_team.config.cost_estimator import RoleCostRow
from ai_team.config.token_tracker import (
    TokenTracker,
    _estimate_tokens,
    _normalize_role,
)


class TestEstimateTokens:
    """Tests for _estimate_tokens."""

    def test_empty_zero(self) -> None:
        assert _estimate_tokens("") == 0

    def test_rough_four_chars_per_token(self) -> None:
        assert _estimate_tokens("abcd") == 1
        assert _estimate_tokens("a" * 8) == 2


class TestNormalizeRole:
    """Tests for _normalize_role."""

    def test_backend_developer(self) -> None:
        assert _normalize_role("Backend Developer") == "backend_developer"

    def test_devops_engineer_to_devops(self) -> None:
        assert _normalize_role("DevOps Engineer") == "devops"

    def test_empty_unknown(self) -> None:
        assert _normalize_role("") == "unknown"


class TestTokenTracker:
    """Tests for TokenTracker."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        s = MagicMock()
        s.max_cost_per_run = 10.0
        return s

    def test_record_and_total_cost(self, mock_settings: MagicMock) -> None:
        tracker = TokenTracker(mock_settings)
        assert tracker.total_cost == 0.0
        tracker.record("manager", 100, 50, 0.01)
        tracker.record("architect", 200, 100, 0.02)
        assert tracker.total_cost == 0.03

    def test_summary_no_estimated_rows(self, mock_settings: MagicMock) -> None:
        tracker = TokenTracker(mock_settings)
        tracker.record("manager", 100, 50, 0.01)
        tracker.summary(None)  # no crash

    def test_summary_with_estimated_rows(self, mock_settings: MagicMock) -> None:
        tracker = TokenTracker(mock_settings)
        tracker.record("manager", 80, 40, 0.008)
        rows = [
            RoleCostRow(
                role="manager",
                model_id="test/model",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.01,
            ),
        ]
        tracker.summary(rows)  # no crash

    def test_save_report_creates_file(self, mock_settings: MagicMock, tmp_path: Path) -> None:
        tracker = TokenTracker(mock_settings)
        tracker.record("manager", 100, 50, 0.01)
        path = tracker.save_report(logs_dir=tmp_path)
        assert path.exists()
        assert path.name.startswith("cost_report_")
        assert path.suffix == ".json"
        data = path.read_text()
        assert "total_cost_usd" in data
        assert "by_role" in data
        assert "manager" in data

    def test_register_unregister_hook_no_crash(self, mock_settings: MagicMock) -> None:
        tracker = TokenTracker(mock_settings)
        tracker.register_crewai_hook()
        tracker.unregister_crewai_hook()
