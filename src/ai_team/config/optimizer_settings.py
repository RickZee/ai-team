"""Settings for the Karpathy AutoOptimizer loop."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OptimizerSettings(BaseSettings):
    """
    Configuration for the autonomous edit→run→measure→keep/revert loop.

    All fields are overridable via OPTIMIZER_* environment variables.
    """

    model_config = SettingsConfigDict(env_prefix="OPTIMIZER_", extra="ignore")

    max_experiments: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Hard cap on iterations per loop run.",
    )
    budget_usd: float = Field(
        default=10.0,
        gt=0,
        description="Total spend ceiling across all experiments in a single loop run.",
    )
    timeout_per_experiment: int = Field(
        default=300,
        ge=30,
        description="Seconds to allow each eval command before it is killed.",
    )
    default_backend: str = Field(
        default="claude-agent-sdk",
        description="Backend used by the optimizer agent to propose edits.",
    )
    default_team: str = Field(
        default="research-optimizer",
        description="Team profile for the optimizer agent.",
    )
    branch_prefix: str = Field(
        default="optimize/",
        description="Git branch prefix for experiment commits.",
    )
    min_improvement_pct: float = Field(
        default=0.5,
        ge=0.0,
        description=(
            "Minimum percentage improvement over the running best for a commit to be kept. "
            "Prevents marginal noise from accumulating."
        ),
    )
    max_budget_per_experiment_usd: float = Field(
        default=1.0,
        gt=0,
        description="Per-iteration spend cap passed to the backend as max_budget_usd.",
    )
    max_turns_per_experiment: int = Field(
        default=40,
        ge=5,
        description="max_turns passed to claude-agent-sdk per iteration.",
    )
