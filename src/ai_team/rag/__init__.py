"""Shared RAG layer: vector store, ingestion, and retrieval (backend-agnostic)."""

from ai_team.rag.pipeline import RAGPipeline, get_rag_pipeline

__all__ = ["RAGPipeline", "get_rag_pipeline"]
