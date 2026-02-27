#!/usr/bin/env bash
# Run the demo and monitor output; stop on first runtime error.
# Usage: ./scripts/monitor_demo.sh [demo_path]
# Example: ./scripts/monitor_demo.sh demos/01_hello_world

DEMO_PATH="${1:-demos/01_hello_world}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="/tmp/demo_monitor_$$.txt"
cd "$REPO_ROOT"

# Error patterns: runtime errors only (not task text like "400 for bad input")
# Include OpenRouter 402 (credits/max_tokens) and LLM Failed so we stop on API limit errors
STOP_PATTERN="ERROR:root:|ValueError: |Traceback \(most recent call last\)|Embedding function conflict: new: openai vs persisted|OpenrouterException.*402|requires more credits, or fewer max_tokens"

echo "Running demo: $DEMO_PATH (streaming output; will stop on first error)."
( poetry run python scripts/run_demo.py "$DEMO_PATH" --skip-estimate 2>&1 | tee "$LOG" ) &
PIPELINE_PID=$!
trap 'kill $PIPELINE_PID 2>/dev/null; rm -f "$LOG"; exit 130' INT TERM

tail -n 0 -f "$LOG" 2>/dev/null | while read -r line; do
  printf '%s\n' "$line"
  if echo "$line" | grep -qE "$STOP_PATTERN"; then
    echo "" >&2
    echo ">>> RUNTIME ERROR DETECTED - stopping demo." >&2
    kill $PIPELINE_PID 2>/dev/null
    rm -f "$LOG"
    exit 1
  fi
done
EXIT=$?
wait $PIPELINE_PID 2>/dev/null || true
FINAL=$?
rm -f "$LOG"
# If we stopped on error, while loop exited 1; else use demo's exit code
[ "$EXIT" = "1" ] && exit 1
exit "${FINAL:-0}"
