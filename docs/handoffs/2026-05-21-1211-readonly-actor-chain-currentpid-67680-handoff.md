# **✅ HANDOFF — Read-only actor-chain milestone, current PID 67680**

Generated: `2026-05-21T16:11Z`  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`  
Lane: **player actor static coordinate-chain discovery**  
Authorization used: **read-only process attach/readback allowed; no debugging**

## Verdict

Current target/proof/candidate continuity is **reconfirmed** for PID `67680` / HWND `0x120CBE`, and the actor-like coordinate candidate `0x242E9932F70` still matches fresh API-now coordinates when the known stable offset is applied.

Static player-actor chain promotion remains **blocked** because the current authorization explicitly excludes debugger/access-provenance work. No x64dbg, CE, breakpoints, movement, input, memory writes, provider writes, or Git mutation were used.

## Phase plan and milestone status

| Phase | Milestone | Result | Evidence |
|---:|---|---|---|
| 1 | Current target lock | Passed | One visible/responding RIFT target: PID `67680`, HWND `0x120CBE`, start `2026-05-21T14:38:42.127583Z` |
| 2 | Proof-anchor safety gate | Passed | `coordinate_recovery_status.py --json` returned `status=passed`, proof `current-target-proofonly-passed` |
| 3 | Actor candidate continuity | Passed after timeout recovery | Candidate readback rerun with 120s reference timeout passed |
| 4 | Read-only owner layout | Passed | Owner `0x242E9932D70`, coord offset `+0x200`, 5/5 module-field signature still matches |
| 5 | No-debug provenance decision | Blocked by scope | Access provenance requires debugger/watchpoint or equivalent static provenance; not authorized in this pass |
| 6 | Durable handoff | Done | This file records exact artifacts and blockers |

## Current target and proof snapshot

| Item | Value |
|---|---|
| Target | `rift_x64` PID `67680`, HWND `0x120CBE` |
| Window state | Visible/responding, not foreground |
| Process start | `2026-05-21T10:38:42.1275829-04:00` / `2026-05-21T14:38:42.127583Z` |
| Proof anchor | `0x242D3DEF010` |
| Proof candidate | `api-family-hit-000001` |
| Proof status | `current-target-proofonly-passed` |
| Proof artifact | `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` |
| Latest proof coordinate | `X=7371.48876953125`, `Y=868.26171875`, `Z=2997.662109375` at `2026-05-21T14:52:00.1090847Z` |
| Safety note | Proof anchor is a movement-safety gate only; it is **not** the player actor static chain |

## Actor-like candidate readback

First attempt:

| Check | Result |
|---|---|
| Command | `python .\scripts\current_pid_candidate_readback.py ... --reference-timeout-seconds 45 --json` |
| Result | Failed before readback: `reference_capture_failed: exit=None; timedOut=True` |
| Safety | No input, no movement, no debugger, no memory read |
| Artifact | `C:\RIFT MODDING\RiftReader\scripts\captures\candidate-readback-currentpid-67680-20260521-160610-511278\candidate-readback-summary.json` |

Recovered attempt:

| Field | Value |
|---|---|
| Command change | Increased only the read-only reference timeout to `120` seconds |
| Status | `passed` |
| Candidate | `api-family-hit-000001` at `0x242E9932F70` |
| Classification | `offset-corrected-current-coordinate-candidate` |
| Fresh API reference | `X=7365.830078`, `Y=870.959961`, `Z=3001.300049` |
| Memory value | `X=7365.82958984375`, `Y=872.4995727539062`, `Z=3001.297607421875` |
| Direct max abs delta | `1.5396117539062288` |
| Offset-corrected max abs delta | `0.004650953124837542` |
| Stable offset used | `X=0.0009304687500844011`, `Y=-1.543588867187509`, `Z=-0.0022093749998930434` |
| Matching candidates | `1 / 3` |
| Artifact | `C:\RIFT MODDING\RiftReader\scripts\captures\candidate-readback-currentpid-67680-20260521-160728-953877\candidate-readback-summary.json` |
| Safety | Read-only process memory read; no input, no movement, no x64dbg, no CE, no memory write |

Interpretation: `0x242E9932F70` remains a strong **actor-like offset candidate** for this current PID. It is still candidate-only because direct Y is offset by about `+1.54` and there is no static/root/access provenance yet.

## Owner-layout and module-field evidence

| Item | Value |
|---|---|
| Hypothesized owner base | `0x242E9932D70` |
| Candidate field / coord storage | `0x242E9932F70` |
| Coord offset from owner | `+0x200` |
| Owner-window module pointer hints | `12` |
| Root sweep status | `passed` |
| Selected RVA | `0x2725638` |
| Module-pointer hits | `6` |
| Non-zero owner-field candidates | `6` |
| Top owner score | `285` |
| Top owner match | `0x242E9932D70` with 5/5 module fields |
| Field RVAs matched | `0x3562D50`, `0x3566B60`, `0x3565170`, `0x3564780`, `0x2725638` |
| Family classifier | `passed`, `ownerFamilyCount=4`, `priorityParentLeadCount=1` |
| Promotion | `candidateOnly=true`, `promotionEligible=false` |

Artifacts:

| Artifact | Path |
|---|---|
| Fresh owner neighborhood | `C:\RIFT MODDING\RiftReader\scripts\captures\pointer-owner-neighborhood-inspector-20260521-160610-600819\summary.json` |
| Fresh root-signature sweep | `C:\RIFT MODDING\RiftReader\scripts\captures\root-signature-module-hint-sweep-20260521-160610-674508\summary.json` |
| Fresh root-family classifier | `C:\RIFT MODDING\RiftReader\scripts\captures\root-signature-family-classifier-20260521-160834-290054\summary.json` |
| Prior semantic classifier | `C:\RIFT MODDING\RiftReader\scripts\captures\coordinate-candidate-semantic-classifier-20260521-153501-617415\summary.json` |
| Prior optimized workflow handoff | `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-21-1154-optimized-actor-chain-workflow-handoff.md` |

## Current blocker

| Blocker | Meaning | Required resolution |
|---|---|---|
| `blocked-no-debugger-access-provenance` | The optimized workflow's next promotion-grade evidence is access provenance or equivalent static/module-root provenance. Current authorization allows read-only attach/readback but forbids debugger work. | Either provide explicit current-turn approval for one bounded debugger/access-provenance step, or continue no-debug static-owner/root resolver research from the priority parent lead without claiming promotion. |
| `riftscan-milestone-review-blocked-no-supported-candidate` | The post-milestone RiftScan strategy gate was run and blocked because no existing supported RiftScan coordinate match artifact is available for this exact target. | Keep RiftScan read-only; do not create provider sessions/reports unless explicitly authorized. This does not invalidate the RiftReader-owned readback above, but it blocks RiftScan-provider expansion. |

## Post-milestone strategy gate

| Check | Result |
|---|---|
| Command | `python .\scripts\riftscan_milestone_review.py --pid 67680 --hwnd 0x120CBE --write-summary --write-markdown --compact-json` |
| Status | `blocked` |
| Primary issue | `no_supported_candidate_schema` |
| Target pointer match | Passed for PID `67680` / HWND `0x120CBE` |
| Current proof pointer | `current-target-proofonly-passed` |
| Summary JSON | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260521-161329.json` |
| Summary Markdown | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260521-161329.md` |

Interpretation: the RiftScan provider lane remains blocked/read-only for this target because no supported existing provider artifact was selected. The current RiftReader-owned actor-candidate readback is still valid candidate-only evidence, but it must not be promoted or expanded into provider writes.

## Safety ledger

| Operation class | Used? | Notes |
|---|---:|---|
| Read-only target discovery | Yes | `get-rift-window-targets.ps1 -Json` |
| Read-only API/reference scan | Yes | RRAPICOORD marker capture, no input |
| Read-only process memory read | Yes | Candidate/owner/root-signature inspection only |
| x64dbg/debugger attach | No | Explicitly skipped under current authorization |
| Breakpoints/watchpoints | No | Not authorized |
| Cheat Engine | No | Forbidden/not used |
| Movement/input | No | No click/key/movement sent in this pass |
| Memory writes/patching | No | Not allowed/not used |
| Provider writes | No | Not used |
| Git mutation | No | No staging/commit/push |


## Continued no-debug Phase 10 result

After the initial milestone, the safe no-debug path continued into priority parent-lane root triage.

| Check | Result |
|---|---|
| Priority target file | `C:\RIFT MODDING\RiftReader\scripts\captures\root-signature-family-classifier-20260521-160834-290054\priority-parent-lead-targets.json` |
| Pointer-family scan | `C:\RIFT MODDING\RiftReader\scripts\captures\pointer-family-scan-20260521-161945-968614\summary.json` |
| Scanned targets | `2` |
| Top hit | `0xE69000000E0` referenced from `0x242A38AAF60` |
| Module hits | `0` |
| rift_x64 hits | `0` |
| Exhaustion report | `C:\RIFT MODDING\RiftReader\scripts\captures\priority-scan-exhaustion-report-20260521-162011-122035\summary.json` |
| Verdict | `priority-lane-exhausted-no-static-root` |
| Safety | Read-only process memory scan only; no input, movement, x64dbg, CE, breakpoints, memory writes, provider writes, or Git mutation |

Interpretation: the current no-debug priority parent lead is exhausted as a static-root path. The actor-like candidate remains valid candidate-only evidence, but this branch does not yield a module/RVA/static-owner resolver.


## Continued no-debug Phase 11 result — broadened parent/owner scans

The safe no-debug search was broadened beyond the single priority parent lead.

| Scan | Targets | Targets with hits | Module hits | rift_x64 hits | Artifact |
|---|---:|---:|---:|---:|---|
| Non-priority parent leads | `6` | `3` | `0` | `0` | `C:\RIFT MODDING\RiftReader\scripts\captures\pointer-family-scan-20260521-162245-598545\summary.json` |
| Owner + coord-storage addresses | `12` | `0` | `0` | `0` | `C:\RIFT MODDING\RiftReader\scripts\captures\pointer-family-scan-20260521-162400-107887\summary.json` |

Additional report: `C:\RIFT MODDING\RiftReader\scripts\captures\priority-scan-exhaustion-report-20260521-162331-293407\summary.json`.

Verdict: `no-debug-root-lanes-exhausted-no-static-root` for the current evidence set. This does not invalidate `0x242E9932F70`; it means no safe no-debug parent/owner scan has found module/static-root provenance.


## Continued no-debug Phase 12 result — reusable status aggregator

Added a tracked reusable offline helper for this lane:

| File | Purpose |
|---|---|
| `scripts/actor_chain_no_debug_status.py` | Thin CLI wrapper |
| `scripts/rift_live_test/actor_chain_no_debug_status.py` | Aggregates current proof/candidate/root-scan artifacts into fail-closed no-debug status |
| `scripts/test_actor_chain_no_debug_status.py` | Unit tests for scan aggregation and promotion-blocking logic |

Real run result:

| Field | Value |
|---|---|
| Command | `python .\scripts\actor_chain_no_debug_status.py --json` |
| Status | `passed` |
| Verdict | `candidate-only-no-debug-root-blocked` |
| Promotion allowed | `false` |
| Summary JSON | `C:\RIFT MODDING\RiftReader\scripts\captures\actor-chain-no-debug-status-20260521-162848-574766\summary.json` |
| Summary Markdown | `C:\RIFT MODDING\RiftReader\scripts\captures\actor-chain-no-debug-status-20260521-162848-574766\summary.md` |
| Blockers | `blocked-no-debugger-access-provenance`, `no-debug-root-lanes-exhausted`, `no-static-resolver-promoted` |

Safety: offline artifact aggregation only. No live process memory read, no input, no movement, no x64dbg, no CE, no memory writes, no provider writes, and no Git mutation.


## Continued no-debug Phase 13 result — post-milestone RiftScan strategy gate

After adding the no-debug status helper, the RiftScan milestone strategy gate was rerun.

| Field | Value |
|---|---|
| Command | `python .\scripts\riftscan_milestone_review.py --pid 67680 --hwnd 0x120CBE --write-summary --write-markdown --compact-json` |
| Status | `blocked` |
| Issue | `no_supported_candidate_schema` |
| Target pointer match | Passed |
| Summary JSON | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260521-163007.json` |
| Summary Markdown | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260521-163007.md` |

Interpretation: unchanged provider boundary. RiftScan remains read-only and cannot be used for supported provider-candidate expansion until an existing supported match artifact is selected or writes are explicitly authorized.

## Resume prompt

Resume in `C:\RIFT MODDING\RiftReader` on `main`. Read this handoff first, then `docs/recovery/optimized-player-actor-coordinate-chain-workflow.md`. Current target was PID `67680` / HWND `0x120CBE` and must be rediscovered before any live read. The actor-like candidate `0x242E9932F70` under owner `0x242E9932D70 + 0x200` revalidated read-only with offset-corrected API delta `0.004650953124837542`. Static actor chain is not promoted. No debugger was used; promotion is blocked on access/static provenance. Do not run movement, CE, x64dbg, watchpoints, or broad scans without fresh target/proof gates and explicit current-turn authorization.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Re-run target discovery before any further live read | PID/HWND/process epochs can drift quickly |
| 2 | Re-run `coordinate_recovery_status.py --json` | Confirms proof anchor remains same-target and current |
| 3 | If staying no-debug, pursue static-owner/root resolver research from `priority-parent-lead-targets.json` | Best safe path without watchpoints |
| 4 | Keep `0x242E9932F70` candidate-only until resolver/restart gates pass | Offset-corrected match is strong but not a static chain |
| 5 | If debugger work is approved later, start with stop-context only | Lowest-risk debugger sanity check |
| 6 | After safe stop-context, use at most one short hardware-read watchpoint on the 12-byte XYZ window | Captures access provenance without broad scanning |
| 7 | Normalize any access event with `x64dbg_access_event_ingest.py` | Converts ephemeral debugger state into durable evidence |
| 8 | Generate resolver candidates only from module/RVA/static-owner evidence | Avoids promoting heap-only absolute addresses |
| 9 | Validate any resolver with fresh API-now vs chain-now across displaced poses | Prevents stale/copy-family promotion |
| 10 | Require restart/relog validation plus final same-target `ProofOnly` before promotion | Separates current-PID success from restart-stable truth |
