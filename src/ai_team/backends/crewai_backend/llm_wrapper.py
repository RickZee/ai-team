"""
LLM wrapper to force non-Instructor path for CrewAI conversions (e.g. long-term memory).

When CrewAI's Converter sees llm.supports_function_calling() == True, it uses
llm.call(..., response_model=...) which goes through Instructor. With Ollama that
can raise "Instructor does not support multiple tool calls, use List[Model] instead".
Wrapping the LLM so supports_function_calling() returns False makes Converter use
the plain-call + model_validate_json path instead, avoiding Instructor for that conversion.
"""

from __future__ import annotations

from typing import Any


class NoFunctionCallingLLMWrapper:
    """
    Wraps a CrewAI LLM so supports_function_calling() returns False.

    All other attributes and methods are delegated to the wrapped LLM. Use for
    planning agents when memory is enabled and the provider (e.g. Ollama) triggers
    Instructor "multiple tool calls" errors during long-term memory evaluation.
    """

    def __init__(self, llm: Any) -> None:
        self._llm = llm

    def supports_function_calling(self) -> bool:
        return False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._llm, name)
