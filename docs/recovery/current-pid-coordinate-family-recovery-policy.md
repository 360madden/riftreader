# Current-PID Coordinate Family Recovery Policy

Created: 2026-05-10 10:30 EDT / 2026-05-10 14:30 UTC  
Scope: RiftReader proof-anchor recovery after target drift, client restart, PID/HWND change, or stale proof-pointer rejection.

## Hard rule

When the tracked proof pointer does not match the current live target PID/HWND, **do not probe the old address plus a few nearby offsets**.

The correct recovery path is a **broad current-PID coordinate-family scan**:

1. prove the new live target with target-control and visual gate;
2. capture a fresh live `RRAPICOORD` / API-runtime coordinate reference;
3. scan the current process memory broadly for matching float32 XYZ triplets;
4. write a candidate family file such as `api-family-vec3-candidates.jsonl`;
5. validate candidates with no-CE readback across at least two poses;
6. promote only after cross-pose evidence proves the same candidate family;
7. run fresh same-target `ProofOnly`;
8. update `current-proof-anchor-readback.json` and `current-truth.md` only after proof passes.

This policy exists to prevent regression into narrow stale-pointer probing after a restart or target drift.

## Trigger conditions

Use this policy when any of these occur:

| Trigger | Required response |
|---|---|
| `ProofOnly` reports `blocked-target-drift` | Treat the tracked proof pointer as stale; start current-PID family scan. |
| `current_proof_pointer_pid_mismatch` | Reject the old pointer; do not run movement. |
| `current_proof_pointer_hwnd_mismatch` | Reject the old pointer; do not run movement. |
| RIFT client restarted | Treat all absolute proof addresses as historical until re-proven. |
| target-control finds a new PID/HWND | Re-run visual gate, then current-PID family scan if proof pointer still targets an older epoch. |
| old readback address fails | Do not search only nearby offsets; scan the coordinate family broadly in the current PID. |

## Explicit anti-patterns

These are forbidden as default recovery behavior:

| Anti-pattern | Why it is wrong |
|---|---|
| Reuse the stale absolute address directly | Absolute addresses drift across process epochs. |
| Probe only the old address and nearby offsets | The valid family may relocate far away. |
| Treat SavedVariables / `ReaderBridgeExport.lua` as live truth | SavedVariables are post-save snapshots, not live IPC. |
| Run `ProofOnly` repeatedly without refreshing candidates | It will continue to block on target drift or stale pointer state. |
| Run movement to test whether coordinates are right | Movement is blocked until target-control, visual gate, proof preflight, and fresh proof all pass. |
| Promote a single-pose match | A single pose is candidate evidence only, not proof. |
| Use Cheat Engine as a fallback without explicit current authorization | Current no-CE lane must fail closed unless CE is re-authorized. |

## Required command shape

After discovering the current PID/HWND and passing target-control + visual gate, run the broad scan helper:

```powershell
cd "C:\RIFT MODDING\RiftReader"
python .\scripts\scan_current_pid_coordinate_family.py --pid <PID> --hwnd <HWND> --process-name rift_x64 --tolerance 0.25 --max-hits 2048 --max-seconds 300 --json
Write-Host "RIFTREADER_FULL_FAMILY_SCAN_DONE"
```

The helper is read-only. It sends no movement, no key input, no `/reloadui`, no screenshot-key input, and uses no Cheat Engine.

## Required evidence contract

The scan result is only the first stage. A passing scan must provide:

| Artifact / field | Meaning |
|---|---|
| `status=passed` | Scan completed and found candidate XYZ triplets. |
| `hitCount > 0` | Candidate family evidence exists. |
| `api-family-vec3-candidates.jsonl` | Candidate file for readback and promotion stages. |
| fresh reference coordinate | The scan was anchored to a current runtime/API coordinate. |
| safety flags | `movementSent=false`, `inputSent=false`, `noCheatEngine=true`. |

A candidate file does **not** authorize movement. It only authorizes the next no-input validation stage.

## Required validation after scan

After the scan produces candidates:

1. read back the top candidates against the current fresh coordinate;
2. manually displace the character between poses when required;
3. re-read candidates after displacement;
4. require the same candidate/family to match across poses;
5. promote only after multi-pose evidence validates the candidate;
6. refresh `scripts/captures/telemetry-proof-coord-anchor.json`;
7. run same-target `ProofOnly`;
8. update `docs/recovery/current-proof-anchor-readback.json` only if same-target `ProofOnly` passes.

## Proven precedent: PID 30992 recovery

The May 10 PID `30992` recovery followed this policy:

| Step | Result |
|---|---|
| Old target | PID `49504` / HWND `0x5121A` pointer rejected as stale. |
| New target | PID `30992` / HWND `0xD1008`. |
| Broad current-PID family scan | Found current XYZ family candidates. |
| Promoted candidate | `api-family-hit-000001` at `0x1E804B53C18`. |
| Pose validation | Two no-CE displaced readback poses validated the candidate family. |
| Promotion method | `no-ce-riftscan-reference-multisample`. |
| Fresh `ProofOnly` | Passed and refreshed the tracked proof pointer. |
| Movement | No automated movement/input was used during reacquisition. |

This precedent is the model for future PID/HWND drift recovery.

## Operator decision tree

| Current state | Next action |
|---|---|
| Target missing | Rediscover RIFT process and HWND first. |
| Target-control blocked | Fix target/focus/window state first. |
| Visual gate blocked | Restore capture/focus state first. |
| `ProofOnly` blocked by target drift | Run full current-PID coordinate-family scan. |
| Family scan passes | Proceed to no-input candidate readback / multi-pose validation. |
| Family scan has no hits | Increase scan budget or investigate alternate coordinate family strategy. |
| Candidate validates across poses | Promote proof anchor, then run same-target `ProofOnly`. |
| `ProofOnly` passes | Update current proof pointer and current truth. |
| Any movement requested before proof passes | Block it. |

## Assistant behavior rule

On future resumes, if the live PID/HWND changes and `ProofOnly` blocks with target drift, the assistant must say:

> The tracked proof pointer is stale for this process epoch. Use the current-PID coordinate-family scan recovery path; do not probe the old address or nearby offsets.

Then provide the broad scan helper command for the current PID/HWND.

## Relationship to current truth

`current-truth.md` remains the authoritative state file. This policy is the durable recovery rule for rebuilding that truth when the current proof pointer becomes stale.
