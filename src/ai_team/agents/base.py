"""
Base Agent for AI Team.

Extends CrewAI's Agent with configuration from YAML/settings, Ollama LLM,
structlog, memory hooks, guardrails, retry logic, token tracking, and health checks.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

import structlog
import yaml
from crewai import Agent, LLM
from langchain_ollama import ChatOllama
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ai_team.config.settings import get_settings
from ai_team.guardrails import SecurityGuardrails

logger = structlog.get_logger(__name__)

# Map agents.yaml role keys to settings.get_model_for_role() keys
ROLE_TO_SETTINGS_KEY: Dict[str, str] = {
    "manager": "manager",
    "product_owner": "product_owner",
    "architect": "architect",
    "backend_developer": "backend_dev",
    "frontend_developer": "frontend_dev",
    "fullstack_developer": "fullstack_dev",
    "devops_engineer": "devops",
    "cloud_engineer": "cloud",
    "qa_engineer": "qa",
}

T = TypeVar("T")


def _load_agents_config() -> Dict[str, Any]:
    """Load agent definitions from config/agents.yaml."""
    config_path = Path(__file__).resolve().parent.parent / "config" / "agents.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Agents config not found: {config_path}")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class _RetryOllamaLLM(ChatOllama):
    """ChatOllama wrapper that retries on failure with exponential backoff."""

    def __init__(
        self,
        max_retries: int = 3,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._max_retries = max_retries

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        @retry(
            retry=retry_if_exception_type((Exception,)),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=60),
            reraise=True,
        )
        def _invoke() -> Any:
            return super(_RetryOllamaLLM, self).invoke(*args, **kwargs)

        return _invoke()


def _wrap_tool_with_guardrail(tool: Any, guardrail_enabled: bool = True) -> Any:
    """Wrap a tool so that execution runs through guardrail checks (input/output)."""
    if not guardrail_enabled:
        return tool

    original_run = getattr(tool, "_run", None) or getattr(tool, "run", None)
    if original_run is None:
        return tool

    def guarded_run(*args: Any, **kwargs: Any) -> str:
        # Validate string inputs for dangerous content
        for v in list(args) + list(kwargs.values()):
            if isinstance(v, str):
                valid, msg = SecurityGuardrails.validate_code_safety(v)
                if not valid:
                    logger.warning("guardrail_blocked_tool_input", reason=msg)
                    return f"Guardrail blocked: {msg}"
        result = original_run(*args, **kwargs)
        if isinstance(result, str):
            valid, msg = SecurityGuardrails.validate_code_safety(result)
            if not valid:
                logger.warning("guardrail_blocked_tool_output", reason=msg)
                return f"Guardrail blocked output: {msg}"
        return result

    if hasattr(tool, "_run"):
        tool._run = guarded_run
    else:
        tool.run = guarded_run
    return tool


class BaseAgent(Agent):
    """
    CrewAI Agent extended with YAML/settings config, Ollama LLM, logging,
    memory hooks, guardrails, retry, token tracking, and health check.
    """

    def __init__(
        self,
        role_name: str,
        role: str,
        goal: str,
        backstory: str,
        *,
        llm: Optional[Any] = None,
        tools: Optional[List[Any]] = None,
        verbose: bool = True,
        allow_delegation: bool = False,
        max_iter: int = 15,
        memory: bool = True,
        before_task: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        after_task: Optional[Callable[[str, Any], None]] = None,
        guardrail_tools: bool = True,
        config_path: Optional[Path] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize BaseAgent.

        :param role_name: Key used in agents.yaml and for model mapping (e.g. 'manager').
        :param role: Human-readable role (e.g. "Engineering Manager").
        :param goal: Agent goal.
        :param backstory: Agent backstory.
        :param llm: Optional LLM instance; if None, one is created from settings for role_name.
        :param tools: Optional list of tools to attach.
        :param verbose: Enable verbose logging.
        :param allow_delegation: Whether agent can delegate.
        :param max_iter: Max reasoning iterations per task.
        :param memory: Use memory.
        :param before_task: Optional callback(task_id, context) for memory persistence before task.
        :param after_task: Optional callback(task_id, output) for memory persistence after task.
        :param guardrail_tools: If True, wrap tools with guardrail checks.
        :param config_path: Override path to agents config (for tests).
        :param kwargs: Passed to CrewAI Agent.
        """
        settings = get_settings()

        if llm is None:
            settings_key = ROLE_TO_SETTINGS_KEY.get(role_name.lower(), role_name.lower())
            model = settings.ollama.get_model_for_role(settings_key)
            # CrewAI 1.x resolves LLM by model name; use "ollama/<model>" so it uses
            # LiteLLM for Ollama instead of the native OpenAI provider (which requires OPENAI_API_KEY).
            llm = LLM(
                model=f"ollama/{model}",
                api_base=settings.ollama.base_url,
                timeout=settings.ollama.request_timeout,
            )
            logger.info(
                "agent_llm_initialized",
                role_name=role_name,
                model=model,
            )

        tool_list = list(tools) if tools else []
        if guardrail_tools and settings.guardrails.security_enabled:
            tool_list = [_wrap_tool_with_guardrail(t, guardrail_tools) for t in tool_list]

        super().__init__(
            role=role,
            goal=goal,
            backstory=backstory,
            llm=llm,
            tools=tool_list,
            verbose=verbose,
            allow_delegation=allow_delegation,
            max_iter=max_iter,
            memory=memory,
            **kwargs,
        )
        # Set custom attributes after super().__init__ so Pydantic doesn't strip them
        object.__setattr__(self, "_role_name", role_name)
        object.__setattr__(self, "_before_task", before_task)
        object.__setattr__(self, "_after_task", after_task)
        object.__setattr__(self, "_token_usage", {"input_tokens": 0, "output_tokens": 0})

    @property
    def role_name(self) -> str:
        """Return the agent role name (config key)."""
        return object.__getattribute__(self, "_role_name")

    @property
    def token_usage(self) -> Dict[str, int]:
        """Return cumulative token usage for this agent."""
        return dict(object.__getattribute__(self, "_token_usage"))

    def record_tokens(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Record token usage (call from hooks or after LLM calls)."""
        usage = object.__getattribute__(self, "_token_usage")
        usage["input_tokens"] += input_tokens
        usage["output_tokens"] += output_tokens
        logger.debug(
            "agent_token_usage",
            role_name=self._role_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def before_task_callback(self, task_id: str, context: Dict[str, Any]) -> None:
        """Invoke before_task hook for memory persistence. Call from task setup if needed."""
        before_task = object.__getattribute__(self, "_before_task")
        if before_task:
            before_task(task_id, context)
            logger.debug("agent_before_task", role_name=self.role_name, task_id=task_id)

    def after_task_callback(self, task_id: str, output: Any) -> None:
        """Invoke after_task hook for memory persistence. Use as Task callback."""
        after_task = object.__getattribute__(self, "_after_task")
        if after_task:
            after_task(task_id, output)
        logger.debug("agent_after_task", role_name=self.role_name, task_id=task_id)

    def attach_tools(self, tools: List[Any], guardrail: bool = True) -> None:
        """Attach tools to this agent (optionally wrapped with guardrails)."""
        settings = get_settings()
        if guardrail and settings.guardrails.security_enabled:
            tools = [_wrap_tool_with_guardrail(t, True) for t in tools]
        self.tools = list(getattr(self, "tools", [])) + list(tools)
        logger.info("agent_tools_attached", role_name=self._role_name, count=len(tools))

    def health_check(self) -> bool:
        """Verify the agent's assigned model is available (Ollama)."""
        settings = get_settings()
        if not settings.ollama.check_health():
            return False
        # Optionally check that the specific model is listed
        try:
            import httpx
            r = httpx.get(
                f"{settings.ollama.base_url.rstrip('/')}/api/tags",
                timeout=5,
            )
            if r.status_code != 200:
                return False
            data = r.json()
            models = [m.get("name") for m in data.get("models", [])]
            # Our LLM may use model name with :tag
            llm = getattr(self, "llm", None)
            model = getattr(llm, "model", None) if llm else None
            if model and models:
                base = model.split(":")[0] if ":" in model else model
                if not any(base in m for m in models):
                    logger.warning("agent_model_not_found", model=model, available=models[:5])
                    return False
        except Exception as e:
            logger.warning("agent_health_check_error", error=str(e))
            return False
        return True


def create_agent(
    role_name: str,
    *,
    tools: Optional[List[Any]] = None,
    before_task: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    after_task: Optional[Callable[[str, Any], None]] = None,
    guardrail_tools: bool = True,
    config_path: Optional[Path] = None,
    agents_config: Optional[Dict[str, Any]] = None,
) -> BaseAgent:
    """
    Factory: create a configured Agent from agents.yaml and settings.

    :param role_name: Key in agents.yaml (e.g. 'manager', 'backend_developer').
    :param tools: Optional tools to attach.
    :param before_task: Optional callback for memory before task.
    :param after_task: Optional callback for memory after task.
    :param guardrail_tools: Wrap tools with guardrail checks.
    :param config_path: Override path to agents YAML (for tests).
    :param agents_config: Pre-loaded config dict (overrides loading from file).
    :return: Configured BaseAgent instance.
    """
    if agents_config is None:
        if config_path and config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                agents_config = yaml.safe_load(f) or {}
        else:
            agents_config = _load_agents_config()

    role_key = role_name.lower().strip()
    if role_key not in agents_config:
        raise KeyError(f"Unknown role_name '{role_name}'. Known: {list(agents_config.keys())}")

    cfg = agents_config[role_key]
    return BaseAgent(
        role_name=role_key,
        role=cfg.get("role", role_name),
        goal=cfg.get("goal", ""),
        backstory=cfg.get("backstory", ""),
        tools=tools or [],
        verbose=cfg.get("verbose", True),
        allow_delegation=cfg.get("allow_delegation", False),
        max_iter=cfg.get("max_iter", 15),
        memory=cfg.get("memory", True),
        before_task=before_task,
        after_task=after_task,
        guardrail_tools=guardrail_tools,
        config_path=config_path,
    )
