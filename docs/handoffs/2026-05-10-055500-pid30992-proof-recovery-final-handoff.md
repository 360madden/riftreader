# PID 30992 proof recovery final handoff

Created: 2026-05-10 05:55 EDT / 2026-05-10 09:55 UTC  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`  
Status: `proof-recovered-docs-current`

## TL;DR

RIFT client restart recovery succeeded for `rift_x64` PID `30992`, HWND `0xD1008`.

The previous proof pointer for PID `49504` / HWND `0x5121A` was correctly treated as stale target-epoch evidence. A broad current-PID coordinate-family scan found the current coordinate family, two no-CE displaced readback poses promoted `api-family-hit-000001` at `0x1E804B53C18`, and fresh same-target `ProofOnly` passed. `docs\recovery\current-proof-anchor-readback.json` and `docs\recovery\current-truth.md` were updated and pushed.

No automated movement/input, no `/reloadui`, no screenshot-key input, and no Cheat Engine were used during reacquisition. The user manually displaced the character between proof poses.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `30992` |
| HWND | `0xD1008` |

## Current proof pointer

| Fact | Value |
|---|---|
| Pointer file | `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` |
| Pointer status | `current-target-proofonly-passed` |
| Last updated UTC | `2026-05-10T09:53:44.001874+00:00` |
| Candidate | `api-family-hit-000001` |
| Candidate address | `0x1E804B53C18` |
| Latest ProofOnly run | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260510-095259\run-summary.json` |
| Latest readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-30992-readback-summary-20260510-055339.json` |
| Current coordinate snapshot | `X=7402.0341796875`, `Y=871.7628173828125`, `Z=3026.4580078125` at `2026-05-10T09:53:43.5120419Z` |

## Reacquisition chain

| Step | Result |
|---|---|
| Restart target detected | PID `30992`, HWND `0xD1008` |
| Target-control | Passed, exact-HWND foreground |
| Visual gate | Passed before ProofOnly attempt |
| Old pointer handling | PID `49504` / HWND `0x5121A` pointer rejected as target drift and archived |
| Reference-capture bug fix | `RRAPICOORD1|status=starting|savedVariablesUse=none` partial startup markers now skipped instead of crashing capture |
| Passive RiftScan candidate generation/readback | Ran with authorization; produced stable candidates but `ReferenceMatchCount=0` |
| Broad family scan | Found current-PID XYZ family; best hit `0x1E804B53C18` |
| Family candidate readback | `23/23` reference matches against fresh RRAPICOORD |
| Pose A | Captured with `api-family-hit-000001` |
| Pose B | Re-read top 23 Pose A candidates after manual displacement; `23/23` reference matches |
| Promotion | Validated no-CE multisample proof anchor |
| Fresh ProofOnly | Passed and updated tracked pointer |
| Current truth | Updated to PID `30992` state |

## Key artifacts

| Artifact | Path |
|---|---|
| Family candidate file | `C:\RIFT MODDING\RiftReader\scripts\captures\family-scan-currentpid-30992-20260510-082207\api-family-vec3-candidates.jsonl` |
| Pose A readback summary | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-proof-pose-a-currentpid-30992-family-20260510-092123\riftscan-riftreader-currentpid-30992-readback-wrapper-summary-20260510-052153.json` |
| Pose B successful readback summary | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-riftreader-currentpid-30992-readback-wrapper-summary-20260510-054646.json` |
| Promotion output | `C:\RIFT MODDING\RiftReader\scripts\captures\promote-currentpid-30992-family-proof-anchor-20260510-055125.json` |
| Proof anchor | `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json` |
| ProofOnly run | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260510-095259\run-summary.json` |
| Proof readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-30992-readback-summary-20260510-055339.json` |
| Historical pointer archive | `C:\RIFT MODDING\RiftReader\docs\recovery\historical\current-proof-anchor-readback-2026-05-10-pid49504-hwnd5121A-historical.json` |

## Important commits

| Commit | Meaning |
|---|---|
| `04158d8` | Skip partial `RRAPICOORD` startup/progress markers during reference capture |
| `44695ab` | Document Python-first reusable helper policy |
| `3806c62` | Document Python helper logging criteria |
| `d66d276` | Add current-PID coordinate family scan helper |
| `1bce6d1` | Refresh current proof pointer for PID `30992` |
| `92ed4dd` | Update current truth for PID `30992` proof recovery |

## Still not revalidated

| Area | Current status |
|---|---|
| Automated post-restart movement/route smoke | Not revalidated for PID `30992` |
| Actor-facing | Not promoted for PID `30992` |
| Yaw | Not promoted for PID `30992` |
| Auto-turn | Not promoted |
| Route execution | Not revalidated |

## Safety boundary

Before any bounded live input/movement:

1. rerun target-control for the exact PID/HWND;
2. rerun visual gate;
3. rerun proof preflight / fresh proof-readback;
4. use bounded movement only;
5. document and commit the result if it becomes current truth.

GitHub connector remains read-only unless explicitly overridden. Complex local workflows should be Python-first helpers with structured logging, blocker reporting, absolute paths, and fail-closed behavior.

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Current proof recovery for restarted client succeeded. Current target is `rift_x64` PID `30992`, HWND `0xD1008`. `current-proof-anchor-readback.json` targets PID `30992` and candidate `api-family-hit-000001` at `0x1E804B53C18`. Fresh `ProofOnly` passed in `scripts\captures\live-test-ProofOnly-20260510-095259\run-summary.json`. `current-truth.md` was updated and pushed in commit `92ed4dd`. No automated movement/input or CE was used; user manually displaced character between proof poses. Next work should not assume post-restart movement, actor-facing, yaw, auto-turn, or route truth until revalidated with fresh target-control, visual gate, proof preflight, and bounded live input.
