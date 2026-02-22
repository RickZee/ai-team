#!/usr/bin/env bash
# Watch pytest run from Cursor terminal file. Usage: ./scripts/watch_test_run.sh [terminal_file]
# Default terminal file is the one used for the full test run with memory limit.

# Don't use set -e: grep exits 1 when no match and we use it in conditionals
TERM_FILE="${1:-/Users/rickzakharov/.cursor/projects/Users-rickzakharov-dev-github-ai-team/terminals/986471.txt}"
INTERVAL="${2:-30}"

# Safe grep for command substitution (no exit 1 when no match)
grep_no_fail() { grep "$@" 2>/dev/null || true; }

while true; do
  clear
  echo "════════════════════════════════════════════════════════════════"
  echo "  Test run status  $(date '+%Y-%m-%d %H:%M:%S')"
  echo "════════════════════════════════════════════════════════════════"
  echo ""

  if [[ ! -f "$TERM_FILE" ]]; then
    echo "  Terminal file not found: $TERM_FILE"
    sleep "$INTERVAL"
    continue
  fi

  # Running time (from metadata)
  SECS=$(grep_no_fail -E '^running_for_seconds:' "$TERM_FILE" | sed 's/running_for_seconds:[^0-9]*//' | tr -d ' ')
  if [[ -n "$SECS" && "$SECS" =~ ^[0-9]+$ ]]; then
    TOTAL_MIN=$((SECS / 60))
    HR=$((TOTAL_MIN / 60))
    MIN=$((TOTAL_MIN % 60))
    S=$((SECS % 60))
    if [[ $HR -gt 0 ]]; then
      echo "  Running: ${HR}h ${MIN}m ${S}s"
    else
      echo "  Running: ${MIN}m ${S}s"
    fi
  else
    echo "  Running: (unknown)"
  fi

  # Pass/fail counts from pytest output
  PASSED=$(grep_no_fail -cE 'PASSED \[' "$TERM_FILE")
  FAILED=$(grep_no_fail -cE 'FAILED \[' "$TERM_FILE")
  SKIPPED=$(grep_no_fail -cE 'SKIPPED \[' "$TERM_FILE")
  echo "  Passed:  ${PASSED:-0}   Failed: ${FAILED:-0}   Skipped: ${SKIPPED:-0}"
  echo ""

  # Current or last test line (used below for "what the team is doing")
  CURRENT=$(grep_no_fail -E '^tests/' "$TERM_FILE" | tail -1)

  # What the team is doing (flow/structlog events, or inferred from test name)
  echo "  --- What the team is doing ---"
  TEAM_LINES=$(grep_no_fail -E 'intake_started|intake_validation|planning_started|planning_complete|planning_failed|development_started|development_complete|development_failed|testing_started|testing_complete|testing_failed|deployment_started|deployment_complete|deployment_failed|project_complete|retrying_planning|retrying_development' "$TERM_FILE" | tail -8)
  if [[ -n "$TEAM_LINES" ]]; then
    echo "$TEAM_LINES" | while read -r line; do
      short=$(echo "$line" | sed 's/^[[:space:]]*//' | head -c 76)
      [[ -n "$short" ]] && echo "    $short"
    done
  else
    # Fallback: JSON event/key or phase/agent mentions
    TEAM_LINES=$(grep_no_fail -E '"event"|"phase"|event=|phase=|Manager|Architect|Product Owner|Backend|Frontend|DevOps|QA Engineer|Planning|Development|Testing|Deployment' "$TERM_FILE" | tail -5)
    if [[ -n "$TEAM_LINES" ]]; then
      echo "$TEAM_LINES" | while read -r line; do
        short=$(echo "$line" | sed 's/^[[:space:]]*//' | head -c 76)
        [[ -n "$short" ]] && echo "    $short"
      done
    else
      # No flow events (pytest captures stdout). Infer from current test name.
      if echo "$CURRENT" | grep -q 'e2e.*hello_world.*flask'; then
        echo "    E2E full flow: Intake → Planning (PO + Architect) → Development"
        echo "    (Backend/Frontend) → Testing (QA) → Deployment (Flask API)."
        echo "    Pytest captures logs; run with -s to see live flow events."
      elif echo "$CURRENT" | grep -q 'e2e/'; then
        echo "    E2E test: full AI team flow (intake → planning → dev → test → deploy)."
        echo "    Run pytest with -s to see live flow events in this watcher."
      else
        echo "    (no flow events in output yet — crew may be running)"
      fi
    fi
  fi
  echo ""

  # Current or last test line (display)
  if [[ -n "$CURRENT" ]]; then
    if echo "$CURRENT" | grep -qE 'PASSED|FAILED|SKIPPED'; then
      echo "  Last completed: $CURRENT"
    else
      echo "  Current test:   $CURRENT"
    fi
  fi

  # Session summary if present (run finished)
  if grep -q 'passed.*failed.*warning' "$TERM_FILE" 2>/dev/null; then
    echo ""
    echo "  --- Session complete ---"
    grep_no_fail -E 'passed|failed|error' "$TERM_FILE" | tail -3
  fi

  # Memory limit message if run was stopped
  if grep -q 'Memory limit exceeded' "$TERM_FILE" 2>/dev/null; then
    echo ""
    grep_no_fail 'Memory limit exceeded' "$TERM_FILE"
  fi

  echo ""
  echo "════════════════════════════════════════════════════════════════"
  echo "  Refreshing in ${INTERVAL}s (Ctrl+C to stop)"
  echo "════════════════════════════════════════════════════════════════"
  sleep "$INTERVAL"
done
