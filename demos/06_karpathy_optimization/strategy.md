# Optimization Strategy

High-level hints for the AutoOptimizer agent. Try these in order —
each is a single, isolated change to test.

## Priority 1 — Database
- Replace per-request `sqlite3.connect()` calls with a connection pool
  (or a module-level connection with `check_same_thread=False`).
- Add indexes on frequently filtered columns (e.g. `created_at`, `id`).
- Use `executemany` instead of looped `execute` for batch inserts.

## Priority 2 — Serialization
- Avoid redundant `dict()` copies when building JSON responses.
- Use `orjson` instead of the stdlib `json` module for response serialization.
- Return pre-computed response dicts from the DB layer instead of ORM objects.

## Priority 3 — HTTP / Flask
- Add `Cache-Control` headers to GET endpoints that return stable data.
- Disable Flask debug mode and reload in any prod-like entry point.
- Use `flask.g` to cache per-request DB connections instead of re-opening.

## Priority 4 — Algorithm
- Replace O(n) in-memory filtering with SQL `WHERE` clauses.
- Remove unnecessary list comprehensions over large result sets.
- Use generator expressions where results are iterated only once.

## Constraints
- Do NOT change the public API contract (endpoints, request/response shapes).
- Do NOT modify test files or CI configuration.
- Do NOT introduce new dependencies without adding them to requirements.txt.
- Make ONE change per iteration. State your hypothesis before editing.
