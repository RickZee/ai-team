.PHONY: quickstart eval eval-judge lint test

quickstart:  ## Run smoke-test on all available backends (clone-and-run entry point)
	@bash scripts/quickstart.sh

eval:  ## Run smoke-test eval, no LLM judge (fast)
	uv run python -m evals.run_evals --compare --scenario smoke-test --no-judge

eval-judge:  ## Run smoke-test eval with LLM judge (requires ANTHROPIC_API_KEY)
	uv run python -m evals.run_evals --compare --scenario smoke-test

lint:  ## Ruff + mypy
	uv run ruff check src/ evals/
	uv run mypy src/ai_team --ignore-missing-imports

test:  ## Unit tests
	uv run pytest tests/unit/ -q
