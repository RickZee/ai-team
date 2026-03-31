# Security best practices

- Never use `eval()`, `exec()`, or `os.system()` on untrusted input.
- Use `subprocess.run(..., shell=False)` with explicit argument lists.
- Load secrets from environment variables or a secrets manager, not source code.
- Validate and normalize file paths; reject traversal (`..`) outside the workspace.
- Use `yaml.safe_load()` or `yaml.load(..., Loader=yaml.SafeLoader)` for YAML parsing.
