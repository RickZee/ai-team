# 2026-10-07 — pip-audit floors before the sequel merge

**The main-branch pre-push gate failed on Security after lint, unit tests, integration, the frontend build, and web E2E had already passed.** `./scripts/pip_audit.sh` reported 30 advisories. `uv.lock` on `feature/field-notes-sequel` matched `main` (`1701918`), whose CI was green on 2026-10-01 ([run 36802691259](https://github.com/RickZee/ai-team/actions/runs/36802691259)). The advisory database had moved; this branch did not.

**Fix:** raise `[tool.uv] constraint-dependencies` where a compatible release exists (`langgraph-sdk` 0.4.6, `multidict` 6.9.1, `oauthlib` 4.0.0, `pyjwt` 2.15.1, `urllib3` 2.8.0, `virtualenv` 21.14.5, `werkzeug` 3.1.9). `litellm` stays pinned at 1.74.9; `PYSEC-2026-4066` is ignored next to the other LiteLLM ids whose fixes need 1.83+. After `uv lock`, pip-audit reports no known vulnerabilities (39 ignored).
