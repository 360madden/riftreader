# Current RIFT live truth — PID 28248 proof anchor current, x64dbg attach blocked, static actor chain not promoted

Updated UTC: `2026-05-23T06:28:30Z`
Repo: `C:\RIFT MODDING\RiftReader`

## Verdict

The current RIFT target is **in-world and proof-anchor current** for PID `28248` / HWND `0x2302BC`. Same-target `ProofOnly` passed for proof anchor `0x2D409F3BBE0`, and the read-only RiftScan/RiftReader milestone gate now reports `ready-for-read-only-proof`.

The player actor static coordinate chain is **not promoted**. The current proof anchor is valid current-PID movement-safety evidence, but it is still a heap address and must be reacquired after target drift/restart. A bounded x64dbg stop-context attach retry was attempted after the proof/readiness refresh; it failed before a debug session started, so no access/static provenance was captured.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `28248` |
| HWND | `0x2302BC` |
| Process start UTC | `2026-05-23T04:33:26.7814151Z` |
| Module base | `0x7FF747730000` |
| Proof anchor | `0x2D409F3BBE0` |
| Proof status | `current-target-proofonly-passed` |
| Latest proof coordinate | `X=7371.4150390625`, `Y=868.0927124023438`, `Z=2997.306884765625` |
| Proof artifact | `docs/recovery/current-proof-anchor-readback.json` |

## Current coordinate proof status

| Field | Value |
|---|---|
| Candidate ID | `api-family-hit-000001` |
| Candidate file | `scripts/captures/family-scan-currentpid-28248-20260523-053403-077701/api-family-vec3-candidates.jsonl` |
| Readback summary | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-28248-readback-summary-20260523-013808.json` |
| ProofOnly run | `C:\RIFT MODDING\RiftReader\scripts\captures\recover-currentpid-coord-anchor-fast-execute-28248-20260523-053152-550559\07-proofonly\live-test-ProofOnly-20260523-053732\run-summary.json` |
| Recovery summary | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-28248-20260523-053152-550559/summary.json` |
| RiftScan milestone review | `scripts/captures/riftscan-milestone-review-20260523-054443.json` |
| Coordinate readiness gate | `scripts/captures/coordinate-proof-readiness-gate-20260523-054451-435504/summary.json` |
| Actor-chain no-debug status | `scripts/captures/actor-chain-no-debug-status-20260523-055040-185416/summary.json` |
| Current-PID no-debug scan batch | `scripts/captures/coordinate-scan-plan-batch-currentpid-28248-20260523-060339-224933/summary.json` |
| x64dbg environment probe | `scripts/captures/x64dbg-attach-environment-probe-20260523-061423-261651/summary.json` |
| x64dbg attach retry | `scripts/captures/x64dbg-live-access-capture-20260523-062455-703468/summary.json` |
| Proof support count | `3` |
| Best max abs distance | `0.006518554687431788` |
| Movement gate | `allowed=true`, but per-run preflight still required |

## Static-chain blockers

- `blocked-no-debugger-access-provenance`: no debugger/watchpoint evidence captured.
- `x64dbg-stop-context-attach-command-rejected-current-pid-28248`: bounded stop-context attach retry failed before debug session start; commands `attach 0x6e58`, `attach 6e58`, and `AttachDebugger 6e58` were rejected.
- `no-module-rva-static-owner-resolver-promoted`: no restart-stable resolver exists yet.
- `not-restart-validated`: no actor/static resolver has survived restart/relog validation.
- `actor-static-chain-not-reacquired-for-current-pid-28248`: the prior PID `67680` actor-like candidate is now historical.
- `actor-candidate-readback-not-passed`: no current-PID actor-chain candidate readback has been promoted.
- Actor yaw/facing remains blocked until current-target behavior-backed proof is separately revalidated.

## Safety ledger for latest update

| Operation | Used? |
|---|---:|
| Read-only target discovery | Yes |
| Fresh ChromaLink/API reference | Yes |
| Read-only process memory read | Yes |
| Approved bounded movement for displacement proof | Yes |
| Final ProofOnly movement/input | No |
| x64dbg/debugger attach | Attempted; failed before debug session start |
| Breakpoints/watchpoints | No |
| Cheat Engine | No |
| Memory writes | No |
| Provider writes | No |
| Git mutation | No |

## Historical rollover

The prior current-truth PID `67680` / HWND `0x120CBE` state was archived before this update:

- `C:\RIFT MODDING\RiftReader\docs\recovery\historical\current-truth-2026-05-23-pid67680-hwnd120CBE-historical-before-pid28248-proof-refresh.json`
- `C:\RIFT MODDING\RiftReader\docs\recovery\historical\current-truth-2026-05-23-pid67680-hwnd120CBE-historical-before-pid28248-proof-refresh.md`
- `docs/recovery/historical/current-proof-anchor-readback-2026-05-23-pid67680-hwnd120CBE-historical.json`

## Required next step

Use the current proof anchor/readiness as the safe coordinate baseline. The immediate x64dbg attach route is currently blocked by command rejection before debug session start, so the next practical actor-chain path is either no-debug/read-only reacquisition or environment-level attach diagnosis without breakpoints/watchpoints. Do not promote an actor static chain until resolver, multi-pose API-now vs chain-now, restart/relog, and final ProofOnly gates pass.
