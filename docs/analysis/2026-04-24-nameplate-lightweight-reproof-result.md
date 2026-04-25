# 2026-04-24 Nameplate lightweight baseline/zoom reproof result

## TL;DR

A lightweight second `nameplate-baseline-zoom` proof completed and passed the screenshot/sequence gate, but it is **not promotion-ready**.

The proof intentionally used `-SkipTextScan -SkipPointerScan` to avoid the process-heavy scans that stalled the default proof. That made the live capture fast enough, but it also means the run has no text/pointer leads for lead-neighborhood promotion.

## Live run

| Field | Value |
|---|---|
| Run root | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-234712-nameplate-baseline-zoom` |
| Candidate | `0x12CFC40B7D0` |
| Nameplate text | `Atank of Sanctum` |
| Mode | Lightweight reproof |
| Scan controls | `-MaxHits 4 -TextPointerScanMode none -SkipTextScan -SkipPointerScan` |
| Operator states | `baseline1,zoom1,baseline2,zoom2` |

## Validation evidence

| Check | Result |
|---|---|
| `check-nameplate-projection-proof-result.ps1` | `ok=true` |
| Visual gate | `passed` |
| Usable screenshots | `4/4` |
| Expected state sequence | `passed` |
| Candidate count in new run | `3` |
| Planner `readyForPipeline` | `true` |
| Planner `readyForPromotionCompare` | `false` |
| Missing evidence | `reproof-run-needs-lead-neighborhood-capture`, `no-promotion-ready-packet-yet` |

## Important negative evidence

The older candidate offset cluster did **not** repeat in the lightweight reproof:

| Comparator | Result |
|---|---|
| Candidate offsets checked | `+0x21D,+0x225,+0x235,+0x23D,+0x24D` |
| Required repeat count | `3` |
| Repeated count | `0` |
| Result | `ok=false` for promotion of that cluster |

The latest rerun saved the comparator JSON outputs under the ignored live
artifact tree for resume/debug use:

| Artifact | Path |
|---|---|
| Candidate-offset compare | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-234712-nameplate-baseline-zoom\diffs\latest-pair-candidate-offset-compare.json` |
| Byte-window compare | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-234712-nameplate-baseline-zoom\diffs\latest-pair-byte-window-compare.json` |
| Planner summary snapshot | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-234712-nameplate-baseline-zoom\diffs\latest-pair-current-planner-summary.json` |

The byte-window comparator also found:

| Metric | Value |
|---|---:|
| Compared offsets | `1024` |
| Repeated changing offsets | `0` |
| Baseline-only changes | `70` |
| Reproof-only changes | `4` |
| Changed in both but different | `37` |

## Promotion status

The latest-pair pipeline plan selected:

| Role | Run |
|---|---|
| Baseline | `20260424-143102-nameplate-baseline-zoom` |
| Reproof | `20260424-234712-nameplate-baseline-zoom` |

The plan is blocked because the reproof has no lead-neighborhood file. Attempting default reproof lead-neighborhood capture failed with:

```text
No nameplate proof leads matched LeadKind=pointer-hit, MinStateCount=2, MaxLeads=3.
```

This is expected for the lightweight reproof because text/pointer scans were intentionally skipped.

## Current conclusion

The second proof is good as a **visual/sequence-gated lightweight reproof**, but it does not validate the previous promotion candidate cluster and does not provide the pointer/text lead evidence needed by the existing promotion packet path.

Do not promote the old `+0x21D/+0x225/+0x235/+0x23D/+0x24D` cluster from this run.

## Recommended next move

Tested bounded targeted lead refresh, not another full process-wide proof:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\capture-nameplate-proof-lead-neighborhoods.ps1" `
  -RunRoot "C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-234712-nameplate-baseline-zoom" `
  -LeadKind both `
  -MinStateCount 1 `
  -MaxLeads 3 `
  -Json
```

If that still has no leads or is too heavy, do **not** promote by force. Either:

Result: this bounded lead refresh also failed quickly with:

```text
No nameplate proof leads matched LeadKind=both, MinStateCount=1, MaxLeads=3.
```

So the practical choices are now:

1. Capture a targeted, less-heavy text/pointer lead pass for the reproof run, or
2. Add a separate promotion path for screenshot-gated candidate-window byte evidence, with explicit weaker-evidence labeling.

Do not fake promotion readiness by manually selecting stale pointer-hit roots from the old baseline run.

## Diagnostic report artifact

Added a no-attach diagnostic report writer for lightweight reproofs:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\write-nameplate-lightweight-reproof-report.ps1" `
  -BaselineRunRoot "C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-143102-nameplate-baseline-zoom" `
  -ReproofRunRoot "C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-234712-nameplate-baseline-zoom" `
  -CandidateOffsets "+0x21D,+0x225,+0x235,+0x23D,+0x24D" `
  -MinCandidateRepeatCount 3 `
  -ByteWindowLength 1024 `
  -Json
```

The report is explicitly **diagnostic-only** and does not write or imply a promotion packet.
The current generated report is ignored with the rest of live artifacts at:

`C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-234712-nameplate-baseline-zoom\diffs\nameplate-lightweight-reproof-report.json`

Latest report summary:

| Field | Value |
|---|---|
| `diagnosticOnly` | `true` |
| `promotionReady` | `false` |
| `promotionReadiness` | `blocked` |
| Candidate repeat count | `0` |
| Repeated changing byte offsets | `0` |
| Blockers | `reproof-run-missing-lead-neighborhood`, `insufficient-repeated-candidate-offsets`, `insufficient-repeated-changing-byte-offsets` |

This preserves the lightweight proof as useful negative evidence without weakening the promotion gate.

## Inventory/planner surfacing

The gated-run inventory and promotion planner now surface this report directly:

| Planner field | Current value |
|---|---|
| `inventory.baselineZoomRunsWithLightweightDiagnostic` | `1` |
| `selectedReproofRun.hasLightweightReproofReport` | `true` |
| `selectedReproofRun.lightweightPromotionReadiness` | `blocked` |

The planner still keeps the next action on lead-neighborhood capture because the diagnostic report is not promotion evidence.

## Future missing-diagnostic planner command

When the latest baseline/reproof pair is blocked for promotion and the selected reproof does **not** already have a lightweight diagnostic report, the planner now recommends two diagnostic report commands:

| Command | Safety |
|---|---|
| `lightweight-reproof-report-plan` | safe, no attach, no artifacts |
| `lightweight-reproof-report-write` | no attach, writes diagnostic artifact only |

These commands are not shown for the current latest reproof because it already has `nameplate-lightweight-reproof-report.json`.

## Non-stale planner blocker summary

The planner now emits `promotionBlockerSummary` so the current state is explicit without rereading historical notes:

| Field | Current value |
|---|---|
| `promotionBlockerSummary.status` | `diagnostic-exists-but-reproof-lead-neighborhood-missing` |
| `promotionBlockerSummary.nextRequiredEvidence` | `reproof-lead-neighborhood` |
| `promotionBlockerSummary.selectedReproofHasLightweightDiagnostic` | `true` |

This keeps the diagnostic report visible while making clear it does not satisfy the lead-neighborhood promotion gate.

## Safe lead-selection dry run

The planner now recommends a safe pre-capture command for missing lead-neighborhood evidence:

| Command | Current behavior |
|---|---|
| `plan-reproof-lead-neighborhood` | No attach, no artifacts, uses `-PlanOnly -AllowNoLeads` to report whether artifact leads exist before any capture attempt. |

Current result for the selected reproof is `captureReady=false`, `blocker=no-leads-matched`, `selectedLeadCount=0`, confirming the lightweight run still has no lead source to capture from.

## Current artifact inventory guard

The planner now compares both all nameplate runs and gated-only nameplate runs. If the workspace has nameplate baseline/zoom artifacts but none pass the screenshot/sequence gate, it reports:

| Field | Value |
|---|---|
| `promotionBlockerSummary.status` | `latest-nameplate-run-not-gated` |
| `inventory.totalBaselineZoomRuns` | all baseline/zoom run folders found |
| `inventory.gatedBaselineZoomRuns` | gated baseline/zoom runs eligible for promotion comparison |
| `inventory.ungatedBaselineZoomRuns` | baseline/zoom run folders that exist but are not promotion evidence |

This prevents stale handoff assumptions from hiding the current local truth when ignored artifact folders differ between worktrees or branches.
