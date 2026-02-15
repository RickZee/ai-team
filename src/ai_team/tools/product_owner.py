"""Product Owner agent tools: requirements parsing, user stories, acceptance criteria, prioritization."""

import re
from typing import List, Tuple

from crewai.tools import tool


# ----- Guardrail: reject vague or contradictory requirements -----

VAGUE_INDICATORS = [
    r"\b(some|something|maybe|perhaps|kind of|sort of|better|nice|good|flexible|etc\.?)\b",
    r"\b(things?|stuff|whatever|somehow|later)\b",
    r"\b(as needed|if possible|when possible)\b",
]
CONTRADICTION_PAIRS = [
    ("must", "optional"),
    ("required", "optional"),
    ("always", "never"),
    ("all", "none"),
    ("minimum", "maximum"),
]


def _check_vague(text: str) -> List[str]:
    """Return list of vague phrase matches."""
    found = []
    for pattern in VAGUE_INDICATORS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            found.append(m.group(0))
    return found


def _check_contradictions(text: str) -> List[Tuple[str, str]]:
    """Return list of (word1, word2) that appear together and contradict."""
    lower = text.lower()
    found = []
    for a, b in CONTRADICTION_PAIRS:
        if a in lower and b in lower:
            found.append((a, b))
    return found


def validate_requirements_guardrail(raw_requirements: str) -> Tuple[bool, str]:
    """
    Guardrail: reject requirements that are too vague or contain contradictions.
    Returns (valid, message). If invalid, message explains the issue.
    """
    vague = _check_vague(raw_requirements)
    contradictions = _check_contradictions(raw_requirements)
    if vague:
        return False, f"Requirements too vague. Avoid: {', '.join(list(set(vague))[:5])}"
    if contradictions:
        pairs = ", ".join(f"'{a}' vs '{b}'" for a, b in contradictions)
        return False, f"Requirements contain contradictions: {pairs}"
    return True, "OK"


@tool("Parse raw requirements into structured themes and actors")
def requirements_parser(raw_ideas: str) -> str:
    """
    Parse raw ideas or vague requirements into structured themes, actors, and key capabilities.
    Input: free-form text describing what the user wants.
    Output: bullet list of themes, target users, and main capabilities to refine into user stories.
    """
    if not raw_ideas or not raw_ideas.strip():
        return "Error: No input provided. Supply raw ideas or requirements text."
    valid, msg = validate_requirements_guardrail(raw_ideas)
    if not valid:
        return f"Guardrail: {msg}"
    # Return a structured template the agent can fill; actual parsing is LLM-driven
    return (
        "Parsed structure (refine with user stories):\n"
        "- Themes: extract 3–7 main themes from the input\n"
        "- Target users: list user roles/personas mentioned or implied\n"
        "- Key capabilities: list main features/capabilities to turn into stories"
    )


@tool("Generate user stories in As a / I want / So that format")
def user_story_generator(requirement_or_theme: str) -> str:
    """
    Generate one or more user stories in standard format: As a [role], I want [capability], so that [benefit].
    Input: a requirement theme or feature description.
    Output: user story sentences, one per line, in the format above.
    """
    if not requirement_or_theme or not requirement_or_theme.strip():
        return "Error: No requirement or theme provided."
    valid, msg = validate_requirements_guardrail(requirement_or_theme)
    if not valid:
        return f"Guardrail: {msg}"
    return (
        "Generate user stories in this format:\n"
        "As a [role], I want [capability], so that [benefit].\n"
        "One story per line; ensure each has a clear role, want, and so that."
    )


@tool("Write testable acceptance criteria for a user story")
def acceptance_criteria_writer(user_story: str) -> str:
    """
    Write testable acceptance criteria for a user story. Criteria should be verifiable (Given/When/Then or checklist).
    Input: a single user story (As a... I want... So that...).
    Output: 3–7 acceptance criteria, each testable and unambiguous.
    """
    if not user_story or not user_story.strip():
        return "Error: No user story provided."
    return (
        "Write acceptance criteria that are:\n"
        "- Testable (verifiable by QA or automation)\n"
        "- Unambiguous (no 'should work', 'user-friendly' without definition)\n"
        "- In Given/When/Then or numbered checklist form\n"
        "Output 3–7 criteria for this story."
    )


@tool("Assign MoSCoW priority and rationale")
def priority_scorer(story_description: str, context: str = "") -> str:
    """
    Assign a MoSCoW priority (Must have, Should have, Could have, Won't have this time) to a story.
    Input: story description and optional context (e.g. MVP scope, business goals).
    Output: priority level and short rationale.
    """
    if not story_description or not story_description.strip():
        return "Error: No story description provided."
    return (
        "Assign MoSCoW priority:\n"
        "- Must have: critical for launch/MVP\n"
        "- Should have: important but not blocking\n"
        "- Could have: nice to have\n"
        "- Won't have this time: out of scope\n"
        "Output: [Priority]: [One-line rationale]"
    )


def get_product_owner_tools() -> list:
    """Return the list of Product Owner tools for agent attachment."""
    return [
        requirements_parser,
        user_story_generator,
        acceptance_criteria_writer,
        priority_scorer,
    ]
