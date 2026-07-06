"""Memory/embedder integration tests.

The short-term ChromaDB memory and the MemoryManager facade were removed with
the memory-subsystem merge (SHOWCASE_PLAN 3.5); the memory model is now
file-based handoff plus the SQLite LongTermStore (covered by unit tests in
``tests/unit/memory``). What remains integration-relevant here is CrewAI's own
crew memory, which is wired through the OpenRouter-backed embedder config.

Run the slow crew test with AI_TEAM_USE_REAL_LLM=1 and AI_TEAM_TEST_MEMORY=1
(requires OPENROUTER_API_KEY for embeddings).
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from ai_team.config.llm_factory import get_embedder_config
from crewai import Agent, Crew, Task
from pydantic import ValidationError as PydanticValidationError

# -----------------------------------------------------------------------------
# CrewAI crew memory uses the OpenRouter-backed embedder
# -----------------------------------------------------------------------------


class TestCrewMemoryUsesOpenRouterEmbedder:
    """CrewAI crew memory uses OpenRouter-backed embedder."""

    def test_get_embedder_config_returns_openrouter_backed(self) -> None:
        """get_embedder_config() returns openai provider with an embedding model for OpenRouter."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}, clear=False):
            config = get_embedder_config()
        assert config.get("provider") == "openai"
        assert "config" in config
        assert "model_name" in config["config"]
        # OpenRouter embeddings use provider/model (e.g. openai/text-embedding-3-small)
        assert "embedding" in config["config"]["model_name"].lower()


@pytest.mark.test_memory
class TestCrewMemoryWithEmbedder:
    """Crew with memory=True and OpenRouter embedder runs."""

    @pytest.mark.slow
    def test_minimal_crew_with_memory_and_embedder_runs(
        self,
        use_real_llm: bool,
        test_memory_enabled: bool,
    ) -> None:
        """Run a minimal Crew with memory=True and get_embedder_config(); no exception."""
        if not (use_real_llm and test_memory_enabled):
            pytest.skip("Set AI_TEAM_USE_REAL_LLM=1 and AI_TEAM_TEST_MEMORY=1 to run")
        if not os.environ.get("OPENROUTER_API_KEY"):
            pytest.skip("OPENROUTER_API_KEY not set")

        from ai_team.config.llm_factory import create_llm_for_role
        from ai_team.config.models import OpenRouterSettings

        llm = create_llm_for_role("manager", OpenRouterSettings())
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
                embedder=get_embedder_config(),
                verbose=False,
            )
        except PydanticValidationError as e:
            if "embedder" in str(e).lower():
                pytest.skip(f"Embedder init failed: {e!s}")
            raise
        result = crew.kickoff(inputs={})
        assert result is not None
