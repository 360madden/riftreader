# **⚠️ COMPACT HANDOFF — Current-PID actor coordinate chain recovery**

Generated: `2026-05-21T15:43Z`
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main` at `f7f0023 Classify coordinate chain candidates semantically`
Remote state observed: `main` is ahead of `origin/main` by 7 commits.
Working tree before this handoff: clean.

## Verdict

| Item | Current status |
|---|---|
| Live RIFT target | One visible/responding `rift_x64` window: PID `67680`, HWND `0x120CBE` |
| Process start | `2026-05-21T10:38:42.1275829-04:00` / `2026-05-21T14:38:42.127583Z` |
| Current proof anchor | Recovered and same-target `ProofOnly` passed |
| Current proof address | `0x242D3DEF010` |
| Actor-like candidate | `0x242E9932F70`, candidate-only, not promotion eligible yet |
| Static pointer chain | Not proven yet |
| x64dbg attach | User authorized attach, but no attach was started before this handoff |
| Safety | No CE, no live debug scan, no memory writes, no provider writes |

Workflow note: use the optimized provenance-first workflow in
`C:\RIFT MODDING\RiftReader\docs\recovery\optimized-player-actor-coordinate-chain-workflow.md`.
Do not regress into repeating broad coordinate value scans once the actor-like
candidate/owner hypothesis is selected.

## Current target and proof state

Fresh read-only checks were run:

| Check | Result |
|---|---|
| `.\scripts\get-rift-window-targets.ps1 -Json` | `ok=true`, `count=1`, PID `67680`, HWND `0x120CBE`, title `RIFT`, responding |
| `python .\scripts\coordinate_recovery_status.py --json` | `status=passed`, blockers `[]`, current proof `current-target-proofonly-passed` |

Current proof file:

`C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json`

Key proof fields:

| Field | Value |
|---|---|
| Proof status | `current-target-proofonly-passed` |
| Movement allowed effective | `true` |
| Proof candidate | `api-family-hit-000001` |
| Proof address | `0x242D3DEF010` |
| Candidate file | `C:\RIFT MODDING\RiftReader\scripts\captures\family-scan-currentpid-67680-20260521-144558-743437\api-family-vec3-candidates.jsonl` |
| Latest ProofOnly summary | `C:\RIFT MODDING\RiftReader\scripts\captures\recover-currentpid-coord-anchor-fast-execute-67680-20260521-144213-194350\07-proofonly\live-test-ProofOnly-20260521-145107\run-summary.json` |
| Latest current coordinate | `X=7371.48876953125`, `Y=868.26171875`, `Z=2997.662109375` at `2026-05-21T14:52:00.1090847Z` |

Important: `0x242D3DEF010` is the current movement-grade proof/API-family anchor for PID `67680`; it is not the finished static player-actor pointer chain.

## Actor-like coordinate candidate lead

Candidate from full current-PID scan:

| Field | Value |
|---|---|
| Candidate address | `0x242E9932F70` |
| Candidate file | `C:\RIFT MODDING\RiftReader\scripts\captures\family-scan-currentpid-67680-20260521-150638-568860\api-family-vec3-candidates.json` |
| Scan summary | `C:\RIFT MODDING\RiftReader\scripts\captures\coordinate-scan-plan-batch-currentpid-67680-20260521-150332-341605\summary.json` |
| Semantics | `actor-like-offset-coordinate-candidate` |
| Promotion | `promotionEligible=false`, `candidateOnly=true` |
| Evidence | X/Z track fresh API across poses; Y is stable offset around API Y + `~1.544` |

Owner-like structure evidence:

| Field | Value |
|---|---|
| Hypothesized owner base | `0x242E9932D70` |
| Coordinate offset from owner | `+0x200` |
| Module pointer fields | `+0x18 -> RVA 0x3562D50`, `+0x30 -> RVA 0x3566B60`, `+0x38 -> RVA 0x3565170`, `+0x40 -> RVA 0x3564780`, `+0xE0 -> RVA 0x2725638` |
| Strong module-hint match | Owner candidate matched all 5/5 module fields |
| Root status | Strong owner signature, but no static root/chain proven |

Key actor-candidate artifacts:

| Artifact | Path |
|---|---|
| Pose validation | `C:\RIFT MODDING\RiftReader\scripts\captures\actor-candidate-pose-validation-67680-20260521-151040\coordinate-anchor-batch-summary.json` |
| Root signature | `C:\RIFT MODDING\RiftReader\scripts\captures\actor-candidate-root-signature-67680-20260521-151540\root-signature.json` |
| Module hint sweep | `C:\RIFT MODDING\RiftReader\scripts\captures\root-signature-module-hint-sweep-20260521-151617-358192\summary.json` |
| Family classifier | `C:\RIFT MODDING\RiftReader\scripts\captures\root-signature-family-classifier-20260521-151630-238569\summary.json` |
| Semantic classifier | `C:\RIFT MODDING\RiftReader\scripts\captures\coordinate-candidate-semantic-classifier-20260521-153501-617415\summary.json` |
| x64dbg chain plan | `C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-coord-chain-plan-20260521-153248-276117\coord-chain-plan-summary.json` |

## Safety constraints for resume

| Constraint | Resume rule |
|---|---|
| Stale data | Do not use stale PID, stale absolute address, or old proof artifact as current truth |
| Current authority | API-now vs memory-now remains authority |
| SavedVariables | Do not use SavedVariables as live truth |
| Cheat Engine | Do not use CE |
| x64dbg | User authorized attach, but only bounded/non-aggressive attach; no debug scan |
| Memory writes | None allowed |
| Movement | Current proof movement gate is passed, but static-chain discovery should not require movement first |
| Target drift | If PID/HWND/process start changes, stop and rerun current-PID reacquisition |

## Recommended immediate resume commands

Reconfirm target first:

```powershell
.\scripts\get-rift-window-targets.ps1 -Json
python .\scripts\coordinate_recovery_status.py --json
```

Safest first x64dbg action is stop-context only. It should attach, capture initial context, detach/resume, and then verify responsiveness. Do not set breakpoints in the first probe.

```powershell
python .\scripts\x64dbg_live_access_capture.py --allow-live-debugger --capture-mode stop-context --target-pid 67680 --target-hwnd 0x120CBE --process-start-time-utc 2026-05-21T14:38:42.127583Z --expected-module-base 0x7FF6A24B0000 --candidate-address 0x242E9932F70 --candidate-evidence-file "C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-coord-chain-plan-20260521-153248-276117\coord-chain-plan-summary.json" --read-size 64 --max-live-attach-seconds 15 --detach-timeout-seconds 10 --unresponsive-abort-seconds 10 --max-go-attempts 1 --ignore-rift-error-handler --json
```

If and only if stop-context succeeds and RIFT remains responsive, the next bounded option is one hardware read watchpoint on `0x242E9932F70`, no stimulus, short timeout, max one go attempt. Avoid `memory-access` mode unless a later explicit decision accepts the extra risk.

## Validation already completed in this slice

| Validation | Result |
|---|---|
| `python -m unittest scripts.test_coordinate_candidate_semantic_classifier scripts.test_x64dbg_coord_chain_plan scripts.test_pointer_family_scan scripts.test_pointer_owner_batch_inspector scripts.test_root_signature_batch_sweep scripts.test_root_signature_module_hint_sweep scripts.test_root_signature_family_classifier` | Passed, 74 tests |
| `python -m json.tool` on x64dbg plan summary | Passed |
| `python -m json.tool` on semantic classifier summary | Passed |
| `python -m json.tool` on actor root signature | Passed |
| `python .\scripts\coordinate_recovery_status.py --json` at handoff time | Passed |

## Latest commits relevant to this handoff

| Commit | Meaning |
|---|---|
| `f7f0023` | Added semantic classifier for coordinate candidate families |
| `19060db` | Recovered current proof anchor after restart for PID `67680` |
| `dc4d2a6` | Allowed BOM API artifacts in x64dbg coord plan |
| `a74cd9f` | Hardened root signature coord pointer slot handling |
| `0d7fea4` | Recovered current-PID coord anchor and planned static chain discovery |
| `52a3ff6` | Added displacement gate to current-PID coordinate reacquisition |

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Reconfirm PID/HWND/process start before any attach | Prevents acting on stale target state |
| 2 | Run `coordinate_recovery_status.py --json` | Confirms proof anchor and target still match |
| 3 | Run x64dbg `stop-context` only | Lowest-risk attach sanity check |
| 4 | Validate the stop-context summary with `python -m json.tool` | Ensures artifact is usable for next steps |
| 5 | Verify RIFT window remains responding after detach | Catch attach-side effects immediately |
| 6 | If safe, run one short hardware-read watchpoint on `0x242E9932F70` | Finds access context without aggressive scanning |
| 7 | Ingest any access event with `x64dbg_access_event_ingest.py` | Converts debugger evidence into repo-owned normalized artifacts |
| 8 | Map instruction/module/RVA context to owner `0x242E9932D70` and offset `+0x200` | Tests whether the actor-like owner has repeatable provenance |
| 9 | Build a candidate chain resolver only from normalized access/static evidence | Avoids hand-transcribed or stale chain truth |
| 10 | Require multi-pose API-now vs chain-now plus same-target ProofOnly before promotion | Keeps movement/navigation truth fail-closed |
