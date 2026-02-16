"""
Development-phase CrewAI tasks: backend implementation, frontend implementation,
and DevOps configuration.

Each task receives context from previous tasks, has a guardrail validation function,
supports retry with feedback on failure, and is intended to be used with structlog
for task start, progress, and completion (logging is applied at crew/flow level or
via guardrail execution).
"""

from __future__ import annotations

import re
from typing import Any, List, Optional, Sequence, Tuple

from crewai import Task
import structlog

from ai_team.models.development import CodeFile, CodeFileList, DeploymentConfig
from ai_team.guardrails.quality import (
    architecture_compliance_guardrail,
    code_quality_guardrail,
    documentation_guardrail,
)
from ai_team.guardrails.security import code_safety_guardrail

logger = structlog.get_logger()

# Default retries for guardrail failure (CrewAI will retry with feedback)
GUARDRAIL_MAX_RETRIES = 3


def _task_output_to_code_files(result: Any) -> List[Tuple[str, str, str]]:
    """Extract (path, content, language) from task output (TaskOutput or pydantic)."""
    files: List[Tuple[str, str, str]] = []
    pydantic_out = getattr(result, "pydantic", None)
    raw = getattr(result, "raw", None) or (result if isinstance(result, str) else str(result))

    if pydantic_out is not None:
        if isinstance(pydantic_out, CodeFileList):
            for item in pydantic_out.root:
                files.append((item.path, item.content, item.language))
            return files
        if isinstance(pydantic_out, list):
            for item in pydantic_out:
                if isinstance(item, CodeFile):
                    files.append((item.path, item.content, item.language))
            return files

    # Fallback: try to parse raw as list of code file descriptions (e.g. JSON-like)
    if raw and isinstance(raw, str) and raw.strip():
        # Minimal heuristic: look for path/content-like blocks (caller may use output_pydantic)
        logger.warning("development_tasks guardrail received raw output; pydantic preferred", raw_len=len(raw))
    return files


def _backend_implementation_guardrail(
    result: Any,
    architecture: Optional[dict] = None,
) -> Tuple[bool, Any]:
    """
    Validate backend task output: code must pass lint (quality), have docstrings,
    and follow architecture. Used as CrewAI task guardrail; returns (True, result)
    or (False, feedback_message).
    """
    logger.info("backend_implementation guardrail started")
    code_files = _task_output_to_code_files(result)
    if not code_files:
        msg = "Backend implementation must produce at least one CodeFile."
        logger.warning("backend_implementation guardrail failed", reason=msg)
        return (False, msg)

    paths: List[str] = []
    for path, content, language in code_files:
        paths.append(path)
        lang = (language or "python").lower()
        # Code safety (lint / dangerous patterns)
        safety = code_safety_guardrail(content)
        if safety.should_block():
            logger.warning("backend_implementation guardrail failed", path=path, reason=safety.message)
            return (False, f"{path}: {safety.message}")
        # Code quality (length, complexity, naming, docstrings)
        quality = code_quality_guardrail(content, language=lang)
        if not quality.passed:
            feedback = "; ".join(quality.suggestions[:5]) if quality.suggestions else quality.message
            logger.warning("backend_implementation guardrail failed", path=path, reason=feedback)
            return (False, f"{path}: {feedback}")
        # Documentation (docstrings for public functions)
        docs = documentation_guardrail(content, docs=content)
        if not docs.passed:
            feedback = "; ".join(docs.suggestions[:3]) if docs.suggestions else docs.message
            logger.warning("backend_implementation guardrail failed", path=path, reason=feedback)
            return (False, f"{path}: {feedback}")

    if architecture:
        arch_result = architecture_compliance_guardrail(paths, architecture)
        if not arch_result.passed:
            feedback = "; ".join(arch_result.suggestions[:3]) if arch_result.suggestions else arch_result.message
            logger.warning("backend_implementation guardrail failed", reason=feedback)
            return (False, f"Architecture compliance: {feedback}")

    logger.info("backend_implementation guardrail passed", file_count=len(code_files))
    return (True, result)


def _frontend_implementation_guardrail(result: Any) -> Tuple[bool, Any]:
    """
    Validate frontend task output: components must be responsive and accessible.
    Heuristics: presence of @media / flex / grid for responsive; aria-*, role=, alt= for a11y.
    """
    logger.info("frontend_implementation guardrail started")
    code_files = _task_output_to_code_files(result)
    if not code_files:
        msg = "Frontend implementation must produce at least one CodeFile."
        logger.warning("frontend_implementation guardrail failed", reason=msg)
        return (False, msg)

    responsive_patterns = re.compile(
        r"@media\s|flex|grid|responsive|min-width|max-width|viewport",
        re.IGNORECASE,
    )
    a11y_patterns = re.compile(
        r"aria-|role\s*=\s*[\"']|alt\s*=\s*[\"']|tabindex|aria-label",
        re.IGNORECASE,
    )

    for path, content, _ in code_files:
        if not responsive_patterns.search(content):
            msg = f"{path}: Add responsive design (e.g. @media, flex/grid, viewport)."
            logger.warning("frontend_implementation guardrail failed", path=path, reason=msg)
            return (False, msg)
        if not a11y_patterns.search(content):
            msg = f"{path}: Add accessibility (e.g. aria-*, role=, alt=)."
            logger.warning("frontend_implementation guardrail failed", path=path, reason=msg)
            return (False, msg)

    logger.info("frontend_implementation guardrail passed", file_count=len(code_files))
    return (True, result)


def _devops_configuration_guardrail(result: Any) -> Tuple[bool, Any]:
    """
    Validate DevOps task output: DeploymentConfig must include Dockerfile, compose,
    and CI pipeline (or equivalent). Returns (True, result) or (False, feedback_message).
    """
    logger.info("devops_configuration guardrail started")
    pydantic_out = getattr(result, "pydantic", None)
    if pydantic_out is not None and isinstance(pydantic_out, DeploymentConfig):
        cfg = pydantic_out
    else:
        msg = "DevOps configuration must produce a DeploymentConfig (Dockerfile, compose, CI pipeline)."
        logger.warning("devops_configuration guardrail failed", reason=msg)
        return (False, msg)

    if not (cfg.dockerfile or cfg.docker_compose):
        msg = "DeploymentConfig must include at least a Dockerfile or docker-compose content."
        logger.warning("devops_configuration guardrail failed", reason=msg)
        return (False, msg)
    if not cfg.ci_cd_config:
        msg = "DeploymentConfig must include a CI/CD pipeline configuration."
        logger.warning("devops_configuration guardrail failed", reason=msg)
        return (False, msg)

    logger.info("devops_configuration guardrail passed")
    return (True, result)


def create_backend_implementation_task(
    agent: Any,
    context: Optional[Sequence[Task]] = None,
    architecture: Optional[dict] = None,
    guardrail_max_retries: int = GUARDRAIL_MAX_RETRIES,
) -> Task:
    """
    Create the backend_implementation task.

    Args:
        agent: CrewAI agent (e.g. backend_developer).
        context: List of tasks that provide context (e.g. [architecture_design, requirements_gathering]).
        architecture: Optional architecture dict for compliance guardrail (layers, forbidden_imports).
        guardrail_max_retries: Number of retries on guardrail failure.

    Returns:
        CrewAI Task configured for backend implementation.
    """
    def guardrail_fn(result: Any) -> Tuple[bool, Any]:
        return _backend_implementation_guardrail(result, architecture=architecture)

    return Task(
        description="Implement backend code based on architecture and requirements. Produce source files, tests, and configs that pass lint, have docstrings, and follow the architecture.",
        expected_output="List of CodeFile objects with source, tests, and configs.",
        agent=agent,
        context=list(context) if context else [],
        output_pydantic=CodeFileList,
        guardrail=guardrail_fn,
        guardrail_max_retries=guardrail_max_retries,
    )


def create_frontend_implementation_task(
    agent: Any,
    context: Optional[Sequence[Task]] = None,
    guardrail_max_retries: int = GUARDRAIL_MAX_RETRIES,
) -> Task:
    """
    Create the frontend_implementation task.

    Args:
        agent: CrewAI agent (e.g. frontend_developer).
        context: List of tasks that provide context (e.g. [architecture_design, backend_implementation]).
        guardrail_max_retries: Number of retries on guardrail failure.

    Returns:
        CrewAI Task configured for frontend implementation.
    """
    return Task(
        description="Implement frontend UI based on architecture and backend APIs. Produce components that are responsive and accessible.",
        expected_output="List of CodeFile objects for frontend components (HTML/CSS/JS or framework components).",
        agent=agent,
        context=list(context) if context else [],
        output_pydantic=CodeFileList,
        guardrail=_frontend_implementation_guardrail,
        guardrail_max_retries=guardrail_max_retries,
    )


def create_devops_configuration_task(
    agent: Any,
    context: Optional[Sequence[Task]] = None,
    guardrail_max_retries: int = GUARDRAIL_MAX_RETRIES,
) -> Task:
    """
    Create the devops_configuration task.

    Args:
        agent: CrewAI agent (e.g. devops_engineer).
        context: List of tasks that provide context (e.g. [architecture_design, backend_implementation, frontend_implementation]).
        guardrail_max_retries: Number of retries on guardrail failure.

    Returns:
        CrewAI Task configured for DevOps configuration.
    """
    return Task(
        description="Create Docker, CI/CD, and deployment configs. Produce a DeploymentConfig with Dockerfile, docker-compose, and CI pipeline.",
        expected_output="DeploymentConfig with Dockerfile, compose, and CI pipeline.",
        agent=agent,
        context=list(context) if context else [],
        output_pydantic=DeploymentConfig,
        guardrail=_devops_configuration_guardrail,
        guardrail_max_retries=guardrail_max_retries,
    )
