# CE Reintegration Ranked Todo

Use this file as the living ranked checklist for bringing Cheat Engine back
into the workflow without immediately changing the debugger-attach Lua logic.

## Rules

- keep CE scan / inspection mode in the normal workflow
- keep CE debugger-trace mode opt-in only
- do **not** patch the shared `debugProcess(2)` path until repeated fresh
  attach failures are logged
- validate useful CE findings back through the reader whenever possible

## Ranked top 20

| Rank | Task | Status | Implementation |
|---|---|---|---|
| 1 | Split CE into scan / inspection lane vs debugger-trace lane | active | documented in workflow and recovery docs |
| 2 | Keep reader/addon as the baseline gate before CE escalation | active | documented in recovery truth/runbook |
| 3 | Start a CE debugger attach crash ledger | implemented | `C:\RIFT MODDING\RiftReader\scripts\log-ce-debugger-failure.ps1` + `C:\RIFT MODDING\RiftReader\scripts\summarize-ce-debugger-failures.ps1` + local CSV ledger |
| 4 | Add a repo-owned ranked CE reintegration checklist | implemented | this file |
| 5 | Reintegrate CE scan mode first | active | documented current direction |
| 6 | Keep debugger-trace mode opt-in only | active | documented current direction |
| 7 | Confirm repeated `windows debugger: 87` failures before patching guards | pending | collect multiple fresh runs |
| 8 | Record per-run preflight facts: CE state, Rift state, elevation, status-file output | implemented | supported in failure ledger fields |
| 9 | Separate CE tasks that work without debugger attach | active | documented as scan / inspection lane |
| 10 | Validate every useful CE finding back through the reader | active | workflow rule |
| 11 | Document the exact future guard sites but leave them unchanged | active | documented in dated analysis report |
| 12 | Standardize expected status/output artifacts per debugger-trace script | implemented | trace scripts now preserve `stage`/`error` details and auto-log attach failures to the ledger |
| 13 | Freeze useful CE runs faster into repo-owned artifacts | active | continue using `scripts\captures\...` |
| 14 | Define a stop threshold for abandoning CE in a bad live session | pending | choose threshold after more attach samples |
| 15 | Keep a current pointer to the CE reintegration plan from recovery docs | implemented | linked from recovery docs |
| 16 | Keep CE scan/manual inspection as the normal discovery accelerator | active | current workflow direction |
| 17 | Avoid making CE debugger-trace the universal first path again | active | current workflow direction |
| 18 | Prepare a future guard patch plan without applying it yet | active | analysis report documents target sites |
| 19 | Reconfirm attach failures across more than one debugger-trace script | pending | compare coord/selector/projector trace attempts |
| 20 | Resume actor-orientation work with addon/reader first, CE second | active | current recovery direction |

## Implemented now

This pass implemented the lowest-risk infrastructure items:

1. ranked checklist
2. crash-ledger helper script
3. local repo-path CSV ledger
4. recovery/doc references to the reintegration plan
5. automatic attach-failure ledger wiring across the debugger-trace scripts
6. a ledger summary helper for quick script/stage/error rollups

## Current hold items

Do **not** implement these yet:

- Lua guards around `debugProcess(2)`
- forced debugger-mode changes
- automatic CE debugger attach retries

Those stay on hold until the crash ledger captures repeated fresh failures.

## Next evidence needed

Before touching the CE Lua debugger-attach path, capture at least:

1. date/time
2. script used
3. exact CE dialog/error text
4. whether a status file was produced
5. whether CE stayed open, detached, or crashed
6. whether the failure happened before any breakpoint was armed

## Related files

- `C:\RIFT MODDING\RiftReader\docs\cheat-engine-workflow.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-cheat-engine-reintegration-and-attach-failure-plan.md`
- `C:\RIFT MODDING\RiftReader\scripts\log-ce-debugger-failure.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\summarize-ce-debugger-failures.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\captures\ce-debugger-attach-failures.csv`
