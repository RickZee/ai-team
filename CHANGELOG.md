# Changelog

## 0.2.0 — 2026-09-13

Production-hardening Track A:

- Control-plane token (`AI_TEAM_WEB_TOKEN`), loopback bind default, workspace
  path containment after resolve.
- Unreachable modules wired or made dormant; uncollected eval tests moved under
  `tests/integration/evals`.
- Frontend lint/test in CI; mypy `ignore_errors` is a LOC ratchet.
- Container builds the React UI; compose context fixed.
- Docs match the code (harness status table, README structure, envelope).

## 0.1.0

Initial public field-study tree.
