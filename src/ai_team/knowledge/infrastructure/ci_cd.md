# CI/CD

- Run lint, type-check, and fast unit tests on every push; gate merges on green CI.
- Cache dependency installs (Poetry/pip) to shorten feedback loops.
- Use matrix builds for supported Python versions when the project supports multiple.
- Store secrets in CI provider vaults, not in repository variables visible to forks.
