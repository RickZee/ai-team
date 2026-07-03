#!/usr/bin/env bash
# quickstart.sh — clone-and-run entrypoint for ai-team
# Runs smoke-test across all available backends and prints a comparison table.
#
# Usage:
#   ./scripts/quickstart.sh                  # all available backends
#   ./scripts/quickstart.sh --no-judge       # skip LLM judge (faster, no API cost)
#   ./scripts/quickstart.sh --backend crewai # single backend

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

# ── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}!${NC} $*"; }
fail() { echo -e "${RED}✗${NC} $*"; exit 1; }

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AI-Team Quickstart — multi-backend smoke test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── check .env ────────────────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
  warn ".env not found — copying from .env.example"
  cp .env.example .env
  fail "Edit .env and add your API keys, then re-run this script."
fi

# ── check required keys ───────────────────────────────────────────────────────
source .env 2>/dev/null || true

MISSING_KEYS=()
[[ -z "${OPENROUTER_API_KEY:-}" ]] && MISSING_KEYS+=("OPENROUTER_API_KEY (for crewai + langgraph)")
[[ -z "${ANTHROPIC_API_KEY:-}" ]] && warn "ANTHROPIC_API_KEY not set — claude-agent-sdk backend will be skipped"

if [[ ${#MISSING_KEYS[@]} -gt 0 ]]; then
  fail "Missing required keys in .env:\n  ${MISSING_KEYS[*]}"
fi

# ── check uv ──────────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
  fail "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# ── install deps if needed ────────────────────────────────────────────────────
if [[ ! -d .venv ]]; then
  echo "Installing dependencies (first run)..."
  uv sync --quiet
fi
ok "Dependencies ready"

# Skip post-run self-improvement reports — saves a few minutes per run
export AI_TEAM_SKIP_POST_RUN=1

# ── parse args ────────────────────────────────────────────────────────────────
EXTRA_ARGS=("$@")

# ── determine backends ────────────────────────────────────────────────────────
if [[ " ${EXTRA_ARGS[*]} " =~ " --backend " ]]; then
  # user specified a single backend; pass through
  BACKEND_MODE="single"
else
  BACKEND_MODE="compare"
fi

echo ""
echo "Scenario: smoke-test (write add(a,b) + one pytest)"
echo "Mode: ${BACKEND_MODE}"
echo ""

# ── run ───────────────────────────────────────────────────────────────────────
if [[ "$BACKEND_MODE" == "compare" ]]; then
  if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    warn "Skipping claude-agent-sdk (no ANTHROPIC_API_KEY)"
    warn "To include it, add ANTHROPIC_API_KEY to .env"
    echo ""
    # Run only crewai + langgraph by running sequentially (compare spawns all 3)
    uv run python -m evals.run_evals \
      --backend crewai \
      --scenario smoke-test \
      --no-judge \
      "${EXTRA_ARGS[@]}" &
    PID_CREWAI=$!
    uv run python -m evals.run_evals \
      --backend langgraph \
      --scenario smoke-test \
      --no-judge \
      "${EXTRA_ARGS[@]}" &
    PID_LANGGRAPH=$!
    wait $PID_CREWAI $PID_LANGGRAPH
  else
    uv run python -m evals.run_evals \
      --compare \
      --scenario smoke-test \
      --no-judge \
      "${EXTRA_ARGS[@]}"
  fi
else
  uv run python -m evals.run_evals \
    --scenario smoke-test \
    --no-judge \
    "${EXTRA_ARGS[@]}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Done. Results in evals/results/"
echo "  To run with LLM judge:  remove --no-judge above"
echo "  To try one backend:     --backend crewai|langgraph|claude-agent-sdk"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
