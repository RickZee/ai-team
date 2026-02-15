"""Unit tests for quality guardrails with passing and failing examples."""

import pytest
from unittest.mock import patch

from ai_team.guardrails.quality import (
    GuardrailResult,
    code_quality_guardrail,
    coverage_guardrail,
    documentation_guardrail,
    architecture_compliance_guardrail,
    dependency_guardrail,
)


# -----------------------------------------------------------------------------
# GuardrailResult
# -----------------------------------------------------------------------------


class TestGuardrailResult:
    def test_score_clamped_to_0_100(self) -> None:
        r = GuardrailResult(passed=True, score=150, message="x", suggestions=[])
        assert r.score == 100
        r2 = GuardrailResult(passed=False, score=-10, message="y", suggestions=[])
        assert r2.score == 0


# -----------------------------------------------------------------------------
# code_quality_guardrail — passing / failing
# -----------------------------------------------------------------------------

GOOD_PYTHON = '''
"""Module docstring."""

def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

def get_name() -> str:
    """Return a constant name."""
    return "ok"
'''

BAD_PYTHON_LONG_FN = '''
def too_long() -> None:
    """This function is way over 50 lines."""
    x = 1
''' + "\n".join(["    y = 2"] * 55)

BAD_PYTHON_TODO = '''
def work() -> None:
    # TODO: implement later
    pass
'''

BAD_PYTHON_NO_DOCSTRING = '''
def public_func(x: int) -> int:
    return x + 1
'''

BAD_PYTHON_NAMING = '''
def BadCamelCase() -> int:
    """Ok."""
    return 0
'''


class TestCodeQualityGuardrail:
    def test_passing_python(self) -> None:
        result = code_quality_guardrail(GOOD_PYTHON, "python")
        assert isinstance(result, GuardrailResult)
        assert result.passed is True
        assert result.score >= 70
        assert len(result.suggestions) == 0

    def test_failing_syntax_error(self) -> None:
        result = code_quality_guardrail("def broken( ", "python")
        assert result.passed is False
        assert result.score == 0
        assert "syntax" in result.message.lower() or "Invalid" in result.message

    def test_failing_todo(self) -> None:
        result = code_quality_guardrail(BAD_PYTHON_TODO, "python")
        assert isinstance(result, GuardrailResult)
        assert any("TODO" in s or "FIXME" in s for s in result.suggestions)

    def test_failing_no_docstring(self) -> None:
        result = code_quality_guardrail(BAD_PYTHON_NO_DOCSTRING, "python")
        assert any("docstring" in s.lower() for s in result.suggestions)

    def test_failing_naming(self) -> None:
        result = code_quality_guardrail(BAD_PYTHON_NAMING, "python")
        assert any("snake_case" in s or "naming" in s.lower() for s in result.suggestions)

    def test_js_camel_case(self) -> None:
        good_js = "function doSomething() { return 1; }"
        result = code_quality_guardrail(good_js, "javascript")
        assert isinstance(result, GuardrailResult)


# -----------------------------------------------------------------------------
# coverage_guardrail — passing / failing
# -----------------------------------------------------------------------------


class TestTestCoverageGuardrail:
    def test_passing_above_threshold(self) -> None:
        report = {"total_coverage": 0.85, "files": {"a.py": 90, "b.py": 80}}
        result = coverage_guardrail(report, min_coverage_threshold=0.8)
        assert result.passed is True
        assert result.score >= 80

    def test_failing_below_threshold(self) -> None:
        report = {"total_coverage": 0.5, "files": {"a.py": 50}}
        result = coverage_guardrail(report, min_coverage_threshold=0.8)
        assert result.passed is False
        assert any("below" in s.lower() or "coverage" in s.lower() for s in result.suggestions)

    def test_flags_zero_coverage_files(self) -> None:
        report = {
            "total_coverage": 0.9,
            "files": {"a.py": 100, "b.py": 0, "c.py": 0},
        }
        result = coverage_guardrail(report, min_coverage_threshold=0.8)
        assert result.passed is True
        assert any("0%" in s for s in result.suggestions)

    def test_uses_settings_threshold_when_not_passed(self) -> None:
        report = {"total_coverage": 0.7}
        with patch("ai_team.guardrails.quality.get_settings") as m:
            m.return_value.guardrails.test_coverage_min = 0.6
            result = coverage_guardrail(report)
            assert result.passed is True


# -----------------------------------------------------------------------------
# documentation_guardrail — passing / failing
# -----------------------------------------------------------------------------


class TestDocumentationGuardrail:
    def test_failing_empty_readme(self) -> None:
        result = documentation_guardrail("def f(): pass", "")
        assert any("README" in s for s in result.suggestions)
        assert result.passed is False or result.score < 100

    def test_passing_with_readme_and_docstring(self) -> None:
        code = '''
def add(a: int, b: int) -> int:
    """Add two numbers.
    Args:
        a: first number
        b: second number
    Returns:
        Sum of a and b.
    """
    return a + b
'''
        result = documentation_guardrail(code, "# Project README\n\nDescription here.")
        assert result.passed is True or result.score >= 70

    def test_failing_public_function_no_docstring(self) -> None:
        code = "def public_api(x): return x"
        result = documentation_guardrail(code, "README content")
        assert any("docstring" in s.lower() for s in result.suggestions)


# -----------------------------------------------------------------------------
# architecture_compliance_guardrail — passing / failing
# -----------------------------------------------------------------------------


class TestArchitectureComplianceGuardrail:
    def test_passing_allowed_modules(self) -> None:
        arch = {"allowed_modules": ["src/", "tests/"]}
        result = architecture_compliance_guardrail(
            ["src/ai_team/main.py", "tests/unit/test_foo.py"],
            arch,
        )
        assert result.passed is True
        assert len(result.suggestions) == 0

    def test_failing_outside_layers(self) -> None:
        arch = {"allowed_modules": ["src/"]}
        result = architecture_compliance_guardrail(
            ["scripts/random_script.py"],
            arch,
        )
        assert any("outside" in s.lower() or "architecture" in s.lower() for s in result.suggestions)

    def test_forbidden_imports(self) -> None:
        arch = {"forbidden_imports": ["legacy/"]}
        result = architecture_compliance_guardrail(
            ["legacy/old_module.py"],
            arch,
        )
        assert len(result.suggestions) >= 1


# -----------------------------------------------------------------------------
# dependency_guardrail — passing / failing
# -----------------------------------------------------------------------------


class TestDependencyGuardrail:
    def test_passing_pinned(self) -> None:
        reqs = "requests==2.31.0\npydantic==2.7.0\n"
        result = dependency_guardrail(reqs)
        assert result.passed is True
        assert result.score >= 80

    def test_failing_unpinned(self) -> None:
        reqs = "requests\nflask\n"
        result = dependency_guardrail(reqs)
        assert any("Unpinned" in s or "pin" in s.lower() for s in result.suggestions)

    def test_actionable_suggestions(self) -> None:
        reqs = "requests\n"
        result = dependency_guardrail(reqs)
        assert isinstance(result, GuardrailResult)
        assert result.suggestions
