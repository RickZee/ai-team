# Testing best practices

- Write unit tests for pure logic; integration tests for I/O and external services.
- Use pytest markers (`integration`, `slow`) to separate fast CI from heavy suites.
- Mock LLM and network boundaries in unit tests; use real APIs only in integration tests.
- Aim for meaningful assertions on behavior, not only line coverage.
- Keep test data small and fixtures in `tests/fixtures/` when shared.
