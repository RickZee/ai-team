"""Vector store factory (ChromaDB default; Lance / pgvector reserved for future wiring)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
from ai_team.rag.config import RAGConfig, VectorStoreKind

logger = structlog.get_logger(__name__)


def create_chroma_store(
    config: RAGConfig,
    embedding_function: Any,
) -> Any:
    """Return a ChromaDB collection with the given embedding function."""
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    path = Path(config.persist_directory)
    path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(path),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    collection = client.get_or_create_collection(
        name=config.collection_name,
        embedding_function=embedding_function,
        metadata={"description": "ai-team RAG knowledge"},
    )
    logger.info(
        "rag_chroma_collection_ready",
        path=str(path),
        collection=config.collection_name,
    )
    return collection


def create_vector_store(
    kind: VectorStoreKind,
    config: RAGConfig,
    embedding_function: Any,
) -> Any:
    """
    Factory for vector backends.

    * ``chromadb``: persistent client (default).
    * ``lance`` / ``pgvector``: not yet wired; raise with guidance.
    """
    if kind == "chromadb":
        return create_chroma_store(config, embedding_function)
    if kind == "lance":
        msg = "RAG vector_store=lance is not wired; use chromadb or add lancedb integration."
        raise NotImplementedError(msg)
    if kind == "pgvector":
        msg = "RAG vector_store=pgvector is not wired; use chromadb for now."
        raise NotImplementedError(msg)
    msg = f"Unknown vector_store {kind!r}"
    raise ValueError(msg)
