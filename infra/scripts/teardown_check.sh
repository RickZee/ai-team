#!/usr/bin/env bash
# List billable resources tagged project=ai-team. With nothing deployed, print 0.
set -euo pipefail

aws_count=0
azure_count=0

if command -v aws >/dev/null 2>&1 && aws sts get-caller-identity >/dev/null 2>&1; then
  aws_count="$(aws resourcegroupstaggingapi get-resources \
    --tag-filters Key=project,Values=ai-team \
    --query 'length(ResourceTagMappingList)' \
    --output text 2>/dev/null || echo 0)"
fi

if command -v az >/dev/null 2>&1 && az account show >/dev/null 2>&1; then
  azure_count="$(az resource list --tag project=ai-team --query 'length(@)' -o tsv 2>/dev/null || echo 0)"
fi

echo "aws: ${aws_count} billable resources"
echo "azure: ${azure_count} billable resources"
