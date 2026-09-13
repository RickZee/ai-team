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

Recorded 2026-09-13 after Track A (Phases 0–5, 8–9 except live 9.1).
Refreshed the same day after Track B (Phases 6–7) and the Phase 3 hygiene sweep.

Commands vs the pre-Track-A parent `946f6d9`:

| Claim | Command | Value |
| --- | --- | --- |
| Python LOC `src/ai_team` + `evals` (excl. `node_modules`, `vendor`) | `git ls-tree -r --name-only <rev>` filtered `*.py`, `wc -l` | **46,704 → 46,049** (**−655**) |
| Tracked `docs/images/` blob bytes | `git cat-file -s` per path | **9,329,198 → 5,289,340** (**−4.0 MB**) |
| Tracked image files | `git ls-files docs/images/` | **34** (working-tree `du` includes untracked campaign files; ignore that) |
| Unit tests collected | `uv run pytest tests/unit --collect-only -q` | **1534** |
| Complexity (≤2-branch exempt) | AST walk / `ratchets.toml` | **55 / 4 / 14** |
| `ignore_errors` LOC | `test_type_budget.py` | **12,726** / 70 files (ratchet 13,000) |
| Docker image size | `docker image inspect --format '{{.Size}}'` after `docker build -f docker/Dockerfile` | Track A **790 MB** was Docker Desktop compressed Size (ratchet 900). GHA run 34773066923: **2.55 GB** uncompressed with `RUN chown -R` doubling. Post-`--chown` predicted **~1.45 GB**; ratchet **1800 MiB** until the next green `image_bytes=` |
| Web E2E | `pytest tests/e2e/web -m web_e2e` | **27 passed, 1 skipped** |
| `.archive/` tracked files | `git ls-files .archive/` | **21** (kept; see `.archive/README.md`) |

The Phase 1 guess was roughly −1,500 to −2,000 LOC and −7 MB of images. Net Python
is smaller because Track B added shims and Phase 7 extracted modules rather than
deleting them. Image bytes dropped ~4 MB, not 7: publication allowlisted assets
were kept. `.archive/` stayed.

Package LOC after the CrewAI move (shims at top level; logic under `backends/`):
agents 129; backends 13923; config 1701; core 1653; crews 56; flows 54;
guardrails 2336; harness 2242; memory 781; models 479; reports 389; tasks 49;
tools 5926; ui 2754; root py 1098; **no `utils/`**.

## Guard suite CI time

Local `pytest tests/unit/repo` is a few seconds inside the unit run. Target < 30 s
added (R20.5) holds locally; GitHub Actions wall-clock is recorded on the first
green `lint` job after a PR into `main`/`develop`. Feature-branch pushes do not
trigger `.github/workflows/ci.yml`.
