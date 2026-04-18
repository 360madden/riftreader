---
state: active
as_of: 2026-04-17
branch: scanner-with-debug
---

# Debug-Trace Progress and Live Attach Status (2026-04-17)

## Verdict

The native debug-trace branch is now materially stronger than the prior handoff:

- the worker can successfully attach to and trace a benign x64 fixture process
- fixture-backed integration tests now cover the memory-write and memory-access lanes
- the earlier interop/finalization failures are fixed
- live attach to `rift_x64` still fails immediately at `DebugActiveProcess`

This means the branch has moved from **compile/smoke only** to **real end-to-end proof on a controlled target**, while the live MMO-client attach question remains open.

## Scope of this pass

This pass continued the native debug-scanning work on:

- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader`

with focus on:

1. adding a benign x64 fixture process
2. adding integration coverage for the out-of-process debug worker
3. diagnosing and fixing runtime blockers revealed by that coverage
4. performing a minimal live attach smoke test against `rift_x64`

## Branch / workspace

| Field | Value |
|---|---|
| Branch | `scanner-with-debug` |
| Worktree | `C:\RIFT MODDING\RiftReader` |
| Primary project | `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj` |

## Main fixes made in this pass

### 1. Blittable native debugger interop

The first integration run exposed a runtime failure in the native debugger lane:

- `System.TypeLoadException`
- caused by managed array fields inside explicit/interop-sensitive debugger structs

The fix replaced those non-blittable fields with fixed-layout blittable fields in:

- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugWindowsNativeMethods.cs`

This removed the type-load failure and allowed `GetThreadContext` / `SetThreadContext` to work correctly against the fixture process.

### 2. Temp-file promotion after writer disposal

The next blocker was a finalization error:

- `"The process cannot access the file because it is being used by another process."`

Root cause:

- temp NDJSON artifact files were being promoted while their writers were still open

The fix narrowed the writer scope so the files are closed before promotion in:

- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugTraceWorker.cs`

### 3. Test harness output deadlock prevention

The initial test harness used synchronous `ReadToEnd()` after process exit wait, which risked blocking when the traced command emitted large JSON output.

The fix changed the harness to drain stdout/stderr asynchronously before final result collection in:

- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\Debugging\DebugTraceWorkerIntegrationTests.cs`

### 4. False missing-file warning cleanup

The worker was marking final manifest/package files as missing because the missing-file set was computed before those final files were written.

That accounting was corrected in:

- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugTraceWorker.cs`

## New coverage added

### Added projects

| Project | Purpose |
|---|---|
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.DebugFixture\RiftReader.DebugFixture.csproj` | benign x64 target for debugger attach / hardware breakpoint validation |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj` | xUnit integration coverage for debug-trace worker |

### Added fixture behavior

The fixture:

- allocates unmanaged memory
- repeatedly reads and writes a 32-bit value
- pre-jits helper methods
- emits a ready JSON file containing:
  - PID
  - process name
  - memory address
  - method entry addresses

This gives a stable, non-game target for proving attach/detach and hardware data-breakpoint behavior end to end.

### Added tests

The current committed integration suite proves:

| Test | Result |
|---|---|
| memory-write trace against fixture | passing |
| memory-access trace against fixture | passing |

An execute/instruction trace test was attempted during this pass but removed before commit because it timed out and would have left the suite red. That execute lane remains unproven.

## Validation completed

| Command | Result |
|---|---|
| `dotnet build "C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj"` | passed |
| `dotnet test "C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj" --no-build --logger "console;verbosity=minimal"` | passed |

Final test status at the end of this pass:

- 2 passed
- 0 failed

## Live attach smoke test

### Goal

Run the smallest bounded live attach attempt possible against the actual client:

- process: `rift_x64`
- mode: `--debug-trace-instruction`
- target: module-relative instruction from prior coord-trace artifact
- timeout: 2000 ms
- max hits: 1
- all optional capture/analyzer lanes disabled

### Target used

Source artifact:

- `C:\RIFT MODDING\RiftReader\scripts\captures\player-coord-write-trace.json`

Resolved target:

- `rift_x64.exe+0x932B3E`

### Live attempts in this pass

| Attempt | PID | Result |
|---|---:|---|
| live attach smoke | `16732` | failed |
| live attach smoke retry | `30752` | failed |

### Failure boundary

Both live attempts failed at the same API boundary:

- `DebugActiveProcess`
- Win32 error `87`
- message: `The parameter is incorrect.`

Observed status fields:

| Field | Value |
|---|---|
| Attach outcome | `attach-not-started` |
| Detach outcome | `not-attached` |
| Event count | `0` |
| Privilege state | `standard` |

### Current interpretation

This pass does **not** prove a specific named anti-cheat or protection product.

What it **does** show:

- the custom debugger worker is capable of end-to-end attach/trace on a benign target
- the same worker can enumerate and resolve the live game process normally
- the live process rejects debugger attach before any debug events are observed

Safest current wording:

- **normal Win32 native debugger attach is being rejected for `rift_x64` in the current environment**

Likely explanations still pending discrimination:

1. target-specific anti-debug / hardening gate
2. privilege / integrity mismatch because the worker is running non-elevated
3. environment/security-product interference

## Files added or materially changed in this pass

| File | Purpose |
|---|---|
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.DebugFixture\Program.cs` | benign x64 debug fixture |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.DebugFixture\RiftReader.DebugFixture.csproj` | fixture project |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj` | test project |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\AssemblyInfo.cs` | disables parallelization |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\Debugging\DebugTraceWorkerIntegrationTests.cs` | fixture-backed integration tests |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugWindowsNativeMethods.cs` | fixed debugger interop layout |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugTraceWorker.cs` | fixed writer lifetime / artifact promotion / manifest accounting |
| `C:\RIFT MODDING\RiftReader\RiftReader.slnx` | includes fixture + tests |

## Current state of the branch

| Area | Status | Notes |
|---|---|---|
| Public debug CLI parsing | working | previously added on this branch |
| Worker compilation | working | clean build |
| Fixture attach/detach | working | proven |
| Fixture memory-write breakpoint lane | working | proven by test |
| Fixture memory-access breakpoint lane | working | proven by test |
| Execute/instruction lane on fixture | partial | attempted, not proven |
| Live `rift_x64` attach | blocked | `DebugActiveProcess` fails with Win32 87 |

## Recommended next step

The highest-value next diagnostic step is:

- retry the same attach smoke from an **elevated** context, or
- add a dedicated `--debug-attach-smoke` mode so attach can be tested without breakpoint setup assumptions

That is the cleanest remaining way to distinguish:

- privilege/integrity mismatch
vs.
- target-specific anti-debug behavior

