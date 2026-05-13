# Live Testing GUI Operator Guide

_Last updated: May 13, 2026 13:27 EDT._

## Purpose

Use this guide for the read-only RiftReader orchestrator HUD and headless
progress inspection commands. These tools are information-only: they read
orchestrator artifacts and never send RIFT input, retry a run, refresh proof, or
touch Cheat Engine.

## Commands

| Task | Command |
|---|---|
| Preview normal/running HUD offline | `cmd\live-gui-demo.cmd --demo-scenario running` |
| Preview passed HUD offline | `cmd\live-gui-demo.cmd --demo-scenario passed` |
| Preview target-blocked HUD offline | `cmd\live-gui-demo.cmd --demo-scenario blocked` |
| Preview reference-capture-blocked HUD offline | `cmd\live-gui-demo.cmd --demo-scenario blocked-reference` |
| Preview proof-blocked HUD offline | `cmd\live-gui-demo.cmd --demo-scenario blocked-proof` |
| Smoke-render HUD without showing a window | `python scripts\live_test_gui.py --demo --smoke-render --compact-json` |
| Open latest run HUD | `cmd\live-gui-latest.cmd` |
| Inspect latest run without opening a window | `cmd\live-gui-inspect-latest.cmd` |
| Strict latest inspect gate | `cmd\live-gui-inspect-latest.cmd --fail-on-warning` |
| Require latest run success | `cmd\live-gui-inspect-latest-ok.cmd` |
| Compact latest inspect JSON | `cmd\live-gui-inspect-latest.cmd --compact-json` |
| Latest inspect summary | `cmd\live-gui-inspect-latest.cmd --summary` |
| Inspect explicit progress file | `python scripts\live_test_gui.py --inspect-progress --progress-file <run-progress.json>` |
| Inspect a run directory | `python scripts\live_test_gui.py --inspect-progress --run-directory <run-dir>` |
| Strict explicit progress gate | `python scripts\live_test_gui.py --inspect-progress --progress-file <run-progress.json> --fail-on-warning` |
| Explicit run-success gate | `python scripts\live_test_gui.py --inspect-progress --progress-file <run-progress.json> --fail-on-warning --require-ok-run` |
| Compact strict gate | `python scripts\live_test_gui.py --inspect-progress --progress-file <run-progress.json> --fail-on-warning --compact-json` |
| Human-readable strict gate | `python scripts\live_test_gui.py --inspect-progress --progress-file <run-progress.json> --fail-on-warning --summary` |

## HUD controls and status lights

The visible HUD remains information-only. The **Refresh** button rereads the
local `run-progress.json` immediately; it does not rerun proof, rescan memory,
send input, attach x64dbg, touch Cheat Engine, or modify provider repos.

The **Copy run**, **Copy progress**, and **Copy summary** buttons copy artifact
paths to the clipboard only. They do not open files or execute commands.

| Light | Green | Amber | Red | Gray |
|---|---|---|---|---|
| `Progress` | Artifact is readable and completed/healthy. | Run is active, warning, or blocked but readable. | Running artifact is stale or failed. | No usable progress yet. |
| `Contract` | Progress JSON contract is valid. | Contract has warnings only. | Contract has hard errors. | Contract unavailable. |
| `Epoch` | This run refreshed the proof pointer or has no stale-epoch warning. | Pointer status needs review or the run is still pending. | Target/proof pointer mismatch, target drift, or stale epoch issue. | Not used. |
| `Target` | Target verification passed. | Target gate has not produced a final pass/fail. | Target verification failed. | No target data. |
| `Proof` | Proof or post-readback is passed. | Proof is pending/running. | Proof/run status is blocked or failed. | No proof data. |
| `Input` | Movement/input was sent by the recorded run. | Not used. | Input failed/no movement/partial stop. | No input sent. |
| `Recorder` | Coordinate recordings exist. | Not used. | Not used. | Recorder idle. |
| `Safety` | No CE and no SavedVariables live truth. | Not used. | Safety invariant failed/unknown. | Not used. |

The **Current Target / Providers** panel summarizes the active PID/HWND, proof
epoch status, API/ChromaLink freshness if the run recorded it, RiftScan strategy
gate status if present, and copyable artifact paths. Missing provider data is
displayed as `not recorded`; that is not a pass.

## Ranked HUD improvement checklist

| # | Improvement | Current status |
|---:|---|---|
| 1 | Safe Refresh button | Complete |
| 2 | Progress + Contract lights | Complete |
| 3 | Last-refresh timestamp/result | Complete |
| 4 | Documented light meanings | Complete |
| 5 | Current Target panel | Complete |
| 6 | ChromaLink/API-now panel | Complete when run payload includes provider data; otherwise reports `not recorded` |
| 7 | RiftScan strategy-gate panel | Complete when run payload includes review data; otherwise reports `not recorded` |
| 8 | Copy-path buttons | Complete |
| 9 | Stale process/proof epoch warning | Complete |
| 10 | Headless smoke-render path | Complete |

## Inspect output

`--inspect-progress` prints compact JSON. Key fields:

| Field | Meaning |
|---|---|
| `status` | Inspect command status, e.g. `progress-valid`, `progress-unreadable`, `progress-invalid`. |
| `ok` | `true` only when the progress JSON parsed and the required contract has no hard errors. |
| `runStatus` | The orchestrator status from `run-progress.json`. |
| `runHealth.state` | Normalized state: `ok`, `running`, `warning`, `blocked`, `failed`, `stale`, or `unknown`. |
| `contract.status` | Progress contract result: `valid`, `warning`, or `invalid`. |
| `contract.issues` | Missing fields, shape problems, or safety invariant violations. |
| `runSummaryFileExists` | Whether the referenced final summary path currently exists. |
| `latestPointer` | Present for `--latest`; includes pointer status, timestamp, health, and resolved file existence. |
| `latestPointer.freshness` | Present for `--latest`; warns when pointer timestamp/status/health disagrees with the referenced progress artifact, or when the repo latest pointer targets artifacts outside this repo tree. |
| `strict` | Present when `--fail-on-warning` is used; contains strict gate status and warning list. |
| `runGate` | Present when `--require-ok-run` is used; fails when the inspected run health is not `ok`. |

Safety invariant failures are hard errors:

- `noCheatEngine` must be `true`.
- `savedVariablesUsedAsLiveTruth` must be `false`.

Missing newer fields such as `runHealth` or `runGates` are warnings so older
artifacts can still be inspected.

For latest-run inspection, `latestPointer.freshness.status=warning` means the
pointer and progress artifact may not describe the same instant. Inspect the
reported `issues` before rerunning any live profile.

Freshness warnings such as `latest_pointer_run_directory_outside_repo` or
`latest_pointer_progress_file_outside_repo` mean the repo latest pointer targets
a temp or external output-root run. Treat that as operator context, not durable
current truth, until a repo-local proof run supersedes it.

New external `--output-root` runs no longer update the repo latest pointer by
default. If a run's progress artifact says
`latestPointer.skipReason=output_root_outside_repo`, inspect that run directly
with `--run-directory` or `--progress-file`; do not expect `--latest` to move.

Use `--fail-on-warning` when the inspect command is acting as an automation
gate. It still prints JSON, but exits nonzero for contract warnings, stale or
warning health, and latest-pointer freshness warnings.

Use `--require-ok-run` when the automation must prove the inspected run itself
passed. This is intentionally separate from `--fail-on-warning`: a blocked run
can have a valid, fresh artifact contract, but it should not satisfy a
"latest run passed" gate.

Use `--compact-json` with `--inspect-progress` when scripts need one-line JSON.
It changes formatting only; it does not change validation or exit behavior.

Use `--summary` with `--inspect-progress` for a short human-readable status
block. It can be combined with `--fail-on-warning`; exit behavior is unchanged.
`--summary` and `--compact-json` are mutually exclusive.

See `docs\live-testing-progress-contract.md` for the full progress/latest-pointer
contract.

## Checked-in fixtures

These fixtures define the current progress/latest-pointer contract:

| Fixture | Purpose |
|---|---|
| `scripts\rift_live_test\testdata\progress-running.json` | Valid running progress artifact; used for stale-health checks. |
| `scripts\rift_live_test\testdata\progress-passed.json` | Valid completed progress artifact. |
| `scripts\rift_live_test\testdata\progress-blocked-reference.json` | Valid blocked reference-capture progress artifact. |
| `scripts\rift_live_test\testdata\latest-pointer.json` | Latest-pointer example that resolves to the passed progress fixture. |
| `scripts\rift_live_test\testdata\latest-pointer-drift.json` | Latest-pointer example with timestamp/status/health drift against running progress. |

The test suite validates these fixtures with `--inspect-progress` logic so
schema or safety-contract drift is caught offline.

## Safe post-crash sequence

After a RIFT crash or restart, use this order:

1. `cmd\live-gui-inspect-latest.cmd`
2. If you need an automation gate for a known-good latest run, use
   `cmd\live-gui-inspect-latest-ok.cmd`.
   Expect this to fail after a blocked/crash-adjacent run; inspect the issue
   instead of treating it as movement-ready.
3. `python scripts\live_test.py --profile ProofOnly --pid <pid> --hwnd <hwnd> --no-gui`
4. `python scripts\live_test.py --profile ProofOnly --pid <pid> --hwnd <hwnd>`
5. Only after those pass, consider a live input profile with explicit approval.
