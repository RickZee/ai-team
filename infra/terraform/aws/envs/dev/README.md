# aws dev

Tags (`project`, `env`, `owner`, `cost_center`) are set once on the AWS provider
`default_tags` block. State defaults to local. `backend.hcl` is not committed.

## Teardown

```bash
terraform destroy
../../../../scripts/teardown_check.sh
```

`terraform apply` and `terraform destroy` are run by Rick.
