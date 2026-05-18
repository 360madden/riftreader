# RiftReader Review Snapshot

Created UTC: 2026-05-18T07:47:54.130968Z
Tool: riftreader-github-review-publish-v0.1.2
Current branch: chatgpt/review-20260518-065000Z
HEAD: 341b4498fcc97ef3c9364e80218546a227a06afe

## Validation profiles
- local-artifact-bridge: ok=True
- transport-probe: ok=True
- package-flow: ok=True
- github-review-publish: ok=True
- main-merge: ok=True

## Allowed dirty paths
- `docs/workflow/main-merge.md`
- `docs/workflow/package-flow.md`
- `scripts/riftreader-main-merge.cmd`
- `scripts/test_github_review_publish.py`
- `scripts/test_main_merge.py`
- `scripts/test_package_flow.py`
- `tools/riftreader_workflow/github_review_publish.py`
- `tools/riftreader_workflow/main_merge.py`
- `tools/riftreader_workflow/package_flow.py`

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
