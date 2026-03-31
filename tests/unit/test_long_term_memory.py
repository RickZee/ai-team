"""Long-term memory stub."""

from __future__ import annotations

from ai_team.memory.long_term import (
    LongTermMemory,
    NullLongTermMemory,
    get_long_term_memory,
)


def test_null_store_search_empty() -> None:
    n = NullLongTermMemory()
    assert n.search("anything") == []


def test_facade_delegates() -> None:
    m = LongTermMemory(impl=NullLongTermMemory())
    m.add_pattern("p1", "lbl", "content", {})
    assert m.search("x") == []


def test_singleton() -> None:
    a = get_long_term_memory()
    b = get_long_term_memory()
    assert a is b
