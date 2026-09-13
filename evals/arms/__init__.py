"""Comparison arms: adapters that produce workspaces scored by the same Trace checks.

An arm is not a Backend. Arms swap the harness (solo, reference, ai_team, ablated)
while holding model and scenario fixed. See ``.kiro/specs/harness-alignment/``.
"""

from __future__ import annotations
