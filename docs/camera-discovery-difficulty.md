# Camera Discovery Difficulty Analysis

## Current State

- **Actor orientation** (player facing) - ✅ FOUND at selected-source +0x60/+0x94
- **Camera yaw/pitch/distance** - ❌ NOT YET FOUND

## Why It's Hard

### 1. Unknown Location
- Camera is NOT in selected-source (proven)
- Not in any known RIFT API
- Must scan memory to find it
- No guarantee it even lives in player owner object

### 2. No Direct Detection
- Can't ask RIFT "where is camera?"
- Must infer from changes: move camera → check what changed in memory
- Must iterate through candidates

### 3. Signal vs Noise
- Memory has thousands of changing values per frame
- Camera movement changes ONLY a few bytes
- Hard to distinguish camera changes from other changes

### 4. Input Methods (Partially Solved)
- ❌ PostMessage mouse - not a trusted normal path
- ❌ MCP mouse - doesn't work  
- ✅ direct mouse_event / focused mouse input - works for RMB+move **when Rift
  can be found cleanly and foreground focus can be verified**

## What's Needed

### A. Validated Leads

| Lead | Description | Status |
|------|-------------|--------|
| Lead A | owner+0xD0 → wrapper+0x100 → candidate+0xA0 | Needs testing |
| Lead B | Container entry 15 +0x338 (vector) +0x094 (distance) | Needs testing |

### B. Process

1. Read candidate address (before)
2. Move camera via mouse_event
3. Read same address (after)
4. Compare bytes → find changes
5. Repeat for each lead

### C. Time Estimate

- **Best case**: 1-2 hours if Lead A or B works
- **Average case**: 5-10 hours, many iterations
- **Worst case**: Camera data not accessible from player owner object → need to scan full memory (very slow)

## Risk Factors

| Factor | Impact | Workaround |
|--------|--------|------------|
| Lead addresses stale | High | Re-trace owner graph |
| Camera in different object | High | Search wider (other players, world objects) |
| Too much memory noise | Medium | Use smaller search window |
| DirectInput intercepts input | High | Already solved - mouse_event works |

## Recommendations for Future AI

1. **Start with Lead A** - most promising based on prior findings
2. **Use focused mouse_event / direct mouse input**, NOT PostMessage or MCP
3. **Get fresh owner trace** before starting - addresses may have shifted
4. **Test one offset at a time**, not bulk scanning
5. **Document every test** - even failures are data

## Conclusion

**Difficulty: MEDIUM-HIGH**
- Solvable if camera data accessible from player owner chain
- Requires systematic testing of candidates
- Input method now works when focus is clean (mouse_event / direct mouse input)
- Main risk: camera data in unexpected location

This is why the branch is called "camera-orientation-discovery" - it's an exploration, not a guarantee.
