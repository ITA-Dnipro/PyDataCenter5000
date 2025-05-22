# Code Style & Pre-commit Hooks

This project enforces consistent code style and formatting using pre-commit hooks.\
Below is a list of hooks that are automatically run before each commit to help maintain clean and readable code.

## Enabled Pre-commit Hooks:

- **black** — Formats code according to Black's opinionated PEP 8-compatible style.
- **isort** — Automatically sorts and organizes Python imports. Compatible with Black.
- **trailing-whitespace** — Removes trailing whitespace from all lines.
- **end-of-file-fixer** — Ensures a single newline at the end of each file.
- **check-json** — Validates JSON files for syntax correctness.
- **check-yaml** — Validates YAML files for syntax correctness.
- **check-merge-conflict** — Detects leftover merge conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).
- **debug-statements** — Prevents accidental commits of `print()` or `pdb` statements.

### Run Pre-commit Hooks Manually

To run all configured pre-commit hooks manually on all files, use:

```bash
pre-commit run --all-files
```
