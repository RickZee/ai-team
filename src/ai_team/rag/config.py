"""Pydantic settings for RAG (env prefix ``RAG_``)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

VectorStoreKind = Literal["chromadb", "lance", "pgvector"]


class RAGConfig(BaseSettings):
    """RAG pipeline and vector store configuration."""

    model_config = SettingsConfigDict(env_prefix="RAG_", extra="ignore")

    enabled: bool = Field(
        default=False, description="Enable RAG augmentation and search_knowledge tool"
    )
    vector_store: VectorStoreKind = Field(
        default="chromadb",
        description="Vector backend: chromadb (default), lance (optional), pgvector (future)",
    )
    persist_directory: str = Field(
        default="./data/rag_chroma",
        description="ChromaDB persistence directory",
    )
    collection_name: str = Field(default="ai_team_knowledge", description="Default collection name")
    chunk_size: int = Field(
        default=1200, ge=200, le=8000, description="Target chunk size in characters"
    )
    chunk_overlap: int = Field(default=150, ge=0, le=500, description="Overlap between chunks")
    top_k: int = Field(default=5, ge=1, le=50, description="Default retrieval top-k")
    embedding_model: str = Field(
        default="openai/text-embedding-3-small",
        description="Embedding model id (OpenRouter format)",
    )
    embedding_api_base: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Embeddings API base URL",
    )


_rag_config: RAGConfig | None = None


def get_rag_config() -> RAGConfig:
    """Singleton RAG settings."""
    global _rag_config
    if _rag_config is None:
        _rag_config = RAGConfig()
    return _rag_config


def reload_rag_config() -> RAGConfig:
    """Force reload from environment."""
    global _rag_config
    _rag_config = RAGConfig()
    return _rag_config
