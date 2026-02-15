"""
AI Team Settings Configuration

This module provides centralized configuration management using Pydantic settings.
All configuration is loaded from environment variables with sensible defaults.
"""

from pathlib import Path
from typing import Dict, List, Optional
from enum import Enum

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelSize(str, Enum):
    """Available model size configurations."""
    SMALL = "small"      # 7-8B models, ~8GB VRAM
    MEDIUM = "medium"    # 14-16B models, ~12GB VRAM
    LARGE = "large"      # 32B models, ~24GB VRAM
    XLARGE = "xlarge"    # 70B+ models, ~48GB+ VRAM


class OllamaModelConfig(BaseSettings):
    """Configuration for Ollama model selection per role."""
    
    model_config = SettingsConfigDict(env_prefix="OLLAMA_")
    
    # Model assignments by role - customize based on your VRAM
    manager_model: str = Field(default="qwen3:14b", description="Model for Manager agent")
    product_owner_model: str = Field(default="qwen3:14b", description="Model for Product Owner")
    architect_model: str = Field(default="deepseek-r1:14b", description="Model for Architect")
    cloud_engineer_model: str = Field(default="qwen2.5-coder:14b", description="Model for Cloud Engineer")
    devops_model: str = Field(default="qwen2.5-coder:14b", description="Model for DevOps Engineer")
    backend_developer_model: str = Field(default="deepseek-coder-v2:16b", description="Model for Backend Dev")
    frontend_developer_model: str = Field(default="qwen2.5-coder:14b", description="Model for Frontend Dev")
    qa_engineer_model: str = Field(default="qwen3:14b", description="Model for QA Engineer")
    
    # Ollama connection settings
    base_url: str = Field(default="http://localhost:11434", description="Ollama API base URL")
    timeout: int = Field(default=300, description="Request timeout in seconds")
    
    # Model parameters
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    num_ctx: int = Field(default=8192, description="Context window size")
    
    def get_model_for_role(self, role: str) -> str:
        """Get the configured model for a specific agent role."""
        role_map = {
            "manager": self.manager_model,
            "product_owner": self.product_owner_model,
            "architect": self.architect_model,
            "cloud_engineer": self.cloud_engineer_model,
            "devops": self.devops_model,
            "backend_developer": self.backend_developer_model,
            "frontend_developer": self.frontend_developer_model,
            "qa_engineer": self.qa_engineer_model,
        }
        return role_map.get(role.lower(), self.manager_model)


class GuardrailConfig(BaseSettings):
    """Configuration for guardrail behavior."""
    
    model_config = SettingsConfigDict(env_prefix="GUARDRAIL_")
    
    # Retry settings
    max_retries: int = Field(default=3, ge=1, le=10, description="Max retry attempts on guardrail failure")
    retry_delay: float = Field(default=1.0, ge=0.0, description="Delay between retries in seconds")
    
    # Behavioral guardrails
    enforce_role_adherence: bool = Field(default=True)
    enforce_scope_control: bool = Field(default=True)
    require_reasoning: bool = Field(default=True)
    max_scope_expansion: float = Field(default=0.3, ge=0.0, le=1.0)
    
    # Security guardrails
    enable_code_safety_check: bool = Field(default=True)
    enable_pii_redaction: bool = Field(default=True)
    enable_secret_detection: bool = Field(default=True)
    enable_prompt_injection_detection: bool = Field(default=True)
    
    # Quality guardrails
    min_output_words: int = Field(default=20)
    max_output_words: int = Field(default=10000)
    require_syntax_validation: bool = Field(default=True)
    require_complete_implementation: bool = Field(default=True)
    min_code_quality_score: float = Field(default=7.0, ge=0.0, le=10.0)
    
    # Allowed directories for file operations
    allowed_directories: List[str] = Field(
        default=["/workspace", "/tmp/ai-team", "./output"],
        description="Directories where file operations are allowed"
    )


class MemoryConfig(BaseSettings):
    """Configuration for memory systems."""
    
    model_config = SettingsConfigDict(env_prefix="MEMORY_")
    
    # Short-term memory (ChromaDB)
    enable_short_term: bool = Field(default=True)
    chroma_persist_dir: str = Field(default="./data/chroma")
    
    # Long-term memory (SQLite)
    enable_long_term: bool = Field(default=True)
    sqlite_path: str = Field(default="./data/memory.db")
    
    # Entity memory
    enable_entity_memory: bool = Field(default=True)
    
    # Memory limits
    max_short_term_items: int = Field(default=100)
    max_context_length: int = Field(default=4000)


class LoggingConfig(BaseSettings):
    """Configuration for logging and observability."""
    
    model_config = SettingsConfigDict(env_prefix="LOG_")
    
    level: str = Field(default="INFO")
    format: str = Field(default="json")  # json or console
    log_file: Optional[str] = Field(default="./logs/ai-team.log")
    
    # Metrics collection
    enable_metrics: bool = Field(default=True)
    metrics_file: str = Field(default="./logs/metrics.json")
    
    # Event callbacks
    enable_webhooks: bool = Field(default=False)
    webhook_url: Optional[str] = Field(default=None)


class Settings(BaseSettings):
    """Main settings class aggregating all configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Project settings
    project_name: str = Field(default="ai-team")
    debug: bool = Field(default=False)
    workspace_dir: Path = Field(default=Path("./workspace"))
    output_dir: Path = Field(default=Path("./output"))
    
    # Sub-configurations
    ollama: OllamaModelConfig = Field(default_factory=OllamaModelConfig)
    guardrails: GuardrailConfig = Field(default_factory=GuardrailConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    # CrewAI settings
    crew_verbose: bool = Field(default=True)
    crew_memory: bool = Field(default=True)
    crew_max_rpm: int = Field(default=10, description="Max requests per minute")
    
    @field_validator("workspace_dir", "output_dir", mode="before")
    @classmethod
    def create_directories(cls, v):
        """Ensure directories exist."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def validate_ollama_connection(self) -> bool:
        """Validate that Ollama is accessible."""
        import httpx
        try:
            response = httpx.get(f"{self.ollama.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_available_models(self) -> List[str]:
        """Get list of available Ollama models."""
        import httpx
        try:
            response = httpx.get(f"{self.ollama.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Force reload of settings from environment."""
    global _settings
    _settings = Settings()
    return _settings
