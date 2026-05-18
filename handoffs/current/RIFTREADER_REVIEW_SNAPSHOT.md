# RiftReader Review Snapshot

Created UTC: 2026-05-18T06:50:00.705935Z
Tool: riftreader-github-review-publish-v0.1.1
Current branch: chatgpt/review-20260518-004517Z
HEAD: 612af79032773afe67b174a693f1515d4a385054

## Validation profiles
- local-artifact-bridge: ok=True
- transport-probe: ok=True
- package-flow: ok=True
- github-review-publish: ok=True

## Allowed dirty paths
- `docs/workflow/github-review-publish.md`
- `handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.json`
- `handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.md`

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
