# AI Session Handoff - April 11, 2026

> **Superseded historical handoff:** this file predates the current live owner/source recovery and still points toward now-obsolete discovery paths. Use `C:\RIFT MODDING\RiftReader\docs\camera-orientation-discovery.md` for the active workflow.

## What I Did (Session Summary)

### Accomplishments

1. **Verified mouse_event WORKS for camera control**
   - Created `scripts/test-rmb-camera.ps1` - programmatic camera rotation
   - Win32 mouse_event with RMB held + move
   - This was the breakthrough from prior session

2. **Ran memory readers to get current state**
   - Got fresh player data: selected-source at `0x1578D4F9910`
   - Captured player signature family with 2 samples
   - Player: Atank, Level 44, Health 17027, Position (7410.34, 863.58, 2935.33)

3. **Tested float scan for camera distance**
   - Scanned for value 15.0 (typical camera distance)
   - Found 20 hits but all UI-related (tooltip anchors, etc.)

4. **Tested string scan for player name "Atank"**
   - Found 3 hits in identity records at 0x360440A0

### Failures

1. **Cheat Engine connection broken**
   - `scripts/cheatengine-exec.ps1` returns 0 always
   - CE autorun may not be installed or connected

2. **Owner structure not found**
   - Tried multiple scan approaches:
     - Scan for pointer to selected-source: 0 hits
     - Scan backward from selected-source: no container
     - Scan full memory for container pattern: not found
   - **Root cause**: New RIFT session, old addresses stale

3. **Can't derive entry 15**
   - Without owner, can't get container entries
   - Could not test the leads

### What Was Tested (ruled out)

| Test | Result |
|------|--------|
| Selected-source +0xB8 to +0x150 | NOT camera (prior session) |
| Owner+0xD0 → wrapper+0x100 | Actor orientation (NOT camera - prior session) |
| Scan for float=15.0 | UI anchors (not camera) |
| Scan for player name | Identity records (not owner) |

### Remaining Leads (UNTESTED)

1. **Entry 15** - Container entry 15 has:
   - +0x338: direction vector (-0.238, 0, -0.971) - magnitude 1.0
   - +0x094: distance 15.0
   - This is HIGHEST PRIORITY - needs testing

2. **Entry 4** - Has direction vectors with pitch

---

## What The Next AI Should Do

### Step 1: Get Fresh Owner Structure

Option A - C# Reader (if ReaderBridge available):
```
dotnet run --project reader/RiftReader.Reader/RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-current --json
```

Option B - Manual Cheat Engine:
1. Attach CE to rift_x64
2. Search string "Atank" → browse memory
3. Go backward ~0x1000 from name string
4. Look for pattern: [pointer to array][count][capacity]
5. That's the container

### Step 2: Get Container Entries

- From owner, read +0x78 = container pointer
- Read entries array, count should be 16
- Entry 15 is the last one

### Step 3: Test Entry 15

1. Read entry15 +0x338 (direction vector)
2. Read entry15 +0x094 (distance)
3. Run `scripts/test-rmb-camera.ps1` to rotate camera
4. Read again
5. IF values change → FOUND CAMERA!

### Step 4: Implement

If camera found:
- Create CameraOrientationReader.cs
- Add CLI flag --read-camera-orientation
- Update CLAUDE.md with offsets

---

## Key Files

| File | Purpose |
|------|---------|
| `docs/camera-discovery-handoff.md` | Main doc (updated) |
| `scripts/test-rmb-camera.ps1` | Working camera control |
| `scripts/cheatengine-exec.ps1` | CE execution (broken) |
| `scripts/captures/player-current-anchor.json` | Stale player anchor |

---

## Technical Notes

- mouse_event works: `mouse_event(MOUSEEVENTF_RIGHTDOWN)` → move → `mouse_event(MOUSEEVENTF_RIGHTUP)`
- RIFT uses DirectInput - cursor position ≠ camera input
- Owner structure: [vtable][child linked list][container at +0x78][...]
- Container: [entries pointer][count][capacity] - 16 entries
- Entry 15: position tracking + direction vector + distance

---

**BLOCKED BY**: Owner structure not found (session-specific addresses stale)

**RECOMMENDATION**: Restart RIFT and ReDoE (ReDiscover Everything) using the workflow above. Entry 15 +0x338/+0x094 is the most promising lead that was never tested.
