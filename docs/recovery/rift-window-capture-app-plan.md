# RiftReader Screen Capture App Plan

**Status:** active implementation artifact for later coding resume
**Created:** 2026-05-14  
**Scope:** `tools/rift-window-capture` and repo-owned capture wrappers/docs  
**Current target stack:** C# / `.NET 10` low-level capture core, Python orchestration wrapper, thin `.cmd` or legacy `.ps1` convenience launchers only

---

## ✅ Implementation progress — 2026-05-14

The first implementation slice is now live-validated for exact-HWND
full-window capture, and the capture code has been split out of the original
monolithic `Program.cs`.

| Item | Status | Evidence |
|---|---|---|
| C#/.NET 10 core | Implemented | Thin dispatcher in `tools/rift-window-capture/Program.cs`; capture logic split under `Capture/`, `Backends/`, `Frames/`, `Targeting/`, `Artifacts/`, and related folders |
| Modular source layout | Implemented | `Program.cs` is now CLI dispatch only; reusable capture/report/artifact/backend code lives in focused C# files |
| Exact `--hwnd` targeting | Implemented | Safe invalid-HWND blocker tests plus live HWND `0xC0994` capture |
| Process-start validation | Implemented | `--expected-process-start-utc` matched `2026-05-13T16:17:56.2083705Z` |
| `--output-root` bundle | Implemented | Writes `manifest.json`, `logs/run.jsonl`, `summary.md`, and PNG |
| `inspect` / `validate` commands | Implemented | Live manifest validates with exit `0` |
| `benchmark` command | Implemented | 3-frame exact-HWND benchmark passed |
| Thin PowerShell launcher | Preserved | `scripts/capture-rift-window-wgc.ps1` only builds/runs and forwards arguments |
| Automated CLI tests | Added | `python scripts\test_rift_window_capture_cli.py` |
| Latest live capture bundle | Passed | `scripts/captures/rift-window-capture-live-exact-hwnd-20260514-031455-830` |
| Latest benchmark bundle | Passed | `scripts/captures/rift-window-capture-live-benchmark-20260514-032103-202` |
| Latest modular smoke bundle | Passed | `scripts/captures/rift-window-capture-modular-smoke-20260514-033313-843` |
| Python orchestration wrapper | Implemented | `scripts/capture_rift_window.py`; writes `controller-summary.json` and `controller-summary.md` |
| Thin `.cmd` launcher | Implemented | `scripts/capture-rift-window.cmd` calls Python and forwards arguments |
| Latest Python controller live smoke | Passed | `scripts/captures/rift-window-capture-python-live-smoke-20260514-034349-044` |
| Backend interface split | Implemented | `Backends/ICaptureBackend.cs`, `WgcCaptureBackend.cs`, and `DesktopDuplicationCaptureBackend.cs` |
| Latest backend-interface live smoke | Passed | `scripts/captures/rift-window-capture-backend-interface-live-smoke-20260514-034719-184` |
| Raw `.bgra` output | Implemented | `--emit-raw-bgra` writes `raw/full-window.bgra` and `raw/full-window.frame.json` |
| Latest raw `.bgra` live smoke | Passed | `scripts/captures/rift-window-capture-raw-bgra-live-smoke-20260514-040054-154` |

Safety boundary remained clean: no movement, no game input, no native
screenshot key, no CE, and no x64dbg.

Still deferred from the full plan: robust named crop profiles beyond
full-window, offline `convert`/`crop`/`diff` commands, and repeated capture
session mode.

---

## ✅ Goal

Build a **repo-standard RIFT game-window capture app** that is reliable enough
for live visual evidence, ChromaLink telemetry-strip capture, offline validation,
frame diffing, OCR/computer-vision preprocessing, and future navigation/debug
workflows.

The app should be:

- **Modular** — no giant single-file helper that becomes fragile later.
- **Scriptable** — every feature usable from CLI and Python automation.
- **Offline-friendly** — inspect, crop, diff, validate, and convert saved
  artifacts without live RIFT.
- **Timestamped and auditable** — every run writes machine-readable manifests,
  structured logs, and a compact human summary.
- **Capture-focused only** — no movement, no input, no memory reads, no debugger
  attachment.
- **Promoted when ready** — once validated, repo workflows should use it by
  default instead of letting it become another unused helper.

---

## 🧭 Core standard

| Layer | Standard | Reason |
|---|---|---|
| Low-level capture core | C# / `.NET 10` | Best fit for Windows capture APIs, process/HWND checks, and efficient frame handling |
| Primary backend | Windows.Graphics.Capture exact HWND/window | Best match for capturing only the RIFT window, including when not focused if compositor capture is valid |
| Fallback backend | DXGI Desktop Duplication + crop | Mature fallback when exact window capture fails or returns unusable frames |
| Internal frame format | Raw `BGRA32` | Native Windows/DirectX-friendly, fast for crops/diffs/OCR/CV |
| Human/debug artifact | PNG | Lossless, easy to view, good for reports |
| Legacy diagnostic artifact | BMP only when explicitly requested | Simple but large; should not be the repo standard |
| Automation brain | Python | Owns orchestration, JSON parsing, summaries, and fail-closed workflow decisions |
| PowerShell | Thin launcher / legacy leaf only | Avoid complex PowerShell orchestration |

---

## 🔎 Mature free/open-source tools to learn from

These projects should guide design decisions. Do **not** blindly copy code,
especially from GPL projects, without license review.

| Project | What to study | How it affects RiftReader |
|---|---|---|
| [Microsoft Windows.UI.Composition Win32 Samples](https://github.com/microsoft/Windows.UI.Composition-Win32-Samples) | Official desktop Win32/WPF/WGC sample patterns | Use as reference for correct Windows.Graphics.Capture desktop integration |
| [Microsoft Windows.Graphics.Capture docs](https://learn.microsoft.com/en-us/uwp/api/windows.graphics.capture) | WGC frame/session/frame-pool model | Keep backend behavior aligned with supported Windows APIs |
| [mmozeiko/wcap](https://github.com/mmozeiko/wcap) | Small, efficient WGC window/monitor recorder | Borrow philosophy: lean app, low CPU/memory, client-area/full-window distinction |
| [OBS Studio](https://github.com/obsproject/obs-studio) | Backend strategy, black-frame handling, game/window/display tradeoffs | Use as design reference for fallback and failure classification, not as copied code |
| [ShareX](https://github.com/ShareX/ShareX) | Mature C# screenshot workflow, capture modes, artifact UX | Use for workflow/artifact ideas; avoid GPL code copy |
| [screen_capture_lite](https://github.com/smasherprog/screen_capture_lite) | Capture abstraction, callbacks, frame-change design | Use as reference for modular backend interfaces and future repeated capture |
| [DXcam](https://github.com/ra1nty/DXcam) | High-FPS Desktop Duplication/WGC ideas, frame pacing, CV-friendly pipeline | Use as reference for benchmark/session mode and Python integration expectations |

---

## 🧱 Proposed code organization

Current implementation note: the 2026-05-14 modular split keeps the top-level
`Program.cs` as a thin command dispatcher, with the first-stage modules already
split into focused folders. The deeper target layout below remains the
direction for future backend/frame/crop/quality expansion.

Target directory:

```text
tools/rift-window-capture/
  RiftWindowCapture.csproj

  Cli/
    Program.cs
    CliOptions.cs
    CommandRouter.cs
    ExitCodes.cs

  Targeting/
    CaptureTarget.cs
    WindowResolver.cs
    ProcessIdentity.cs
    HwndParser.cs
    WindowGeometry.cs

  Backends/
    ICaptureBackend.cs
    CaptureBackendResult.cs
    WgcWindowCaptureBackend.cs
    WgcMonitorCaptureBackend.cs
    DxgiDesktopDuplicationBackend.cs

  Frames/
    BgraFrame.cs
    FrameMetadata.cs
    PixelFormatContract.cs
    FrameBufferPool.cs

  Artifacts/
    CaptureRunManifest.cs
    ArtifactWriter.cs
    PngFrameWriter.cs
    RawBgraFrameWriter.cs
    JsonlRunLogger.cs
    MarkdownSummaryWriter.cs

  Crops/
    CropProfile.cs
    CropParser.cs
    CropEngine.cs

  Quality/
    FrameQualityAnalyzer.cs
    BlackFrameDetector.cs
    FlatFrameDetector.cs
    TransparencyDetector.cs

  Timing/
    CaptureTiming.cs
    TimestampSource.cs

  Offline/
    RawBgraReader.cs
    FrameDiffEngine.cs
    ManifestValidator.cs
```

The existing helper can be migrated in stages. The first implementation does
not need every file at once, but new code should move toward this structure
instead of expanding a monolithic `Program.cs`.

---

## 🖥️ Capture backend strategy

| Priority | Backend | Expected use |
|---:|---|---|
| 1 | `wgc-window` | Exact RIFT HWND/window capture; preferred normal mode |
| 2 | `wgc-monitor` | Capture monitor then crop if exact window capture is unavailable |
| 3 | `dxgi-desktop` | Desktop Duplication fallback; useful for full desktop or monitor-region capture |
| 4 | `native-rift-screenshot` | Separate proof path only; sends RIFT screenshot key and is not the general visual capture standard |

Hard rules:

- Do not use GDI/`PrintWindow` as the default path for RIFT DirectX content.
- Do not send input from this app.
- Do not move the player.
- Do not attach CE/x64dbg.
- Do not call old screenshots “fresh” unless the manifest proves timestamp and
  target identity.

---

## 📦 Standard capture artifact bundle

Every successful or blocked run should create an output root like:

```text
capture-20260514-061530-8f3c2a/
  manifest.json
  summary.md
  logs/
    run.jsonl
  images/
    full-window.png
    client.png
    telemetry-strip.png
  raw/
    full-window.bgra
    full-window.frame.json
  debug/
    backend-report.json
    quality-report.json
    timing-report.json
```

Raw files should be optional by default because they are large. The internal
processing contract should still be Raw `BGRA32`.

---

## 🧾 Manifest contract

Minimum `manifest.json` fields:

```json
{
  "schema": "rift-window-capture-manifest/v1",
  "runId": "capture-20260514-061530-8f3c2a",
  "status": "passed",
  "startedAtUtc": "2026-05-14T06:15:30.100Z",
  "endedAtUtc": "2026-05-14T06:15:30.420Z",
  "target": {
    "pid": 2928,
    "hwnd": "0xC0994",
    "processName": "rift_x64",
    "processStartUtc": "2026-05-13T16:17:56.208370Z",
    "windowTitle": "RIFT"
  },
  "backend": {
    "requested": "wgc-window",
    "actual": "wgc-window",
    "fallbackUsed": false
  },
  "frame": {
    "pixelFormat": "BGRA32",
    "width": 641,
    "height": 391,
    "strideBytes": 2564,
    "orientation": "top-down"
  },
  "timing": {
    "requestedAtUtc": "2026-05-14T06:15:30.150Z",
    "acquiredAtUtc": "2026-05-14T06:15:30.230Z",
    "writtenAtUtc": "2026-05-14T06:15:30.300Z",
    "requestToAcquireMs": 80,
    "requestToWriteMs": 150
  },
  "quality": {
    "usable": true,
    "blackPixelRatio": 0.005,
    "lumaStdDev": 39.94,
    "transparentPixelRatio": 0.0
  },
  "safety": {
    "movementSent": false,
    "inputSent": false,
    "reloaduiSent": false,
    "screenshotKeySent": false,
    "cheatEngineUsed": false,
    "x64dbgAttached": false
  },
  "artifacts": {
    "summaryMarkdown": "summary.md",
    "runLogJsonl": "logs/run.jsonl",
    "fullWindowPng": "images/full-window.png",
    "fullWindowRaw": "raw/full-window.bgra"
  },
  "blockers": [],
  "warnings": []
}
```

---

## 🧰 CLI command set

### Canonical Python controller

Use Python as the repo workflow entry point when a capture run needs durable
controller evidence around the C# tool invocation:

```powershell
python .\scripts\capture_rift_window.py capture `
  --hwnd 0xC0994 `
  --pid 2928 `
  --expected-process-start-utc 2026-05-13T16:17:56.208370Z `
  --output-root scripts\captures\rift-window-capture-python-20260514 `
  --emit-png `
  --emit-raw-bgra `
  --crop full-window `
  --require-usable `
  --json
```

Safe command-plan/self-test examples:

```powershell
python .\scripts\capture_rift_window.py --dry-run --hwnd 0x1 --json
python .\scripts\capture_rift_window.py --self-test --no-build --json
```

The Python controller writes `controller-summary.json` and
`controller-summary.md` beside the native C# capture manifest. The thin
`scripts\capture-rift-window.cmd` launcher only calls Python and forwards
arguments.

### `capture`

Single capture run.

```powershell
RiftWindowCapture.exe capture `
  --pid 2928 `
  --hwnd 0xC0994 `
  --expected-process-start-utc 2026-05-13T16:17:56.208370Z `
  --backend wgc-window `
  --fallback dxgi-desktop `
  --output-root scripts\captures\rift-window-capture-20260514-061530 `
  --crop full-window `
  --crop telemetry-strip `
  --emit-png `
  --emit-raw-bgra `
  --require-usable `
  --json
```

### `benchmark`

Measure real capture latency and repeated frame performance.

```powershell
RiftWindowCapture.exe benchmark `
  --pid 2928 `
  --hwnd 0xC0994 `
  --frames 30 `
  --backend wgc-window `
  --output-root scripts\captures\capture-benchmark-20260514 `
  --json
```

### `crop`

Generate crops from existing raw/full-frame artifact.

```powershell
RiftWindowCapture.exe crop `
  --manifest scripts\captures\run\manifest.json `
  --profile telemetry-strip `
  --emit-png `
  --json
```

### `convert`

Convert raw `BGRA32` to PNG offline.

```powershell
RiftWindowCapture.exe convert `
  --raw raw\full-window.bgra `
  --metadata raw\full-window.frame.json `
  --png images\full-window.png `
  --json
```

### `diff`

Compare two frames offline.

```powershell
RiftWindowCapture.exe diff `
  --before run-a\raw\full-window.bgra `
  --after run-b\raw\full-window.bgra `
  --metadata run-a\raw\full-window.frame.json `
  --json
```

### `inspect`

Read a manifest and summarize target, quality, timing, and artifacts.

```powershell
RiftWindowCapture.exe inspect --manifest run\manifest.json --json
```

### `validate`

Validate that an artifact bundle is internally consistent.

```powershell
RiftWindowCapture.exe validate --manifest run\manifest.json --json
```

---

## 🪵 Logging and error system

Every run should write:

- Console JSON when `--json` is provided.
- `manifest.json` for durable run state.
- `logs/run.jsonl` for event stream.
- `summary.md` for human review.

Example JSONL events:

```json
{"tsUtc":"2026-05-14T06:15:30.123Z","level":"info","event":"target.resolve.start","pid":2928,"hwnd":"0xC0994"}
{"tsUtc":"2026-05-14T06:15:30.155Z","level":"info","event":"backend.selected","backend":"wgc-window"}
{"tsUtc":"2026-05-14T06:15:30.241Z","level":"info","event":"frame.acquired","width":641,"height":391,"strideBytes":2564}
{"tsUtc":"2026-05-14T06:15:30.287Z","level":"info","event":"artifact.written","path":"images/full-window.png"}
```

Error object contract:

```json
{
  "stage": "frame.acquire",
  "code": "wgc-timeout",
  "message": "No frame was received before timeout.",
  "exceptionType": "TimeoutException",
  "backend": "wgc-window",
  "recoverable": true
}
```

Exit codes:

| Code | Meaning |
|---:|---|
| `0` | Completed successfully |
| `1` | Unexpected failure |
| `2` | Known safe blocker, such as target mismatch, timeout, or unusable frame |
| `64` | Bad CLI usage |

---

## ✂️ Crop profiles

Built-in crop profiles should be named and manifest-recorded.

| Profile | Purpose |
|---|---|
| `full-window` | Complete captured window/frame |
| `client` | Client area if detectable |
| `telemetry-strip` | ChromaLink / addon telemetry extraction |
| `top-left` | Debug/probe area |
| `center` | Player/world visual checks |
| `chat` | Optional UI/chat validation |
| `minimap` | Optional navigation visual work |
| `custom:x,y,w,h` | Script-specified crop |

The crop command must record source frame identity and exact rectangle in the
manifest so later analysis can reproduce it.

---

## ⚡ Performance best practices

| Practice | Reason |
|---|---|
| Reuse D3D device/context inside a run/session | Avoid avoidable startup overhead |
| Add future `serve` or `session` mode | Avoid multi-second one-shot helper startup for repeated captures |
| Use pooled buffers | Reduce GC churn |
| Treat PNG as output artifact, not internal processing format | PNG encoding adds latency |
| Record request/acquire/write timestamps separately | Distinguishes capture latency from disk/write latency |
| Support `benchmark` command | Prevents guessing about capture speed |
| Fail closed on black/flat/transparent frames when requested | Avoids false validation |
| Keep fallbacks explicit and logged | Prevents silent backend drift |

Future persistent mode example:

```powershell
RiftWindowCapture.exe serve --pid 2928 --hwnd 0xC0994 --stdio-jsonl
```

Python could then send JSON commands without restarting the .NET process for
every frame.

---

## 🧪 Validation plan

| Stage | Validation |
|---|---|
| Build | `dotnet build tools\rift-window-capture\RiftWindowCapture.csproj` |
| CLI parse | Unit tests for `--pid`, `--hwnd`, `--backend`, `--crop`, bad args |
| Targeting | Unit tests for HWND parse, process-start mismatch, title mismatch |
| Frame contract | Tests for BGRA metadata, stride, orientation, dimensions |
| Artifact writing | Tests for manifest JSON, JSONL log, PNG, optional raw |
| Quality gate | Tests for all-black, flat, transparent, usable frames |
| Offline commands | Convert/crop/diff/inspect/validate against fixture frames |
| Live smoke | Exact RIFT HWND capture with `--require-usable` when live target is available |
| Wrapper | Python wrapper `--dry-run` and one live smoke when approved |
| Promotion check | Existing workflows call canonical wrapper instead of ad-hoc capture code |

---

## 🚦 Implementation stages

| Stage | Deliverable | Notes |
|---:|---|---|
| 1 | Add/confirm explicit `--hwnd` targeting | Must fail closed on wrong or missing target |
| 2 | Add process identity checks | Include process start UTC to prevent stale PID logic |
| 3 | Add `--output-root` bundle mode | Manifest/log/summary paths become stable |
| 4 | Add structured JSONL logger | Timestamp every major stage |
| 5 | Introduce `BgraFrame` contract | Normalize all backends to Raw `BGRA32` internally |
| 6 | Add PNG writer | Default human/debug artifact |
| 7 | Add optional raw `.bgra` writer | Useful for offline crop/diff/CV |
| 8 | Add crop profiles | Especially `full-window`, `client`, and `telemetry-strip` |
| 9 | Add `benchmark` command | Measure actual capture latency and repeated capture cost |
| 10 | Add offline commands | `inspect`, `validate`, `convert`, `crop`, `diff` |
| 11 | Add Python wrapper | Repo workflow calls Python; C# remains capture engine |
| 12 | Promote in docs/current truth | Make this the default capture standard |

---

## 📌 Promotion rules

The helper is **not promoted** merely because it exists.

Promote it only after:

1. C# project builds.
2. One exact-HWND live RIFT capture passes quality gate.
3. `manifest.json`, `logs/run.jsonl`, and `summary.md` are written.
4. PNG artifact is viewable and tied to the manifest.
5. `--require-usable` blocks bad/black/flat frames.
6. Python wrapper exists or is clearly planned as the canonical entry point.
7. Existing docs say this is the standard full-window capture helper.
8. At least one repo workflow uses it instead of an ad-hoc screenshot path.

Canonical future wording:

> Use `scripts/rift_window_capture.py` for full RIFT game-window capture. Do not
> create ad-hoc PrintWindow/GDI/MCP/screenshot helpers unless the canonical
> helper fails and the failure is recorded in the run manifest.

---

## ✅ Top 10 recommended next coding actions

| # | Action | Why |
|---:|---|---|
| 1 | Keep this plan as the resume anchor | Prevents re-planning from scratch |
| 2 | Add explicit `--hwnd` support to the current C# helper | Exact window targeting is the first reliability requirement |
| 3 | Add process-start validation | Prevents stale PID/HWND mistakes |
| 4 | Add `--output-root` bundle mode | Makes every capture resumable |
| 5 | Add `manifest.json` and `logs/run.jsonl` | Creates durable evidence |
| 6 | Add `BgraFrame` model | Establishes Raw `BGRA32` as internal standard |
| 7 | Add PNG output as default human artifact | Better than BMP for normal debug/reports |
| 8 | Add named crop profiles | Supports full-window and ChromaLink-specific workflows |
| 9 | Add `benchmark` command | Measures real speed instead of guessing |
| 10 | Promote wrapper/docs after validation | Ensures the helper actually gets used |

---

## Resume prompt

Use this to resume coding later:

```text
Resume RiftReader screen capture app work from
docs/recovery/rift-window-capture-app-plan.md.

Start with the smallest safe implementation slice:
1. inspect current tools/rift-window-capture project,
2. add explicit --hwnd and process-start validation if missing,
3. add output-root manifest/log bundle,
4. preserve existing wrapper compatibility,
5. build/test,
6. summarize exact changed files and validation.

Do not send game input, do not move the player, do not use CE/x64dbg, and do
not promote the helper as canonical until live exact-HWND capture plus manifest
validation pass.
```
