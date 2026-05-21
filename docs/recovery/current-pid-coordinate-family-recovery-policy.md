# Current-PID Coordinate Family Recovery Policy

Created: 2026-05-10 10:30 EDT / 2026-05-10 14:30 UTC
Scope: RiftReader proof-anchor recovery after target drift, client restart, PID/HWND change, or stale proof-pointer rejection.

## Hard rule

When the tracked proof pointer does not match the current live target PID/HWND, **do not probe the old address plus a few nearby offsets**.

The correct recovery path is a **broad current-PID coordinate-family scan**:

1. prove or rediscover the new live PID/HWND;
2. immediately invalidate `docs/recovery/current-proof-anchor-readback.json` to
   `status=blocked-target-drift` for the discovered PID/HWND if the old pointer
   targets another PID/HWND;
3. preserve the old pointer under `docs/recovery/historical/` and treat its
   `candidateId`, `matchFile`, absolute address, readbacks, and
   `movementAllowed=true` fields as historical hints only;
4. prove the new live target with target-control and visual gate;
5. capture a fresh live `RRAPICOORD` / API-runtime coordinate reference;
6. scan the current process memory broadly for matching float32 XYZ triplets;
7. if exact/current copies drift between scans, scan the **entire family** and include `--scan-stride 1` to catch unaligned payloads;
8. write a candidate family file such as `api-family-vec3-candidates.jsonl`;
9. validate candidates with no-CE readback across at least two poses;
10. promote only after cross-pose evidence proves the same candidate/source family;
11. run fresh same-target `ProofOnly`;
12. update `current-proof-anchor-readback.json` to a proof-passed pointer and update `current-truth.md` only after proof passes.

This policy exists to prevent regression into narrow stale-pointer probing after a restart or target drift.

## Boundary: proof-anchor recovery is not static actor-chain discovery

This policy is the correct workflow for rebuilding a **movement-safe current
proof anchor** after target drift or restart. It is not the optimized workflow
for proving a restart-stable player actor static chain once the proof anchor is
already current.

| Lane | Correct trigger | Correct next step |
|---|---|---|
| Proof-anchor recovery | Proof pointer is stale, missing, or target-drifted | Broad current-PID coordinate-family scan, multi-pose validation, same-target `ProofOnly` |
| Actor static-chain discovery | Proof anchor is current and an actor-like candidate exists | Stop repeating broad value scans; pivot to owner layout, bounded access provenance, resolver generation, API-now vs chain-now validation, and restart validation |

Durable actor-chain workflow:
`docs/recovery/optimized-player-actor-coordinate-chain-workflow.md`.

Anti-regression rule: never promote a proof/API-family anchor as the player
actor static chain, and never keep broad-scanning proof-anchor families when the
active task is to prove static actor provenance for an already-selected
actor-like candidate.

## Stale-data invariant

Once the current PID/HWND is known, that live target identity wins over every
cached artifact. Code must not use a current-proof pointer whose `target`
metadata differs from the discovered PID/HWND, even if the stale pointer says
`status=current-target-proofonly-passed` or `movementAllowed=true`.

Required stale-pointer behavior:

| Situation | Required code behavior |
|---|---|
| Old pointer PID/HWND differs from discovered PID/HWND | Archive the old JSON under `docs/recovery/historical/`, then replace `current-proof-anchor-readback.json` with a `blocked-target-drift` blocker for the discovered target. |
| A helper needs a candidate ID | Prefer an explicit current candidate file or same-target proof anchor; otherwise fall back to profile config. Never read `candidateId` from a mismatched pointer. |
| A helper needs a match file | Only use a match file from a same-target pointer, an explicit candidate file, or a same-PID current scan. |
| Old pointer contains useful family hints | Copy them into `staleProofPointer.preservedEvidence` or handoff notes as reacquisition hints only. |
| Movement/navigation is requested | Block until fresh same-target `ProofOnly` replaces the blocker with a proof-passed pointer. |

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
python .\scripts\scan_current_pid_coordinate_family.py --pid <PID> --hwnd <HWND> --process-name rift_x64 --tolerance 0.25 --max-hits 2048 --scan-stride 1 --max-seconds 300 --json
Write-Host "RIFTREADER_FULL_FAMILY_SCAN_DONE"
```

The helper is read-only. It sends no movement, no key input, no `/reloadui`, no screenshot-key input, and uses no Cheat Engine.

When a broad current-family window is already known, preserve the entire family shape instead of only the closest offsets:

```powershell
cd "C:\RIFT MODDING\RiftReader"
python .\scripts\capture_current_pid_coordinate_family_snapshot.py --pid <PID> --hwnd <HWND> --process-name rift_x64 --min-address <FAMILY_START> --max-address <FAMILY_END> --scan-stride 1 --window-x 256 --window-y 64 --window-z 256 --near-tolerance 0.25 --json
Write-Host "RIFTREADER_FULL_FAMILY_SNAPSHOT_DONE"
```

The snapshot helper is also read-only and candidate-only. It is meant to expose copy/ring/source-family structure before debugger work.

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

## May 13 update: unaligned copy-family discovery

The PID `60628` recovery found a failure mode this policy must preserve:

| Finding | Evidence / rule |
|---|---|
| Aligned-only scans can miss the freshest coordinate copy. | Current coordinate payloads in the `0x1FF07570000` destination family were often unaligned. |
| `--scan-stride 1` is required for this family. | The best current candidate was `0x1FF0757215A`; duplicate `0x1FF07572183`; both were invisible to aligned-only scanning. |
| Exact destination addresses still move. | Aligned candidates such as `0x1FF075700AC`, `0x1FF075704E8`, `0x1FF07571240`, and `0x1FF075719E4` were useful evidence but not stable truth. |
| Broad family snapshot remains the correct strategy. | `scripts/capture_current_pid_coordinate_family_snapshot.py` recorded the current family shape and near-reference clusters without movement or memory writes. |
| x64dbg is useful only after family ranking. | Page memory breakpoints caught the copy path; exact-address hardware watchpoints on destination slots timed out. |
| The source lead is more important than the copy slot. | At `rift_x64.exe+0x47D533`, `rdx = [r14] = 0x1FF6D600020`; source buffer `rdx + 0x28` held current XYZ. |
| Promotion is still blocked. | Pointer scans found heap refs only; no restart-stable static pointer chain or same-target `ProofOnly` proof anchor exists for PID `60628`. |

Durable artifacts:

- Handoff: `docs/handoffs/2026-05-13-0539-currentpid-60628-unaligned-coordinate-copy-truth.md`
- Code/doc checkpoint: `132fa64 Recover unaligned coordinate copy evidence`
- Best unaligned scan: `scripts/captures/family-scan-currentpid-60628-20260513-053508/family-scan-summary.json`
- Broad snapshot: `scripts/captures/coordinate-family-snapshot-currentpid-60628-20260513-053557/family-snapshot-summary.json`
- x64dbg caller capture: `scripts/captures/x64dbg-live-access-capture-20260513-053859-682586/summary.json`

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
