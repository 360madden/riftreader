# RiftReader Handoff - Player Actor-Yaw Discovery + RiftScan Coordination

Created: May 8, 2026 08:29 EDT / 12:29 UTC
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
Primary lane: **player actor-yaw discovery first**, then player actor-facing only after yaw proof is fresh and ready.
Hard boundaries: **No CE** and **do not modify `C:\RIFT MODDING\Riftscan`**.

## TL;DR

The current slice hardened player actor-yaw discovery and RiftScan coordination without sending live input, using CE, or writing to RiftScan. A new offline actor-yaw readiness reporter now produces a resumable summary/latest pointer and fails closed when artifacts are stale. The latest readiness checkpoint reports `stale-artifacts-refresh-required`, so the next live/proof work should refresh current-session yaw candidate search and yaw validation before any actor-facing promotion work.

## Current target truth

| Fact | Value |
|---|---|
| Last live target recorded in current-truth | `rift_x64` PID `33912`, HWND `0xE0DB2` |
| Current movement truth | Movement-grade and 2m waypoint-smoke validated in earlier May 8 work |
| Auto-turn state | Still blocked; no promoted turn backend |
| Actor-facing state | Existing behavior-backed lead remains documented, but this slice did not force new facing promotion |
| RiftScan boundary | Read-only provider/reference; no repo writes authorized |
| CE boundary | No Cheat Engine, CE Lua, debugger attach, breakpoints, watchpoints, or `cheatengine-exec.ps1` |

## What changed in this slice

| Area | Files / behavior |
|---|---|
| Yaw candidate validation output | `scripts\test-actor-yaw-candidates.ps1` now reports `ValidationFocus=player-actor-yaw-discovery`, stable `CandidateKey`, same-source multi-offset grouping, `BestCandidate`, and `FacingPromotionAttempted=false` |
| Yaw regression fixture | `scripts\test-actor-yaw-candidates-reversible-output.ps1` covers two same-source offsets, candidate keys, grouping, best candidate, and no facing promotion |
| Restart-check test isolation | `scripts\test-current-actor-yaw-restart-check-validator.ps1` now uses coherent temp fixtures rather than requiring stale historical packet files to match current lead artifacts |
| Ledger gate tests | Added C# tests for ledger loading, pointer-hop scoring penalties, parser wiring, and JSON output ledger fields |
| Ledger docs | `docs\player-actor-yaw-candidate-ledger.md` defines candidate key, penalty semantics, JSON output contract, promotion boundary, and durable readiness checkpoint command |
| Yaw readiness reporter | `scripts\summarize_actor_yaw_discovery.py` summarizes candidate-search and yaw-validation artifacts, never authorizes movement/facing promotion, and fails stale artifacts closed |
| Readiness persistence | Reporter now supports `--write-summary`, `--write-markdown`, `--update-latest-pointer`, `--latest-pointer-file`, and refuses output inside RiftScan |
| Convenience launcher | `scripts\summarize-actor-yaw-discovery.cmd` is a dumb pass-through wrapper to Python |
| RiftScan coordination | Added/validated RiftReader-owned coordination, feedback, milestone-review, and aggregate validation surfaces; RiftScan remains clean/read-only |
| Current truth | `docs\recovery\current-truth.md` was updated with yaw-readiness and RiftScan coordination truth |

## Important artifacts

| Artifact | Purpose |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\captures\latest-actor-yaw-discovery-readiness.json` | Latest actor-yaw readiness pointer |
| `C:\RIFT MODDING\RiftReader\scripts\captures\actor-yaw-discovery-readiness-20260508-122421.json` | Latest persisted yaw readiness summary from the stale-artifact gate smoke |
| `C:\RIFT MODDING\RiftReader\scripts\captures\actor-yaw-discovery-readiness-20260508-122421.md` | Markdown companion for that summary |
| `C:\RIFT MODDING\RiftReader\docs\player-actor-yaw-candidate-ledger.md` | Contract for yaw candidate ledger and readiness gate |
| `C:\RIFT MODDING\RiftReader\scripts\validate_riftscan_coordination.py` | Aggregate no-CE/read-only RiftScan coordination validation runner |
| `C:\RIFT MODDING\RiftReader\scripts\captures\latest-riftscan-validation.json` | Latest RiftScan coordination validation pointer from earlier slice |
| `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md` | Current truth/status surface |

## Latest actor-yaw readiness checkpoint

`C:\RIFT MODDING\RiftReader\scripts\captures\latest-actor-yaw-discovery-readiness.json` currently records:

| Field | Value |
|---|---|
| `status` | `stale-artifacts-refresh-required` |
| `decision` | `refresh-stale-artifacts` |
| `movementAllowed` | `false` |
| `facingPromotionAllowed` | `false` |
| `noCheatEngine` | `true` |
| `writesToRiftScan` | `false` |
| `freshnessGatePassed` | `false` |
| `staleArtifactCount` | `2` |

Stale inputs at checkpoint time:

| Input | Age at checkpoint |
|---|---:|
| `scripts\captures\player-orientation-candidate-search.json` | ~48.41h |
| `scripts\captures\actor-yaw-candidate-test.json` | ~374.59h |

## Validation completed

| Command / check | Result |
|---|---|
| `pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-actor-facing-proof-suite.ps1` | Passed |
| `python .\scripts\test_summarize_actor_yaw_discovery.py` | Passed, 9/9 |
| `python .\scripts\test_actor_yaw_candidate_ledger_docs.py` | Passed, 2/2 |
| `python -m py_compile .\scripts\summarize_actor_yaw_discovery.py .\scripts\test_summarize_actor_yaw_discovery.py` | Passed |
| `cmd /c .\scripts\summarize-actor-yaw-discovery.cmd --help` | Passed |
| `python .\scripts\summarize_actor_yaw_discovery.py --write-summary --write-markdown --update-latest-pointer --require-fresh --compact-json` | Correctly returned stale-gate exit `2`; wrapper check treated this as expected success |
| `python .\scripts\validate_riftscan_coordination.py --repo-root . --riftscan-root 'C:\RIFT MODDING\Riftscan' --pid 33912 --hwnd 0xE0DB2 --process-name rift_x64 --quick --timeout-seconds 240 --compact-json` | Passed, `stepCount=18`, `failedStepCount=0`, `writesToRiftScan=false` |
| `git diff --check` | Passed; only LF-to-CRLF warnings |
| `git -C 'C:\RIFT MODDING\Riftscan' status --short --branch` | Clean: `## main...origin/main` |

Earlier same-session validation also passed:

| Check | Result |
|---|---|
| Targeted C# ledger/parser/JSON output filter | Passed, 29/29 |
| Broader targeted C# orientation/navigation/facing/parser filter | Passed, 33/33 |
| Full `dotnet test .\RiftReader.slnx --configuration Debug --no-restore` | Passed, 92/92 |
| Full RiftScan coordination validation before final yaw readiness additions | Passed, `stepCount=19`, `failedStepCount=0`, `writesToRiftScan=false` |

## Dirty worktree at handoff creation

The worktree intentionally contains a broad uncommitted slice. Do not assume only this handoff is dirty.

Major modified/untracked groups:

| Group | Paths |
|---|---|
| RiftScan coordination | `scripts\rift_live_test\riftscan_coordination.py`, `riftscan_feedback.py`, `riftscan_milestone_review.py`, `riftscan_validation.py`, CLI wrappers, tests, validation runner |
| RiftScan proof hardening | `scripts\capture-riftscan-proof-pose.ps1`, `import-riftscan-coordinate-candidates.ps1`, `promote-riftscan-reference-match-to-proof-anchor.ps1`, related tests |
| Live-test orchestrator | `scripts\rift_live_test\runner.py`, `scripts\test_live_test_orchestrator.py`, `configs\live-test-profiles.json` |
| Actor-yaw discovery | `scripts\test-actor-yaw-candidates.ps1`, `scripts\test-actor-yaw-candidates-reversible-output.ps1`, `scripts\test-current-actor-yaw-restart-check-validator.ps1` |
| Actor-yaw readiness | `scripts\summarize_actor_yaw_discovery.py`, `scripts\summarize-actor-yaw-discovery.cmd`, `scripts\test_summarize_actor_yaw_discovery.py` |
| C# ledger/parser tests | `reader\RiftReader.Reader.Tests\Models\*`, `reader\RiftReader.Reader.Tests\Formatting\PlayerOrientationCandidateSearchJsonOutputTests.cs`, parser test updates |
| Docs | `docs\player-actor-yaw-candidate-ledger.md`, `docs\recovery\README.md`, `docs\recovery\current-truth.md`, `docs\riftscan-riftreader-coordinate-candidate-workflow.md`, `agents.md` |

## Next resume procedure

1. Start by reading this handoff and `C:\RIFT MODDING\RiftReader\scripts\captures\latest-actor-yaw-discovery-readiness.json`.
2. Re-check `git status --short --branch` in `C:\RIFT MODDING\RiftReader` and `git -C 'C:\RIFT MODDING\Riftscan' status --short --branch`.
3. Keep `C:\RIFT MODDING\Riftscan` read-only unless the user explicitly authorizes provider edits.
4. Do not use CE.
5. If continuing actor-yaw discovery, refresh current-session candidate search and yaw validation first because current inputs are stale.
6. Re-run the readiness checkpoint with:

```cmd
C:\RIFT MODDING\RiftReader\scripts\summarize-actor-yaw-discovery.cmd --write-summary --write-markdown --update-latest-pointer --require-fresh
```

7. Only after fresh readiness reaches `yaw-ready-for-facing-proof-suite`, run:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File C:\RIFT MODDING\RiftReader\scripts\test-actor-facing-proof-suite.ps1
```

8. Do not promote actor-facing or navigation use from stale yaw artifacts.

## Ready-to-paste resume prompt

```text
Resume from C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-08-082900-player-actor-yaw-riftscan-coordination-handoff.md. Continue player actor-yaw discovery first, then player actor-facing only if the fresh yaw readiness gate supports it. No CE. Do not modify C:\RIFT MODDING\Riftscan; use it read-only as needed for optimal discovery. Start by reading latest-actor-yaw-discovery-readiness.json, checking RiftReader and RiftScan git status, then refresh stale actor-yaw artifacts against the exact live PID/HWND before any promotion work.
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Refresh actor-yaw candidate search on the exact current PID/HWND | Current readiness gate says the candidate-search artifact is stale |
| 2 | Re-run yaw validation with reverse stimulus/repeats | Needed for fresh reversible yaw proof |
| 3 | Re-run `summarize-actor-yaw-discovery.cmd --write-summary --write-markdown --update-latest-pointer --require-fresh` | Produces the next resumable gate and blocks stale artifacts |
| 4 | Keep actor-facing promotion blocked until fresh yaw readiness says `yaw-ready-for-facing-proof-suite` | Preserves the requested yaw-first order |
| 5 | Use `test-actor-facing-proof-suite.ps1` only after fresh yaw readiness passes | Shared proof applies downstream, but should not be forced early |
| 6 | Keep RiftScan read-only and use explicit `-CandidateFile` commands | Prevents accidental provider capture/session/report writes |
| 7 | Re-run `validate_riftscan_coordination.py --quick` after the next major milestone | Confirms no-CE/no-write strategy remains intact |
| 8 | Review the broad dirty worktree before committing | Current slice spans coordination, yaw, tests, docs, and live-test hardening |
| 9 | If committing, consider one coherent checkpoint commit rather than piecemeal mixed state | Easier rollback and review |
| 10 | Update `docs\recovery\current-truth.md` immediately after fresh yaw proof | Keeps latest validated truth ahead of stale artifacts |
