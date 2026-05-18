# Compact handoff — workflow status and review helper blockers resolved

Created: 2026-05-18 06:07:48 Eastern Daylight Time
Branch: `main`
HEAD before this handoff commit: `744e376 744e376ac2c726759283a5a311d0b51134470a3a 2026-05-18 06:04:40 -0400 Add ChatGPT workflow review helpers`
Scope: Follow-up after executing the 1-10 milestone list from the handoff review.

## TL;DR

The workflow/status blocker from the prior review is fixed: `scripts\riftreader-workflow-status.cmd --compact-json` now reports the checked-out `HEAD` (`744e376`) instead of the newest commit from unrelated refs. The untracked workflow-helper files on `main` were resolved by curating the useful review-branch payload into `main` as `744e376` and deliberately excluding generated `artifacts/chatgpt-payloads` smoke payloads.

OpenCode/non-Codex workflow helpers are now present on `main`: local artifact bridge, transport probe, package flow, GitHub review publish, main merge, policy lint, docs, wrappers, tests, and refreshed current summaries.

Live movement remains blocked. There is no live `rift_x64` process in the current status check, current coordinate proof remains `blocked-target-drift`, and the stale PID/HWND `27552` / `0x3411E2` stays historical-only.

## What changed in this milestone

| Commit | Pushed | Purpose |
|---|---:|---|
| `862adef` | yes | Fixed `status_packet.py` so compact status uses checked-out `HEAD`, not `git log --all`; added regression test. |
| `744e376` | yes | Added curated ChatGPT workflow review helpers from the review lane; excluded generated transport-smoke artifacts. |

## Current repo state at handoff creation

```text
## main...origin/main
 M handoffs/current/RIFTREADER_POLICY_LINT_SUMMARY.json
 M handoffs/current/RIFTREADER_POLICY_LINT_SUMMARY.md
 M handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.json
 M handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.md
```

Expected dirty files at this handoff point are this new handoff plus refreshed `handoffs/current` summaries after `744e376`.

## Validation performed

| Validation | Result |
|---|---|
| `python -m unittest scripts.test_opencode_status_packet` | passed, 11 tests |
| `python -m unittest scripts.test_local_artifact_bridge scripts.test_transport_probe scripts.test_package_flow scripts.test_github_review_publish scripts.test_main_merge scripts.test_policy_lint scripts.test_opencode_status_packet scripts.test_primary_workflow_policy` | passed, 87 tests |
| `python -m py_compile` on new workflow tools/tests | passed |
| `python tools/riftreader_workflow/package_flow.py --json validate-current --profile <each profile>` for local-artifact-bridge, transport-probe, package-flow, github-review-publish, main-merge, policy-lint | all passed |
| `python tools/riftreader_workflow/policy_lint.py --json validate-repo --scope changed` | passed, 0 blockers, 0 warnings |
| `python tools/riftreader_workflow/github_review_publish.py --json validate-ready --profiles local-artifact-bridge,transport-probe,package-flow,github-review-publish,main-merge,policy-lint` | passed; refreshed `handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.*` |
| `git --no-pager diff --cached --check` before each commit | passed |
| `git push origin main` for both commits | passed |

## Current proof / live blockers

| Blocker | Current truth |
|---|---|
| Live process | `rift_x64` not detected during current status check. |
| Coordinate proof | `blocked-target-drift`; prior proof target remains historical-only. |
| Movement gate | blocked: no live target reacquisition and no same-target proof. |
| RiftScan milestone review | blocked for live/discovery expansion: selected candidate source is `none`; no supported RiftScan match file found for current requested target. |
| CE/x64dbg | not used; no attach. |
| Input/movement | none sent. |

## Branch/review-lane decision

The local `chatgpt/review-20260518-065000Z` branch is superseded by the curated `main` commit `744e376` for useful workflow files. I did **not** push that local branch tip because it includes generated `artifacts/chatgpt-payloads` smoke payloads that the workflow policy says not to stage into the main path. I also did not delete or rewrite the branch in this milestone.

## Resume sequence

1. Start from `main` at or after `744e376` plus this handoff commit.
2. Confirm `git --no-pager status --short --branch` is clean after the handoff commit.
3. Run `scripts\riftreader-workflow-status.cmd --compact-json`; `git.head.hash` should be the checked-out HEAD, not a side-branch commit.
4. Keep movement blocked until RIFT is loaded, fresh API/runtime truth exists, and same-target ProofOnly/current-PID proof passes.
5. If doing more workflow work, use the Python-owned helpers and explicit path staging; do not stage generated `artifacts/` payloads.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Commit this handoff plus refreshed `handoffs/current` summaries. | Leaves a current, repo-owned resume point after the milestone. |
| 2 | Re-run compact status after the handoff commit. | Confirms `git.head` still follows checked-out HEAD with a clean tree. |
| 3 | Leave movement blocked until a live `rift_x64` target exists. | Current proof status is stale/offline. |
| 4 | When live target returns, start with no-input PID/HWND/API runtime reacquisition. | Prevents stale proof reuse. |
| 5 | Only run RiftScan consumer paths with explicit existing candidate files unless writes are authorized. | Preserves provider boundary. |
| 6 | Do not push the superseded review branch unless you explicitly want its historical generated artifacts remote. | Main already has the curated useful code. |
| 7 | Use `policy_lint.py --scope changed` before future workflow commits. | Catches policy regressions cheaply. |
| 8 | Use `github_review_publish.py validate-ready` for future review snapshots. | Keeps review handoffs consistent and machine-readable. |
| 9 | Keep workflow helpers Python-owned and `.cmd` wrappers thin. | Matches current repo policy. |
| 10 | If expanding into live proof, run `scripts\riftscan_milestone_review.py` before and after the milestone. | It keeps stale/candidate evidence from becoming movement truth. |
