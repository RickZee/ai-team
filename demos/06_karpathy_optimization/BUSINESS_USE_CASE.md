# Business Use Case: Autonomous Performance Optimization (Karpathy Loop)

After shipping an application, the business wants **measurable performance gains** without blocking a senior engineer on a tuning sprint. The idea: agents propose one change at a time, measure a metric, keep what works, revert what doesn't, and record lessons for the next run — overnight, within a defined budget.

## Business need

Performance work gets deferred until incidents force a fire drill. When engineers finally tune, the changes are large, risky, undocumented, and hard to review. There's no institutional memory of what was tried and what failed. We want a governed, budgeted loop that produces small auditable commits.

## What matters

- Loop runs within a token/cost budget (`--budget`, `--max-experiments`)
- API contract and test suite stay untouched — no regressions allowed
- Every experiment logged; promoted lessons available for future runs
- Positive improvement on the target metric when infra supports it

## Who asked for this

Engineering leads targeting KPI improvements (RPS, latency, pass rate). FinOps owns the budget constraint. This demo requires demo 02 (TODO app) to exist as the optimization target.

---

> **Note for the team:** Product Owner defines the metric, budget ceiling, and "no regression" acceptance criteria. Architect (or Optimizer agent) designs the experiment loop, revert strategy, and logging schema. This document is the stakeholder brief — not the spec.
