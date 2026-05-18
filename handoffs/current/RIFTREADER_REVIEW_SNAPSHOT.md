# RiftReader Review Snapshot

Created UTC: 2026-05-18T07:16:47.951436Z
Tool: riftreader-github-review-publish-v0.1.1
Current branch: chatgpt/review-20260518-065000Z
HEAD: 341b4498fcc97ef3c9364e80218546a227a06afe

## Validation profiles
- local-artifact-bridge: ok=True
- transport-probe: ok=True
- package-flow: ok=True
- github-review-publish: ok=True

## Allowed dirty paths
- `docs/workflow/chatgpt-development-standards.md`
- `docs/workflow/package-flow.md`

## Ignored/generated dirty paths
- `artifacts/chatgpt-payloads`

## Unexpected dirty paths
None.

## Policy
- Python owns workflow logic.
- CMD/PowerShell wrappers stay thin.
- Stage explicit allowlisted paths only.
- Do not stage generated payload artifacts.
- Review branches are preferred over direct main pushes.

# END_OF_REVIEW_SNAPSHOT
