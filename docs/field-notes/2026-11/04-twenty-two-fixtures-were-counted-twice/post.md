# Twenty-two fixtures were counted twice

**Status:** Ready after this branch is on `main`.
**Proof:** `evals/fixtures/traces/`

---

The eval gate compared fixtures to the outcome in the filename, and one of its rules said no trace should be loaded twice. The first time that rule ran, it found 22. Each of those traces existed under two names, `CHK-…__pass.json` and `CHK-…__pass__fixture.json`, byte for byte the same file, same id. Every rate the suite printed had counted them twice.

They stayed on disk. Deleting committed fixtures was left as a decision. The files were identical, so the decision is which name to keep, and the extra name is the one that does not match the set the checks already use.

The 22 `__fixture.json` copies are gone. 72 trace ids, 72 files. A test fails if any id shows up twice.

Takeaway: when a trace id is the unit of a rate, one id gets one file.

The corpus:
evals/fixtures/traces/

How many of your golden files are the same example under two names?

#AgenticAI #AIEngineering #LLMOps

---

**Receipts**
- 94 files, 72 distinct trace ids, 22 duplicate ids, counted 2026-09-30. Each deleted file matched its sibling by sha256.
- Kept the name without the extra `__fixture` suffix. Trace ids inside the files are unchanged.
- `tests/unit/evals/test_fixture_contract.py::test_fixture_files_have_unique_trace_ids`.
