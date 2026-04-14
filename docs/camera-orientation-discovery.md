# Camera Orientation Discovery Workflow

## Overview
Camera yaw/pitch/distance are not exposed via the Rift API and must be discovered through memory scanning and stimulus testing. Camera is independent from actor orientation — the player character can face one direction while the camera looks another.

**Status**: Yaw verified live, pitch available via orbit derivation, direct pitch scalar still unresolved  
**Branch**: `feature/camera-orientation-discovery`  
**Key files**: 
- `scripts/test-camera-stimulus.ps1` — stimulus testing helper
- `scripts/read-live-camera-yaw-pitch.ps1` — current live yaw + derived pitch reader
- `scripts/find-live-camera-angle-candidates.ps1` — paired pitch/yaw candidate scanner
- `scripts/generate-camera-probe.ps1` — CE probe generator
- `scripts/captures/player-actor-orientation.json` — baseline component address (known)

---

## Latest Live Findings (April 13, 2026)

### Confirmed

- **Yaw is live in the selected-source basis**, not just actor state in theory.
  - Current live selected source: `0x1FDA0D13170`
  - Strong yaw rows remain the duplicated basis vectors:
    - `+0x60/+0x68/+0x78`
    - `+0x94/+0x9C/+0xAC`
- `scripts/test-camera-stimulus.ps1 -Stimulus mouse-yaw -Json` now produces real camera-only deltas:
  - yaw changes
  - pitch remains `0`
  - player coord delta remains `0`
- **Pitch is currently recoverable from orbit coordinates, not from a direct scalar.**
  - Best live source is the duplicated camera-orbit triplet in **entry 15**:
    - `+0xA8/+0xAC/+0xB0`
    - duplicate at `+0xB4/+0xB8/+0xBC`
  - Derive pitch from `(cameraCoord - playerCoord)` using `atan2(dy, horizontalDistance)`
  - `scripts/read-live-camera-yaw-pitch.ps1 -Json` is the current canonical live reader

### Important negative results

- A paired live scan across:
  - `selected-source`
  - `entry4`
  - `entry15`
  - then **all owner entries**
  - with scan windows up to **8 KB**
  did **not** find a credible direct pitch scalar in normal radians/degrees ranges.
- `selected-source +0x7D0` basis hypothesis did **not** validate live; those rows are zero in the current client.
- The only angle-like pitch-only candidate found in widened scans was:
  - `entry4 +0x1D0`
  - but repeated live trials showed it is **too noisy and not trustworthy**.

### Practical conclusion

- **Use direct yaw + derived pitch for now.**
- Do **not** treat `entry4 +0x1D0` as verified.
- The next real target is a **direct pitch scalar** or a direct camera basis outside the currently scanned owner-entry neighborhoods.

---

## Phase 1: Memory Layout Hypothesis

### Known Structure (from Actor Orientation)
```
SelectedSourceAddress = 0x1AEF0941250 (example, varies per session)

+0x48  Coord triplet (player position copy 1)
+0x60  Actor forward vector (basis row 1)
+0x6C  Actor up vector (basis row 2)
+0x78  Actor right vector (basis row 3)
+0x88  Coord triplet (player position copy 2)
+0x94  Actor forward vector (basis row 1, duplicate)
+0xA0  Actor up vector (basis row 2, duplicate)
+0xAC  Actor right vector (basis row 3, duplicate)
+0xB8  [Camera data likely starts here]
+0x150 [Camera search range ends]
```

### Camera Expected Structure (Revised)
Current live evidence suggests:
- **Yaw** is represented by the selected-source basis rows
- **Pitch** is recoverable from orbit position relative to the player
- **Distance** is also recoverable from the same orbit vector magnitude
- A **direct pitch scalar** has not yet been found in the nearby owner-entry neighborhoods

Search areas that have already been tested live:
- selected-source: up to **+0x2000**
- owner entries: up to **+0x2000**
- all entries paired against pitch up/down and yaw left/right stimulus

Result so far:
- strong yaw basis: **confirmed**
- orbit-position pitch: **confirmed**
- direct pitch scalar: **not yet confirmed**

---

## Phase 2: Cheat Engine Scanning

### Quick Start

1. **Open Rift process in Cheat Engine**
   ```powershell
   # Run Rift and get into world
   # Open Cheat Engine, attach to rift_x64.exe
   ```

2. **Get baseline component address**
   ```powershell
   scripts\read-player-current.cmd
   # Look for SelectedSourceAddress in output, e.g., 0x1AEF0941250
   ```

3. **Calculate camera search range**
   ```
   Camera start = SelectedSourceAddress + 0xB8
   Camera end = SelectedSourceAddress + 0x150
   Example: 0x1AEF0941250 + 0xB8 = 0x1AEF0941308
   ```

4. **Generate CE probe** (optional, for reference)
   ```powershell
   scripts\generate-camera-probe.ps1 -SelectedSourceAddress 0x1AEF0941250
   ```

### Manual Scanning Strategy

**For Camera Yaw Discovery:**
1. Face a known direction (e.g., north with actor yaw ≈ 0°)
2. Move mouse right (rotate camera right)
3. Scan memory at camera range for float values that increased (yaw angle)
4. Narrow to candidates with range ~0-360 (or 0-2π if radians)

**For Camera Pitch Discovery:**
1. Look straight ahead (camera pitch ≈ 0°)
2. Move mouse up (tilt camera up)
3. Scan for float values that became negative (pitch angle, convention varies)
4. Narrow to candidates with range ~-60 to +60 (degrees)

**For Camera Distance Discovery:**
1. Note current camera distance (in units)
2. Scroll mouse wheel to zoom in/out
3. Scan for float values that decreased/increased by ~5-20 units
4. Narrow to candidates with range ~5-100 (typical 3rd-person camera)

### Smart Family Capture (Advanced)

If available, use directional next-scans instead of exact-value:
1. **First scan**: All values in range
2. **Mouse movement** (yaw right): Next scan for "increased" values
3. **Mouse movement** (yaw left): Next scan for "decreased" values (must toggle from previous)
4. **Repeat** for pitch and distance

This quickly eliminates candidates that don't respond to input.

---

## Phase 3: Stimulus Testing (Automated Validation)

Once you have candidate addresses, validate them programmatically:

```powershell
# Test camera yaw response
scripts\test-camera-stimulus.ps1 -Stimulus mouse-yaw -Json

# Test camera pitch response
scripts\test-camera-stimulus.ps1 -Stimulus mouse-pitch -Json

# Test camera distance (zoom)
scripts\test-camera-stimulus.ps1 -Stimulus mouse-wheel -Json

# Test all stimuli
scripts\test-camera-stimulus.ps1 -Stimulus all -Json | ConvertFrom-Json -Depth 20
```

**Expected Results:**
- `mouse-yaw-right`: selected-source yaw basis changes while player coord remains stable
- `mouse-pitch-up`: entry15 orbit coordinates change while selected-source pitch remains flat
- `mouse-wheel-zoom-in`: orbit distance should change
- **Important**: player coordinates should remain ~stable during pure camera movement

**Current Note**: `scripts/test-camera-stimulus.ps1` is now useful for live yaw verification, but the current pitch source is better read through `scripts/read-live-camera-yaw-pitch.ps1`.

---

## Phase 4: Implementation (Once Addresses Found)

### Create CameraOrientationReader.cs

Once camera offsets are validated:

```csharp
// reader/RiftReader.Reader/Models/CameraOrientationReader.cs
public static CameraOrientationReadResult Read(
    ProcessMemoryReader reader,
    ReaderBridgeSnapshotDocument snapshotDocument,
    nint selectedSourceAddress)
{
    // Read camera vectors/angles at discovered offsets
    // Calculate yaw/pitch from forward vector (if basis) or direct read (if scalars)
    // Compare against actor orientation (if both available)
    
    return new CameraOrientationReadResult(
        Mode: "camera-orientation-live",
        SelectedSourceAddress: selectedSourceAddress.ToString("X"),
        CameraYawDegrees: cameraYaw,
        CameraPitchDegrees: cameraPitch,
        CameraDistance: cameraDistance,
        ActorYawDegrees: actorYaw,
        DeltaYawFromActor: cameraYaw - actorYaw,
        Notes: validationNotes
    );
}

public sealed record CameraOrientationReadResult(
    string Mode,
    string SelectedSourceAddress,
    double? CameraYawDegrees,
    double? CameraPitchDegrees,
    double? CameraDistance,
    double? ActorYawDegrees,
    double? DeltaYawFromActor,
    IReadOnlyList<string> Notes);
```

### Update CLI

```csharp
// reader/RiftReader.Reader/Cli/ReaderOptions.cs
public bool ReadCameraOrientation { get; init; }

// reader/RiftReader.Reader/Program.cs
if (options.ReadCameraOrientation)
{
    return RunReadCameraOrientationMode(options);
}
```

### Create Helper Scripts

- `scripts/capture-camera-orientation.ps1` — wrapper around `read-camera-orientation`
- `scripts/profile-camera-keys.ps1` — test which inputs affect camera (mouse buttons, mouse wheel)

---

## Phase 5: Validation & Documentation

### Validation Checklist

- [ ] Camera yaw/pitch deltas correlate with mouse movement input
- [ ] Camera basis matrix (if present) is orthonormal (det ≈ 1.0)
- [ ] Camera can face opposite direction from actor (decoupling test)
- [ ] Camera distance scales correctly with mouse wheel
- [ ] Live gameplay: smooth camera response, no jitter
- [ ] Offsets stable across multiple sessions

### Documentation

Once offsets are validated, update:
1. `CLAUDE.md` section 3 (add camera offsets to verified facts)
2. Trace artifact: `scripts/captures/player-camera-orientation.json`
3. This file: replace hypothesis with confirmed offsets

---

## Expected Offsets (To Be Discovered)

| Field | Hypothesis | Confirmed | Offset | Type | Range | Notes |
|-------|-----------|-----------|--------|------|-------|-------|
| Field | Hypothesis | Confirmed | Offset / Source | Type | Range | Notes |
|-------|-----------|-----------|-----------------|------|-------|-------|
| Camera yaw | Yes | ✅ | selected-source `+0x60/+0x94` basis forward rows | basis-derived | degrees from basis | Live verified with RMB yaw |
| Camera pitch | Yes | ⚠️ | entry15 orbit coords `+0xA8..+0xBC` relative to player coord | derived | camera-relative angle | Works live, but not a direct scalar |
| Camera distance | Yes | ⚠️ | entry15 orbit vector magnitude | derived | world units | Strong lead, derived not direct |
| Direct pitch scalar | Yes | ❌ | none verified in nearby 8 KB entry scans | float32 | n/a | `entry4 +0x1D0` is weak/noisy only |
| Camera basis at selected-source `+0x7D0` | Maybe | ❌ | zero rows in current client | basis | n/a | Old hypothesis did not validate |

---

## Troubleshooting

### Camera deltas don't correlate with mouse movement
- Verify SelectedSourceAddress is correct (run `read-player-current.cmd`)
- Check that focus is on Rift window during stimulus test
- Try wider search range (+0xB0 to +0x160) if candidates are outside +0xB8 to +0x150

### Actor coordinates change during camera stimulus
- Normal in 3rd-person view if character is close to view boundary
- Test in an open area with plenty of space
- Verify by running stimulus test, checking `ActorCoordDelta` field (should be ~0)

### Candidates found but don't match stimulus
- May have found wrong structure (e.g., UI camera instead of player camera)
- Try alternate search ranges: +0x100 to +0x180, +0x140 to +0x1C0
- Check if camera is stored in a separate system (not in selected-source component)

### Multiple candidate vectors
- Camera may use 3×3 basis matrix like actor (3 triplets = 3 candidates)
- Validate using determinant check in stimulus test
- Duplication pattern (primary + duplicate) suggests basis matrix approach

---

## Next Steps

1. **Immediate**: Follow Phase 2 (Cheat Engine scanning) to find candidate addresses
2. **Validate**: Use Phase 3 stimulus testing on candidates
3. **Implement**: Once offsets confirmed, implement CameraOrientationReader.cs (Phase 4)
4. **Document**: Update CLAUDE.md and trace artifacts (Phase 5)

## References

- Actor orientation discovery: `CLAUDE.md` section 3 (verified offsets)
- Actor orientation reader: `reader/RiftReader.Reader/Models/PlayerOrientationReader.cs`
- Actor stimulus test workflow: `scripts/test-actor-orientation-stimulus.ps1`
- Component structure: `scripts/captures/player-owner-components.json`
