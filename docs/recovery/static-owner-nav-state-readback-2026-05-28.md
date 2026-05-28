# Static owner nav-state readback — candidate only

Updated UTC: `2026-05-28T03:22:00Z`

# **✅ RESULT**

The promoted coordinate owner can now be read as a repeatable navigation-state source for **position + candidate yaw/facing**:

| Field | Chain / formula |
|---|---|
| Position | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Facing target candidate | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` |
| Yaw | `atan2((owner+0x314)-(owner+0x328), (owner+0x30C)-(owner+0x320))` |

This is still **candidate-only**. It does not promote facing/yaw or the full actor/stat chain.

## Live response check

| Step | Coordinate | Yaw | Lookahead | Stability |
|---|---|---:|---:|---|
| Before `right` 250 ms | `{'x': 7260.65576171875, 'y': 821.4660034179688, 'z': 2989.657470703125}` | `83.646986` | `9.999149` | samples `3`, coord max delta `0.0`, yaw range `0.0` |
| After `right` 250 ms | `{'x': 7260.65576171875, 'y': 821.4660034179688, 'z': 2989.657470703125}` | `131.647713` | `9.999296` | samples `3`, coord max delta `0.0`, yaw range `0.0` |

| Signal | Value |
|---|---:|
| Frame change | `60.7778%` |
| Yaw delta | `48.000727` degrees |
| Coordinate planar drift | `0.0` |

Interpretation: the candidate yaw changes strongly on a turn pulse while position remains stationary, which is the response needed for nav-grade facing readback.

## Artifacts

| Artifact | Path |
|---|---|
| Before state summary | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-state-20260528-031944-060785\summary.json` |
| After state summary | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-state-20260528-032009-849296\summary.json` |
| Baseline screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260527-231937-553.png` |
| Changed screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260527-231958-523.png` |
| Final screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260527-232003-389.png` |
| JSON report | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-nav-state-readback-2026-05-28.json` |

## Safety

| Boundary | Status |
|---|---|
| Exact target | PID/HWND/process-start checked |
| Live input | Sent with approval: `right` 250 ms |
| Cheat Engine | Not used |
| x64dbg | Not used |
| Target memory writes | None |
| Provider writes | None |
| Facing promotion | Not done |
| Navigation control | Not done |

## Next gate

Before writing this into current truth as promoted facing/yaw, run one more bounded left/right/forward repeat or get explicit approval to promote based on current evidence.
