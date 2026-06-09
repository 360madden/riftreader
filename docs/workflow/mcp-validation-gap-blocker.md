# MCP Full Automation Validation Gap Blocker

Version: riftreader-mcp-validation-gap-blocker-doc-v0.1.0
Total-Character-Count: 2726
Purpose: Record the current validation blocker for user-driven full automation after ChatGPT prompts.

## Current goal

The target workflow is:

```text
Joey prompts ChatGPT
→ ChatGPT submits a package through MCP
→ local repo drafts/reviews/dry-runs automatically
→ local repo executes strong validation
→ local repo applies only policy-approved changes
→ local repo validates again
→ later, local repo commits/pushes only under policy
→ ChatGPT reads results and continues
```

## Confirmed working path

```text
ChatGPT → submit_package_proposal → local inbox
ChatGPT → create_package_draft_from_inbox → inert local draft
ChatGPT → review_latest_package_draft → ready/no blockers
ChatGPT → dry_run_latest_package_draft → structural dry-run passes
ChatGPT → apply_latest_package_draft without token → APPLY_APPROVAL_MISSING
```

## Hard validation gap

Package dry-run currently reports declared checks but does not execute them.

Observed pattern:

```json
{
  "checks": {
    "declaredCount": 3,
    "runCount": 0,
    "failedCount": 0
  }
}
```

This is not strong CI. It is only structural review.

## Required before auto-apply-safe

Before any package can be auto-applied, the local workflow must ensure:

```text
- declaredCount > 0 for code/helper packages
- runCount == declaredCount
- failedCount == 0
- py_compile passes for Python files
- unit tests pass for testable helper logic
- git diff --check passes
- stdout/stderr are captured
- summary artifact records every check result
- failure blocks apply
```

## Recommended next implementation

Patch package-intake or add a repo-owned validation stage so dry-run can execute declared checks in a temporary workspace before real apply.

Required behavior:

```text
1. Create temporary workspace under .riftreader-local.
2. Copy or materialize a safe repo snapshot.
3. Overlay package draft files into that workspace.
4. Run only allowlisted checks:
   - python -m py_compile ...
   - python -m unittest ...
   - git --no-pager diff --check
5. Capture stdout/stderr/exit code/timing.
6. Return runCount and failedCount accurately.
7. Block apply if checks fail or if declared checks were not executed.
```

## Safety boundaries

```text
- no arbitrary shell endpoint
- no arbitrary file read/write endpoint
- no git add/commit/push
- no provider writes
- no RIFT input
- no CE
- no x64dbg
- no live movement or screenshot hotkeys
```

## Current decision

Do not apply code-bearing automation packages until the validation runner path executes declared checks and reports runCount equal to declaredCount.

## END_OF_SCRIPT_MARKER
