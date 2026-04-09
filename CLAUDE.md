# RiftReader — AI Developer Context

Read this file at the start of every session. It is the single authoritative reference for design decisions, verified reverse-engineering facts, anti-patterns, and coding rules. When this file conflicts with README.md or other docs, **this file wins** — those docs describe intent; this file describes what the code actually does.

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
| Owner graph and component structure | Player data is accessed through a stable owner object → container → selected-source component hierarchy. Structure is hierarchical, not flat. |
| Coordinate triplet as anchor | Player position (x/y/z as float triplet) is the primary stable anchor. Other fields are located relative to it. |
| Actor orientation from basis matrix | Player facing/yaw/pitch derived from a 3×3 basis matrix (forward/up/right rows) at fixed offsets (`+0x60/+0x6C/+0x78` and duplicate at `+0x94/+0xA0/+0xAC`). |
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

### Verified Addresses & Structure Offsets (as of 2026-04-09)

These are live observations from the current Rift client session. They may shift between game updates or client sessions:

- **Player coord triplet**: Accessed via owner object → selected-source component at stable index 6
- **Actor basis matrix**: Forward row at `+0x60`, duplicate basis at `+0x94` (three 12-byte rows: forward/up/right)
- **Health / HealthMax / Level / Resource fields**: Located in stat-hub graph; ranked by shared hub prevalence
- **Owner container**: Stable across session (e.g., `0x1AEE411B280` in last validated session)
- **Selector owner path**: Traces from owner → selector object → selected-source index → target component

See saved trace artifacts in `scripts/captures/` for the last verified anchors (JSON format).

---

## 4. Verified RIFT API Facts (Addon Layer)

**ALWAYS search before using any RIFT API.** These facts were verified against `seebs.net` and `rift.mestoph.net` as of 2026-04-09. Re-verify if you have any doubt.

### Verified ✅

| API | Returns / Notes |
|-----|----------------|
| `Inspect.Unit.Detail("player")` | Table with `.health`, `.healthMax`, `.level`, `.calling` (string), `.combat` (bool), `.dead` (bool), `.mana`/`.manaMax`, `.energy`/`.energyMax`, `.power`/`.powerMax` |
| `Inspect.Unit.Lookup("player.target")` | Unit ID string of current target, or nil |
| `Inspect.Unit.Detail(unitId)` | Same table as above for any unit ID |
| `Inspect.Stat()` | Table keyed by stat name |
| `Inspect.Time.Real()` | Realtime float clock (seconds) |
| `Command.Event.Attach(event, handler, name)` | Attaches event handler; name must be unique |
| `Event.System.Update.Begin` | Fires every frame |
| `UI.CreateContext(name)` + `UI.CreateFrame()` | Standard UI frame creation |

### Not exposed / unverified ⚠️

| Item | Status |
|------|--------|
| Player facing / yaw via Rift API | **NOT EXPOSED**. Derive from memory basis matrix or position deltas. |
| Direct memory addresses | UNVERIFIED until validated in live session. Use addon exports to verify. |

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
  - `--read-player-orientation` — Actor yaw/pitch from basis matrix
  - `--read-player-coord-anchor` — Validates coordinate write instruction and derives anchor details
- **Reverse-engineering tooling**: Cheat Engine workflow helpers, module-local pattern validation, stat-hub graph enumeration

### In Progress ⏳

- **Actor orientation key profiling** — Testing which input keys actually turn the player; building a control-binding classification (actor-turn / no-turn / movement / mixed)
- **Live actor orientation capture** — Comparing before/after basis matrices to measure yaw/pitch/vector changes in response to input

### Next (v0.2.0)

- **Multiple entity readers** — Extend player snapshot reader to read target, party members
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
    Cli/                    Command-line interface and help
    Memory/                 Process attachment, memory read, bounds checks
    Formatting/             OutputFormatters (text, JSON, colorized output)
    Models/                 Data classes (PlayerSnapshot, OwnerGraph, etc.)

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
- After any C# memory-read change: test with `dotnet build` and `dotnet test`, then validate via `read-player-current.cmd`.
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
