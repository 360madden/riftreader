# RiftReader Review Snapshot

Created UTC: 2026-05-18T10:31:20.566690Z
Tool: riftreader-github-review-publish-v0.1.3
Current branch: main
HEAD: 3cbd6ad8fbeb6accb98f4fb47aa3a06fea580a74

## Validation profiles
- local-artifact-bridge: ok=True
- transport-probe: ok=True
- package-flow: ok=True
- github-review-publish: ok=True
- main-merge: ok=True
- policy-lint: ok=True

## Allowed dirty paths
- `handoffs/current/RIFTREADER_POLICY_LINT_SUMMARY.json`
- `handoffs/current/RIFTREADER_POLICY_LINT_SUMMARY.md`

## Ignored/generated dirty paths

## Unexpected dirty paths
None.

## Policy
- Python owns workflow logic.
- CMD/PowerShell wrappers stay thin.
- Stage explicit allowlisted paths only.
- Do not stage generated payload artifacts.
- Review branches are preferred over direct main pushes.

# END_OF_REVIEW_SNAPSHOT
