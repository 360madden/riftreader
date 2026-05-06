# RiftReader / RiftScan no-CE proof-anchor handoff

Created: 2026-05-06 12:51:59 -04:00
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

RiftReader's current-PID RiftScan candidate/readback loop is now proven, and a no-CE promotion path now exists to convert **multi-pose, same-candidate, same-PID, reference-tracked evidence** into a movement-gate-compatible proof anchor.

Movement is still blocked until live evidence is collected and `scripts\promote-riftscan-reference-match-to-proof-anchor.ps1` emits `scripts\captures\telemetry-proof-coord-anchor.json`, then `scripts\assert-current-proof-coord-anchor.ps1` returns `Status=valid` and `MovementAllowed=true`.

**Hard boundary:** do **not** use Cheat Engine / CE / CE debugger / `cheatengine-exec.ps1` unless explicitly reauthorized. Recent work used no CE and sent no game movement/input.

## Current truth / status

| Area | Status | Notes |
|---|---|---|
| RiftScan candidate generation | Working | RiftScan candidates can be imported into RiftReader watchsets. |
| RiftReader current-PID readback | Working | Wrapper reads/decode candidate vec3 windows with `--record-session`. |
| Reference scoring | Working | `-ReferenceX/Y/Z` and `-ReferenceFile` are supported, including stale-reference guards. |
| Best reference triage | Working | `BestReferenceMatches` is emitted and sorted by smallest reference delta. |
| No-CE proof promotion code path | Implemented + regression-tested | New promotion script validates multi-pose evidence and writes a proof anchor. |
| Movement preflight gate | Extended + regression-tested | Accepts legacy coord-trace anchors and strict no-CE promoted anchors. |
| Live movement | Still blocked | Do not move until current live anchor passes preflight. |
| Current live PID from last session | `47560` / HWND `0x2122E` | Treat as session-specific; re-check in new chat because RIFT may restart. |

## Key files added/changed in this workstream

### Candidate import/readback/reference scoring

- `C:\RIFT MODDING\RiftReader\scripts\import-riftscan-coordinate-candidates.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-import-riftscan-coordinate-candidates.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\invoke-riftscan-coordinate-readback.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-invoke-riftscan-coordinate-readback-decode.ps1`
- `C:\RIFT MODDING\RiftReader\docs\riftscan-riftreader-coordinate-candidate-workflow.md`

### Movement gate / proof-anchor safety

- `C:\RIFT MODDING\RiftReader\scripts\assert-current-proof-coord-anchor.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-assert-current-proof-coord-anchor.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\navigation\run-a-to-b-prototype.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\navigation\test-run-a-to-b-proof-anchor-gate.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\navigation\test-navigation-proof-suite.ps1`

### New no-CE promotion bridge

- `C:\RIFT MODDING\RiftReader\scripts\promote-riftscan-reference-match-to-proof-anchor.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-promote-riftscan-reference-match-to-proof-anchor.ps1`

## What the new no-CE promotion script does

Script:

```powershell
.\scripts\promote-riftscan-reference-match-to-proof-anchor.ps1
```

It takes 2+ readback summary files for the same candidate at manually changed positions and fails closed unless all are true:

| Requirement | Why |
|---|---|
| Same target PID | Blocks old-process/session reuse. |
| `NoCheatEngine=true` | Preserves no-CE workflow boundary. |
| `MovementSent=false` | Prevents using Codex-sent movement evidence as passive proof. |
| Same candidate address/region/offset across poses | Prevents switching candidates mid-proof. |
| Stable decoded samples per pose | Avoids noisy/invalid memory. |
| Candidate matches same-time reference at every pose | Ties candidate to an external coordinate truth surface. |
| Reference displacement meets `-MinReferenceDisplacement` | Ensures more than a single still pose. |
| Candidate delta tracks reference delta within `-MaxDeltaError` | Converts candidate scoring into movement-grade proof evidence. |

Successful output anchor fields include:

```json
{
  "Mode": "proof-coord-anchor",
  "CanonicalCoordSourceKind": "riftscan-reference-validated-candidate",
  "ProofMethod": "no-ce-riftscan-reference-multisample",
  "ProofValidationStatus": "validated",
  "ProofProcessMatchesProcess": true,
  "NoCheatEngine": true,
  "MovementSent": false,
  "CoordXRelativeOffset": 0,
  "CoordYRelativeOffset": 4,
  "CoordZRelativeOffset": 8
}
```

## Last known important artifacts

These are historical/session-specific and may be stale after a RIFT restart:

| Artifact | Meaning |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-20260506-091657.json` | Current-PID candidate readback wrapper summary; candidates decoded/stable/source-preview matched. |
| `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-currentpid-47560-passive-vec3-watchset-20260506-091657.json` | Imported RiftScan candidate watchset for PID 47560. |
| `C:\RIFT MODDING\RiftReader\scripts\captures\proof-coord-anchor-preflight-currentpid-47560-no-ce-post-movement-gate-20260506-093120.json` | Preflight failed closed because anchor was old-PID/stale. |
| `C:\RIFT MODDING\RiftReader\scripts\captures\proof-coord-anchor-preflight-currentpid-47560-20260506-092319.json` | Earlier failed-closed proof-anchor preflight for PID 47560. |

## Validation already run

| Command / check | Result |
|---|---|
| PowerShell parser checks for changed scripts | Passed |
| `pwsh -File .\scripts\test-assert-current-proof-coord-anchor.ps1` | Passed |
| `pwsh -File .\scripts\test-promote-riftscan-reference-match-to-proof-anchor.ps1` | Passed |
| `pwsh -File .\scripts\test-invoke-riftscan-coordinate-readback-decode.ps1` | Passed |
| `pwsh -File .\scripts\test-import-riftscan-coordinate-candidates.ps1` | Passed |
| `pwsh -File .\scripts\navigation\test-navigation-proof-suite.ps1` | Passed; includes `riftscan-reference-proof-promotion-regression` |
| `dotnet test .\RiftReader.slnx --no-restore` | Passed: 73/73 |
| `git diff --check` | Passed; LF -> CRLF warnings only |
| CE process check | No Cheat Engine processes detected |

## Current git status at handoff time

```text
 M addon/RiftReaderApiProbe/main.lua
 M agents.md
 M reader/RiftReader.Reader/Telemetry/TelemetrySources.cs
 M scripts/navigation/run-a-to-b-prototype.ps1
 M scripts/navigation/test-navigation-proof-suite.ps1
 M scripts/test-actor-yaw-candidates.ps1
 M scripts/trace-coord-writer-instruction.ps1
 M scripts/trace-player-coord-write.ps1
?? addon/RiftReaderApiProbe/README.md
?? addon/RiftReaderApiProbe/RiftAddon.toc
?? docs/handoffs/2026-05-06-065844-api-coord-reacquisition-handoff.md
?? docs/handoffs/2026-05-06-125036-riftscan-riftreader-no-ce-proof-anchor-handoff.md
?? docs/riftscan-riftreader-coordinate-candidate-workflow.md
?? scripts/assert-current-proof-coord-anchor.ps1
?? scripts/import-riftscan-coordinate-candidates.ps1
?? scripts/invoke-riftscan-coordinate-readback.ps1
?? scripts/navigation/test-run-a-to-b-proof-anchor-gate.ps1
?? scripts/promote-riftscan-reference-match-to-proof-anchor.ps1
?? scripts/test-assert-current-proof-coord-anchor.ps1
?? scripts/test-import-riftscan-coordinate-candidates.ps1
?? scripts/test-invoke-riftscan-coordinate-readback-decode.ps1
?? scripts/test-promote-riftscan-reference-match-to-proof-anchor.ps1
```

Notes:

- There are pre-existing modified files in the working tree unrelated or partially related to this lane: addon probe files, telemetry source file, actor-yaw scripts, trace scripts, etc.
- Do not blindly stage/commit everything unless the next chat intentionally reviews scope.
- The main new proof-anchor/candidate files are untracked at handoff time.

## Exact next live sequence, no CE

### 1. Re-resolve current RIFT PID/HWND

```powershell
Get-Process -Name rift_x64 | Select-Object Id, ProcessName, MainWindowHandle, Responding, StartTime
```

Use the current PID/HWND in all later commands. Do not assume PID `47560` is still current.

### 2. Capture pose A candidate readback with reference file

Create or obtain a same-time reference coordinate JSON, e.g.:

```json
{
  "source": "overlay-ocr-or-manual-same-time",
  "captured_at_utc": "<UTC timestamp>",
  "tolerance": 0.25,
  "coordinate": { "x": 0.0, "y": 0.0, "z": 0.0 }
}
```

Then run:

```powershell
.\scripts\invoke-riftscan-coordinate-readback.ps1 `
  -ProcessId <current_rift_pid> `
  -TargetWindowHandle <current_rift_hwnd> `
  -CandidateFile '<fresh-or-existing-riftscan-vec3_candidates.jsonl>' `
  -ReferenceFile .\scripts\captures\pose-a-reference.json `
  -ReferenceMaxAgeSeconds 60 `
  -TopReferenceMatches 5 `
  -Json
```

Save the emitted summary path.

### 3. User manually moves character 5-10m

Manual movement only. Codex should not send movement yet.

### 4. Capture pose B candidate readback with a fresh reference file

Run the wrapper again with pose B reference JSON. Ensure the same candidate id appears and is among best reference matches.

### 5. Promote candidate to no-CE proof anchor

```powershell
.\scripts\promote-riftscan-reference-match-to-proof-anchor.ps1 `
  -ReadbackSummaryFile `
    .\scripts\captures\pose-a-summary.json, `
    .\scripts\captures\pose-b-summary.json `
  -CandidateId <same_candidate_id> `
  -ProcessId <current_rift_pid> `
  -TargetWindowHandle <current_rift_hwnd> `
  -OutputFile .\scripts\captures\telemetry-proof-coord-anchor.json `
  -MinReferenceDisplacement 1.0 `
  -MaxDeltaError 0.25 `
  -MaxEvidenceAgeSeconds 120 `
  -Json
```

### 6. Run the hard movement preflight

```powershell
.\scripts\assert-current-proof-coord-anchor.ps1 `
  -ProcessId <current_rift_pid> `
  -TargetWindowHandle <current_rift_hwnd> `
  -Json
```

Only if it returns `Status=valid` and `MovementAllowed=true` should any movement attempt be considered.

## Do not do these in the next chat unless explicitly authorized

- Do not use Cheat Engine / CE.
- Do not call `scripts\cheatengine-exec.ps1`.
- Do not allow `resolve-proof-coord-anchor.ps1` to refresh via CE-backed tracing.
- Do not send movement or auto-turn input until preflight passes.
- Do not trust SavedVariables as live coordinates without a fresh save timestamp proving same-time capture.
- Do not treat single-pose candidate/readback/reference match as movement-grade proof.

## Ready-to-paste resume prompt for new chat

```text
Read the newest handoff in C:\RIFT MODDING\RiftReader\docs\handoffs for the RiftReader/RiftScan no-CE proof-anchor lane. Continue from there. Hard rules: do NOT use Cheat Engine/CE/cheatengine-exec.ps1, do NOT send movement/input until assert-current-proof-coord-anchor.ps1 returns Status=valid and MovementAllowed=true for the current RIFT PID/HWND. First re-check current RIFT PID/HWND and git status. Then continue the live no-CE multi-pose promotion workflow: collect pose A/B readback summaries with fresh ReferenceFile artifacts, promote the same candidate with promote-riftscan-reference-match-to-proof-anchor.ps1, and run the proof-anchor preflight. Keep historical artifacts but treat PIDs/addresses as session-specific.
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Re-check current RIFT PID/HWND. | Live facts are session-specific after crashes/restarts. |
| 2 | Review git status before editing. | Working tree contains multiple modified/untracked files. |
| 3 | Capture fresh pose A reference JSON and readback summary. | Starts no-CE multi-pose proof evidence. |
| 4 | Manually move the character 5-10m. | Creates displacement without Codex movement. |
| 5 | Capture fresh pose B reference JSON and readback summary. | Required for delta tracking proof. |
| 6 | Use the same best candidate id across pose A/B. | Promotion requires stable same-address candidate. |
| 7 | Run the promotion script with strict thresholds. | Produces current-PID proof anchor only if evidence is strong. |
| 8 | Run `assert-current-proof-coord-anchor.ps1`. | Central movement gate must approve before navigation. |
| 9 | If preflight fails, inspect promotion evidence and blockers, not movement code. | Most likely issue is reference/candidate delta mismatch or stale evidence. |
| 10 | Only after preflight passes, run a tiny guarded route with 5m arrival radius. | Safe live validation after proof truth is restored. |
