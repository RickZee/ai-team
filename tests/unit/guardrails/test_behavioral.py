"""Unit tests for behavioral guardrails with mock agent outputs."""

from pydantic import BaseModel, Field

from ai_team.guardrails.behavioral import (
    GuardrailResult,
    delegation_guardrail,
    guardrail_to_crewai_callable,
    iteration_limit_guardrail,
    make_output_format_guardrail,
    make_reasoning_guardrail,
    make_role_adherence_guardrail,
    make_scope_control_guardrail,
    output_format_guardrail,
    reasoning_guardrail,
    role_adherence_guardrail,
    scope_control_guardrail,
)


# -----------------------------------------------------------------------------
# role_adherence_guardrail
# -----------------------------------------------------------------------------


def test_role_adherence_guardrail_qa_engineer_pass():
    """QA output with only test code passes."""
    mock_output = """
    def test_user_login_succeeds():
        assert login("u", "p") is True
    class TestAuth:
        def test_token_valid(self):
            pass
    """
    result = role_adherence_guardrail(mock_output, "qa_engineer")
    assert result.status == "pass"
    assert result.retry_allowed is True


def test_role_adherence_guardrail_qa_engineer_fail_production_code():
    """QA output with production code fails."""
    mock_output = """
    def get_user_by_id(user_id: int):
        return db.query(User).get(user_id)
    """
    result = role_adherence_guardrail(mock_output, "qa_engineer")
    assert result.status == "fail"
    assert "test" in result.message.lower() or "production" in result.message.lower()
    assert result.details and "violations" in result.details


def test_role_adherence_guardrail_backend_fail_frontend():
    """Backend dev generating frontend code fails."""
    mock_output = """
    function App() {
      const [count, useState] = React.useState(0);
      return <div>{count}</div>;
    }
    """
    result = role_adherence_guardrail(mock_output, "backend_developer")
    assert result.status == "fail"
    assert "frontend" in result.message.lower() or "React" in result.message.lower()


def test_role_adherence_guardrail_backend_pass():
    """Backend dev with only API/database code passes."""
    mock_output = """
    from fastapi import APIRouter
    router = APIRouter()
    @router.get("/users")
    def list_users():
        return db.query(User).all()
    """
    result = role_adherence_guardrail(mock_output, "backend_developer")
    assert result.status == "pass"


def test_role_adherence_guardrail_product_owner_fail_implementation():
    """Product Owner writing implementation fails."""
    mock_output = """
    import os
    class Service:
        def run(self):
            return 42
    """
    result = role_adherence_guardrail(mock_output, "product_owner")
    assert result.status == "fail"


def test_role_adherence_guardrail_unknown_role_pass():
    """Unknown role has no restrictions and passes."""
    result = role_adherence_guardrail("anything at all", "unknown_role")
    assert result.status == "pass"


def test_role_adherence_guardrail_manager_fail_implementation():
    """Manager output with code implementation fails."""
    mock_output = "import json\n\ndef get_status():\n    return {'phase': 'dev'}\n"
    result = role_adherence_guardrail(mock_output, "manager")
    assert result.status == "fail"
    assert "manager" in result.message.lower() or "implementation" in result.message.lower()


# -----------------------------------------------------------------------------
# scope_control_guardrail
# -----------------------------------------------------------------------------


def test_scope_control_guardrail_pass():
    """Output aligned with requirements passes."""
    requirements = "Implement user login and logout with session management."
    mock_output = "Implemented user login and logout with session management in Redis."
    result = scope_control_guardrail(mock_output, requirements)
    assert result.status == "pass"
    assert result.details and "relevance_ratio" in result.details


def test_scope_control_guardrail_fail_off_scope():
    """Output with low relevance fails."""
    requirements = "Implement user login and session management."
    mock_output = "The weather today is sunny. Frogs are amphibians. Coffee is great."
    result = scope_control_guardrail(mock_output, requirements, min_relevance=0.5)
    assert result.status == "fail"
    assert "scope" in result.message.lower() or "relevance" in result.message.lower()


def test_scope_control_guardrail_empty_requirements_pass():
    """Empty requirements yields pass (nothing to check)."""
    result = scope_control_guardrail("some output", "")
    assert result.status == "pass"


def test_scope_control_guardrail_creep_warn():
    """Output with possible scope creep can warn."""
    requirements = "Add login button."
    mock_output = "Added login button, signup flow, password reset, OAuth, and admin dashboard."
    result = scope_control_guardrail(
        mock_output, requirements, max_expansion=0.25, min_relevance=0.3
    )
    # May be pass or warn depending on keyword overlap
    assert result.status in ("pass", "warn")


# -----------------------------------------------------------------------------
# reasoning_guardrail
# -----------------------------------------------------------------------------


def test_reasoning_guardrail_short_no_indicators_fails():
    """Short output with no reasoning indicators fails."""
    result = reasoning_guardrail("Done.")
    assert result.status == "fail"


def test_reasoning_guardrail_with_rationale_passes():
    """Output with rationale passes."""
    result = reasoning_guardrail("We chose Redis because it supports TTL and is already in our stack.")
    assert result.status == "pass"


def test_reasoning_guardrail_long_passes():
    """Long enough output passes even without keywords."""
    result = reasoning_guardrail("This is a sufficiently long response that describes the approach in detail. " * 2)
    assert result.status == "pass"


def test_make_reasoning_guardrail_crewai():
    """make_reasoning_guardrail returns CrewAI callable (True/False)."""
    fn = make_reasoning_guardrail()
    assert fn("We decided to use JWT because it is stateless.") is True
    assert fn("No.") is False


# -----------------------------------------------------------------------------
# delegation_guardrail
# -----------------------------------------------------------------------------


def test_delegation_guardrail_manager_pass():
    """Manager delegating is allowed."""
    result = delegation_guardrail("manager", "backend_developer", "Implement API")
    assert result.status == "pass"


def test_delegation_guardrail_architect_pass():
    """Architect delegating is allowed."""
    result = delegation_guardrail("architect", "devops_engineer", "Set up CI/CD")
    assert result.status == "pass"


def test_delegation_guardrail_individual_contributor_fail():
    """Individual contributor cannot delegate."""
    result = delegation_guardrail("backend_developer", "frontend_developer", "Build UI")
    assert result.status == "fail"
    assert "delegate" in result.message.lower() or "allowed" in result.message.lower()


def test_delegation_guardrail_circular_fail():
    """Circular delegation fails."""
    result = delegation_guardrail(
        "manager",
        "architect",
        "Review design",
        delegation_chain=["manager", "architect"],
    )
    assert result.status == "fail"
    assert "circular" in result.message.lower()


def test_delegation_guardrail_no_circular_pass():
    """Non-circular chain passes."""
    result = delegation_guardrail(
        "manager",
        "backend_developer",
        "Implement feature",
        delegation_chain=["manager"],
    )
    assert result.status == "pass"


# -----------------------------------------------------------------------------
# output_format_guardrail
# -----------------------------------------------------------------------------


class _SimpleModel(BaseModel):
    """Minimal Pydantic model for tests."""

    title: str = Field(...)
    count: int = Field(default=0)


def test_output_format_guardrail_pass():
    """Valid JSON matching Pydantic model passes."""
    mock_output = '{"title": "Report", "count": 5}'
    result = output_format_guardrail(mock_output, _SimpleModel)
    assert result.status == "pass"
    assert result.details and result.details.get("expected_type") == "_SimpleModel"


def test_output_format_guardrail_pass_with_code_block():
    """JSON inside markdown code block passes."""
    mock_output = """Here is the result:
```json
{"title": "Report", "count": 1}
```
"""
    result = output_format_guardrail(mock_output, _SimpleModel)
    assert result.status == "pass"


def test_output_format_guardrail_fail_invalid_json():
    """Invalid JSON fails."""
    mock_output = '{"title": "Report", count: 5}'  # unquoted key
    result = output_format_guardrail(mock_output, _SimpleModel)
    assert result.status == "fail"
    assert "JSON" in result.message or "json" in result.message
    assert result.details and "json_error" in result.details


def test_output_format_guardrail_fail_validation_error():
    """JSON that doesn't match schema fails."""
    mock_output = '{"title": 123}'  # title must be str; count missing has default
    result = output_format_guardrail(mock_output, _SimpleModel)
    assert result.status == "fail"
    assert "format" in result.message.lower() or "match" in result.message.lower() or "validation" in result.message.lower()


def test_output_format_guardrail_fail_non_json_text():
    """Plain text that isn't JSON fails."""
    mock_output = "This is just a paragraph of text."
    result = output_format_guardrail(mock_output, _SimpleModel)
    assert result.status == "fail"


# -----------------------------------------------------------------------------
# iteration_limit_guardrail
# -----------------------------------------------------------------------------


def test_iteration_limit_guardrail_pass():
    """Within limit passes."""
    result = iteration_limit_guardrail(3, 10)
    assert result.status == "pass"
    assert result.details["current_iteration"] == 3
    assert result.details["max_iterations"] == 10


def test_iteration_limit_guardrail_warn_at_80():
    """At 80% of limit returns warn."""
    result = iteration_limit_guardrail(8, 10)
    assert result.status == "warn"
    assert "limit" in result.message.lower() or "approach" in result.message.lower()
    assert result.retry_allowed is True


def test_iteration_limit_guardrail_fail_at_limit():
    """At max iterations fails."""
    result = iteration_limit_guardrail(10, 10)
    assert result.status == "fail"
    assert "limit" in result.message.lower()
    assert result.retry_allowed is False


def test_iteration_limit_guardrail_fail_above_limit():
    """Above max iterations fails."""
    result = iteration_limit_guardrail(11, 10)
    assert result.status == "fail"
    assert result.retry_allowed is False


def test_iteration_limit_guardrail_invalid_max_fail():
    """max_iterations <= 0 fails."""
    result = iteration_limit_guardrail(0, 0)
    assert result.status == "fail"
    assert result.retry_allowed is False


# -----------------------------------------------------------------------------
# CrewAI integration
# -----------------------------------------------------------------------------


def test_guardrail_to_crewai_callable_pass():
    """CrewAI callable returns True when guardrail passes."""
    fn = make_role_adherence_guardrail("backend_developer")
    out = "def get_user(): return db.query(User).first()"
    assert fn(out) is True


def test_guardrail_to_crewai_callable_fail():
    """CrewAI callable returns False when guardrail fails."""
    fn = make_role_adherence_guardrail("backend_developer")
    out = "const x = React.useState(0);"
    assert fn(out) is False


def test_make_scope_control_guardrail_crewai():
    """Scope control bound guardrail works as CrewAI callable."""
    fn = make_scope_control_guardrail("Implement login and logout.")
    assert fn("Login and logout implemented with sessions.") is True


def test_make_output_format_guardrail_crewai():
    """Output format bound guardrail works as CrewAI callable."""
    fn = make_output_format_guardrail(_SimpleModel)
    assert fn('{"title": "A", "count": 0}') is True
    assert fn("not json") is False


def test_guardrail_result_model():
    """GuardrailResult serializes and has expected fields."""
    r = GuardrailResult(status="fail", message="test", details={"x": 1}, retry_allowed=False)
    assert r.status == "fail"
    assert r.message == "test"
    assert r.details == {"x": 1}
    assert r.retry_allowed is False
    # Pydantic round-trip
    r2 = GuardrailResult.model_validate(r.model_dump())
    assert r2.status == r.status and r2.message == r.message
