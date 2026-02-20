"""Unit tests for memory.knowledge_base."""

import tempfile
from pathlib import Path

import yaml
import pytest

from ai_team.memory.knowledge_base import (
    DEFAULT_KNOWLEDGE_SCOPES,
    KnowledgeBase,
    KnowledgeItem,
    get_knowledge_base,
)


@pytest.fixture
def temp_knowledge_dir(tmp_path):
    """Create a minimal knowledge dir with best_practices and templates."""
    (tmp_path / "best_practices.yaml").write_text(
        yaml.dump({
            "python": ["Use type hints.", "Follow PEP 8."],
            "api": ["Use REST conventions.", "Return 200 for success."],
        }),
        encoding="utf-8",
    )
    (tmp_path / "templates.yaml").write_text(
        yaml.dump({
            "pytest": "Pytest template: use fixtures and parametrize.",
            "readme": "README template: title, install, usage.",
        }),
        encoding="utf-8",
    )
    return tmp_path


class TestKnowledgeBase:
    def test_load_from_default_dir(self):
        """Default dir loads bundled best_practices and templates."""
        kb = KnowledgeBase()
        topics = kb.list_topics()
        assert "python" in topics
        assert "api" in topics
        assert "testing" in topics
        assert "pytest" in kb.list_template_types()

    def test_load_from_custom_dir(self, temp_knowledge_dir):
        """Custom dir loads only files from that path."""
        kb = KnowledgeBase(knowledge_dir=temp_knowledge_dir)
        assert set(kb.list_topics()) == {"python", "api"}
        assert set(kb.list_template_types()) == {"pytest", "readme"}

    def test_get_best_practices(self, temp_knowledge_dir):
        kb = KnowledgeBase(knowledge_dir=temp_knowledge_dir)
        bp = kb.get_best_practices("python")
        assert len(bp) == 2
        assert "type hints" in bp[0]
        assert kb.get_best_practices("unknown") == []
        assert kb.get_best_practices("") == []

    def test_get_template(self, temp_knowledge_dir):
        kb = KnowledgeBase(knowledge_dir=temp_knowledge_dir)
        tpl = kb.get_template("pytest")
        assert "fixtures" in tpl or "fixture" in tpl
        assert kb.get_template("nonexistent") == ""
        assert kb.get_template("") == ""

    def test_search_knowledge(self, temp_knowledge_dir):
        kb = KnowledgeBase(knowledge_dir=temp_knowledge_dir)
        items = kb.search_knowledge("fixture")
        assert isinstance(items, list)
        assert all(isinstance(i, KnowledgeItem) for i in items)
        assert all("fixture" in i.content.lower() or "fixture" in i.title.lower() for i in items)
        assert kb.search_knowledge("") == []
        assert kb.search_knowledge("   ") == []

    def test_get_knowledge_source_content_all(self, temp_knowledge_dir):
        kb = KnowledgeBase(knowledge_dir=temp_knowledge_dir)
        content = kb.get_knowledge_source_content()
        assert "Best practices: python" in content
        assert "Template: pytest" in content

    def test_get_knowledge_source_content_scope(self, temp_knowledge_dir):
        kb = KnowledgeBase(knowledge_dir=temp_knowledge_dir)
        content = kb.get_knowledge_source_content(["python"])
        assert "Best practices: python" in content
        assert "Template: pytest" not in content
        content2 = kb.get_knowledge_source_content(["pytest"])
        assert "Template: pytest" in content2

    def test_get_crewai_knowledge_source_role(self):
        kb = get_knowledge_base()
        src = kb.get_crewai_knowledge_source(role="backend_developer")
        assert src is not None
        assert type(src).__name__ == "StringKnowledgeSource"

    def test_get_crewai_knowledge_source_scope(self, temp_knowledge_dir):
        kb = KnowledgeBase(knowledge_dir=temp_knowledge_dir)
        src = kb.get_crewai_knowledge_source(scope=["python"])
        assert src is not None

    def test_default_knowledge_scopes_has_expected_roles(self):
        assert "architect" in DEFAULT_KNOWLEDGE_SCOPES
        assert "backend_developer" in DEFAULT_KNOWLEDGE_SCOPES
        assert "qa_engineer" in DEFAULT_KNOWLEDGE_SCOPES


class TestKnowledgeItem:
    def test_model(self):
        item = KnowledgeItem(
            id="bp_python_0",
            topic="python",
            title="Use type hints",
            content="Use type hints on all public functions.",
            source="best_practices",
        )
        assert item.topic == "python"
        assert item.source == "best_practices"
