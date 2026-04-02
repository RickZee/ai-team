---
description: "Analyze test failures and propose minimal, targeted fixes"
tools: ["Read", "Glob", "Grep"]
---

# Test Analysis Skill

When tests fail:

1. Parse failure output for root cause (assertion, import, fixture, env)
2. Map failures to the smallest code or test change
3. Avoid expanding scope; prefer fixing tests when the spec is wrong, code when behavior is wrong
