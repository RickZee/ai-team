# Prompt 3.11: Generate conditional routing

**Source:** PROJECT_PLAN_OPUS_4_5.md — Phase 3 (Task & Flow Design)

---

Create routing logic for:
1. Planning success → Development
2. Planning needs clarification → Human feedback
3. Development success → Testing
4. Testing failure (retryable) → Development retry
5. Testing failure (fatal) → Human escalation
6. All tests pass → Deployment
7. Deployment success → Complete

Use @router decorator with string-based routing.
