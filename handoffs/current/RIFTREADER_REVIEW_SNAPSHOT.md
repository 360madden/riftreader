# RiftReader Review Snapshot

Created UTC: 2026-05-18T00:24:37.043200Z
Tool: riftreader-github-review-publish-v0.1.0
Current branch: main
HEAD: e603683738effa122c746ed521ac121dd5bc2081

## Validation profiles
- local-artifact-bridge: ok=True
- transport-probe: ok=True
- package-flow: ok=True
- github-review-publish: ok=True

## Allowed dirty paths
- `docs/workflow/chatgpt-development-standards.md`
- `docs/workflow/github-review-publish.md`
- `docs/workflow/local-artifact-bridge.md`
- `docs/workflow/package-flow.md`
- `docs/workflow/transport-probe.md`
- `handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.json`
- `handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.md`
- `scripts/riftreader-github-review-publish.cmd`
- `scripts/riftreader-local-artifact-bridge.cmd`
- `scripts/riftreader-package-flow.cmd`
- `scripts/riftreader-transport-probe.cmd`
- `scripts/test_github_review_publish.py`
- `scripts/test_local_artifact_bridge.py`
- `scripts/test_package_flow.py`
- `scripts/test_transport_probe.py`
- `tools/riftreader_workflow/github_review_publish.py`
- `tools/riftreader_workflow/local_artifact_bridge.py`
- `tools/riftreader_workflow/package_flow.py`
- `tools/riftreader_workflow/transport_probe.py`

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
