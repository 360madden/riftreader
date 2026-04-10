# Camera Orientation Discovery Workflow

## Overview
Camera yaw/pitch/distance are not exposed via the Rift API and must be discovered through memory scanning and stimulus testing. Camera is independent from actor orientation — the player character can face one direction while the camera looks another.

**Status**: Discovery in progress  
**Branch**: `feature/camera-orientation-discovery`  
**Key files**: 
- `scripts/test-camera-stimulus.ps1` — stimulus testing helper
- `scripts/generate-camera-probe.ps1` — CE probe generator
- `scripts/captures/player-actor-orientation.json` — baseline component address (known)

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

### Camera Expected Structure (Hypothesis)
Based on actor orientation pattern, camera likely contains:
- **Camera forward vector** (float32 triplet, normalized ~1.0 magnitude)
- **Camera yaw angle** (degrees or radians)
- **Camera pitch angle** (degrees or radians, range ~-60 to +60)
- **Camera distance** (float32 scalar, range ~5-100 units)
- **Camera up vector** (optional, if using basis matrix like actor)

Search range: **+0xB8 to +0x150** (88 bytes)

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
- `mouse-yaw-right`: Actor yaw delta > 0 (positive rotation)
- `mouse-pitch-up`: Actor pitch delta < 0 (negative tilt, convention-dependent)
- `mouse-wheel-zoom-in`: Camera distance delta < 0 (zoom closer)
- **Important**: Actor coordinate delta should remain ~0 (camera-only movement)

**Important Note**: The stimulus test currently measures **actor orientation** changes. For camera validation, we need to:
1. Add camera-specific fields to the capture (requires C# reader updates)
2. Compare camera deltas to actor deltas to verify decoupling

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
| Camera forward | Yes | ❌ | +0xC0? | float32 triplet | ±1.0 (normalized) | Similar to actor basis |
| Camera yaw | Yes | ❌ | +0xCC? | float32 | 0-360° or 0-2π | Degrees or radians TBD |
| Camera pitch | Yes | ❌ | +0xD0? | float32 | -60 to +60° | Negative when looking down |
| Camera distance | Yes | ❌ | +0xD4? | float32 | 5-100 units | Zoom level |
| Camera up | Maybe | ❌ | +0xE0? | float32 triplet | ±1.0 (if using basis) | Optional |

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
