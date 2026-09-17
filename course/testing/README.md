# Testing the course

How to have an agent (Cursor) walk through the course as a learner, check every step, and
report what to improve.

## Run it

In Cursor, type **`/test-course`** (from `.cursor/commands/test-course.md`), adjust the four
parameters, and send. Or write your own task, for example:

> Use the course-test skill. scope: week-3, mode: stranger, budget_usd: 0, fix: no.

| Parameter | Use |
| --- | --- |
| `scope` | `all`, `week-3`, or one step like `W3.S2` |
| `mode` | `stranger` = fresh clone, no data, no keys (the real test) · `maintainer` = this checkout and its runs |
| `budget_usd` | `/test-course` defaults to **$10**; `0` skips the paid steps. $10 covers weeks 1–2 and an optional small week 6 batch (spend plan: skill §2a) |
| `fix` | `yes` applies documentation fixes for P0/P1 findings on a branch, after the report |

The full procedure the agent follows is [`.cursor/skills/course-test/SKILL.md`](../../.cursor/skills/course-test/SKILL.md).

## What you get

```
course/testing/runs/<date>-<mode>/
  report.md            verdict, scorecard, findings with fixes, top 5 improvements
  observations.jsonl   one line per step block: expected, actual, result, severity, suggestion
  spend.jsonl          one line per paid run: step, backend, run id, actual cost
  logs/                raw output of every command
```

Compare two runs by diffing their `observations.jsonl` — step ids are stable because they
come from [`extract_steps.py`](./extract_steps.py).

## What the agent will not do

- Spend money, unless you give it a budget.
- Do week 4's reading for you. Open coding is human work by design; the agent only checks the
  tools work, with notes marked `SIMULATED`.
- Edit the course, unless you pass `fix: yes` — and then only documentation, on a branch,
  never pushed.

## Helpers

| File | Does |
| --- | --- |
| [`extract_steps.py`](./extract_steps.py) | Lists steps with stable ids and missing beats |
| [`run_step.py`](./run_step.py) | Runs one lab command in the learner's shell with a real time limit; kills the whole process group and reports leftovers (macOS has no `timeout`) |

## Quick structural check (no agent)

```bash
python3 course/testing/extract_steps.py
```

Lists every step, how many runnable blocks it has, and which of the Predict / Run / Observe /
Explain beats are missing. Reading-only steps legitimately have no Run block.
