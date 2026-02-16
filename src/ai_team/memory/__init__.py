"""
Memory and knowledge base configuration for agent context.

Unified memory: short-term (ChromaDB, per-project RAG), long-term (SQLite,
conversations/metrics/patterns), and entity memory (project structure).
Knowledge base: best practices and templates in memory/knowledge/; load as
CrewAI knowledge source with configurable scope per role.
Initialize via get_memory_manager().initialize(settings.memory) from app config.
"""

from ai_team.memory.memory_config import (
    EntityStore,
    LongTermStore,
    MemoryManager,
    MemoryType,
    OllamaChromaEmbeddingFunction,
    ShortTermStore,
    get_memory_manager,
)
from ai_team.memory.knowledge_base import (
    KnowledgeBase,
    KnowledgeItem,
    get_knowledge_base,
)

__all__ = [
    "EntityStore",
    "LongTermStore",
    "MemoryManager",
    "MemoryType",
    "OllamaChromaEmbeddingFunction",
    "ShortTermStore",
    "get_memory_manager",
    "KnowledgeBase",
    "KnowledgeItem",
    "get_knowledge_base",
]
