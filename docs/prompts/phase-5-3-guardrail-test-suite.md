# Prompt 5.3: Generate guardrail test suite

**Source:** PROJECT_PLAN_OPUS_4_5.md — Phase 5 (Testing, Iteration & Guardrail Validation)

---

Create comprehensive tests for all guardrails:
1. Test dangerous code detection (eval, exec, system)
2. Test PII pattern detection and redaction
3. Test prompt injection detection
4. Test role adherence validation
5. Test output format validation
6. Test retry behavior on failures
7. Include adversarial test cases

Use pytest fixtures for test data.
