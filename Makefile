.PHONY: local-smoke otel-up otel-down otel-backfill test-otel-integration

BACKEND ?= langgraph
COMPOSE = docker compose -f docker/docker-compose.yml
OTEL_ENDPOINT ?= http://localhost:4318

local-smoke:
	uv run python scripts/local_smoke.py --backend $(BACKEND)

# Local trace viewing: Aspire http://localhost:18888 (live), Phoenix http://localhost:6006 (history).
# Named so `up` leaves the unprofiled `app` service alone (it refuses to start without a token).
OTEL_SERVICES = otel-collector aspire-dashboard phoenix

otel-up:
	mkdir -p output/otel output/phoenix
	$(COMPOSE) --profile observability up -d $(OTEL_SERVICES)

otel-down:
	$(COMPOSE) --profile observability rm -sf $(OTEL_SERVICES)

# Send every run in output/runs/ whose last export wasn't posted.
otel-backfill:
	uv run python -m evals.cli trace export-otel --all --endpoint $(OTEL_ENDPOINT) --if-changed

# Needs Docker. Uses its own ports and temp folders; never touches output/.
test-otel-integration:
	AI_TEAM_DOCKER_TESTS=1 uv run pytest tests/integration/test_otel_local_stack.py -m integration -v
