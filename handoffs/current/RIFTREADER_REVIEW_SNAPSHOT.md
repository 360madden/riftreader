# RiftReader Review Snapshot

Created UTC: 2026-05-18T00:45:17.351477Z
Tool: riftreader-github-review-publish-v0.1.1
Current branch: chatgpt/review-20260518-002437Z
HEAD: 86e64190cdaab38e2f3211e4c5f3971740da141b

## Validation profiles
- local-artifact-bridge: ok=True
- transport-probe: ok=True
- package-flow: ok=True
- github-review-publish: ok=True

## Allowed dirty paths
- `docs/workflow/github-review-publish.md`
- `handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.json`
- `handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.md`
- `scripts/test_github_review_publish.py`
- `tools/riftreader_workflow/github_review_publish.py`

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
