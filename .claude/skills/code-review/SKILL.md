---
description: "Review code for security vulnerabilities, performance issues, and style violations"
tools: ["Read", "Glob", "Grep"]
---

# Code Review Skill

When asked to review code:

1. Scan for security issues: `eval()`, `exec()`, SQL injection, XSS, hardcoded secrets
2. Check performance: N+1 queries, unnecessary loops, missing indexes
3. Verify style: type hints, docstrings, consistent naming
4. Output a structured review with severity levels (critical / warning / info)
