# RiftReader current proof + input incident recovery handoff — 2026-05-19 21:19 EDT

## TL;DR

- Current coordinate proof anchor survived the post-update recovery and is still valid for PID `1948` / HWND `0x3C0D58`.
- Current anchor: `api-family-hit-000010 @ 0x1A91015CB00` from `scripts/captures/family-scan-currentpid-1948-20260520-003014-344522/api-family-vec3-candidates.jsonl`.
- Post-incident `ProofOnly` passed with `movementSent=false` / `movementAttempted=false`.
- Current coordinate after incident: `x=7298.86572265625, y=818.2576904296875, z=3013.78515625`.
- Live movement automation is paused because a family snapshot auto-displacement sent `WindowMessage W` for `250 ms` and the operator observed spinning.
- Emergency key-release helper was added and validated: `scripts/rift_emergency_key_release.py`.

## Current status

| Surface | Status | Evidence |
|---|---|---|
| Target | `current` | PID `1948`, HWND `0x3C0D58`, module base `0x7FF7B77A0000` |
| Coordinate proof | `current-valid` | `scripts/captures/live-test-ProofOnly-20260520-011554/run-summary.json` |
| Current coordinate | `fresh` | `x=7298.86572265625, y=818.2576904296875, z=3013.78515625` |
| ChromaLink | `fresh/stable` | `scripts/captures/chromalink-world-state-reference-20260520-011324-196091/rift-api-reference-currentpid-1948-20260520-011324-249862.json`; two-sample planar delta `0` |
| Movement automation | `paused` | `blocked-live-input-spin-incident` in `docs/recovery/current-truth.json` |
| Actor yaw/facing | `blocked-target-drift` | old PID `33912` / HWND `0xE0DB2`; current readback smoke failed closed |
| Static chain | `blocked-root-pointer-not-plausible` | current `rift_x64.exe+0x32E1780` root slot read `0x10` |

## What happened in the input incident

The richer current-PID family-neighborhood snapshot sequence was run with:

```text
python .\scripts\current_pid_family_snapshot_sequence.py --pid 1948 --hwnd 0x3C0D58 --process-name rift_x64 --reference-source chromalink --scan-plan .\scripts\captures\memory-region-inventory-currentpid-1948-20260520-010617-064995\scan-plan.json --auto-displacement-key W --auto-displacement-hold-ms 250 --auto-displacement-timeout-seconds 15 --json
```

Artifacts:

- Summary: `scripts/captures/family-snapshot-sequence-currentpid-1948-20260520-010705-285310/summary.json`
- Command envelopes: `scripts/captures/family-snapshot-sequence-currentpid-1948-20260520-010705-285310/command-envelopes.json`
- Delta analysis: `scripts/captures/family-snapshot-sequence-currentpid-1948-20260520-010705-285310/delta-analysis/delta-summary.json`

Observed command envelope:

- Stage: `auto-displacement`
- Key: `W`
- Hold: `250 ms`
- Input method: `WindowMessage`
- Exit: `0`

Result:

- Sequence read `39` selected ranges: `15` prior exact windows, `4` prior-family neighborhoods, `20` current scan-plan ranges.
- Delta analyzer blocked with `no-delta-tracking-vec3-candidates`.
- Operator reported the player spinning.
- Emergency release was sent and then made durable.

## New helper added

| File | Purpose |
|---|---|
| `scripts/rift_live_test/emergency_key_release.py` | Windows exact-target keyup-only release helper; sends `WM_KEYUP` + `SendInput KEYEVENTF_KEYUP` only |
| `scripts/rift_emergency_key_release.py` | Thin CLI wrapper |
| `scripts/test_emergency_key_release.py` | Unit tests for key list, aliases, dry-run, and keyup-only semantics |

Validated commands:

```text
python .\scripts\rift_emergency_key_release.py --self-test --json
python .\scripts\rift_emergency_key_release.py --pid 1948 --hwnd 0x3C0D58 --process-name rift_x64 --dry-run --output-root .\scripts\captures --json
python .\scripts\rift_emergency_key_release.py --pid 1948 --hwnd 0x3C0D58 --process-name rift_x64 --output-root .\scripts\captures --json
```

Live release artifact:

- `scripts/captures/emergency-key-release-20260520-011453-542635/summary.json`
- Safety: `movementSent=false`, `keyDownSent=false`, `mouseDownSent=false`, `inputType=keyup-only`
- All PostMessage and SendInput keyups succeeded.

## Current blockers

| Blocker | Exact state |
|---|---|
| Movement automation | Paused after spin incident; proof remains valid, but effective movement is false in status output |
| Actor yaw/facing | Stale promoted lead from PID `33912`; current PID `1948` revalidation needed before auto-turn/facing |
| Static chain | Historical root RVA `0x32E1780` read back `0x10` at current VA `0x7FF7BAA81780`; not plausible |
| Adjacent family snapshot | Ran broad/prior-neighborhood set but yielded `no-delta-tracking-vec3-candidates` |

## Validation performed

```text
python .\scripts\validate_current_truth.py --json
python .\scripts\coordinate_recovery_status.py --json
.\scripts\riftreader-workflow-status.cmd --compact-json
$env:PYTHONPATH=(Resolve-Path .\scripts).Path; python -m unittest scripts.test_emergency_key_release scripts.test_coordinate_recovery_status scripts.test_x64dbg_static_chain_resolve scripts.test_actor_yaw_current_truth_status scripts.test_actor_yaw_readback_smoke scripts.test_validate_current_truth scripts.test_current_truth_compact_summary scripts.test_opencode_status_packet

git --no-pager diff --check
```

Results:

- `validate_current_truth`: passed, no warnings.
- `coordinate_recovery_status`: passed; proof `movementAllowed=true`, effective movement `movementAllowedEffective=false` due input incident pause.
- `riftreader-workflow-status`: blocked by design; movement gate `allowed=false`, status `blocked-live-input-spin-incident`.
- Unit tests: `46` passed.
- `git diff --check`: passed; only normal CRLF warnings from Git.

## Resume sequence

1. Do not run more live movement automation yet.
2. Continue read-only proof/anchor analysis if needed.
3. Review `scripts/post-rift-key.ps1` WindowMessage backend behavior and compare with C# SendInput `ScanCode` backend before re-enabling movement.
4. Wire `scripts/rift_emergency_key_release.py` as a pre/post guard around any future movement workflow.
5. If movement is re-enabled, start with a tiny exact-target smoke only after key-release guard and post-readback are green.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Harden movement wrappers to run emergency key-release before and after input | Prevent stuck/spin state from persisting |
| 2 | Disable `--auto-displacement-key` use in family snapshots by default | The last run produced unsafe spin and no candidates |
| 3 | Compare WindowMessage `W` with C# SendInput `ScanCode` in a guarded dry/smoke path | Identify backend-specific cause |
| 4 | Add a target-control field for `inputBackendPaused` | Prevent scripts from treating proof-valid as movement-safe |
| 5 | Keep `ProofOnly` available | It refreshed the proof safely with no movement |
| 6 | Analyze the blocked family snapshot offline | It still records useful changed-byte/family range evidence |
| 7 | Re-run adjacent-family snapshots only without auto input or with manual operator movement | Avoid agent-caused spin while collecting evidence |
| 8 | Keep actor yaw/facing blocked | Current promoted yaw lead is stale for PID `1948` |
| 9 | Keep static-chain root demoted | Current root slot read `0x10`, not a valid owner pointer |
| 10 | Commit the safety/reporting slice separately from future live-input fixes | Keeps review clean and rollback simple |


## Window geometry note

Current exact-target geometry check for PID `1948` / HWND `0x3C0D58`:

- Client rect: `640x360` — OK.
- Outer window rect: `656x399` because of borders/titlebar.
- Treat client size as the hard gate for visual/capture workflows.
- Use `tools/RiftReader.WindowTools inspect` / `resize --client-width 640 --client-height 360` on the exact HWND if it drifts.
