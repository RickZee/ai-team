"""Chain-of-thought prompting templates and ReasoningEnhancer for agent tasks.

Provides per-task-type reasoning templates, structured output instructions,
self-reflection prompts, and helpers to integrate with agent backstory prompts.
"""

import re
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# 1. Reasoning templates per task type (chain-of-thought)
# ---------------------------------------------------------------------------

REASONING_TEMPLATES: Dict[str, str] = {
    "requirements_reasoning": (
        "Think step by step: 1) Identify user types, 2) List core features, "
        "3) Define acceptance criteria, 4) Prioritize by business value, 5) Identify risks"
    ),
    "architecture_reasoning": (
        "Think step by step: 1) List system components, 2) Define interfaces, "
        "3) Choose technologies with justification, 4) Design data flow, 5) Identify failure modes"
    ),
    "code_reasoning": (
        "Think step by step: 1) Understand requirements, 2) Design module structure, "
        "3) Implement core logic, 4) Add error handling, 5) Write docstrings, 6) Self-review"
    ),
    "test_reasoning": (
        "Think step by step: 1) Identify test cases from requirements, "
        "2) Design test structure, 3) Create fixtures, 4) Write happy path tests, "
        "5) Write edge cases, 6) Verify coverage"
    ),
}

# ---------------------------------------------------------------------------
# 2. Structured output: response format instructions (appended to prompts)
# ---------------------------------------------------------------------------

OUTPUT_FORMAT_INSTRUCTIONS: Dict[str, str] = {
    "requirements": (
        "Respond with a valid JSON object matching RequirementsDocument: "
        "project_name, description (required—brief top-level project summary in 1–2 sentences), target_users (list), user_stories (list of {as_a, i_want, so_that, "
        "acceptance_criteria: [{description, testable}], priority: MoSCoW}), "
        "non_functional_requirements (list of {category, description, measurable}), "
        "assumptions (list), constraints (list). Include at least 3 user stories with acceptance criteria."
    ),
    "architecture": (
        "Respond with a valid JSON object matching ArchitectureDocument: "
        "system_overview, components (list of {name, responsibilities}), "
        "technology_stack (list of {name, category, justification}), "
        "interface_contracts (list of {provider, consumer, contract_type, description}), "
        "data_model_outline, ascii_diagram, adrs (list of {title, status, context, decision, consequences}), "
        "deployment_topology."
    ),
    "code": (
        "Respond with a valid JSON array of CodeFile objects: "
        "each {path, content, language, description, has_tests}. "
        "Ensure paths are relative to the project root and content is complete."
    ),
    "test": (
        "Respond with a valid JSON object for test/QA output: "
        "TestResult: test_files_generated (list of {path, content}), execution_results ({passed, failed, errors, total, output}), "
        "coverage_report (line_coverage, branch_coverage, per_file), bug_reports (list), "
        "quality_gate_passed, feedback_for_developers. "
        "CodeReviewReport: summary, findings (list of {title, severity, file_path, description, recommendation}), "
        "critical_count, high_count, passed."
    ),
}

# JSON schema templates (minimal) for validation/parsing documentation
JSON_SCHEMA_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "requirements": {
        "type": "object",
        "required": ["project_name", "description", "user_stories"],
        "properties": {
            "project_name": {"type": "string"},
            "description": {"type": "string"},
            "target_users": {"type": "array", "items": {"type": "string"}},
            "user_stories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "as_a": {"type": "string"},
                        "i_want": {"type": "string"},
                        "so_that": {"type": "string"},
                        "acceptance_criteria": {"type": "array"},
                        "priority": {"type": "string"},
                    },
                },
            },
            "non_functional_requirements": {"type": "array"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "constraints": {"type": "array", "items": {"type": "string"}},
        },
    },
    "architecture": {
        "type": "object",
        "required": ["system_overview", "components"],
        "properties": {
            "system_overview": {"type": "string"},
            "components": {"type": "array"},
            "technology_stack": {"type": "array"},
            "interface_contracts": {"type": "array"},
            "data_model_outline": {"type": "string"},
            "ascii_diagram": {"type": "string"},
            "adrs": {"type": "array"},
            "deployment_topology": {"type": "string"},
        },
    },
    "code": {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["path", "content", "language", "description"],
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "language": {"type": "string"},
                "description": {"type": "string"},
                "has_tests": {"type": "boolean"},
            },
        },
    },
    "test": {
        "type": "object",
        "properties": {
            "test_files_generated": {"type": "array"},
            "execution_results": {"type": "object"},
            "coverage_report": {"type": "object"},
            "quality_gate_passed": {"type": "boolean"},
            "feedback_for_developers": {"type": "string"},
            "summary": {"type": "string"},
            "findings": {"type": "array"},
            "critical_count": {"type": "integer"},
            "high_count": {"type": "integer"},
            "passed": {"type": "boolean"},
        },
    },
}

# Map task_type (e.g. requirements_reasoning) to output format key
TASK_TYPE_TO_OUTPUT_KEY: Dict[str, str] = {
    "requirements_reasoning": "requirements",
    "architecture_reasoning": "architecture",
    "code_reasoning": "code",
    "test_reasoning": "test",
}

# ---------------------------------------------------------------------------
# 3. Self-reflection prompt
# ---------------------------------------------------------------------------

SELF_REFLECTION_PROMPT: str = (
    "Review your output. Does it meet all requirements? "
    "What could be improved? Rate your confidence 1-10."
)

# ---------------------------------------------------------------------------
# 4. ReasoningEnhancer class
# ---------------------------------------------------------------------------


class ReasoningEnhancer:
    """
    Enhances agent prompts with chain-of-thought reasoning templates,
    structured output instructions, and self-reflection. Integrates with
    agent backstory by appending reasoning guidance.
    """

    def __init__(
        self,
        include_output_format: bool = True,
        include_self_reflection_by_default: bool = False,
    ) -> None:
        """
        Initialize the enhancer.

        :param include_output_format: If True, append structured output instructions.
        :param include_self_reflection_by_default: If True, add_self_reflection is applied when enhance_prompt is used (optional second step).
        """
        self._include_output_format = include_output_format
        self._include_self_reflection_by_default = include_self_reflection_by_default

    def enhance_prompt(self, base_prompt: str, task_type: str) -> str:
        """
        Prepend chain-of-thought reasoning and optionally append output format.

        :param base_prompt: Original task or agent prompt.
        :param task_type: One of requirements_reasoning, architecture_reasoning, code_reasoning, test_reasoning.
        :return: Enhanced prompt with reasoning template and optional format instructions.
        """
        reasoning = REASONING_TEMPLATES.get(task_type)
        if not reasoning:
            logger.warning("unknown_task_type", task_type=task_type)
            return base_prompt

        parts = [f"{reasoning}\n\n", base_prompt]

        if self._include_output_format:
            output_key = TASK_TYPE_TO_OUTPUT_KEY.get(task_type)
            if output_key and output_key in OUTPUT_FORMAT_INSTRUCTIONS:
                parts.append("\n\n")
                parts.append(OUTPUT_FORMAT_INSTRUCTIONS[output_key])

        result = "".join(parts)
        if self._include_self_reflection_by_default:
            result = self.add_self_reflection(result)
        return result

    def add_self_reflection(self, prompt: str) -> str:
        """
        Append the self-reflection instruction to the prompt.

        :param prompt: Existing prompt text.
        :return: Prompt with self-reflection line appended.
        """
        if not prompt.strip().endswith(".") and not prompt.strip().endswith("?"):
            prompt = prompt.rstrip() + "."
        return f"{prompt}\n\n{SELF_REFLECTION_PROMPT}"

    @staticmethod
    def parse_confidence(response: str) -> float:
        """
        Extract confidence rating (1-10) from a response that includes self-reflection.

        Looks for patterns like "confidence: 7", "confidence 8", "Rate: 8", "8/10".

        :param response: LLM response that may contain a confidence rating.
        :return: Float in [0, 10], or 5.0 if not found (neutral default).
        """
        if not response or not response.strip():
            return 5.0

        text = response.strip()
        # "confidence 7" or "confidence: 7" or "confidence (7)"
        m = re.search(
            r"\bconfidence\s*[:\s(]*(\d(?:\.\d+)?)\s*[/)\]]?",
            text,
            re.IGNORECASE,
        )
        if m:
            try:
                v = float(m.group(1))
                return max(0.0, min(10.0, v))
            except ValueError:
                pass

        # "7/10" or "8 / 10"
        m = re.search(r"(\d(?:\.\d+)?)\s*/\s*10", text)
        if m:
            try:
                v = float(m.group(1))
                return max(0.0, min(10.0, v))
            except ValueError:
                pass

        # Standalone number 1-10 in context of "rate" or "rating"
        m = re.search(r"(?:rate|rating|score)\s*(?:is|:)?\s*(\d(?:\.\d+)?)", text, re.IGNORECASE)
        if m:
            try:
                v = float(m.group(1))
                return max(0.0, min(10.0, v))
            except ValueError:
                pass

        logger.debug("confidence_not_found", response_preview=text[:200])
        return 5.0


# ---------------------------------------------------------------------------
# Integration with agent backstory prompts
# ---------------------------------------------------------------------------


def enhance_backstory_with_reasoning(backstory: str, task_type: str) -> str:
    """
    Append chain-of-thought reasoning to an agent backstory so the agent
    follows step-by-step reasoning for the given task type.

    Use when building agent prompts (e.g. in create_agent or task description)
    to reinforce reasoning behavior aligned with the agent's role.

    :param backstory: Agent backstory from config or code.
    :param task_type: One of requirements_reasoning, architecture_reasoning, code_reasoning, test_reasoning.
    :return: Backstory with reasoning guidance appended.
    """
    reasoning = REASONING_TEMPLATES.get(task_type)
    if not reasoning:
        return backstory
    backstory = backstory.rstrip()
    if not backstory.endswith("."):
        backstory = backstory + "."
    return f"{backstory} When working on this task, {reasoning.lower()}."


# ---------------------------------------------------------------------------
# Parsing helpers to extract structured data from LLM responses
# ---------------------------------------------------------------------------

# Pattern for JSON block in markdown or raw text
_JSON_BLOCK_RE = re.compile(
    r"```(?:json)?\s*([\s\S]*?)```",
    re.IGNORECASE,
)
_JSON_OBJECT_RE = re.compile(r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})", re.DOTALL)
_JSON_ARRAY_RE = re.compile(r"(\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\])", re.DOTALL)


def extract_json_from_response(response: str) -> Optional[str]:
    """
    Extract a JSON string from an LLM response (markdown code block or raw JSON).

    :param response: Raw response text that may contain JSON.
    :return: First plausible JSON string (object or array), or None if not found.
    """
    if not response or not response.strip():
        return None

    # Prefer ```json ... ``` block
    for match in _JSON_BLOCK_RE.finditer(response):
        candidate = match.group(1).strip()
        if (candidate.startswith("{") or candidate.startswith("[")) and (
            candidate.endswith("}") or candidate.endswith("]")
        ):
            return candidate

    # Fallback: first {...} or [...] that looks like JSON
    for pattern in (_JSON_OBJECT_RE, _JSON_ARRAY_RE):
        for match in pattern.finditer(response):
            candidate = match.group(1).strip()
            if len(candidate) > 10:
                return candidate

    return None


def get_reasoning_template(task_type: str) -> Optional[str]:
    """Return the chain-of-thought template for the given task type, or None."""
    return REASONING_TEMPLATES.get(task_type)


def get_output_format_instruction(output_key: str) -> Optional[str]:
    """Return the structured output instruction for the given key (requirements, architecture, code, test)."""
    return OUTPUT_FORMAT_INSTRUCTIONS.get(output_key)
