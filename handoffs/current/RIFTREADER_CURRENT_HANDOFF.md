# RiftReader Current Handoff

- Generated UTC: `2026-06-04T01:52:35Z`
- Branch: `main`
- HEAD: `37f0a7b96cbc83c3397819815678e59b083af94f` `Refresh current proof anchor for PID 77152`
- Current lane: `post-update static pointer-chain repair after proof-anchor recovery`

## TL;DR

Proof-anchor recovery succeeded and was committed to `main`, but the old promoted static owner root is null in the current process. Stop trying stale current-truth/static-dashboard refresh. Next lane is static pointer-chain repair.

## Verified proof anchor

- Status: `current-target-proofonly-passed`
- PID/HWND: `77152` / `0x17A0DB2`
- Anchor address: `0x1D4BA11BE00`
- Commit: `37f0a7b96cbc83c3397819815678e59b083af94f` `Refresh current proof anchor for PID 77152`
- ProofOnly passed UTC: `2026-06-03T23:57:10Z`

## Static owner root result

- Chain: `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`
- Live PID/HWND: `77152` / `0x17A0DB2`
- Live module base: `0x7FF7211C0000`
- Root RVA/address: `0x32EBC80` / `0x7FF7244ABC80`
- Verdict: `root-pointer-null`
- Artifact: `scripts/captures/static-owner-coordinate-chain-readback-20260604-010515-373344/summary.json`

## Latest status packet

- Status UTC: `2026-06-04T01:07:25Z`
- Status: `blocked`
- Git clean: `True`
- Head: `37f0a7b Refresh current proof anchor for PID 77152`
- Compact status artifact: `.riftreader-local/workflow-status/20260604-010725Z/compact-sitrep.json`

## Current blockers

- `static-owner-root-null:[rift_x64+0x32EBC80]==0x0`
- `navigation-pointer-discovery-dashboard-stale-from-pid-12664`
- `current-truth-refresh-plan-blocked:coordinateReadback-not-passed/navState-not-fresh/dashboard-has-stale-readback-source`
- `status overlay still reports artifact-pid-stale from old current-truth/status inputs despite current proof anchor being committed`

## Exact next action

Patch automation/status workflow so proof-anchor-current plus static-root-null is classified as static-chain-repair-needed, not as proof-anchor-recovery-needed; then resume post-update static pointer-chain repair to find the replacement static owner root.

## Do not do

- Do not run current-truth-refresh-apply from stale PID 12664 dashboard artifacts.
- Do not reuse [rift_x64+0x32EBC80] as current truth while root-pointer-null persists.
- Do not promote support fields or old facing/nav data from PID 12664.
- Do not run live x64dbg, Cheat Engine, breakpoints, watchpoints, or movement unless explicitly selected in a later turn.
- Do not switch back to bridge implementation work unless explicitly asked.

## Verified helpers/docs

- `scripts/recover_current_pid_coord_anchor_fast.py`
- `scripts/promote-current-pid-proof-anchor-from-batch.ps1`
- `scripts/live_test.py --profile ProofOnly`
- `scripts/static_owner_coordinate_chain_readback.py`
- `scripts/riftreader-workflow-status.cmd`
- `docs/recovery/current-pid-coordinate-family-recovery-policy.md`
- `handoffs/current/RIFTREADER_AUTOMATION_ORCHESTRATOR_PLAN.md`

## Drive artifact note

- Drive root: `G:\My Drive\RiftReader`
- Policy: `No new Drive artifact was required in this handoff. GitHub main remains source of truth.`
