"""
AI Team Settings Configuration

This module provides centralized configuration management using Pydantic settings.
Configuration is loaded from .env by default; alternative YAML loading is supported.
"""

from pathlib import Path
from typing import Any, List, Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GuardrailSettings(BaseSettings):
    """
    Guardrail configuration: retries per type, thresholds, pattern lists,
    and enable/disable flags per category.
    """

    model_config = SettingsConfigDict(env_prefix="GUARDRAIL_", extra="ignore")

    # Max retries per guardrail type
    behavioral_max_retries: int = Field(default=3, ge=0, le=10, description="Max retries for behavioral guardrails")
    security_max_retries: int = Field(default=3, ge=0, le=10, description="Max retries for security guardrails")
    quality_max_retries: int = Field(default=3, ge=0, le=10, description="Max retries for quality guardrails")

    # Thresholds
    code_quality_min_score: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum code quality score (0–1)")
    test_coverage_min: float = Field(default=0.6, ge=0.0, le=1.0, description="Minimum test coverage ratio (0–1)")
    max_file_size_kb: int = Field(default=500, ge=1, description="Max allowed file size in KB")

    # Pattern lists (regex or substring patterns)
    dangerous_patterns: List[str] = Field(
        default_factory=lambda: ["eval(", "exec(", "__import__", "os.system", "subprocess.call"],
        description="Patterns that trigger security/behavioral guardrails",
    )
    pii_patterns: List[str] = Field(
        default_factory=lambda: [r"\b\d{3}-\d{2}-\d{4}\b", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"],
        description="Regex patterns for PII detection",
    )

    # Enable/disable per category
    behavioral_enabled: bool = Field(default=True, description="Enable behavioral guardrails")
    security_enabled: bool = Field(default=True, description="Enable security guardrails")
    quality_enabled: bool = Field(default=True, description="Enable quality guardrails")


class MemorySettings(BaseSettings):
    """
    Memory backend configuration: ChromaDB path, SQLite path,
    embedding model, collection name, retention, and master enable flag.
    Short-term (ChromaDB): collection per project; long-term (SQLite): cross-project.
    """

    model_config = SettingsConfigDict(env_prefix="MEMORY_", extra="ignore")

    chromadb_path: str = Field(default="./data/chroma", description="ChromaDB persistence directory")
    sqlite_path: str = Field(default="./data/memory.db", description="SQLite database path for long-term memory")
    embedding_model: str = Field(
        default="openai/text-embedding-3-small",
        description="Embedding model (OpenRouter: provider/model, e.g. openai/text-embedding-3-small)",
    )
    collection_name: str = Field(default="ai_team_memory", description="ChromaDB collection name prefix (project_id appended)")
    memory_enabled: bool = Field(default=True, description="Master switch to enable/disable memory")
    max_results: int = Field(default=10, ge=1, le=100, description="Max results for RAG/semantic retrieval (top_k)")
    retention_days: int = Field(default=90, ge=1, le=3650, description="Days to retain long-term memory entries before cleanup")
    share_between_crews: bool = Field(
        default=True,
        description="When True, short-term memory is shared across crews within the same project",
    )
    embedding_api_base: str = Field(
        default="https://openrouter.ai/api/v1",
        description="API base URL for embeddings (OpenRouter)",
    )


class LoggingSettings(BaseSettings):
    """Logging configuration: level, format (json/console), and log file path."""

    model_config = SettingsConfigDict(env_prefix="LOG_", extra="ignore")

    log_level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)")
    log_format: str = Field(default="json", description="Format: 'json' or 'console'")
    log_file: Optional[str] = Field(default="./logs/ai-team.log", description="Optional log file path")

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        allowed = ("json", "console")
        if v.lower() not in allowed:
            raise ValueError(f"log_format must be one of {allowed}")
        return v.lower()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        u = v.upper()
        if u not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return u


class CallbackSettings(BaseSettings):
    """Callback system: optional webhook for phase transitions."""

    model_config = SettingsConfigDict(env_prefix="CALLBACK_", extra="ignore")

    webhook_url: Optional[str] = Field(default=None, description="URL for POST on phase transitions (crew start/complete)")
    webhook_enabled: bool = Field(default=False, description="Enable webhook notifications when webhook_url is set")


class HumanFeedbackSettings(BaseSettings):
    """Human-in-the-loop feedback: timeout and default when no response."""

    model_config = SettingsConfigDict(env_prefix="FEEDBACK_", extra="ignore")

    timeout_seconds: int = Field(default=300, ge=0, le=86400, description="Wait for user input (0 = no timeout)")
    default_response: str = Field(default="", description="Default response when timeout or no input")


class ProjectSettings(BaseSettings):
    """Project execution settings: output/workspace dirs, iterations, and timeout."""

    model_config = SettingsConfigDict(env_prefix="PROJECT_", extra="ignore")

    output_dir: str = Field(default="./output", description="Default output directory for artifacts")
    workspace_dir: str = Field(default="./workspace", description="Workspace root for file operations")
    max_iterations: int = Field(default=10, ge=1, le=100, description="Max iterations per run")
    default_timeout: int = Field(default=3600, ge=1, description="Default timeout in seconds for runs")
    crew_verbose: bool = Field(default=True, description="Verbose crew execution (e.g. for development)")
    crew_max_rpm: Optional[int] = Field(default=None, ge=1, description="Max requests per minute for crew")
    planning_sequential: bool = Field(
        default=False,
        description="Use sequential process and disable crew planning for planning crew.",
    )


class Settings(BaseSettings):
    """
    Root settings class. Loads from .env by default; supports creation from YAML.

    Nested models: guardrails, memory, logging, project, callback, human_feedback.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    guardrails: GuardrailSettings = Field(default_factory=GuardrailSettings, description="Guardrail config")
    memory: MemorySettings = Field(default_factory=MemorySettings, description="Memory backend config")
    logging: LoggingSettings = Field(default_factory=LoggingSettings, description="Logging config")
    project: ProjectSettings = Field(default_factory=ProjectSettings, description="Project execution config")
    callback: CallbackSettings = Field(default_factory=CallbackSettings, description="Callback/webhook config")
    human_feedback: HumanFeedbackSettings = Field(
        default_factory=HumanFeedbackSettings, description="Human-in-the-loop feedback config"
    )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Settings":
        """
        Create Settings from a YAML file. Top-level keys should match
        nested model names (guardrails, memory, logging, project, etc.).
        Environment variables still override when present.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        # Build kwargs for nested models; leave missing as default
        kwargs: dict[str, Any] = {}
        for name, model_class in [
            ("guardrails", GuardrailSettings),
            ("memory", MemorySettings),
            ("logging", LoggingSettings),
            ("project", ProjectSettings),
            ("callback", CallbackSettings),
            ("human_feedback", HumanFeedbackSettings),
        ]:
            if name in data and isinstance(data[name], dict):
                kwargs[name] = model_class.model_validate(data[name])
        return cls(**kwargs)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance (loads from .env)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Force reload of settings from environment."""
    global _settings
    _settings = Settings()
    return _settings
