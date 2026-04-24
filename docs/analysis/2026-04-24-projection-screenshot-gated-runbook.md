---
state: current
as_of: 2026-04-24
---

# Projection Screenshot-Gated Capture Runbook — 2026-04-24

## Scope

This runbook is for the `navigation` branch tooltip/nameplate projection lane in
`C:\RIFT MODDING\RiftReader`.

Goal: capture memory samples only when each state also has a usable no-input
screenshot, then analyze with a fail-closed visual gate before treating any
memory candidate as promotable.

## Snapshot metadata

| Item | Value |
|---|---|
| Date | 2026-04-24 |
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `navigation` |
| Input mode | Operator prepares visible state; helper performs read-only capture/scans only |
| Live safety | No helper mouse movement, clicks, casts, keyboard input, focus changes, or player movement |
| Visual gate | DXGI Desktop Duplication, multi-attempt, usable-frame required |

## Command order

### 1. Confirm no-input visual capture works

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\test-rift-window-capture-methods.ps1" `
  -ProcessName rift_x64 `
  -DesktopDuplicationAttempts 3 `
  -Json
```

Pass condition:

- `usable=true`
- best method is preferably `DXGIDesktopDuplication`
- at least one generated screenshot visibly contains Rift game content

If this fails, do **not** run projection sampling.

### 2. Capture screenshot-gated states

Nameplate baseline/zoom example:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\capture-tooltip-hover-diff.ps1" `
  -ProcessName rift_x64 `
  -CandidateAddress 0x12CFC40B7D0 `
  -CandidateLength 1024 `
  -TooltipText "Atank of Sanctum" `
  -States baseline1,zoom1,baseline2,zoom2 `
  -TextPointerScanMode allHits `
  -CaptureScreenshot `
  -RequireUsableScreenshot `
  -ScreenshotAttempts 3 `
  -RunLabel nameplate-baseline-zoom `
  -Json
```

Operator rule: before pressing Enter for each state, visually confirm the exact
state label is true. The helper will not create the state for you.

### 3. Analyze with fail-closed visual gate

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\analyze-tooltip-hover-diff.ps1" `
  -InputDirectory "<run-root>" `
  -BaselineStateRegex "^baseline" `
  -ActiveStateRegex "^zoom" `
  -BaselineLabel baseline `
  -ActiveLabel zoom `
  -RequireVisualGate `
  -Json
```

Pass condition:

- analyzer exits `0`
- `screenshotGate.visualGateStatus=passed`
- `diffs\screenshot-gate.json` shows every analyzed state has `usable=true`

## Output files to inspect

| File | Purpose |
|---|---|
| `<run-root>\summary.json` | Top-level capture + analysis summary |
| `<run-root>\samples.ndjson` | Per-state memory sample records |
| `<run-root>\states\<state>\screenshots\<state>.bmp` | Visual proof for a state |
| `<run-root>\states\<state>\screenshots\<state>.capture.json` | Raw capture metadata / usability proof |
| `<run-root>\diffs\screenshot-gate.json` | Analyzer visual-gate rollup |
| `<run-root>\diffs\field-candidates.json` | Ranked memory field candidates |
| `<run-root>\diffs\scan-evidence.json` | Explicit pointer/numeric scan evidence |

## Promotion rules

| Condition | Decision |
|---|---|
| `visualGateStatus=passed` and repeat memory field candidate exists | Candidate may move to live re-proof / writer tracing |
| `visualGateStatus=not-captured` | Historical or memory-only; do not promote projection claims |
| `visualGateStatus=failed-or-partial` | Blocked; rerun capture before interpreting state labels |
| Any click/cast/mailbox interaction occurred | Stop; label run unsafe for display-only projection proof |
| State labels were operator-uncertain | Keep as exploratory only |

## Current validated smoke artifacts

| Artifact | Result |
|---|---|
| `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-095742-screenshot-gate-analyzer-smoke` | Analyzer visual gate passed with two usable screenshots |
| `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-045239-mailbox-tooltip-live` | Older run analyzes as `visualGateStatus=not-captured` |

## Immediate next step

Run the real operator-confirmed nameplate baseline/zoom capture with
`-CaptureScreenshot -RequireUsableScreenshot`, then analyze it with
`-RequireVisualGate` before interpreting any field candidates.

## Optional one-command capture and analysis

`capture-tooltip-hover-diff.ps1` can now run the analyzer automatically after
capture. Use this when the run should immediately fail if visual proof is
missing or black.

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\capture-tooltip-hover-diff.ps1" `
  -ProcessName rift_x64 `
  -CandidateAddress 0x12CFC40B7D0 `
  -CandidateLength 1024 `
  -TooltipText "Atank of Sanctum" `
  -States baseline1,zoom1,baseline2,zoom2 `
  -TextPointerScanMode allHits `
  -CaptureScreenshot `
  -RequireUsableScreenshot `
  -ScreenshotAttempts 3 `
  -AnalyzeAfterCapture `
  -AnalyzerBaselineStateRegex "^baseline" `
  -AnalyzerActiveStateRegex "^zoom" `
  -AnalyzerBaselineLabel baseline `
  -AnalyzerActiveLabel zoom `
  -AnalyzerRequireVisualGate `
  -RunLabel nameplate-baseline-zoom `
  -Json
```

The run root will include `post-capture-analysis.json` plus the usual
`summary.json` and `diffs\*.json` analyzer outputs.

## Thin wrapper for nameplate proof

A wrapper now preserves the recommended fail-closed defaults:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\run-nameplate-projection-proof.ps1" `
  -CandidateAddress 0x12CFC40B7D0 `
  -NameplateText "Atank of Sanctum" `
  -Json
```

The wrapper forwards to `capture-tooltip-hover-diff.ps1` with:

- `-TextPointerScanMode allHits`
- `-CaptureScreenshot`
- `-RequireUsableScreenshot`
- `-AnalyzeAfterCapture`
- `-AnalyzerRequireVisualGate`
- baseline states `baseline1,baseline2`
- active states `zoom1,zoom2`

Use `-PlanOnly -Json` first to verify the command shape without attaching to
Rift or creating artifacts.

## Offline workflow validation

Use this before staging/checkpointing to validate the screenshot-gated workflow
without live input:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\test-projection-screenshot-gate-workflow.ps1" -Json
```

It checks:

- PowerShell parse for the projection helper scripts and validator script
- `RiftWindowCapture.csproj` build
- `run-nameplate-projection-proof.ps1 -PlanOnly -Json`, including key-argument
  preservation and no-artifact behavior
- `run-nameplate-projection-proof.cmd -PlanOnly -Json`, unless
  `-SkipCmdWrapperSmoke` is set, including key-argument preservation and
  no-artifact behavior
- `test-projection-screenshot-gate-workflow.cmd` in non-recursive smoke mode,
  unless `-SkipCmdWrapperSmoke` or `-SkipSelfCmdWrapperSmoke` is set, including
  proof that the inner run skipped build, artifact smoke, and recursive CMD
  smoke paths
- existing screenshot-gated smoke artifact with analyzer `-RequireVisualGate`, if present
- fail-closed analyzer behavior when `-RequireVisualGate` is used without
  screenshot captures

Use `-SkipArtifactSmoke` when running on a machine without the local ignored
smoke artifacts. The fail-closed negative smoke is generated under the system
temp directory and does not depend on local ignored artifacts.

## CMD wrappers

The projection helper scripts now have matching `.cmd` wrappers that use the
repo-standard `scripts\_run-pwsh.cmd` launcher. These are useful from CMD,
Explorer, or tools that should not need to locate `pwsh` manually.

| Wrapper | Target |
|---|---|
| `scripts\run-nameplate-projection-proof.cmd` | `run-nameplate-projection-proof.ps1` |
| `scripts\test-projection-screenshot-gate-workflow.cmd` | `test-projection-screenshot-gate-workflow.ps1` |
| `scripts\capture-tooltip-hover-diff.cmd` | `capture-tooltip-hover-diff.ps1` |
| `scripts\analyze-tooltip-hover-diff.cmd` | `analyze-tooltip-hover-diff.ps1` |
| `scripts\capture-rift-window-wgc.cmd` | `capture-rift-window-wgc.ps1` |
| `scripts\capture-rift-window-printwindow.cmd` | `capture-rift-window-printwindow.ps1` |
| `scripts\test-rift-window-capture-methods.cmd` | `test-rift-window-capture-methods.ps1` |

Example:

```cmd
scripts\run-nameplate-projection-proof.cmd -CandidateAddress 0x12CFC40B7D0 -NameplateText "Atank of Sanctum" -PlanOnly -Json
```

The `.cmd` wrapper path is intended for ordinary shell-safe values such as
addresses and nameplate text with spaces. For unusual literal shell metacharacters
or embedded quote characters, prefer the `.ps1` wrapper from PowerShell so
argument boundaries are explicit.

## Validator covers wrapper arguments

`test-projection-screenshot-gate-workflow.ps1` now also verifies wrapper argument
preservation:

- runs `run-nameplate-projection-proof.ps1 -PlanOnly -Json`
- verifies the PowerShell wrapper preserves the planned `CandidateAddress` and
  `NameplateText` values
- verifies the PowerShell wrapper keeps `mode=plan-only`, `controlsInput=false`,
  and creates no run artifacts
- verifies the shared repo-standard `scripts\_run-pwsh.cmd` launcher exists and
  preserves the expected `RIFTREADER_PS1` handoff, PowerShell 7 discovery,
  execution flags, argument pass-through, and exit-code propagation
- reports those shared-launcher contract checks in the `cmd-wrapper-inspection`
  JSON as `launcherContract`
- inspects all seven projection `.cmd` wrappers for the shared launcher call and
  expected `.ps1` target
- verifies each projection `.cmd` wrapper preserves the standard wrapper shape:
  `@echo off`, `setlocal EnableExtensions`, argument pass-through, and launcher
  exit-code propagation
- reports each inspected wrapper's target and wrapper-shape checks in the
  `cmd-wrapper-inspection` JSON, including `targetExists=true`
- verifies the wrapper manifest has no duplicate wrapper names or target names
  and reports `wrapperCount`, `uniqueWrapperCount`, and `uniqueTargetCount`
- runs `run-nameplate-projection-proof.cmd -PlanOnly -Json` unless `-SkipCmdWrapperSmoke` is set
- verifies the CMD wrapper preserves the planned `CandidateAddress` and
  `NameplateText` values for the normal nameplate proof command
- verifies the CMD wrapper keeps `mode=plan-only`, `controlsInput=false`, and
  creates no run artifacts
- runs `test-projection-screenshot-gate-workflow.cmd` with build/artifact/CMD
  recursion skipped, proving the validator CMD entrypoint launches successfully
  without recursively invoking itself

Use `-SkipCmdWrapperSmoke` only when `cmd.exe` is unavailable or when validating
purely inside PowerShell-hosted automation. `-SkipSelfCmdWrapperSmoke` only
skips the validator's own CMD-wrapper smoke and is intended for the bounded
inner self-smoke call.

## Latest full offline validation

Full validation was run without skips:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\test-projection-screenshot-gate-workflow.ps1" -Json
```

Result: `ok=true`.

| Check | Result |
|---|---|
| PowerShell parse | Passed for 7 scripts. |
| CMD wrapper inspection | Passed for shared launcher plus 7 unique wrappers/targets, including machine-readable launcher/wrapper contract data and `targetExists=true` for each wrapper target. |
| Capture project build | Passed. |
| PowerShell nameplate wrapper plan | Passed, including `CandidateAddress` / `NameplateText` preservation and plan-only no-artifact behavior. |
| CMD nameplate wrapper plan | Passed, including `CandidateAddress` / `NameplateText` preservation and plan-only no-artifact behavior. |
| Validator CMD wrapper smoke | Passed in bounded non-recursive smoke mode, with expected inner skips verified. |
| Analyzer visual-gate smoke | Passed with `visualGateStatus=passed`. |
| Analyzer visual-gate negative smoke | Passed by failing closed with `visualGateStatus=not-captured`. |
