---
state: historical
as_of: 2026-04-17
---

# Native Debug-Scanning Branch Handoff (2026-04-17)

## Scope

This handoff freezes the current state of the **native debug-scanning /
trace-worker feature branch** for:

- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader`

The branch goal is to add a **bounded, opt-in, hardware-breakpoint-only native
trace lane** without changing the reader's default read-only behavior.

This report also captures a short evidence note from the same session on the
separate question of **RIFT engine lineage**, because that research affects how
future reverse-engineering work should phrase engine assumptions.

## Snapshot metadata

| Field | Value |
|---|---|
| State | `historical` |
| As of | `2026-04-17` |
| Report date | `2026-04-17` |
| Game update/build date | unknown |
| Branch | `scanner-with-debug` |
| Worktree | `C:\RIFT MODDING\RiftReader` |
| Input mode | repo file edits + local CLI validation + web source review; no live game attach |
| Validation status | partial working |

## Commands run

```powershell
git status --short --branch
git diff --stat
dotnet build 'C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj'
dotnet run --project 'C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj' -- --debug-trace-summary --trace-directory . --json
dotnet run --project 'C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj' -- --process-name definitely-not-a-rift-process --debug-trace-instruction --debug-address 0x1234 --debug-disable-stack-capture --debug-disable-memory-windows --debug-disable-follow-up-suggestions --json
```

## Artifacts checked

- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Cli\ReaderOptions.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Cli\ReaderOptionsParser.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Program.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Memory\ProcessMemoryReader.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Memory\ProcessMemoryRegion.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Formatting\DebugTraceSummaryTextFormatter.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugTraceContracts.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugTraceNdjsonLoader.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugTracePackageLoader.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugTraceRequestBuilder.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugTraceWorker.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugWindowsNativeMethods.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj`
- `C:\RIFT MODDING\RiftReader\docs\recovery\focused-postmessage-discovery-prompt.json` (unrelated existing untracked worktree file; not part of this feature)

## Files touched this pass

| File | Reason |
|---|---|
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Cli\ReaderOptions.cs` | Added public debug modes/options and modular capability-disable switches |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Cli\ReaderOptionsParser.cs` | Added parser/validation for native debug modes, worker mode, and summary mode |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Program.cs` | Added debug dispatch, worker spawning, and offline summary integration |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Memory\ProcessMemoryReader.cs` | Exposed process handle needed by the debug worker |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Memory\ProcessMemoryRegion.cs` | Added address helpers used by preflight and capture logic |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Formatting\DebugTraceSummaryTextFormatter.cs` | Added dedicated offline summary formatting for debug trace packages |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugTraceContracts.cs` | Added immutable request/capability/package contracts |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugTraceNdjsonLoader.cs` | Added NDJSON loader support for trace artifacts |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugTracePackageLoader.cs` | Added package inspection / summary loading |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugTraceRequestBuilder.cs` | Added request-building and capability wiring |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugTraceWorker.cs` | Added bounded out-of-process worker, package writing, analyzers, and cleanup flow |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugWindowsNativeMethods.cs` | Added Windows x64 native debug interop and hardware-breakpoint support |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj` | Added disassembly dependency (`Iced`) |

## Surviving anchors

| Area | Result | Notes |
|---|---|---|
| Branch isolation | working | Native debug work is isolated on `scanner-with-debug`; default reader behavior remains opt-in and additive |
| Build | working | `dotnet build` succeeded cleanly on `2026-04-17` |
| Public CLI surface | working | Instruction trace, memory write/access trace, player coord preset, summary mode, and internal worker mode all parse |
| Modular capability model | working | Public `--debug-disable-*` switches now control capture/analyzer modules instead of hardwiring them on |
| Out-of-process worker model | working at compile/smoke-test level | Main CLI writes a request and dispatches a hidden worker mode; no live Rift proof yet |
| Trace artifact model | working at compile/smoke-test level | Package manifest, debug manifest, NDJSON streams, module map, failure ledger, and analyzer outputs are implemented |
| Summary-mode rejection path | working | `--debug-trace-summary --trace-directory . --json` failed cleanly because the current directory is not a debug package |
| Clean invalid-process rejection | working | Instruction trace mode failed cleanly on a non-existent process name rather than falling through or crashing |
| Coord-write preset plumbing | partial | The preset is wired to existing coord-trace lineage resolution, but has not yet been validated live against Rift |

## Broken or drifted anchors

| Area | Result | Notes |
|---|---|---|
| Live Rift attach/detach | unverified | No manual acceptance run against the actual client yet |
| Real hardware-breakpoint hit capture | unverified | Execute/data watchpoint hits have not yet been proven against a live target or benign fixture process |
| Fixture-process integration coverage | missing | No dedicated x64 fixture target/tests yet for thread-create, timeout, target-exit, or abnormal worker exit cases |
| Execute-breakpoint before/after provenance | partial | Current slice captures rich context, but true post-execute destination confirmation is not yet the strongest possible form |
| Worktree cleanliness | mixed | `C:\RIFT MODDING\RiftReader\docs\recovery\focused-postmessage-discovery-prompt.json` remains as an unrelated untracked file and should not be mistaken for part of this branch's feature scope |

## Stale artifacts

- No stale repo analysis artifact was created by this pass.
- The unrelated untracked file below is **not** evidence for the native debug branch and should not be folded into future debug-scanning summaries:
  - `C:\RIFT MODDING\RiftReader\docs\recovery\focused-postmessage-discovery-prompt.json`

## Validation results frozen here

| Check | Result | Notes |
|---|---|---|
| `dotnet build` | passed | Clean build; `0 Warning(s)`, `0 Error(s)` |
| Debug summary smoke test | expected failure | `Debug trace package manifest 'C:\RIFT MODDING\RiftReader\package-manifest.json' was not found.` |
| Invalid-process debug smoke test | expected failure | `No running process was found with the name 'definitely-not-a-rift-process'.` |
| Live target / live Rift validation | not run | Still pending |

## Working design snapshot

### Public debug modes now present

- `--debug-trace-instruction`
- `--debug-trace-memory-write`
- `--debug-trace-memory-access`
- `--debug-trace-player-coord-write`
- `--debug-trace-summary --trace-directory <path>`
- internal worker mode: `--debug-worker --debug-request-file <path>`

### Public modular runtime controls now present

- `--debug-disable-register-capture`
- `--debug-disable-stack-capture`
- `--debug-disable-memory-windows`
- `--debug-disable-instruction-decode`
- `--debug-disable-instruction-fingerprint`
- `--debug-disable-hit-clustering`
- `--debug-disable-follow-up-suggestions`

### Package outputs now present

- `package-manifest.json`
- `debug-trace-manifest.json`
- `events.ndjson`
- `hits.ndjson`
- `markers.ndjson`
- `modules.json`
- `instruction-fingerprints.json`
- `hit-clusters.json`
- `follow-up-suggestions.json`
- `native-debug-failure-ledger.ndjson`

## Engine-lineage note from the same session

This was a separate research thread, but it is relevant to future RE framing.

### Current best wording

Use this wording unless stronger primary evidence is recovered:

> RIFT is **not a Unity game**. Official Trion material points to a broader
> proprietary / custom **Trion Platform** / **RIFT graphics engine** framing,
> while several secondary sources associate the game with **Gamebryo** or
> Gamebryo-related middleware.

### Primary-source context checked

- [Trion interview on "Trion Platform technology"](https://www.trionworlds.com/en/news/media-coverage/2011/10/interview-trion-worlds-launches-codename-red-door-initiative/)
- [Official RIFT multicore post referencing "RIFT's graphics engine"](https://www.trionworlds.com/rift/en/2016/06/01/true-multicore-support-is-now-live/)

### Secondary-source context checked

| Source | Claim | Confidence note |
|---|---|---|
| [Game Developer](https://www.gamedeveloper.com/business/ubisoft-licenses-gamebryo-for-guitar-game-i-rocksmith-i-) | Says Gamebryo had been used in games including Trion's new MMORPG Rift | strongest non-official source seen in this pass |
| [MobyGames: Rift](https://www.mobygames.com/game/50822/rift/) | Lists `Middleware: Gamebryo / Lightspeed / NetImmerse` | useful, but community-curated and middleware != total engine identity |
| [MobyGames: Rift series group](https://www.mobygames.com/group/10680/rift-series/) | Groups Rift under `Middleware: Gamebryo / Lightspeed / NetImmerse` | same caution as above |
| [ModDB: RIFT](https://www.moddb.com/games/rift) | Lists `Engine: Gamebryo` | helpful but non-authoritative |
| [Dexerto game database](https://www.dexerto.com/gaming/db/game/rift/) | Lists `Game Engine: Gamebryo` | weak metadata/aggregator signal |
| [[H]ardForum thread](https://hardforum.com/threads/rift-planes-of-telara-looking-good-mmorpg.1555061/post-1036700280) | Claims the game used Gamebryo toolsets rather than the Gamebryo engine | interesting counter-signal, but not primary proof |

### RE implication

Future reverse-engineering notes should **not** assume Unity conventions and
should also avoid overstating Gamebryo as a fully settled primary-source fact.
The safest working assumption is:

- **custom/proprietary Trion runtime, potentially with Gamebryo lineage or components**

## Branch / workflow authority

Current authority for native debug-scanning work during this pass:

- branch: `scanner-with-debug`
- worktree: `C:\RIFT MODDING\RiftReader`
- project root for implementation: `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader`

Workflow rule for the next agent:

- continue native debugger/scanner work on `scanner-with-debug`
- keep `main` as the stable baseline unless/until this feature is proven
- do **not** treat `C:\RIFT MODDING\RiftReader\docs\recovery\focused-postmessage-discovery-prompt.json` as part of the native debug feature scope

## Input mode and safety notes

- No live hardware-breakpoint attach was performed against the Rift client in this pass.
- No software breakpoints, code patching, page-guard tracing, or injection were used.
- No direct key stimulus, direct mouse stimulus, chat command injection, or `/reloadui` was used.
- Validation in this pass was limited to:
  - repo inspection
  - C# patching
  - local build validation
  - local CLI smoke tests on safe negative paths
  - web evidence review for the engine-lineage question

## Immediate next step

Add a **benign x64 fixture process + integration coverage** for the new worker
before depending on live Rift validation, then run one manual acceptance pass
with:

- `--debug-trace-player-coord-write`

against the live client to prove attach/detach safety, hit capture, and artifact
quality end to end.