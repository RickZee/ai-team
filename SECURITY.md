# Security

This project runs autonomous AI agents that write and execute code. That makes it
a security-relevant system by construction: generated code is untrusted input,
agent tool calls are untrusted actions, and LLM outputs can carry injected
instructions. This document describes the threat model and the controls in place.

## Threat model

| Threat | Vector | Control |
|---|---|---|
| Malicious/unsafe generated code | Agent writes code containing `eval`/`exec`/`os.system`, shell injection, unsafe deserialization | `code_safety_guardrail` scans all generated code; project rules prohibit `eval()`, `exec()`, `os.system()`; subprocess calls use argument lists with `shell=False`; `yaml.safe_load` only |
| Workspace escape | Agent writes outside its per-run workspace via `..` traversal or absolute paths | `path_security_guardrail` — path normalization, workspace-boundary validation, system-path denylist; adversarial tests in `tests/unit/tools/test_file_tools_adversarial.py` and `test_git_tools_adversarial.py` |
| Secret exfiltration | Agent reads or writes credentials, `.env`, keys | Sensitive-filename rejection for automated writes (`.env`, credentials); `secret_detection_guardrail` scans outputs; no secrets in git (env-var configuration via Pydantic Settings) |
| Prompt injection | Task briefs, file contents, or tool results carrying instructions to the agent | `prompt_injection_guardrail` on inputs; agent role/scope behavioral guardrails limit blast radius; HITL escalation on repeated failures |
| PII leakage | Generated artifacts or logs containing personal data | `pii_redaction_guardrail` on task outputs |
| Runaway cost | Misbehaving agent loop burning API spend | Per-run budget caps enforced at runtime (live-verified aborts); hard wall-clock timeouts with subprocess kill |
| Cross-run interference | One run reading or writing another run's workspace | Per-run workspace isolation; subprocess isolation per backend run; see [journal/2026-07-06.md](docs/journal/2026-07-06.md) for run-identity contract fixes |
| Unaccountable automation | A human override silently converting a failing run into a passing one | Distinct `complete_approved` terminal status; `audit.jsonl` per run; HITL decisions recorded |

## Guardrail architecture

Three layers, enforced at different points:

1. **Behavioral** (`src/ai_team/guardrails/behavioral.py`) — role adherence and
   scope relevance: agents act only within their role's mandate.
2. **Security** (`src/ai_team/guardrails/security.py`) — code safety, path
   security, secret detection, PII redaction, prompt-injection detection.
   Applied across all three orchestration backends via backend-specific adapters.
3. **Quality** (`src/ai_team/guardrails/quality.py`) — syntax validity,
   completeness gates; failures route to bounded retries, then human review.

Guardrails are tested with both happy-path and adversarial cases (project rule:
every new tool or guardrail ships with adversarial tests).

## Execution isolation

- Backend runs execute in subprocesses with hard timeouts and clean kill
  semantics (no orphaned work after deadline).
- Generated code is executed only inside per-run workspaces; evaluation commands
  run in the target workspace, never the repo root.
- Local web UI binds to localhost; it is a development/operations console, not an
  internet-facing service. Do not expose it publicly without adding
  authentication — it can start paid runs and delete run data.

## Reporting a vulnerability

Open a GitHub issue with the `security` label, or email the maintainer directly
(see repo profile) for anything sensitive. Include a minimal reproduction.
Please do not open public issues for anything that could enable abuse of a
deployed instance before a fix lands.

## Known limitations (honest ledger)

- Guardrails are pattern/heuristic based — they reduce, not eliminate, prompt
  injection and unsafe-code risk. Do not run this system against untrusted
  briefs with credentials in scope.
- The web UI has no authentication layer (localhost-only by design).
- Cross-run workspace-nesting leak was fixed via the run-identity contract (journal
  [2026-07-06](docs/journal/2026-07-06.md)); report any recurrence as a security issue.
