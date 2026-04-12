# Camera Yaw/Pitch Discovery via Cheat Engine

## Problem
- Camera data is **NOT** in the selected-source component
- Static offsets at +0x7D0/+0x7DC/+0x7E8 don't update on camera rotation
- Camera must be in a separate memory location or separate object

## Solution: Manual Cheat Engine Pointer Search

### Phase 1: Find Camera Yaw Address

**Objective**: Locate the float32 that stores current camera yaw angle

**Steps**:

1. **Start fresh Cheat Engine session**
   - Attach to `rift_x64`
   - Clear any prior searches

2. **Get baseline camera yaw**
   ```powershell
   cd C:\RIFT MODDING\RiftReader
   .\scripts\capture-camera-snapshot.ps1
   ```
   - Note the `CameraYaw.Degrees` value (e.g., `27.5468°`)
   - This is what we're looking for

3. **CE: First exact-value scan**
   - Value type: **Float**
   - Search value: **27.5468** (from above)
   - Scan scope: **All memory** (or narrow to rift_x64 module if slow)
   - Click **First Scan** → Hits will be 100+ (camera yaw stored in multiple places)

4. **Narrow candidates: Rotation test**
   - Rotate camera in-game (move mouse left/right, ~90°)
   - Note new camera yaw angle (e.g., `117.5468°`)
   - CE: **Next Scan** → type new yaw value, scan type **Exact Value**
   - This eliminates static addresses
   - Should now have <10 candidates

5. **Validate remaining candidates**
   - For each candidate address in the list:
     - Add to address list (right-click → "Add address manually to the address list")
     - Click **"Pointer"** to expand the address in the data view
     - Watch the value while rotating camera
     - **Valid address**: Value changes smoothly as you rotate (e.g., 0° → 45° → 90°)
     - **Invalid address**: Value stays static or jumps erratically

6. **Confirm camera yaw address**
   - You've found it when:
     - Value changes by approximately same amount as your mouse movement
     - Value is continuous (not jumping in large steps)
     - Value repeats if you rotate back

### Phase 2: Find Camera Pitch Address

**Objective**: Locate the float32 that stores camera pitch (vertical angle)

**Steps**:

1. **Get baseline pitch**
   ```powershell
   .\scripts\capture-camera-snapshot.ps1
   ```
   - Note `CameraPitch.Degrees` (e.g., `0.0000°`)

2. **CE: Exact-value scan for pitch**
   - Value: **0.0000** (or actual baseline)
   - Value type: **Float**
   - Scan → Hits will be many

3. **Tilt camera up in-game**
   - Move mouse up (vertical movement)
   - Note new pitch angle (e.g., `-30.0°`)
   - CE: **Next Scan** → new value → should eliminate candidates significantly

4. **Validate candidate**
   - Watch for smooth changes as you tilt camera
   - Confirm it increases when tilting up, decreases when tilting down

### Phase 3: Find Camera Distance Address

**Objective**: Locate float32 for camera distance if it's adjustable

**Steps**:

1. **Get baseline distance**
   ```powershell
   .\scripts\capture-camera-snapshot.ps1
   ```
   - Note `CameraDistance` (e.g., `10.5` units)

2. **Adjust camera distance in-game**
   - Mouse wheel or similar (depends on Rift keybinds)
   - Note new distance

3. **CE: Exact-value scan**
   - Follow same pattern as yaw/pitch
   - Validate by watching distance value change

### Phase 4: Extract Offsets

Once you've identified the addresses:

1. **Analyze offset patterns**
   - Note all three addresses (yaw, pitch, distance)
   - Look for patterns:
     - Are they sequential? (Yaw at X, Pitch at X+4, Distance at X+8)
     - Do they share a base address?
     - Are they in different objects?

2. **Find the base address**
   - If sequential, they're in a struct: Find the base address
   - If scattered, they might be in different objects: Find each base

3. **Calculate relative offsets**
   - Example:
     - Base address: `0x12345678`
     - Yaw found at: `0x123456B0` → Offset = `+0x38`
     - Pitch found at: `0x123456B4` → Offset = `+0x3C`
     - Distance found at: `0x123456B8` → Offset = `+0x40`

4. **Pointer walk (optional)**
   - Right-click address → **Pointer** → See what points to it
   - Example:
     - Address `0x123456B0` is pointed to by `0xABCDEF00`
     - That address might be the camera object pointer
     - You can then walk from player object to camera object

### Phase 5: Validate & Document

1. **Create validation snapshot**
   ```powershell
   .\scripts\capture-camera-snapshot.ps1 -OutputFile camera-discovery-$(Get-Date -Format 'yyyyMMdd-HHmmss').json
   ```

2. **Document findings**
   - Camera base address / pointer source
   - Camera yaw offset
   - Camera pitch offset
   - Camera distance offset (if found)
   - Session metadata (date, game client version, region if known)

3. **Test stability**
   - Zone transition → addresses should refresh (they'll change)
   - Relog → addresses will definitely change
   - **Conclusion**: Offsets are stable within a session; addresses are session-specific

## Implementation After Discovery

Once offsets are confirmed:

1. **Create `CameraOrientationReader.cs`**
   - Pattern: Mirror `PlayerOrientationReader.cs`
   - Read camera yaw/pitch/distance from discovered offsets
   - Validate basis orthonormality if basis matrix is found

2. **Add CLI option**
   - `--read-camera-orientation` → outputs camera yaw/pitch/distance

3. **Update CLAUDE.md Section 3**
   - Document discovered offsets
   - Include validation notes

4. **Write integration tests**
   - Stimulus test: Verify camera angle matches input
   - Decoupling test: Camera yaw ≠ actor yaw (they can differ)

## Notes

- **Why manual**: Camera might be in UI system, rendering system, or separate controller object — all difficult to automate without game knowledge
- **Why CE pointer search works**: Following chains from known addresses finds the camera structure
- **Session-specific addresses**: Game memory relocates on startup; offsets are stable, addresses are not
- **Typical camera distance**: ~5-30 units from player; stored as float if adjustable
