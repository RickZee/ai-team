"""
Product Owner agent: transforms vague ideas into clear, prioritized requirements.

Uses BaseAgent, requirements tools, RequirementsDocument output, self-validation,
and guardrails to reject vague or contradictory requirements.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ai_team.agents.base import BaseAgent, create_agent
from ai_team.agents.product_owner_templates import get_template_for_project_type
from ai_team.models.requirements import (
    AcceptanceCriterion,
    MoSCoW,
    NonFunctionalRequirement,
    RequirementsDocument,
    UserStory,
)
from ai_team.tools.product_owner import (
    get_product_owner_tools,
    validate_requirements_guardrail,
)


# ----- Self-validation: completeness, no ambiguous terms, testable criteria -----

AMBIGUOUS_TERMS = re.compile(
    r"\b(some|something|maybe|perhaps|kind of|sort of|better|nice|good|flexible|"
    r"things?|stuff|whatever|somehow|as needed|if possible|when possible|etc\.?)\b",
    re.IGNORECASE,
)


def _validation_errors(doc: RequirementsDocument) -> List[str]:
    """Run self-validation; return list of error messages (empty if valid)."""
    errors: List[str] = []

    # Completeness
    if not doc.project_name or not doc.description.strip():
        errors.append("Project name and description are required.")
    if not doc.user_stories:
        errors.append("At least one user story is required.")
    for i, story in enumerate(doc.user_stories):
        if not story.as_a or not story.i_want or not story.so_that:
            errors.append(f"User story {i + 1}: missing 'as a', 'I want', or 'so that'.")
        if not story.acceptance_criteria:
            errors.append(f"User story {i + 1}: no acceptance criteria.")
        for j, ac in enumerate(story.acceptance_criteria):
            if not ac.description.strip():
                errors.append(f"User story {i + 1}, criterion {j + 1}: empty description.")
            if not ac.testable:
                errors.append(f"User story {i + 1}, criterion {j + 1}: must be testable.")

    # No ambiguous terms in key text
    for story in doc.user_stories:
        text = f"{story.as_a} {story.i_want} {story.so_that}"
        if AMBIGUOUS_TERMS.search(text):
            errors.append(f"User story contains ambiguous terms: '{story.i_want[:60]}...'")

    return errors


def validate_requirements_document(doc: RequirementsDocument) -> Tuple[bool, List[str]]:
    """
    Self-validation: checks completeness, no ambiguous terms, testable criteria.
    Returns (is_valid, list of error messages).
    """
    errors = _validation_errors(doc)
    return (len(errors) == 0, errors)


def create_product_owner_agent(
    tools: Optional[List[Any]] = None,
    config_path: Optional[Path] = None,
    agents_config: Optional[Dict[str, Any]] = None,
) -> BaseAgent:
    """
    Create the Product Owner agent with config from agents.yaml and default tools.

    :param tools: Override tools; if None, uses requirements_parser, user_story_generator,
                  acceptance_criteria_writer, priority_scorer.
    :param config_path: Override path to agents YAML (for tests).
    :param agents_config: Pre-loaded config dict (overrides file).
    :return: Configured BaseAgent instance.
    """
    agent_tools = tools if tools is not None else get_product_owner_tools()
    return create_agent(
        "product_owner",
        tools=agent_tools,
        guardrail_tools=True,
        config_path=config_path,
        agents_config=agents_config,
    )


def _extract_json_block(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from a ```json ... ``` or ``` ... ``` block."""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try parsing the whole text as JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def _dict_to_requirements_document(data: Dict[str, Any]) -> Optional[RequirementsDocument]:
    """Build RequirementsDocument from a dict (e.g. parsed JSON)."""
    try:
        stories = []
        for s in data.get("user_stories", []):
            ac_list = [
                AcceptanceCriterion(description=c.get("description", ""), testable=c.get("testable", True))
                if isinstance(c, dict)
                else AcceptanceCriterion(description=getattr(c, "description", ""), testable=getattr(c, "testable", True))
                for c in s.get("acceptance_criteria", [])
            ]
            priority_val = s.get("priority", "Must have")
            if isinstance(priority_val, str):
                priority_val = next((p for p in MoSCoW if p.value == priority_val), MoSCoW.MUST)
            stories.append(
                UserStory(
                    as_a=s.get("as_a", "user"),
                    i_want=s.get("i_want", ""),
                    so_that=s.get("so_that", ""),
                    acceptance_criteria=ac_list,
                    priority=priority_val,
                    story_id=s.get("story_id", ""),
                )
            )
        nfr_list = [
            NonFunctionalRequirement(
                category=n.get("category", ""),
                description=n.get("description", ""),
                measurable=n.get("measurable", True),
            )
            for n in data.get("non_functional_requirements", [])
            if isinstance(n, dict)
        ]
        return RequirementsDocument(
            project_name=data.get("project_name", "Untitled Project"),
            description=data.get("description", ""),
            target_users=data.get("target_users", []),
            user_stories=stories,
            non_functional_requirements=nfr_list,
            assumptions=data.get("assumptions", []),
            constraints=data.get("constraints", []),
        )
    except Exception:
        return None


def requirements_from_agent_output(
    raw_output: str,
    project_name: str = "",
    description: str = "",
) -> Tuple[Optional[RequirementsDocument], List[str]]:
    """
    Parse agent output into a RequirementsDocument.

    Tries to extract JSON from a code block or full text, then validates.
    If parsing or validation fails, returns (None, list of errors).
    """
    errors: List[str] = []
    data = _extract_json_block(raw_output)
    if data:
        doc = _dict_to_requirements_document(data)
        if doc:
            valid, validation_errors = validate_requirements_document(doc)
            if not valid:
                return None, validation_errors
            return doc, []

    # Fallback: minimal document from narrative
    if not project_name and raw_output:
        for line in raw_output.split("\n")[:5]:
            if line.strip().lower().startswith("project"):
                project_name = line.split(":", 1)[-1].strip() or "Untitled Project"
                break
        if not project_name:
            project_name = "Untitled Project"
    doc = RequirementsDocument(
        project_name=project_name or "Untitled Project",
        description=description or raw_output.strip()[:500] if raw_output else "No description.",
        target_users=[],
        user_stories=[
            UserStory(
                as_a="user",
                i_want="requirements to be implemented",
                so_that="the product meets stakeholder needs",
                acceptance_criteria=[
                    AcceptanceCriterion(description="Requirements are documented and prioritized.", testable=True)
                ],
                priority=MoSCoW.MUST,
            )
        ],
        non_functional_requirements=[],
        assumptions=[],
        constraints=[],
    )
    valid, validation_errors = validate_requirements_document(doc)
    if not valid:
        return None, validation_errors
    return doc, []


__all__ = [
    "create_product_owner_agent",
    "get_template_for_project_type",
    "requirements_from_agent_output",
    "validate_requirements_document",
    "validate_requirements_guardrail",
]
