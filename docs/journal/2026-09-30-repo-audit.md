# 2026-09-30 — repo audit: what the repo declares vs. what it exercises

**Session:** 2026-09-30. Agent-assisted (Claude, Cowork).
**Branch:** `chore/repo-audit-2026-09`, eight commits on top of `a7dec30`.
**Scope:** structure, dependencies, tooling, tests, docs, outdated references. Every
external claim below has a link in [Sources](#sources).

## The one lesson

Almost every finding had the same shape: **something was declared, and nothing exercised
it.** A dependency listed and never imported. An AI-assistant rule describing an API that
does not exist. An adversarial test suite that CI never collects. A harness layer marked
*enforced* whose function nobody calls. A citation to a page that returns 404.

Each of those passes review, because a reviewer reads the declaration. Each is caught by
a cheap mechanical question: *what imports it, what collects it, what calls it, what does
the URL return?* The repo already asks two of those questions (`test_reachability`,
`test_references`). The findings below are the places where the question was one level
too shallow: `test_reachability` asks "is this module imported?", and `guardrail_risk`
is imported, inside a function that is never called.

## Fixed on this branch

| # | Finding | Evidence | Fix | Commit |
| --- | --- | --- | --- | --- |
| 1 | 29 deprecated shim modules + `_compat.py` with zero importers | Only consumer was the test of the shims; spec R10.3 already made shims optional | Deleted | `71d3c34` |
| 2 | 17 direct dependencies nothing imports (crewai-tools, langchain-community, sqlalchemy, tenacity, pillow, lxml, …) | `grep` of every `import` in `src/ evals/ scripts/ tests/` | Removed; CVE floors moved to `[tool.uv] constraint-dependencies`. Lock loses 23 packages (pyarrow, lancedb, pymupdf, docker, youtube-transcript-api) | `d5ab7f7` |
| 3 | `requires-python = "<=3.13"` excludes 3.13.1+ | PEP 440: 3.13.1 > 3.13 | `<3.14` | `d5ab7f7` |
| 4 | Two formatters: CI ran `ruff format`, CONTRIBUTING/CLAUDE.md/Cursor rules said Black + isort | Ruff docs: not meant to be used interchangeably with Black on an ongoing basis | Ruff only; ruff 0.3.7 → 0.16.9; Markdown excluded from formatting | `d5ab7f7`, `a1300a8` |
| 5 | `evals.run_evals` under `ignore_errors` but type-checks clean | `mypy evals/` with the override removed: 0 errors | Override retired; type-debt ratchet 13,000 → 12,241 LOC | `d5ab7f7` |
| 6 | Eval logs at fixed `/tmp/eval_<backend>.log` | In the sandbox the file already existed, owned by `nobody` → `PermissionError` | Per-user 0700 dir under `tempfile.gettempdir()` (CWE-377) | `1a16050` |
| 7 | Unit tests opened the developer's real `./data/memory.db` | `sqlite3.OperationalError: disk I/O error` on a read-only mount | Session fixture pins `MEMORY_SQLITE_PATH` to temp | `1a16050` |
| 8 | Secret detector missed every key format the repo itself uses | `sk-[A-Za-z0-9]{24,}` stops at the first hyphen: `sk-ant-…`, `sk-or-v1-…`, `sk-proj-…` passed; so did `github_pat_`, `ghs_`, `AKIA…` | Prefix patterns from GitHub and AWS docs; placeholder negatives | `47d3a3c` |
| 9 | CrewAI used its own copy of the secret/injection regexes | "system: you are …" rejected on LangGraph/Claude SDK, accepted on CrewAI | Class API reads the function API's lists; parity test | `47d3a3c` |
| 10 | 36 adversarial guardrail tests never ran in CI | `tests/guardrails/` is outside `tests/unit`, the only path CI runs | Moved to `tests/unit/guardrails/adversarial/` | `a1300a8` |
| 11 | Always-applied Cursor rules described another project | "built with CrewAI", Ollama models, Textual TUI, `get_ollama_llm()` (does not exist) | Rewritten from `pyproject.toml` and the code | `a1300a8` |
| 12 | Pointer-only docs (`EVALS.md` 9 lines, `EVALS_ROADMAP.md` 13) and a 119 KB prompt log for `crewai>=0.80` | Inbound links hop through a stub | Deleted, links repointed; history keeps them | `fd3b820` |
| 13 | Image-reference guard walked the untracked `workspace/` | 39 s, machine-dependent, flaky under xdist | Reads `git ls-files`: 0.5 s | `fd3b820` |
| 14 | `uv run pytest` failed collection | `tests/conformance/` had no `__init__.py` and shares a basename with a unit test (pytest's rule for rootdir-relative imports) | Package marker; 1,957 tests collect | `3a7de30` |
| 15 | Husain & Shankar cited via an `eugeneyan.com` URL | Returns 404; not their site; two different titles for one link | Their Evals FAQ and Husain's Field Guide | `3a7de30` |
| 16 | HARNESS.md: `risk_class` guardrail subsets **enforced** | `TeamProfile.risk_class` read by nothing; `should_run` called only by `create_full_guardrail_chain`, called by nothing | Row now says **not wired** | `3a7de30` |
| 17 | README: pitch twice, two quick starts, caveat three times, "ten" vs "seventeen" classes, shim dirs in the tree, stale framework-doc URLs | Read top to bottom | One reading path, Mermaid flow incl. the eval path, two existing figures placed where the argument needs them, `docs/README.md` map | `3a7de30` |
| 18 | Run-delete test could remove a real `workspace/<id>/` | `Operation not permitted: …/workspace/del-1/src` | Session pins `PROJECT_WORKSPACE_DIR` to temp | `a60cb5f` |

Unit suite: 1,768 passed, sequential and under `-n 4`. `ruff check`, `ruff format --check`,
`mypy src/`, `mypy evals/`: clean.

## Open, with a recommendation

Ordered by what a reviewer would hit first. None of these is fixed here, because each is a
decision or a multi-day change rather than a cleanup.

| Finding | Evidence | Recommendation |
| --- | --- | --- |
| **Tests still create run dirs in the repo** | Backends fall back to a literal `"./workspace"` (deliberately, to avoid a stale `PROJECT_WORKSPACE_DIR` mirror). ~14 dirs per unit-suite run; 77 during this audit | One `DEFAULT_WORKSPACE_ROOT` captured at boot in `config/settings.py`, used by all three backends; then extend the `_isolate_run_output` leak assertion to `workspace/` |
| **`risk_class` is configuration with no effect** | See #16 | Wire `should_run` into the live guardrail path, or delete `guardrail_risk.py`, `create_full_guardrail_chain` and the profile field. Also: make `test_reachability` call-graph aware for lazily imported modules |
| **CrewAI 1.6.1; latest 1.15.23** | `uv tree --outdated` | Upgrade on its own branch; the `litellm==1.74.9` pin exists for CrewAI 1.6 and should move with it. Stay off litellm 1.82.7/1.82.8 (malicious uploads, 2026-03-24) |
| **`create_react_agent` deprecated since LangGraph 1.0** (5 call sites) and `langgraph-supervisor` now recommends a tool-based supervisor | Runtime `LangGraphDeprecatedSinceV10` warning; supervisor README | Migrate to `langchain.agents.create_agent` before LangGraph 2.0 removes it |
| **Code-safety regexes still duplicated** | `SecurityGuardrails.DANGEROUS_CODE_PATTERNS` vs `security._DEFAULT_DANGEROUS_PATTERNS` differ (e.g. the class flags any `subprocess.run`) | Same treatment as #9, after checking what CrewAI dev agents currently emit |
| **`actions/*` pinned at v4-era SHAs** with `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` as a workaround | `actions/checkout` is at v7.0.1 | Bump each action to its current SHA and drop the env override |
| **Pinned-low runtime libs**: structlog `<25` (26.1), httpx `<0.28` (0.28.1), pytest-cov 4.1 (7.1), mypy 1.x (2.3) | `uv tree --outdated` | Upgrade one per PR. pytest-cov 7 changed subprocess handling that `tests/conftest.py` works around |
| **Python 3.13 declared, never tested** | CI matrix is 3.11/3.12 | Add 3.13 to the unit job, or declare `<3.13` |
| **Two courses, one tool** | `course/` (v2) runs `docs/course/minieval.py` from v1's tree | One `course/` with `course/tools/minieval.py`; keep a redirect note at the old path because posts link to it |
| **Status tables disagree** | `CLOUD_NATIVE.md` lists crewai/langgraph/claude-sdk *local* as `not yet`; README publishes n=5 local batches | Define "recorded run" once, then fill the three local rows from the existing batch bundles |
| **Complexity concentrated in two files** | `crewai_backend/flows/main_flow.py` 1,478 LOC; `ui/web/server.py` 1,393 LOC (`_run_artifact_metrics`: 44 branches); 61 functions > 80 lines | Production-hardening Track B already owns this; the ratchets in `tests/unit/repo/ratchets.toml` are the right mechanism |
| **Hero figure embeds a dated benchmark** | `architecture_diagram.svg` carries the 2026-07-04 n=5 table | Drop the table from the SVG; the README table is the maintained copy |
| **Unpinned images** | `ollama/ollama` (compose, optional profile) | Pin a tag like the other services |
| **pytest-randomly installed, disabled by default** | `addopts = "-p no:randomly"` | Either enable it in CI (the conftest already defends against order leaks) or drop the dependency |

## Before → after

| | `main` | branch |
| --- | --- | --- |
| Diff (before this entry) | — | 282 files, +1,025 / −4,475 lines |
| Direct runtime dependencies | 38 | 21 |
| Locked packages | 223 | 201 |
| Tests collected by `uv run pytest` | collection error | 1,957 |
| Adversarial guardrail tests in CI | 0 | 36 |
| mypy `ignore_errors` budget | 13,000 LOC | 12,241 LOC |
| Image guard runtime | 39 s | 0.5 s |
| README | 419 lines | 309 lines |

## Sources

- Ruff formatter as a Black replacement, and import sorting via `ruff check --select I`: <https://docs.astral.sh/ruff/formatter/>
- uv dependency constraints and `requires-python` bounds: <https://docs.astral.sh/uv/concepts/resolution/>
- PEP 440 version comparison: <https://peps.python.org/pep-0440/>
- LiteLLM March 2026 supply-chain incident (1.82.7, 1.82.8): <https://docs.litellm.ai/blog/security-update-march-2026>
- CrewAI releases: <https://pypi.org/project/crewai/>
- LangGraph docs (moved from langchain-ai.github.io): <https://docs.langchain.com/oss/python/langgraph/overview>
- langgraph-supervisor note recommending the tool-based supervisor pattern: <https://github.com/langchain-ai/langgraph-supervisor-py>
- Claude Agent SDK overview: <https://code.claude.com/docs/en/agent-sdk/overview>
- Claude model lifecycle (Sonnet 4.6 active, not retired before 2027-02-17): <https://platform.claude.com/docs/en/about-claude/model-deprecations>
- GitHub token prefixes: <https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github#githubs-token-formats>
- AWS access key ID prefixes: <https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_identifiers.html#identifiers-unique-ids>
- OWASP LLM01 prompt injection (no fool-proof prevention; filters are one layer): <https://genai.owasp.org/llmrisk/llm01-prompt-injection/>
- CWE-377 insecure temporary file: <https://cwe.mitre.org/data/definitions/377.html>
- pytest test layout and import modes: <https://docs.pytest.org/en/stable/explanation/goodpractices.html>
- actions/checkout releases: <https://github.com/actions/checkout/releases>
- Mermaid in GitHub Markdown: <https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams>
- Husain & Shankar, error analysis: <https://hamel.dev/blog/posts/evals-faq/why-is-error-analysis-so-important-in-llm-evals-and-how-is-it-performed.html>
