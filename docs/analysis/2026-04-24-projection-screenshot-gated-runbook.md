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
- for nameplate proof, `expectedStateSequence.passed=true`

Post-run nameplate proof gate check:

```powershell
scripts\check-nameplate-projection-proof-result.cmd -RunRoot "<run-root>" -Json
```

If checking immediately after the run and the default artifact directory is not
mixed with other active captures, use the latest nameplate run:

```powershell
scripts\check-nameplate-projection-proof-result.cmd -Latest -Json
```

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

- `-MaxHits 24`
- `-TextPointerScanMode allHits`
- `-CaptureScreenshot`
- `-RequireUsableScreenshot`
- `-AnalyzeAfterCapture`
- `-AnalyzerRequireVisualGate`
- baseline states `baseline1,baseline2`
- active states `zoom1,zoom2`

Use `-PlanOnly -Json` first to verify the command shape without attaching to
Rift or creating artifacts. The plan includes `operatorChecklist` entries for
the required `baseline1,zoom1,baseline2,zoom2` sequence so the operator can
confirm each visible state before starting the real capture.

For fast candidate reproof after a full pointer-scanned proof already exists,
keep the same screenshot/sequence gates but skip the expensive text pointer
scans:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\run-nameplate-projection-proof.ps1" `
  -CandidateAddress 0x12CFC40B7D0 `
  -NameplateText "Atank of Sanctum" `
  -MaxHits 4 `
  -TextPointerScanMode none `
  -SkipPointerScan `
  -Json
```

This is intended for rechecking already-discovered offsets such as the current
`+0x21D/+0x225/+0x235/+0x23D/+0x24D` flag cluster. Do not use the fast mode as
the first proof for a new nameplate target; run the default full proof first so
text/pointer evidence is captured at least once.

After a fast reproof run completes, compare it to the full proof with:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\compare-nameplate-projection-proof-runs.ps1" `
  -BaselineRunRoot "C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-143102-nameplate-baseline-zoom" `
  -ReproofRunRoot "<fast-reproof-run-root>" `
  -CandidateOffsets "+0x21D,+0x225,+0x235,+0x23D,+0x24D" `
  -MinRepeatCount 3 `
  -Json
```

The comparator fails closed unless both runs have passed screenshot/sequence
gates and at least `-MinRepeatCount` requested candidate offsets repeat.
It also includes `baselineByteValues` and `reproofByteValues` per requested
offset so a non-repeat can be diagnosed without manually decoding
`samples.ndjson`.

To compare an entire raw byte window between two gated runs:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\compare-nameplate-proof-byte-windows.ps1" `
  -BaselineRunRoot "C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-143102-nameplate-baseline-zoom" `
  -ReproofRunRoot "<fast-reproof-run-root>" `
  -StartOffset 0 `
  -Length 1024 `
  -Json
```

Use this when a candidate cluster fails to repeat. It separates
`repeated-changing`, `baseline-only-change`, `reproof-only-change`, and
`changed-in-both-different` offsets across the same gated state sequence.

To pivot from a failed byte window to text/pointer-owner leads, extract the
proof's text-hit and pointer-hit roots:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\extract-nameplate-proof-leads.ps1" `
  -RunRoot "C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-143102-nameplate-baseline-zoom" `
  -Json
```

Use the ranked `pointerHitLeads` and `textLeads` as follow-up roots for owner
neighborhood or pointer-chain capture. The extractor requires a passed
screenshot/sequence gate unless `-AllowUngated` is explicitly set.

To capture the first read-only memory neighborhood from the top repeated
pointer-hit roots:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\capture-nameplate-proof-lead-neighborhoods.ps1" `
  -RunRoot "C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-143102-nameplate-baseline-zoom" `
  -Json
```

Use `-PlanOnly` first when you only want root selection and exact Reader
commands. Plan-only mode sets `controlsInput=false`, does not attach to
`rift_x64`, and does not create artifacts. Live mode is still read-only: it only
uses `RiftReader.Reader` memory reads and does not focus, click, type, or move.
The default output is
`<RunRoot>\lead-neighborhoods\nameplate-proof-lead-neighborhoods.json`.

Current captured lead-neighborhood artifact:

| Field | Value |
|---|---|
| Run root | `artifacts\tooltip-projection\20260424-143102-nameplate-baseline-zoom` |
| Output | `artifacts\tooltip-projection\20260424-143102-nameplate-baseline-zoom\lead-neighborhoods\nameplate-proof-lead-neighborhoods.json` |
| Selected roots | `0X12CFA406C10`, `0X12CFA5FC070`, `0X12D034C9AE8` |
| Subgraph | 18 nodes / 15 edges |
| Controls input | `false` |

After two lead-neighborhood captures exist, compare them with:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\compare-nameplate-proof-lead-neighborhoods.ps1" `
  -BaselineRunRoot "<first-proof-run-root>" `
  -ReproofRunRoot "<second-proof-run-root>" `
  -MinRepeatedRootCount 1 `
  -Json
```

The comparator resolves each run's default
`lead-neighborhoods\nameplate-proof-lead-neighborhoods.json`, fails closed if
either artifact is not a captured read-only neighborhood, and reports repeated
selected roots, root nodes, nodes, and pointer edges. For the current
single-artifact sanity check, comparing the captured artifact to itself reports
3 repeated selected roots, 18 repeated nodes, and 15 repeated edges.
Its `candidateSummary` block is the machine-readable promotion surface:

- `candidateSummary.promotionReady` is `true` only when all comparator checks
  passed and the repeated-root / repeated-edge thresholds were met.
- `candidateSummary.recommendedRoots` lists repeated selected roots with their
  baseline/reproof lead states and source-text addresses.
- `candidateSummary.recommendedEdges` lists repeated pointer edges by
  `fromAddress`, `toAddress`, and `sourceOffsetHex`.

When the comparator summary is promotion-ready, write a durable promotion
packet with:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\write-nameplate-proof-promotion-packet.ps1" `
  -BaselineRunRoot "<first-proof-run-root>" `
  -ReproofRunRoot "<second-proof-run-root>" `
  -MinRepeatedRootCount 1 `
  -Json
```

The writer re-runs the neighborhood comparator, writes
`lead-neighborhoods\nameplate-proof-promotion-packet.json` under the reproof
run by default, and fails closed without writing a packet unless
`candidateSummary.promotionReady=true`. Use `-AllowNotReady` only when a
diagnostic not-ready packet is explicitly useful.
The validator also covers the negative path: when the repeated-root threshold is
higher than the evidence supports, the writer exits non-zero, reports
`insufficient-repeated-selected-roots`, and leaves no packet file behind.

For the normal post-proof path, the promotion pipeline wrapper runs the packet
writer against existing neighborhood artifacts and can optionally capture
missing neighborhoods from proof run roots:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\run-nameplate-proof-promotion-pipeline.ps1" `
  -BaselineRunRoot "<first-proof-run-root>" `
  -ReproofRunRoot "<second-proof-run-root>" `
  -CaptureMissingNeighborhoods `
  -MinRepeatedRootCount 1 `
  -Json
```

Use `-PlanOnly` first to print the planned capture/packet steps. Plan-only mode
does not create artifacts or attach to the process. The pipeline keeps
`controlsInput=false`; when
`-CaptureMissingNeighborhoods` is set it may perform read-only process memory
capture for missing neighborhood artifacts in run mode, but still does not
focus, click, type, or move. Plan output includes `wouldAttachToProcessOnRun`
when missing neighborhoods would require a read-only capture during an actual
run.

After two gated `nameplate-baseline-zoom` proof roots exist, the same pipeline
can auto-select the latest pair from inventory:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\run-nameplate-proof-promotion-pipeline.ps1" `
  -LatestBaselineZoomPair `
  -CaptureMissingNeighborhoods `
  -MinRepeatedRootCount 1 `
  -PlanOnly `
  -Json
```

`-LatestBaselineZoomPair` picks the newest gated baseline/zoom proof as the
reproof run and the previous gated baseline/zoom proof as the baseline run. Do
not combine it with explicit `-BaselineRunRoot`, `-ReproofRunRoot`,
`-BaselineFile`, or `-ReproofFile`.

To inventory the available nameplate proof roots before choosing baseline and
reproof inputs:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\list-nameplate-proof-runs.ps1" `
  -RequireGated `
  -Top 10 `
  -Json
```

The inventory reports each run's screenshot/sequence gate status, sample state
sequence, manifest seed fields (`candidateAddress`, `candidateLength`,
`nameplateText`, and `processName`), lead-neighborhood presence,
promotion-packet presence, and `promotionReady` value when a packet exists.

To summarize readiness and print the next command to run:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\plan-nameplate-proof-promotion.ps1" -Json
```

The planner uses the inventory, selects candidate baseline/reproof proof roots,
reports missing evidence such as `need-second-gated-nameplate-baseline-zoom-proof`,
and emits recommended commands for inventory, second proof, neighborhood capture,
or promotion pipeline execution as appropriate. It also exposes a single
machine-readable `nextAction` with safety flags (`controlsInput`,
`attachesToProcess`, `createsArtifacts`, `requiresOperatorConfirmation`,
`safeToRunNow`, and `safetyBlockers`) so automation can choose the safest
immediate command without parsing the whole recommendation list. When at least
two gated baseline/zoom proofs exist, it
treats the newest proof as reproof and the previous proof as baseline, then
recommends the latest-pair pipeline command.

To run only the planner's safe immediate action:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\invoke-nameplate-promotion-next-action.ps1" -Execute -Json
```

The helper refuses to execute when `nextAction.safeToRunNow=false`. In the
current one-proof state the safe action is the plan-only second-proof command,
so `-Execute` still performs no attach and creates no artifacts.
When only one prior gated baseline/zoom manifest is available, the second-proof
plan and live commands are both pre-seeded with that manifest's
candidate/nameplate arguments. Run the planner's
`run-second-baseline-zoom-proof-plan` command first and inspect its
`operatorChecklist`, then run `run-second-baseline-zoom-proof` only after the
candidate/nameplate are confirmed current. The seed includes a `seed.staleRisk`
warning; replace the candidate address with a freshly resolved live candidate if
the process, UI object, or hovered nameplate changed.

The nameplate wrapper intentionally rejects `-NonInteractive` for real capture
mode. Baseline/zoom proof requires operator confirmation for every visible
state so the analyzer does not compare four back-to-back snapshots of the same
screen state.

The shared capture helper uses the analyzer active-state regex for its
baseline/active text bookkeeping. For the nameplate wrapper this means `zoom1`
and `zoom2` are treated as active states even though some legacy output fields
still use tooltip/hover terminology for compatibility.

Each sample row also records `stateRole` and `isActiveState`; check those fields
after capture if a run's state labels are in doubt. The analyzer preserves these
as `originalState`, `stateRole`, and `isActiveState` in
`diffs\screenshot-gate.json`. The nameplate wrapper also passes an expected
state sequence audit to the analyzer, so the same file should include
`expectedStateSequence.passed=true` for the required
`baseline1,zoom1,baseline2,zoom2` sequence.

## Offline workflow validation

Use this before staging/checkpointing to validate the screenshot-gated workflow
without live input:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\test-projection-screenshot-gate-workflow.ps1" -Json
```

It checks:

- PowerShell parse for the expected projection helper scripts and validator script,
  including duplicate-entry checks
- `RiftWindowCapture.csproj` build
- `run-nameplate-projection-proof.ps1 -PlanOnly -Json`, including key-argument
  preservation, default scan controls, operator checklist, and no-artifact
  behavior
- bounded fast-reproof wrapper PlanOnly mode with `-MaxHits 4`,
  `-TextPointerScanMode none`, and `-SkipPointerScan`
- `run-nameplate-projection-proof.cmd -PlanOnly -Json`, unless
  `-SkipCmdWrapperSmoke` is set, including key-argument preservation and
  default scan controls and no-artifact behavior
- `test-projection-screenshot-gate-workflow.cmd` in non-recursive smoke mode,
  unless `-SkipCmdWrapperSmoke` or `-SkipSelfCmdWrapperSmoke` is set, including
  proof that the inner run skipped build, artifact smoke, and recursive CMD
  smoke paths
- existing screenshot-gated smoke artifact with analyzer `-RequireVisualGate`, if present
- analyzer handling for offsets whose typed view values are null in every sample
- fail-closed analyzer behavior when `-RequireVisualGate` is used without
  screenshot captures
- fail-closed analyzer behavior when usable screenshots are present but the
  expected proof state sequence is wrong
- `check-nameplate-projection-proof-result.ps1` against a generated fully gated
  baseline/zoom fixture by explicit `-RunRoot` and `-Latest`
- `compare-nameplate-projection-proof-runs.ps1` against a generated fully gated
  fixture to verify repeated candidate offset reporting
- `compare-nameplate-proof-byte-windows.ps1` against a generated fully gated
  fixture to verify repeated raw byte-window change reporting
- `extract-nameplate-proof-leads.ps1` against a generated fully gated fixture
  to verify text-hit and pointer-hit lead aggregation
- `capture-nameplate-proof-lead-neighborhoods.ps1 -PlanOnly` against a
  generated fully gated fixture to verify pointer-hit root planning without
  attaching to the Rift process or creating artifacts
- `compare-nameplate-proof-lead-neighborhoods.ps1` against generated captured
  neighborhood fixtures to verify repeated selected-root and pointer-edge
  reporting
- `write-nameplate-proof-promotion-packet.ps1` against generated captured
  neighborhood fixtures to verify durable promotion-packet creation only after
  comparator gates are promotion-ready
- `run-nameplate-proof-promotion-pipeline.ps1` against generated captured
  neighborhood fixtures to verify plan-only no-side-effect behavior and packet
  creation from existing neighborhood artifacts
- `run-nameplate-proof-promotion-pipeline.ps1 -LatestBaselineZoomPair` against
  two generated gated proof roots to verify newest-as-reproof,
  previous-as-baseline auto-selection, and plan-only no-attach semantics
- `list-nameplate-proof-runs.ps1` against a generated gated proof fixture to
  verify proof-run inventory with manifest seed, lead-neighborhood, and
  promotion-packet status
- `plan-nameplate-proof-promotion.ps1` against a generated inventory fixture to
  verify promotion-readiness planning and manifest-seeded plan-only plus live
  next-step command output, including structured `commandParts` and per-command
  safety metadata plus a top-level `recommendedCommandSafety` summary, when a
  second gated proof is missing
- `plan-nameplate-proof-promotion.ps1` against two generated gated proof roots
  to verify previous-as-baseline, newest-as-reproof ordering and latest-pair
  pipeline recommendations, including latest-pair command safety metadata and
  safety-summary counts, plus inherited unsafe `nextAction` safety metadata
  when one latest-pair run is still missing lead-neighborhood evidence
- `invoke-nameplate-promotion-next-action.ps1` against a generated one-proof
  fixture to verify safe `nextAction` reporting and guarded execution of the
  plan-only next action, including top-level operator checklist and
  recommended-command safety summary surfacing
- `invoke-nameplate-promotion-next-action.ps1 -Execute` against a generated
  one-proof fixture whose manifest-seeded nameplate text contains PowerShell
  metacharacters, to verify command-string quoting and structured
  `commandParts` preserve the text literally
- `invoke-nameplate-promotion-next-action.ps1 -Execute` against a generated
  unsafe two-proof fixture to verify fail-closed refusal when the next action
  would attach to the process and create artifacts while preserving the
  normalized no-execution result shape

Use `-SkipArtifactSmoke` when running on a machine without the local ignored
smoke artifacts. The fail-closed negative smoke is generated under the system
temp directory and does not depend on local ignored artifacts.

## Branch-level offline validation

Use this aggregate check before pushing or handing off the branch. It runs the
aggregate validator script/CMD-wrapper contract check, screenshot workflow
validator, Reader tests, and `git diff --check` without touching the Rift client
or creating live artifacts:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\test-navigation-projection-offline.ps1" -Json
```

Use `-SkipArtifactSmoke` on machines that do not have the ignored local
`artifacts\tooltip-projection\20260424-095742-screenshot-gate-analyzer-smoke`
fixture.

## CMD wrappers

The projection helper scripts now have matching `.cmd` wrappers that use the
repo-standard `scripts\_run-pwsh.cmd` launcher. These are useful from CMD,
Explorer, or tools that should not need to locate `pwsh` manually.

| Wrapper | Target |
|---|---|
| `scripts\run-nameplate-projection-proof.cmd` | `run-nameplate-projection-proof.ps1` |
| `scripts\check-nameplate-projection-proof-result.cmd` | `check-nameplate-projection-proof-result.ps1` |
| `scripts\test-projection-screenshot-gate-workflow.cmd` | `test-projection-screenshot-gate-workflow.ps1` |
| `scripts\compare-nameplate-projection-proof-runs.cmd` | `compare-nameplate-projection-proof-runs.ps1` |
| `scripts\compare-nameplate-proof-byte-windows.cmd` | `compare-nameplate-proof-byte-windows.ps1` |
| `scripts\extract-nameplate-proof-leads.cmd` | `extract-nameplate-proof-leads.ps1` |
| `scripts\capture-nameplate-proof-lead-neighborhoods.cmd` | `capture-nameplate-proof-lead-neighborhoods.ps1` |
| `scripts\compare-nameplate-proof-lead-neighborhoods.cmd` | `compare-nameplate-proof-lead-neighborhoods.ps1` |
| `scripts\write-nameplate-proof-promotion-packet.cmd` | `write-nameplate-proof-promotion-packet.ps1` |
| `scripts\run-nameplate-proof-promotion-pipeline.cmd` | `run-nameplate-proof-promotion-pipeline.ps1` |
| `scripts\list-nameplate-proof-runs.cmd` | `list-nameplate-proof-runs.ps1` |
| `scripts\plan-nameplate-proof-promotion.cmd` | `plan-nameplate-proof-promotion.ps1` |
| `scripts\invoke-nameplate-promotion-next-action.cmd` | `invoke-nameplate-promotion-next-action.ps1` |
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
- inspects all projection `.cmd` wrappers for the shared launcher call and
  expected `.ps1` target
- verifies each projection `.cmd` wrapper preserves the standard wrapper shape:
  `@echo off`, `setlocal EnableExtensions`, argument pass-through, and launcher
  exit-code propagation
- reports each inspected wrapper's target and wrapper-shape checks in the
  `cmd-wrapper-inspection` JSON, including `targetExists=true`
- verifies the wrapper manifest has no duplicate wrapper names or target names
  and reports `expectedWrapperCount`, `wrapperCount`, `uniqueWrapperCount`, and
  `uniqueTargetCount`
- verifies the CMD wrapper target list matches the parsed PowerShell script
  manifest
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
| PowerShell parse | Passed for expected 18 scripts with 18 unique entries. |
| CMD wrapper inspection | Passed for expected 18 projection wrappers with 18 unique wrappers/targets, matching the parsed PowerShell manifest and including machine-readable launcher/wrapper contract data plus `targetExists=true` for each wrapper target. |
| Capture project build | Passed. |
| PowerShell nameplate wrapper plan | Passed, including `CandidateAddress` / `NameplateText` preservation, operator-checklist roles, and plan-only no-artifact behavior. |
| CMD nameplate wrapper plan | Passed, including `CandidateAddress` / `NameplateText` preservation and plan-only no-artifact behavior. |
| Validator CMD wrapper smoke | Passed in bounded non-recursive smoke mode, with expected inner skips verified. |
| Analyzer visual-gate smoke | Passed with `visualGateStatus=passed`. |
| Analyzer visual-gate negative smoke | Passed by failing closed with `visualGateStatus=not-captured`. |
| Lead-neighborhood plan smoke | Passed with selected pointer-hit root planning, `controlsInput=false`, `attachesToProcess=false`, and no artifact creation. |
| Lead-neighborhood comparator smoke | Passed with repeated selected-root, pointer-edge, and promotion-candidate summary reporting. |
| Promotion-packet smoke | Passed with durable packet creation only after comparator gates were promotion-ready. |
| Promotion-packet negative smoke | Passed by failing closed and leaving no packet when repeated-root thresholds were not met. |
| Promotion-pipeline smoke | Passed with plan-only no-attach/no-input behavior and packet creation from existing neighborhood artifacts. |
| Promotion-pipeline latest-pair smoke | Passed with newest gated baseline/zoom proof selected as reproof, previous gated baseline/zoom proof selected as baseline, and plan-only no-attach semantics. |
| Proof-run inventory smoke | Passed with gated proof root, manifest seed fields, lead-neighborhood status, and promotion-packet status reporting. |
| Promotion-readiness planner smoke | Passed with missing-evidence, `safeToRunNow=true` `nextAction`, empty `safetyBlockers`, and manifest-seeded plan-only plus live next-command reporting when only one gated baseline/zoom proof exists. |
| Promotion command parts smoke | Passed by emitting structured `commandParts` alongside display command strings for safe execution. |
| Promotion recommended-command safety smoke | Passed by marking plan-only commands safe and live proof commands unsafe for automation with explicit blockers. |
| Promotion safety summary smoke | Passed by emitting top-level `recommendedCommandSafety` counts and unsafe command names for quick automation gating. |
| Promotion-readiness planner latest-pair smoke | Passed with previous gated baseline/zoom proof selected as baseline, newest gated baseline/zoom proof selected as reproof, `safeToRunNow=true` `nextAction`, and latest-pair pipeline recommendation. |
| Promotion latest-pair command safety smoke | Passed by marking latest-pair pipeline plan safe and artifact-writing run unsafe without attach when lead-neighborhood evidence already exists. |
| Promotion latest-pair safety summary smoke | Passed by summarizing latest-pair recommended command safety with artifact-writing runs unsafe and no attach required when neighborhoods already exist. |
| Promotion unsafe next-action safety smoke | Passed by inheriting unsafe recommended command safety onto missing-neighborhood `nextAction` metadata. |
| Promotion command quoting smoke | Passed by preserving manifest-seeded nameplate text containing PowerShell metacharacters through generated `commandParts` execution. |
| Promotion next-action helper smoke | Passed by reporting the safe planner `nextAction`, guarded `commandParts` execution of the plan-only next action, and top-level operator checklist plus recommended-command safety summary surfacing. |
| Promotion next-action unsafe smoke | Passed by refusing to execute an unsafe next action that would attach to the process and create artifacts while preserving the normalized no-execution result shape. |

The aggregate branch validator was also run:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\test-navigation-projection-offline.ps1" -Json
```

Result: `ok=true`; projection workflow validator `38/38`, Reader tests `70/70`,
and `git diff --check` exited `0` with CRLF normalization warnings only.
