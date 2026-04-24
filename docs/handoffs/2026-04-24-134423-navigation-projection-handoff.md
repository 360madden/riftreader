---
state: current
as_of: 2026-04-24T13:44:23-04:00
branch: navigation
---

# Navigation Projection Handoff — 2026-04-24 13:44 EDT

## TL;DR

The `navigation` branch has a clean, offline-validated screenshot-gated projection workflow. Mailbox tooltip work should be treated as a tooling/smoke-test fallback, not the main discovery lead. The next best proof target is operator-confirmed nameplate baseline/zoom capture using the fail-closed nameplate wrapper.

## Current repo state

| Item | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `navigation` |
| Git status at handoff creation | Clean; tracking `origin/navigation` with no ahead/behind marker shown by `git status --short --branch` |
| Latest commit | `42bd340 Validate aggregate projection offline gate` |
| Live game input/movement during latest offline work | None |

## Latest commit stack

| Commit | Summary |
|---|---|
| `42bd340` | Validate aggregate projection offline gate |
| `b606976` | Add projection branch offline validation |
| `24b0621` | Validate projection script wrapper parity |
| `5f00faa` | Enforce projection CMD wrapper count |
| `90d1086` | Report projection CMD wrapper uniqueness |
| `5e98698` | Report projection CMD target existence |
| `f976a44` | Report projection CMD contract checks |
| `4998a3b` | Verify projection validator self-smoke bounds |
| `bb0080c` | Validate projection CMD launcher contract |
| `f6fd416` | Smoke projection validator CMD wrapper |
| `5a5e4ea` | Validate projection CMD wrapper shape |
| `b5518ae` | Parse projection workflow validator |
| `68df7d8` | Validate projection CMD launcher presence |
| `a59f8c4` | Validate projection CMD wrapper targets |
| `96cddfa` | Harden projection visual gate validation |

## What is built now

| Area | Current artifact |
|---|---|
| Branch-level offline gate | `C:\RIFT MODDING\RiftReader\scripts\test-navigation-projection-offline.ps1` and `.cmd` |
| Workflow validator | `C:\RIFT MODDING\RiftReader\scripts\test-projection-screenshot-gate-workflow.ps1` and `.cmd` |
| Nameplate proof wrapper | `C:\RIFT MODDING\RiftReader\scripts\run-nameplate-projection-proof.ps1` and `.cmd` |
| Tooltip capture/analyzer | `capture-tooltip-hover-diff.ps1`, `analyze-tooltip-hover-diff.ps1`, matching `.cmd` wrappers |
| Window capture helpers | WGC/Desktop Duplication and PrintWindow helpers under `scripts\` plus `tools\rift-window-capture\` |
| Runbook | `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-24-projection-screenshot-gated-runbook.md` |
| Review/stage manifest | `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-24-navigation-projection-branch-review-manifest.md` |

## Validation status

Latest aggregate validation before this handoff passed:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-navigation-projection-offline.ps1 -OutputTailLines 5 -Json
```

| Step | Last known result |
|---|---|
| Aggregate validator contract | Passed |
| Projection workflow validator | Passed, `8/8` checks |
| Reader tests | Passed, `70/70` |
| `git diff --check` | Passed |
| Worktree after validation/commit | Clean |

## Decision: mailbox tooltip vs. something else

| Candidate | Decision | Reason |
|---|---|---|
| Mailbox tooltip | Demote to fallback/smoke-test target | Useful for building the capture/analyzer pipeline, but previous mailbox runs were low-signal and UI-heavy. |
| Nameplate baseline/zoom | Primary next proof target | Cleaner match for projected entity/nameplate truth and already has a fail-closed wrapper. |
| Reticle/target marker | Secondary if nameplate is low-signal | More navigation-relevant than mailbox tooltip if nameplate does not produce useful signal. |
| Movement/navigation proof | Defer | Do not layer movement validation on uncertain projection truth. |

## Recommended resume command

Start with the offline gate:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\test-navigation-projection-offline.cmd -Json
```

Then dry-run the nameplate proof command shape:

```powershell
.\scripts\run-nameplate-projection-proof.cmd `
  -CandidateAddress 0x12CFC40B7D0 `
  -NameplateText "Atank of Sanctum" `
  -PlanOnly `
  -Json
```

## Live-proof boundary

Do **not** interact with the Rift window, focus it, click, type, move, cast, or run live movement proof unless the user explicitly approves live interaction. The next live proof, when approved, should be operator-controlled baseline/zoom nameplate capture with screenshots required and visual gate required.

## Next live proof shape, when approved

Use the nameplate wrapper without `-PlanOnly` only after the operator can prepare the visible states:

```powershell
.\scripts\run-nameplate-projection-proof.cmd `
  -CandidateAddress 0x12CFC40B7D0 `
  -NameplateText "Atank of Sanctum" `
  -Json
```

Expected operator states:

| State | Operator action |
|---|---|
| `baseline1` | Nameplate/target text not in active projected/zoom state |
| `zoom1` | Nameplate/target text visibly active/zoomed |
| `baseline2` | Return to baseline |
| `zoom2` | Return to active/zoomed |

The helper should not control input; it prompts and captures/reads only after the operator confirms each state.

## Blockers / cautions

| Item | Caution |
|---|---|
| Candidate address `0x12CFC40B7D0` | It is a current workflow default/candidate, not durable truth until live re-proven. |
| Mailbox tooltip artifacts | Treat as historical/exploratory unless a new screenshot-gated run passes visual gate. |
| Ignored artifacts | `artifacts\tooltip-projection\` and `artifacts\window-capture\` are intentionally ignored; force-add only selected proof artifacts if explicitly needed. |
| Live interaction | Ask first before any game-window focus/input/movement. |

## Top 5 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Run `scripts\test-navigation-projection-offline.cmd -Json` after resuming | Confirms branch tooling still passes locally. |
| 2 | Keep mailbox tooltip as fallback only | It is low-signal for entity projection truth. |
| 3 | Use nameplate baseline/zoom as the next real live proof | Best current target for projection/entity signal. |
| 4 | If nameplate proof is low-signal, pivot to reticle/target marker | More navigation-relevant than mailbox tooltip. |
| 5 | Avoid movement proof until projection signal is visually gated | Prevents compounding uncertain projection data with navigation behavior. |
