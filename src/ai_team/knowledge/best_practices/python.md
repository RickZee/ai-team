# Python best practices

- Use type hints on public functions and Pydantic models for structured data.
- Prefer `pathlib.Path` over string paths for file operations.
- Use `structlog` for logging instead of `print` in production code.
- Keep functions focused; extract helpers when cyclomatic complexity grows.
- Use context managers (`with`) for files and network clients.
