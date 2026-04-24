# Tooltip Hover Diff Helper Live Run — 2026-04-24

## Verdict

**Low-signal for the current mailbox tooltip raw candidate window.** The helper pipeline ran 3 hidden/hover cycles with screenshot-gated visual confirmation and Reader CLI memory reads. Tooltip text hits and repeat pointer-scan artifacts were captured, but the sampled candidate window stayed effectively static across hidden/hover states, so no screen-rect/projection-anchor field was promoted.

## Scope / safety

- Live control owner: main agent only.
- Inputs used: mouse hover only; no clicks, casts, mailbox opens, looting, or player movement.
- Target/read check: every sampled state reported `hasTarget=false`.
- Cursor was moved off the mailbox after the run.

## Implemented helpers

| Script | Purpose | Notes |
|---|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\capture-tooltip-hover-diff.ps1` | State-labeled Reader CLI capture wrapper | Emits manifest/events/samples/state JSON; supports comma-separated `-States`; does not control live input. |
| `C:\RIFT MODDING\RiftReader\scripts\analyze-tooltip-hover-diff.ps1` | Offline scorer for hidden/hover memory diffs | Emits `diffs\hidden_vs_hover.json`, `diffs\stable-hover-fields.json`, `diffs\field-candidates.json`, and `summary.json`. |

## Live artifact set

| Item | Path |
|---|---|
| Run root | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-045239-mailbox-tooltip-live` |
| Manifest | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-045239-mailbox-tooltip-live\manifest.json` |
| Samples | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-045239-mailbox-tooltip-live\samples.ndjson` |
| Events | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-045239-mailbox-tooltip-live\events.ndjson` |
| Screenshots manifest | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-045239-mailbox-tooltip-live\screenshots.json` |
| Analyzer summary | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-045239-mailbox-tooltip-live\summary.json` |
| Field candidates | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-045239-mailbox-tooltip-live\diffs\field-candidates.json` |

## Screenshot pair/cycle paths

| State | Screenshot |
|---|---|
| hidden | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-045239-mailbox-tooltip-live\screenshots\hidden.png` |
| hover | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-045239-mailbox-tooltip-live\screenshots\hover.png` |
| hidden2 | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-045239-mailbox-tooltip-live\screenshots\hidden2.png` |
| hover2 | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-045239-mailbox-tooltip-live\screenshots\hover2.png` |
| hidden3 | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-045239-mailbox-tooltip-live\screenshots\hidden3.png` |
| hover3 | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-045239-mailbox-tooltip-live\screenshots\hover3.png` |

## Memory evidence summary

| Evidence | Result |
|---|---|
| Sample count | 6 total: 3 hidden, 3 hover |
| Candidate sampled | `0x12CF46C6F80 ± 0x200` (`baseAddress=0x12CF46C6D80`, length 1024) |
| `hasTarget` | `false` for all 6 states |
| Text hits | 2-4 hits per state; hover states added transient tooltip-string hits |
| Repeat pointer-scan lead | `0x12CF88E0A30 -> 0x12CF46C6B80` repeated in hover/hover2/hover3 pointer scans |
| Analyzer candidates | `0` promoted candidates in the sampled raw window |
| Analyzer decision | No `text-pointer-field`, lifecycle flag, UI rect, owner pointer, or projection anchor promoted from the sampled candidate window |

## Reuse classification

| Classification | Decision |
|---|---|
| Entity-only projection | Not proven |
| Arbitrary XYZ projection | Not proven |
| Tooltip-only UI anchoring | Plausible visually, but not memory-proven from this sampled window |
| Low-signal | **Current result** |

The mailbox tooltip is visually reliable and hover-only, but this run did not find a reusable projection/rect anchor in the selected raw window. The repeat pointer-scan lead is useful as a follow-up seed, but it is still a current-session candidate only and cannot be promoted without a raw-window repeat check and/or writer/source tracing.

## Validation run

| Check | Result |
|---|---|
| PowerShell parser check | Passed for both helper scripts |
| Capture helper plan/smoke | Passed, including comma-separated `-States hidden,hover` normalization |
| Capture helper summary smoke | Passed after fixing the summary construction issue |
| Analyzer fixture/smoke | Passed; known hover text pointer at `+0x8` promoted as `text-pointer-field` |
| `git diff --check` | Passed |
| Live hidden/hover cycles | Passed visually with 3 cycles and `hasTarget=false` |
| Candidate validation | Low-signal: no promoted field candidates in sampled window |

## Recommendation

Do not build marker rendering from the mailbox tooltip candidate yet. Next, use the repeat pointer-scan lead (`0x12CF46C6B80`) and/or direct writer/source tracing to locate the actual tooltip layout/rect owner, or pivot the same helper pipeline to nameplates where the projection path is likely more durable.

## Follow-up — pointer-lead resample attempt

A follow-up run was started against the repeated pointer-scan lead window:

| Item | Value |
|---|---|
| Candidate | `0x12CF46C6B80 ± 0x200` |
| Run root | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-053531-mailbox-pointerlead-live` |
| Completed state | `hidden` only |
| Abort reason | Screenshot capture failed while preparing `hover`; stopped before hover memory capture because tooltip state could not be visually confirmed. |
| Safety action | Cursor moved off mailbox and capture helper interrupted. |
| Abort note | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-053531-mailbox-pointerlead-live\aborted-note.json` |

No pointer-lead promotion should be inferred from this partial run. It is only a recorded aborted attempt.

## Helper extension after abort

`capture-tooltip-hover-diff.ps1` now supports optional follow-up scans without adding new memory-reader code:

| Parameter | Purpose |
|---|---|
| `-ExtraPointerTargets` | Run explicit `--scan-pointer` probes for known/repeat pointer leads in every state. |
| `-ScanInt32Values` | Run explicit `--scan-int32` probes for candidate screen/rect values. |
| `-ScanFloatValues` | Run explicit `--scan-float` probes for candidate screen/rect values. |
| `-ScanDoubleValues` | Run explicit `--scan-double` probes for candidate screen/rect values. |
| `-ScanTolerance` | Shared tolerance for float/double scans. |

These additions keep the existing Reader CLI as the only memory reader and are intended to make the next screenshot-gated run faster once screen capture is available again.

## Follow-up — PrintWindow-gated pointer-lead run

The screenshot blocker was worked around with a read-only `PrintWindow(PW_RENDERFULLCONTENT)` helper, then the pointer-lead run was completed with 3 screenshot-gated hidden/hover cycles.

| Item | Value |
|---|---|
| Run root | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-062412-mailbox-pointerlead-printwindow-live` |
| Screenshot method | `C:\RIFT MODDING\RiftReader\scripts\capture-rift-window-printwindow.ps1` |
| Candidate window | `0x12CF46C6B80 ± 0x200` (`baseAddress=0x12CF46C6980`, length 1024) |
| States | `hidden`, `hover`, `hidden2`, `hover2`, `hidden3`, `hover3` |
| Screenshots manifest | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-062412-mailbox-pointerlead-printwindow-live\screenshots.json` |
| Analyzer field candidates | `0` promoted from the raw pointer-lead window |
| Scan evidence file | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-062412-mailbox-pointerlead-printwindow-live\diffs\scan-evidence.json` |
| `hasTarget` | `false` in all 6 samples |

### Pointer-lead result

| Probe | Result |
|---|---|
| `0x12CF88E0A30` explicit pointer scan | State-invariant hit at `0x12C94D64CA8`; not hover-specific |
| Candidate raw bytes | No promoted hidden/hover lifecycle, rect, owner, or projection field |
| Screen numeric scans `906/644` | Broad numeric scan noise; downranked by analyzer |
| Tooltip text/pointer lane | Remains useful for finding text records, but not enough for projection/rect promotion |

### Updated classification

The mailbox tooltip path remains visually reliable, but both sampled memory windows are low-signal for reusable projection:

| Window | Decision |
|---|---|
| `0x12CF46CE240 ± 0x200` | Low-signal/static for rect/projection |
| `0x12CF46C6B80 ± 0x200` | Low-signal/static for rect/projection |
| Explicit `0x12CF88E0A30` pointer scan | State-invariant, not a hover lifecycle field |

### Helper corrections made after this run

| Script | Correction |
|---|---|
| `capture-tooltip-hover-diff.ps1` | Hidden text baselines are now cumulative across every hidden state, not only the first hidden state. This prevents stale/transient tooltip strings from being misclassified as hover-only in later cycles. |
| `analyze-tooltip-hover-diff.ps1` | Added `diffs\scan-evidence.json` and scan-evidence scoring for explicit pointer/numeric scans. Broad numeric scans are downranked as noise. |
| `capture-rift-window-printwindow.ps1` | Added as a screenshot fallback when `CopyFromScreen` fails; it does not control live input. |

### Current recommendation

Do not continue mining these two mailbox tooltip windows for projection unless we add writer/source tracing. The next best proof path is either writer/source tracing from tooltip layout updates, or pivoting the same helper/analyzer pipeline to nameplates where screen-space projection data is more likely to be durable.

## Follow-up — nameplate-pivot preparation

The helper/analyzer pipeline was generalized for the nameplate pivot, but the live baseline-vs-zoom proof was stopped before capture because visual reliability degraded.

| Item | Result |
|---|---|
| Analyzer state grouping | Added `-BaselineStateRegex`, `-ActiveStateRegex`, `-BaselineLabel`, and `-ActiveLabel` so states like `baseline1/zoom1` can be compared without pretending they are hidden/hover states. |
| Capture helper text-pointer mode | Added `-TextPointerScanMode allHits` so persistent nameplate text can be pointer-scanned in every state, not only hover-only tooltip states. |
| Nameplate text seed | `Atank of Sanctum` scanned successfully with 3 hits: `0x12CE51CA980`, `0x12CFAF091D0`, `0x12CFB4BC500`. |
| Pointer seeds from nameplate text | `0x12CE51CA980 -> 0x12CFC40B7D0`; `0x12CFAF091D0 -> 0x12D034CC668`; `0x12CFB4BC500 -> 0x12C9832C980`. |
| Live zoom/input proof | Not completed. A target-window mouse-wheel experiment was attempted outside the committed helper set, then stopped because subsequent `PrintWindow` captures were black. No nameplate projection inference should be made from this. |
| Safety cleanup | The experimental mouse-wheel helper was not retained. |

### Current nameplate-ready command shapes

Capture example, once visual capture is reliable again:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\capture-tooltip-hover-diff.ps1" `
  -ProcessName rift_x64 `
  -CandidateAddress 0x12CFC40B7D0 `
  -CandidateLength 1024 `
  -TooltipText "Atank of Sanctum" `
  -States baseline1,zoom1,baseline2,zoom2 `
  -TextPointerScanMode allHits `
  -RunLabel nameplate-baseline-zoom `
  -Json
```

Analyzer example:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\analyze-tooltip-hover-diff.ps1" `
  -InputDirectory "<run-root>" `
  -BaselineStateRegex "^baseline" `
  -ActiveStateRegex "^zoom" `
  -BaselineLabel baseline `
  -ActiveLabel zoom `
  -Json
```

### Nameplate pivot status

Nameplate evidence is ready for a retry once the live visual channel is stable, but the current session should not continue live camera/zoom manipulation until the black-capture state is resolved. Offline helper/analyzer validation passed.

## Follow-up — screenshot quality gate hardening

The `PrintWindow` fallback was hardened so it fails closed instead of allowing black game-content captures to masquerade as visual proof.

| Item | Result |
|---|---|
| Script | `C:\RIFT MODDING\RiftReader\scripts\capture-rift-window-printwindow.ps1` |
| Added behavior | Tries multiple `PrintWindow` flags, scores content-region brightness/non-black ratio, reports `usable`, and supports `-RequireUsable`. |
| Current test screenshot | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\printwindow-screenshots\quality-test-20260424-074601.png` |
| Current quality result | `usable=false`; selected flag `0`; content non-black ratio `0.012346`; classified as likely black/unusable. |
| `-RequireUsable` test | Failed closed and wrote `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\printwindow-screenshots\require-usable-test-20260424-074834.png.quality.json`. |
| Rift MCP capture | Still blocked by `CopyFromScreen`: `The handle is invalid.` |
| Windows MCP desktop capture | Still blocked by access denied. |

## Follow-up — no-input capture-method diagnostics

A reusable no-input diagnostic helper was added to avoid re-testing capture methods by hand.

| Item | Result |
|---|---|
| Script | `C:\RIFT MODDING\RiftReader\scripts\test-rift-window-capture-methods.ps1` |
| Purpose | Try multiple non-input capture paths and score each output with the same black-content quality gate. |
| Diagnostic run root | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\capture-diagnostics\20260424-075213-capture-methods` |
| Best method in current run | `PrintWindowFlag2`, but still `usable=false`. |
| Methods tested | `PrintWindowFlag2`, `PrintWindowFlag0`, `PrintWindowFlag1`, `WindowDcBitBlt`, `ClientDcBitBlt`, `ScreenDcBitBltClient`, `CopyFromScreenClient`. |
| Outcome | No tested no-input capture method produced usable game content. PrintWindow/window DC paths captured only title/chrome or black content; client DC was black; screen DC failed with Win32 error `6`; `CopyFromScreen` still throws `The handle is invalid.` |

The diagnostic helper now records additional window metadata. The latest run is:

| Item | Value |
|---|---|
| Diagnostic run root | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\capture-diagnostics\20260424-080101-capture-methods` |
| Window class | `TWNClientFramework` |
| Visible / minimized | `isVisible=true`, `isIconic=false` |
| Foreground | `isForeground=false`, `foregroundWindowHandle=0x0` |
| Display affinity | `0` (`WDA_NONE`; not capture-protected by window affinity) |
| DWM cloaked | `0` (not cloaked) |
| Best capture method | `PrintWindowFlag2`, still `usable=false` |

This narrows the failure: the window is visible, not minimized, not DWM-cloaked, and not using display-affinity capture protection. The remaining evidence points to the current desktop/capture stack being unable to capture DirectX game content through GDI/PrintWindow paths.

## Follow-up — memory sanity while visual capture is blocked

Reader memory access remains healthy, so the current blocker is visual truth, not process attach/read access.

| Item | Result |
|---|---|
| Run root | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\memory-sanity\20260424-075724` |
| `--read-target-current` | Mode `target-current-read`, `hasTarget=false` |
| Nameplate text scan | `"Atank of Sanctum"` returned `3` hits |
| Mailbox tooltip text scan | `"Send and receive mail here."` returned `2` hits |
| Interpretation | Existing Reader CLI can still read/scan Rift, and the nameplate seed remains available for a later visual-gated probe. |

### Current live decision

Do **not** resume nameplate/camera/tooltip live sampling in the current visual state. The memory reader remains usable, but projection proof requires a reliable visual gate; otherwise camera/hover labels cannot be trusted.

Safe continuation options are now limited to offline/helper work, memory-only exploratory scans explicitly labeled as unvisualized, or restoring a usable capture path before the next live proof cycle.

## Follow-up — Windows Graphics Capture helper

A Windows Graphics Capture / D3D11 helper was added as the next no-input escalation after GDI, `CopyFromScreen`, and `PrintWindow` all failed to capture game content.

| Item | Result |
|---|---|
| Project | `C:\RIFT MODDING\RiftReader\tools\rift-window-capture\RiftWindowCapture.csproj` |
| Main source | `C:\RIFT MODDING\RiftReader\tools\rift-window-capture\Program.cs` |
| Wrapper | `C:\RIFT MODDING\RiftReader\scripts\capture-rift-window-wgc.ps1` |
| Build | `dotnet build C:\RIFT MODDING\RiftReader\tools\rift-window-capture\RiftWindowCapture.csproj -v:minimal` passed with `0` warnings and `0` errors. |
| Runtime interop fixes | Uses C#/WinRT marshaling for `GraphicsCaptureItem`, `IDirect3DDevice`, and `IDirect3DSurface` instead of invalid COM object casts. |
| Image output | Writes BMP directly from mapped BGRA rows to avoid `System.Drawing` PNG encoder failure during WGC frame extraction. |
| Default output root | `%TEMP%\RiftReader-window-capture\wgc` because WGC BMP writes failed under the repo path with spaces while `%TEMP%` succeeded. |

### WGC live capture result

| Item | Value |
|---|---|
| Latest WGC window capture | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\wgc-captures\capture-20260424-082144-260.bmp` |
| Window JSON sidecar | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\wgc-captures\capture-20260424-082144-260.bmp.json` |
| `Ok` | `true` |
| `Usable` | `false` |
| Size | `1281 x 1305` |
| Whole-frame black ratio | `0.9739583239865885` |
| Content black ratio | `0.9976395664207496` |
| Content luma stddev | `2.2716370184813504` |
| Interpretation | WGC can acquire a Rift frame and window chrome, but the game-content region is still black/flat. This restores a stronger diagnostic path, not a usable projection-proof visual gate yet. |

A monitor-based WGC fallback was also added and tested:

| Item | Value |
|---|---|
| WGC monitor capture | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\wgc-captures\capture-20260424-082446-620.bmp` |
| Monitor JSON sidecar | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\wgc-captures\capture-20260424-082446-620.bmp.json` |
| `Ok` / `Usable` | `true` / `false` |
| Size | `2560 x 1440` |
| Black ratio | `1` |
| Content black ratio | `1` |
| Interpretation | Monitor capture succeeds mechanically but is fully black, so it does not restore visual truth. |

### Current visual-capture status

| Capture path | Current status |
|---|---|
| Rift MCP / `CopyFromScreen` | Fails with `The handle is invalid.` |
| Windows MCP desktop screenshot | Access denied |
| `PrintWindow` / GDI DC capture | Window chrome or black content only |
| WGC / D3D11 window helper | Captures window frame/chrome, but game content is black/flat; `Usable=false` |
| WGC / D3D11 monitor helper | Captures full monitor frame, but it is fully black; `Usable=false` |

The memory-reader lane remains valid, but live projection sampling is still blocked until a capture path shows non-black game content.

## Follow-up — DXGI Desktop Duplication fallback

A no-input DXGI Desktop Duplication fallback was added to the existing WGC helper so the visual-gate diagnostics no longer stop at Windows Graphics Capture / GDI / PrintWindow.

| Item | Result |
|---|---|
| Tool change | `C:\RIFT MODDING\RiftReader\tools\rift-window-capture\Program.cs` now supports `--desktop-duplication`. |
| Wrapper change | `C:\RIFT MODDING\RiftReader\scripts\capture-rift-window-wgc.ps1` now supports `-DesktopDuplication`. |
| Capture method label | JSON reports `CaptureMethod` (`WindowsGraphicsCaptureWindow`, `WindowsGraphicsCaptureMonitor`, or `DXGIDesktopDuplication`). |
| Validation | `dotnet build C:\RIFT MODDING\RiftReader\tools\rift-window-capture\RiftWindowCapture.csproj -v:minimal` passed with `0` warnings and `0` errors. |
| Live input used | None. |

### Desktop Duplication live result

| Item | Value |
|---|---|
| Diagnostic JSON | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\desktop-duplication-captures\capture-20260424-094225-034.desktopdup.json` |
| BMP output | `C:\Users\mrkoo\AppData\Local\Temp\RiftReader-window-capture\wgc\capture-20260424-094226-016.bmp` |
| `Ok` / `Usable` | `true` / `false` |
| Capture method | `DXGIDesktopDuplication` |
| Size | `2560 x 1440` |
| Black ratio | `1` |
| Content black ratio | `1` |
| Content luma stddev | `0` |
| Interpretation | Desktop Duplication acquires a frame successfully, but it is fully black, so it does **not** restore visual truth for tooltip/nameplate projection proof. |

### Updated capture-blocker classification

The current capture stack now has a stronger negative result: GDI/PrintWindow, WGC window, WGC monitor, and DXGI Desktop Duplication all acquire mechanically but fail the usable game-content gate (or fail before content). This points away from helper bugs and toward the current Windows/session/game-rendering capture path returning black frames for Rift.

Do not resume tooltip/nameplate projection sampling until a non-black visual gate is restored, unless the next run is explicitly memory-only and labeled unvisualized.

## Follow-up — visual gate restored with multi-attempt Desktop Duplication

The capture lane was hardened again after the first single-frame Desktop Duplication run returned black. The helper now records richer Desktop Duplication diagnostics and can take multiple no-input attempts, selecting the best frame by usability/non-black/luma variation.

| Item | Result |
|---|---|
| Tool change | `C:\RIFT MODDING\RiftReader\tools\rift-window-capture\Program.cs` now supports `--attempts <n>` for Desktop Duplication and records source texture / output metadata. |
| Wrapper change | `C:\RIFT MODDING\RiftReader\scripts\capture-rift-window-wgc.ps1` now supports `-Attempts`. |
| Diagnostic helper change | `C:\RIFT MODDING\RiftReader\scripts\test-rift-window-capture-methods.ps1` now includes `DXGIDesktopDuplication` in the no-input method sweep and copies the temp BMP into the diagnostic image folder. |
| Live input used | None. |

### Restored capture result

| Item | Value |
|---|---|
| Diagnostic run root | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\capture-diagnostics\20260424-094950-capture-methods` |
| Summary mirror | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\capture-diagnostics\latest-capture-methods-with-dd.json` |
| Best method | `DXGIDesktopDuplication` |
| Desktop Duplication image | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\capture-diagnostics\20260424-094950-capture-methods\images\DXGIDesktopDuplication.bmp` |
| Desktop Duplication JSON | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\capture-diagnostics\20260424-094950-capture-methods\images\DXGIDesktopDuplication.json` |
| `Ok` / `Usable` | `true` / `true` |
| Capture attempt count | `3` |
| Selected attempt | `2` |
| Size | `2560 x 1440` |
| Black ratio | `0.0015201822916666666` |
| Content black ratio | `0.0015574776785714285` |
| Content luma stddev | `92.57801462977272` |
| Source texture format | `B8G8R8A8_UNorm` |
| Output | `\\.\DISPLAY1`, `RawRect { Left = 0, Top = 0, Right = 2560, Bottom = 1440 }` |
| Protected content masked out | `false` |

### Updated live decision

The visual truth gate is **currently restored** for no-input screenshots. Projection sampling can resume using screenshot-gated states, but the next run should still keep the safety rule: no clicks/casts/mailbox interactions, and any hover/zoom/movement state labels must be visually confirmed by the newly usable capture path.

## Follow-up — screenshot-gated capture helper integration

The restored Desktop Duplication visual gate was wired into the tooltip/nameplate capture helper so future state captures can fail closed when the screenshot is black/unusable.

| Item | Result |
|---|---|
| WGC wrapper | `C:\RIFT MODDING\RiftReader\scripts\capture-rift-window-wgc.ps1` now supports `-RequireUsable`. |
| Capture tool | `C:\RIFT MODDING\RiftReader\tools\rift-window-capture\Program.cs` now supports `--require-usable` and exits non-zero when the frame is mechanically captured but unusable. |
| Hover/nameplate helper | `C:\RIFT MODDING\RiftReader\scripts\capture-tooltip-hover-diff.ps1` now supports `-CaptureScreenshot`, `-RequireUsableScreenshot`, and `-ScreenshotAttempts`. |
| State artifact | Each captured state can now include `states\<state>\screenshots\<state>.bmp` plus `<state>.capture.json`. |
| Safety | The screenshot path uses no mouse, keyboard, clicks, casts, focus changes, or movement. |

### Smoke validation

| Item | Value |
|---|---|
| Run root | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-095431-screenshot-gate-smoke` |
| Screenshot capture record | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-095431-screenshot-gate-smoke\states\capturetest\screenshots\capturetest.capture.json` |
| Screenshot output | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-095431-screenshot-gate-smoke\states\capturetest\screenshots\capturetest.bmp` |
| Candidate memory smoke | Read `16` bytes from `0x12CFC40B7C8` successfully. |
| Helper result | Completed successfully with `-CaptureScreenshot -RequireUsableScreenshot -ScreenshotAttempts 3 -NonInteractive`. |

### Updated next-run command shape

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

Use this only once the operator-visible state is prepared for each state label. The helper still does not control input; it only captures/read-scans after the operator confirms the state.

## Follow-up — analyzer visual-gate reporting

The analyzer now consumes screenshot-gate artifacts created by `capture-tooltip-hover-diff.ps1`, so projection runs report whether every sampled state had a usable visual capture.

| Item | Result |
|---|---|
| Analyzer change | `C:\RIFT MODDING\RiftReader\scripts\analyze-tooltip-hover-diff.ps1` now reads each sample's `files.screenshotCapture` and `files.screenshotOutput`. |
| New output | `diffs\screenshot-gate.json` with per-state capture existence, usability, capture method, content black ratio, and luma stddev. |
| Summary integration | `summary.json` and analyzer JSON output now include `screenshotGate.visualGateStatus`. |
| Backward compatibility | Older runs without screenshots now analyze successfully and report `visualGateStatus=not-captured`. |

### Validation

| Run | Result |
|---|---|
| Older mailbox run `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-045239-mailbox-tooltip-live` | Analyzer completed; `screenshotGate.visualGateStatus=not-captured`. |
| Screenshot smoke run `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-095742-screenshot-gate-analyzer-smoke` | Analyzer completed; `screenshotGate.visualGateStatus=passed`, `captureRecordCount=2`, `usableCount=2`. |

### Practical impact

Future tooltip/nameplate projection evidence can now be filtered on both memory-diff results and visual-gate truth. A run with good memory candidates but missing/black screenshots should stay candidate-only, while a run with `visualGateStatus=passed` is suitable for screenshot-backed follow-up analysis.

## Follow-up — analyzer fail-closed visual gate

The analyzer can now enforce screenshot-backed proof instead of only reporting it.

| Item | Result |
|---|---|
| Script | `C:\RIFT MODDING\RiftReader\scripts\analyze-tooltip-hover-diff.ps1` |
| New parameter | `-RequireVisualGate` |
| Pass condition | `screenshotGate.visualGateStatus` must be `passed`. |
| Failure behavior | Analyzer writes `diffs\screenshot-gate.json` and `summary.json`, then exits non-zero with the visual-gate status in the error. |
| Purpose | Prevents projection candidates from being promoted when screenshots are missing, black, or partial. |

### Validation

| Check | Result |
|---|---|
| Positive smoke | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-095742-screenshot-gate-analyzer-smoke` passed with `-RequireVisualGate`; `visualGateStatus=passed`. |
| Negative smoke | Older no-screenshot mailbox run failed as intended with `visualGateStatus=not-captured`. |
| Parser / build | PowerShell parse passed; `RiftWindowCapture.csproj` build passed with 0 warnings and 0 errors. |

### Recommended analyzer command for promoted projection runs

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

## Follow-up — operator runbook added

A concise current runbook was added for the screenshot-gated projection lane:

`C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-24-projection-screenshot-gated-runbook.md`

It captures the safe command order:

1. Confirm no-input visual capture works with `test-rift-window-capture-methods.ps1`.
2. Capture operator-confirmed states with `capture-tooltip-hover-diff.ps1 -CaptureScreenshot -RequireUsableScreenshot`.
3. Analyze with `analyze-tooltip-hover-diff.ps1 -RequireVisualGate`.

`docs\analysis\README.md` now links this as the current operator runbook for the `navigation` branch projection workflow.

## Follow-up — review/staging manifest added

A review manifest was added to classify what should be staged versus kept local before the branch is checkpointed:

`C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-24-navigation-projection-branch-review-manifest.md`

Current artifact footprint observed at manifest creation:

| Item | Value |
|---|---|
| Artifact roots checked | `artifacts\tooltip-projection`, `artifacts\window-capture` |
| File count | `239` |
| Approx size | `202.85 MB` |

Recommendation: stage source scripts, helper project source, and concise docs/runbooks first. Keep screenshot/BMP-heavy capture runs local unless durable proof artifacts are explicitly requested in git.

## Follow-up — generated capture roots ignored

To keep the branch reviewable, the generated capture roots are now ignored by `.gitignore`:

```text
artifacts/tooltip-projection/
artifacts/window-capture/
```

This removes the ~203 MB screenshot/diagnostic artifact bulk from normal `git status` without deleting local files. Durable artifacts can still be force-added selectively if needed.

## Follow-up — capture helper can run analyzer automatically

`capture-tooltip-hover-diff.ps1` now supports optional post-capture analysis:

| Parameter | Purpose |
|---|---|
| `-AnalyzeAfterCapture` | Runs `analyze-tooltip-hover-diff.ps1` after state capture completes. |
| `-AnalyzerBaselineStateRegex` / `-AnalyzerActiveStateRegex` | Controls baseline/active grouping for the analyzer. |
| `-AnalyzerBaselineLabel` / `-AnalyzerActiveLabel` | Labels analyzer output. |
| `-AnalyzerRequireVisualGate` | Adds fail-closed visual-gate enforcement to post-capture analysis. |

Smoke run:

| Item | Value |
|---|---|
| Run root | `C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-115020-post-capture-analysis-smoke` |
| Result | Capture completed and post-capture analysis passed with `screenshotGate.visualGateStatus=passed`. |
| Safety | No helper input, clicks, casts, focus changes, or movement. |

The screenshot-gated runbook now includes the one-command capture+analyze form.

## Follow-up — nameplate proof wrapper added

A thin wrapper was added for the real nameplate proof command:

`C:\RIFT MODDING\RiftReader\scripts\run-nameplate-projection-proof.ps1`

It forwards to the screenshot-gated capture helper with post-capture analysis and `-AnalyzerRequireVisualGate` enabled by default. Plan-only validation passed with `CandidateAddress=0x12CFC40B7D0` and `NameplateText="Atank of Sanctum"`.

## Follow-up — review manifest stage command refreshed

The review manifest stage command was refreshed after the later `.gitignore` and nameplate wrapper additions. It now includes:

- `.gitignore`
- `docs\analysis\2026-04-24-navigation-projection-branch-review-manifest.md`
- `scripts\run-nameplate-projection-proof.ps1`

The command still excludes generated capture roots by default.

## Follow-up — offline workflow validation script added

A no-live-input validation script was added:

`C:\RIFT MODDING\RiftReader\scripts\test-projection-screenshot-gate-workflow.ps1`

Validation run result:

| Check | Result |
|---|---|
| PowerShell parse | Passed for 6 projection helper scripts. |
| Capture project build | Passed. |
| Nameplate wrapper plan | Passed; screenshot and analyzer gates preserved. |
| Analyzer visual-gate smoke | Passed against existing local screenshot-gated smoke artifact. |

## Follow-up — CMD wrappers added

CMD wrappers were added for the projection helper scripts so they can be launched through the repo-standard `scripts\_run-pwsh.cmd` path.

Validation:

| Check | Result |
|---|---|
| `scripts\run-nameplate-projection-proof.cmd -PlanOnly -Json` | Passed and preserved screenshot/analyzer gates. |
| `scripts\test-projection-screenshot-gate-workflow.cmd -SkipBuild -SkipArtifactSmoke -Json` | Passed. |

## Follow-up — validator now covers CMD wrappers

`test-projection-screenshot-gate-workflow.ps1` now validates the `.cmd` wrapper layer as well as the PowerShell scripts.

Latest no-live-input validation with `-SkipBuild -SkipArtifactSmoke -Json` passed:

| Check | Result |
|---|---|
| PowerShell parse | Passed. |
| CMD wrapper inspection | Passed for 7 wrappers. |
| PowerShell nameplate wrapper plan | Passed. |
| CMD nameplate wrapper plan | Passed. |

## Follow-up — full offline validator pass

The full offline projection workflow validator was run without skips and returned `ok=true`.

| Check | Result |
|---|---|
| PowerShell parse | Passed for 6 scripts. |
| CMD wrapper inspection | Passed for 7 wrappers. |
| Capture project build | Passed. |
| PowerShell nameplate wrapper plan | Passed. |
| CMD nameplate wrapper plan | Passed. |
| Analyzer visual-gate smoke | Passed with `visualGateStatus=passed`. |
