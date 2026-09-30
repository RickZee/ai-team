.PHONY: local-smoke

BACKEND ?= langgraph

local-smoke:
	uv run python scripts/local_smoke.py --backend $(BACKEND)
