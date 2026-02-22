"""
OpenRouter model configuration for 3-tier environments (dev, test, prod).

CrewAI uses LiteLLM under the hood. Model IDs use the
'openrouter/<provider>/<model>' format for LiteLLM routing.
Controlled by AI_TEAM_ENV; see the config guide for exact model IDs and pricing.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

ROLE_TOKEN_BUDGETS: Dict[str, Dict[str, int]] = {
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

_DEEPSEEK_V3 = "openrouter/deepseek/deepseek-chat-v3-0324"
_DEVSTRAL_2 = "openrouter/mistralai/devstral-2-2507"
_DEEPSEEK_R1 = "openrouter/deepseek/deepseek-r1-0528"
_GEMINI_FLASH = "openrouter/google/gemini-3.0-flash"
_MINIMAX_M2 = "openrouter/minimax/minimax-m2-1"
_CLAUDE_SONNET = "openrouter/anthropic/claude-sonnet-4"
_GPT52 = "openrouter/openai/gpt-5.2"
_GPT53_CODEX = "openrouter/openai/codex-gpt-5.3"

# Pricing per 1M tokens (input, output) — from config guide
_PRICES: Dict[str, ModelPricing] = {
    _DEEPSEEK_V3: ModelPricing(input_per_m=0.25, output_per_m=0.38),
    _DEVSTRAL_2: ModelPricing(input_per_m=0.05, output_per_m=0.22),
    _DEEPSEEK_R1: ModelPricing(input_per_m=0.40, output_per_m=1.75),
    _GEMINI_FLASH: ModelPricing(input_per_m=0.50, output_per_m=3.00),
    _MINIMAX_M2: ModelPricing(input_per_m=0.28, output_per_m=1.20),
    _CLAUDE_SONNET: ModelPricing(input_per_m=3.00, output_per_m=15.00),
    _GPT52: ModelPricing(input_per_m=2.00, output_per_m=14.00),
    _GPT53_CODEX: ModelPricing(input_per_m=3.00, output_per_m=12.00),
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


ENV_MODELS: Dict[Environment, Dict[str, RoleModelConfig]] = {
    Environment.DEV: {
        "manager": _role(_DEEPSEEK_V3),
        "product_owner": _role(_DEEPSEEK_V3),
        "architect": _role(_DEEPSEEK_V3),
        "backend_developer": _role(_DEVSTRAL_2, temperature=0.4),
        "frontend_developer": _role(_DEVSTRAL_2, temperature=0.4),
        "fullstack_developer": _role(_DEVSTRAL_2, temperature=0.4),
        "cloud_engineer": _role(_DEEPSEEK_V3),
        "devops": _role(_DEVSTRAL_2, temperature=0.4),
        "qa_engineer": _role(_DEEPSEEK_V3),
    },
    Environment.TEST: {
        "manager": _role(_GEMINI_FLASH),
        "product_owner": _role(_GEMINI_FLASH),
        "architect": _role(_DEEPSEEK_R1, temperature=0.3),
        "backend_developer": _role(_MINIMAX_M2, temperature=0.4),
        "frontend_developer": _role(_MINIMAX_M2, temperature=0.4),
        "fullstack_developer": _role(_MINIMAX_M2, temperature=0.4),
        "cloud_engineer": _role(_DEEPSEEK_R1, temperature=0.3),
        "devops": _role(_DEVSTRAL_2, temperature=0.4),
        "qa_engineer": _role(_DEEPSEEK_R1, temperature=0.3),
    },
    Environment.PROD: {
        "manager": _role(_CLAUDE_SONNET, temperature=0.5),
        "product_owner": _role(_GPT52, temperature=0.5),
        "architect": _role(_CLAUDE_SONNET, temperature=0.3),
        "backend_developer": _role(_GPT53_CODEX, temperature=0.2),
        "frontend_developer": _role(_CLAUDE_SONNET, temperature=0.3),
        "fullstack_developer": _role(_GPT53_CODEX, temperature=0.2),
        "cloud_engineer": _role(_CLAUDE_SONNET, temperature=0.3),
        "devops": _role(_GPT53_CODEX, temperature=0.3),
        "qa_engineer": _role(_CLAUDE_SONNET, temperature=0.3),
    },
}


class OpenRouterSettings(BaseSettings):
    """OpenRouter and environment settings loaded from .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openrouter_api_key: str = Field(description="OpenRouter API key", alias="OPENROUTER_API_KEY")
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

    def get_models(self) -> Dict[str, RoleModelConfig]:
        """Return role → RoleModelConfig for the current environment."""
        return ENV_MODELS[self.ai_team_env]

    def get_model_for_role(self, role: str) -> RoleModelConfig:
        """Return RoleModelConfig for the given agent role. Normalizes devops_engineer → devops."""
        models = self.get_models()
        key = role.lower()
        if key == "devops_engineer":
            key = "devops"
        return models.get(key, models["manager"])
