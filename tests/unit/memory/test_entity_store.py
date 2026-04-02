"""Unit tests for ``EntityStore``."""

from __future__ import annotations

from pathlib import Path

import pytest
from ai_team.memory.memory_config import EntityStore


@pytest.fixture
def sqlite_path(tmp_path: Path) -> str:
    return str(tmp_path / "ent.sqlite")


class TestEntityStoreUpsert:
    def test_upsert_returns_id(self, sqlite_path: str) -> None:
        es = EntityStore(sqlite_path)
        eid = es.upsert_entity("proj1", "UserService", "service", {"lang": "py"})
        assert eid > 0
        got = es.get_entity("proj1", "UserService")
        assert got is not None
        assert got["name"] == "UserService"
        assert got["entity_type"] == "service"

    def test_upsert_updates_existing(self, sqlite_path: str) -> None:
        es = EntityStore(sqlite_path)
        es.upsert_entity("p", "api", "file", {})
        es.upsert_entity("p", "api", "service", {"v": 2})
        got = es.get_entity("p", "api")
        assert got["entity_type"] == "service"


class TestEntityStoreRelationships:
    def test_add_relationship_links_entities(self, sqlite_path: str) -> None:
        es = EntityStore(sqlite_path)
        es.upsert_entity("p", "a", "x", {})
        es.upsert_entity("p", "b", "y", {})
        es.add_relationship("p", "a", "b", "calls")
        rels = es.get_relationships("p")
        assert len(rels) == 1
        assert rels[0]["from_name"] == "a"
        assert rels[0]["to_name"] == "b"


class TestEntityStoreDeletion:
    def test_delete_project_removes_entities(self, sqlite_path: str) -> None:
        es = EntityStore(sqlite_path)
        es.upsert_entity("p", "only", "z", {})
        es.delete_project("p")
        assert es.get_entities("p") == []
