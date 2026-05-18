# ChatGPT Development Standards for RiftReader

Version: riftreader-chatgpt-development-standards-v0.1.0  
Total-Character-Count: 2128  
Purpose: Document the ChatGPT-owned coding and validation standards for RiftReader workflow helpers.

## Operating rule

RiftReader workflow helpers must be treated as durable repo tooling, not disposable chat snippets.

## Python-first rule

Python owns real workflow logic. CMD and PowerShell wrappers are convenience launchers only.

Thin wrappers may:

```text
cd /d repo root
python tools\...\helper.py %*
exit /b %ERRORLEVEL%
```

Wrappers must not own package parsing, JSON construction, Git policy, path traversal defense, or validation logic.

## Quality rules

- Prefer existing repo helpers before adding new tools.
- Avoid hardcoded usernames and local-only assumptions.
- Use repo-relative paths and explicit allowlists.
- Fail closed on validation, schema, hash, path, Git, or test failures.
- Emit clean JSON when `--json` is used.
- Do not print a success marker after a failed critical stage.
- Do not use `git add .`.
- Do not stage generated payload artifacts.
- Do not perform live RIFT, ProofOnly, CE, or x64dbg operations unless that lane is explicitly selected.

## Required checks for delivered code

Each delivered helper or patch must have a visible checklist covering:

- syntax or parse check
- unit tests where practical
- smoke test where practical
- package integrity and manifest checks for ZIP packages
- path safety review
- Git staging safety review
- output contract review
- artifact hygiene review
- runtime validation limits or known gaps

## Review transport policy

GitHub may be used as review transport after local validation passes. The safe default is a review branch, not direct `main`.

The expected flow is:

```text
apply package
validate profiles
write sanitized review snapshot
stage exact allowlisted paths
commit
push review branch
verify remote SHA
ChatGPT reads GitHub read-only
```

Generated folders such as `artifacts/` and `.riftreader-local/` are not review payloads and must not be staged.

# END_OF_CHATGPT_DEVELOPMENT_STANDARDS
