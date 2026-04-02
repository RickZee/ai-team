"""Tests for ``tools.rag_search.search_knowledge``."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ai_team.tools.rag_search import search_knowledge


def test_search_knowledge_disabled_returns_message() -> None:
    mock_cfg = MagicMock()
    mock_cfg.enabled = False
    with patch("ai_team.tools.rag_search.get_rag_config", return_value=mock_cfg):
        out = search_knowledge.invoke({"query": "testing"})
    assert "disabled" in out.lower()


def test_search_knowledge_empty_query() -> None:
    mock_cfg = MagicMock()
    mock_cfg.enabled = True
    with patch("ai_team.tools.rag_search.get_rag_config", return_value=mock_cfg):
        out = search_knowledge.invoke({"query": "  "})
    assert "non-empty" in out.lower()


def test_search_knowledge_with_mock_pipeline() -> None:
    mock_cfg = MagicMock()
    mock_cfg.enabled = True
    mock_cfg.top_k = 3
    pipe = MagicMock()
    pipe.retrieve.return_value = [{"text": "snippet"}]
    pipe.format_context.return_value = "CTX"
    with (
        patch("ai_team.tools.rag_search.get_rag_config", return_value=mock_cfg),
        patch("ai_team.tools.rag_search.get_rag_pipeline", return_value=pipe),
    ):
        out = search_knowledge.invoke({"query": "pytest"})
    assert out == "CTX"
