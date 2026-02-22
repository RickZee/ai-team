"""
Planning tasks: requirements_gathering and architecture_design.

Task definitions are loaded from config/tasks.yaml. Factory functions create
CrewAI Task objects with context passing, guardrails, and timeout configuration.
"""

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import structlog
import yaml
from crewai import Task

from ai_team.agents.architect import validate_architecture_against_requirements
from ai_team.agents.product_owner import _dict_to_requirements_document
from ai_team.config.settings import get_settings
from ai_team.models.architecture import (
    ArchitectureDecisionRecord,
    ArchitectureDocument,
    Component,
    InterfaceContract,
    TechnologyChoice,
)
from ai_team.models.requirements import RequirementsDocument

logger = structlog.get_logger(__name__)

# Minimum user stories with acceptance criteria for requirements guardrail
MIN_USER_STORIES = 3


def _load_tasks_yaml(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load tasks.yaml; return full dict. Uses config_path or default next to config."""
    if config_path is not None and config_path.exists():
        path = config_path
    else:
        path = Path(__file__).resolve().parent.parent / "config" / "tasks.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Tasks config not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def planning_tasks_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Return the planning section of tasks.yaml as a dict.

    Keys: requirements_gathering, architecture_design. Each value has
    description, agent, expected_output, output_pydantic, guardrail, context,
    timeout_seconds.
    """
    data = _load_tasks_yaml(config_path)
    return data.get("planning") or {}


def _output_pydantic_class(name: str) -> Any:
    """Resolve output_pydantic string to Pydantic model class."""
    mapping = {
        "RequirementsDocument": RequirementsDocument,
        "ArchitectureDocument": ArchitectureDocument,
    }
    if name not in mapping:
        raise ValueError(f"Unknown output_pydantic: {name}. Known: {list(mapping)}")
    return mapping[name]


def _task_output_text(result: Any) -> str:
    """Extract raw text from CrewAI TaskOutput or similar."""
    if hasattr(result, "raw"):
        return getattr(result, "raw") or ""
    if isinstance(result, str):
        return result
    return str(result)


# -----------------------------------------------------------------------------
# Guardrails
# -----------------------------------------------------------------------------


def requirements_guardrail(task_output: Any) -> Tuple[bool, Any]:
    """
    Guardrail: requirements must have at least 3 user stories with acceptance
    criteria. Task output can be string or CrewAI result; parsed as JSON when
    possible. Returns (passed, result) for CrewAI Task guardrail API.
    Result must be a string when passed=False so CrewAI does not receive TaskOutput.
    """
    text = _task_output_text(task_output)
    data = _extract_json_block_for_requirements(text)
    if not data:
        logger.warning("requirements_guardrail_no_json", output_preview=text[:200])
        return (False, "Requirements guardrail: no valid JSON in output.")
    doc = _dict_to_requirements_document(data)
    if not doc:
        logger.warning("requirements_guardrail_parse_failed")
        return (False, "Requirements guardrail: failed to parse RequirementsDocument.")
    if len(doc.user_stories) < MIN_USER_STORIES:
        logger.warning(
            "requirements_guardrail_too_few_stories",
            count=len(doc.user_stories),
            required=MIN_USER_STORIES,
        )
        return (False, f"Requirements guardrail: need at least {MIN_USER_STORIES} user stories with acceptance criteria.")
    for i, story in enumerate(doc.user_stories):
        if not story.acceptance_criteria:
            logger.warning(
                "requirements_guardrail_story_missing_criteria",
                story_index=i,
                i_want=story.i_want[:60],
            )
            return (False, f"Requirements guardrail: user story {i} missing acceptance_criteria.")
    return (True, text)


def _find_balanced_brace_json(text: str) -> Optional[str]:
    """Find first top-level {...} in text (balanced braces); return that substring or None."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _extract_json_block_for_requirements(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from markdown block, raw JSON, or first top-level {...} in text."""
    if not text or not text.strip():
        return None
    # 1) Markdown code block
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # 2) Whole text is JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # 3) First top-level JSON object in text (e.g. prose then { ... })
    candidate = _find_balanced_brace_json(text)
    if candidate:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    return None


def _extract_json_block_for_arch(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from markdown block, raw JSON, or first top-level {...} in text."""
    if not text or not text.strip():
        return None
    # 1) Markdown code block
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # 2) Whole text is JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # 3) First top-level JSON object in text (e.g. prose then { ... })
    candidate = _find_balanced_brace_json(text)
    if candidate:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    return None


def _dict_to_architecture_document(data: Dict[str, Any]) -> Optional[ArchitectureDocument]:
    """Build ArchitectureDocument from dict (e.g. parsed agent output)."""
    try:
        components = [
            Component(name=c.get("name", ""), responsibilities=c.get("responsibilities", ""))
            for c in data.get("components", [])
            if isinstance(c, dict)
        ]
        tech_stack = [
            TechnologyChoice(
                name=t.get("name", ""),
                category=t.get("category", ""),
                justification=t.get("justification", ""),
            )
            for t in data.get("technology_stack", [])
            if isinstance(t, dict)
        ]
        contracts = [
            InterfaceContract(
                provider=ic.get("provider", ""),
                consumer=ic.get("consumer", ""),
                contract_type=ic.get("contract_type", ""),
                description=ic.get("description", ""),
            )
            for ic in data.get("interface_contracts", [])
            if isinstance(ic, dict)
        ]
        adrs = [
            ArchitectureDecisionRecord(
                title=adr.get("title", ""),
                status=adr.get("status", "Accepted"),
                context=adr.get("context", ""),
                decision=adr.get("decision", ""),
                consequences=adr.get("consequences", ""),
            )
            for adr in data.get("adrs", [])
            if isinstance(adr, dict)
        ]
        return ArchitectureDocument(
            system_overview=data.get("system_overview", ""),
            components=components,
            technology_stack=tech_stack,
            interface_contracts=contracts,
            data_model_outline=data.get("data_model_outline", ""),
            ascii_diagram=data.get("ascii_diagram", ""),
            adrs=adrs,
            deployment_topology=data.get("deployment_topology", ""),
        )
    except Exception:
        return None


def architecture_guardrail(task_output: Any) -> Tuple[bool, Any]:
    """
    Guardrail: architecture must address all requirements (structural completeness
    when requirements are not available; full check is done when the planning crew
    runs and can call validate_architecture_against_requirements(arch, requirements)
    after both tasks complete). Returns (passed, result) for CrewAI Task guardrail API.
    Result must be a string when passed=False so CrewAI does not receive TaskOutput.
    """
    text = _task_output_text(task_output)
    data = _extract_json_block_for_arch(text)
    if not data:
        logger.warning("architecture_guardrail_no_json", output_preview=text[:200])
        return (False, "Architecture guardrail: no valid JSON in output.")
    arch = _dict_to_architecture_document(data)
    if not arch:
        logger.warning("architecture_guardrail_parse_failed")
        return (False, "Architecture guardrail: failed to parse ArchitectureDocument.")
    valid, gaps = validate_architecture_against_requirements(arch, requirements=None)
    if not valid:
        logger.warning("architecture_guardrail_gaps", gaps=gaps)
        return (False, f"Architecture guardrail: gaps or incomplete ({gaps}).")
    return (True, text)


def _get_guardrail_for_task(task_key: str) -> Callable[[Any], Tuple[bool, Any]]:
    """Return the guardrail callable for a planning task key (CrewAI: (passed, result))."""
    guardrails = {
        "requirements_gathering": requirements_guardrail,
        "architecture_design": architecture_guardrail,
    }
    if task_key not in guardrails:
        raise ValueError(f"Unknown planning task: {task_key}. Known: {list(guardrails)}")
    return guardrails[task_key]


def create_planning_tasks(
    agents: Dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> Tuple[List[Task], Dict[str, int]]:
    """
    Create CrewAI Task objects for the planning crew from config/tasks.yaml.

    Context passing: architecture_design receives requirements_gathering output
    as context. Guardrails and timeouts are applied per task.

    :param agents: Map from agent name (e.g. "product_owner", "architect") to
                   CrewAI Agent instance.
    :param config_path: Optional path to tasks.yaml.
    :return: (list of Task in order, dict of task_id -> timeout_seconds for runner).
    """
    planning = planning_tasks_config(config_path)
    if not planning:
        raise ValueError("No 'planning' section in tasks config")

    settings = get_settings()
    default_timeout = getattr(
        settings.project,
        "default_timeout",
        3600,
    )

    task_list: List[Task] = []
    task_by_key: Dict[str, Task] = {}
    timeouts: Dict[str, int] = {}

    # Order: requirements_gathering first, then architecture_design (context depends on first)
    ordered_keys = ["requirements_gathering", "architecture_design"]
    for key in ordered_keys:
        if key not in planning:
            continue
        cfg = planning[key]
        agent_name = cfg.get("agent")
        if not agent_name or agent_name not in agents:
            raise ValueError(f"Task '{key}' agent '{agent_name}' not in agents map")
        agent = agents[agent_name]

        description = cfg.get("description", "")
        expected_output = cfg.get("expected_output", "")
        output_pydantic_name = cfg.get("output_pydantic")
        output_pydantic = _output_pydantic_class(output_pydantic_name) if output_pydantic_name else None
        context_keys: List[str] = cfg.get("context") or []
        context_tasks = [task_by_key[k] for k in context_keys if k in task_by_key]
        timeout_seconds = cfg.get("timeout_seconds") or default_timeout

        guardrail_fn = _get_guardrail_for_task(key)
        task = Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            context=context_tasks,
            output_pydantic=output_pydantic,
            guardrail=guardrail_fn,
        )
        task_list.append(task)
        task_by_key[key] = task
        # CrewAI Task may not have an id; use key as identifier for timeout config
        timeouts[key] = timeout_seconds

    return task_list, timeouts
