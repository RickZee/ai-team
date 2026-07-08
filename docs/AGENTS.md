# Agent personas

Nine specialist agents simulate a software engineering organization. Personas are
**registered in code** in [`src/ai_team/config/agents.yaml`](../src/ai_team/config/agents.yaml)
and loaded by CrewAI/LangGraph backends. The Claude Agent SDK backend maps the same
YAML roles to SDK subagent definitions in
[`src/ai_team/backends/claude_agent_sdk_backend/agents/`](../src/ai_team/backends/claude_agent_sdk_backend/agents/).

Which agents run for a given project is controlled by **team profiles**
([`team_profiles.yaml`](../src/ai_team/config/team_profiles.yaml), [TEAM_PROFILES.md](TEAM_PROFILES.md)),
not by editing `agents.yaml` per run.

---

## Catalog

| YAML key | Title | Delegation | max_iter | Memory | Primary responsibility |
| -------- | ----- | ---------- | -------- | ------ | -------------------- |
| `manager` | Engineering Manager / Project Coordinator | yes | 15 | yes | Coordinate phases, resolve blockers, escalate to humans |
| `product_owner` | Product Owner / Requirements Analyst | no | 10 | yes | Requirements, user stories, acceptance criteria, MoSCoW prioritization |
| `architect` | Solutions Architect / Tech Lead | yes | 12 | yes | System design, ADRs, NFRs, component boundaries |
| `backend_developer` | Senior Backend Developer | no | 15 | yes | APIs, data layer, server code, self-review before handoff |
| `frontend_developer` | Senior Frontend Developer | no | 15 | yes | UI components, accessibility, state, CSS/design systems |
| `fullstack_developer` | Senior Fullstack Developer | no | 15 | yes | End-to-end features; **must** write files via `file_writer` tool |
| `cloud_engineer` | Cloud Infrastructure Engineer | no | 10 | yes | IaC (Terraform/CloudFormation), networking, IAM, cost/security |
| `devops_engineer` | DevOps / SRE Engineer | no | 10 | yes | CI/CD, Docker/K8s, observability, root `README.md` for every run |
| `qa_engineer` | QA Engineer / Test Automation Specialist | no | 5 | yes | Pytest suites via `file_writer`; min coverage gate 80% |

---

## Persona detail

### Manager (`manager`)

- **Goal:** Coordinate the team, resolve blockers, ensure on-time delivery; escalate
  when confidence is low or decisions need a human.
- **Backstory:** 20+ years engineering leadership; agile and distributed teams;
  assigns work by capability and workload; tracks phase transitions.
- **SDK mapping:** Orchestrator phase agents (`planning-agent`, `development-agent`,
  `deployment-agent`) when those phases are in the active profile.

### Product Owner (`product_owner`)

- **Goal:** Turn vague ideas into clear, prioritized requirements with acceptance criteria.
- **Backstory:** 15+ years product management; user story mapping and MoSCoW.
- **SDK mapping:** `product-owner` subagent.

### Architect (`architect`)

- **Goal:** Scalable, maintainable architectures with clear interfaces.
- **Backstory:** Principal architect; distributed systems, cloud, ADRs.
- **SDK mapping:** `architect` subagent (default model tier: `opus` in SDK backend).

### Backend Developer (`backend_developer`)

- **Goal:** Robust backend services, REST/GraphQL APIs, performant schemas, production-ready error handling.
- **Backstory:** 12+ years; Python/Node/Go; FastAPI, Flask, Django; obsessive API design and tests.
- **SDK mapping:** `backend-developer` subagent.

### Frontend Developer (`frontend_developer`)

- **Goal:** Responsive, accessible, performant UIs; component architecture and design systems.
- **Backstory:** React/Vue expert; Core Web Vitals, a11y, TypeScript, React Testing Library.
- **SDK mapping:** `frontend-developer` subagent.

### Fullstack Developer (`fullstack_developer`)

- **Goal:** Complete features across stack; APIs + UI aligned with architecture.
- **Backstory:** Comfortable on server and client; **critical rule:** every source file must be written with the `file_writer` tool, never as plain text in the message body.
- **SDK mapping:** `fullstack-developer` subagent.

### Cloud Engineer (`cloud_engineer`)

- **Goal:** IaC, cost/performance/security/reliability; reusable Terraform modules.
- **Backstory:** AWS/GCP/Azure certified; least privilege; no manual infra.
- **SDK mapping:** `cloud-engineer` subagent (default SDK model: `haiku`).

### DevOps Engineer (`devops_engineer`)

- **Goal:** CI/CD, Docker, monitoring, alerting; always produce a root `README.md`.
- **Backstory:** SRE background (Netflix/Google/Spotify scale); GitOps, observable systems.
- **YAML key note:** model config uses `devops` internally (`devops_engineer` → `devops` in `models.py`).
- **SDK mapping:** `devops-engineer` subagent (default SDK model: `haiku`).

### QA Engineer (`qa_engineer`)

- **Goal:** Comprehensive testing; pytest files written with `file_writer` only.
- **Backstory:** Test pyramid advocate; reads `src/` from workspace, writes `test_*.py`.
- **Guardrail:** `min_coverage_threshold: 0.8` in YAML.
- **SDK mapping:** `testing-agent` when `testing` phase is active.

---

## How personas connect to models

| Backend | Persona source | Model source |
| ------- | -------------- | ------------ |
| CrewAI / LangGraph | `agents.yaml` (goal, backstory) | `models.py` `ENV_MODELS[AI_TEAM_ENV]` + optional `team_profiles.yaml` `model_overrides` |
| Claude Agent SDK | Same YAML + SDK prompt builders | SDK short names (`sonnet`, `opus`, `haiku`) or profile `model_overrides` |

See [MODELS.md](MODELS.md) for per-environment model matrices and provider comparison.

---

## Changing a persona

1. Edit [`src/ai_team/config/agents.yaml`](../src/ai_team/config/agents.yaml).
2. For SDK-specific prompt text, edit
   [`agents/prompts.py`](../src/ai_team/backends/claude_agent_sdk_backend/agents/prompts.py)
   or [`agents/definitions.py`](../src/ai_team/backends/claude_agent_sdk_backend/agents/definitions.py).
3. Add/adjust unit tests under `tests/unit/test_agents.py`.
4. Update this document if role responsibilities change.
