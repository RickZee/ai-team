"""Long-term memory (SQLite) + lessons: the self-improvement substrate.

Agents coordinate through files on disk (per CLAUDE.md); durable cross-run
memory is the LongTermStore plus the lessons loop that promotes recurring
failure patterns into role-scoped guidance.
"""

from ai_team.memory.memory_config import LongTermStore

__all__ = ["LongTermStore"]
