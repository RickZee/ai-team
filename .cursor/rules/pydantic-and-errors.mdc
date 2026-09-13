---
description: Pydantic, error handling, and logging conventions
globs: "**/*.py"
alwaysApply: false
---

# Pydantic Conventions

- Use Pydantic v2 `BaseModel`; `Field(description=...)` for all fields
- Validators: `@field_validator` or `@model_validator`; `model_config` with `json_schema_extra` where helpful
- Settings: `pydantic_settings.BaseSettings` with `SettingsConfigDict`
- Output models: `src/ai_team/models/outputs.py`; state models: `src/ai_team/backends/crewai_backend/flows/state.py`

# Error Handling

- Custom exceptions live next to the code that raises them; never use a catch-all ``utils.exceptions`` module.
- Never use bare `except:`; catch specific exceptions
- Use `tenacity` for retry with exponential backoff
- Log errors with structlog including context (agent, tool, phase)

# Logging

- Use **structlog** only; never `print()` or `logging` directly
- Get logger: `logger = structlog.get_logger(__name__)`
- Bind context: `logger.bind(agent=self.role, phase=current_phase)`
- Levels: DEBUG (tool calls), INFO (phase transitions), WARNING (retries), ERROR (hard failures)

```python
logger = structlog.get_logger(__name__)
logger.bind(agent=self.role_name, phase=current_phase).info("Task started")
```
