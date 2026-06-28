#!/usr/bin/env bash
# Cursor beforeShellExecution hook: block git push when pre-push checks fail.
set -euo pipefail

input=$(cat)
command=$(echo "$input" | python3 -c "import json,sys; print(json.load(sys.stdin).get('command',''))")

if [[ ! "$command" =~ git[[:space:]]+push ]]; then
  echo '{"permission": "allow"}'
  exit 0
fi

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [[ -z "$repo_root" || ! -f "$repo_root/scripts/pre_push_check.sh" ]]; then
  echo '{"permission": "allow"}'
  exit 0
fi

if ! (cd "$repo_root" && ./scripts/pre_push_check.sh); then
  echo '{
    "permission": "deny",
    "user_message": "Pre-push checks failed (ruff / mypy / pip-audit). Run ./scripts/pre_push_check.sh and fix errors before pushing.",
    "agent_message": "git push blocked: ./scripts/pre_push_check.sh failed. Fix lint or security issues first."
  }'
  exit 0
fi

echo '{"permission": "allow"}'
exit 0
