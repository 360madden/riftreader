# Live-Test HUD / Orchestrator Checkpoint

_Created: May 7, 2026 14:00 EDT_

## TL;DR

The Python live-test orchestrator has been polished offline after the RIFT crash. The current work adds a read-only Tk HUD, headless progress inspection, strict automation gates, latest-pointer freshness checks, atomic report writes, child-command telemetry, run health/gates metadata, invalid-HWND fail-closed handling, and checked-in progress fixtures.

No live game window, Cheat Engine, or input automation was used during this HUD/orchestrator polish pass.

## Safety posture

| Boundary | Current state |
|---|---|
| Live game window | Not required for current GUI/HUD work. |
| Cheat Engine | Not used; no-CE live boundary preserved. |
| SavedVariables live truth | Prohibited; HUD/inspect expect `savedVariablesUsedAsLiveTruth=false`. |
| GUI controls | Information-only; no movement, proof refresh, retry, stop, scan, or game-control actions. |
| Default GUI | `showGui=true` in profile defaults; `--no-gui` disables per run. |
| Strict inspect | `--fail-on-warning` exits nonzero on contract/freshness/stale warnings. |

## Crash context / latest live truth before offline polish

| Item | Current truth |
|---|---|
| User-reported issue | RIFT crashed after live-test attempts. |
| Last known successful live run before crash | `Forward250 --live`, one `W` 250ms pulse, planar delta about `0.225977833842375`. |
| Successful summary path | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-Forward250-20260507-163612\run-summary.json` |
| Last failed/crash-adjacent series | `ForwardSeries3x250 --live`, failed before movement during reference capture; no usable `RRAPICOORD1`. |
| Crash checkpoint handoff | `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-07-124304-crash-checkpoint-after-recorder-validation.md` |
| Since crash | Offline work only. |

## Major implemented pieces in current working tree

| Area | Files | Summary |
|---|---|---|
| Read-only HUD | `scripts\live_test_gui.py`, `scripts\rift_live_test\gui.py` | Tk HUD watches `run-progress.json`, shows status lights, labels, live info, issues, state history, and disabled informational Options menu. |
| Orchestrator GUI wiring | `scripts\live_test.py`, `scripts\rift_live_test\runner.py`, `configs\live-test-profiles.json` | Profiles default to HUD on, support `--no-gui`, write GUI metadata, run gates, run health, latest child command, and latest-run pointer data. |
| Headless inspect | `scripts\rift_live_test\gui.py` | `--inspect-progress` validates progress JSON without opening a window. Supports `--latest`, `--run-directory`, `--compact-json`, and `--fail-on-warning`. |
| Latest freshness | `scripts\rift_live_test\gui.py` | `latestPointer.freshness` detects timestamp drift plus pointer/progress status and health mismatches. |
| Strict automation gate | `scripts\rift_live_test\gui.py` | `strict` output object reports warning list; exit code becomes nonzero when warnings exist. |
| Atomic reports | `scripts\rift_live_test\reports.py` | JSON/markdown writes use atomic replace with retry for transient Windows reader locks. |
| Timeout capture | `scripts\rift_live_test\commands.py` | Child command timeouts return structured result artifacts instead of escaping as unstructured failures. |
| Target validation | `scripts\rift_live_test\target.py` | Invalid HWND values fail closed before Win32 calls. |
| Fixtures | `scripts\rift_live_test\testdata\*.json` | Checked-in progress/latest-pointer examples for passed, running/stale, blocked-reference, and drift-warning cases. |
| Docs | `docs\live-testing-gui-operator-guide.md`, `docs\live-testing-progress-contract.md`, `docs\live-testing-python-orchestrator-plan.md`, `docs\overview.md` | Operator guide, JSON contract, implementation plan notes, and overview links updated. |
| Launchers | `cmd\live-gui-demo.cmd`, `cmd\live-gui-latest.cmd`, `cmd\live-gui-inspect-latest.cmd` | Dumb `.cmd` wrappers that only cd to repo and call Python. |

## Current checked-in fixture set

| Fixture | Expected behavior |
|---|---|
| `scripts\rift_live_test\testdata\progress-running.json` | Valid running progress; can become `stale` under inspect thresholds. |
| `scripts\rift_live_test\testdata\progress-passed.json` | Valid passed progress; contract warning because final summary is marked written but absent in fixture directory. |
| `scripts\rift_live_test\testdata\progress-blocked-reference.json` | Valid blocked reference-capture progress. |
| `scripts\rift_live_test\testdata\latest-pointer.json` | Normal latest pointer resolving to passed fixture; freshness `ok`. |
| `scripts\rift_live_test\testdata\latest-pointer-drift.json` | Drifted latest pointer resolving to running fixture; freshness `warning`; strict mode exits nonzero. |

## Most recent validation before this handoff

| Command | Result |
|---|---|
| `python -m py_compile scripts\live_test.py scripts\live_test_gui.py scripts\rift_live_test\commands.py scripts\rift_live_test\gui.py scripts\rift_live_test\reports.py scripts\rift_live_test\runner.py scripts\rift_live_test\target.py scripts\test_live_test_orchestrator.py` | Passed. |
| `python scripts\test_live_test_orchestrator.py` | Passed, 56 tests. |
| `python scripts\live_test.py --validate-profiles` | Passed, 5 profiles valid. |
| `python scripts\live_test_gui.py --latest --latest-pointer scripts\rift_live_test\testdata\latest-pointer-drift.json --inspect-progress --compact-json \| python -m json.tool > $null` | Passed. |
| `python scripts\live_test_gui.py --latest --latest-pointer scripts\rift_live_test\testdata\latest-pointer-drift.json --inspect-progress --fail-on-warning --compact-json` | Exited `1` as expected for drift warnings. |
| `python scripts\live_test_gui.py --latest --latest-pointer scripts\rift_live_test\testdata\latest-pointer.json --inspect-progress --compact-json \| python -m json.tool > $null` | Passed. |
| `git diff --check` | Passed; CRLF warnings only. |

## Current git state at handoff creation

| Item | State |
|---|---|
| Branch | `main...origin/main [ahead 3]` |
| Modified tracked files | `configs/live-test-profiles.json`, `docs/live-testing-python-orchestrator-plan.md`, `docs/overview.md`, `scripts/live_test.py`, `scripts/rift_live_test/commands.py`, `scripts/rift_live_test/reports.py`, `scripts/rift_live_test/runner.py`, `scripts/rift_live_test/target.py`, `scripts/test_live_test_orchestrator.py` |
| New/untracked files | `cmd/live-gui-demo.cmd`, `cmd/live-gui-inspect-latest.cmd`, `cmd/live-gui-latest.cmd`, `docs/live-testing-gui-operator-guide.md`, `docs/live-testing-progress-contract.md`, `scripts/live_test_gui.py`, `scripts/rift_live_test/gui.py`, `scripts/rift_live_test/testdata/`, this handoff file |
| Commit/stage status | Not staged, not committed. |

## Resume checklist

1. Stay offline until explicitly reauthorizing live RIFT work.
2. Re-run `git status --short --branch` to confirm current working tree.
3. Re-run `python scripts\test_live_test_orchestrator.py` after any code edit.
4. Use `python scripts\live_test_gui.py --latest --inspect-progress --fail-on-warning --compact-json` for latest-run triage.
5. Before any live retest, prefer `ProofOnly --no-gui` first, then HUD-enabled `ProofOnly`, then only movement with explicit approval.

## Recommended next best actions

| # | Action | Why |
|---:|---|---|
| 1 | Review full uncommitted diff for scope creep. | The patch now spans GUI, runner, reports, docs, launchers, and tests. |
| 2 | Run one offline visual HUD demo. | Unit tests validate logic, not layout/readability. |
| 3 | Add manual visual HUD QA checklist. | Keeps GUI minimalist and informational without adding controls. |
| 4 | Add human-readable `--inspect-progress --summary`. | Faster operator triage than full JSON. |
| 5 | Add top-level post-crash no-live quickstart. | Reduces future mistakes after a client crash. |
| 6 | Consider staging/committing the offline HUD hardening. | Creates a clean rollback point before live retesting. |
| 7 | Re-run strict latest inspect on real latest artifact. | Confirms post-crash artifact state before any proof refresh. |
| 8 | If live is reauthorized, start with `ProofOnly --no-gui`. | Revalidates target/proof without HUD or input. |
| 9 | Then run HUD-enabled `ProofOnly`. | Verifies HUD integration safely before movement. |
| 10 | Only after proof is clean, consider a bounded input profile. | Keeps movement behind current proof and explicit approval. |

## May 7 14:15 EDT addendum - inspect summary mode and heartbeat cleanup

| Item | Update |
|---|---|
| Heartbeat queue | `keep-working-prompt-queue` was deleted after it fired beyond the requested queued follow-ups. |
| Inspect output | `--summary` now prints a short human-readable inspect status block. |
| Strict compatibility | `--summary` works with `--fail-on-warning`; exit behavior is unchanged. |
| Output guardrail | `--summary` requires `--inspect-progress` and is mutually exclusive with `--compact-json`. |
| Latest validation | `python scripts\test_live_test_orchestrator.py` passed with 59 tests after this addendum. |

Useful commands:

```powershell
python scripts\live_test_gui.py --latest --inspect-progress --summary
python scripts\live_test_gui.py --latest --inspect-progress --fail-on-warning --summary
python scripts\live_test_gui.py --inspect-progress --progress-file scripts\rift_live_test\testdata\progress-blocked-reference.json --summary
```
