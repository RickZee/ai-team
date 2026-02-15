"""E2E tests for full pipeline (optional, slower)."""

import pytest


@pytest.mark.e2e
@pytest.mark.skip(reason="E2E placeholder — enable when Ollama and crews are wired")
def test_full_project_generation() -> None:
    """Placeholder: run full flow from request to deployment config."""
    pass
