"""Dedicated memory/embedder integration tests.

Run when AI_TEAM_USE_REAL_LLM=1 and AI_TEAM_TEST_MEMORY=1 (Crew memory test),
or AI_TEAM_TEST_MEMORY=1 (MemoryManager short-term ChromaDB test). Requires Ollama
and the embedding model (e.g. nomic-embed-text) for tests that use embeddings.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crewai import Agent, Crew, Task
from pydantic import ValidationError as PydanticValidationError

from ai_team.config.settings import MemorySettings, get_settings
from ai_team.memory import get_crew_embedder_config
from ai_team.memory.memory_config import MemoryManager


@pytest.mark.test_memory
class TestCrewMemoryWithEmbedder:
    """Crew with memory=True and Ollama embedder runs without OpenAI."""

    def test_minimal_crew_with_memory_and_embedder_runs(
        self,
        use_real_llm: bool,
        test_memory_enabled: bool,
    ) -> None:
        """Run a minimal Crew with memory=True and get_crew_embedder_config(); no exception."""
        if not (use_real_llm and test_memory_enabled):
            pytest.skip("Set AI_TEAM_USE_REAL_LLM=1 and AI_TEAM_TEST_MEMORY=1 to run")
        if not get_settings().validate_ollama_connection():
            pytest.skip("Ollama unreachable")

        from langchain_ollama import ChatOllama

        settings = get_settings()
        llm = ChatOllama(
            model=settings.ollama.default_model,
            base_url=settings.ollama.base_url,
            request_timeout=settings.ollama.request_timeout,
        )
        agent = Agent(
            role="Responder",
            goal="Answer in one word when asked.",
            backstory="You are a minimal test agent.",
            llm=llm,
        )
        task = Task(
            description="When asked what to say, reply with the word hello.",
            agent=agent,
            expected_output="The word hello.",
        )
        try:
            crew = Crew(
                agents=[agent],
                tasks=[task],
                memory=True,
                embedder=get_crew_embedder_config(),
                verbose=False,
            )
        except PydanticValidationError as e:
            if "embedder" in str(e).lower() or "nomic" in str(e).lower() or "not found" in str(e).lower():
                pytest.skip(
                    f"Embedder init failed (embedding model may be missing): {e!s}. "
                    "Run: ollama pull nomic-embed-text"
                )
            raise
        result = crew.kickoff(inputs={})
        assert result is not None


@pytest.mark.test_memory
class TestMemoryManagerShortTermChromaDB:
    """MemoryManager short-term (ChromaDB) store/retrieve round-trip with Ollama embeddings."""

    def test_short_term_store_and_retrieve_round_trip(
        self,
        test_memory_enabled: bool,
        tmp_path: Path,
    ) -> None:
        """Store a doc in short_term and retrieve by semantic query; requires Ollama + embedding model."""
        if not test_memory_enabled:
            pytest.skip("Set AI_TEAM_TEST_MEMORY=1 to run")
        if not get_settings().validate_ollama_connection():
            pytest.skip("Ollama unreachable (embedding model required)")

        chroma_path = str(tmp_path / "chroma")
        sqlite_path = str(tmp_path / "memory.db")
        settings = MemorySettings(
            chromadb_path=chroma_path,
            sqlite_path=sqlite_path,
            memory_enabled=True,
            embedding_model=get_settings().memory.embedding_model,
            ollama_base_url=get_settings().memory.ollama_base_url,
        )
        manager = MemoryManager()
        manager.initialize(settings)
        assert manager.is_initialized

        project_id = "memory-test-proj"
        doc_id = "doc1"
        text = "We use PostgreSQL for the user database and Redis for sessions."
        manager.store(
            key=doc_id,
            value=text,
            memory_type="short_term",
            project_id=project_id,
        )

        results = manager.retrieve(
            query="What database do we use for users?",
            memory_type="short_term",
            top_k=3,
            project_id=project_id,
        )
        assert len(results) >= 1
        assert any("PostgreSQL" in (r.get("document") or "") for r in results)
