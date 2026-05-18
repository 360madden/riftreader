# RiftReader Main Merge Helper

Version: riftreader-main-merge-docs-v0.1.0
Total-Character-Count: 2219
Purpose: Document the Python-owned helper for inspecting review branches and squash-merging validated RiftReader workflow branches into main.

## Purpose

`riftreader-main-merge` replaces large interactive PowerShell squash-merge blocks with a reusable Python helper.

It performs:

```text
inspect review branch
verify allowlisted diff paths
run diff whitespace checks
optionally squash merge into main
push main
verify remote SHA
```

## Files

```text
tools/riftreader_workflow/main_merge.py
scripts/riftreader-main-merge.cmd
scripts/test_main_merge.py
docs/workflow/main-merge.md
```

## Commands

Inspect a review branch without changing refs:

```powershell
.\scripts\riftreader-main-merge.cmd --json inspect-review --review-branch origin/chatgpt/review-YYYYMMDD-HHMMSSZ --expected-review-sha <sha>
```

Preview a squash merge without committing or pushing:

```powershell
.\scripts\riftreader-main-merge.cmd --json squash-review --review-branch origin/chatgpt/review-YYYYMMDD-HHMMSSZ --expected-review-sha <sha>
```

Actually squash merge, push `main`, and verify remote SHA:

```powershell
.\scripts\riftreader-main-merge.cmd --json squash-review --review-branch origin/chatgpt/review-YYYYMMDD-HHMMSSZ --expected-review-sha <sha> --yes-push
```

Run synthetic local bare-remote validation:

```powershell
.\scripts\riftreader-main-merge.cmd --json self-test
```

Validate installed helper files, tests, self-test, and `git diff --check`:

```powershell
.\scripts\riftreader-main-merge.cmd --json validate-current
```

## Safety model

The helper fails closed unless all conditions pass:

- review SHA matches when provided
- diff paths are allowlisted
- generated artifacts are ignored, not staged
- `git diff --check` passes before merge
- squash-staged paths equal inspected diff paths
- `git diff --cached --check` passes before commit
- `main` push succeeds
- remote `main` SHA equals local squash commit

The helper never uses `git add .`.

## Generated paths ignored by policy

```text
.riftreader-local/
artifacts/
scripts/captures/
scripts/sessions/
Interface/
AddOns/
```

## END_OF_MAIN_MERGE_DOCS
