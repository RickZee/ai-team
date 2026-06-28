# Business Use Case: Setup Smoke Test

Not a real project. Purpose is to verify the agent pipeline runs end-to-end with the absolute minimum token spend before attempting any real demo.

## Business need

Something is wrong and we don't know where — keys, routing, model access, tool wiring, or workspace setup. We need to know which layer is broken without burning budget on a full demo.

## What matters

- Each agent in the pipeline gets invoked at least once
- Output files land in the workspace
- No crash, no auth failure, no silent skip

## Who asked for this

Any engineer setting up the system for the first time, or debugging a broken environment.

---

> **Note for the team:** This demo uses the `prototype` profile (Architect + Fullstack + QA). Smallest real crew that exercises planning → development → testing phases. If this passes, move to the To-do app scenario (`demos/02_todo_app`).
