#!/usr/bin/env bash
# Run pip-audit with the same ignore list as .github/workflows/ci.yml security job.
# Transitive / pinned advisories are documented inline; bump direct deps in pyproject.toml first.
# GHSA-xf7x-x43h-rpqh: crewai pins json-repair~=0.25.2; fix is 0.60.1+ (DoS via circular $ref).
# CVE-2026-45830/31/33: chromadb Python server IDOR; no PyPI fix (affected through latest).
# litellm pinned at 1.74.9 for CrewAI/Pydantic (see pyproject.toml); proxy-admin / SSTI /
#   auth fixes need 1.83.0–1.84.0 which conflict with that pin (PYSEC-2026-347{6-9},
#   PYSEC-2026-3861, CVE-2026-1277{1,2,3,5}).
# PYSEC-2026-3819: crewai/crewai-tools SSRF in validate_url; fix is 1.15.1+ — stack stays on
#   1.6.1 until a deliberate CrewAI major bump.
set -euo pipefail
cd "$(dirname "$0")/.."

exec uv run pip-audit \
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
  --ignore-vuln GHSA-4gg8-gxpx-9rph \
  --ignore-vuln CVE-2026-48775 \
  --ignore-vuln CVE-2026-48776 \
  --ignore-vuln GHSA-xf7x-x43h-rpqh \
  --ignore-vuln CVE-2026-45830 \
  --ignore-vuln CVE-2026-45831 \
  --ignore-vuln CVE-2026-45833 \
  --ignore-vuln PYSEC-2026-3476 \
  --ignore-vuln PYSEC-2026-3477 \
  --ignore-vuln PYSEC-2026-3478 \
  --ignore-vuln PYSEC-2026-3479 \
  --ignore-vuln PYSEC-2026-3819 \
  --ignore-vuln PYSEC-2026-3861 \
  --ignore-vuln CVE-2026-12771 \
  --ignore-vuln CVE-2026-12772 \
  --ignore-vuln CVE-2026-12773 \
  --ignore-vuln CVE-2026-12795
