# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# RiftReader — AI Developer Context

Read this file at the start of every session. It is the single authoritative reference for design decisions, verified reverse-engineering facts, anti-patterns, and coding rules. When this file conflicts with README.md or other docs, **this file wins** — those docs describe intent; this file describes what the code actually does.

> **Post-update warning (April 14, 2026):** parts of this file are a
> pre-update historical snapshot. The low-level reader baseline still works, but
> the source-chain / selector-owner / owner-components path drifted after the
> game update. Before trusting actor-orientation or camera-specific claims
> below, check:
>
> - `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
> - `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-post-update-anchor-drift-report.md`
> - `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-camera-workflow-branch-audit.md`

---

## 0. Build & Run Commands

**Solution file**: `RiftReader.slnx` (repo root)

```cmd
# Build
scripts\build-reader.cmd
# or: dotnet build RiftReader.slnx

# Run (pass args after --)
scripts\run-reader.cmd -- --process-name rift_x64 --read-player-current --json
# or: dotnet run --project reader\RiftReader.Reader\RiftReader.Reader.csproj -- <args>

# Deploy addon after Lua changes
scripts\deploy-addon.cmd

# Sync Cheat Engine probe scripts after reader probe changes
scripts\sync-cheatengine.cmd
```

There is no test project. Validate C# changes by building (`dotnet build RiftReader.slnx`) then running `scripts\read-player-current.cmd`.

---

## 1. System Identity

RiftReader is a **memory-based reader and reverse-engineering toolkit** for the RIFT game client. It uses a hybrid approach:
- **Lua addons** in the RIFT client export validated game state snapshots to disk (ReaderBridgeExport, RiftReaderValidator)
- **C# .NET 10 memory reader** attaches to the target Rift process and reads game data directly from memory
- **Cheat Engine integration** assists with reverse engineering by helping validate addresses and generate capture helpers

**The memory reader is the primary data source.** Addon exports serve as validation checkpoints. The reader discovers, validates, and reads player snapshots including position, orientation, health, level, and stat-hub relationships directly from game memory.

---

## 2. Non-Negotiable Design Decisions

These decisions are locked. Do not propose changing them without a full rationale. If a future task seems to require violating one, stop and flag it.

| Decision | Rationale |
|----------|-----------|
| Addon exports validate reader anchors | Addon data is Rift-API-backed ground truth; reader compares memory reads against it to confirm anchor validity. |
| Typed reader modes > generic memory dumps | Player snapshot readers (`--read-player-current`, `--read-player-orientation`, `--read-player-coord-anchor`) ship before building N-entity generic readers. |
| Cheat Engine for validation only | CE assists discovery and helps confirm addresses during reverse engineering. Reader does not depend on CE at runtime. |
| Owner graph and component structure | Historical pre-update model: player data was accessed through an owner object → container → selected-source component hierarchy. Revalidate after updates before assuming this remains stable. |
| Coordinate triplet as anchor | Player position (x/y/z as float triplet) is the primary stable anchor. Other fields are located relative to it. |
| Actor orientation from basis matrix | Historical pre-update model: player facing/yaw/pitch was derived from a 3×3 basis matrix (forward/up/right rows) at offsets `+0x60/+0x6C/+0x78` with a duplicate at `+0x94/+0xA0/+0xAC`. Revalidate after updates. |
| Stat-hub graph for identity and resources | Player stats (health, mana, level) accessed through a stable owner-component graph; stat hubs are shared and ranked by prevalence. |
| Module-local pattern validation | Instruction patterns discovered via CE are validated as module-local (within rift_x64.exe bounds) before being trusted for reader use. |
| No runtime CE dependency | Reader runs standalone. CE-assisted capture helpers are tooling, not runtime requirements. |

---

## 3. Source of Truth

When any two files disagree, use this priority order:

1. **The actual C# source code** — what the code does is reality
2. **This file (CLAUDE.md)** — verified facts from reverse engineering and code review
3. **README.md** — user-facing overview and command reference
4. **Script documentation** — helper scripts document their own workflows

### Historical Verified Addresses & Structure Offsets (last verified 2026-04-09)

These are **pre-April-14-2026** observations from a previously validated Rift
client session. Treat them as historical evidence until revalidated on the
updated client:

- **Player coord triplet**: Accessed via owner object → selected-source component at stable index 6
- **Actor basis matrix**: Forward row at `+0x60`, duplicate basis at `+0x94` (three 12-byte rows: forward/up/right)
- **Health / HealthMax / Level / Resource fields**: Located in stat-hub graph; ranked by shared hub prevalence
- **Owner container**: Stable across session (e.g., `0x1AEE411B280` in last validated session)
- **Selector owner path**: Traces from owner → selector object → selected-source index → target component

See saved trace artifacts in `scripts/captures/` for the last verified anchors (JSON format).

---

## 3A. Recovery Documentation System

When rebuilding after drift, stale artifacts, or partial corruption, start with:

- C:\RIFT MODDING\RiftReader\docs\recovery\README.md
- C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md
- C:\RIFT MODDING\RiftReader\docs\recovery\rebuild-runbook.md
- C:\RIFT MODDING\RiftReader\docs\recovery\artifact-tiers.md

These are the repo-owned rebuild documents. Historical handoff docs are background context only unless the recovery docs explicitly send you there.

---
## 4. Verified RIFT API Facts (Addon Layer)

**ALWAYS search before using any RIFT API.** These facts were verified against `seebs.net` and `rift.mestoph.net` as of 2026-04-09. Re-verify if you have any doubt.

### Verified ✅

#### Unit APIs

| API | Returns / Notes |
|-----|----------------|
| `Inspect.Unit.Lookup("player")` | Unit ID string of player, or nil |
| `Inspect.Unit.Lookup("player.target")` | Unit ID string of current target, or nil |
| `Inspect.Unit.Detail(unitId)` | Table with unit details (see fields below) |
| `Inspect.Unit.List()` | Table of visible unit IDs (keys only, values are nil) |
| `Inspect.Unit.Castbar(unitId)` | Table with cast info: `.active`, `.abilityName`, `.duration`, `.remaining`, `.channeled`, `.uninterruptible`, `.progressPct`, `.text` |

#### Inspect.Unit.Detail Fields

| Field | Type | Notes |
|-------|------|-------|
| `.id` | string | Unit ID |
| `.name` | string | Display name |
| `.level` | number | Unit level |
| `.calling` | string | Calling (class archetype) |
| `.guild` | string | Guild name |
| `.relation` | string | Relation to player (ally, enemy, etc.) |
| `.role` | string | Combat role |
| `.player` | boolean | Is a player character |
| `.combat` | boolean | In combat |
| `.pvp` | boolean | In PvP |
| `.health` | number | Current health |
| `.healthMax` | number | Maximum health |
| `.absorb` | number | Absorb shield value |
| `.vitality` | number | Vitality stat |
| `.mana` / `.manaMax` | number | Mana resource |
| `.energy` / `.energyMax` | number | Energy resource |
| `.power` / `.powerMax` | number | Power resource |
| `.charge` / `.chargeMax` | number | Charge resource |
| `.planar` / `.planarMax` | number | Planar attunement |
| `.combo` | number | Combo points |
| `.zone` | string | Current zone name |
| `.locationName` | string | Sub-zone/location name |
| `.coordX` / `.coordY` / `.coordZ` | number | 3D coordinates |
| `.dead` | boolean | Is dead |

#### Buff APIs

| API | Returns / Notes |
|-----|----------------|
| `Inspect.Buff.List(unitId)` | Table of buff IDs (keys only) |
| `Inspect.Buff.Detail(unitId, buffIds)` | Table keyed by buff ID with `.name`, `.stack`, `.remaining`, `.debuff` |

#### Stat API

| API | Returns / Notes |
|-----|----------------|
| `Inspect.Stat()` | Table keyed by stat name (string keys, number values). Fields vary by class/build. |

#### System APIs

| API | Returns / Notes |
|-----|----------------|
| `Inspect.Time.Real()` | Realtime float clock (seconds since session start) |
| `Inspect.System.Secure()` | Boolean: true if in secure instance (raid, dungeon) |
| `Inspect.Mouse()` | Table with `.x`, `.y` screen coordinates |

#### Event APIs

| API | Returns / Notes |
|-----|----------------|
| `Command.Event.Attach(event, handler, name)` | Attaches event handler; name must be unique |
| `Event.System.Update.Begin` | Fires every frame |
| `Event.System.Update.End` | Fires every frame (after update) |
| `Event.System.Secure.Enter` | Fires when entering secure instance |
| `Event.System.Secure.Leave` | Fires when leaving secure instance |
| `Event.Unit.Detail.Zone` | Fires on zone change |
| `Event.Unit.Detail.Role` | Fires on role change |
| `Event.Unit.Detail.Level` | Fires on level change |
| `Event.Addon.Startup.End` | Fires after addon loads |
| `Event.Addon.SavedVariables.Load.End` | Fires when saved variables load |
| `Event.Addon.SavedVariables.Save.Begin` | Fires before saved variables save |

#### UI APIs

| API | Returns / Notes |
|-----|----------------|
| `UI.CreateContext(name)` | Creates UI context |
| `UI.CreateFrame(type, name, parent)` | Creates UI frame (types: "Text", "Frame", "RiftButton", "RiftWindow", etc.) |

#### Command APIs

| API | Returns / Notes |
|-----|----------------|
| `Command.Console.Display(channel, showPrefix, message, showInChat)` | Displays console message |
| `Command.Slash.Register(cmd)` | Registers slash command (returns table to insert handlers into) |

### Not exposed / unverified ⚠️

| Item | Status |
|------|--------|
| Player facing / yaw via Rift API | **NOT EXPOSED**. Derive from memory basis matrix or position deltas. |
| Direct memory addresses | UNVERIFIED until validated in live session. Use addon exports to verify. |
| `Inspect.Unit.Heading()` / `.Pitch()` | UNVERIFIED - not used in current addon code |
| `Inspect.Unit.Gear()` / `.GearScore()` | UNVERIFIED - not used in current addon code |
| `Inspect.Zone.ID()` / `Inspect.Map.ID()` | UNVERIFIED - not used in current addon code |

---

## 5. Anti-Patterns

Things that look reasonable but are wrong for this system. Don't do these.

- **Don't trust a single addon snapshot.** Always compare reader memory results against the latest ReaderBridge export before declaring an anchor valid.
- **Don't assume struct offsets are stable across game updates.** They shift. Validate anchors frequently and keep trace artifacts with session metadata.
- **Don't read floats directly from memory without validating precision.** Player coords are float32; validate against addon export comparisons before trusting the value.
- **Don't assume owner/component indices are stable across zone transitions or reloads.** Trace artifacts include selector path; re-verify after game transitions.
- **Don't collapse multiple stat hubs into a single lookup.** Health may come from one hub, mana from another, level from a third. Enumerate and rank by prevalence.
- **Don't skip the module-local pattern validation step.** Instructions must be within rift_x64.exe bounds. Out-of-module patterns are false positives.
- **Don't add secondary data sources without validating against the primary anchor.** If you read data X from memory, compare it against the latest addon export. Addon data is the ground truth.
- **Don't hardcode addresses.** Always read trace artifacts or rebuild the anchor on startup. Addresses shift between sessions.
- **Don't suppress nullable warnings without a comment.** `// NilRisk:` comment required explaining why.
- **Don't add runtime CE dependencies.** CE is a reverse-engineering aid, not a production requirement. Reader must work standalone.

---

## 6. Current State & Next Priorities

### Shipped ✅

- **Addon layer**: ReaderBridgeExport (exports ReaderBridge state), RiftReaderValidator (manual snapshots + history)
- **Memory reader CLI**: Process attachment, generic scans (string/int/float/pointer), ReaderBridge-assisted scans
- **Discovery modes**: Cheat Engine probe generation, module pattern scanning, pointer reference scanning
- **Typed reader modes**:
  - `--read-player-current` — Full player snapshot from memory (coord, health, level, etc.)
  - `--read-player-orientation` — Historical pre-update actor yaw/pitch path from the basis matrix; revalidation currently required
  - `--read-player-coord-anchor` — Validates coordinate write instruction and derives anchor details
  - `--read-target-current` — Full target snapshot from memory (coord, health, level, name, distance)
  - `--rank-stat-hubs` — Walks identity-component graph and ranks shared memory hubs by player-stat prevalence; optionally emits a CE probe script via `--cheatengine-stat-hubs`
- **Reverse-engineering tooling**: Cheat Engine workflow helpers, module-local pattern validation, stat-hub graph enumeration

### In Progress ⏳

- **Actor orientation key profiling** — Historical pre-update workstream; rerun required on the updated client
- **Live actor orientation capture** — Historical pre-update workflow until rerun on the updated client

### Next (v0.2.0)

- **Party member readers** — Extend target reader pattern to enumerate and read party members
- **Persistent anchor caching** — Cache validated owner paths and trace artifacts across sessions
- **Broader stat coverage** — Mana, energy, power, stat values
- **Combat state tracking** — Read in-combat flag and cooldown timers
- **UI-integrated reader** — In-game menu to trigger snapshots and view live data

### Not started (v0.3.0+)

- **Movement prediction** — Extrapolate player velocity from coord history
- **Pathfinding** — Simple follow behavior based on leader position
- **Auto-update detection** — Detect game updates and flag when anchors may be stale
- **Linux/Mac capture backends** — Non-Windows support

---

## 7. Coding Rules — Lua / Addon Layer (`addon/`)

- **Language**: Lua 5.1 only. No `bit` library. No external libraries.
- **ALWAYS verify RIFT API before use.** State uncertainty if unresolved.
  - `site:seebs.net rift [APIName]` or `rift.mestoph.net`
- All `Inspect.*` and `Command.*` calls wrapped in `pcall()`; check `ok` before using result.
- Nil-check all results before use.
- Minimize global state; prefer module-local variables.
- All saved-variable tables must be backward-compatible with prior addon versions.
- No magic numbers — use named config constants.
- Flag all nil-reference risks with `-- NilRisk:` comment before finalizing code.

---

## 8. Coding Rules — C# / .NET 10 (`reader/`)

- **Target**: .NET 10, C# 12, nullable enabled project-wide.
- No suppressed nullability warnings without `// NilRisk:` comment explaining why.
- All P/Invoke structs: explicit `[StructLayout]` with correct `Size` annotation.
- No `Thread.Sleep` in hot paths — use `async/await` or `CancellationToken`.
- `System.Text.Json` only — no Newtonsoft.Json.
- Immutable records for all data models (`init`-only properties).
- Constructor-injected dependencies — no static mutable state.
- Interface-based design — all major classes expose an interface.
- No `async void` — use `Task` or `Task<T>` throughout.
- All process memory reads must include bounds checks and null guards.
- Trace artifact JSON: use consistent schema. See `scripts/captures/` for examples.

---

## 9. Cheat Engine Helpers

Cheat Engine scripts live in `scripts/cheat-engine/` and are generated/refreshed via:

```powershell
C:\RIFT MODDING\RiftReader\scripts\sync-cheatengine.cmd
```

Key helpers:

- **Probe generation** — `--cheatengine-probe` generates Lua that attaches to a target process and enumerates candidate addresses
- **Smart family capture** — `smart-capture-player-family.cmd` uses directional next-scans (`changed`, `increased`, `decreased`) instead of relying on second exact-value scans
- **Selector owner trace** — Breaks on source-object load, captures owner chain, verifies against latest addon export
- **Owner graph walk** — Maps stable owner relationships (wrapper, backref, state children)
- **Stat-hub enumeration** — Traces stat-side graph and ranks shared hubs by component prevalence

Do not hand-edit generated CE Lua. Regenerate via sync-cheatengine whenever the reader probe changes.

---

## 10. Reverse-Engineering Workflow

### Quick Player Snapshot

```powershell
C:\RIFT MODDING\RiftReader\scripts\read-player-current.cmd
```

### Full Anchor Refresh (when addresses have drifted)

1. **Refresh addon state** — Move in game to trigger new ReaderBridge export
2. **Smart capture new family** — `smart-capture-player-family.cmd` to get fresh coord candidates
3. **Trace coord write** — `trace-player-coord-write.cmd` to capture the instruction
4. **Walk owner graph** — `capture-player-owner-graph.cmd` to map structure
5. **Read through new anchor** — `read-player-current.cmd -RefreshAnchor` to validate

### Long Session (No Updates)

Just run `read-player-current.cmd` repeatedly. Reader caches the best family and validates via addon exports.

---

## 11. Quick File Map

```
addon/
  ReaderBridgeExport/       Exports ReaderBridge.State to disk as Lua
  RiftReaderValidator/      Manual snapshots + rolling history

reader/
  RiftReader.Reader/
    Cli/                    Command-line interface and help (ReaderOptions, ReaderOptionsParser)
    Memory/                 Process attachment, memory read, bounds checks (ProcessMemoryReader)
    Processes/              Process/module discovery (ProcessLocator, ProcessModuleLocator)
    Scanning/               Memory scanners (string, int, float, pointer, signature, module pattern)
    AddonSnapshots/         Loaders for ReaderBridge and Validator saved-variable files
    CheatEngine/            CE probe script generation (CheatEngineProbeScriptWriter)
    Formatting/             Text/JSON output formatters, one per result type
    Models/                 Typed result records and reader logic (PlayerCurrentReader, PlayerOrientationReader, etc.)
    Program.cs              Top-level dispatch: checks options in priority order and routes to the correct Run* method

scripts/
  read-player-current.cmd               One-command player snapshot
  trace-player-coord-write.cmd          Capture coord-write instruction
  capture-player-owner-graph.cmd        Map owner relationships
  smart-capture-player-family.cmd       CE-assisted family confirmation
  profile-actor-orientation-keys.cmd    Test which keys turn the player
  capture-actor-orientation.cmd         Read live yaw/pitch from basis

docs/
  overview.md                           System overview
  cheat-engine-workflow.md              CE reverse-engineering guide
  addon-validation-spec.md              Addon snapshot contract
  reader-cli-ux.md                      CLI design notes
```

---

## 12. Shared Rules (Both Layers)

- No magic numbers — use named constants or existing config values.
- Match the style of the file being edited; don't reformat unrelated code.
- After any Lua change: validate syntax with `luac` and deploy with `deploy-addon.cmd`.
- After any C# memory-read change: build with `dotnet build RiftReader.slnx`, then validate via `read-player-current.cmd`.
- All addresses from reverse engineering: document in trace artifacts (JSON) with session metadata (date, client version if known, last-verified-by-addon timestamp).

---

## 13. Known Limitations & Gotchas

- **Struct offsets are session-specific**: They may shift between game updates or client restarts. Always validate new anchors against addon exports before trusting them.
- **Floating-point precision**: Player coords read from memory may have minor precision differences from addon-export floats due to rounding. Comparisons should use tolerance (`Math.Abs(a - b) < 0.01`).
- **Owner container indices are mode-dependent**: Selected source index may shift if player is in different zones or after combat transitions. Re-validate after major state changes.
- **No anti-cheat evasion**: This tool is for legitimate addon development and research. Do not use for cheating or against the Rift EULA.
- **Windows-only (for now)**: Reader uses Windows P/Invoke and Win32 APIs. Linux/Mac support is planned for v0.3.0+.

---

Last updated: 2026-04-09
