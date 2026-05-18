# RiftReader GitHub Review Publish

Version: riftreader-github-review-publish-docs-v0.1.2
Total-Character-Count: 2685
Purpose: Document the Python-owned GitHub review publish helper for moving validated RiftReader workflow state to GitHub for ChatGPT read-only review.

## Purpose

`riftreader-github-review-publish` reduces copy/paste by turning validated local workflow state into a review branch on GitHub.

It is intentionally conservative:

- validates configured profiles first
- writes sanitized review snapshots
- stages explicit allowlisted files only
- refuses unexpected dirty paths
- ignores generated payload/artifact folders
- pushes a review branch only when `--yes-push` is supplied
- verifies the remote branch SHA after push

## Files

```text
tools/riftreader_workflow/github_review_publish.py
scripts/riftreader-github-review-publish.cmd
scripts/test_github_review_publish.py
docs/workflow/github-review-publish.md
```

## Commands

Validate current workflow state and write snapshot without commit or push:

```powershell
.\scripts\riftreader-github-review-publish.cmd --json validate-ready
```

Preview a review-branch publish plan without pushing:

```powershell
.\scripts\riftreader-github-review-publish.cmd --json publish-branch
```

Actually publish a review branch:

```powershell
.\scripts\riftreader-github-review-publish.cmd --json publish-branch --yes-push
```

Run internal synthetic checks:

```powershell
.\scripts\riftreader-github-review-publish.cmd --json self-test
```

## Safety model

The helper stages only an internal allowlist of workflow code, workflow docs, tests, and review snapshot files. It never stages generated payload folders such as:

```text
artifacts/
.riftreader-local/
scripts/captures/
scripts/sessions/
Interface/
AddOns/
```

## Output

With `--json`, stdout is clean JSON intended for machine review.

# END_OF_GITHUB_REVIEW_PUBLISH_DOCS

## v0.1.1 return-to-start-branch option

After a successful review branch publish, operators can ask the helper to switch the local checkout back to the branch that was active before publishing:

```powershell
.\scripts
iftreader-github-review-publish.cmd --json publish-branch --yes-push --return-to-start-branch
```

This option is intentionally explicit. The default behavior remains conservative and leaves the checkout on the newly created review branch for direct inspection. When enabled, the JSON `publish` object reports:

```text
startingBranch
returnedToStartBranch
finalBranch
```

If publishing fails after the helper has switched to the review branch, it attempts to return to the starting branch before surfacing the failure.

# END_OF_GITHUB_REVIEW_PUBLISH_DOCS_V011
