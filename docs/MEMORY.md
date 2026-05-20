# Memory

AI-Team uses memory for three related purposes: short-term context within a project,
long-term learning across runs, and role-scoped retrieval of project knowledge.

## Stores

| Store | Backing system | Purpose |
| ----- | -------------- | ------- |
| Short-term | ChromaDB | Per-project semantic search over task outputs and handoff context. |
| Long-term | SQLite | Cross-run conversation history, metrics, failure records, and learned patterns. |
| Entity | SQLite | Project entities and relationships such as files, APIs, services, and dependencies. |

The shared entry point is `src/ai_team/memory/memory_config.py`, which exposes store
classes and a `MemoryManager` interface.

## Embeddings

Short-term memory uses ChromaDB with an OpenRouter-compatible embedding function. The
default embedding model is configured through `OPENROUTER_EMBEDDING_MODEL`; the current
default is documented in `README.md`.

If old ChromaDB data was created with a different embedding provider, remove the old
collection data before running again. See `docs/GETTING_STARTED.md` for the common
`openai vs persisted: ollama` troubleshooting path.

## Lessons and self-improvement

Failure-driven learning is implemented in `src/ai_team/memory/lessons.py`:

1. failed runs persist structured failure records into long-term memory
2. repeated patterns can be promoted into lessons
3. lessons are loaded by role and injected into future prompts

The current maturity and remaining automation gaps are documented in
`docs/SELF_IMPROVEMENT_AUDIT.md`.

## RAG sources

Static knowledge lives under `src/ai_team/knowledge/` and is chunked for retrieval by
the RAG pipeline. Markdown is split by section heading; code and plain text use fixed
windows. The ingestion utilities live in `src/ai_team/rag/`.
