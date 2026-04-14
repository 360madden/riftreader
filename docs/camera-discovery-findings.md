# Camera Discovery — Findings & Revised Approach

> **Superseded as active guidance:** this file correctly ruled out selected-source `+0xB8..+0x150`, but it predates the current verified live yaw/orbit workflow. Keep it as historical evidence, not the current procedure. See `C:\RIFT MODDING\RiftReader\docs\camera-orientation-discovery.md`.

**Date**: April 10, 2026  
**Status**: Camera location identified as outside selected-source component  
**Branch**: `feature/camera-orientation-discovery`

## Key Finding

**Camera data is NOT stored in the selected-source component range (+0xB8 to +0x150).**

Evidence:
- Scanned 88 bytes of camera range (+0xB8 to +0x150 from component base 0x1577AC2FB60)
- Found 28 candidate float values (normalized vectors, distance scalars, angles)
- Sent mouse input stimulus (yaw rotation)
- Re-scanned camera range — **zero significant changes** (Δ < 0.001 for all 22 floats)
- Conclusion: Camera angle/distance are NOT updated in this memory region during mouse movement

## Memory Structure Insights

The camera range does contain some interesting data:
- **+0x0 to +0xC**: Normalized vector components (0.95, 0.95, 0.95, 1.0)
  - Magnitude ~1.0 at +0xC — looks like a basis vector component
  - Could be unrelated structure or camera **orientation anchor** (fixed reference, not live angle)
- **+0x20-+0x28**: Player position coordinates (7421.4, 863.59, 2942.34)
  - Matches exact player location from addon export
  - Unusual to be in "camera" range — suggests this is actually character/entity-related data

## Revised Hypothesis

Camera is likely stored in **one of three locations**:

### Option 1: Separate Camera Controller Object
- Rift may have a camera object/system parallel to the player entity
- Not rooted from selected-source component
- Must be discovered by:
  1. Finding a camera "focus point" (should be at player position + camera offset)
  2. Scanning for float triplets near player coordinates
  3. Looking for pattern changes when mouse moves

### Option 2: UI Rendering System
- Camera may be stored in the UI/rendering layer (not game logic)
- Could be in a completely separate memory region
- May require hooking input callbacks or screen space calculations

### Option 3: Player Component (But Different Structure)
- Camera could be nested deeper in the owner-component graph
- Not directly in the selected-source but accessible via container/wrapper chain
- Would need to walk owner pointers further

## Recommended Next Steps

### Immediate (Discovery)
1. **Search for camera-like float patterns globally:**
   - Scan entire process for triplets matching (player.coord + camera offset)
   - Rift 3rd person camera typically: offset ≈ (0, 5, 10) units behind/above player
   - Example: If player at (7421, 864, 2942), camera likely near (7421±20, 864±10, 2942±30)

2. **Test stimulus correlation on found addresses:**
   - Use stimulus test to validate yaw/pitch changes match mouse input
   - Filter out false positives (will find many position data, need angle data)

3. **Trace from input system:**
   - Camera input handling (mouse look) likely triggers memory updates
   - Could instrument Rift module to trace input → memory writes
   - Or use Cheat Engine "break on access" for memory regions near camera

### Alternative Approaches
- **x64dbg breakpoint on module functions**: Hook GetCursorPos, mouse input Win32 APIs
- **Rift.MetaObject inspection**: Check if Rift exposes camera via internal object model
- **Reverse address from known UI feature**: Find "look at target" or "camera zoom" commands in Lua, trace to C++

## Next Investigation Phase

**Switching to Opus for strategic planning** — camera discovery requires:
- Broader memory space analysis (not just selected-source component)
- Multiple parallel search strategies
- Cross-validation against game behavior

Will implement a **multi-pronged approach**:
1. Global float pattern search (camera offsets from player)
2. Input callback tracing (mouse movement → memory correlation)
3. Owner-graph extension (check if camera linked via other pointers)
