"""Verify LRU cache in subgraph_runners returns same graph for same profile, different for different."""

from __future__ import annotations

import pytest
from ai_team.backends.langgraph_backend.graphs.subgraph_runners import (
    _cached_planning,
    reset_subgraph_cache,
)

from .stub_chat_model import FakeChatModelWithBindTools

MULTI_STUB = FakeChatModelWithBindTools(responses=["ok"] * 120)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    reset_subgraph_cache()
    yield
    reset_subgraph_cache()


def _no_tools(_role: str) -> list:
    return []


class TestSubgraphCache:
    def test_same_profile_returns_same_graph(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "ai_team.backends.langgraph_backend.graphs.planning.get_langchain_tools_for_role",
            _no_tools,
        )
        monkeypatch.setattr(
            "ai_team.backends.langgraph_backend.graphs.planning.create_chat_model_for_role",
            lambda *_a, **_kw: MULTI_STUB,
        )
        agents = frozenset({"manager", "product_owner", "architect"})
        overrides: tuple[tuple[str, str], ...] = ()

        g1 = _cached_planning(agents, overrides)
        g2 = _cached_planning(agents, overrides)
        assert g1 is g2

    def test_different_profile_returns_different_graph(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "ai_team.backends.langgraph_backend.graphs.planning.get_langchain_tools_for_role",
            _no_tools,
        )
        monkeypatch.setattr(
            "ai_team.backends.langgraph_backend.graphs.planning.create_chat_model_for_role",
            lambda *_a, **_kw: MULTI_STUB,
        )
        full = frozenset({"manager", "product_owner", "architect"})
        subset = frozenset({"architect"})
        overrides: tuple[tuple[str, str], ...] = ()

        g_full = _cached_planning(full, overrides)
        g_subset = _cached_planning(subset, overrides)
        assert g_full is not g_subset

    def test_reset_clears_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "ai_team.backends.langgraph_backend.graphs.planning.get_langchain_tools_for_role",
            _no_tools,
        )
        monkeypatch.setattr(
            "ai_team.backends.langgraph_backend.graphs.planning.create_chat_model_for_role",
            lambda *_a, **_kw: MULTI_STUB,
        )
        agents = frozenset({"manager", "product_owner", "architect"})
        overrides: tuple[tuple[str, str], ...] = ()

        g1 = _cached_planning(agents, overrides)
        reset_subgraph_cache()
        g2 = _cached_planning(agents, overrides)
        assert g1 is not g2
