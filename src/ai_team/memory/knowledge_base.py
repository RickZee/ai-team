"""
Reference knowledge base for agents: best practices and template library.

Loads structured YAML from src/ai_team/memory/knowledge/. Provides retrieval APIs
and optional integration with CrewAI knowledge sources (configurable scope per role).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)

# Default knowledge directory next to this module
_KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"

# Role -> list of topic keys to include in knowledge scope (subset of best_practices + templates)
DEFAULT_KNOWLEDGE_SCOPES: Dict[str, List[str]] = {
    "manager": ["python", "api", "devops"],
    "product_owner": ["python", "api", "testing"],
    "architect": ["python", "api", "database", "devops", "security"],
    "backend_developer": ["python", "api", "database", "testing", "security"],
    "frontend_developer": ["python", "api", "testing", "security"],
    "fullstack_developer": ["python", "api", "database", "testing", "devops", "security"],
    "devops_engineer": ["python", "api", "devops", "security"],
    "cloud_engineer": ["api", "database", "devops", "security"],
    "qa_engineer": ["python", "api", "testing", "security"],
}


class KnowledgeItem(BaseModel):
    """A single knowledge entry (best practice or template snippet)."""

    id: str = Field(description="Unique identifier")
    topic: str = Field(description="Topic or category (e.g. python, api, template)")
    title: str = Field(description="Short title or label")
    content: str = Field(description="Full text content")
    source: str = Field(description="Origin: best_practices or template")


class KnowledgeBase:
    """
    Reference knowledge: best practices by topic and template library.

    Loads from YAML files in memory/knowledge/. Supports retrieval and
    CrewAI knowledge source integration with configurable scope per agent role.
    """

    def __init__(self, knowledge_dir: Optional[Path] = None) -> None:
        self._dir = Path(knowledge_dir) if knowledge_dir else _KNOWLEDGE_DIR
        self._best_practices: Dict[str, List[str]] = {}
        self._templates: Dict[str, str] = {}
        self._items: List[KnowledgeItem] = []
        self._load()

    def _load(self) -> None:
        """Load best_practices.yaml and templates.yaml from the knowledge directory."""
        bp_path = self._dir / "best_practices.yaml"
        tpl_path = self._dir / "templates.yaml"
        if not self._dir.is_dir():
            logger.warning("knowledge_dir_missing", path=str(self._dir))
            return
        if bp_path.is_file():
            try:
                with open(bp_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                self._best_practices = {k: v for k, v in (data or {}).items() if isinstance(v, list)}
                logger.debug("best_practices_loaded", topics=list(self._best_practices.keys()))
            except (yaml.YAMLError, OSError) as e:
                logger.warning("best_practices_load_failed", path=str(bp_path), error=str(e))
        if tpl_path.is_file():
            try:
                with open(tpl_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                self._templates = {k: (v.strip() if isinstance(v, str) else str(v)) for k, v in (data or {}).items()}
                logger.debug("templates_loaded", keys=list(self._templates.keys()))
            except (yaml.YAMLError, OSError) as e:
                logger.warning("templates_load_failed", path=str(tpl_path), error=str(e))
        self._build_items()

    def _build_items(self) -> None:
        """Build flat list of KnowledgeItem for search."""
        self._items = []
        idx = 0
        for topic, practices in self._best_practices.items():
            for i, text in enumerate(practices):
                if not text or not isinstance(text, str):
                    continue
                self._items.append(
                    KnowledgeItem(
                        id=f"bp_{topic}_{i}",
                        topic=topic,
                        title=f"{topic}: {text[:60]}..." if len(text) > 60 else text,
                        content=text,
                        source="best_practices",
                    )
                )
                idx += 1
        for key, content in self._templates.items():
            if not content:
                continue
            self._items.append(
                KnowledgeItem(
                    id=f"tpl_{key}",
                    topic="template",
                    title=key,
                    content=content,
                    source="template",
                )
            )

    def get_best_practices(self, topic: str) -> List[str]:
        """
        Return the list of best-practice strings for the given topic.

        Topics: python, api, database, testing, devops, security.
        Returns empty list if topic is unknown or not loaded.
        """
        key = (topic or "").strip().lower()
        return list(self._best_practices.get(key, []))

    def get_template(self, template_type: str) -> str:
        """
        Return the template content for the given type.

        Types: flask_fastapi_api, react_component, pytest, dockerfile,
        docker_compose, github_actions, readme.
        Returns empty string if type is unknown.
        """
        key = (template_type or "").strip().lower()
        return self._templates.get(key, "")

    def search_knowledge(self, query: str, limit: int = 20) -> List[KnowledgeItem]:
        """
        Search knowledge by substring match on title and content (case-insensitive).

        Returns up to `limit` matching items, ordered by topic then id.
        """
        if not query or not query.strip():
            return []
        q = query.strip().lower()
        out: List[KnowledgeItem] = []
        for item in self._items:
            if q in item.title.lower() or q in item.content.lower():
                out.append(item)
                if len(out) >= limit:
                    break
        return out

    def get_knowledge_source_content(self, scope: Optional[List[str]] = None) -> str:
        """
        Return aggregated text of best practices and templates for the given scope.

        Scope is a list of topic keys (e.g. ["python", "api", "testing"]) and/or
        template keys. If None, all loaded content is included. Used to build
        a CrewAI StringKnowledgeSource for agent/crew knowledge_sources.
        """
        parts: List[str] = []
        if scope is None:
            for topic, practices in self._best_practices.items():
                parts.append(f"## Best practices: {topic}\n")
                parts.extend(f"- {p}" for p in practices)
                parts.append("")
            for key, content in self._templates.items():
                parts.append(f"## Template: {key}\n")
                parts.append(content)
                parts.append("")
        else:
            scope_set = {s.strip().lower() for s in scope if s}
            for topic in scope_set:
                if topic in self._best_practices:
                    parts.append(f"## Best practices: {topic}\n")
                    parts.extend(f"- {p}" for p in self._best_practices[topic])
                    parts.append("")
                if topic in self._templates:
                    parts.append(f"## Template: {topic}\n")
                    parts.append(self._templates[topic])
                    parts.append("")
        return "\n".join(parts).strip()

    def get_crewai_knowledge_source(
        self,
        role: Optional[str] = None,
        scope: Optional[List[str]] = None,
    ) -> Any:
        """
        Return a CrewAI StringKnowledgeSource for the given role or explicit scope.

        If role is provided, uses DEFAULT_KNOWLEDGE_SCOPES to derive scope;
        otherwise uses scope if provided, or all knowledge. Requires crewai to be
        installed. Returns None if StringKnowledgeSource cannot be imported.
        """
        if role and scope is None:
            scope = DEFAULT_KNOWLEDGE_SCOPES.get((role or "").strip().lower())
        content = self.get_knowledge_source_content(scope)
        if not content:
            return None
        try:
            from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource
            return StringKnowledgeSource(content=content)
        except ImportError:
            logger.debug("crewai_knowledge_source_skip", reason="StringKnowledgeSource not available")
            return None

    def list_topics(self) -> List[str]:
        """Return loaded best-practice topic keys."""
        return list(self._best_practices.keys())

    def list_template_types(self) -> List[str]:
        """Return loaded template type keys."""
        return list(self._templates.keys())


# Singleton for use across the app
_knowledge_base: Optional[KnowledgeBase] = None


def get_knowledge_base(knowledge_dir: Optional[Path] = None) -> KnowledgeBase:
    """Return the global KnowledgeBase instance (creates one if needed)."""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase(knowledge_dir=knowledge_dir)
    return _knowledge_base
