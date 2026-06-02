# Post-update recovery/reacquisition handoff — 2026-06-02 20:22 UTC

## Verdict

The repository is clean and aligned with `origin/main` at commit
`918595b Add post-update global container coordinate readback`.

The 2026-06-02 RIFT update invalidated the old promoted static owner root for
the current epoch. The latest blocked-safe packet still reports
`[rift_x64+0x32EBC80] == 0x0`, so stale 2026-06-01 promoted coordinate truth
must not be used for navigation.

Recovery has a strong **candidate-only** coordinate readback:

`[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30`

This chain passed no-input current readback and a five-sample stationary
polling baseline in the latest durable artifacts, but it is **not promoted**,
**not restart/relog proof**, and **not movement/displacement proof**.

## Current status

| Surface | Status |
|---|---|
| Git | `main` clean and aligned with `origin/main`; HEAD `918595b`. |
| Decision packet | `blocked-safe`; latest command returned exit code `2`, which is expected for the known post-update gate. |
| Old promoted static root | Blocked: `[rift_x64+0x32EBC80]` is readable but currently null in the latest exact-target readback. |
| Candidate coordinate chain | `[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30`; candidate-only current readback passed. |
| Latest RIFT epoch artifact | Manifest `STABLE-1-1152-a-1256395`; `rift_x64.exe` manifest SHA1 `a8ba8748ea752e4e5581cea34188dc702469c923`. |
| Latest exact-target artifact | PID `77152`, HWND `0x17A0DB2`, process start `2026-06-02T15:45:29.2617327Z`; verify freshness before any new live assumption. |
| Navigation consumer readiness | Still blocked from consumer use until status surfaces separate post-update candidate evidence from promoted navigation truth. |

## Evidence artifacts

| Artifact | Why it matters |
|---|---|
| `scripts/captures/static-owner-coordinate-chain-readback-20260602-175043-068641/summary.json` | Newer readback proving the old promoted root pointer is null. |
| `scripts/captures/postupdate-static-access-chain-20260602-195804-076419/summary.json` | Static/Ghidra-backed lead showing function `0xC38390` reads `rift_x64+0x32DD7E8`. |
| `scripts/captures/postupdate-global-container-coordinate-readback-20260602-200619-457973/summary.json` | Candidate-only chain readback; best max abs delta vs reference `0.004628906250218279`; 5/5 stationary polling samples matched. |
| `scripts/captures/postupdate-owner-root-rediscovery-20260602-201119-651369/summary.json` | Rollup showing global-container readback while keeping overall recovery blocked. |
| `docs/handoffs/2026-06-02-2006-postupdate-global-container-coordinate-readback-handoff.md` | Prior compact handoff for the helper and candidate readback slice. |

## Safety boundary preserved

No live input, movement, route control, `/reloadui`, screenshot key, debugger or
Cheat Engine attach, target memory write, provider repo write, current-truth
apply, ProofOnly, proof promotion, actor-chain promotion, or navigation
execution was performed in this handoff slice.

One PowerShell command was initially typed with `&`, which PowerShell parsed as
a background-job operator. `Get-Job` showed no remaining job in the follow-up
shell, and the decision packet was re-run with a PowerShell-safe separator.

## What was intentionally not changed

| Area | Reason |
|---|---|
| `docs/recovery/current-truth.json` / `.md` | No promotion or current-truth apply is allowed without proof gates. |
| `scripts/navigation_consumer_state.py` | The candidate-vs-promoted bridge was planned but not implemented before this handoff request. |
| `tools/riftreader_workflow/decision_packet.py` | Still reports safe next action as owner-root rediscovery; it does not yet compactly surface the new global-container candidate. |
| Navigation route execution | Blocked until a promoted, restart-surviving, movement-proven coordinate truth exists and live movement approval is explicit. |

## Exact safe resume commands

```powershell
git --no-pager status --short --branch
cmd /c scripts\riftreader-decision-packet.cmd --compact-json --write; Write-Host "LAST=$LASTEXITCODE"
scripts\riftreader-postupdate-global-container-coordinate-readback.cmd --samples 5 --interval-seconds 0.2 --json
```

Expected current decision-packet result: exit code `2`, status `blocked`, lane
`proof-recovery`, target epoch `post-update-static-root-blocked`, blocker
`latest-static-owner-readback-root-pointer-null`.

## Next implementation slice

The next safe code slice should wire the post-update global-container readback
into consumer/status surfaces **as candidate evidence only**:

| File | Change |
|---|---|
| `scripts/navigation_consumer_state.py` | Load latest `postupdate-global-container-coordinate-readback-*` summary and expose `postUpdateRecovery` with `candidateOnly=true`, `promotionEligible=false`, and `routeControlAuthorized=false`. |
| `docs/schemas/navigation/navigation-consumer-state.schema.json` | Add optional `postUpdateRecovery` fields so downstream consumers can distinguish candidate evidence from promoted navigation truth. |
| `scripts/test_navigation_consumer_state.py` | Assert candidate evidence is visible but consumer route control remains blocked. |
| `tools/riftreader_workflow/decision_packet.py` | Summarize the latest global-container candidate and adjust safe next action from repeated rediscovery to no-input candidate refresh when a fresh candidate exists. |
| `scripts/test_decision_packet.py` | Cover the new candidate-only packet fields and blocked-safe behavior. |

## Validation target for the next code slice

```powershell
python -m py_compile scripts\navigation_consumer_state.py scripts\test_navigation_consumer_state.py tools\riftreader_workflow\decision_packet.py scripts\test_decision_packet.py
python -m unittest scripts.test_navigation_consumer_state scripts.test_decision_packet
python tools\riftreader_workflow\decision_packet.py --self-test --json
cmd /c scripts\riftreader-decision-packet.cmd --compact-json --write; Write-Host "LAST=$LASTEXITCODE"
git --no-pager diff --check
cmd /c scripts\riftreader-policy-lint.cmd --json validate-repo --scope changed --no-write-summary
```

## Hard stops

Stop for explicit approval before any of these:

1. Live movement, input, target selection, route execution, or displacement
   stimulus.
2. x64dbg, Cheat Engine, debugger attach, breakpoints, or watchpoints.
3. Provider repo writes to ChromaLink/RiftScan or any external repo.
4. Current-truth apply, proof promotion, actor-chain promotion, or ProofOnly.
5. Treating `0x32DD7E8` candidate evidence as consumer-ready navigation truth.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Implement the candidate-vs-promoted bridge in `navigation_consumer_state.py`. | Downstream consumers need to see the new evidence without accidentally using it as truth. |
| 2 | Add decision-packet awareness for the latest global-container readback. | The local control plane should stop recommending stale repeated rediscovery when a candidate refresh is the better safe next step. |
| 3 | Schema-test `postUpdateRecovery`. | Prevents downstream package consumers from misreading candidate data. |
| 4 | Re-run the no-input global-container readback after any game restart. | Confirms the candidate survived the current process epoch before further proof planning. |
| 5 | Keep old `[rift_x64+0x32EBC80]` truth blocked. | It is null post-update and unsafe for navigation. |
| 6 | Build a proof plan before movement stimulus. | Avoids underpowered probes and keeps target/PID/HWND/process-start gates explicit. |
| 7 | Run Ghidra/static xref follow-up around `rift_x64+0x32DD7E8`. | May explain the container structure and reveal a better owner/root path. |
| 8 | Prepare but do not run a restart-survival packet for the candidate. | The candidate needs restart/relog proof before promotion can even be considered. |
| 9 | Update current-truth docs only after proof gates pass. | Prevents stale or candidate-only data from becoming promoted navigation state. |
| 10 | Commit/push only coherent validated slices. | Keeps the recovery trail reviewable and easy to resume. |
