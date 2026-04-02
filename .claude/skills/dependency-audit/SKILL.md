---
description: "Check dependencies for obvious risk signals (pin drift, known bad patterns)"
tools: ["Read", "Glob", "Grep"]
---

# Dependency Audit Skill

When auditing dependencies:

1. Identify manifest files (`pyproject.toml`, `package.json`, lockfiles)
2. Flag unpinned or overly broad version ranges in production paths
3. Recommend concrete version pins or follow-up automation (e.g. `pip-audit`), not blind upgrades
