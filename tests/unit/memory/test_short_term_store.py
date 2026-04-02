"""Unit tests for ``ShortTermStore`` with mocked Chroma collection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ai_team.memory.memory_config import ShortTermStore


@pytest.fixture
def store(tmp_path: Path) -> ShortTermStore:
    return ShortTermStore(
        chromadb_path=str(tmp_path / "chroma"),
        embedding_model="openai/text-embedding-3-small",
        collection_name="test_coll",
    )


class TestShortTermStoreMocked:
    def test_add_calls_upsert(self, store: ShortTermStore) -> None:
        coll = MagicMock()
        with patch.object(store, "get_collection", return_value=coll):
            store.add("proj-1", "doc1", "hello world", metadata={"k": "v"})
        coll.upsert.assert_called_once()
        call_kw = coll.upsert.call_args.kwargs
        assert call_kw["ids"] == ["doc1"]
        assert "hello world" in call_kw["documents"][0]

    def test_search_returns_tuples(self, store: ShortTermStore) -> None:
        coll = MagicMock()
        coll.query.return_value = {
            "ids": [["id1"]],
            "documents": [["text"]],
            "distances": [[0.5]],
            "metadatas": [[{"project_id": "proj-1"}]],
        }
        with patch.object(store, "get_collection", return_value=coll):
            hits = store.search("proj-1", "q", top_k=3)
        assert len(hits) == 1
        assert hits[0][0] == "id1"
        assert hits[0][1] == "text"

    def test_add_skips_empty_document(self, store: ShortTermStore) -> None:
        coll = MagicMock()
        with patch.object(store, "get_collection", return_value=coll):
            store.add("p", "id", "", metadata=None)
        coll.upsert.assert_not_called()
