# RiftReader Handoff — stage-0 navigation pointer refresh — 2026-06-01 21:24 UTC

# **✅ CURRENT RESULT**

Stage-0 navigation pointer discovery is refreshed, indexed, and backed by fresh
current-target truth. The dashboard is fresh, the worktree was clean before this
handoff slice, and local `main` was ahead of `origin/main` by 11 commits. No
push was performed.

## Repo / Git

| Field | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` |
| HEAD before this handoff | `364d454` — `Refresh current truth after forward route refresh` |
| Remote state before this handoff | `main...origin/main [ahead 11]` |
| Push | Not performed; still requires explicit push approval |

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `12664` |
| HWND | `0x205146C` |
| Process start UTC | `2026-06-01T17:19:45.159353Z` |
| Module base | `0x7FF6EE5D0000` |
| Owner address | `0x1E067A80010` |

## Navigation chain status

| Purpose / field | Chain / value | Status |
|---|---|---|
| Position | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` | Promoted; current PID readback + API-now passed |
| Facing/yaw | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` | Promoted; current yaw `44.11798623707763°` |
| Derived velocity/speed | Dashboard live-correlation ledger | Forward/back/stop correlation passed; not a dedicated static speed pointer |
| `owner+0x304` | `[rift_x64+0x32EBC80]+0x304` | Candidate-only; semantics review classifies yaw-adjacent, not active turn-rate |
| `owner+0x438` | raw float `7232.0`, hex `0x45E20000` | Candidate-only; unchanged during forward progress |
| `owner+0x43C` | raw float `800.0`, hex `0x44480000` | Candidate-only; unchanged during forward progress |
| `owner+0x440` | raw float `2976.0`, hex `0x453A0000` | Candidate-only; unchanged during forward progress |
| Actor/stat chain | no-debug actor status | Not promoted; `current-proof-anchor-not-passed` |

## Key evidence

| Evidence | Result / path |
|---|---|
| Navigation dashboard | `.riftreader-local\navigation-pointer-discovery\latest\summary.json`; `passed`, fresh, no stale sources |
| Current truth | `docs\recovery\current-truth.json`; updated `2026-06-01T21:21:33Z` |
| Latest chain/API max abs delta | `0.004418749999786087 <= 0.25` |
| Latest coordinate | `(7308.57421875, 823.53662109375, 3045.098388671875)` at `2026-06-01T21:19:13.898492+00:00` |
| API marker | `scripts\captures\rift-api-reference-currentpid-12664-20260601-212046.json` |
| Static readback | `scripts\captures\static-owner-coordinate-chain-readback-20260601-211913-897755\summary.json` |
| Fresh forward route step | `scripts\captures\static-owner-nav-route-step-20260601-211844-099888\summary.json`; progress `6.9267917148948435m` |
| Fresh backward contrast | `scripts\captures\static-owner-nav-route-step-20260601-210105-864282\summary.json`; expected wrong-way delta `-1.8726568906169936m` |
| Support-field contrast | `supportFieldMotion.status=support-fields-unchanged-during-forward-progress` |
| Offline static evidence | `scripts\captures\ghidra-static-analysis-20260601-210631\summary.json`; `8,057,130` instructions scanned, `200` root refs captured |
| Actor no-debug status | `scripts\captures\actor-chain-no-debug-status-20260601-210455-466513\summary.json`; candidate found, not promoted |

## Local commits in this stage-0 continuation

| Commit | Message |
|---|---|
| `54c8e48` | `Surface navigation velocity ledger in decisions` |
| `4d90257` | `Expose navigation support offset readbacks` |
| `ebab21c` | `Index navigation support field motion contrast` |
| `4d40f3b` | `Refresh current navigation truth after live probes` |
| `258a7be` | `Refresh current truth after backward contrast` |
| `364d454` | `Refresh current truth after forward route refresh` |

## Safety

- Exact-target live movement was sent only under the current approved live
  navigation lane and through PID/HWND-bound helpers.
- No Cheat Engine or x64dbg attach, breakpoints, watchpoints, target writes, or
  provider repo writes were performed.
- The current-truth apply helper updated tracked truth only after fresh
  static-chain/API-now evidence and did not promote proof, actor, facing, or
  turn-rate truth.
- Offline Ghidra evidence was refreshed from the installed binary only; it did
  not read or write target-process memory.
- No Git push was performed.

## Resume checklist

```powershell
git --no-pager status --short --branch
cmd /c scripts\riftreader-decision-packet.cmd --compact-json --write --run-safe-checks
cmd /c scripts\riftreader-navigation-pointer-discovery.cmd --json --write
cmd /c scripts\riftreader-actor-chain-no-debug-status.cmd --json
```

## Next recommended direction

Stage 0 is complete and fresh. The next useful local lane is actor/stat-chain
provenance, starting no-debug/read-only where practical. If x64dbg access
provenance is required, keep it bounded to the current PID/HWND and do not
promote actor/proof truth until the dedicated gates pass. Push remains a
separate explicit approval boundary.
