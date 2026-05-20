# Agents

AI-Team models a small engineering organization. Agent definitions live in
`src/ai_team/config/agents.yaml`; team composition lives in
`src/ai_team/config/team_profiles.yaml`.

## Core agents

| Agent | Responsibility | Delegation |
| ----- | -------------- | ---------- |
| Manager | Coordinates phases, assigns work, resolves blockers, and escalates to humans when clarification is needed. | Yes |
| Product Owner | Turns vague requests into prioritized requirements, user stories, and acceptance criteria. | No |
| Architect | Designs system structure, component boundaries, interfaces, and ADRs. | Yes |
| Backend Developer | Builds APIs, services, persistence layers, and backend tests. | No |
| Frontend Developer | Builds responsive, accessible UI components and client-side behavior. | No |
| Fullstack Developer | Delivers complete vertical slices across API, data, and UI layers. | No |
| QA Engineer | Creates and runs tests, validates acceptance criteria, and reports quality risks. | No |
| DevOps Engineer | Produces CI/CD, Docker, deployment, monitoring, and reliability artifacts. | No |
| Cloud Engineer | Designs infrastructure-as-code with cost, security, and reliability constraints. | No |
| Optimizer | Runs one-change-at-a-time optimization experiments against a measured metric. | No |

## Team profiles

Profiles select the minimum useful set of agents for a given request:

| Profile | Agents | Phases |
| ------- | ------ | ------ |
| `full` | Manager, Product Owner, Architect, Backend, Frontend, Fullstack, DevOps, Cloud, QA | intake, planning, development, testing, deployment |
| `backend-api` | Manager, Product Owner, Architect, Backend, QA, DevOps | intake, planning, development, testing, deployment |
| `frontend-app` | Manager, Product Owner, Architect, Frontend, QA, DevOps | intake, planning, development, testing, deployment |
| `data-pipeline` | Manager, Product Owner, Architect, Backend, QA | intake, planning, development, testing |
| `prototype` | Architect, Fullstack, QA | intake, planning, development, testing |
| `infra-only` | Architect, DevOps, Cloud | intake, planning, deployment |
| `research-optimizer` | Optimizer | optimize |

## Runtime notes

- CrewAI and LangGraph consume the same role definitions and team profiles.
- The Claude Agent SDK backend maps the same roles onto SDK subagents and file-based
  handoff under the run workspace.
- Role boundaries are enforced by behavioral guardrails; for example, QA should produce
  tests and reports rather than production source, while Product Owner output should stay
  in requirements and acceptance criteria.
