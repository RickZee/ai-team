# Guardrails

Guardrails keep agent output inside role, safety, and quality boundaries. The main
implementations live in `src/ai_team/guardrails/`.

## Behavioral guardrails

Behavioral checks validate whether an agent stayed within its assigned role and task
scope. Examples:

- QA output should focus on tests and quality reports, not production source changes.
- Product Owner output should define requirements, not implementation code.
- Backend and frontend agents should avoid crossing into each other's domains unless the
  selected team profile explicitly uses the Fullstack Developer.
- Managers and architects may reference technical details while coordinating, but direct
  implementation is treated differently from delegation.

Key file: `src/ai_team/guardrails/behavioral.py`.

## Security guardrails

Security checks block or warn on risky generated content:

- dangerous execution patterns such as `eval()`, `exec()`, `os.system()`, unsafe
  `subprocess` calls, and unsafe YAML loading
- PII and secret-like strings, with redacted output in guardrail details
- prompt-injection attempts and suspicious instruction override patterns
- unsafe file paths, traversal, and sensitive filename access

Key file: `src/ai_team/guardrails/security.py`.

## Quality guardrails

Quality checks score generated code and documents for maintainability and completeness:

- Python syntax validity
- function and file size limits
- approximate cyclomatic complexity
- public function docstrings and type hints
- TODO/FIXME/HACK markers
- hardcoded credential patterns
- JSON validity and placeholder detection

Key file: `src/ai_team/guardrails/quality.py`.

## Testing

Guardrails are covered by focused unit tests and adversarial cases under `tests/unit/`
and `tests/guardrails/`. New guardrails should include passing, failing, and edge-case
tests, plus adversarial inputs for security-sensitive behavior.
