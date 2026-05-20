# RiftReader handoff — current proof, 640x360 geometry, input incident, and blockers

Generated: 2026-05-19 21:27:18 local
Repo: `C:\RIFT MODDING\RiftReader`
Branch baseline: `main...origin/main`, HEAD `c80cd92` (`Add MCP final maintenance handoff`)
Purpose: resume safely without re-reading the whole thread.

## ✅ RESULT verdict

| Area | Status | Evidence / path | Resume policy |
|---|---|---|---|
| Current coordinate proof | ✅ `current-target-proofonly-passed` | `docs/recovery/current-proof-anchor-readback.json`; `scripts/captures/live-test-ProofOnly-20260520-011554/run-summary.json` | Current only for PID `1948` / HWND `0x3C0D58` / process epoch `2026-05-19T17:31:18.6311824+00:00`. |
| Current coordinate | ✅ `X=7298.86572265625`, `Y=818.2576904296875`, `Z=3013.78515625` | Recorded `2026-05-20T01:16:16.7719982Z` | Use as latest post-incident proof coordinate; refresh if target drifts. |
| Current proof anchor | ✅ `api-family-hit-000010 @ 0x1A91015CB00` | `scripts/captures/family-scan-currentpid-1948-20260520-003014-344522/api-family-vec3-candidates.jsonl` | Current valid after same-target ProofOnly; not portable across process restart. |
| Movement/input automation | ⛔ paused | `movementGate.status=blocked-live-input-spin-incident` | Do not run live movement automation until input backend/spin incident is reviewed and explicitly cleared. |
| Window geometry | ✅ exact client `640x360` | `tools/RiftReader.WindowTools inspect`; verified `2026-05-20T01:20:10Z` | Preserve this exact client geometry before visual capture or input. |
| ChromaLink current coordinate surface | ✅ fresh post-incident | `scripts/captures/chromalink-world-state-reference-20260520-011324-196091/summary.json` | Consumer-side truth only; no provider edits. |
| Static chain | ⛔ blocked/current invalid | root slot `rift_x64.exe+0x32E1780` read back `0x10` | Historical/static-chain formulas are not current proof. |
| Actor yaw/facing | ⛔ stale/target-drift | `scripts/captures/actor-yaw-readback-smoke-currentpid-1948-20260520-005608/run-summary.json` | Do not reuse until current-PID revalidation. |
| RiftScan | 🟨 provider/reference only | no new provider writes in this slice | Read-only provider evidence only; no movement truth by itself. |

## ✅ Truth gained before the 1-hour stop condition

| Truth item | Verdict |
|---|---|
| Live target remains PID `1948` / HWND `0x3C0D58` | ✅ recovered/current |
| RIFT client area is exactly `640x360`; outer window is `656x399` | ✅ recovered/current |
| Current coordinate proof survived post-incident ProofOnly with no movement sent | ✅ recovered/current |
| ChromaLink post-incident samples were fresh/stable around the proof coordinate | ✅ recovered/current |
| Old PID `27552` proof pointer is historical only; current proof uses PID `1948` anchor | ✅ recovered/current classification |
| Static owner/source-chain root RVA did not survive current layout (`0x10`) | ✅ negative/current blocker truth |
| Actor yaw/facing artifacts are stale for current PID/HWND | ✅ current blocker truth |
| Family/adjacent scan attempt produced no delta-tracking vec3 candidates and exposed input-backend risk | ✅ blocker truth |

## 🔴 / 🟡 / 🟢 checklist

| Status | Item | Details |
|---|---|---|
| 🟢 | Current live PID/HWND | PID `1948`, HWND `0x3C0D58`, title `RIFT`. |
| 🟢 | Current coordinate proof | ProofOnly passed after emergency key-release. |
| 🟢 | Current coordinate anchor | `api-family-hit-000010 @ 0x1A91015CB00`. |
| 🟢 | Client geometry | Client area exactly `640x360`; keep this before capture/input. |
| 🟢 | Emergency key release helper | `scripts/rift_emergency_key_release.py`; live artifact `scripts/captures/emergency-key-release-20260520-011453-542635/summary.json`. |
| 🟡 | Movement proof history | Forward smoke/series previously passed, but automation is now paused after spin incident. |
| 🟡 | Family/adjacent scanning | Broad scans found stable family patterns; adjacent sequence blocked with `no-delta-tracking-vec3-candidates`. |
| 🔴 | Live movement automation | Paused due to unsafe spinning observed during `WindowMessage W` auto-displacement. |
| 🔴 | Static chain | Current root slot reads `0x10`; resolver blocks as `root-pointer-not-plausible`. |
| 🔴 | Actor yaw/facing | Stale/target-drift; no current live readback. |

## Current reacquisition artifacts

| Artifact | Path |
|---|---|
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| Current truth doc | `docs/recovery/current-truth.md` |
| Current truth JSON | `docs/recovery/current-truth.json` |
| Archived stale PID 27552 pointer | `docs/recovery/historical/current-proof-anchor-readback-2026-05-20-pid27552-hwnd3411E2-historical.json` |
| Current scan candidate JSONL | `scripts/captures/family-scan-currentpid-1948-20260520-003014-344522/api-family-vec3-candidates.jsonl` |
| Current proof readback | `scripts/captures/proof-anchor-currentpid-1948-readback-summary-20260519-211613.json` |
| Post-incident ProofOnly | `scripts/captures/live-test-ProofOnly-20260520-011554/run-summary.json` |
| Post-incident ChromaLink | `scripts/captures/chromalink-world-state-reference-20260520-011324-196091/summary.json` |
| Emergency key release | `scripts/captures/emergency-key-release-20260520-011453-542635/summary.json` |
| Input incident sequence | `scripts/captures/family-snapshot-sequence-currentpid-1948-20260520-010705-285310/summary.json` |
| Static-chain blocker | `scripts/captures/static-chain-current-target-pid1948-20260520-0058/resolve-source-cache-root-readback/summary.json` |
| Actor-yaw fail-closed smoke | `scripts/captures/actor-yaw-readback-smoke-currentpid-1948-20260520-005608/run-summary.json` |

## Input/spin incident summary

| Field | Value |
|---|---|
| Incident status | `agent-live-movement-paused-after-spin-incident` |
| Observed | `2026-05-20T01:08:38Z` |
| Auto-displacement | `WindowMessage W`, hold `250 ms` |
| Incident result | blocked: `no-delta-tracking-vec3-candidates` |
| Emergency release | passed; keyup-only; no key-down/movement |
| Post-incident proof | passed ProofOnly; `movementSent=false`, `movementAttempted=false` |
| Current policy | movement automation pause overrides prior movement authorization until reviewed/cleared |

## Current code/doc changes in working tree

| Path / group | Purpose |
|---|---|
| `docs/recovery/current-proof-anchor-readback.json`, `docs/recovery/current-truth.*` | Promote current PID 1948 proof, archive stale PID 27552, record geometry/input incident gates. |
| `scripts/coordinate_recovery_status.py` + tests | Exposes `movementAllowedEffective=false` when proof is valid but automation is paused. |
| `scripts/rift_live_test/emergency_key_release.py`, `scripts/rift_emergency_key_release.py`, `scripts/test_emergency_key_release.py` | Adds exact-target keyup-only emergency release helper. |
| `scripts/current_pid_family_snapshot_sequence.py` + tests | Adds default pre/post emergency key-release guard around auto-displacement. |
| `scripts/rift_live_test/actor_yaw_current_truth_status.py`, `actor_yaw_readback_smoke.py` + tests | Fail-closed on target drift instead of treating stale actor-yaw artifacts as current. |
| `scripts/rift_live_test/x64dbg_static_chain_resolve.py` + tests | Blocks implausible root pointer readbacks such as `0x10`. |
| `docs/handoffs/20260519-211920-current-proof-input-incident-recovery-handoff.md` | Earlier handoff for same incident/proof recovery. |

## Validation completed before this handoff

| Command | Result |
|---|---|
| `python .\scripts\validate_current_truth.py --json` | ✅ passed; artifactCount `71` |
| `python .\scripts\coordinate_recovery_status.py --json` | ✅ passed; movementAllowedEffective `false` |
| `.\scripts\riftreader-workflow-status.cmd --compact-json` | ⚠️ blocked intentionally by movement gate / input incident |
| `python -m unittest ...` targeted suite | ✅ `57 tests` OK |
| `git --no-pager diff --check` | ✅ no whitespace errors; CRLF warnings only |

## Stop / resume rules

1. If no truth is gained within 1 hour of the next live/recovery session, stop and preserve artifacts/status.
2. Do not send live movement/input from automation until the spin incident is reviewed and the pause is explicitly cleared.
3. Keyup-only emergency release is allowed as safety mitigation; it must remain exact PID/HWND targeted.
4. If the PID/HWND/process epoch changes, treat current proof as stale and rerun current-PID reacquisition from fresh API/runtime truth.
5. Keep RIFT client area exactly `640x360` before visual capture or input-sensitive workflows.
6. Do not use CE/x64dbg live attach unless explicitly reauthorized in a new user turn.
7. Do not use SavedVariables as live coordinate truth.
8. Do not edit ChromaLink or RiftScan provider repos from this lane.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Review the `WindowMessage W` auto-displacement path and why it caused spinning | Highest-risk blocker before any more movement automation. |
| 2 | Keep movement paused and run only no-input/read-only status commands | Preserves current proof without compounding the input incident. |
| 3 | Verify exact `640x360` client geometry at the start of the next session | User flagged geometry as result-affecting. |
| 4 | Inspect `command-envelopes.json` for the family snapshot incident | Confirms exact input method, key, hold, and process targeting. |
| 5 | Add/verify a bounded input-backend smoke that cannot hold/spin | Needed before clearing movement automation pause. |
| 6 | Re-run ChromaLink freshness + ProofOnly after any target restart | Keeps API-now vs memory-now proof current. |
| 7 | Keep actor-yaw/facing blocked until current-PID artifacts exist | Prevents stale yaw fields from contaminating movement decisions. |
| 8 | Treat static-chain formulas as historical only until a current resolver proves them | Current root slot already failed plausibility. |
| 9 | Continue family analysis offline/read-only using existing candidate files | Can recover patterns without sending input. |
| 10 | Commit the coherent safety/proof slice only after review | Working tree has meaningful docs/scripts/tests; keep commit scope explicit. |

## Safety summary

| Safety field | Value |
|---|---|
| movementSent by handoff creation | `false` |
| inputSent by handoff creation | `false` |
| reloaduiSent | `false` |
| screenshotKeySent | `false` |
| noCheatEngine | `true` |
| x64dbgAttach | `false` |
| SavedVariablesUsedAsLiveTruth | `false` |
| providerWrites | `false` |
| git ref mutation | `false` |
| repo file mutation | `true` — this handoff file only |
| staged/committed/pushed | `false` |

## Continuation update — 2026-05-19 21:31 local

After this handoff was created, the family snapshot workflow was hardened without sending live movement/input:

| Change | Result |
|---|---|
| `scripts/current_pid_family_snapshot_sequence.py` now imports current-truth `movementGate` and `clientGeometry` | Auto-displacement sees the same movement pause and `640x360` requirement recorded in current truth. |
| Auto-displacement now fails closed when current-truth movement gate is blocked | Verified with `--auto-displacement-key W`: status `blocked`, `movementSent=false`, `inputSent=false`; blockers were `current-truth-movement-gate-blocked`, `current-truth-automation-movement-paused`, and `current-truth-live-input-incident`. |
| Auto-displacement now verifies required client geometry before sending input | Uses current-truth `requiredClientWidth=640` / `requiredClientHeight=360`; blocks before input if the exact target client area drifts. |
| Emergency key-release pre/post guard remains enabled by default | Guard remains keyup-only and exact PID/HWND targeted. |
| Validation | `59` targeted tests passed; `validate_current_truth.py` passed; `coordinate_recovery_status.py` passed; `git diff --check` passed with CRLF warnings only. |

This means a future accidental `--auto-displacement-key` invocation cannot bypass the post-spin movement pause unless an explicit override flag is supplied after operator reauthorization.

## Continuation update — 2026-05-19 21:37 local

Additional no-live-input hardening was completed after reviewing the spin symptom:

| Change | Result |
|---|---|
| Emergency release helper can now plan/release mouse buttons with up-only events | Adds optional `--include-mouse-buttons` for left/right/middle mouse-up events; still never sends mouse-down or key-down. |
| Family snapshot emergency guard now includes mouse-button release | Future authorized auto-displacement pre/post guards can clear stuck mouse-look/turn state as well as keyboard movement/turn keys. |
| Root-cause note | Offline evidence does not prove a keybind issue. The incident command was `WindowMessage W` for 250 ms, but circular spinning is also consistent with a stuck mouse-look/turn state; the previous emergency helper was keyboard-only. |
| Validation | Emergency helper self-test passed; dry-run with `--include-mouse-buttons` planned only release/up events; targeted tests passed. |

Movement automation remains paused. These changes only make future recovery/guard behavior safer after the movement gate is explicitly cleared.

## Continuation update — 2026-05-19 21:40 local

No-input family/adjacent-family analysis was completed from existing current-PID candidate files:

| Finding | Evidence |
|---|---|
| Current anchor family survived across current-PID scans | `api-family-hit-000010 @ 0x1A91015CB00` is present in the anchor 16MiB family `0x1A910000000` across the compared scans. |
| Adjacent immediate 16MiB families did not produce candidate hits in these scans | Anchor family `+0` had 1 hit in each run; adjacent `-1` and `+1` had `0 / 0`. |
| Cross-run address overlap exists | 35 shared addresses between the 2026-05-19 and first 2026-05-20 scans; 28 shared addresses between each earlier scan and the latest 2026-05-20 scan. |
| Artifact | `scripts/captures/current-pid-family-neighborhood-analysis-1948-20260520-014004-594292/summary.json` and `.md`. |
| Safety | No input, no movement, no live memory read, no provider writes, no CE/x64dbg. |

Classification: useful offline reacquisition evidence only. It does not promote any new movement truth beyond the already-current ProofOnly anchor.

## Continuation update — 2026-05-19 21:44 local

The one-off current-PID family neighborhood analysis was promoted into a reusable repo helper:

| Change | Result |
|---|---|
| Added `scripts/current_pid_family_neighborhood_analysis.py` | Rebuilds current-PID family/adjacent-family overlap from existing candidate JSONL files. No live memory read, no input, no CE/x64dbg, no provider writes. |
| Added `scripts/test_current_pid_family_neighborhood_analysis.py` | Covers family alignment, candidate JSONL loading, anchor-family/adjacent-family overlap, pairwise shared-address counts, and current-truth bootstrapping. |
| Fresh artifact from reusable helper | `scripts/captures/current-pid-family-neighborhood-analysis-1948-20260520-014329-347891/summary.json`. |
| Reconfirmed result | Anchor family survived; immediate adjacent `-1/+1` 16MiB families had no hits; 35 cross-run shared addresses. |

This makes the family-survival truth reproducible after future restarts without reusing an ad-hoc shell block.

## Continuation update — 2026-05-19 21:47 local

RiftScan/RiftReader strategy gate blocker was fixed consumer-side:

| Finding / change | Result |
|---|---|
| Blocker found | `riftscan_milestone_review.py --compact-json` initially blocked because the current proof pointer's `matchFile` is a JSONL candidate file and the consumer attempted single-object JSON parsing (`JSONDecodeError: Extra data`). |
| Fix | `scripts/rift_live_test/riftscan_coordination.py` now supports RiftReader `api-family-vec3-candidates.jsonl` as a read-only candidate file. |
| Test | `scripts/test_riftscan_coordination.py` now covers JSONL candidate-file summarization. |
| Strategy gate after fix | `riftscan_milestone_review.py --compact-json` returns `ready-for-read-only-proof`, selecting `api-family-hit-000010` from the current proof pointer. |
| Coordination validation | `python scripts/validate_riftscan_coordination.py --pid 1948 --hwnd 0x3C0D58 --process-name rift_x64 --quick --compact-json` passed: 18 steps, 0 failures, writesToRiftScan=false. |

This does not grant movement permission; it only restores read-only strategy-gate consumption of the current RiftReader JSONL candidate file.


## Continuation update — 2026-05-19 21:51 EDT — workflow bridge command for family-neighborhood analysis

### What changed

- Added a thin launcher: `scripts\riftreader-family-neighborhood-analysis.cmd`.
- Added compact workflow/status bridge command key `family-neighborhood-analysis` in `tools\riftreader_workflow\status_packet.py`.
- Added status-packet test coverage so the command appears as existing and carries the explicit read-only safety statement.
- Hardened `scripts\test_current_pid_family_neighborhood_analysis.py` so package-style unittest invocation from repo root can import the helper consistently.

### Latest read-only family-neighborhood artifact

- `scripts\captures\current-pid-family-neighborhood-analysis-1948-20260520-015028-488548\summary.json`
- Anchor: `api-family-hit-000010 @ 0x1A91015CB00`
- Anchor family survived across the three current-PID candidate files.
- Immediate adjacent 16MiB families around the anchor remain empty in the analyzed files.
- This is offline candidate-neighborhood evidence only; it does not promote movement truth and it sends no live input/read/write.

### Validation

- `python -m unittest scripts.test_opencode_status_packet scripts.test_current_pid_family_neighborhood_analysis scripts.test_current_pid_family_snapshot_sequence scripts.test_emergency_key_release scripts.test_coordinate_recovery_status scripts.test_x64dbg_static_chain_resolve scripts.test_actor_yaw_current_truth_status scripts.test_actor_yaw_readback_smoke scripts.test_validate_current_truth scripts.test_current_truth_compact_summary scripts.test_riftscan_coordination scripts.test_riftscan_feedback scripts.test_riftscan_milestone_review scripts.test_riftscan_validation` → 96 tests OK.
- `scripts\riftreader-family-neighborhood-analysis.cmd --self-test --json` → passed.
- `scripts\riftreader-family-neighborhood-analysis.cmd --json` → passed and wrote the artifact above.
- `scripts\riftreader-workflow-status.cmd --compact-json` → returned blocked as expected because movement automation is still paused after the spin incident; bridge command now appears with `exists=true`.
- `git --no-pager diff --check` → passed; CRLF warnings only.

### Safety state

- movementSent: false for this continuation.
- inputSent: false for this continuation.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.

## Continuation update — 2026-05-19 21:54 EDT — WindowMessage auto-displacement fail-closed hardening

### What changed

- Added `auto_displacement_backend_blockers()` to `scripts\current_pid_family_snapshot_sequence.py`.
- Added CLI flag `--allow-window-message-auto-displacement`.
- Auto-displacement with `--auto-displacement-key` now blocks by default with `auto-displacement-window-message-backend-blocked` before preflight/input, unless that explicit override is passed.
- This is independent of the current-truth movement gate: even if the movement gate is later cleared, the WindowMessage backend must be explicitly reauthorized before reuse.
- Added regression coverage in `scripts\test_current_pid_family_snapshot_sequence.py` and made the test import path robust for repo-root package-style unittest runs.

### Validation

- `python -m unittest scripts.test_current_pid_family_snapshot_sequence` → 15 tests OK.
- `python .\scripts\current_pid_family_snapshot_sequence.py --self-test --json` → passed; no live process queried.
- `python -m unittest scripts.test_opencode_status_packet scripts.test_current_pid_family_neighborhood_analysis scripts.test_current_pid_family_snapshot_sequence scripts.test_emergency_key_release scripts.test_coordinate_recovery_status scripts.test_x64dbg_static_chain_resolve scripts.test_actor_yaw_current_truth_status scripts.test_actor_yaw_readback_smoke scripts.test_validate_current_truth scripts.test_current_truth_compact_summary scripts.test_riftscan_coordination scripts.test_riftscan_feedback scripts.test_riftscan_milestone_review scripts.test_riftscan_validation` → 97 tests OK.
- `git --no-pager diff --check` → passed; CRLF warnings only.

### Safety state

- movementSent: false for this continuation.
- inputSent: false for this continuation.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.

## Continuation update — 2026-05-19 21:56 EDT — emergency release workflow bridge command

### What changed

- Added `scripts\riftreader-emergency-release.cmd` as a thin launcher for `scripts\rift_emergency_key_release.py`.
- Added compact workflow/status bridge command key `emergency-release` in `tools\riftreader_workflow\status_packet.py`.
- The advertised command uses `--include-mouse-buttons` and records the safety boundary: release/up events only; no key-down, mouse-down, movement, debugger, or provider writes.
- Added status-packet test coverage and made `scripts\test_emergency_key_release.py` robust for repo-root package-style unittest runs.

### Validation

- `python -m unittest scripts.test_opencode_status_packet scripts.test_emergency_key_release` → 19 tests OK.
- `scripts\riftreader-emergency-release.cmd --self-test --json` → passed.
- `scripts\riftreader-emergency-release.cmd --pid 99 --hwnd 0x1234 --dry-run --include-mouse-buttons --json` → planned only; `inputSent=false`, `movementSent=false`, `keyDownSent=false`, `mouseDownSent=false`.
- `scripts\riftreader-workflow-status.cmd --compact-json` → returned blocked as expected because movement automation is still paused; `emergency-release` bridge command appears with `exists=true`.
- `python -m unittest scripts.test_opencode_status_packet scripts.test_current_pid_family_neighborhood_analysis scripts.test_current_pid_family_snapshot_sequence scripts.test_emergency_key_release scripts.test_coordinate_recovery_status scripts.test_x64dbg_static_chain_resolve scripts.test_actor_yaw_current_truth_status scripts.test_actor_yaw_readback_smoke scripts.test_validate_current_truth scripts.test_current_truth_compact_summary scripts.test_riftscan_coordination scripts.test_riftscan_feedback scripts.test_riftscan_milestone_review scripts.test_riftscan_validation` → 97 tests OK.
- `git --no-pager diff --check` → passed; CRLF warnings only.

### Safety state

- movementSent: false for this continuation.
- inputSent: false for this continuation.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.

## Continuation update — 2026-05-19 21:59 EDT — current-truth docs aligned with new input guardrails

### What changed

- Updated `docs\recovery\current-truth.json` and `docs\recovery\current-truth.md` so the movement/input section reflects the new state:
  - coordinate proof remains current for PID `1948` / HWND `0x3C0D58`;
  - movement automation remains paused;
  - `WindowMessage` auto-displacement is blocked by default by `scripts\current_pid_family_snapshot_sequence.py`;
  - explicit override is `--allow-window-message-auto-displacement` after incident review;
  - emergency release is available through `scripts\riftreader-emergency-release.cmd`.
- Added canonical artifact references for the emergency release launcher, family-neighborhood launcher/helper, workflow status packet, and snapshot sequence guard.
- Added `scripts\__init__.py` so repo-root `python -m unittest scripts.*` runs consistently expose `scripts\` imports such as `rift_live_test`.

### Validation

- `python .\scripts\validate_current_truth.py --json` → passed; 76 artifact paths checked.
- `python .\scripts\coordinate_recovery_status.py --json` → passed; proof current, `movementAllowed=true`, effective movement still `false` due incident gate.
- `scripts\riftreader-workflow-status.cmd --compact-json` → returned blocked as expected; updated movement reason and bridge commands present.
- `python -m unittest scripts.test_validate_current_truth scripts.test_current_truth_compact_summary scripts.test_coordinate_recovery_status scripts.test_opencode_status_packet scripts.test_current_pid_family_snapshot_sequence scripts.test_emergency_key_release scripts.test_current_pid_family_neighborhood_analysis` → 49 tests OK.
- `python -m unittest scripts.test_actor_yaw_current_truth_status scripts.test_actor_yaw_readback_smoke scripts.test_x64dbg_static_chain_resolve scripts.test_riftscan_coordination scripts.test_riftscan_feedback scripts.test_riftscan_milestone_review scripts.test_riftscan_validation` → 48 tests OK.
- Combined targeted suite (`scripts.test_opencode_status_packet ... scripts.test_riftscan_validation`) → 97 tests OK.
- `git --no-pager diff --check` → passed; CRLF warnings only.

### Safety state

- movementSent: false for this continuation.
- inputSent: false for this continuation.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.

## Continuation update — 2026-05-19 22:07 EDT — additional live-input surface hardening

### What changed

- Inspected live-input call sites for `post-rift-key.ps1`, `WindowMessage`, `UseWindowMessage`, SendInput, and movement profile paths.
- Hardened `scripts\invoke-gated-forward-smoke.ps1`:
  - `window-message` remains a valid explicit backend value, but is now blocked by default after the spin incident.
  - New explicit override: `-AllowWindowMessageBackend`.
  - Default block status: `blocked-input-backend` with issue `window-message-input-backend-blocked-after-spin-incident`.
  - The block happens before preflight/key invocation, so no input is attempted or sent.
- Updated `scripts\test-invoke-gated-forward-smoke.ps1`:
  - verifies default WindowMessage backend blocks before preflight/input;
  - verifies explicit override still exercises the legacy path for regression fixtures;
  - added `ConvertFrom-JsonCompat` so the test works in both Windows PowerShell and PowerShell 7.
- Hardened turn-key profiling:
  - `scripts\rift_live_test\turn_keys.py` blocks live `post-message` input unless `allow_post_message_input=True`.
  - `scripts\profile_turn_keys.py` adds `--allow-post-message-input` and emits structured blocked JSON instead of a traceback when blocked.
  - Added regression coverage in `scripts\test_turn_key_profile.py`.
- Updated `docs\recovery\current-truth.json` and `.md` with the new gated-forward and turn-key post-message guardrails.

### Validation

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-invoke-gated-forward-smoke.ps1` → passed.
- `pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-invoke-gated-forward-smoke.ps1` → passed.
- `python -m unittest scripts.test_turn_key_profile` → 10 tests OK.
- `python .\scripts\profile_turn_keys.py --pid 123 --hwnd 0x123 --live --input-modes post-message --keys D --repeat 1 --output-root .riftreader-local\turn-key-guard-smoke` → structured `blocked-input-backend`, `inputSent=false`, `movementSent=false`.
- `python .\scripts\validate_current_truth.py --json` → passed; 81 artifact paths checked.
- Combined targeted suite including turn-key profile (`scripts.test_opencode_status_packet ... scripts.test_turn_key_profile`) → 107 tests OK.
- `git --no-pager diff --check` → passed; CRLF warnings only.

### Safety state

- movementSent: false for this continuation.
- inputSent: false for this continuation.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.

## Continuation update — 2026-05-19 22:16 EDT — read-only live-input surface audit

### What changed

- Added `scripts\live_input_surface_audit.py`, a reusable read-only source audit for live-input-capable surfaces.
- Added thin launcher `scripts\riftreader-live-input-surface-audit.cmd`.
- Added status-packet bridge command key `live-input-surface-audit` in `tools\riftreader_workflow\status_packet.py`.
- Added regression coverage in `scripts\test_live_input_surface_audit.py` and status-packet coverage in `scripts\test_opencode_status_packet.py`.
- The helper scans repo-owned `scripts\` and `tools\` source files only, skips generated captures/build output, and writes durable JSON/Markdown under `scripts\captures\live-input-surface-audit-*`.
- Latest audit artifact: `scripts\captures\live-input-surface-audit-20260520-021631-803449\summary.json` / `summary.md`.

### Latest audit result

- Status: `passed-with-review-required`.
- Surfaces found: `49`.
- Guarded surfaces: `5`.
- Release-only surfaces: `1`.
- Review-required surfaces: `30`.
- Critical/forbidden surfaces: `2` (`scripts\capture_x64dbg_coord_copy_probe_batch.py`, `scripts\rift_live_test\x64dbg_live_access_capture.py`).
- Current-truth movement gate read by the audit: `blocked-live-input-spin-incident`, `automationMovementPaused=true`, required client geometry `640x360`.
- No surface is promoted or authorized by this audit; it is inventory only.

### Validation

- `python -m unittest scripts.test_live_input_surface_audit scripts.test_opencode_status_packet` → 18 tests OK.
- `scripts\riftreader-live-input-surface-audit.cmd --self-test --json` → passed.
- `scripts\riftreader-live-input-surface-audit.cmd --json` → passed and wrote `scripts\captures\live-input-surface-audit-20260520-021631-803449\summary.json`.
- `scripts\riftreader-workflow-status.cmd --compact-json` → returned blocked as expected because movement automation is still paused; `live-input-surface-audit` bridge command appears with `exists=true`.

### Safety state

- movementSent: false for this continuation.
- inputSent: false for this continuation.
- reloaduiSent: false.
- screenshotKeySent: false.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.
