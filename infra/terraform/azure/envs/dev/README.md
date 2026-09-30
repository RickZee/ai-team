# azure dev

Tags (`project`, `env`, `owner`, `cost_center`) are one `locals.tags` map, passed
into modules. State defaults to local. `backend.hcl` is not committed.

## Teardown

```bash
terraform destroy
../../../../scripts/teardown_check.sh
```

`terraform apply` and `terraform destroy` are run by Rick.
