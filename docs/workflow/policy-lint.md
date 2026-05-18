# RiftReader Policy Lint

Version: riftreader-policy-lint-docs-v0.1.2-test
Total-Character-Count: 1648
Purpose: Document the Python-owned RiftReader policy lint gate.

## Purpose

`riftreader-policy-lint` converts ChatGPT workflow policy into executable repository checks.

The gate is intentionally scoped. By default, `validate-repo` checks changed files only so old repository debt does not block new safe work. Full-repo audits are available with `--scope all`.

## Commands

```powershell
.\scripts\riftreader-policy-lint.cmd --json self-test
.\scripts\riftreader-policy-lint.cmd --json validate-repo
.\scripts\riftreader-policy-lint.cmd --json validate-repo --scope all
.\scripts\riftreader-policy-lint.cmd --json validate-paths --paths docs/workflow/policy-lint.md
```

## Enforced blockers

- `git add .` in executable/script docs.
- Forbidden generated/local paths when explicitly scanned.
- Non-thin CMD wrappers for Python workflow helpers.
- Python CLI helpers over 1000 characters without `main()`, `argparse`, or controlled error handling.
- Python CLI helpers over 3000 characters without a matching test file.
- Trailing whitespace in scanned files.
- `subprocess.run(... shell=True ...)` in workflow helpers.

## Warnings

- Large library-style Python modules without dedicated tests.
- Python CLI helpers without `--json` or structured JSON output.
- Subprocess use without timeout/captured output.
- Large CLI helpers without self-test.

## Output

The helper writes compact summaries to:

```text
handoffs/current/RIFTREADER_POLICY_LINT_SUMMARY.json
handoffs/current/RIFTREADER_POLICY_LINT_SUMMARY.md
```

## END_OF_POLICY_LINT_DOCS
