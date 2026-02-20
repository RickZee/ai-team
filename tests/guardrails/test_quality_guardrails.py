"""
Comprehensive guardrail effectiveness tests for quality guardrails.

Covers code quality, test coverage, and output format (structured output).
Uses realistic AI-generated style inputs.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, Field

from ai_team.guardrails.behavioral import output_format_guardrail
from ai_team.guardrails.quality import (
    GuardrailResult,
    code_quality_guardrail,
    coverage_guardrail,
)


# -----------------------------------------------------------------------------
# Code quality
# -----------------------------------------------------------------------------


def test_python_code_with_syntax_error_fails_with_specific_message(
    task_output_factory: Any,
) -> None:
    """Python code with syntax error should fail with specific message."""
    raw = (
        "def process_data(input_data):\n"
        "    result = input_data.map(lambda x: x  # missing closing paren\n"
        "    return result\n"
    )
    result = code_quality_guardrail(raw, "python")
    assert result.passed is False
    assert result.score == 0
    assert "syntax" in result.message.lower() or "Invalid" in result.message


def test_code_with_no_error_handling_on_io_fails(task_output_factory: Any) -> None:
    """Code with no error handling on I/O should fail (quality suggestion)."""
    raw = (
        "def read_config(path):\n"
        "    f = open(path)\n"
        "    data = f.read()\n"
        "    f.close()\n"
        "    return data\n"
    )
    result = code_quality_guardrail(raw, "python")
    assert result.passed is False or any(
        "error handling" in s.lower() or "try" in s.lower() or "with" in s.lower()
        for s in result.suggestions
    )
    assert any(
        "open" in s.lower() or "I/O" in s or "file" in s.lower()
        for s in result.suggestions
    )


def test_code_with_hardcoded_credentials_fails(task_output_factory: Any) -> None:
    """Code with hardcoded credentials should fail."""
    raw = (
        "api_key = \"sk-1234567890abcdef\"\n"
        "def call_api():\n"
        "    return requests.get(url, headers={'Authorization': api_key})\n"
    )
    result = code_quality_guardrail(raw, "python")
    assert result.passed is False or any(
        "credential" in s.lower() or "environment" in s.lower()
        for s in result.suggestions
    )


def test_well_structured_code_passes(task_output_factory: Any) -> None:
    """Well-structured code should pass."""
    raw = (
        '"""Module for user helpers."""\n'
        "\n"
        "def get_user_name(user_id: int) -> str:\n"
        '    """Return display name for user.\n'
        "    Args:\n"
        "        user_id: Primary key.\n"
        "    Returns:\n"
        "        Display name.\n"
        '    """\n'
        "    user = fetch_user(user_id)\n"
        "    return user.display_name or 'Unknown'\n"
    )
    result = code_quality_guardrail(raw, "python")
    assert result.passed is True
    assert result.score >= 70
    assert len(result.suggestions) == 0


# -----------------------------------------------------------------------------
# Test coverage
# -----------------------------------------------------------------------------


def test_output_with_zero_test_cases_when_tests_expected_fails(
    task_output_factory: Any,
) -> None:
    """Output with 0 test cases / 0% coverage when tests expected should fail."""
    report = {"total_coverage": 0.0, "files": {"main.py": 0, "api.py": 0}}
    result = coverage_guardrail(report, min_coverage_threshold=0.8)
    assert result.passed is False
    assert any(
        "below" in s.lower() or "coverage" in s.lower() or "0%" in s
        for s in result.suggestions
    )


def test_output_with_tests_below_minimum_threshold_fails(
    task_output_factory: Any,
) -> None:
    """Output with coverage below minimum threshold should fail."""
    report = {"total_coverage": 0.45, "files": {"a.py": 40, "b.py": 50}}
    result = coverage_guardrail(report, min_coverage_threshold=0.8)
    assert result.passed is False
    assert result.score < 80


def test_output_with_adequate_test_cases_passes(task_output_factory: Any) -> None:
    """Output with adequate test cases / coverage should pass."""
    report = {"total_coverage": 0.88, "files": {"a.py": 90, "b.py": 86}}
    result = coverage_guardrail(report, min_coverage_threshold=0.8)
    assert result.passed is True
    assert result.score >= 80


# -----------------------------------------------------------------------------
# Output format (structured output — uses behavioral output_format_guardrail)
# -----------------------------------------------------------------------------


class _RequiredFieldsModel(BaseModel):
    """Minimal model with required fields for tests."""

    name: str = Field(..., description="Item name")
    count: int = Field(..., description="Count")


def test_malformed_json_when_json_expected_fails(task_output_factory: Any) -> None:
    """Malformed JSON when JSON expected should fail."""
    raw = "Here is the result: { name: \"foo\", count: 3 }"  # unquoted keys
    result = output_format_guardrail(raw, _RequiredFieldsModel)
    assert result.status == "fail"
    assert "JSON" in result.message or "json" in result.message


def test_missing_required_fields_in_structured_output_fails(
    task_output_factory: Any,
) -> None:
    """Missing required fields in structured output should fail."""
    raw = '{"name": "only"}'
    result = output_format_guardrail(raw, _RequiredFieldsModel)
    assert result.status == "fail"
    assert "format" in result.message.lower() or "match" in result.message.lower() or "validation" in result.message.lower() or "count" in result.message.lower()


def test_valid_structured_output_passes(task_output_factory: Any) -> None:
    """Valid structured output should pass."""
    raw = '{"name": "items", "count": 42}'
    result = output_format_guardrail(raw, _RequiredFieldsModel)
    assert result.status == "pass"
    assert result.details and result.details.get("expected_type") == "_RequiredFieldsModel"
