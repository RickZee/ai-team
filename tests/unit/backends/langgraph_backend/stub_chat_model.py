"""Test doubles for LangGraph subgraph compilation (supervisor ``bind_tools``)."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.fake_chat_models import FakeListChatModel


class FakeChatModelWithBindTools(FakeListChatModel):
    """
    ``FakeListChatModel`` that implements ``bind_tools`` for ``langgraph_supervisor``.

    The default fake raises ``NotImplementedError`` in ``bind_tools``.
    """

    def bind_tools(self, tools: Any, **kwargs: Any) -> FakeChatModelWithBindTools:
        _ = tools
        _ = kwargs
        return self
