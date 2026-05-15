# Fast coordinate restart recovery

Created: 2026-05-15

## Purpose

Use this workflow after a RIFT client restart or target drift when the previous
coordinate proof anchor is stale. It keeps the fast path explicit:

1. confirm the current PID/HWND;
2. obtain fresh API/runtime coordinate truth;
3. scan the last successful family range first when a restart profile exists;
4. fall back to current-PID family inventory and stop-on-hit scanning;
5. require displaced-pose validation before promotion;
6. require same-target `ProofOnly` after promotion.

Old absolute candidate addresses are never current truth after a restart. The
restart profile stores **family/range timing hints**, not movement truth.

## Default commands

From `C:\RIFT MODDING\RiftReader`:

| Goal | Command |
|---|---|
| Dry-run plan | `scripts\recover-current-pid-coord-anchor-fast.cmd --pid <PID> --hwnd <HWND> --use-restart-profile --json` |
| No-movement execute | `scripts\recover-current-pid-coord-anchor-fast.cmd --pid <PID> --hwnd <HWND> --execute --use-restart-profile --json` |
| Full promotion refresh | `scripts\recover-current-pid-coord-anchor-fast.cmd --pid <PID> --hwnd <HWND> --execute --use-restart-profile --movement-approved --allow-current-truth-update --run-proofonly --write-restart-profile --json` |
| Compact status | `python scripts\coordinate_recovery_status.py --json` |

Use the no-movement execute first after each restart. It writes a run-local
restart profile without replacing the repo profile. Only run the full promotion
refresh when current truth needs to be rebuilt and movement is approved for
displaced-pose validation.

## ChromaLink freshness lane

ChromaLink is the fastest API-now truth source only when health/freshness pass.
Reachability is not enough.

Quick provider check:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink\scripts\Get-ChromaLinkStackStatus.ps1"
```

Expected useful state:

| Field | Required value |
|---|---|
| `Healthy` | `true` |
| `Stale` | `false` |
| `FreshFrames` | greater than `0` |
| `CLI Watch` | `1` |
| `Profile` | `P360C` |

If ChromaLink is stale:

1. verify the RIFT client is `640x360`;
2. restart the ChromaLink watch loop if the active watcher is old/stuck;
3. rerun `scripts\chromalink_world_state_reference.py`;
4. only use ChromaLink as reference when that helper returns `status=passed`.

### 2026-05-15 validation note

During the follow-up validation, ChromaLink was reachable but stale because the
old `ChromaLink.Cli.exe watch --backend screen` process had stopped producing
fresh frames. The RIFT client geometry was already correct (`640x360`). Restarting
only the watch process restored:

| Check | Result |
|---|---|
| `Healthy` | `true` |
| `Stale` | `false` |
| `FreshFrames` | `4` |
| `CLI Watch` | `1` |
| `Profile` | `P360C` |

The fresh ChromaLink reference then passed at:

```text
scripts\captures\chromalink-refresh-check-20260515-after-watch-restart\summary.json
```

The profile-first no-movement execute then used ChromaLink instead of RRAPICOORD
and found the anchor family directly:

| Stage | Result |
|---|---|
| ChromaLink reference | passed in about `0.35s` |
| Profile-priority family scan | passed in about `3.18s` |
| Inventory/scan-plan batch | skipped |
| Movement | blocked/not sent |

Run artifact:

```text
scripts\captures\recover-currentpid-coord-anchor-fast-execute-27552-20260515-062338-196633\summary.json
```

## Restart profile behavior

`docs\recovery\coordinate-recovery-profile.json` records the previous winning
range:

| Field | Meaning |
|---|---|
| `bestScanRange.minAddressHex` / `maxAddressHex` | range hint to scan first |
| `candidateJsonl` | previous candidate output, historical only |
| `stageTimings` | timing evidence for future speed comparisons |
| `profileScanUsed` | whether the most recent run succeeded through the profile-first lane |
| `proofOnlySummaryJson` | final same-target proof artifact when promotion completed |

When `--use-restart-profile` is set, the helper tries
`profile-priority-family-scan` after fresh reference selection and before the
full inventory. If that profile scan produces no current-PID hit, the helper
falls back to inventory plus scan-plan batch.

## Safety boundaries

| Boundary | Rule |
|---|---|
| Cheat Engine | not used |
| x64dbg | offline/read-only only until explicitly changed |
| SavedVariables | not live truth |
| Movement | blocked unless `--movement-approved` is passed |
| Truth writes | blocked unless `--allow-current-truth-update` is passed |
| Proof gate | run `--run-proofonly` immediately after promotion |

## Recovery speed pattern

Fast recoveries share the same shape:

1. use a fresh API reference immediately;
2. avoid stale absolute pointer probing;
3. scan a high-value family/range first;
4. promote only after displaced-pose tracking;
5. write the profile again after final proof so the next restart starts with
   better timing hints.
