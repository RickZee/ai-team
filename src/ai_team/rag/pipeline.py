"""RAG pipeline: ingest documents, retrieve, optional rerank."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
from ai_team.memory.memory_config import OpenRouterChromaEmbeddingFunction
from ai_team.rag.config import RAGConfig, get_rag_config
from ai_team.rag.ingestion import TextChunk, chunk_file
from ai_team.rag.vector_store import create_vector_store

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RetrievalHit:
    """One retrieved chunk."""

    text: str
    score: float | None
    metadata: dict[str, Any]


def _rerank_by_overlap(query: str, hits: list[RetrievalHit]) -> list[RetrievalHit]:
    """Lightweight rerank: boost chunks sharing tokens with the query."""
    q_tokens = set(query.lower().split())
    if not q_tokens:
        return hits

    def score(h: RetrievalHit) -> float:
        base = h.score or 0.0
        t = set(h.text.lower().split())
        overlap = len(q_tokens & t) / max(len(q_tokens), 1)
        return base + overlap * 0.01

    return sorted(hits, key=score, reverse=True)


class RAGPipeline:
    """
    Backend-agnostic RAG: ChromaDB collection + OpenRouter embeddings.

    Call :meth:`ingest_directory` to load markdown under ``src/ai_team/knowledge/``,
    then :meth:`retrieve` for semantic search.
    """

    def __init__(self, config: RAGConfig | None = None) -> None:
        self._config = config or get_rag_config()
        self._ef = OpenRouterChromaEmbeddingFunction(
            model=self._config.embedding_model,
            base_url=self._config.embedding_api_base,
        )
        self._collection: Any = None

    def _ensure_collection(self) -> Any:
        if self._collection is None:
            self._collection = create_vector_store(
                self._config.vector_store,
                self._config,
                self._ef,
            )
        return self._collection

    def ingest_chunks(self, chunks: list[TextChunk]) -> int:
        """Add text chunks to the vector store. Returns number of rows added."""
        col = self._ensure_collection()
        ids: list[str] = []
        texts: list[str] = []
        metas: list[dict[str, Any]] = []
        for i, ch in enumerate(chunks):
            uid = f"{ch.source_id}::{i}"
            ids.append(uid)
            texts.append(ch.text)
            metas.append(
                {
                    "source_id": ch.source_id,
                    "section": ch.section or "",
                }
            )
        if not ids:
            return 0
        col.add(ids=ids, documents=texts, metadatas=metas)
        logger.info("rag_ingest_chunks", count=len(ids))
        return len(ids)

    def ingest_directory(
        self,
        root: Path,
        *,
        glob_pattern: str = "**/*.md",
    ) -> int:
        """Load all matching files under ``root`` and ingest."""
        total = 0
        root = root.resolve()
        if not root.is_dir():
            logger.warning("rag_ingest_dir_missing", path=str(root))
            return 0
        for path in sorted(root.glob(glob_pattern)):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as e:
                logger.warning(
                    "rag_ingest_file_read_failed", path=str(path), error=str(e)
                )
                continue
            rel = str(path.relative_to(root))
            chunks = chunk_file(rel, text, self._config.chunk_size)
            total += self.ingest_chunks(chunks)
        logger.info("rag_ingest_directory_done", root=str(root), chunks=total)
        return total

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievalHit]:
        """Semantic search; optional token-overlap rerank."""
        k = top_k if top_k is not None else self._config.top_k
        col = self._ensure_collection()
        if not query.strip():
            return []
        raw = col.query(query_texts=[query], n_results=k)
        docs = raw.get("documents") or [[]]
        dists = raw.get("distances") or [[]]
        metas = raw.get("metadatas") or [[]]
        row_docs = docs[0] if docs else []
        row_dist = dists[0] if dists else []
        row_meta = metas[0] if metas else []
        hits: list[RetrievalHit] = []
        for i, doc in enumerate(row_docs):
            score = None
            if i < len(row_dist) and row_dist[i] is not None:
                try:
                    score = float(row_dist[i])
                except (TypeError, ValueError):
                    score = None
            meta = row_meta[i] if i < len(row_meta) else {}
            hits.append(
                RetrievalHit(
                    text=doc,
                    score=score,
                    metadata=dict(meta) if isinstance(meta, dict) else {},
                )
            )
        return _rerank_by_overlap(query, hits)

    def format_context(self, hits: list[RetrievalHit]) -> str:
        """Format hits for injection into prompts."""
        parts: list[str] = []
        for i, h in enumerate(hits, start=1):
            src = h.metadata.get("source_id", "unknown")
            parts.append(f"[{i}] ({src})\n{h.text.strip()}")
        return "\n\n---\n\n".join(parts)

    def reset_collection(self) -> None:
        """Delete and recreate the Chroma collection (for re-ingestion)."""
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        path = Path(self._config.persist_directory)
        path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(
            path=str(path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        try:
            client.delete_collection(self._config.collection_name)
        except Exception:
            logger.debug(
                "rag_collection_delete_skipped", name=self._config.collection_name
            )
        self._collection = None
        _ = self._ensure_collection()


_pipeline: RAGPipeline | None = None


def get_rag_pipeline(config: RAGConfig | None = None) -> RAGPipeline:
    """Singleton pipeline (optional config override for tests)."""
    global _pipeline
    if _pipeline is None or config is not None:
        _pipeline = RAGPipeline(config=config)
    return _pipeline


def reset_rag_pipeline_for_tests() -> None:
    """Clear singleton (tests only)."""
    global _pipeline
    _pipeline = None
