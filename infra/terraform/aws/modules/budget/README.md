# budget

<!-- BEGIN_TF_DOCS -->
Monthly cost budget. Alerts at 50% and 100% of `monthly_budget_usd` (default 25).
Tags are the AWS provider default tags in `envs/dev`, not repeated on this resource
(`aws_budgets_budget` does not take tags).
<!-- END_TF_DOCS -->

## Teardown

From `envs/dev`: `terraform destroy`. Then `infra/scripts/teardown_check.sh`.
