# Static owner facing/yaw discovery workflow

# **✅ WORKFLOW — STUDY AND OPTIMIZE THIS LANE**

This document records the workflow that produced, promoted, and restart-validated the static owner facing/yaw chain:

- Coordinate resolver: `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`
- Facing/yaw resolver: `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314`
- Yaw formula: `atan2(facingZ - playerZ, facingX - playerX)`

The workflow is intentionally evidence-first: no heap address is static, no candidate is promoted from a single live read, and every current-target claim is bound to PID/HWND/process-start/module-base.

## Phase map

| Phase | Goal | Strongest artifacts |
|---|---|---|
| 1. Exact target identity | Bind current RIFT PID/HWND/process-start/module-base before reading memory. | `scripts\riftreader-launcher-inspection.cmd --json`; readback `target` envelopes. |
| 2. Coordinate anchor | Reacquire the static owner through `rift_x64+0x32EBC80`, then read owner `+0x320/+0x324/+0x328`. | `scripts\static-owner-coordinate-chain-readback.cmd --use-current-truth --samples 3 --interval-seconds 0.20 --expect-stationary --json` |
| 3. Same-owner nav readback | Read position and candidate facing target from the same owner object. | `scripts\static-owner-nav-now.cmd` |
| 4. Dynamic facing evidence | Compare pose changes and yaw deltas to identify owner-relative facing target. | `scripts\static_owner_facing_discovery.py`; camera yaw classification/multipose summaries. |
| 5. Offline static evidence | Use Ghidra to prove the owner-layout cluster and writer-site context offline. | `scripts\riftreader-ghidra-static-evidence.cmd --run --binary-path "C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe" --json` |
| 6. Proof gates | Package three-pose movement, restart survival, API-now agreement, and static evidence without auto-promotion. | `scripts\riftreader-facing-target-three-pose-gate.cmd --json`; `scripts\riftreader-facing-target-restart-survival-packet.cmd --json`; readiness review. |
| 7. Explicit promotion | Write a durable promotion artifact only after all gates are ready and approval exists. | `docs\recovery\static-owner-facing-yaw-promoted-2026-06-01.json`; `.md` companion. |
| 8. Post-restart survival | Restart manually, rebind current target, prove static root/offsets survive the new process epoch. | `scripts\captures\facing-target-restart-survival-packet-20260601-172408-160107\summary.json` |
| 9. Propagation | Update dashboard/status/current-truth docs without performing a new promotion. | `riftreader-navigation-pointer-discovery`, `current-truth-refresh-plan`, `current-truth-refresh-apply`. |

## Why Ghidra made this faster

| Observation | Effect |
|---|---|
| Ghidra found a same-owner write cluster around `0x14003FA33..0x14003FA75`. | It reduced search space from broad memory regions to one owner layout. |
| The cluster covered `owner+0x304`, `+0x30C/+0x310/+0x314`, and `+0x320/+0x324/+0x328`. | It linked facing and position to the same owner object, making `+0x30C` much more plausible than arbitrary scan hits. |
| Offline static analysis needed no live input, no debugger attach, and no memory writes. | It could run repeatedly without risking game-state mutation or target crash. |
| Static evidence was still treated as candidate-only until live proof gates passed. | It improved speed without weakening promotion discipline. |

## Efficient command loop

Run from `C:\RIFT MODDING\RiftReader`.

```powershell
cmd /c scripts\riftreader-launcher-inspection.cmd --json
cmd /c scripts\static-owner-coordinate-chain-readback.cmd --use-current-truth --samples 3 --interval-seconds 0.20 --expect-stationary --json
cmd /c scripts\static-owner-nav-now.cmd
cmd /c scripts\riftreader-navigation-pointer-discovery.cmd --json --write
cmd /c scripts\riftreader-current-truth-refresh-plan.cmd --json --write
```

When a promotion/restart packet already exists and the user has opened the appropriate gate, apply tracked truth with:

```powershell
cmd /c scripts\riftreader-current-truth-refresh-apply.cmd --apply --json
cmd /c scripts\riftreader-workflow-status.cmd --compact-json --write
cmd /c scripts\riftreader-decision-packet.cmd --compact-json --write
```

## Evidence gate checklist

| Gate | Required proof | Notes |
|---|---|---|
| Static resolver complete | Root RVA, owner read, offsets, and chain expression documented. | Absolute owner/facing/position heap addresses must be current-epoch only. |
| Same-cycle readback | Coordinates and facing target read in one target epoch. | Yaw depends on both values. |
| Three-pose displacement | Movement/turn evidence agrees across at least three poses. | Live input requires explicit approval. |
| API-now agreement | RRAPICOORD/API coordinate matches chain coordinate within tolerance. | Current target only; old API proof becomes historical. |
| Restart/relog survival | PID/process-start changes, owner heap address may change, offsets remain valid. | This is the strongest static-chain survival test. |
| Static source context | Offline Ghidra/source-site evidence supports owner-layout semantics. | Static evidence accelerates discovery but does not promote alone. |
| Promotion artifact | Tracked JSON/Markdown promotion packet records exactly what is promoted and what is not. | Promotion remains a separate explicit gate. |

## Efficiency opportunities

| Opportunity | Expected benefit | Boundary |
|---|---|---|
| Add a one-command `post-restart-facing-yaw-reacquire` Python helper. | Reduces manual sequence after restarts and avoids stale PID/HWND mistakes. | No input; exact-target readbacks only. |
| Store facing-target derived address in nav-state summaries. | Avoids dashboard fallback to stale comparison addresses. | Address is current-epoch only, not static. |
| Include restart-survival packet freshness in current-truth refresh plan. | Makes post-restart propagation review easier. | Report-only; no promotion. |
| Generate a compact promotion-review appendix from all gate artifacts. | Faster human review and easier audit. | Must preserve explicit promotion gate. |
| Add regression fixture for promoted-facing post-restart target drift. | Prevents future dashboard/current-truth stale-target regressions. | Synthetic tests only. |
| Split candidate-only support fields from promoted facing in UI labels. | Reduces confusion around `owner+0x304` and route-control fields. | Do not imply turn-control promotion. |
| Cache Ghidra pointer evidence summaries by binary hash. | Avoids re-scanning unchanged binaries. | Must invalidate on binary patch/update. |
| Add a restart-survival diff view. | Makes owner-change/offset-stability proof visually obvious. | Read-only artifact rendering. |

## Current known promoted state

| Field | Value |
|---|---|
| Current PID/HWND | `12664` / `0x205146C` |
| Process start UTC | `2026-06-01T17:19:45.159353Z` |
| Owner address | `0x1E067A80010` |
| Coordinate address | `0x1E067A80330` (`owner+0x320`) |
| Facing target address | `0x1E067A8031C` (`owner+0x30C`) |
| Current yaw | `41.29403500816383°` |
| API-now max delta | `0.00248046875003638` <= `0.25` |
| Promotion artifact | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-facing-yaw-promoted-2026-06-01.json` |
| Restart survival packet | `C:\RIFT MODDING\RiftReader\scripts\captures\facing-target-restart-survival-packet-20260601-172408-160107\summary.json` |
