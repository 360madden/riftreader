# MCP Mouse Control Camera Discovery Plan

**Date**: April 11, 2026
**Status**: Planning
**Branch**: `feature/camera-orientation-discovery`

## Overview

With the Windows MCP (Model Context Protocol), we now have programmatic mouse control that works against RIFT. This enables automated camera stimulus testing instead of manual mouse movement.

## MCP Capabilities

The MCP provides these mouse functions:
- `windows-mcp_Move` - Move mouse cursor to [x, y] coordinates
- `windows-mcp_Click` - Click at coordinates or UI element
- `windows-mcp_Scroll` - Scroll at coordinates
- `windows-mcp_App(mode="switch")` - Bring window to foreground

**Test Result (April 11, 2026)**: MCP moves cursor on screen, but RIFT camera does NOT rotate. RIFT uses DirectInput which reads raw mouse hardware events, not cursor position. This is the same reason PostMessage doesn't work.

**Implication**: MCP cannot automate camera rotation. Must use manual mouse movement for stimulus testing.

## Discovery Workflow

### Phase 1: Get Baseline State

1. **Switch to Rift window**
   ```
   windows-mcp_App(mode="switch", name="Rift")
   ```

2. **Get player anchor address**
   ```powershell
   dotnet run --project reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-current --json
   ```
   Extract `SelectedSourceAddress` (e.g., `0x1577AC2FB60`)

3. **Calculate search addresses**
   - Owner = derived from selector trace
   - Owner +0xD0 = owner-state-wrapper
   - Wrapper +0x100 = candidate object (Lead A)
   - Container entry 15 = Lead B

### Phase 2: Before Stimulus Capture

Capture memory state at candidate addresses BEFORE mouse movement:

```powershell
# Read candidate object at owner+0xD0->wrapper+0x100
$beforeWrapper = Read-MemoryBytes -Address $wrapperPlus100 -Length 512

# Read entry 15 at +0x338 and +0x094
$beforeEntry15 = Read-MemoryBytes -Address $entry15 -Length 1024
```

### Phase 3: Apply Mouse Stimulus

Use MCP to rotate camera:

```powershell
# Yaw right - move mouse horizontally
windows-mcp_Move(loc=[currentX + 300, currentY])

# Pitch up - move mouse vertically  
windows-mcp_Move(loc=[currentX, currentY - 200])

# Zoom in - scroll wheel
windows-mcp_Scroll(direction="down", wheel_times=5)
```

### Phase 4: After Stimulus Capture

Capture memory state AFTER mouse movement:

```powershell
$afterWrapper = Read-MemoryBytes -Address $wrapperPlus100 -Length 512
$afterEntry15 = Read-MemoryBytes -Address $entry15 -Length 1024
```

### Phase 5: Compare and Identify

Compute deltas:
```powershell
$deltaWrapper = Compare-Bytes -Before $beforeWrapper -After $afterWrapper
$deltaEntry15 = Compare-Bytes -Before $beforeEntry15 -After $afterEntry15
```

Filter for significant changes (> 0.001 for floats).

## Scripts to Create

| Script | Purpose |
|--------|---------|
| `test-mcp-camera-stimulus.ps1` | Main orchestration script |
| `read-candidate-addresses.ps1` | Read Lead A and Lead B addresses |
| `mcp-move-mouse.ps1` | MCP mouse movement wrapper |
| `compare-memory-snapshots.ps1` | Byte comparison with delta analysis |

## Implementation Notes

### Mouse Movement Parameters

| Stimulus | MCP Action | Expected Memory Change |
|----------|-----------|----------------------|
| Camera yaw right | Move mouse +300 X | Float delta at candidate basis |
| Camera pitch up | Move mouse -200 Y | Pitch angle delta |
| Camera zoom in | Scroll down 5 ticks | Distance scalar delta |

### Timing

- Hold mouse movement: ~500ms
- Wait after movement before read: ~250ms
- Total cycle: ~1 second per stimulus

### Safety

- Start with small movements (100-200 pixels)
- Verify Rift is foreground before each test
- Log all before/after states for debugging

## PostMessage Test Results (April 11, 2026)

**Tested**: PostMessage with WM_MOUSEMOVE and WM_MOUSEWHEEL to Rift window

**Result**: FAILED - Messages sent successfully but camera did not move

**Window class found**: `TWNClientFramework` (not "Rift")

**Conclusion**: PostMessage does NOT work for mouse input to RIFT. RIFT uses DirectInput which ignores Windows message queue mouse events.

**MCP is required** for automated mouse input.

### Lead A: Owner +0xD0 → Wrapper +0x100 → Basis at +0xA0

Expected: 3x3 basis matrix that shows BOTH yaw AND pitch changes

Script approach:
1. Read owner, follow +0xD0 to wrapper
2. Follow +0x100 to candidate object  
3. Read 256 bytes at candidate +0xA0 (basis matrix location)
4. Compare before/after camera movement

### Lead B: Entry 15 +0x338 + Distance at +0x094

Expected: Normalized direction vector + distance scalar

Script approach:
1. Get container address from owner graph
2. Read entry 15 (container + 15*entrySize)
3. Read +0x338 (normalized vector), +0x094 (distance)
4. Compare before/after camera rotation and zoom

## Next Steps

1. Create `test-mcp-camera-stimulus.ps1` that orchestrates the full workflow
2. Get current selected-source address from live session
3. Walk owner +0xD0 chain to get candidate addresses
4. Run MCP mouse movement + memory capture cycle
5. Identify which lead shows camera data

## References

- MCP mouse functions: `Move`, `Click`, `Scroll`, `App(switch)`
- Existing scripts: `test-camera-stimulus.ps1`, `capture-actor-orientation.ps1`
- Documentation: `docs/camera-discovery-handoff.md` (updated April 11, 2026)