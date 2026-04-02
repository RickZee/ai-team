"""Additional ``MemoryManager`` unit tests (dispatch, cleanup, export, retention)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from ai_team.config.settings import MemorySettings
from ai_team.memory.memory_config import MemoryManager


@pytest.fixture
def manager(tmp_path: Path) -> MemoryManager:
    m = MemoryManager()
    settings = MemorySettings(
        chromadb_path=str(tmp_path / "chroma"),
        sqlite_path=str(tmp_path / "mem.sqlite"),
        memory_enabled=True,
        retention_days=90,
    )
    m.initialize(settings)
    return m


class TestMemoryManagerDispatch:
    def test_store_short_term_requires_project_id(self, manager: MemoryManager) -> None:
        assert manager.store("k", "v", "short_term", project_id=None) is None

    def test_store_entity_requires_project_id(self, manager: MemoryManager) -> None:
        assert manager.store("name", {"type": "file"}, "entity", project_id=None) is None

    def test_retrieve_short_term_requires_project(self, manager: MemoryManager) -> None:
        assert manager.retrieve("q", "short_term", project_id=None) == []

    def test_store_long_term_conversation(self, manager: MemoryManager) -> None:
        rid = manager.store(
            "c1",
            {"role": "user", "content": "hi", "_subtype": "conversation"},
            "long_term",
            project_id="px",
        )
        assert rid
        out = manager.retrieve("hi", "long_term", project_id="px", top_k=5)
        assert out and out[0]["type"] == "conversation"


class TestMemoryManagerExportCleanup:
    def test_cleanup_calls_delete_collection(self, manager: MemoryManager) -> None:
        with patch.object(manager._short, "delete_collection") as dc:  # noqa: SLF001
            manager.cleanup("proj-x")
        dc.assert_called_once_with("proj-x")

    def test_export_shape(self, manager: MemoryManager) -> None:
        manager.store(
            "c1",
            {"role": "u", "content": "x", "_subtype": "conversation"},
            "long_term",
            project_id="pe",
        )
        exp = manager.export("pe")
        assert exp["project_id"] == "pe"
        assert "long_term_conversations" in exp
        assert "entities" in exp

    def test_apply_retention_delegates(self, manager: MemoryManager) -> None:
        with patch.object(manager._long, "apply_retention", return_value=3) as ar:  # noqa: SLF001
            n = manager.apply_retention()
        assert n == 3
        ar.assert_called_once()


class TestMemoryManagerDisabled:
    def test_not_initialized_when_memory_disabled(self, tmp_path: Path) -> None:
        m = MemoryManager()
        m.initialize(
            MemorySettings(
                chromadb_path=str(tmp_path / "c"),
                sqlite_path=str(tmp_path / "s.sqlite"),
                memory_enabled=False,
            )
        )
        assert not m.is_initialized
        assert m.store("k", "v", "long_term") is None
