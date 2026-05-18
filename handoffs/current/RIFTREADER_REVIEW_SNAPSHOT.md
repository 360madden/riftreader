# RiftReader Review Snapshot

Created UTC: 2026-05-18T10:04:06.227944Z
Tool: riftreader-github-review-publish-v0.1.3
Current branch: main
HEAD: 862adef76983b7f7909ec3d7d2e50a2268cf3c38

## Validation profiles
- local-artifact-bridge: ok=True
- transport-probe: ok=True
- package-flow: ok=True
- github-review-publish: ok=True
- main-merge: ok=True
- policy-lint: ok=True

## Allowed dirty paths
- `.github/workflows/riftreader-policy.yml`
- `docs/workflow/chatgpt-development-standards.md`
- `docs/workflow/github-review-publish.md`
- `docs/workflow/local-artifact-bridge.md`
- `docs/workflow/main-merge.md`
- `docs/workflow/package-flow.md`
- `docs/workflow/policy-lint.md`
- `docs/workflow/transport-probe.md`
- `handoffs/current/RIFTREADER_POLICY_LINT_SUMMARY.json`
- `handoffs/current/RIFTREADER_POLICY_LINT_SUMMARY.md`
- `handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.json`
- `handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.md`
- `scripts/riftreader-github-review-publish.cmd`
- `scripts/riftreader-local-artifact-bridge.cmd`
- `scripts/riftreader-main-merge.cmd`
- `scripts/riftreader-package-flow.cmd`
- `scripts/riftreader-policy-lint.cmd`
- `scripts/riftreader-transport-probe.cmd`
- `scripts/test_github_review_publish.py`
- `scripts/test_local_artifact_bridge.py`
- `scripts/test_main_merge.py`
- `scripts/test_package_flow.py`
- `scripts/test_policy_lint.py`
- `scripts/test_transport_probe.py`
- `tools/riftreader_workflow/github_review_publish.py`
- `tools/riftreader_workflow/local_artifact_bridge.py`
- `tools/riftreader_workflow/main_merge.py`
- `tools/riftreader_workflow/package_flow.py`
- `tools/riftreader_workflow/policy_lint.py`
- `tools/riftreader_workflow/transport_probe.py`

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
