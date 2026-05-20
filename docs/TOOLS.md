# Tools

AI-Team tools are the controlled interface between agents and the workspace. They
wrap file, code, git, test, and retrieval operations with validation, structured
inputs, audit logging, and guardrails where needed.

## Tool categories

- **File tools** (`src/ai_team/tools/file_tools.py`): secure read, write, list, create,
  and delete operations scoped to allowed workspace/output roots.
- **Code tools** (`src/ai_team/tools/code_tools.py`): sandboxed Python execution,
  linting, formatting, and constrained shell execution.
- **Git tools** (`src/ai_team/tools/git_tools.py`): local repository status, diff, log,
  branch, and commit operations with protected-branch safeguards.
- **Test tools** (`src/ai_team/tools/test_tools.py`): pytest, coverage, single-test
  execution, lint checks, and test quality helpers.
- **Role tools** (`src/ai_team/tools/product_owner.py`,
  `src/ai_team/tools/architect.py`): structured requirements and architecture helpers.
- **RAG tools** (`src/ai_team/tools/rag_search.py`): retrieval over indexed project and
  knowledge sources.

## Safety model

Tools should validate inputs before doing work, reject unsafe paths or commands, use
Pydantic models for structured input/output, and emit audit logs for significant
operations. File-writing and execution tools are expected to run security and quality
checks before exposing results back to agents.

## Adding a tool

1. Create the tool in `src/ai_team/tools/`.
2. Validate paths, commands, and structured inputs up front.
3. Add audit logging for all operations with side effects.
4. Define Pydantic models for inputs and outputs when data is structured.
5. Add happy-path and adversarial tests.
6. Register the tool with the agent or backend that needs it.
