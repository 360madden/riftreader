# Camera Discovery Handoff Document

**Date**: April 10, 2026
**Branch**: `feature/camera-orientation-discovery`
**Character**: Atank (Level 44), Thedeor's Circle
**Last session addresses**: Owner `0x1576A38AA10`, Selected-source `0x1577AC2FB60`, Container `0x1577AD9B540`

---

## 1. Objective

Find the memory offsets for **camera yaw**, **camera pitch**, and **camera distance** in the RIFT game client. The camera is independent from the player character's actor orientation -- the player can face north while the camera looks east. Actor orientation (yaw/pitch from basis matrix) is already shipped and working. Camera orientation is NOT exposed by any RIFT API and must be discovered through memory scanning.

The end goal is a `--read-camera-orientation` CLI mode in the C# reader, mirroring the existing `--read-player-orientation` mode.

---

## 2. What Has Been Proven

### Confirmed working (shipped)

- **Actor basis matrix at +0x60/+0x94** in the selected-source component reads actor yaw/pitch correctly. This is the `--read-player-orientation` mode. The basis is a 3x3 matrix with forward/up/right rows at 12-byte intervals. A duplicate copy lives at +0x94/+0xA0/+0xAC.
- **Keyboard input injection works** via `scripts/post-rift-key.ps1` using Win32 PostMessage. The A key turns the player left. The D key strafes right (does NOT turn the character).

### Confirmed NOT camera

- **RIFT API does NOT expose camera data.** Verified against seebs.net and rift.mestoph.net (CLAUDE.md section 4). No `Inspect.Unit.*` or `Inspect.Camera.*` API exists. Do not waste time on addon-based approaches.
- **Camera is NOT in the selected-source component (+0x0 to +0x800).** A full 2048-byte dump of the selected-source component was scanned before and after a ~185-degree player turn. Only the actor basis at +0x60/+0x94 changed. The range +0xB8 to +0x150 (originally hypothesized as camera) showed zero delta. The static basis at +0x7D0/+0x7DC/+0x7E8 also showed zero change on turn.
- **Mouse input CANNOT be injected** via PostMessage or SendInput from a non-foreground process. Camera rotation requires actual mouse movement or Cheat Engine manual work. This is a critical constraint for automated testing.

### Input key mapping (verified)

| Key | Effect |
|-----|--------|
| A | Turn player left (actor yaw changes) |
| D | Strafe right (actor yaw does NOT change, position changes) |
| W/S | Move forward/backward |
| Mouse horizontal | Rotate camera yaw |
| Mouse vertical | Tilt camera pitch |
| Mouse wheel | Zoom camera in/out (distance) |

---

## 3. Container Entry Scan Results

The player's owner object has a container (`0x1577AD9B540`) with **16 entries** (indices 0--15). Only entry 6 was previously explored (it is the selected-source). A full scan of all 16 entries was performed:

### Entries with actor basis copies (1, 2, 3, 6)

Entries 1, 2, 3, and 6 contain data at the standard +0x60/+0x94 offsets that changes when the player turns. Entry 6 is the selected-source (the "primary" component). Entries 1-3 appear to be secondary copies or interpolation targets.

Entry 3 also has a coord match at +0x88 (player position).

### Entry 4 -- minimal change, possible interpolation

Address: `0x1577AC2C120`. Had only a single changed value at +0x1D0 during turn tests. The Q68/Q100 fields contain pointers (`0x1577B142A10`, `0x1576FF33B90`) suggesting this is a more complex object, not a simple data component.

### Entries 12--15 -- position-tracking data

These entries (`0x1575264BEE0` through `0x1575264C000`) contain position triplets that are approximately 10 units from the player position and track player movement. Specifically:

- Position (7409.34, 859.12, 2937.58) at entry 15 +0x0A8 -- distance 13.7 from player
- Position (7418.19, 862.75, 2932.10) at entry 15 +0x0B4 -- distance 10.8 from player
- Position (7416.77, 865.75, 2940.08) at entry 15 +0x578 -- distance 5.6 from player
- Y values are 4.5 units below player -- could be an anchor/follow point

Entry 15 is particularly interesting (deep-scan performed, see `scripts/captures/deep-scan-entry15.json`):
- **Normalized vector at +0x338**: (-0.238, 0, -0.971), magnitude 1.0 -- this is a direction vector
- **Distance scalar at +0x094**: value 15.0 -- could be camera distance
- **Identity-like basis at +0x060**: (0,0,1), (0,1,0), (1,0,0) -- axis-aligned, possibly default/static

### Entries 0, 5, 7--11

No significant camera-like data found. Most contain garbage floats, pointers, or zeroes at the standard coordinate/orientation offsets.

---

## 4. Promising Leads (From Latest Agent Work)

### Lead A: Owner-state wrapper chain -> basis matrix at 0x1579115D0A0

The owner object at +0xD0 points to an **owner-state-wrapper** at `0x1577CB1F2D0`. Following this wrapper's pointer chain:

```
Owner +0xD0 -> 0x1577CB1F2D0 (owner-state-wrapper)
  +0x100 -> 0x1579115D0A0  (promising target)
  +0x188 -> 0x1578AA40570  (second copy, possibly interpolation)
```

The address `0x1579115D0A0` appears in the owner graph's BackrefAt100 field for the owner-state-wrapper nodes. This is reachable via a stable pointer chain: `owner +0xD0 -> wrapper +0x100 -> target`. The plan notes this target has a 3x3 basis matrix at +0xA0 with BOTH yaw and pitch that was observed to change. This is the **highest-priority lead** to validate.

The second address `0x1578AA40570` at wrapper +0x188 may be an interpolation or smoothed copy of the same data.

### Lead B: Entry 15 normalized vector at +0x338

The normalized vector (-0.238, 0, -0.971) at entry 15 +0x338 has magnitude 1.0 and a Y component of 0. This looks like a camera-forward direction projected onto the XZ plane. The implied yaw would be approximately 194 degrees (atan2(-0.238, -0.971)). Needs validation by reading this before and after camera rotation.

### Lead C: Entry 15 distance scalar at +0x094

Value of 15.0 at entry 15 +0x094 is consistent with a typical 3rd-person camera distance. Needs validation by reading before and after mouse wheel zoom.

### Lead D: Entry 4 direction vector with pitch

Entry 4 was noted to have a direction vector with pitch of approximately 46 degrees. Not enough data was gathered to confirm this tracks camera movement. Worth revisiting.

---

## 5. Scripts Created for Camera Discovery

### Discovery/scanning scripts (in `scripts/`)

| Script | Purpose |
|--------|---------|
| `capture-camera-snapshot.ps1` | Reads live component data for baseline |
| `scan-camera-candidates.ps1` | Scans component range for float candidates |
| `diff-scan-camera.ps1` | Differential scan -- reads before/after stimulus |
| `test-camera-stimulus.ps1` | Automated stimulus test (sends key, measures delta) |
| `test-camera-stimulus-with-memory.ps1` | Extended stimulus test with memory dump |
| `simple-camera-memory-test.ps1` | Simplified memory read for camera range |
| `test-camera-turn.ps1` | Before/after player turn comparison |
| `capture-camera-memory-dump.ps1` | Full memory dump of camera search range |
| `search-camera-global.ps1` | Global float search for camera-like values |
| `find-camera-by-yaw-scan.ps1` | Yaw value scanning approach |
| `find-camera-by-position.ps1` | Search by camera position coordinates |
| `auto-discover-camera-yaw.ps1` | Automated two-phase yaw discovery |
| `generate-camera-probe.ps1` | CE probe script generator for camera |
| `scan-container-entries.ps1` | Dumps all 16 container entries with analysis |
| `diff-container-entries.ps1` | Differential scan across all container entries |

### Input injection scripts (in `scripts/`)

| Script | Purpose |
|--------|---------|
| `post-rift-key.ps1` | Send keystroke to Rift via PostMessage |
| `post-rift-key.cmd` | Wrapper for post-rift-key.ps1 |
| `post-rift-command.ps1` | Send slash commands to Rift |
| `post-rift-command.cmd` | Wrapper for post-rift-command.ps1 |
| `post-rift-command-ahk.ahk` | AutoHotkey-based command input |

### Documentation (in `docs/`)

| File | Purpose |
|------|---------|
| `camera-orientation-discovery.md` | Full workflow with phases 1--5 |
| `camera-discovery-findings.md` | Key findings and revised approach |
| `camera-ce-discovery-procedure.md` | Cheat Engine manual discovery procedure |

### Capture artifacts (in `scripts/captures/`)

| File | Purpose |
|------|---------|
| `camera-discovery-session.md` | Session info and CE scanning steps |
| `deep-scan-entry15.json` | 2048-byte analysis of container entry 15 |
| `player-owner-components.json` | All 16 container entries with basic analysis |
| `player-owner-graph.json` | Owner object children (14 nodes) |
| `walk-owner-state-pointers.json` | Full pointer walk from owner and state record |

---

## 6. Dead Ends (Approaches That Failed)

### 1. Camera in selected-source component (+0xB8 to +0x150)

**Why it seemed plausible**: Actor basis is at +0x60/+0x94 in the same component, so camera might be nearby.
**Why it failed**: Full 88-byte differential scan showed zero change when player turned ~185 degrees. All float values in this range are static.

### 2. Camera at +0x7D0/+0x7DC/+0x7E8 (static basis)

**Why it seemed plausible**: Looks like a 3x3 basis matrix pattern (three 12-byte rows).
**Why it failed**: Values showed exactly zero delta after 185-degree turn. This is static/default data, not live camera state.

### 3. Camera at +0x0E4 (static position reference)

**Why it seemed plausible**: Contains a float value in the right range.
**Why it failed**: Confirmed static -- does not update on any movement or rotation.

### 4. Extended component range (+0x0 to +0x800)

**Why it seemed plausible**: Maybe camera is deeper in the component.
**Why it failed**: Only 10 offsets change during movement out of the full 2048-byte range, and all are coordinate copies at known positions (+0x48, +0x60, +0x6C, +0x78, +0x88, +0x94, +0xA0, +0xAC). No camera data anywhere in the component.

### 5. Mouse input injection via PostMessage/SendInput

**Why it seemed plausible**: Keyboard injection works via PostMessage.
**Why it failed**: RIFT uses DirectInput or raw input for mouse, which cannot be faked from another process. This means automated camera stimulus tests are impossible without physical mouse movement or a hardware-level input device.

### 6. RIFT API for camera

**Why it seemed plausible**: RIFT has a rich addon API with `Inspect.Unit.*`.
**Why it failed**: Verified against seebs.net and rift.mestoph.net -- no camera API exists. This is listed in CLAUDE.md section 4 as a confirmed non-exposure.

---

## 7. Next Steps

### Priority 1: Validate Lead A (owner +0xD0 -> wrapper +0x100 chain)

This is the most promising lead. The chain `owner +0xD0 -> 0x1577CB1F2D0 +0x100 -> 0x1579115D0A0` reportedly has a basis matrix at +0xA0 that shows both yaw AND pitch changes.

**To validate**:
1. Read 256 bytes from `0x1579115D0A0` (or re-derive the address from the owner chain since addresses are session-specific).
2. Have user manually rotate camera with mouse.
3. Read again and compute delta.
4. If basis matrix at +0xA0 changed proportionally to mouse movement, this is the camera.
5. Also check the second copy at `0x1578AA40570` (wrapper +0x188).

**Script approach**: Create a new script that walks `owner +0xD0` to get the wrapper, then reads wrapper `+0x100` to get the target, then dumps 512 bytes from the target. Run before/after manual mouse rotation.

### Priority 2: Validate entry 15 leads

Read entry 15 +0x338 (normalized vector) and +0x094 (distance scalar) before and after camera rotation. If the normalized vector rotates and the distance changes with zoom, entry 15 holds camera data.

### Priority 3: Cheat Engine manual search (fallback)

If leads A and B fail, use the Cheat Engine procedure documented in `docs/camera-ce-discovery-procedure.md`:
1. Attach CE to rift_x64.
2. Scan for unknown float, then rotate camera with mouse, then scan for "changed" values.
3. Repeat to narrow candidates.
4. Validate candidates by watching values during smooth camera rotation.

This requires the user to manually move the mouse in-game while CE is running.

### Priority 4: Implementation (once offsets found)

1. Create `CameraOrientationReader.cs` mirroring `PlayerOrientationReader.cs`.
2. Add `--read-camera-orientation` CLI option.
3. Create `CameraOrientationFormatter.cs`.
4. Save validated offsets to `scripts/captures/camera-orientation-offsets.json`.
5. Update CLAUDE.md section 3 with confirmed offsets.

---

## 8. Key Constraints and Session Notes

### Addresses are session-specific, offsets are stable

All absolute addresses (e.g., `0x1576A38AA10`) change every time the game client restarts. The **offsets within structures** are stable (e.g., actor basis is always at +0x60 from the selected-source address). The reader discovers the selected-source address dynamically at runtime via the ReaderBridge addon export.

### Owner graph structure (stable)

```
Owner (0x1576A38AA10)
  +0x0   -> vtable (0x7FF7691599E0)
  +0x8   -> linked-child (0x1577AD9A380)
  +0x78  -> container (0x1577AD9B540) -- holds 16 entries
  +0x80  -> name/label structure (0x1577AD9B5D8)
  +0xA0  -> linked-child (0x1577AC2F3E0), SourceAt8 = selected-source
  +0xA8  -> linked-child (0x1577AC2F478)
  +0xD0  -> owner-state-wrapper (0x1577CB1F2D0) *** CAMERA LEAD ***
    +0x100 -> 0x1579115D0A0 (candidate basis matrix at +0xA0)
    +0x188 -> 0x1578AA40570 (possible interpolation copy)
  +0x118 -> linked-child (0x1576A38AB40)
  +0x128 -> linked-child (0x1576A38ABC0)

Container (0x1577AD9B540) -- 16 entries
  [0]  0x1577AC2F5A0 -- zeroes
  [1]  0x1577AC2FAB0 -- actor basis copy
  [2]  0x1577AC2FAF0 -- actor basis copy
  [3]  0x1577AC2FB20 -- coord match at +0x88
  [4]  0x1577AC2C120 -- complex object (pointers at Q68/Q100), minimal change
  [5]  0x1577AC2F1E0 -- misc pointers
  [6]  0x1577AC2FB60 -- SELECTED-SOURCE (player position + actor basis)
  [7]  0x1577AC2FC80 -- misc
  [8]  0x1577AC2FCD0 -- misc pointers
  [9]  0x1577AC2FE00 -- misc
  [10] 0x1577AC2FE60 -- misc
  [11] 0x1577AC2FE90 -- misc pointers
  [12] 0x1575264BEE0 -- position tracking (~10 units from player)
  [13] 0x1575264BF50 -- position tracking
  [14] 0x1575264BF80 -- position tracking
  [15] 0x1575264C000 -- position tracking, normalized vector at +0x338, distance 15.0 at +0x094
```

### How to re-derive addresses in a new session

1. Run `scripts/read-player-current.cmd` to get the selected-source address.
2. The selected-source address is entry 6 in the container.
3. The container address is stored in `player-owner-components.json` (re-capture with the reader's `--read-player-current` mode).
4. The owner address is found via the selector trace (stored in `player-selector-owner-trace.json`).
5. From the owner, follow +0xD0 to reach the owner-state-wrapper, then +0x100 for the camera candidate.

### Build and validate

```cmd
dotnet build RiftReader.slnx
scripts\read-player-current.cmd
```

No test project exists. Validate by building and running against the live game client.

---

## 9. File Reference

### Critical source files for implementation

| File | Role |
|------|------|
| `reader/RiftReader.Reader/Models/PlayerOrientationReader.cs` | Pattern to follow for CameraOrientationReader |
| `reader/RiftReader.Reader/Models/PlayerCurrentReader.cs` | Full player snapshot reader |
| `reader/RiftReader.Reader/Models/PlayerOwnerComponentRanker.cs` | Owner graph walking logic |
| `reader/RiftReader.Reader/Cli/ReaderOptionsParser.cs` | CLI option registration |
| `reader/RiftReader.Reader/Program.cs` | Top-level dispatch |
| `reader/RiftReader.Reader/Formatting/` | Output formatters (one per result type) |

### Key capture artifacts

| File | Content |
|------|---------|
| `scripts/captures/player-owner-graph.json` | Owner structure with 14 children |
| `scripts/captures/player-owner-components.json` | 16 container entries |
| `scripts/captures/walk-owner-state-pointers.json` | Full pointer walk (large file) |
| `scripts/captures/deep-scan-entry15.json` | Entry 15 deep analysis |
| `scripts/captures/camera-discovery-session.md` | Session notes and CE steps |

---

## 10. Summary for New Agent

You are looking for the memory location where RIFT stores camera yaw/pitch/distance. The camera is independent from the player character's facing direction.

**What works**: Actor orientation from basis matrix at selected-source +0x60. Keyboard input via PostMessage.

**What does NOT work**: Mouse injection, any RIFT API for camera, any offset in the selected-source component.

**Best lead**: Owner object +0xD0 -> owner-state-wrapper +0x100 -> candidate object at 0x1579115D0A0 with a basis matrix at +0xA0. This was reported to show both yaw and pitch changes. Validate this first.

**Second lead**: Container entry 15 has a normalized direction vector at +0x338 and a distance scalar of 15.0 at +0x094.

**Fallback**: Manual Cheat Engine float search with user rotating the camera by hand.

**Constraint**: You cannot inject mouse input programmatically. Camera rotation requires the user to physically move the mouse or use Cheat Engine.
