"""
Development-phase CrewAI tasks: backend implementation, frontend implementation,
and DevOps configuration.

Each task receives context from previous tasks, has a guardrail validation function,
supports retry with feedback on failure, and is intended to be used with structlog
for task start, progress, and completion (logging is applied at crew/flow level or
via guardrail execution).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

import structlog
from ai_team.guardrails.quality import (
    architecture_compliance_guardrail,
    code_quality_guardrail,
    documentation_guardrail,
)
from ai_team.guardrails.security import code_safety_guardrail
from ai_team.models.development import CodeFile, CodeFileList, DeploymentConfig
from crewai import Task

logger = structlog.get_logger()

# Keep retries low — crewai deadlocks during pydantic output parsing on retry 2+
GUARDRAIL_MAX_RETRIES = 1


def _task_output_to_code_files(result: Any) -> list[tuple[str, str, str]]:
    """Extract (path, content, language) from task output (TaskOutput or pydantic)."""
    files: list[tuple[str, str, str]] = []
    pydantic_out = getattr(result, "pydantic", None)
    raw = getattr(result, "raw", None) or (result if isinstance(result, str) else str(result))

    if pydantic_out is not None:
        if isinstance(pydantic_out, CodeFileList):
            for item in pydantic_out.files:
                files.append((item.path, item.content, item.language))
            return files
        if isinstance(pydantic_out, list):
            for item in pydantic_out:
                if isinstance(item, CodeFile):
                    files.append((item.path, item.content, item.language))
            return files

    # Fallback: try to parse raw as JSON list of code file dicts
    if raw and isinstance(raw, str) and raw.strip():
        logger.warning(
            "development_tasks guardrail received raw output; pydantic preferred", raw_len=len(raw)
        )
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
        try:
            parsed = json.loads(cleaned)
            items = parsed if isinstance(parsed, list) else parsed.get("files", [])
            for item in items:
                if isinstance(item, dict) and "path" in item and "content" in item:
                    files.append((item["path"], item["content"], item.get("language", "python")))
            if files:
                logger.info(
                    "development_tasks guardrail parsed raw json fallback",
                    file_count=len(files),
                )
        except (json.JSONDecodeError, AttributeError, TypeError) as exc:
            logger.warning("development_tasks guardrail raw json parse failed", error=str(exc))
    return files


def _backend_implementation_guardrail(
    result: Any,
    architecture: dict | None = None,
) -> tuple[bool, Any]:
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

    paths: list[str] = []
    for path, content, language in code_files:
        paths.append(path)
        lang = (language or "python").lower()
        # Code safety (lint / dangerous patterns)
        safety = code_safety_guardrail(content)
        if safety.should_block():
            logger.warning(
                "backend_implementation guardrail failed", path=path, reason=safety.message
            )
            return (False, f"{path}: {safety.message}")
        # Code quality (length, complexity, naming, docstrings)
        quality = code_quality_guardrail(content, language=lang)
        if not quality.passed:
            feedback = (
                "; ".join(quality.suggestions[:5]) if quality.suggestions else quality.message
            )
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
            feedback = (
                "; ".join(arch_result.suggestions[:3])
                if arch_result.suggestions
                else arch_result.message
            )
            logger.warning("backend_implementation guardrail failed", reason=feedback)
            return (False, f"Architecture compliance: {feedback}")

    logger.info("backend_implementation guardrail passed", file_count=len(code_files))
    # Return raw string so CrewAI calls _export_output() and sets task_output.pydantic.
    # If we return the TaskOutput object directly, CrewAI skips pydantic re-parsing.
    raw = getattr(result, "raw", None)
    return (True, raw if raw is not None else result)


def _frontend_implementation_guardrail(result: Any):
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
    # Only check markup/style files — package.json, .env, .md etc. never have aria-/flex
    ui_extensions = {".css", ".html", ".htm", ".jsx", ".tsx", ".js", ".ts", ".vue", ".svelte"}

    ui_files = [
        (path, content, lang)
        for path, content, lang in code_files
        if any(path.lower().endswith(ext) for ext in ui_extensions)
        or lang in {"css", "html", "javascript", "typescript", "jsx", "tsx"}
    ]

    # If no UI files at all, skip — non-UI project accidentally routed through frontend crew
    if not ui_files:
        logger.info("frontend_implementation guardrail skipped", reason="no_ui_files")
        raw = getattr(result, "raw", None)
        return (True, raw if raw is not None else result)

    for path, content, _ in ui_files:
        if not responsive_patterns.search(content):
            msg = f"{path}: Add responsive design (e.g. @media, flex/grid, viewport)."
            logger.warning("frontend_implementation guardrail failed", path=path, reason=msg)
            return (False, msg)
        if not a11y_patterns.search(content):
            msg = f"{path}: Add accessibility (e.g. aria-*, role=, alt=)."
            logger.warning("frontend_implementation guardrail failed", path=path, reason=msg)
            return (False, msg)

    logger.info("frontend_implementation guardrail passed", file_count=len(code_files))
    raw = getattr(result, "raw", None)
    return (True, raw if raw is not None else result)


def _devops_configuration_guardrail(result: Any):
    """
    Validate DevOps task output: DeploymentConfig must include Dockerfile, compose,
    and CI pipeline (or equivalent). Returns (True, result) or (False, feedback_message).
    """
    logger.info("devops_configuration guardrail started")
    pydantic_out = getattr(result, "pydantic", None)
    cfg: DeploymentConfig | None = None
    if pydantic_out is not None and isinstance(pydantic_out, DeploymentConfig):
        cfg = pydantic_out
    else:
        # Fallback: try to parse raw JSON output into DeploymentConfig
        raw = getattr(result, "raw", None) or (result if isinstance(result, str) else None)
        if raw and isinstance(raw, str) and raw.strip():
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned)
            try:
                data = json.loads(cleaned)
                if isinstance(data, dict):
                    cfg = DeploymentConfig(
                        **{k: v for k, v in data.items() if k in DeploymentConfig.model_fields}
                    )
                    logger.info("devops_configuration guardrail parsed raw json fallback")
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                logger.warning(
                    "devops_configuration guardrail raw json parse failed", error=str(exc)
                )
        if cfg is None:
            msg = "DevOps configuration must produce a DeploymentConfig (Dockerfile, compose, CI pipeline)."
            logger.warning("devops_configuration guardrail failed", reason=msg)
            return (False, msg)

    assert cfg is not None

    if not (cfg.dockerfile or cfg.docker_compose):
        msg = "DeploymentConfig must include at least a Dockerfile or docker-compose content."
        logger.warning("devops_configuration guardrail failed", reason=msg)
        return (False, msg)
    if not cfg.ci_cd_config:
        msg = "DeploymentConfig must include a CI/CD pipeline configuration."
        logger.warning("devops_configuration guardrail failed", reason=msg)
        return (False, msg)

    logger.info("devops_configuration guardrail passed")
    raw = getattr(result, "raw", None)
    return (True, raw if raw is not None else result)


def create_backend_implementation_task(
    agent: Any,
    context: Sequence[Task] | None = None,
    architecture: dict | None = None,
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

    def guardrail_fn(result: Any):
        return _backend_implementation_guardrail(result, architecture=architecture)

    return Task(
        description=(
            "Implement ONLY what is specified in the requirements and architecture below. "
            "Do not add features, frameworks, or files not listed. "
            "Produce source files and tests that pass lint, have docstrings, and strictly follow the architecture.\n\n"
            "REQUIREMENTS:\n{requirements_doc}\n\n"
            "ARCHITECTURE:\n{architecture_doc}"
        ),
        expected_output=(
            'JSON object with a "files" key containing a list of CodeFile objects. '
            'Example: {"files": [{"path": "src/app.py", "content": "...", "language": "python", '
            '"description": "...", "has_tests": false}]}'
        ),
        agent=agent,
        context=list(context) if context else [],
        output_pydantic=CodeFileList,
        guardrail=guardrail_fn,
        guardrail_max_retries=guardrail_max_retries,
    )


def create_frontend_implementation_task(
    agent: Any,
    context: Sequence[Task] | None = None,
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
        description=(
            "Implement ONLY the frontend components specified in the requirements and architecture below. "
            "Do not add pages, features, or dependencies not listed. "
            "Produce responsive, accessible components.\n\n"
            "REQUIREMENTS:\n{requirements_doc}\n\n"
            "ARCHITECTURE:\n{architecture_doc}"
        ),
        expected_output=(
            'JSON object with a "files" key containing a list of CodeFile objects. '
            'Example: {"files": [{"path": "src/App.jsx", "content": "...", "language": "javascript", '
            '"description": "...", "has_tests": false}]}'
        ),
        agent=agent,
        context=list(context) if context else [],
        output_pydantic=CodeFileList,
        guardrail=_frontend_implementation_guardrail,
        guardrail_max_retries=guardrail_max_retries,
    )


def create_devops_configuration_task(
    agent: Any,
    context: Sequence[Task] | None = None,
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
