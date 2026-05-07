# RiftReader Handoff — RiftScan-first proof anchor + forward smoke

Created: 2026-05-06T23:31:10-04:00 / 2026-05-07T03:31:10Z
Repo: `C:\RIFT MODDING\RiftReader`
Branch at handoff creation: `main`
Base commit before handoff file: `114a5dd Use RiftScan coordinate candidates for proof anchor`
Target from latest live proof: `rift_x64` PID `47560`, HWND `0x2122E`

## TL;DR

The resumed live movement lane was corrected to use **RiftScan as the primary coordinate-candidate source**. RiftScan produced candidate `rift-addon-coordinate-candidate-000001` at `0x2400EA32120`; RiftReader imported it, validated it against live UI/reference readback, promoted it into `scripts\captures\telemetry-proof-coord-anchor.json`, and successfully ran a proof-gated `1000 ms W` forward pulse.

The code/docs slice was committed and pushed as:

- `114a5dd Use RiftScan coordinate candidates for proof anchor`

This handoff exists to resume later in a new chat without re-discovering the same context.

## Hard safety boundaries

| Boundary | Status |
|---|---|
| Cheat Engine / CE Lua / debugger / watchpoints | **Do not use** unless explicitly reauthorized in the new conversation after crash-risk acknowledgement |
| SavedVariables as live truth | **Do not use** for live movement truth; treat as post-save snapshot only |
| Live input | Only after exact PID/HWND bind + focus + screenshot + fresh proof-anchor current-readback preflight |
| Proof age | Short-lived; the latest recorded valid preflight is historical by the time a new chat resumes |
| Candidate source | Prefer RiftScan first; do not fall back to weak heuristic/current-player caches for movement proof |

## Current committed truth files

| File | Purpose |
|---|---|
| `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md` | Human-readable current truth; updated to RiftScan-first proof |
| `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` | Machine-readable pointer to the latest proof/readback state |
| `C:\RIFT MODDING\RiftReader\docs\recovery\README.md` | Recovery entrypoint; updated with current no-CE coord proof note |
| `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json` | Current local proof-anchor cache artifact; session/time-bound |

## Fresh RiftScan candidate evidence

| Field | Value |
|---|---|
| RiftScan repo | `C:\RIFT MODDING\Riftscan` |
| RiftScan session | `C:\RIFT MODDING\Riftscan\sessions\codex-current-coord-region-passive-20260506-230940` |
| RiftScan match file | `C:\RIFT MODDING\Riftscan\reports\generated\codex-current-coord-region-passive-20260506-230940-addon-coordinate-matches.json` |
| Candidate ID | `rift-addon-coordinate-candidate-000001` |
| Candidate absolute address | `0x2400EA32120` |
| Source region | `region-001892` |
| Source base / offset | `0x2400E970000 + 0xC2120` |
| Axis order | `xyz` |
| Support | `3` snapshots |
| Best max abs distance | `0` |

## Latest proof-anchor/readback state

| Item | Value |
|---|---|
| Proof anchor generated | `2026-05-07T03:22:38.8570044Z` |
| Proof method | `no-ce-riftscan-reference-multisample` |
| Canonical source kind | `riftscan-reference-validated-candidate` |
| Promotion poses | Pose B -> Pose C |
| Max reference planar displacement | `1.2165525060594347` |
| Max candidate/reference delta error | `0.0368164062501819` |
| Latest current-readback summary | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-232245.json` |
| Latest status at capture time | `valid`, `MovementAllowed=true` |
| Latest proof-anchor age gate | `ProofAnchorMaxAgeSeconds=60` |
| Latest coord | `X=7437.0498046875`, `Y=885.2205810546875`, `Z=3054.30517578125` |

Important: because `ProofAnchorMaxAgeSeconds=60`, the latest recorded valid state should be treated as a **historical proof checkpoint** when resuming later. Revalidate before live movement.

## Forward pulse proof

| Item | Value |
|---|---|
| Input | Exact-window `W`, `1000 ms` |
| Baseline screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260506-232057-700.png` |
| Changed screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260506-232107-504.png` |
| Final screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260506-232110-751.png` |
| Pre-readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-232031.json` |
| Post-readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-232117.json` |
| Movement delta | `dX=0.23681640625`, `dY=0`, `dZ=-1.21630859375`, planar `1.2391483387792066` |

## Code changes in pushed commit `114a5dd`

| File | Change |
|---|---|
| `scripts\import-riftscan-coordinate-candidates.ps1` | Direct support for RiftScan addon-coordinate match JSON: `source_base_address_hex`, `source_offset_hex`, `support_count`, `best_memory_x/y/z` |
| `scripts\invoke-riftscan-coordinate-readback.ps1` | Decode-only summaries preserve process/HWND from watchset |
| `scripts\test-import-riftscan-coordinate-candidates.ps1` | Added direct RiftScan match fixture |
| `scripts\test-invoke-riftscan-coordinate-readback-decode.ps1` | Added process/HWND preservation assertions |
| `docs\recovery\current-truth.md` | Updated current truth to RiftScan-first proof |
| `docs\recovery\README.md` | Updated recovery start point |
| `docs\recovery\current-proof-anchor-readback.json` | Added tracked pointer to latest proof/readback state |

## Validation already passed before push

| Validation | Result |
|---|---|
| `scripts\test-import-riftscan-coordinate-candidates.ps1` | Passed |
| `scripts\test-invoke-riftscan-coordinate-readback-decode.ps1` | Passed |
| `scripts\test-promote-riftscan-reference-match-to-proof-anchor.ps1` | Passed |
| `scripts\test-invoke-riftscan-coordinate-readback-proof-gate.ps1` | Passed |
| `docs\recovery\current-proof-anchor-readback.json` JSON parse | Passed |
| `git diff --cached --check` | Passed before commit |

## Resume checklist for new chat

1. `cd C:\RIFT MODDING\RiftReader`
2. `git pull --ff-only`
3. Read this handoff first, then read:
   - `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
   - `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json`
4. Re-check live target with exact PID/HWND. Do **not** assume PID `47560` / HWND `0x2122E` survived.
5. If the same process/window is still live, run:
   ```powershell
   pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\assert-current-proof-coord-anchor-readback.ps1 -ProcessId 47560 -TargetWindowHandle 0x2122E -Json
   ```
6. Only if that returns `Status=valid` and `MovementAllowed=true`, use the `rift-window-control` bind/focus/capture/input/wait/capture loop for any live movement.
7. If preflight fails stale or PID/HWND changed, reacquire candidates using RiftScan first; do not use CE or heuristic cached anchors.
8. Next preferred live test: short waypoint route with about 5m arrival radius, not a blind long run.

## Ready-to-paste resume prompt

```text
Resume from handoff: C:\RIFT MODDING\RiftReader\docs\\handoffs\\2026-05-06-233226-riftscan-first-proof-anchor-resume-handoff.md

Goal: continue the RiftScan-first no-CE movement proof lane. Read the handoff, then inspect current git status and docs/recovery/current-proof-anchor-readback.json. Do not use Cheat Engine or SavedVariables as live truth. Before any live input, re-bind the exact Rift window, rerun assert-current-proof-coord-anchor-readback.ps1 for the current PID/HWND, and only proceed if Status=valid and MovementAllowed=true. If the proof is stale or PID/HWND changed, coordinate with C:\RIFT MODDING\Riftscan to acquire fresh coordinate candidates first.
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | `git pull --ff-only` in the new chat | Ensures the pushed RiftScan-first commit and this handoff are present |
| 2 | Re-read `current-proof-anchor-readback.json` | It is the fastest machine-readable truth pointer |
| 3 | Re-bind exact live PID/HWND | Prevents wrong-window input |
| 4 | Rerun proof-anchor current-readback preflight | Required because the age gate is short-lived |
| 5 | If stale, use RiftScan to reacquire candidates first | RiftScan produced the strongest candidate surface |
| 6 | Avoid CE unless explicitly reauthorized | Current path works without CE crash risk |
| 7 | Avoid SavedVariables as live truth | Prevents stale snapshot contamination |
| 8 | Run one proof-gated short movement before route work | Confirms live movement remains safe |
| 9 | Move next to a short waypoint route with 5m radius | Converts forward pulse proof into nav proof |
| 10 | Add a one-command RiftScan import/promote wrapper | Reduces manual coordination errors |
