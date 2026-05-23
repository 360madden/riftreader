# Current RIFT live truth — no live target; PID 28248 proof is historical

Updated UTC: `2026-05-23T06:47:00Z`
Repo: `C:\RIFT MODDING\RiftReader`

## Verdict

The previously recovered PID `28248` / HWND `0x2302BC` proof anchor is now **historical only**. After the local milestone commit, the live target drifted: `coordinate_recovery_status.py --json` blocked with `artifact-target-pid-not-running:artifact=28248;live=28496`, and a later process check found no live `rift_x64` process.

ChromaLink is also **provider-stale** and cannot currently provide API-now player position truth. Movement/proof promotion is blocked until a new live in-world PID/HWND passes same-target recovery and final `ProofOnly`.

## Last valid historical target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `28248` |
| HWND | `0x2302BC` |
| Process start UTC | `2026-05-23T04:33:26.7814151Z` |
| Module base | `0x7FF747730000` |
| Proof anchor | `0x2D409F3BBE0` |
| Historical ProofOnly status | `passed-proof-only` |
| Latest historical coordinate | `X=7371.4150390625`, `Y=868.0927124023438`, `Z=2997.306884765625` |
| Historical proof archive | `docs/recovery/historical/current-proof-anchor-readback-2026-05-23-pid28248-hwnd2302BC-historical-after-target-drift.json` |
| Historical truth archive | `docs/recovery/historical/current-truth-2026-05-23-pid28248-hwnd2302BC-historical-after-target-drift.json` |

## Drift / closure evidence

| Check | Result |
|---|---|
| Coordinate recovery status | Blocked at `2026-05-23T06:43:26Z`: `artifact-target-pid-not-running:artifact=28248;live=28496` |
| Brief replacement observation | PID `28496`, HWND `0x9121A`, module base `0x7FF7A3830000`, start UTC `2026-05-23T06:40:40.099749Z` |
| ChromaLink freshness | Blocked: `provider-stale`, `player-position-missing`, `rift-process-missing` |
| ChromaLink artifact | `C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink\artifacts\diagnostics\chromalink-ensure-fresh-20260523T064352Z\summary.json` |
| Pointer-family scan retry | Blocked cleanly with `target-window-not-found`: `scripts/captures/pointer-family-scan-20260523-064638-227102/summary.json` |

## Current blockers

- `target-drift-no-live-rift-target`: no current in-world PID/HWND proof surface is live.
- `provider-stale-player-position-missing`: ChromaLink is stale and player position is not usable as API-now truth.
- `blocked-target-drift`: `docs/recovery/current-proof-anchor-readback.json` now records the PID `28248` proof as stale/historical.
- `actor-static-chain-not-reacquired-for-current-pid`: no current-PID actor/static-chain candidate exists.
- `no-static-resolver-promoted` / `not-restart-validated`: no restart-stable actor resolver exists.

## Safety ledger for latest update

| Operation | Used? |
|---|---:|
| Read-only process/window checks | Yes |
| ChromaLink freshness/status check | Yes |
| Pointer-family scan retry | Attempted; blocked before scan because target was not found |
| Movement/game input | No |
| x64dbg/debugger attach | No new attach after drift |
| Breakpoints/watchpoints | No |
| Cheat Engine | No |
| Memory writes | No |
| Provider writes | No |
| Git push | No |

## Required next step

Restore a live RIFT in-world target and ChromaLink freshness first. Once a live PID/HWND is present at supported geometry, run a new current-target recovery/ProofOnly pass before any movement, actor-chain scan, or proof promotion. Treat all PID `28248` addresses as historical reacquisition hints only.
