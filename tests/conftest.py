"""Pytest configuration and shared fixtures."""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: integration tests (may use external services)")
    config.addinivalue_line("markers", "e2e: end-to-end tests (slow, full pipeline)")
