"""
Comprehensive unit tests for guardrails: behavioral, security, quality;
known-bad inputs; pass/fail return signatures; chaining and ordering.
"""

from unittest.mock import patch

import pytest
from pydantic import BaseModel, Field

from ai_team.guardrails.behavioral import (
    GuardrailResult as BehavioralGuardrailResult,
    delegation_guardrail,
    iteration_limit_guardrail,
    make_output_format_guardrail,
    make_role_adherence_guardrail,
    make_scope_control_guardrail,
    role_adherence_guardrail,
    scope_control_guardrail,
    output_format_guardrail,
)
from ai_team.guardrails.security import (
    GuardrailResult as SecurityGuardrailResult,
    code_safety_guardrail,
    pii_redaction_guardrail,
    secret_detection_guardrail,
    path_security_guardrail,
)
from ai_team.guardrails.quality import (
    GuardrailResult as QualityGuardrailResult,
    code_quality_guardrail,
    coverage_guardrail,
    documentation_guardrail,
)


# -----------------------------------------------------------------------------
# Behavioral guardrails in isolation
# -----------------------------------------------------------------------------


class TestBehavioralGuardrailsIsolation:
    def test_role_adherence_guardrail_qa_pass(self) -> None:
        out = "def test_login(): assert login() is True"
        result = role_adherence_guardrail(out, "qa_engineer")
        assert result.status == "pass"
        assert result.retry_allowed is True

    def test_role_adherence_guardrail_qa_fail_production_code(self) -> None:
        out = "def get_user(user_id: int): return db.query(User).get(user_id)"
        result = role_adherence_guardrail(out, "qa_engineer")
        assert result.status == "fail"
        assert result.message

    def test_scope_control_guardrail_pass(self) -> None:
        result = scope_control_guardrail(
            "Implemented user login and logout with Redis.",
            "Implement user login and logout with session management.",
        )
        assert result.status == "pass"

    def test_scope_control_guardrail_fail_off_scope(self) -> None:
        result = scope_control_guardrail(
            "The weather is sunny. Frogs are amphibians.",
            "Implement user login and session management.",
            min_relevance=0.5,
        )
        assert result.status == "fail"

    def test_delegation_guardrail_manager_pass(self) -> None:
        result = delegation_guardrail("manager", "backend_developer", "Implement API")
        assert result.status == "pass"

    def test_delegation_guardrail_individual_contributor_fail(self) -> None:
        result = delegation_guardrail(
            "backend_developer", "frontend_developer", "Build UI"
        )
        assert result.status == "fail"
        assert "delegate" in result.message.lower() or "allowed" in result.message.lower()

    def test_iteration_limit_guardrail_pass(self) -> None:
        result = iteration_limit_guardrail(3, 10)
        assert result.status == "pass"
        assert result.details["current_iteration"] == 3
        assert result.details["max_iterations"] == 10

    def test_iteration_limit_guardrail_fail_at_limit(self) -> None:
        result = iteration_limit_guardrail(10, 10)
        assert result.status == "fail"
        assert result.retry_allowed is False


class _SimpleModel(BaseModel):
    title: str = Field(...)
    count: int = Field(default=0)


def test_output_format_guardrail_pass() -> None:
    result = output_format_guardrail('{"title": "Report", "count": 5}', _SimpleModel)
    assert result.status == "pass"


def test_output_format_guardrail_fail_invalid_json() -> None:
    result = output_format_guardrail('{"title": "Report", count: 5}', _SimpleModel)
    assert result.status == "fail"
    assert "json" in result.message.lower() or "JSON" in result.message


# -----------------------------------------------------------------------------
# Security guardrails with known-bad inputs
# -----------------------------------------------------------------------------


class TestSecurityGuardrailsKnownBad:
    def test_code_safety_pass_clean(self) -> None:
        r = code_safety_guardrail("def foo(): return 1")
        assert r.status == "pass"

    def test_code_safety_fail_eval(self) -> None:
        r = code_safety_guardrail("x = eval(user_input)")
        assert r.status == "fail"
        assert "eval" in r.message.lower() or "dangerous" in r.message.lower()

    def test_code_safety_fail_exec(self) -> None:
        r = code_safety_guardrail("exec(code)")
        assert r.status == "fail"

    def test_code_safety_fail_os_system(self) -> None:
        r = code_safety_guardrail("os.system('rm -rf /')")
        assert r.status == "fail"

    def test_pii_pass_no_pii(self) -> None:
        r = pii_redaction_guardrail("Hello world")
        assert r.status == "pass"
        assert r.details and r.details.get("redacted") == "Hello world"

    def test_pii_redact_email(self) -> None:
        r = pii_redaction_guardrail("Contact alice@example.com")
        assert r.status in ("pass", "warn")
        assert "alice@example.com" not in (r.details or {}).get("redacted", "")

    def test_secret_detection_fail_api_key(self) -> None:
        r = secret_detection_guardrail("api_key = 'sk-1234567890abcdef'")
        assert r.status == "fail" or "secret" in (r.message or "").lower()

    def test_path_security_fail_traversal(self) -> None:
        with patch("ai_team.guardrails.security.get_settings") as m:
            m.return_value.project.workspace_dir = "/allowed/workspace"
            m.return_value.project.output_dir = "/allowed/output"
            r = path_security_guardrail("../../../etc/passwd")
        assert r.status == "fail" or "path" in (r.message or "").lower()


# -----------------------------------------------------------------------------
# Quality guardrails with known-low-quality inputs
# -----------------------------------------------------------------------------


class TestQualityGuardrailsKnownLowQuality:
    def test_code_quality_pass_good_python(self) -> None:
        code = '''
"""Doc."""
def add(a: int, b: int) -> int:
    """Add."""
    return a + b
'''
        result = code_quality_guardrail(code, "python")
        assert isinstance(result, QualityGuardrailResult)
        assert result.passed is True

    def test_code_quality_fail_syntax_error(self) -> None:
        result = code_quality_guardrail("def broken( ", "python")
        assert result.passed is False
        assert "syntax" in result.message.lower() or "Invalid" in result.message

    def test_coverage_guardrail_pass_above_threshold(self) -> None:
        result = coverage_guardrail(
            {"total_coverage": 0.85, "files": {"a.py": 85}},
            min_coverage_threshold=0.8,
        )
        assert result.passed is True

    def test_coverage_guardrail_fail_below_threshold(self) -> None:
        result = coverage_guardrail(
            {"total_coverage": 0.5, "files": {"a.py": 50}},
            min_coverage_threshold=0.8,
        )
        assert result.passed is False

    def test_documentation_guardrail_has_suggestions(self) -> None:
        result = documentation_guardrail("def foo(): pass", "")
        assert isinstance(result, QualityGuardrailResult)
        assert hasattr(result, "suggestions")


# -----------------------------------------------------------------------------
# Guardrail pass/fail return signatures
# -----------------------------------------------------------------------------


class TestGuardrailPassFailSignatures:
    def test_behavioral_guardrail_result_signature(self) -> None:
        r = BehavioralGuardrailResult(
            status="fail",
            message="test",
            details={"violations": []},
            retry_allowed=False,
        )
        assert r.status == "fail"
        assert r.message == "test"
        assert r.details == {"violations": []}
        assert r.retry_allowed is False
        r2 = BehavioralGuardrailResult.model_validate(r.model_dump())
        assert r2.status == r.status

    def test_security_guardrail_result_is_ok_and_should_block(self) -> None:
        assert SecurityGuardrailResult(status="pass", message="ok").is_ok() is True
        assert SecurityGuardrailResult(status="fail", message="no").should_block() is True
        assert SecurityGuardrailResult(status="warn", message="w").should_block() is False

    def test_quality_guardrail_result_score_clamped(self) -> None:
        r = QualityGuardrailResult(
            passed=True, score=150, message="x", suggestions=[]
        )
        assert r.score == 100
        r2 = QualityGuardrailResult(
            passed=False, score=-10, message="y", suggestions=[]
        )
        assert r2.score == 0


# -----------------------------------------------------------------------------
# Guardrail chaining and ordering
# -----------------------------------------------------------------------------


class TestGuardrailChainingAndOrdering:
    """Test that multiple guardrails can be chained and order is respected."""

    def test_chain_behavioral_then_security(self) -> None:
        """Run role_adherence then code_safety; both must pass for overall pass."""
        output = "def get_user(): return db.query(User).first()"
        r1 = role_adherence_guardrail(output, "backend_developer")
        r2 = code_safety_guardrail(output)
        assert r1.status == "pass"
        assert r2.status == "pass"

    def test_chain_fail_first_guardrail(self) -> None:
        """If first guardrail fails, chain can short-circuit conceptually."""
        output = "const x = React.useState(0);"
        r1 = role_adherence_guardrail(output, "backend_developer")
        assert r1.status == "fail"
        # Security would still run if we called it; we assert first failure
        r2 = code_safety_guardrail(output)
        assert r2.status == "pass"  # code is safe, just wrong role

    def test_ordering_scope_then_output_format(self) -> None:
        """Scope control then output format: both applied in sequence."""
        requirements = "Return a JSON report with title and count."
        output = '{"title": "Report", "count": 1}'
        scope_result = scope_control_guardrail(output, requirements)
        format_result = output_format_guardrail(output, _SimpleModel)
        assert scope_result.status == "pass"
        assert format_result.status == "pass"

    def test_crewai_callables_chain(self) -> None:
        """CrewAI-style callables (True/False) can be combined with and."""
        role_fn = make_role_adherence_guardrail("backend_developer")
        format_fn = make_output_format_guardrail(_SimpleModel)
        good = "def get_user(): return 1"
        assert role_fn(good) is True
        assert format_fn('{"title": "A", "count": 0}') is True
        assert role_fn("const x = React.useState(0)") is False
        assert format_fn("not json") is False
