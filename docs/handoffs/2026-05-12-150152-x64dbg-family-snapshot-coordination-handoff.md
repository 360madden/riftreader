# Compact handoff — x64dbg + family-snapshot coordinate recovery coordination

| Field | Value |
|---|---|
| Generated local | `2026-05-12T15:01:52-04:00` |
| Generated UTC | `2026-05-12T19:01:52Z` |
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` |
| Current committed HEAD before this handoff | `f95e3719b8c6335b29840181d3750bb6cde2da66` — `Document x64dbg pointer-chain workflow` |
| Live target at handoff refresh | `rift_x64` PID `63412`, HWND `0xB70082`, title `RIFT` |
| Safety verdict | **Blocked for movement/proof promotion; okay for read-only coordination and family-snapshot planning** |

## TL;DR

We installed/verified external x64dbg and documented the pointer-chain workflow, but **do not attach x64dbg yet**. The current proof anchor is stale for the live process epoch: stored proof metadata points to PID `57656` / HWND `0x5417BC`, while the current RIFT target is PID `63412` / HWND `0xB70082`. ChromaLink is running and the world-state endpoint is reachable, but the player position field was still stale/not navigation-available at last check, so it is **not proof-grade API-now truth yet**. The next best path is to stabilize fresh ChromaLink/API coordinate truth, then use **current-PID family snapshot scanning** instead of individual offset probing.

## Current safety boundaries

| Boundary | Current state |
|---|---|
| Cheat Engine | **Not authorized / not used** |
| x64dbg attach to RIFT | **Not authorized yet / not done** |
| Movement/input | **Not sent** |
| RiftScan | Read-only provider boundary preserved |
| ChromaLink | Provider repo boundary preserved; helpers started, no provider source edits |
| SavedVariables | Historical/stale seed only, not live coordinate truth |

## Completed this session

| Area | Result |
|---|---|
| x64dbg install | User installed latest snapshot at `C:\RIFT MODDING\Tools\x64dbg` |
| x64dbg verification | Verified `release\x64\x64dbg.exe`; smoke-launched and closed cleanly; no RIFT attach |
| x64dbg release notes | Reviewed `C:\RIFT MODDING\Tools\x64dbg\release\release-notes.md`; April 2026 / `2026.04.20` snapshot is appropriate |
| Repo docs/scripts | Added x64dbg pointer-chain workflow and updated x64dbg launcher docs |
| Previous commit/push | `f95e371` pushed to `origin/main` |
| RiftScan milestone review | Ran current strategy gate; result `blocked`, no movement allowed |
| ChromaLink coordination | Started existing HTTP bridge and CLI watch helpers; no ChromaLink source edits |
| Workflow pivot | Agreed that targeted family snapshots + batch scanning should replace individual offset probing |

## Current live target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `63412` |
| HWND | `0xB70082` |
| Title | `RIFT` |
| Foreground | `False` |
| Rect | Left `-1928`, Top `349`, Right `8`, Bottom `1397`, Width `1936`, Height `1048` |
| Start time | `2026-05-12T11:53:24.4410214-04:00` |
| Responding | `True` |

## ChromaLink status at handoff

| Item | Value |
|---|---|
| HTTP bridge process | `ChromaLink.HttpBridge.exe` PID `74552` |
| Telemetry watcher | `dotnet` PID `72016`; child `ChromaLink.Cli.exe` PID `59348` |
| World-state URL | `http://127.0.0.1:7337/api/v1/riftreader/world-state` |
| Last HTTP check | `HTTP 200`, top-level `ok=true`, `ready=true`, `fresh=true`, `stale=false` |
| Important caveat | `navigation.playerPositionAvailable=false`; `player.position.fresh=false`, `stale=true`, age about `72s` at sample time |
| Last seen position payload | `x=7376.87`, `y=863.82`, `z=2990.35`, observed `2026-05-12T18:59:15.3183812Z` |
| Proof-grade? | **No** — endpoint reachable, but coordinate field not fresh/navigation-available yet |

## RiftScan / proof-anchor status

| Item | Value |
|---|---|
| Current proof pointer file | `docs\recovery\current-proof-anchor-readback.json` |
| Proof pointer target in file | PID `57656`, HWND `0x5417BC`, process `rift_x64` |
| Current live target | PID `63412`, HWND `0xB70082` |
| Verdict | **Stale target epoch; do not use for movement/proof promotion** |
| RiftScan review artifact | `scripts\captures\riftscan-milestone-review-20260512-185050.json` and `.md` |
| RiftScan review result | `blocked` / `block` |
| Key blockers | `selected-candidate-present` failed; `target-pointer-match` failed |
| Specific mismatch | `pointer_pid_mismatch:actual=57656;expected=63412`; `pointer_hwnd_mismatch:actual=0x5417BC;expected=0xB70082` |

## Important artifacts

| Path | Why it matters |
|---|---|
| `docs\recovery\x64dbg-pointer-chain-workflow.md` | New documented safe x64dbg workflow |
| `scripts\open-x64dbg.ps1` | Launcher now prefers external x64dbg install path |
| `tools\reverse-engineering\README.md` | Documents external x64dbg install as preferred |
| `docs\recovery\README.md` | Links x64dbg workflow |
| `scripts\captures\x64dbg-preflight-20260512-140936\x64dbg-preflight-summary.json` | Preflight artifact; attach blocked until explicit approval |
| `scripts\captures\x64dbg-forward-eval-20260512-144219\x64dbg-forward-eval-summary.json` | Forward evaluation artifact; blocked on API/runtime coordinate freshness |
| `scripts\captures\rift-api-reference-scan-currentpid-63412-20260512-184223.json` | RRAPICOORD1 marker scan; no usable API-now marker proof |
| `scripts\captures\riftscan-milestone-review-20260512-185050.json` | Combined RiftScan/RiftReader strategy gate for current target |
| `C:\RIFT MODDING\Tools\x64dbg\release\release-notes.md` | Reviewed local x64dbg snapshot notes |

## Resume instruction for new chat

Paste this first in the next chat:

```text
Resume RiftReader from docs/handoffs/2026-05-12-150152-x64dbg-family-snapshot-coordination-handoff.md. Keep ChromaLink as provider, RiftReader as consumer, and RiftScan read-only unless explicitly authorized. Do not use CE, do not send movement, and do not attach x64dbg until explicit current-target approval. First stabilize fresh ChromaLink/API coordinate truth for current PID/HWND, then run current-PID family snapshot scanning instead of individual offset probing.
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Re-check current RIFT PID/HWND with `scripts\get-rift-window-targets.ps1 -Json` | Prevents target drift before any proof work |
| 2 | Stabilize ChromaLink world-state until `player.position.fresh=true` and navigation position is available | Needed for API-now/runtime-now coordinate truth |
| 3 | Keep ChromaLink helper processes running only if they continue producing fresh telemetry | Avoids chasing stale provider output |
| 4 | If ChromaLink position remains stale, inspect visibility/capture conditions for the RIFT overlay/telemetry strip | The current RIFT window is not foreground and spans negative X coordinates |
| 5 | Run current-PID family snapshot scanning once fresh API truth exists | Saves time versus individual offset probing |
| 6 | Score grouped candidate families across multiple poses before using x64dbg | Reduces false positives and single-pose coincidences |
| 7 | Re-run `scripts\riftscan_milestone_review.py` after the first current-PID family candidate batch | Keeps RiftReader/RiftScan gates aligned |
| 8 | Use x64dbg only on top-ranked current-PID families, and only after explicit attach approval | Keeps debugger use surgical and low-risk |
| 9 | Watch 12-byte vec3 windows rather than isolated 4-byte floats in debugger/proof work | Preserves X/Y/Z access relationships |
| 10 | Promote nothing until same-target multi-pose proof and restart/reacquisition validation pass | Prevents stale pointer chains from becoming navigation truth |
