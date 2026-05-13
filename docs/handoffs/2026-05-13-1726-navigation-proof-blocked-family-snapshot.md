# Handoff: navigation proof blocked, broad family snapshot refreshed

Generated: 2026-05-13 17:26 EDT / 2026-05-13 21:26 UTC
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

The RIFT target **was present**. My earlier target-missing conclusion was wrong:
`check_rift_target_control.py` had a bug/path gap when called without exact
`--pid`.

Current target:

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `2928` |
| HWND | `0xC0994` |
| Title | `RIFT` |
| Responding | `true` |

Exact target-control and visual gate now pass. Same-target `ProofOnly` still
blocks because the promoted proof pointer is stale PID `57656` / HWND
`0x5417BC`.

## What changed in code

| File | Change |
|---|---|
| `scripts/rift_live_test/target_control.py` | Process-name/title-only target-control now enumerates windows instead of returning false `target-process-missing`. |
| `scripts/test_target_control.py` | Added regression coverage for process-name/title target selection without exact PID. |
| `scripts/navigation_target_watch.py` | New passive no-input target watcher CLI. |
| `scripts/rift_live_test/navigation_target_watch.py` | Passive target watcher implementation. |
| `scripts/test_navigation_target_watch.py` | Unit tests for target-found/missing/minimized summaries. |

## Current evidence

| Evidence | Result |
|---|---|
| Direct process enumeration | PID `2928`, HWND `0xC0994`, title `RIFT`, responding. |
| Passive target watch | `scripts/captures/navigation-target-watch-20260513-211838-550348/summary.json`; `target-found-passive`. |
| Exact target-control | `scripts/captures/target-control-currentpid-2928-20260513-171853/target-control-status.json`; `passed-target-control`. |
| Process-name target-control | `scripts/captures/target-control-currenttarget-20260513-172535/target-control-status.json`; `passed-target-control`. |
| Visual gate | `scripts/captures/visual-gate-currentpid-2928-20260513-171907/visual-gate-status.json`; `passed-visual-baseline`. |
| ProofOnly | `scripts/captures/live-test-ProofOnly-20260513-211940/run-summary.json`; `blocked-target-drift`, no movement sent. |
| Broad family snapshot | `scripts/captures/family-snapshot-sequence-currentpid-2928-20260513-212104-107039/summary.json`; `passed`. |
| Candidate readback | `scripts/captures/candidate-readback-currentpid-2928-20260513-212405-624415/candidate-readback-summary.json`; `passed`, candidate-only. |

## Broad family-group result

| Metric | Value |
|---|---|
| Selected ranges | `39` |
| Current-PID scan-plan ranges | `20` |
| Prior exact windows | `14` |
| Prior family-neighborhood ranges | `5` |
| Candidate count | `1000` |
| Clean candidate count | `489` |
| Family count | `2` |
| Known offset-copy family | `0x268DF200000` |
| Known top delta address | `0x268DF21ED30` |
| Fresh best readback | `0x268BEF2C6A8` |
| Readiness | `candidate_only_not_movement_proof` |

## Safety state

| Boundary | State |
|---|---|
| Navigation movement | Blocked. |
| Auto-turn | Blocked. |
| Proof promotion | None. |
| Cheat Engine | Not used. |
| x64dbg | Not launched/attached. |
| Memory writes | None. |
| Discovery stimulus | One bounded exact-HWND `w` pulse inside broad snapshot helper; recorded as discovery stimulus, not navigation proof. |

## Next best actions

| # | Action | Why |
|---:|---|---|
| 1 | Keep navigation movement blocked. | `ProofOnly` is still blocked-target-drift. |
| 2 | Use the fresh broad snapshot/readback artifacts as recovery evidence. | They are stronger than narrow stale-address probes. |
| 3 | Investigate why fresh best readback shifted to `0x268BEF2C6A8`. | It may be a lower-offset coordinate-copy family worth comparing against `0x268DF21ED30`. |
| 4 | Run another broad snapshot only if a distinct safe movement vector is available. | More vector diversity would separate real coord copies from correlated UI/scene data. |
| 5 | Avoid promoting offset-corrected copies directly. | They are candidate-only and not static/restart proof. |
| 6 | Prefer finding source/owner relationship for the best families. | Navigation needs a stable proof anchor, not just offset-corrected values. |
| 7 | Rerun `navigation_resume_status.py` after any proof-recovery attempt. | Keeps the gate summary current. |
| 8 | Keep auto-turn disabled. | No current actor-facing/turn backend is promoted. |
| 9 | Do not use x64dbg until there is a new attach tactic. | Two prior current-PID attach attempts failed before attach. |
| 10 | Update `current-truth.md` after the next proof result. | Keeps future resumes aligned to navigation-first state. |

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. RIFT target is PID `2928`,
HWND `0xC0994`. Target-control and visual gate pass, but same-target
`ProofOnly` blocks because the proof pointer is stale PID `57656` / HWND
`0x5417BC`. Movement/navigation remains blocked. A broad 39-range family
snapshot with one bounded `w` discovery stimulus passed and readback found
candidate-only offset-corrected families; best fresh readback is
`0x268BEF2C6A8`, while the known family `0x268DF200000` / `0x268DF21ED30`
remains high-signal. Use broad family-group snapshots/offline deltas, not narrow
stale-address probing, if proof recovery continues.
