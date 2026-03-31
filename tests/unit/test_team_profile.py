"""Tests for team profile loading."""

from __future__ import annotations

import pytest
from ai_team.core.team_profile import load_team_profile, load_team_profiles


def test_load_team_profiles_has_full() -> None:
    profiles = load_team_profiles()
    assert "full" in profiles
    assert "manager" in profiles["full"].agents
    rag = profiles["full"].metadata.get("rag")
    assert isinstance(rag, dict)
    assert "knowledge_topics" in rag


def test_load_team_profile_unknown() -> None:
    with pytest.raises(KeyError, match="Unknown team profile"):
        load_team_profile("nonexistent_profile_xyz")
