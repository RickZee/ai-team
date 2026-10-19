"""
ai_team: one nine-agent software team on interchangeable orchestration backends.

Backends (CrewAI, LangGraph, Claude Agent SDK; Strands and Agent Framework as stubs)
run behind one ``Backend`` protocol and share the harness: ToolBus, guardrails,
spend guard, pinned context and results bundle. Map: ``docs/MODULE_MAP.md``.
"""
