# budget

<!-- BEGIN_TF_DOCS -->
Resource group plus a monthly consumption budget. Alerts at 50% and 100% of
`monthly_budget_usd` (default 25). Tags come from the shared `locals` map.
<!-- END_TF_DOCS -->

## Teardown

From `envs/dev`: `terraform destroy`. Then `infra/scripts/teardown_check.sh`.
