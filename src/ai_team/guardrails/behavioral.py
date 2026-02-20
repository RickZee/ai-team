"""
Behavioral guardrails for AI Team agents.

Ensures agents stay within role boundaries, control scope, delegate appropriately,
produce correctly formatted output, and respect iteration limits.
Integrates with CrewAI's task guardrail parameter via guardrail_to_crewai_callable().
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Literal, Optional, Type, TypeVar

from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# GuardrailResult
# -----------------------------------------------------------------------------


class GuardrailResult(BaseModel):
    """Result of a guardrail check. Used by all behavioral guardrails."""

    status: Literal["pass", "fail", "warn"] = Field(
        ...,
        description="pass = check succeeded; fail = check failed (retry or reject); warn = advisory.",
    )
    message: str = Field(..., description="Human-readable summary.")
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured details (e.g. violations, parse errors).",
    )
    retry_allowed: bool = Field(
        default=True,
        description="If True, task may be retried on failure; otherwise treat as final fail.",
    )


# -----------------------------------------------------------------------------
# Role adherence
# -----------------------------------------------------------------------------

# Roles that may delegate (from agents.yaml: manager, architect have allow_delegation: true)
ALLOWED_DELEGATORS = {"manager", "architect", "engineering_manager", "solutions_architect", "tech_lead"}

# Role-specific forbidden patterns: backend shouldn't emit frontend; QA shouldn't modify source; etc.
ROLE_RESTRICTIONS: Dict[str, Dict[str, Any]] = {
    "qa_engineer": {
        "forbidden_patterns": [
            (r"def\s+(?!test_)\w+\(", "Production code (non-test function)"),
            (r"class\s+(?!Test)\w+\(", "Production class (non-test)"),
            (r"(?<!test_)\.py\s*$|^(?!test_)\w+\.py", "Modifying non-test source files"),
        ],
        "message": "QA Engineer should only write test code, not modify production source.",
    },
    "product_owner": {
        "forbidden_patterns": [
            (r"def\s+\w+\(", "Implementation (function definition)"),
            (r"class\s+\w+\(", "Implementation (class definition)"),
            (r"import\s+\w+", "Code imports"),
        ],
        "message": "Product Owner should focus on requirements, not implementation.",
    },
    "architect": {
        "forbidden_patterns": [
            (r"INSERT\s+INTO", "Data manipulation"),
            (r"DELETE\s+FROM", "Data manipulation"),
            (r"UPDATE\s+\w+\s+SET", "Data manipulation"),
        ],
        "message": "Architect should design systems, not implement data operations.",
    },
    "backend_developer": {
        "forbidden_patterns": [
            (r"<script\b", "Frontend script tag"),
            (r"<style\b", "Frontend style tag"),
            (r"useState\s*\(|useEffect\s*\(|React\.", "React frontend code"),
            (r"vue\s*\.|Vue\.|createApp\s*\(|@vue", "Vue frontend code"),
            (r"@angular|NgModule\s*\(|Component\s*\(\s*\{", "Angular frontend code"),
            (r"\.css\s*\{|@media\s+", "Standalone CSS"),
        ],
        "message": "Backend developer should not generate frontend UI code (React/Vue/CSS).",
    },
    "frontend_developer": {
        "forbidden_patterns": [
            (r"CREATE\s+TABLE|ALTER\s+TABLE|DROP\s+TABLE", "Database DDL"),
            (r"INSERT\s+INTO|DELETE\s+FROM|UPDATE\s+\w+\s+SET", "Database DML"),
            (r"flask\s*\.|FastAPI\s*\(|django\.conf|@app\.route", "Backend server framework"),
            (r"sqlalchemy|Session\s*\(|engine\.execute", "ORM/DB session"),
        ],
        "message": "Frontend developer should not generate backend/database code.",
    },
    "manager": {
        "forbidden_patterns": [
            (r"def\s+\w+\s*\(", "Code implementation (function definition)"),
            (r"class\s+\w+\s*[\(:]", "Code implementation (class definition)"),
            (r"import\s+\w+", "Code imports"),
        ],
        "message": "Manager should coordinate and delegate, not produce implementation code.",
    },
}


def role_adherence_guardrail(task_output: str, agent_role: str) -> GuardrailResult:
    """
    Verify the agent stayed within its role boundaries.

    E.g. backend dev shouldn't generate frontend code; QA shouldn't modify
    production source; product owner shouldn't emit implementation code.
    """
    role_lower = agent_role.lower().strip().replace(" ", "_")
    violations: List[str] = []

    if role_lower in ROLE_RESTRICTIONS:
        restrictions = ROLE_RESTRICTIONS[role_lower]
        for pattern, label in restrictions["forbidden_patterns"]:
            if re.search(pattern, task_output, re.IGNORECASE):
                violations.append(label)

    if violations:
        return GuardrailResult(
            status="fail",
            message=ROLE_RESTRICTIONS.get(role_lower, {}).get("message", "Role boundary violation.")
            or "Role boundary violation.",
            details={"violations": violations, "agent_role": agent_role},
            retry_allowed=True,
        )
    return GuardrailResult(
        status="pass",
        message="Output adheres to role boundaries.",
        details={"agent_role": agent_role},
        retry_allowed=True,
    )


# -----------------------------------------------------------------------------
# Scope control
# -----------------------------------------------------------------------------


def scope_control_guardrail(
    task_output: str,
    original_requirements: str,
    max_expansion: float = 0.25,
    min_relevance: float = 0.5,
) -> GuardrailResult:
    """
    Ensure output addresses the task and doesn't add unrequested features.

    Flags scope creep with specific examples (keywords in output not tied to
    requirements).
    """
    req_words = set(re.findall(r"\b\w{4,}\b", original_requirements.lower()))
    out_words = set(re.findall(r"\b\w{4,}\b", task_output.lower()))

    if not req_words:
        return GuardrailResult(
            status="pass",
            message="No requirement keywords to check; scope not validated.",
            retry_allowed=True,
        )

    overlap = len(req_words & out_words) / len(req_words)
    extra = out_words - req_words
    # Heuristic: "scope creep" if many prominent words in output aren't in requirements
    # and relevance is low
    creep_candidates = list(extra)[:15] if len(extra) > 20 else []

    if overlap < min_relevance:
        return GuardrailResult(
            status="fail",
            message=f"Output deviates from task scope (relevance {overlap:.0%} below {min_relevance:.0%}).",
            details={
                "relevance_ratio": round(overlap, 3),
                "task_keyword_overlap": overlap,
                "possible_scope_creep_examples": creep_candidates[:10],
            },
            retry_allowed=True,
        )

    if creep_candidates and overlap < (1 - max_expansion):
        return GuardrailResult(
            status="warn",
            message="Output may include scope creep; consider focusing on requirements.",
            details={
                "relevance_ratio": round(overlap, 3),
                "possible_scope_creep_examples": creep_candidates[:10],
            },
            retry_allowed=True,
        )

    return GuardrailResult(
        status="pass",
        message="Output is within task scope.",
        details={"relevance_ratio": round(overlap, 3)},
        retry_allowed=True,
    )


# -----------------------------------------------------------------------------
# Reasoning (minimum substance and rationale)
# -----------------------------------------------------------------------------

REASONING_INDICATORS = re.compile(
    r"\b(because|rationale|therefore|reason|so that|in order to|thus|hence|"
    r"the reason|this is because|we chose|we decided|recommendation)\b",
    re.IGNORECASE,
)
MIN_REASONING_LENGTH = 80


def reasoning_guardrail(task_output: str) -> GuardrailResult:
    """
    Ensure output shows reasoning: sufficient length and rationale indicators.
    Fails short outputs with no reasoning phrases (adversarial: terse non-reasoned output).
    """
    text = task_output.strip()
    if len(text) >= MIN_REASONING_LENGTH:
        return GuardrailResult(
            status="pass",
            message="Output has sufficient length and is not trivially short.",
            details={"length": len(text)},
            retry_allowed=True,
        )
    if REASONING_INDICATORS.search(text):
        return GuardrailResult(
            status="pass",
            message="Output includes reasoning indicators.",
            details={"length": len(text)},
            retry_allowed=True,
        )
    return GuardrailResult(
        status="fail",
        message="Output is too short and lacks clear reasoning or rationale.",
        details={"length": len(text), "min_length": MIN_REASONING_LENGTH},
        retry_allowed=True,
    )


# -----------------------------------------------------------------------------
# Delegation
# -----------------------------------------------------------------------------


def delegation_guardrail(
    delegating_agent: str,
    target_agent: str,
    task: str,
    delegation_chain: Optional[List[str]] = None,
) -> GuardrailResult:
    """
    Validate that delegation makes sense (e.g. Manager can delegate; individual
    contributors shouldn't). Check for circular delegation when chain is provided.
    """
    deleg_lower = delegating_agent.lower().strip().replace(" ", "_")
    target_lower = target_agent.lower().strip().replace(" ", "_")
    chain = delegation_chain or []

    # Only certain roles should delegate
    if deleg_lower not in ALLOWED_DELEGATORS:
        return GuardrailResult(
            status="fail",
            message=f"Agent '{delegating_agent}' is not allowed to delegate. Only Manager/Architect roles may delegate.",
            details={
                "delegating_agent": delegating_agent,
                "target_agent": target_agent,
                "allowed_delegators": list(ALLOWED_DELEGATORS),
            },
            retry_allowed=True,
        )

    # Circular: if we have a chain, target should not already be in it
    if chain and target_lower in [c.lower().replace(" ", "_") for c in chain]:
        return GuardrailResult(
            status="fail",
            message="Circular delegation detected: target agent already in delegation chain.",
            details={
                "delegating_agent": delegating_agent,
                "target_agent": target_agent,
                "delegation_chain": chain,
            },
            retry_allowed=True,
        )

    return GuardrailResult(
        status="pass",
        message="Delegation is allowed and not circular.",
        details={
            "delegating_agent": delegating_agent,
            "target_agent": target_agent,
        },
        retry_allowed=True,
    )


# -----------------------------------------------------------------------------
# Output format (Pydantic)
# -----------------------------------------------------------------------------

T = TypeVar("T", bound=BaseModel)


def output_format_guardrail(
    output: str,
    expected_format: Type[T],
) -> GuardrailResult:
    """
    Validate that output matches the expected Pydantic model.

    Attempts to parse (including optional JSON markdown code blocks) and
    returns structured validation errors if invalid.
    """
    text = output.strip()
    # Unwrap ```json ... ``` or ``` ... ```
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if code_block:
        text = code_block.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return GuardrailResult(
            status="fail",
            message=f"Output is not valid JSON: {e!s}",
            details={"json_error": str(e), "expected_type": expected_format.__name__},
            retry_allowed=True,
        )

    try:
        expected_format.model_validate(data)
    except Exception as e:
        return GuardrailResult(
            status="fail",
            message=f"Output does not match expected format: {e!s}",
            details={
                "validation_error": str(e),
                "expected_type": expected_format.__name__,
            },
            retry_allowed=True,
        )

    return GuardrailResult(
        status="pass",
        message="Output matches expected Pydantic model.",
        details={"expected_type": expected_format.__name__},
        retry_allowed=True,
    )


# -----------------------------------------------------------------------------
# Iteration limit
# -----------------------------------------------------------------------------


def iteration_limit_guardrail(
    current_iteration: int,
    max_iterations: int,
) -> GuardrailResult:
    """
    Prevent infinite loops in agent reasoning.

    Log warning at 80% of limit, fail at or above limit.
    """
    if max_iterations <= 0:
        return GuardrailResult(
            status="fail",
            message="max_iterations must be positive.",
            details={"current_iteration": current_iteration, "max_iterations": max_iterations},
            retry_allowed=False,
        )

    if current_iteration >= max_iterations:
        return GuardrailResult(
            status="fail",
            message=f"Iteration limit reached ({current_iteration} >= {max_iterations}).",
            details={
                "current_iteration": current_iteration,
                "max_iterations": max_iterations,
            },
            retry_allowed=False,
        )

    threshold_80 = int(max_iterations * 0.8)
    if current_iteration >= threshold_80:
        return GuardrailResult(
            status="warn",
            message=f"Approaching iteration limit ({current_iteration}/{max_iterations}).",
            details={
                "current_iteration": current_iteration,
                "max_iterations": max_iterations,
                "warning_at": threshold_80,
            },
            retry_allowed=True,
        )

    return GuardrailResult(
        status="pass",
        message="Within iteration limit.",
        details={"current_iteration": current_iteration, "max_iterations": max_iterations},
        retry_allowed=True,
    )


# -----------------------------------------------------------------------------
# CrewAI integration
# -----------------------------------------------------------------------------


def guardrail_to_crewai_callable(
    guardrail_fn: Callable[..., GuardrailResult],
    *args: Any,
    **kwargs: Any,
) -> Callable[[str], bool]:
    """
    Wrap a behavioral guardrail so it can be used as CrewAI's task guardrail.

    CrewAI expects a callable that takes task output and returns True (pass) or
    False (fail). Pass and warn are treated as success; fail as failure (task may
    retry if guardrail_max_retries allows).
    """
    def crewai_guardrail(task_output: str) -> bool:
        result = guardrail_fn(task_output, *args, **kwargs)
        return result.status != "fail"
    return crewai_guardrail


def make_role_adherence_guardrail(agent_role: str) -> Callable[[str], bool]:
    """CrewAI-compatible guardrail for role adherence (bound to agent_role)."""
    return guardrail_to_crewai_callable(role_adherence_guardrail, agent_role=agent_role)


def make_scope_control_guardrail(original_requirements: str) -> Callable[[str], bool]:
    """CrewAI-compatible guardrail for scope control (bound to requirements)."""
    return guardrail_to_crewai_callable(
        scope_control_guardrail,
        original_requirements=original_requirements,
    )


def make_reasoning_guardrail() -> Callable[[str], bool]:
    """CrewAI-compatible guardrail for reasoning (no extra args)."""
    return guardrail_to_crewai_callable(reasoning_guardrail)


def make_output_format_guardrail(expected_format: Type[BaseModel]) -> Callable[[str], bool]:
    """CrewAI-compatible guardrail for output format (bound to Pydantic type)."""
    return guardrail_to_crewai_callable(output_format_guardrail, expected_format=expected_format)
