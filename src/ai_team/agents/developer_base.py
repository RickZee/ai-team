"""
Shared DeveloperBase for Backend, Frontend, and Fullstack developers.

Provides common tools (code_generation, file_writer, dependency_resolver, code_reviewer),
self-review discipline, code style awareness (PEP8/ESLint), context awareness
(architecture doc and requirements), and guardrail integration for code quality.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import structlog

from ai_team.agents.base import BaseAgent
from ai_team.guardrails import QualityGuardrails, SecurityGuardrails
from ai_team.tools.developer_tools import get_developer_common_tools

logger = structlog.get_logger(__name__)

# Default context paths (relative to project root) for context awareness
DEFAULT_ARCHITECTURE_PATH = "docs/architecture.md"
DEFAULT_REQUIREMENTS_PATH = "docs/requirements.md"


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
        tools: Optional[List[Any]] = None,
        extra_tools: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize DeveloperBase with common developer tools.

        :param role_name: Config key (e.g. backend_developer, frontend_developer).
        :param role: Human-readable role.
        :param goal: Agent goal.
        :param backstory: Agent backstory (should mention self-review, PEP8/ESLint, context).
        :param tools: Override full tool list; if None, common tools + extra_tools are used.
        :param extra_tools: Additional tools (e.g. backend- or frontend-specific) appended to common.
        :param kwargs: Passed to BaseAgent (llm, verbose, allow_delegation, etc.).
        """
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
        object.__setattr__(self, "_architecture_path", kwargs.get("architecture_path", DEFAULT_ARCHITECTURE_PATH))
        object.__setattr__(self, "_requirements_path", kwargs.get("requirements_path", DEFAULT_REQUIREMENTS_PATH))

    @property
    def architecture_path(self) -> str:
        """Path to architecture doc for context awareness."""
        return object.__getattribute__(self, "_architecture_path")

    @property
    def requirements_path(self) -> str:
        """Path to requirements doc for context awareness."""
        return object.__getattribute__(self, "_requirements_path")

    def validate_generated_code(self, content: str) -> Tuple[bool, str]:
        """
        Run code quality and security guardrails on generated code.

        Use this in task callbacks or after code generation to ensure output
        passes security checks, optional Python/JS syntax checks, and no
        dangerous placeholders. Integrates with guardrail integration requirement.

        :param content: Generated code or mixed output (may contain markdown/code blocks).
        :return: (True, content) if valid; (False, error_message) otherwise.
        """
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
        # Python syntax check when content looks like Python
        if "def " in content or "class " in content or "import " in content:
            valid, msg = QualityGuardrails.validate_python_syntax(content)
            if not valid:
                logger.warning("developer_guardrail_syntax", reason=msg)
                return (False, msg)
        return (True, content)

    def context_instruction(self, workspace_root: Optional[Path] = None) -> str:
        """
        Return an instruction string for the agent to read architecture and requirements.

        Use when building task descriptions so the developer stays consistent
        with architecture doc and requirements.
        """
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
