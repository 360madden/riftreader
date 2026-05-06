# 2026-05-06 14:44:56 - Current readback coord-truth handoff

## TL;DR

Movement/input is **stopped**. Continue coord work only through read-only proof paths until the user explicitly resumes movement.

The current strongest coordinate truth is a direct, exact-PID, no-input Reader readback from the validated proof anchor:

`C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-144259.json`

It proves `api-probe-triplet-000007` at `0x2400EA32120` is readable in current process `rift_x64` PID `47560`, stable across 12 samples, with no region read failures, no Cheat Engine, no SavedVariables live truth, and no movement sent.

## Hard boundaries for resume

| Boundary | Required behavior |
|---|---|
| Movement/input | **Do not send movement/input** until the user explicitly says to resume. |
| Cheat Engine | Do **not** use CE, CE Lua, CE debugger attach, CE watchpoints/breakpoints, or `cheatengine-exec.ps1`. |
| SavedVariables | Do **not** use `ReaderBridgeExport.lua` as live truth. Treat SavedVariables as post-save snapshots only. |
| Proof source | Prefer `proof-anchor-current-readback` / `assert-current-proof-coord-anchor-readback.ps1` for current coordinate proof. |
| Candidate scans | Treat RiftScan/watchset candidates as supporting evidence unless the current proof-anchor preflight/readback validates them. |
| ChromaLink | Keep provider/consumer boundary; do not edit ChromaLink from this RiftReader lane. |

## Repo snapshot

| Field | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` |
| HEAD before this handoff commit | `b42578a` |
| Created local time | `2026-05-06 14:44:56 -04:00` |
| Current process | `rift_x64` PID `47560`, HWND `0x2122E`, title `RIFT` |
| Current proof summary | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-144259.json` |

## Current strongest coord proof

| Field | Value |
|---|---|
| Artifact | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-144259.json` |
| Status | `valid` |
| MovementAllowed | `true` - means proof gate satisfied, not movement sent |
| MovementSent | `false` |
| NoCheatEngine | `true` |
| ProofAnchorStatus | `valid` |
| ProofAnchorSource | `cache` |
| ProofAnchorCandidateId | `api-probe-triplet-000007` |
| ProofAnchorCandidateAddressHex | `0x2400EA32120` |
| RegionAddressHex | `0x2400EA320E0` |
| CandidateOffsetInRegion | `64` |
| ReadbackIntegrityStatus | `ok` |
| ReadbackRecordedSampleCount | `12` |
| ReadbackTotalRegionReadFailures | `0` |
| DecodedSampleCount | `12` |
| StableAcrossReadbackSamples | `true` |
| MaxAbsDeltaAcrossReadbackSamples | `0` |
| CanonicalCoordSource | `proof-anchor-current-readback` |
| MovementGate | `satisfied_by_current_process_proof_anchor_current_readback` |
| Current X/Y/Z | `7445.84716796875`, `887.244384765625`, `3027.352783203125` |

## Files changed in this handoff lane

| File | Purpose |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\assert-current-proof-coord-anchor-readback.ps1` | New direct no-input proof-anchor readback script. Runs proof preflight, creates one-region watchset, records exact-PID Reader samples, decodes X/Y/Z, and fails closed. |
| `C:\RIFT MODDING\RiftReader\scripts\test-assert-current-proof-coord-anchor-readback.ps1` | Regression guardrails for no CE, no input, exact PID attach, no SavedVariables live truth, and stable current-readback proof semantics. |
| `C:\RIFT MODDING\RiftReader\scripts\invoke-riftscan-coordinate-readback.ps1` | Updated wrapper to use `assert-current-proof-coord-anchor.ps1`, expose proof-gate status, and tie the proof-anchor candidate to current readback. |
| `C:\RIFT MODDING\RiftReader\scripts\test-invoke-riftscan-coordinate-readback-proof-gate.ps1` | Regression guard for the wrapper proof-gate behavior. |
| `C:\RIFT MODDING\RiftReader\scripts\assert-current-proof-coord-anchor.ps1` | Allows valid no-CE RiftScan reference proof cache to satisfy current proof preflight before legacy resolver fallback. |
| `C:\RIFT MODDING\RiftReader\scripts\test-assert-current-proof-coord-anchor.ps1` | Adds coverage that default preflight accepts valid no-CE RiftScan proof cache. |
| `C:\RIFT MODDING\RiftReader\addon\RiftReaderApiProbe\main.lua` | API coordinate scaffold from earlier in the lane; publishes live `RRAPICOORD1` marker without SavedVariables live truth. |
| `C:\RIFT MODDING\RiftReader\addon\RiftReaderApiProbe\README.md` | Documents the API probe workflow. |
| `C:\RIFT MODDING\RiftReader\addon\RiftReaderApiProbe\RiftAddon.toc` | Addon manifest for the API probe. |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Telemetry\TelemetrySources.cs` | Avoids treating stale addon snapshot coords as mismatch evidence unless addon reference is fresh. |
| `C:\RIFT MODDING\RiftReader\agents.md` | Records current no-CE live boundary. |
| `C:\RIFT MODDING\RiftReader\scripts\test-actor-yaw-candidates.ps1` | Adds proof-anchor coordinate fallback for exact PID/HWND actor-yaw testing when current-player reader path fails. |
| `C:\RIFT MODDING\RiftReader\scripts\trace-coord-writer-instruction.ps1` | Hardens hit summarization against null hits. |
| `C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1` | Allows explicit candidate-address tracing to proceed when current-player snapshot is unavailable. |

## Validation completed

| Command / check | Result |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\validate-addon.cmd` | Passed. Lua syntax validated for 4 addons. |
| PowerShell parser check for changed proof/trace/test scripts | Passed. |
| `pwsh -NoProfile -File .\scripts\test-assert-current-proof-coord-anchor-readback.ps1` | Passed. |
| `pwsh -NoProfile -File .\scripts\test-assert-current-proof-coord-anchor.ps1` | Passed. |
| `pwsh -NoProfile -File .\scripts\test-invoke-riftscan-coordinate-readback-proof-gate.ps1` | Passed. |
| `pwsh -NoProfile -File .\scripts\test-invoke-riftscan-coordinate-readback-decode.ps1` | Passed. |
| `dotnet test .\RiftReader.slnx --no-restore` | Passed: 73 tests. |
| `git diff --check` / `git diff --cached --check` | Passed; only Git line-ending normalization warnings were reported. |
| Direct no-input 4-sample proof readback | Passed; artifact `proof-anchor-currentpid-47560-readback-summary-20260506-144231.json`. |
| Direct no-input 12-sample proof readback | Passed; artifact `proof-anchor-currentpid-47560-readback-summary-20260506-144259.json`. |

## What was not validated

| Pending | Why |
|---|---|
| Runtime `/rap coord` after live UI reload | Requires live addon reload/user-approved live input. |
| New manual or movement-backed delta after this stop point | User explicitly stopped movement. |
| CE/source-chain proof refresh | Intentionally not attempted due current no-CE boundary. |

## Resume prompt

```text
Resume from C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-06-144456-current-readback-coord-truth-handoff.md. Movement is stopped. Do not send movement/input unless I explicitly resume it. Continue proving coord truth using no-CE, no-SavedVariables live truth paths. Start with C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-144259.json and C:\RIFT MODDING\RiftReader\scripts\assert-current-proof-coord-anchor-readback.ps1.
```

## Top 10 next recommended actions

| # | Action | Why |
|---:|---|---|
| 1 | Promote `proof-anchor-current-readback` into the current-truth docs/status surface. | Makes the newest validated source easy to find. |
| 2 | Add a `latest-proof-anchor-current-readback.json` pointer file. | Removes timestamp hunting on resume. |
| 3 | Keep movement disabled until the user explicitly resumes. | Preserves the current stop boundary. |
| 4 | Re-run direct no-input proof after any manual movement. | Confirms the same address tracks live coordinate changes without Codex input. |
| 5 | Compare direct proof readback and wrapper readback outputs in a small validator. | Ensures both proof paths stay semantically aligned. |
| 6 | Add docs clarifying `MovementAllowed` means proof gate satisfied, not movement sent. | Prevents future confusion in no-movement phases. |
| 7 | Add direct readback script to the telemetry/navigation preflight checklist. | Ensures movement code never uses stale or heuristic coords. |
| 8 | Validate `/rap coord` only after explicit live-addon reload approval or manual user reload. | Keeps live input gated while still enabling API scaffold proof. |
| 9 | Keep old SavedVariables-derived artifacts explicitly classified stale/post-save. | Prevents accidental mixing with live truth. |
| 10 | Commit/push this handoff and focused proof-readback changes as a reviewable slice. | Preserves the current proof state and restart path. |