# RiftReader Handoff — static facing/yaw promoted; waiting for manual restart — 2026-06-01 17:18 UTC

# **✅ CURRENT RESULT**

Static owner facing/yaw is promoted and pushed. Operator is about to manually restart RIFT to run the strongest practical survival recheck.

## Repo / Git

| Field | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` |
| Current HEAD before this handoff commit | `9ba4efa` — `Promote static owner facing yaw` |
| Remote state before this handoff commit | `main` matched `origin/main` at `9ba4efa` |
| Latest compact status | `.riftreader-local\workflow-status\20260601-171625Z\compact-sitrep.json` |

## Promoted chains

| Purpose | Chain / formula | Status |
|---|---|---|
| Position | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` | Promoted coordinate resolver |
| Facing target vector | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` | Promoted static owner facing/yaw source |
| Yaw formula | `atan2(facingZ - playerZ, facingX - playerX)` | Use after same-cycle coordinate + facing readback |

## Promotion artifacts

| Artifact | Path |
|---|---|
| Promotion JSON | `docs\recovery\static-owner-facing-yaw-promoted-2026-06-01.json` |
| Promotion Markdown | `docs\recovery\static-owner-facing-yaw-promoted-2026-06-01.md` |
| Current truth | `docs\recovery\current-truth.json` |
| Promotion apply helper | `scripts\riftreader-facing-target-promotion-apply.cmd` / `scripts\facing_target_promotion_apply.py` |
| Dashboard | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` |

## Current pre-restart live target snapshot

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `41808` |
| HWND | `0x2B0A26` |
| Process start | `2026-06-01T01:50:50.903773Z` |
| Module base | `0x7FF6EE5D0000` |
| Last coordinate/nav readback | `2026-06-01T16:48:56Z` epoch; fresh at status time but expected to become stale after restart |

## Current dashboard verdict before restart

| Surface | Value |
|---|---|
| Navigation pointer status | `passed` |
| Facing/yaw status | `promoted-static-owner-facing-yaw-current-pid-readback-passed` |
| Facing promotion performed | `true` |
| Next recommended action | `Use the promoted static-owner facing/yaw chain for yaw readback after exact PID/HWND/process-start/module-base preflight.` |

## What is intentionally NOT promoted

- Turn-rate/support field `owner+0x304`.
- Support fields `owner+0x300` and `owner+0x408`.
- Full actor/stat chain.
- Proof anchor.
- Autonomous turn-control automation.

## Manual restart plan

Operator will manually restart RIFT after this handoff is pushed. After restart, do not reuse PID `41808`, HWND `0x2B0A26`, module base, owner heap address, or any old absolute heap address as current truth.

## Resume checklist after manual restart

Run these in order from `C:\RIFT MODDING\RiftReader`:

```powershell
cmd /c scripts\riftreader-launcher-inspection.cmd --json
cmd /c scripts\static-owner-coordinate-chain-readback.cmd --use-current-truth --samples 3 --interval-seconds 0.20 --expect-stationary --json
cmd /c scripts\static-owner-nav-now.cmd
cmd /c scripts\riftreader-navigation-pointer-discovery.cmd --json --write
cmd /c scripts\riftreader-workflow-status.cmd --compact-json --write
cmd /c scripts\riftreader-decision-packet.cmd --compact-json --write
```

If the PID/process-start changed and the chains still resolve, record a fresh restart survival recheck. The proof to look for is: static root RVA `0x32EBC80` still resolves, owner heap address may change, offsets `0x30C/+0x310/+0x314` and `0x320/+0x324/+0x328` remain valid, yaw is sane, and API-now vs chain-now remains within tolerance.

## Safety notes

- This handoff sends no game input and performs no debugger/CE work.
- Restart is manual/operator-owned.
- Post-restart reads must rebind exact PID/HWND/process-start/module-base first.
- If target identity is ambiguous or stale, stop and refresh identity before any readback or movement.

## Recommended next action

After manual restart, run the resume checklist above and create a fresh post-promotion restart survival packet if the promoted facing/yaw chain survives.
