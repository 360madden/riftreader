---
state: current
as_of: 2026-04-24
---

# Navigation Projection Branch Review Manifest — 2026-04-24

## Scope

This manifest classifies the current untracked `navigation` branch projection work
before staging or cleanup. It is intentionally conservative: keep source and
concise docs reviewable, keep bulky capture artifacts out of the first source
patch unless the user explicitly wants durable proof artifacts tracked.

## Current branch status

| Item | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `navigation` |
| Capture/artifact total | `239` files, about `202.85 MB` under `artifacts\tooltip-projection` + `artifacts\window-capture` |
| Git staged files | none at manifest creation |

## Source/docs recommended for first review patch

| Path | Reason |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\capture-tooltip-hover-diff.ps1` | Main screenshot-gated state capture helper. |
| `C:\RIFT MODDING\RiftReader\scripts\capture-tooltip-hover-diff.cmd` | CMD wrapper for the capture helper. |
| `C:\RIFT MODDING\RiftReader\scripts\analyze-tooltip-hover-diff.ps1` | Analyzer, screenshot-gate reporting, and `-RequireVisualGate`. |
| `C:\RIFT MODDING\RiftReader\scripts\analyze-tooltip-hover-diff.cmd` | CMD wrapper for the analyzer. |
| `C:\RIFT MODDING\RiftReader\scripts\capture-rift-window-wgc.ps1` | Wrapper for WGC/Desktop Duplication capture. |
| `C:\RIFT MODDING\RiftReader\scripts\capture-rift-window-wgc.cmd` | CMD wrapper for WGC/Desktop Duplication capture. |
| `C:\RIFT MODDING\RiftReader\scripts\capture-rift-window-printwindow.ps1` | GDI/PrintWindow fallback and quality gate. |
| `C:\RIFT MODDING\RiftReader\scripts\capture-rift-window-printwindow.cmd` | CMD wrapper for PrintWindow fallback capture. |
| `C:\RIFT MODDING\RiftReader\scripts\test-rift-window-capture-methods.ps1` | No-input capture-method diagnostic sweep. |
| `C:\RIFT MODDING\RiftReader\scripts\test-rift-window-capture-methods.cmd` | CMD wrapper for capture-method diagnostics. |
| `C:\RIFT MODDING\RiftReader\scripts\test-projection-screenshot-gate-workflow.ps1` | Offline validation for parser checks, capture helper build, shared CMD launcher contract, CMD wrapper shape/launcher/target inspection, wrapper key-argument preservation, plan-only no-artifact behavior, bounded validator CMD-wrapper smoke, analyzer visual-gate smoke, and fail-closed no-screenshot behavior. |
| `C:\RIFT MODDING\RiftReader\scripts\test-projection-screenshot-gate-workflow.cmd` | CMD wrapper for offline workflow validation. |
| `C:\RIFT MODDING\RiftReader\scripts\run-nameplate-projection-proof.ps1` | Thin wrapper that preserves screenshot-gated capture and fail-closed analyzer defaults for nameplate proof runs. |
| `C:\RIFT MODDING\RiftReader\scripts\run-nameplate-projection-proof.cmd` | CMD wrapper for the nameplate proof wrapper. |
| `C:\RIFT MODDING\RiftReader\tools\rift-window-capture\RiftWindowCapture.csproj` | .NET helper project file. |
| `C:\RIFT MODDING\RiftReader\tools\rift-window-capture\Program.cs` | WGC/Desktop Duplication implementation. |
| `C:\RIFT MODDING\RiftReader\.gitignore` | Keeps generated projection/window-capture artifact roots out of normal status/staging. |
| `C:\RIFT MODDING\RiftReader\docs\analysis\README.md` | Links the current operator runbook. |
| `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-24-navigation-projection-branch-review-manifest.md` | This staging/cleanup manifest. |
| `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-24-projection-screenshot-gated-runbook.md` | Current runbook for capture and fail-closed analysis. |
| `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-24-tooltip-entity-projection-discovery.md` | Dated discovery report. |
| `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-24-tooltip-hover-diff-helper-live-run.md` | Append-only running evidence report. |
| `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-04-24-030911-navigation-reticle-marker-handoff.md` | Earlier same-day marker/reticle handoff. |

## Generated outputs to avoid in first source patch

| Path / pattern | Reason |
|---|---|
| `C:\RIFT MODDING\RiftReader\tools\rift-window-capture\bin\` | Build output; already ignored by `.gitignore`. |
| `C:\RIFT MODDING\RiftReader\tools\rift-window-capture\obj\` | Build output; already ignored by `.gitignore`. |
| `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\capture-diagnostics\` | Useful diagnostics but bulky, about `46.85 MB`. |
| `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-0335-tooltip-projection\` | Initial screenshot-heavy mailbox evidence, about `45.69 MB`. |
| `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-095742-screenshot-gate-analyzer-smoke\` | Smoke proof, about `28.16 MB`; keep locally unless durable artifact tracking is requested. |
| `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-062412-mailbox-pointerlead-printwindow-live\` | Low-signal mailbox pointer-lead run, about `22.23 MB`. |
| `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\wgc-captures\` | Diagnostic WGC captures, about `20.44 MB`. |
| `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-045239-mailbox-tooltip-live\` | Older low-signal mailbox run, about `19.61 MB`. |
| `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-095431-screenshot-gate-smoke\` | One-state smoke proof, about `14.07 MB`. |
| `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\printwindow-screenshots\` | PrintWindow quality tests, about `5.74 MB`. |

## Artifact retention recommendation

| Artifact class | Recommendation |
|---|---|
| Source scripts and .NET helper source | Track. |
| Runbooks and dated analysis docs | Track. |
| Tiny JSON summaries that are explicitly referenced by docs | Consider tracking only if a later PR needs proof artifacts in-repo. |
| BMP/PNG screenshots and repeated diagnostic runs | Keep local by default; do not stage in first review patch. |
| Failed/aborted runs | Keep local until user approves pruning, then delete or archive outside git. |

## Suggested stage command once user approves staging

```powershell
git add -- `
  .gitignore `
  docs/analysis/README.md `
  docs/analysis/2026-04-24-navigation-projection-branch-review-manifest.md `
  docs/analysis/2026-04-24-projection-screenshot-gated-runbook.md `
  docs/analysis/2026-04-24-tooltip-entity-projection-discovery.md `
  docs/analysis/2026-04-24-tooltip-hover-diff-helper-live-run.md `
  docs/handoffs/2026-04-24-030911-navigation-reticle-marker-handoff.md `
  scripts/analyze-tooltip-hover-diff.cmd `
  scripts/analyze-tooltip-hover-diff.ps1 `
  scripts/capture-tooltip-hover-diff.cmd `
  scripts/capture-tooltip-hover-diff.ps1 `
  scripts/capture-rift-window-printwindow.cmd `
  scripts/capture-rift-window-printwindow.ps1 `
  scripts/capture-rift-window-wgc.cmd `
  scripts/capture-rift-window-wgc.ps1 `
  scripts/run-nameplate-projection-proof.cmd `
  scripts/run-nameplate-projection-proof.ps1 `
  scripts/test-projection-screenshot-gate-workflow.cmd `
  scripts/test-projection-screenshot-gate-workflow.ps1 `
  scripts/test-rift-window-capture-methods.cmd `
  scripts/test-rift-window-capture-methods.ps1 `
  tools/rift-window-capture/RiftWindowCapture.csproj `
  tools/rift-window-capture/Program.cs
```

Do not stage `artifacts\tooltip-projection\` in the first pass unless the user
explicitly asks to preserve proof artifacts in git.

## Immediate next step

Run the real nameplate baseline/zoom proof using the screenshot-gated runbook,
or stage the source/docs patch set above if the user wants to checkpoint the
branch before more live proof.

## Follow-up — gitignore noise reduction

The generated capture roots were added to `.gitignore` after this manifest was created:

```text
artifacts/tooltip-projection/
artifacts/window-capture/
```

This intentionally ignores only the screenshot/projection diagnostic roots from
this branch. It does **not** ignore the broader `artifacts\` tree and does not
affect durable Cheat Engine table guidance under
`artifacts\cheat-engine\tables\`.

If a future proof artifact under these ignored roots must be committed, use an
explicit `git add -f <path>` for that selected artifact only.

## Follow-up — nameplate proof wrapper

`C:\RIFT MODDING\RiftReader\scripts\run-nameplate-projection-proof.ps1` was
added after the first manifest draft and is now included in the recommended
first review patch list and stage command above.

## Follow-up — offline workflow validation script

Add this source file to the first review patch as well:

| Path | Reason |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\test-projection-screenshot-gate-workflow.ps1` | Offline validation for parser checks, capture helper build, shared CMD launcher contract, CMD wrapper shape/launcher/target inspection, wrapper key-argument preservation, plan-only no-artifact behavior, bounded validator CMD-wrapper smoke, analyzer visual-gate smoke, and fail-closed no-screenshot behavior. |

Latest validation passed with `ok=true`.

## Follow-up — full offline validator pass

Latest checkpoint validation passed with no skips:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\test-projection-screenshot-gate-workflow.ps1" -Json
```

Result: `ok=true`; parser, machine-readable shared CMD launcher contract, CMD wrapper
shape/launcher/target inspection with target existence reporting, capture project build,
PowerShell wrapper plan, CMD wrapper plan, wrapper key-argument preservation,
plan-only no-artifact behavior, bounded validator CMD-wrapper smoke, analyzer visual-gate smoke, and fail-closed
no-screenshot visual-gate smoke all passed.
