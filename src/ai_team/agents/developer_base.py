"""
Shared DeveloperBase for Backend, Frontend, and Fullstack developers.

Provides common tools (code_generation, file_writer, dependency_resolver, code_reviewer),
self-review discipline, code style awareness (PEP8/ESLint), context awareness
(architecture doc and requirements), and guardrail integration for code quality.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import structlog
import yaml
from ai_team.agents.base import BaseAgent, _load_agents_config
from ai_team.guardrails import QualityGuardrails, SecurityGuardrails
from ai_team.tools.developer_tools import get_developer_common_tools

logger = structlog.get_logger(__name__)

# Default context paths (relative to project root) for context awareness
DEFAULT_ARCHITECTURE_PATH = "docs/architecture.md"
DEFAULT_REQUIREMENTS_PATH = "docs/requirements.md"

TDev = TypeVar("TDev", bound="DeveloperBase")


class DeveloperBase(BaseAgent):
    """
    Base agent for all developers (backend, frontend, fullstack).

    - Common tools: code_generation, file_writer, dependency_resolver, code_reviewer
    - Self-review: agent is instructed to review own code before marking task complete
    - Code style: PEP8 (Python) and ESLint (JS/TS) awareness in backstory
    - Context awareness: reads architecture and requirements docs for consistency
    - Guardrail integration: validate_generated_code() runs security and quality checks
    """

    def __init__(
        self,
        role_name: str,
        role: str,
        goal: str,
        backstory: str,
        *,
        tools: list[Any] | None = None,
        extra_tools: list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if tools is None:
            common = get_developer_common_tools()
            extra = list(extra_tools) if extra_tools else []
            tools = common + extra
        super().__init__(
            role_name=role_name,
            role=role,
            goal=goal,
            backstory=backstory,
            tools=tools,
            **kwargs,
        )
        object.__setattr__(
            self, "_architecture_path", kwargs.get("architecture_path", DEFAULT_ARCHITECTURE_PATH)
        )
        object.__setattr__(
            self, "_requirements_path", kwargs.get("requirements_path", DEFAULT_REQUIREMENTS_PATH)
        )

    @property
    def architecture_path(self) -> str:
        return object.__getattribute__(self, "_architecture_path")

    @property
    def requirements_path(self) -> str:
        return object.__getattribute__(self, "_requirements_path")

    def validate_generated_code(self, content: str) -> tuple[bool, str]:
        valid, msg = SecurityGuardrails.validate_code_safety(content)
        if not valid:
            logger.warning("developer_guardrail_code_safety", reason=msg)
            return (False, msg)
        valid, msg = SecurityGuardrails.validate_no_secrets(content)
        if not valid:
            logger.warning("developer_guardrail_no_secrets", reason=msg)
            return (False, msg)
        valid, msg = QualityGuardrails.validate_no_placeholders(content)
        if not valid:
            logger.warning("developer_guardrail_placeholders", reason=msg)
            return (False, msg)
        if "def " in content or "class " in content or "import " in content:
            valid, msg = QualityGuardrails.validate_python_syntax(content)
            if not valid:
                logger.warning("developer_guardrail_syntax", reason=msg)
                return (False, msg)
        return (True, content)

    def context_instruction(self, workspace_root: Path | None = None) -> str:
        root = workspace_root or Path.cwd()
        arch = root / self.architecture_path
        req = root / self.requirements_path
        parts = []
        if arch.exists():
            parts.append(f"Read {self.architecture_path} for architecture and interfaces.")
        if req.exists():
            parts.append(f"Read {self.requirements_path} for requirements and acceptance criteria.")
        if not parts:
            return "No architecture or requirements paths found; proceed from task description."
        return " ".join(parts)


def create_developer_agent(
    role_key: str,
    agent_cls: type[TDev],
    *,
    tool_getter: Callable[[], list[Any]] | None = None,
    tools: list[Any] | None = None,
    before_task: Callable[[str, dict[str, Any]], None] | None = None,
    after_task: Callable[[str, Any], None] | None = None,
    guardrail_tools: bool = True,
    config_path: Path | None = None,
    agents_config: dict[str, Any] | None = None,
    default_role: str | None = None,
    **kwargs: Any,
) -> TDev:
    """Create a developer agent from agents.yaml with optional role-specific tools."""
    if agents_config is None:
        if config_path and config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                agents_config = yaml.safe_load(f) or {}
        else:
            agents_config = _load_agents_config()

    if role_key not in agents_config:
        raise KeyError(f"'{role_key}' not in agents config. Known: {list(agents_config.keys())}")

    cfg = agents_config[role_key]
    extra_tools = None
    if tools is None and tool_getter is not None:
        extra_tools = tool_getter()
    return agent_cls(
        role_name=role_key,
        role=cfg.get("role", default_role or role_key),
        goal=cfg.get("goal", ""),
        backstory=cfg.get("backstory", ""),
        tools=tools,
        extra_tools=extra_tools,
        verbose=cfg.get("verbose", True),
        allow_delegation=cfg.get("allow_delegation", False),
        max_iter=cfg.get("max_iter", 15),
        memory=cfg.get("memory", True),
        before_task=before_task,
        after_task=after_task,
        guardrail_tools=guardrail_tools,
        **kwargs,
    )
