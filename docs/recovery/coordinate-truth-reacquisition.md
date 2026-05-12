# Coordinate Truth Reacquisition

Version: v0.1.0
Scope: RiftReader / RiftScan recovery lane
Primary audience: human operator / future assistant
Machine companion: `docs/recovery/coordinate-truth-reacquisition.machine.md`

## Purpose

This document defines the **coordinate truth reacquisition** workflow for RiftReader after a RIFT client restart, patch, maintenance return, or target PID/HWND drift.

The goal is not merely to find an XYZ-looking memory value. The goal is to rebuild a **current, movement-grade coordinate proof anchor** for the exact live target process/window, then validate it through same-target `ProofOnly`.

A coordinate proof anchor is considered current only when:

1. the live RIFT target PID/HWND is resolved;
2. a fresh runtime/API coordinate reference is available;
3. a coordinate-family candidate is found in current process memory;
4. the candidate tracks fresh references across displaced poses;
5. the proof anchor is promoted from multi-pose evidence;
6. current readback assertion passes for the same PID/HWND;
7. same-target `ProofOnly` passes and refreshes `docs/recovery/current-proof-anchor-readback.json`.

## Current known-good example

The latest successful recovery at the time this document was created:

| Field | Value |
|---|---|
| Target process | `rift_x64` |
| PID | `57656` |
| HWND | `0x5417BC` |
| Candidate | `api-family-hit-000001` |
| Anchor address | `0xCC080EC30C` |
| Promotion status | `validated` |
| Assert status | `valid` |
| ProofOnly status | `passed-proof-only` |
| ProofOnly movement | `movementSent=false`, `movementAttempted=false` |
| Current coordinate snapshot | `X=7407.42919921875`, `Y=871.8069458007812`, `Z=3030.127685546875` |
| Snapshot time | `2026-05-12T11:10:56.4345281Z` |
| Final truth commit | `4ee32cf682639e58a1e6c0ae81121f1143de470d` |

This example proves the workflow can reacquire coordinate truth after a restart/maintenance return without Cheat Engine.

## Critical terminology

| Term | Meaning |
|---|---|
| **Coordinate data truth** | The validated relationship between a current live memory address and the real player coordinate. |
| **Current-now coordinate** | A fresh coordinate value read at a specific moment. Old values are historical snapshots, not current-now truth. |
| **Proof anchor** | The promoted coordinate memory candidate stored in `scripts/captures/telemetry-proof-coord-anchor.json`. |
| **Current proof pointer** | `docs/recovery/current-proof-anchor-readback.json`, refreshed only after same-target `ProofOnly` passes. |
| **Target epoch** | One specific RIFT process/window lifetime, identified by PID/HWND/process start. |
| **Target drift** | Any mismatch between proof pointer PID/HWND and the actual current RIFT PID/HWND. |
| **Movement stimulus** | A bounded key pulse used only to create coordinate displacement evidence. |
| **Navigation movement** | Route following, waypoint execution, auto-turn, follow behavior, or autonomous movement. Not allowed until separately validated. |

## What coordinate truth does and does not prove

Coordinate truth proves:

- the current PID/HWND has a valid coordinate proof anchor;
- memory readback can produce trustworthy XYZ for the player;
- same-target `ProofOnly` can refresh the current proof pointer.

Coordinate truth does **not** prove:

- actor yaw;
- camera yaw/pitch;
- auto-turn;
- route execution;
- waypoint navigation;
- path safety;
- stuck detection;
- combat/follow behavior.

Those require separate gated validation lanes.

## Source-of-truth files

| File | Purpose |
|---|---|
| `docs/recovery/current-proof-anchor-readback.json` | Current proof pointer. Updated only after same-target `ProofOnly` passes. |
| `docs/recovery/current-truth.md` | Human-readable current truth summary. |
| `scripts/captures/telemetry-proof-coord-anchor.json` | Runtime proof anchor cache used by proof/readback workflows. |
| `scripts/captures/latest-live-test-run.json` | Pointer to the latest live-test orchestrator run. |
| `handoffs/current/RIFTREADER_CURRENT_HANDOFF.md` | Current compact handoff. |
| `handoffs/current/RIFTREADER_CURRENT_HANDOFF.json` | Machine-readable current compact handoff. |
| `G:\My Drive\RiftReader\status\RIFTREADER_CURRENT_STATUS.md` | Drive mirror/status artifact. |
| `G:\My Drive\RiftReader\status\RIFTREADER_CURRENT_STATUS.json` | Drive mirror/status artifact. |

## Tool inventory

### Repo-owned Python control plane

| Tool | Role |
|---|---|
| `scripts/riftreader_postupdate_proof_reacquire_stage1.py` | Python-first Stage 1 control plane. Resolves target, runs visual gate, runs coordinate-family scan, and optionally collects movement-stimulus pose evidence. |
| `cmd/riftreader-postupdate-proof-reacquire-stage1.cmd` | Thin launcher for Stage 1. |
| `scripts/live_test.py --profile ProofOnly` | Same-target proof validation and current proof pointer refresh. |
| `scripts/test_riftreader_postupdate_proof_reacquire_stage1.py` | Offline unit tests for the Stage 1 helper. |

### Existing leaf helpers reused by Stage 1

| Tool | Role |
|---|---|
| `scripts/check_live_visual_gate.py` | No-input visual/focus/capture gate. |
| `scripts/rift_live_test/visual_gate_status.py` | Visual gate implementation. |
| `scripts/scan_current_pid_coordinate_family.py` | Read-only current-PID memory scan for XYZ-like coordinate triplets near a fresh runtime reference. |
| `scripts/capture-rift-api-reference-coordinate.ps1` | Captures a fresh runtime coordinate reference using `RRAPICOORD1` marker scanning. |
| `scripts/reacquire-current-pid-coordinate-anchor-batch.ps1` | Captures multiple displaced proof poses, sends bounded `W` movement stimulus when enabled, and ranks coordinate candidates. |
| `scripts/send-rift-key-csharp.ps1` | Sends bounded input stimulus through the proven C# SendInput path. |
| `scripts/invoke-riftscan-coordinate-readback.ps1` | Reads/scans coordinate candidates and compares them to fresh references. |
| `scripts/capture-riftscan-proof-pose.ps1` | Captures a proof pose against a candidate file and reference. |

### Promotion and proof helpers

| Tool | Role |
|---|---|
| `scripts/promote-riftscan-reference-match-to-proof-anchor.ps1` | Promotes multi-pose coordinate evidence to `telemetry-proof-coord-anchor.json`. |
| `scripts/assert-current-proof-coord-anchor-readback.ps1` | Confirms the promoted proof anchor reads valid/stable current coordinates for exact PID/HWND. |
| `scripts/promote-current-pid-proof-anchor-from-batch.ps1` | Older wrapper that promotes top-level `current-pid-coordinate-anchor-batch-*` runs. Do not use blindly for nested Python Stage 1 batches. |
| `riftreader-promote-stage1-and-proofonly-v0.1.0.py` | Downloaded transitional helper used to promote the latest nested Stage 1 batch and run same-target `ProofOnly`. Recommended future improvement: make this repo-owned. |

### Final truth/handoff helper

| Tool | Role |
|---|---|
| `riftreader-finalize-proofonly-truth-v0.1.0.py` | Downloaded transitional helper used to finalize `current-truth.md`, current proof pointer, handoffs, Drive status, and commit/push explicit files after `ProofOnly` passed. Recommended future improvement: make this repo-owned. |

## Normal reacquisition workflow after client restart

### Preconditions

- RIFT client is running.
- Character is fully in-world.
- Local repo is clean.
- Remote `origin/main` is current or local repo has been fast-forwarded.
- No old PID/HWND proof pointer is assumed current.
- No Cheat Engine is used.

### Stage 0 — verify repo and target readiness

Recommended local check:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
git status --short
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

Expected:

- `git status --short` is empty;
- local HEAD equals remote main unless a fast-forward is needed.

### Stage 1 — reacquire candidate family and proof-pose evidence

Primary command:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
"C:\Users\mrkoo\AppData\Local\Programs\Python\Python314\python.exe" "scripts\riftreader_postupdate_proof_reacquire_stage1.py" --visual-full --allow-movement-stimulus --json
```

Stage 1 performs:

1. live RIFT target resolution;
2. visual gate/focus/capture check;
3. fresh `RRAPICOORD1` reference capture;
4. current-PID coordinate-family scan;
5. candidate JSONL generation;
6. bounded movement-stimulus pose collection if `--allow-movement-stimulus` is set and gates pass;
7. candidate ranking across poses.

Expected promotion-ready result:

```text
status=promotion-candidate-found
ok=true
movementSent=true
batchStatus=promotion-candidate-found
candidateJsonl=<path to api-family-vec3-candidates.jsonl>
```

Stage 1 may send bounded `W` movement stimulus. It must record movement count, key, hold duration, PID/HWND, before/after coordinate evidence, and output paths.

Stage 1 does **not** promote the anchor, run `ProofOnly`, or update truth files.

### Stage 2 — promote proof anchor and run same-target ProofOnly

Use the current Python promotion runner if the batch is nested under the Python Stage 1 run. The older `promote-current-pid-proof-anchor-from-batch.ps1` only searches top-level batch directories and should not be used blindly for nested batches.

Promotion requirements:

- candidate supports at least the required number of poses;
- movement evidence is satisfied;
- max reference delta is within tolerance;
- exact PID/HWND still matches;
- readback summary files exist;
- promotion status becomes `validated`;
- assert readback status becomes `valid`;
- assert movement gate becomes `true`.

Then run same-target `ProofOnly`:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
"C:\Users\mrkoo\AppData\Local\Programs\Python\Python314\python.exe" "scripts\live_test.py" --profile ProofOnly --pid <PID> --hwnd <HWND> --process-name rift_x64 --no-gui
```

Expected:

```text
status=passed-proof-only
ok=true
movementSent=false
movementAttempted=false
currentProofPointerUpdate.updated=true
```

### Stage 3 — finalize truth and handoff

Finalize only after same-target `ProofOnly` passes.

Files to update:

- `docs/recovery/current-proof-anchor-readback.json`;
- `docs/recovery/current-truth.md`;
- `docs/recovery/historical/current-proof-anchor-readback-<date>-pid<oldpid>-hwnd<oldhwnd>-historical.json`;
- `handoffs/current/RIFTREADER_CURRENT_HANDOFF.md`;
- `handoffs/current/RIFTREADER_CURRENT_HANDOFF.json`;
- `handoffs/current/live-return-proof-recovered/<timestamp>/...`.

Drive status mirrors should also be updated:

- `G:\My Drive\RiftReader\status\RIFTREADER_CURRENT_STATUS.md`;
- `G:\My Drive\RiftReader\status\RIFTREADER_CURRENT_STATUS.json`.

Commit using an explicit allowlist only. Do not stage capture directories or use `git add .`.

## Timing expectations

After the character is already in-world:

| Workflow segment | Expected time |
|---|---:|
| Target resolution + visual gate | under 1 minute |
| Family scan | about 3–4 minutes |
| Movement-stimulus pose batch | about 3–6 minutes |
| Promotion + assert + ProofOnly | about 1 minute |
| Final truth/handoff commit | under 1 minute |

Practical expectation: **7–12 minutes** for coordinate proof reacquisition after a clean client restart.

This estimate includes coordinate data truth reacquisition. It does not include:

- patch download/login time;
- visual/focus troubleshooting;
- route smoke;
- yaw/facing recovery;
- auto-turn validation;
- waypoint navigation validation.

## Acceptance criteria

A coordinate proof anchor is recovered only when all of the following are true:

| Criterion | Required value |
|---|---|
| Exact target resolved | `processName=rift_x64`, current PID, current HWND |
| Visual gate | `passed-visual-baseline` before any movement stimulus |
| Family scan | `status=passed`, candidate JSONL produced |
| Movement evidence | enough bounded movement pulses for promotion, or manually displaced poses with recorded evidence |
| Candidate support | required support pose count satisfied |
| Promotion | `ProofValidationStatus=validated` |
| Assert readback | `Status=valid` |
| Movement gate | `MovementAllowed=true` |
| ProofOnly | `passed-proof-only` |
| ProofOnly movement | `movementSent=false`, `movementAttempted=false` |
| Current pointer update | `currentProofPointerUpdate.updated=true` |
| Truth files | updated only after ProofOnly passes |
| Git | explicit files committed/pushed and remote SHA verified |

## Failure handling

| Failure | Meaning | Correct response |
|---|---|---|
| `target_drift` | proof pointer PID/HWND does not match current RIFT target | Reacquire; do not use old pointer. |
| `blocked-target` | RIFT target not found or ambiguous | Confirm one live RIFT window, character in-world, rerun. |
| visual gate blocked | focus/capture/window visibility not safe | Restore focus/visible desktop/capture path, rerun. |
| no candidate JSONL | coordinate scan did not find current family | Increase scan budget/tolerance or inspect reference capture. |
| insufficient poses | not enough displaced evidence | Collect more poses or rerun Stage 1. |
| promotion not validated | candidate evidence insufficient/inconsistent | Do not update truth; inspect ranked candidates/readback summaries. |
| assert invalid | promoted anchor does not read back correctly for current PID/HWND | Do not run navigation; rerun promotion or reacquire. |
| ProofOnly failed | proof anchor not accepted by same-target proof workflow | Keep pointer historical; continue recovery. |
| git dirty | local changes exist before commit | Stop and inspect status; do not overwrite unrelated files. |

## Safety policy

- No Cheat Engine by default.
- SavedVariables are not live truth.
- Old PID/HWND proof pointers are historical only.
- Bounded movement stimulus is allowed for coordinate evidence only when fresh coordinate truth can be captured before/after.
- Navigation movement is not allowed until coordinate proof passes and navigation-specific gates are separately validated.
- Do not update truth files before same-target `ProofOnly`.
- Do not commit capture directories unless explicitly requested.
- Do not run broad destructive commands.
- Do not use GitHub connector writes; local git is the write path.

## Post-proof next lanes

After coordinate proof is restored, the next movement/navigation lanes are separate:

1. actor yaw / body facing recovery;
2. forward vector or heading vector validation;
3. velocity/movement vector scanning;
4. movement/control flags;
5. zone/context identity;
6. observed-forward waypoint smoke;
7. multi-point route smoke.

Do not collapse these into coordinate truth. Coordinate truth is the foundation; navigation truth requires additional evidence.

## Future improvement targets

1. Make the promotion/finalization Python helpers repo-owned instead of Downloads-based transitional helpers.
2. Add a fast-path scan near the previous known coordinate family neighborhood before full memory scan.
3. Persist a compact recovery manifest after every successful proof recovery.
4. Add a single command that chains Stage 1, promotion, ProofOnly, finalization, and Drive status with strict gates.
5. Add machine-readable recovery state so future assistants can select the correct next action without parsing prose.

## END_OF_DOCUMENT_MARKER
