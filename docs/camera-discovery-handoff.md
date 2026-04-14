# Camera Discovery Handoff - April 11, 2026

> **Superseded historical handoff:** keep this file for background only. The selected-source `+0xB8..+0x150` window and the old entry15 `+0x338/+0x094` lead are no longer the active workflow. Use `C:\RIFT MODDING\RiftReader\docs\camera-orientation-discovery.md` and `C:\RIFT MODDING\RiftReader\scripts\read-live-camera-yaw-pitch.ps1` for the current live path.

## STATUS: IN PROGRESS - Blocked

**Objective**: Find camera yaw/pitch/distance in RIFT memory.

---

## What WORKS (from prior agent)

1. **mouse_event rotates camera** - Win32 mouse_event with RMB held works to programmatically rotate camera
   - Script: `scripts/test-rmb-camera.ps1`
   - This enables automated stimulus testing

2. **Player orientation found** - Actor basis at selected-source +0x60/+0x94 gives player yaw/pitch (shipped)

3. **Selected-source address**: `0x1578D4F9910` (current session, needs re-validation)

---

## WHAT WAS TESTED (and ruled out)

| Lead | Status |
|------|--------|
| Selected-source +0xB8 to +0x150 | NOT camera - static data |
| Lead A: owner+0xD0 → wrapper+0x100 → basis | **ACTOR orientation**, NOT camera |
| Entry 15 +0x338 vector, +0x094 distance | **NOT TESTED** - high priority |
| Entry 4 direction vector with pitch | **NOT TESTED** - secondary priority |

---

## REMAINING LEADS TO TEST

### Priority 1: Entry 15 (container entry 15)

From prior session (addresses stale):
- Entry 15 at: `0x1575264C000` (must re-derive)
- +0x338: normalized direction vector (-0.238, 0, -0.971) - magnitude 1.0, looks like camera forward
- +0x094: distance scalar 15.0 - typical 3rd-person camera distance

**Validation needed**:
1. Find current session's container and entry 15
2. Read entry 15 +0x338 and +0x094 BEFORE camera rotate
3. Use mouse_event to rotate camera
4. Read again - vector should rotate, distance should change

### Priority 2: Entry 4

- Has pointers at Q68/Q100
- Prior session showed "direction vector with pitch ~46 degrees"

---

## BLOCKERS

1. **Owner structure not found** - Can't derive container/entries from selected-source
   - CE client returns 0 (not connected or autorun not installed)
   - Memory scan for container structure (entries+count+capacity pattern) failed
   - Need to restart RIFT or use manual CE

2. **Cache files may be stale** - `scripts/captures/` empty, no owner-component JSON

---

## NEXT AGENT STEPS

1. **Get fresh owner structure**:
   ```
   dotnet run --project reader/RiftReader.Reader/RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-current --json
   ```
   Or use Cheat Engine manual:
   1. Open CE → Attach to rift_x64
   2. Find player name "Atank" → Right-click → "Browse this memory region"
   3. Go backward ~0x1000 looking for vtable pointer pattern
   4. From there, find container at +0x78 (entries+count)

2. **Get container entries**:
   - From owner, read +0x78 → pointer to entries array
   - Read count at +0x78+8, entries at pointer
   - Should have 16 entries (indices 0-15)
   - Entry 15 is the last one

3. **Validate entry 15**:
   - Read entry15 +0x338 (3 floats = direction vector)
   - Read entry15 +0x094 (float = distance)
   - Run camera rotate test: `scripts/test-rmb-camera.ps1`
   - Read again - vector should change, distance may change

4. **If entry 15 fails**, try entry 4 (+0x68, +0x100)

---

## SCRIPTS AVAILABLE

| Script | Purpose |
|--------|---------|
| `scripts/test-rmb-camera.ps1` | Rotate camera via mouse_event |
| `scripts/cheatengine-exec.ps1` | Execute Lua in CE (needs connection) |
| `reader/RiftReader.Reader.csproj` | Memory scanning, capture |

---

## KEY FILES

- `docs/camera-discovery-handoff.md` - This file
- `scripts/test-rmb-camera.ps1` - Working camera control
- `scripts/captures/player-current-anchor.json` - Stale selected-source (0x1578D4F9910)

---

**Bottom line**: Entry 15 at +0x338/+0x094 is the highest-priority untested lead. Derive current session container → entry 15 → read these offsets before/after camera rotation.
