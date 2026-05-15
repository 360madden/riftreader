# Static-chain offline/read-only handoff — current coordinate anchor

Generated: `2026-05-15T03:10:10.144801-04:00` local / `2026-05-15T07:10:10.146360+00:00` UTC

## Verdict

The current coordinate proof anchor remains valid for the current live target, but the stable static pointer chain is **not discovered yet**. This handoff preserves the latest offline/read-only x64dbg static-chain plan as a tracked repo document. It does **not** approve or perform x64dbg live attach, watchpoints, stepping, breakpoints, target memory writes, CE, game input, or movement.

## Current committed coordinate proof

| Item | Value |
|---|---|
| committed HEAD | `a73ef6a` |
| proof pointer file | `docs/recovery/current-proof-anchor-readback.json` |
| status | `current-target-proofonly-passed` |
| lastUpdatedUtc | `2026-05-15T06:59:08.641457+00:00` |
| processName | `rift_x64` |
| processId | `27552` |
| targetWindowHandle | `0x3411E2` |
| candidateId | `api-family-hit-000001` |
| anchorAddress | `0x27B1ED850C0` |
| supportCount | `6` |
| x | `7314.9091796875` |
| y | `875.12158203125` |
| z | `3052.639892578125` |
| coordinateRecordedAtUtc | `2026-05-15T06:59:07.9448272Z` |
| latestProofOnlyStatus | `passed-proof-only` |
| latestProofOnlyGeneratedAtUtc | `2026-05-15T06:59:08.635200+00:00` |

## Latest offline static-chain plan

| Item | Value |
|---|---|
| plan status | `planned` |
| plan generatedAtUtc | `2026-05-15T07:06:42Z` |
| process | `rift_x64` |
| pid | `27552` |
| hwnd | `0x3411E2` |
| processStartUtc | `2026-05-15T01:11:57.750696Z` |
| moduleBaseAddressHex | `0x7FF71CD90000` |
| truth source | `chromalink-riftreader-world-state` |
| truth sampledAtUtc | `2026-05-15T07:06:38.4598252+00:00` |
| truth x | `7314.91` |
| truth y | `875.12` |
| truth z | `3052.64` |
| candidateId | `api-family-hit-000001` |
| candidateAddress | `0x27B1ED850C0` |
| axisOrder | `xyz` |
| watchSizeBytes | `12` |
| poseCountRequired | `3` |
| preflightStatus | `passed` |
| preflightDebuggerProcessCount | `0` |
| readinessStatus | `ready-for-current-turn-approval` |
| readyForBoundedDebuggerCapture | `False` |

## Safety boundary

| Item | Value |
|---|---|
| movementSent | `False` |
| inputSent | `False` |
| noCheatEngine | `True` |
| x64dbgLiveAttachStarted | `False` |
| x64dbgCommandsExecuted | `False` |
| processAttachOrMemoryReadStarted | `False` |
| targetMutationAllowed | `False` |
| candidateOnly | `True` |

Important current-session note: a later process scan saw `rifterrorhandler_x64` running. This handoff remains valid for offline planning, but any future live x64dbg attach/watchpoint lane must first clear/understand that process and rerun same-target no-attach preflight.

## Blockers

- None.

## Warnings

- `x64dbg live RIFT attach is not authorized in this plan; request explicit current-turn approval before any attach/watchpoint session`

## Readiness checks

| Check | Status | Passed | Detail |
|---|---:|---:|---|
| `target-identity-complete` | `passed` | `True` | PID, HWND, process start UTC, and module base are present. |
| `strict-no-attach-preflight` | `passed` | `True` | A passed same-target no-attach preflight with zero debugger-class processes is required before live debugger approval. |
| `api-coordinate-present` | `passed` | `True` | API/runtime coordinate X/Y/Z and sampled UTC are present. |
| `candidate-address-present` | `passed` | `True` | A coordinate candidate address is present for the planned watch window. |
| `live-attach-policy-bounds` | `passed` | `True` | Live attach timeout, unresponsive abort, and go/run attempt limits are within policy. |
| `artifact-age-policy` | `passed` | `True` | Optional max-age checks for preflight/API artifacts are satisfied, or no max age was requested. |
| `strict-live-debugger-readiness-preset` | `passed` | `True` | When enabled, strict readiness requires preflight, API coordinate, and candidate artifacts plus max-age gates. |
| `current-turn-debugger-approval` | `pending` | `False` | Live debugger capture still requires explicit current-turn approval; planner generation is artifact-only. |

## Promotion gates still required

1. same PID/HWND/process-start target for all samples
2. fresh API/runtime coordinate sampled close to each chain read
3. same chain tracks X/Y/Z across at least three displaced poses
4. module-relative or static-owner root, not heap-only
5. restart/client-epoch validation
6. repo-owned runtime readback without x64dbg
7. same-target ProofOnly pass before movement

## Artifact references

| Item | Value |
|---|---|
| summaryJson | `C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-static-chain-plan-static-chain-refresh-20260515-0706\coord-chain-plan-summary.json` |
| summaryMarkdown | `C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-static-chain-plan-static-chain-refresh-20260515-0706\coord-chain-plan.md` |
| candidateTemplateJson | `C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-static-chain-plan-static-chain-refresh-20260515-0706\x64dbg-coordinate-chain-candidate-template.json` |
| sessionChecklistMarkdown | `C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-static-chain-plan-static-chain-refresh-20260515-0706\x64dbg-coordinate-chain-session-checklist.md` |
| rerunCommandText | `C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-static-chain-plan-static-chain-refresh-20260515-0706\x64dbg-coordinate-chain-rerun-command.txt` |
| compactHandoffJson | `C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-static-chain-plan-static-chain-refresh-20260515-0706\x64dbg-coordinate-chain-compact-handoff.json` |
| compactHandoffMarkdown | `C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-static-chain-plan-static-chain-refresh-20260515-0706\x64dbg-coordinate-chain-compact-handoff.md` |
| runDirectory | `C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-static-chain-plan-static-chain-refresh-20260515-0706` |

## Exact next safe workflow

| # | Action | Why |
|---:|---|---|
| 1 | Keep `docs/recovery/current-proof-anchor-readback.json` as the committed current proof pointer. | It is the latest pushed current-truth contract. |
| 2 | Do not commit timestamp-only ProofOnly refreshes. | Anchor/PID/coordinate are unchanged, so timestamp churn is noise. |
| 3 | Treat this document as the tracked static-chain resume point. | It preserves the ignored capture artifact paths in repo history. |
| 4 | Keep CE disabled. | The current recovery lane is no-CE. |
| 5 | Keep x64dbg live attach/watchpoints blocked without explicit current-turn approval. | The plan is offline/read-only only. |
| 6 | Before any future live debugger session, rerun no-attach preflight and confirm no `rifterrorhandler_x64` risk. | The process appeared after the latest plan. |
| 7 | If live x64dbg is approved later, watch the 12-byte XYZ window at the candidate address only. | Keeps the debugger session narrow. |
| 8 | Ingest any manual access event with `scripts/x64dbg_access_event_ingest.py`. | Converts debugger notes into repo-owned evidence. |
| 9 | Validate chain-now vs API-now outside x64dbg before promotion. | x64dbg access events are candidate evidence only. |
| 10 | Require multi-pose, restart/client-epoch, runtime readback, and ProofOnly before movement eligibility. | Prevents static-chain false positives from becoming movement truth. |

## Ready-to-paste resume prompt

```text
Resume static-chain discovery from `docs/handoffs/2026-05-15-0310-static-chain-offline-readonly-handoff.md`.
Do not use CE. Do not attach x64dbg, set watchpoints/breakpoints, step/trace, or send game input unless I explicitly approve that in the current turn.
First rerun no-attach preflight for PID/HWND/process-start/module-base and check whether rifterrorhandler_x64 is still running.
Treat `0x27B1ED850C0` as current only for PID 27552 / HWND 0x3411E2 / process start `2026-05-15T01:11:57.750696Z`; after any restart it is stale and only a reacquisition hint.
Continue with offline/read-only static-chain evidence handling and promote nothing until API-now vs chain-now, multi-pose, restart/client-epoch, runtime readback, and ProofOnly gates pass.
```
