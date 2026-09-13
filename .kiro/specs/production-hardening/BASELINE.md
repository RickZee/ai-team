# Production-hardening baseline

Recorded 2026-09-13 before Track A. Every number is reproduced by the command
in the same row. Docker image size was not built at baseline (no local daemon
requirement for this record); the ratchet is set when task 5.3 first builds.

## Commands and values

| Claim | Command | Value |
| --- | --- | --- |
| LOC per top-level package | `find src/ai_team/$pkg -name '*.py' ! -path '*/node_modules/*' \| xargs wc -l` | agents 1327; backends 6551; config 1582; core 1516; crews 1388; flows 2986; guardrails 2335; harness 2159; knowledge (md, not py); memory 781; models 939; reports 389; tasks 1071; tools 5887; ui 2442; utils 1100 |
| Orphan modules | `wc -l` on the five files | lessons_loop 161; session_loop 315; verifiers 25; qa_verdicts 75; ladder_report 228; **804 total** |
| Uncollected tests | `wc -l evals/backends/test_*.py evals/test_backend_comparison.py` | 175+169+191+273 = **808** |
| `ignore_errors` module patterns | parse `pyproject.toml` `[[tool.mypy.overrides]]` with `ignore_errors` | **18** patterns (spec intro said 16; vendor + fixtures globs included) |
| Complexity (src/*.py excl. frontend/node_modules) | AST walk | functions >80 lines: **42**; >150: **5**; >8 params: **14** (spec intro 63/8/17 counted evals + more) |
| `docs/**/*.md` | `find docs -name '*.md' \| wc -l` | **48** (spec intro 42; journal/campaign/showcase grew) |
| Tracked images | `git ls-files docs/images/` | **33** files, `du -sh docs/images` = **9.0M**; 20 unreferenced |
| Tracked `.archive/` | `git ls-files .archive/` | **21** files |
| `evals/golden/.validation_log.jsonl` | `wc -c` | **0** bytes, tracked |
| Unit tests collected | `uv run pytest tests/unit --collect-only -q` | **1483** |
| Docker image size | not measured (no build at baseline) | set at task 5.3 |

## After-state

Recorded 2026-09-13 after Track A (Phases 0–5, 8–9 except live 9.1; Track B deferred).

| Claim | Value |
| --- | --- |
| Unit tests | **1518** passed (`uv run pytest tests/unit`) |
| Frontend vitest | **127** passed |
| `ignore_errors` LOC | **12,726** across 70 files (ratchet 13,000) |
| Complexity (≤2-branch exempt) | **58 / 7 / 15** (80-line / 150-line / 8-param) |
| `.archive/` tracked files | **21** (kept; see `.archive/README.md`) |
| Docker image size | **790 MB** (`docker build -f docker/Dockerfile -t ai-team:ci`); ratchet **900 MB** |
| Web E2E | **27 passed, 1 skipped** (`pytest tests/e2e/web -m web_e2e`) |
| Guard suite (`tests/unit/repo`) | included in unit run; lint job also runs it |

LOC delta vs before: `.archive/` **kept** (21 tracked files + README); unreferenced compare screenshots deleted; Poetry tables removed; hatchling wheel builds `ai_team` (not `src.ai_team`).

## Guard suite CI time

Local `pytest tests/unit/repo` is a few seconds inside the 68s unit run. Target < 30 s added (R20.5) holds locally; GitHub Actions wall-clock is recorded on the first green `lint` job after merge.
