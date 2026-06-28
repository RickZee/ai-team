#!/usr/bin/env bash
# Run pip-audit with the same ignore list as .github/workflows/ci.yml security job.
# Transitive / pinned advisories are documented inline; bump direct deps in pyproject.toml first.
set -euo pipefail
cd "$(dirname "$0")/.."

exec poetry run pip-audit \
  --ignore-vuln CVE-2025-69872 \
  --ignore-vuln PYSEC-2022-42969 \
  --ignore-vuln PYSEC-2024-278 \
  --ignore-vuln PYSEC-2025-183 \
  --ignore-vuln CVE-2026-35029 \
  --ignore-vuln CVE-2026-35030 \
  --ignore-vuln GHSA-69x8-hrgq-fjj8 \
  --ignore-vuln CVE-2026-42271 \
  --ignore-vuln GHSA-pjjw-68hj-v9mw \
  --ignore-vuln PYSEC-2026-161 \
  --ignore-vuln CVE-2026-45829 \
  --ignore-vuln CVE-2026-49468 \
  --ignore-vuln CVE-2026-47102 \
  --ignore-vuln CVE-2026-47101 \
  --ignore-vuln GHSA-6v7p-g79w-8964 \
  --ignore-vuln CVE-2026-48818 \
  --ignore-vuln CVE-2026-48817 \
  --ignore-vuln CVE-2026-54283 \
  --ignore-vuln CVE-2026-54282 \
  --ignore-vuln GHSA-4gg8-gxpx-9rph
