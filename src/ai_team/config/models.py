"""
OpenRouter model configuration for 3-tier environments (dev, test, prod).

CrewAI uses LiteLLM under the hood. Model IDs use the
'openrouter/<provider>/<model>' format for LiteLLM routing.
Controlled by AI_TEAM_ENV; see docs/MODELS.md for the role×tier matrix,
strengths/weaknesses, and justification for each pick.
"""

from __future__ import annotations

from enum import Enum

import structlog
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger(__name__)


class Environment(str, Enum):
    """Active environment tier; set via AI_TEAM_ENV."""

    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class ModelPricing:
    """Per-million-token pricing for cost estimation. Not a Pydantic model to avoid nesting in RoleModelConfig from _PRICES."""

    __slots__ = ("input_per_m", "output_per_m")

    def __init__(self, input_per_m: float, output_per_m: float) -> None:
        self.input_per_m = input_per_m
        self.output_per_m = output_per_m

    def estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for given input and output token counts."""
        return (input_tokens / 1_000_000) * self.input_per_m + (
            output_tokens / 1_000_000
        ) * self.output_per_m


class RoleModelConfig:
    """Model assignment + pricing + temperature for a single agent role. Plain class for use in ENV_MODELS."""

    __slots__ = ("model_id", "pricing", "temperature", "max_tokens")

    def __init__(
        self,
        model_id: str,
        pricing: ModelPricing,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        self.model_id = model_id
        self.pricing = pricing
        self.temperature = temperature
        self.max_tokens = max_tokens


# ── Token budgets per role (medium-complexity project) ──────────────────────

ROLE_TOKEN_BUDGETS: dict[str, dict[str, int]] = {
    "manager": {"input": 3_000, "output": 2_000},
    "product_owner": {"input": 2_000, "output": 4_000},
    "architect": {"input": 4_000, "output": 6_000},
    "backend_developer": {"input": 6_000, "output": 12_000},
    "frontend_developer": {"input": 5_000, "output": 10_000},
    "fullstack_developer": {"input": 5_500, "output": 11_000},
    "cloud_engineer": {"input": 3_000, "output": 5_000},
    "devops": {"input": 3_000, "output": 5_000},
    "qa_engineer": {"input": 5_000, "output": 8_000},
}

# ── Model ID constants (openrouter/<provider>/<model>) ──────────────────────
# IDs verified against OpenRouter /models (2026-07). Pricing is OpenRouter
# pass-through $/1M tokens — re-check https://openrouter.ai/models before prod budgets.
# Justification for each assignment: docs/MODELS.md.

_DEEPSEEK_V4_FLASH = "openrouter/deepseek/deepseek-v4-flash"
_DEEPSEEK_V4_PRO = "openrouter/deepseek/deepseek-v4-pro"
_GEMINI_35_FLASH = "openrouter/google/gemini-3.5-flash"
_MINIMAX_M3 = "openrouter/minimax/minimax-m3"
_CLAUDE_SONNET_46 = "openrouter/anthropic/claude-sonnet-4.6"
_CLAUDE_OPUS_48 = "openrouter/anthropic/claude-opus-4.8"
_GPT54 = "openrouter/openai/gpt-5.4"
_GPT55 = "openrouter/openai/gpt-5.5"

_PRICES: dict[str, ModelPricing] = {
    _DEEPSEEK_V4_FLASH: ModelPricing(input_per_m=0.09, output_per_m=0.18),
    _DEEPSEEK_V4_PRO: ModelPricing(input_per_m=0.435, output_per_m=0.87),
    _GEMINI_35_FLASH: ModelPricing(input_per_m=1.50, output_per_m=9.00),
    _MINIMAX_M3: ModelPricing(input_per_m=0.30, output_per_m=1.20),
    _CLAUDE_SONNET_46: ModelPricing(input_per_m=3.00, output_per_m=15.00),
    _CLAUDE_OPUS_48: ModelPricing(input_per_m=5.00, output_per_m=25.00),
    _GPT54: ModelPricing(input_per_m=2.50, output_per_m=15.00),
    _GPT55: ModelPricing(input_per_m=5.00, output_per_m=30.00),
}


def _role(
    model_id: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> RoleModelConfig:
    return RoleModelConfig(
        model_id=model_id,
        pricing=_PRICES[model_id],
        temperature=temperature,
        max_tokens=max_tokens,
    )


ENV_MODELS: dict[Environment, dict[str, RoleModelConfig]] = {
    # DEV — one cheap generalist; validate wiring, not quality ceilings.
    Environment.DEV: {
        "manager": _role(_DEEPSEEK_V4_FLASH),
        "product_owner": _role(_DEEPSEEK_V4_FLASH),
        "architect": _role(_DEEPSEEK_V4_FLASH),
        "backend_developer": _role(_DEEPSEEK_V4_FLASH, temperature=0.4),
        "frontend_developer": _role(_DEEPSEEK_V4_FLASH, temperature=0.4),
        "fullstack_developer": _role(_DEEPSEEK_V4_FLASH, temperature=0.4),
        "cloud_engineer": _role(_DEEPSEEK_V4_FLASH, temperature=0.4),
        "devops": _role(_DEEPSEEK_V4_FLASH, temperature=0.4),
        "qa_engineer": _role(_DEEPSEEK_V4_FLASH, temperature=0.4),
    },
    # TEST — role-fit mid-tier: orchestrators vs reasoners vs coders.
    Environment.TEST: {
        "manager": _role(_GEMINI_35_FLASH),
        "product_owner": _role(_GEMINI_35_FLASH),
        "architect": _role(_DEEPSEEK_V4_PRO, temperature=0.3),
        "backend_developer": _role(_MINIMAX_M3, temperature=0.4),
        "frontend_developer": _role(_MINIMAX_M3, temperature=0.4),
        "fullstack_developer": _role(_MINIMAX_M3, temperature=0.4),
        "cloud_engineer": _role(_DEEPSEEK_V4_PRO, temperature=0.3),
        "devops": _role(_MINIMAX_M3, temperature=0.4),
        "qa_engineer": _role(_DEEPSEEK_V4_PRO, temperature=0.3),
    },
    # PROD — best-fit frontier mix; Opus only where ambiguity cost is highest.
    Environment.PROD: {
        "manager": _role(_CLAUDE_SONNET_46, temperature=0.5),
        "product_owner": _role(_GPT54, temperature=0.5),
        "architect": _role(_CLAUDE_OPUS_48, temperature=0.3),
        "backend_developer": _role(_GPT55, temperature=0.2),
        "frontend_developer": _role(_CLAUDE_SONNET_46, temperature=0.3),
        "fullstack_developer": _role(_GPT55, temperature=0.2),
        "cloud_engineer": _role(_CLAUDE_SONNET_46, temperature=0.3),
        "devops": _role(_GPT54, temperature=0.3),
        "qa_engineer": _role(_CLAUDE_SONNET_46, temperature=0.3),
    },
}

# ── Anthropic Messages API (Claude Agent SDK) ─────────────────────────────────
# The SDK accepts short tokens (sonnet, opus, haiku). Use these full strings when
# pinning models in team profile overrides or documentation.
ANTHROPIC_MESSAGES_MODEL_SONNET = "claude-sonnet-4-6"
ANTHROPIC_MESSAGES_MODEL_OPUS = "claude-opus-4-8"
ANTHROPIC_MESSAGES_MODEL_HAIKU = "claude-haiku-4-5"


class OpenRouterSettings(BaseSettings):
    """OpenRouter and environment settings loaded from .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Default to empty string so tooling (e.g. mypy) doesn't treat it as a required constructor arg.
    # Runtime code should still validate presence before making real network calls.
    openrouter_api_key: str = Field(
        default="",
        description="OpenRouter API key",
        alias="OPENROUTER_API_KEY",
    )
    openrouter_api_base: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API base URL",
        alias="OPENROUTER_API_BASE",
    )
    ai_team_env: Environment = Field(
        default=Environment.DEV,
        description="Active tier: dev | test | prod",
        alias="AI_TEAM_ENV",
    )
    max_cost_per_run: float = Field(
        default=5.0,
        ge=0,
        description="Max spend per pipeline run (USD)",
        alias="AI_TEAM_MAX_COST_PER_RUN",
    )
    show_cost_estimate: bool = Field(
        default=True,
        description="Show cost estimate before execution",
        alias="AI_TEAM_SHOW_COST_ESTIMATE",
    )
    prod_confirm: bool = Field(
        default=True,
        description="Require confirmation before prod runs",
        alias="AI_TEAM_PROD_CONFIRM",
    )
    or_site_url: str = Field(
        default="",
        description="Site URL for OpenRouter identification",
        alias="OR_SITE_URL",
    )
    or_app_name: str = Field(
        default="AI-Team-Capstone",
        description="App name for OpenRouter identification",
        alias="OR_APP_NAME",
    )

    def get_models(self) -> dict[str, RoleModelConfig]:
        """Return role → RoleModelConfig for the current environment."""
        return ENV_MODELS[self.ai_team_env]

    def get_model_for_role(self, role: str) -> RoleModelConfig:
        """Return RoleModelConfig for the given agent role. Normalizes devops_engineer → devops."""
        models = self.get_models()
        key = role.lower()
        if key == "devops_engineer":
            key = "devops"
        if key not in models:
            logger.warning("unknown_role_model", role=role, fallback="manager")
        return models.get(key, models["manager"])
