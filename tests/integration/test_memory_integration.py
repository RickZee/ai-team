"""Dedicated memory/embedder integration tests.

Run when AI_TEAM_USE_REAL_LLM=1 and AI_TEAM_TEST_MEMORY=1 (Crew memory test),
or AI_TEAM_TEST_MEMORY=1 (MemoryManager short-term ChromaDB test). Requires Ollama
and the embedding model (e.g. nomic-embed-text) for tests that use embeddings.

Covers: MemoryManager before_task/after_task wiring, cross-session retrieval,
CrewAI crew memory with local embedder (no OpenAI). Uses temporary ChromaDB/SQLite
for test isolation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
from crewai import Agent, Crew, Task
from pydantic import ValidationError as PydanticValidationError

from ai_team.config.settings import MemorySettings, get_settings
from ai_team.memory import get_crew_embedder_config
from ai_team.memory.memory_config import MemoryManager


# -----------------------------------------------------------------------------
# MemoryManager wired into before_task / after_task hooks
# -----------------------------------------------------------------------------


class TestMemoryManagerBeforeAfterTaskHooks:
    """MemoryManager wired into before_task stores context; after_task stores output."""

    def test_before_task_hook_stores_task_context(
        self,
        tmp_path: Path,
    ) -> None:
        """When before_task callback is invoked with (task_id, context), MemoryManager stores it."""
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

        project_id = "hook-test-proj"
        stored_context: Dict[str, Any] = {}

        def before_task(task_id: str, context: Dict[str, Any]) -> None:
            stored_context["task_id"] = task_id
            stored_context["context"] = context
            # Persist via MemoryManager (short_term keyed by task_id)
            text = str(context) if isinstance(context, str) else str(context)
            manager.store(
                key=f"task_ctx_{task_id}",
                value=text,
                memory_type="short_term",
                project_id=project_id,
            )

        before_task("requirements_gathering", {"project_description": "Build a CLI tool."})
        assert stored_context["task_id"] == "requirements_gathering"
        assert "project_description" in str(stored_context["context"])

        # Retrieve by query (embedding search) - requires Ollama for embeddings
        if get_settings().validate_ollama_connection():
            results = manager.retrieve(
                query="project description",
                memory_type="short_term",
                top_k=3,
                project_id=project_id,
            )
            assert len(results) >= 1

    def test_after_task_hook_stores_task_output(
        self,
        tmp_path: Path,
    ) -> None:
        """When after_task callback is invoked with (task_id, output), MemoryManager can store it."""
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

        project_id = "after-task-proj"
        stored_output: Dict[str, Any] = {}

        def after_task(task_id: str, output: Any) -> None:
            stored_output["task_id"] = task_id
            stored_output["output"] = output
            text = str(output) if not isinstance(output, str) else output
            manager.store(
                key=f"task_out_{task_id}",
                value=text[:5000],
                memory_type="short_term",
                project_id=project_id,
            )

        after_task("architecture_design", '{"system_overview": "REST API"}')
        assert stored_output["task_id"] == "architecture_design"
        assert "system_overview" in str(stored_output["output"])


class TestMemoryCrossSessionRetrieval:
    """Cross-session: simulate second run, verify memory available."""

    @pytest.mark.slow
    def test_cross_session_retrieval_uses_same_storage(
        self,
        test_memory_enabled: bool,
        tmp_path: Path,
    ) -> None:
        """Store in one session; new manager instance with same path can retrieve (long_term or short_term)."""
        if not test_memory_enabled:
            pytest.skip("Set AI_TEAM_TEST_MEMORY=1 to run")
        if not get_settings().validate_ollama_connection():
            pytest.skip("Ollama unreachable (embedding required for short_term)")

        chroma_path = str(tmp_path / "chroma")
        sqlite_path = str(tmp_path / "memory.db")
        project_id = "cross-session-proj"
        settings = MemorySettings(
            chromadb_path=chroma_path,
            sqlite_path=sqlite_path,
            memory_enabled=True,
            embedding_model=get_settings().memory.embedding_model,
            ollama_base_url=get_settings().memory.ollama_base_url,
        )

        # Session 1: create manager, store
        manager1 = MemoryManager()
        manager1.initialize(settings)
        manager1.store(
            key="session1_doc",
            value="The API uses JWT for authentication.",
            memory_type="short_term",
            project_id=project_id,
        )

        # Session 2: new manager, same path, initialize, retrieve
        manager2 = MemoryManager()
        manager2.initialize(settings)
        results = manager2.retrieve(
            query="authentication",
            memory_type="short_term",
            top_k=3,
            project_id=project_id,
        )
        assert len(results) >= 1
        assert any("JWT" in (r.get("document") or "") for r in results)


class TestCrewMemoryUsesLocalEmbedder:
    """CrewAI crew memory uses local embedder (no network calls to OpenAI)."""

    def test_get_crew_embedder_config_returns_ollama(self) -> None:
        """get_crew_embedder_config() returns Ollama provider, not OpenAI."""
        config = get_crew_embedder_config()
        assert config.get("provider") == "ollama"
        assert "config" in config
        assert "model_name" in config["config"] or "url" in config["config"]
        # Explicitly no OpenAI
        assert "openai" not in str(config).lower() or config.get("provider") != "openai"


@pytest.mark.test_memory
class TestCrewMemoryWithEmbedder:
    """Crew with memory=True and Ollama embedder runs without OpenAI."""

    @pytest.mark.slow
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

    @pytest.mark.slow
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
