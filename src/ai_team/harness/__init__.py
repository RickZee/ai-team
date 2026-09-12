"""Shared harness facade: context, receipts, and task routing.

Backends import this package instead of reaching into tools/memory/guardrails
directly for the seven-layer contract. This module MUST NOT import backends
or crews.
"""

from __future__ import annotations

from ai_team.harness.context import ConstraintLoader, StateWriter
from ai_team.harness.journal import JournalEvent, append_journal_event
from ai_team.harness.receipt import ChangeReceipt, ReceiptWriter
from ai_team.harness.router import TaskType, resolve_route

__all__ = [
    "ChangeReceipt",
    "ConstraintLoader",
    "JournalEvent",
    "ReceiptWriter",
    "StateWriter",
    "TaskType",
    "append_journal_event",
    "resolve_route",
]
