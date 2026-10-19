# 2026-10-18 — AWS backend plan, two cloud specs, and one OTel shape for every backend

**The AWS plan was the right destination reached in the wrong order: it changed the model
provider, the framework and the host at once. It now climbs one variable at a time, a second AWS
spec covers the managed-loop option, and every backend can be exported to OpenTelemetry in the
same shape and read back without loss.** The Docker half ran later on the Mac and found three
faults the unit tests couldn't, one of which silently dropped every span bound for Aspire (§9).

**Author:** Rick Zakharov (with agent assist)
**Preceded by:** [2026-10-07 pip-audit floors](2026-10-07-pip-audit-floors.md).
**Branch:** `docs/aws-spec-revisions`, from `4bb9f59`. Four commits: `718843e`, `5a603a8`,
`0801115`, `8c499db`. Nothing merged to `main`.

---

## 1. What was found

| Finding | Verified how | Consequence |
| --- | --- | --- |
| Every Terraform module pins `hashicorp/aws` 5.100.0; the AgentCore resources are in the 6.x line. `validate` passes only because the modules are empty | `infra/terraform/aws/modules/*/versions.tf`; CDKTF `provider-aws` 21.x carries `bedrockagentcore_*` | `aws-strands-agentcore` 0.1 now has to move the pin and prove it with `providers schema` |
| The lessons store is SQLite on local disk; an AgentCore session's disk is discarded | `memory/lessons.py`, AgentCore Runtime docs | Cloud run *n* could not change run *n+1*. New R5.4 / task 4.0: S3 round trip with a conditional write |
| The July comparisons ran LangGraph and CrewAI on DeepSeek and the Claude SDK on Claude | `docs/COMPARISON_RESULTS.md`, 2026-07-01 tables | Framework and model were already confounded. New Step 0 (task 2.0): existing backends on Bedrock, same model ids as Strands |
| Claude on Bedrock is called through `us.` inference profiles; a model-ARN-only policy is refused | AWS IAM model for inference profiles | Task 3.2 pairs profile and foundation-model ARNs; a `terraform test` asserts it |
| The "±20% against the Bedrock console" cost check can't close the same day | Billing lags about 24 h | Task 2.2 checks against CloudWatch `AWS/Bedrock` token metrics |
| CLI runs of LangGraph and CrewAI never call `ResultsBundle.finalize()` | `grep -rn "\.finalize(" src` → web server, Claude SDK backend, thin slice only; `cli_run._finish_run` doesn't | No `completed_at`, no final cost row, no receipt, and `apply_lessons_at_finish` never runs on that path. Filed as `eval-methodology-alignment` R1.9 / task 1.7 |
| All 13 spec headers said "Draft for implementation", including two at 100% | Header grep against checkbox counts | Generated register (§2) |
| The AgentCore Harness (GA June 2026) has client-side **inline-function** tools: the loop stops and hands each tool call back | Harness API write-ups (classmethod, hidekazu-konishi), Terraform `aws_bedrockagentcore_harness` | A config-only AWS agent can keep ToolBus in-process; that made a fair spec possible |
| No real run in `output/runs/` has a single `llm_call` span; most tool spans have no `agent_role`; audit rows carry no call id | Payload census, newest run per backend (`otel-observability` design §6) | Model calls appear only once per-call cost rows exist (methodology R1.6). Tool pairs match on tool, role, phase, run id |
| `make_trace_id` adds a random suffix on every build | `evals/trace/builder.py::make_trace_id` | An export keyed on it would be a new OTel trace every time. Ids now come from the run id |
| The spec said `test_import_direction.py` kept `src/` from importing `evals/`. It didn't | Read the test | Added `test_src_does_not_import_evals` |
| Phoenix ≥ 15.10 converts `gen_ai.*` to OpenInference at ingest | Phoenix release notes, 2026-05-15 | OpenInference names are still written; they take precedence |
| `import-otel` ignored OTLP's list-form attributes and multi-line request files | Exporting a real run and reading it back | Real Strands / Agent Framework spans would have mapped to `other`. Fixed in `8c499db` |

## 2. What changed

| Commit | Decision |
| --- | --- |
| `718843e` | `aws-strands-agentcore` revised: Step 0 (2.0), lessons in the cloud (4.0), provider pin, inference-profile IAM, CloudWatch cost check, per-commit artifact sync, explicit session end, Transaction Search, S3-native state locking, optional Code Interpreter test. New spec `aws-agentcore-harness` (21 tasks) and `docs/agentcore-harness/USER_GUIDE.md`, written ahead with a status banner. Spec statuses use four words (Draft, In progress, Done, Replaced by); `scripts/spec_index.py` generates the register in `.kiro/specs/README.md`; `tests/unit/test_spec_index.py` fails when it drifts. Task counts are left out of the table so ticking a box doesn't make it stale |
| `5a603a8` | New spec `otel-observability`, revised once after a review against the source. `eval-methodology-alignment` gains R1.9 / 1.7 (every run path finalizes). `docs/AWS_BACKEND_ARCHITECTURE.md` (six architectures, deployment options, cost model; all diagrams Mermaid). `docs/observability/README.md` (local, AWS, Azure) |
| `0801115` | `otel-observability` design §0: every component, what it is, why it won, what lost (Phoenix vs Jaeger, Tempo, Langfuse, SigNoz; collector vs direct export; OTLP JSON vs protobuf). Glossary entries |
| `8c499db` | OTel Phase 1 built: `evals/trace/otel_export.py`, `otel_run.py`, `trace export-otel`, lossless re-import in `otel_import.py`. Compose: Phoenix 20.5.0, every observability port on `127.0.0.1`, collector `memory_limiter` + `batch` + `health_check`, native-backend tags. `make otel-up / otel-down / otel-backfill / test-otel-integration`. `harness/otel_tags.py` (dormant until the Strands and Agent Framework tasks call it). 6 of 14 OTel boxes ticked |

### Specs touched

| Spec | State after today |
| --- | --- |
| `aws-strands-agentcore` | Draft; revised (31 tasks) |
| `aws-agentcore-harness` | Draft; new (21 tasks) |
| `otel-observability` | In progress; 9 of 14 ticked (0.1, 0.2, 1.1–1.4, 2.1–2.3) |
| `eval-methodology-alignment` | + R1.9, task 1.7 |
| `azure-agent-framework` | + a line in 1.6 to call the run-id helper |

## 3. The thing worth naming on its own

A cloud migration is three treatments in one: model provider, framework and host. The published
comparison had already mixed the first two before AWS entered: two backends on DeepSeek, one on
Claude. The plan would have added the third. The order is now Step 0 (same backends, Bedrock
model), Step 1 (Strands on the laptop), Step 2 (same image on AgentCore), Step 3 (one AWS service
per change). Each result has the step before it as its comparison. Step 0 is the cheapest task in
the plan (about a day, under $5) and the one that makes the rest readable.

## 4. Verification

```bash
uv run ruff check . && uv run ruff format --check .        # clean, 522 files
uv run mypy src/ evals/                                    # 267 files, no issues
uv run pytest tests/unit/evals/test_otel_export.py tests/unit/evals/test_otel_import_roundtrip.py \
  tests/unit/evals/test_otel_export_cli.py tests/unit/evals/test_otel_import.py \
  tests/unit/harness/test_otel_tags.py tests/unit/repo tests/conformance \
  tests/integration/test_otel_local_stack.py tests/unit/test_spec_index.py -q
# 152 passed, 1 skipped (the Docker integration module, by design without AI_TEAM_DOCKER_TESTS=1)

# A real run, copied with its workspace, exported twice and read back:
uv run python -m evals.cli trace export-otel output/runs/2026-09-18_224914_write-a-single-python-module_01
uv run python -m evals.cli trace import-otel output/runs/2026-09-18_224914_write-a-single-python-module_01/logs/otel.harness.jsonl
# 27 ai-team spans → 19 OTel spans (9 merged tool pairs, 8 QA, 1 spend, 1 root);
# re-import counts identical (tool_use 9, tool_result 9, qa_verdict 8, spend_event 1); two exports byte-identical
```

Checked in a Linux VM against the repo, with its own Python environment (the Mac `.venv` doesn't
run there). The rest of `tests/unit` was not run in full: the VM's 180-second call limit cut the
run in `tests/unit/tools/test_smoke_tools.py`, whose failures there come from the VM's Python
lacking Flask, not from this change.

## 5. Key files

```
.kiro/specs/
  README.md                          # generated register, 14 specs
  aws-strands-agentcore/             # revised
  aws-agentcore-harness/             # new
  otel-observability/                # new; design §0 components, §6 census, §8 auto-export (Phase 4)
  eval-methodology-alignment/        # + R1.9, task 1.7
docs/
  AWS_BACKEND_ARCHITECTURE.md        # architectures A–F, deployment options, cost model
  agentcore-harness/USER_GUIDE.md    # written ahead
  observability/README.md            # local, AWS, Azure (unchecked sections marked)
evals/trace/
  otel_export.py                     # Trace → OTLP JSON, both naming schemes, no SDK
  otel_run.py                        # export a run folder, POST, otel.export.json, --all
  otel_import.py                     # lossless for our exports; OTLP list attributes; JSONL requests
src/ai_team/harness/otel_tags.py     # run-id helper for native-OTel backends (dormant)
docker/docker-compose.yml, otel-collector.yaml, VERSIONS.md
scripts/spec_index.py
output/otel-check.sh                 # one-off Docker check (gitignored), see §6
```

## 6. Not done

| Item | Why | What closes it |
| --- | --- | --- |
| ~~OTel 0.2, 2.1, 2.3~~ | Closed later the same day on the Mac; see §9 | — |
| OTel 2.4 smoke run per backend + screenshot; 3.1–3.3 guide walk-throughs | Need live runs and, for 3.2/3.3, cloud runs | After 2.1 |
| OTel 4.1 auto-export | Blocked on methodology 1.7 (CLI runs don't finalize) | 1.7 first |
| Every task in `aws-strands-agentcore`, `aws-agentcore-harness` | Specs only today | Start at Step 0 (strands 2.0) and spike 0.1 |
| Foundation 0.5, 4.2, 6.2, 6.3 | Not in scope | Before the first cloud spend |
| Phoenix licence (Elastic License 2.0) | Read from Arize's licence page, not the LICENSE file | Task 0.2 re-check |
| `.mypy_cache` | The VM's mypy wrote into it and a later run crashed on it | `rm -rf .mypy_cache` if mypy errors on the Mac |

## 7. What's next

- [x] Run `bash output/otel-check.sh`; tick OTel 0.2, 2.1, 2.3 from the log (§9)
- [ ] `eval-methodology-alignment` 1.7: CLI runs finalize (also closes the lessons gap on that path)
- [ ] `aws-strands-agentcore` 2.0 (Step 0) and 0.1 (spike), then 0.2 account prep
- [ ] OTel 2.4: one cheap run per backend, `make otel-backfill`, screenshot
- [ ] Merge `docs/aws-spec-revisions` to `main`

## 8. Design note

Two decisions today have the same shape. The OTel work exports ai-team's own record rather than
instrumenting five frameworks, because five instrumentations would compare instrumentation
libraries. The AWS plan changes one variable per step, because three changes at once make any
result unattributable. Both choose the measurement you can hold constant over the one that
looks more native. A framework's own telemetry and a cloud's own console are worth having, as a
second source to check against, never as the instrument.

## 9. Addendum: the Docker half, run on the Mac

`bash output/otel-check.sh` with Docker 29.8.2. OTel 0.2, 2.1 and 2.3 ticked: 9 of 14.

| Check | Result |
| --- | --- |
| Phoenix 20.5.0 pulled | Digest in `docker/VERSIONS.md` |
| Ports | 4317, 4318, 6006, 13133, 18888 on `127.0.0.1` only (`lsof`) |
| Real run (19 spans) sent | In `output/otel/traces.jsonl`, Phoenix and Aspire |
| Same run sent again | Phoenix still 19: re-sent ids replace, not duplicate |
| Phoenix restarted, then recreated | Still 19 |
| `make test-otel-integration` | 2 passed, 33 s; no containers left |

The script's first pass looked green and wasn't. Three faults, all fixed:

| Fault | Seen as | Fix |
| --- | --- | --- |
| Aspire's OTLP/HTTP endpoint can't read gzip, the collector's default | Aspire empty; collector log "Exporting failed. Dropping data", HTTP 500, all 19 spans | `compression: none` on `otlphttp/aspire`; repo test |
| Aspire UI wanted a browser token | `302 /login` | `DASHBOARD__FRONTEND__AUTHMODE: Unsecured` (port is localhost-only, like Phoenix); repo test |
| `make otel-up` (and the integration test) also started the unprofiled `app` | `docker-app-1` restarting: "Refusing to bind '0.0.0.0' without AI_TEAM_WEB_TOKEN"; integration test 216 s building it | Name the three services in `otel-up`, `otel-down` and the test; repo test |

The integration test passed while Aspire dropped every span, because it only asked Phoenix and
the file. It now fails on any dropped export in the collector log; putting gzip back made it
fail, so the guard works. The general point: a fan-out collector reports one viewer's refusal
only in its own log, so a test that reads one viewer proves nothing about the others.
