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


class OllamaSettings(BaseSettings):
    """
    Ollama API and per-role model configuration.

    Supports base URL, timeouts, retries, and optional model assignment
    per agent role with a default model fallback.
    """

    model_config = SettingsConfigDict(env_prefix="OLLAMA_", extra="ignore")

    base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL",
    )
    default_model: str = Field(
        default="qwen3:14b",
        description="Default model used when a role has no specific assignment",
    )
    manager_model: str = Field(default="qwen3:14b", description="Model for Manager agent")
    product_owner_model: str = Field(default="qwen3:14b", description="Model for Product Owner")
    architect_model: str = Field(default="deepseek-r1:14b", description="Model for Architect")
    backend_dev_model: str = Field(default="deepseek-coder-v2:16b", description="Model for Backend Developer")
    frontend_dev_model: str = Field(default="qwen2.5-coder:14b", description="Model for Frontend Developer")
    fullstack_dev_model: str = Field(default="deepseek-coder-v2:16b", description="Model for Fullstack Developer")
    devops_model: str = Field(default="qwen2.5-coder:14b", description="Model for DevOps")
    cloud_model: str = Field(default="qwen2.5-coder:14b", description="Model for Cloud Engineer")
    qa_model: str = Field(default="qwen3:14b", description="Model for QA Agent")

    request_timeout: int = Field(default=300, ge=1, le=3600, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retries for Ollama requests")

    def get_model_for_role(self, role: str) -> str:
        """Return the configured model for the given agent role."""
        role_map = {
            "manager": self.manager_model,
            "product_owner": self.product_owner_model,
            "architect": self.architect_model,
            "backend_dev": self.backend_dev_model,
            "frontend_dev": self.frontend_dev_model,
            "fullstack_dev": self.fullstack_dev_model,
            "devops": self.devops_model,
            "cloud": self.cloud_model,
            "qa": self.qa_model,
        }
        return role_map.get(role.lower(), self.default_model)

    def check_health(self) -> bool:
        """Validate that the Ollama server is reachable. Returns True if healthy."""
        try:
            import httpx
            response = httpx.get(f"{self.base_url.rstrip('/')}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False


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
    embedding model, collection name, and master enable flag.
    """

    model_config = SettingsConfigDict(env_prefix="MEMORY_", extra="ignore")

    chromadb_path: str = Field(default="./data/chroma", description="ChromaDB persistence directory")
    sqlite_path: str = Field(default="./data/memory.db", description="SQLite database path for long-term memory")
    embedding_model: str = Field(default="nomic-embed-text", description="Model used for embeddings")
    collection_name: str = Field(default="ai_team_memory", description="ChromaDB collection name")
    memory_enabled: bool = Field(default=True, description="Master switch to enable/disable memory")


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


class ProjectSettings(BaseSettings):
    """Project execution settings: output/workspace dirs, iterations, and timeout."""

    model_config = SettingsConfigDict(env_prefix="PROJECT_", extra="ignore")

    output_dir: str = Field(default="./output", description="Default output directory for artifacts")
    workspace_dir: str = Field(default="./workspace", description="Workspace root for file operations")
    max_iterations: int = Field(default=10, ge=1, le=100, description="Max iterations per run")
    default_timeout: int = Field(default=3600, ge=1, description="Default timeout in seconds for runs")


class Settings(BaseSettings):
    """
    Root settings class. Loads from .env by default; supports creation from YAML.

    Nested models: ollama, guardrails, memory, logging, project.
    Use validate_ollama_connection() to check Ollama on startup.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    ollama: OllamaSettings = Field(default_factory=OllamaSettings, description="Ollama API and model config")
    guardrails: GuardrailSettings = Field(default_factory=GuardrailSettings, description="Guardrail config")
    memory: MemorySettings = Field(default_factory=MemorySettings, description="Memory backend config")
    logging: LoggingSettings = Field(default_factory=LoggingSettings, description="Logging config")
    project: ProjectSettings = Field(default_factory=ProjectSettings, description="Project execution config")

    def validate_ollama_connection(self) -> bool:
        """Validate that the Ollama server is reachable. Returns True if healthy."""
        return self.ollama.check_health()

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Settings":
        """
        Create Settings from a YAML file. Top-level keys should match
        nested model names (ollama, guardrails, memory, logging, project).
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
            ("ollama", OllamaSettings),
            ("guardrails", GuardrailSettings),
            ("memory", MemorySettings),
            ("logging", LoggingSettings),
            ("project", ProjectSettings),
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
