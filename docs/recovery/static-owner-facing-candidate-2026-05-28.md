# Static owner facing/yaw candidate — not promoted

Updated UTC: `2026-05-28T02:41:00Z`

# **✅ CANDIDATE FOUND**

The promoted coordinate owner now has a strong navigation-facing candidate:

`owner+0x30C/+0x310/+0x314` as a **look/facing target coordinate**, interpreted relative to current position at `owner+0x320/+0x324/+0x328`.

Yaw formula:

`atan2((owner+0x314) - (owner+0x328), (owner+0x30C) - (owner+0x320))`

This is **candidate-only** until explicit promotion approval. It does not promote the full actor/stat chain.

## Target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `34176` |
| HWND | `0x3D1544` |
| Process start UTC | `2026-05-27T18:06:53.0701460Z` |
| Module base | `0x7FF77AF40000` |
| Owner | `0x278C3830010` |
| Current position source | `owner+0x320/+0x324/+0x328` |
| Facing target candidate | `owner+0x30C/+0x310/+0x314` |

## Evidence

| Stimulus | Result |
|---|---|
| `right` 250 ms | Frame changed; coordinate drift `0.0`; candidate yaw changed `35.647° -> 79.412°` (`+43.765°`). |
| `left` 250 ms | Frame changed; coordinate drift `0.0`; candidate yaw returned near baseline `35.647° -> 31.412°`. |
| `w` 300 ms | Movement planar distance `1.978`; movement yaw `31.968°`; candidate facing before movement `31.412°`; difference `0.556°`. |

## Interpretation

The field triplet at `owner+0x30C/+0x310/+0x314` behaves like a point approximately `10m` in front of the player. Subtracting the promoted current position yields a forward/facing vector suitable for yaw calculation.

This is stronger than a raw scalar because it is tied to both turn response and forward movement response.

## Artifacts

| Artifact | Path |
|---|---|
| Baseline snapshot | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-facing-snapshot-yaw2-baseline-20260528-023901-461780\summary.json` |
| After right snapshot | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-facing-snapshot-yaw2-after-right-250ms-20260528-023920-389977\summary.json` |
| After left snapshot | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-facing-snapshot-yaw2-after-left-250ms-20260528-023954-693021\summary.json` |
| Turn comparison | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-facing-comparison-20260528-023955-197499\summary.json` |
| After forward snapshot | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-facing-snapshot-yaw2-after-forward-w300ms-20260528-024048-505448\summary.json` |
| Forward comparison | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-facing-comparison-20260528-024049-011009\summary.json` |
| Candidate JSON | `docs/recovery/static-owner-facing-candidate-2026-05-28.json` |

## Safety

| Boundary | Status |
|---|---|
| Live input | Sent with approval: `right:250ms`, `left:250ms`, `w:300ms` |
| Exact target | PID/HWND/process-start checked by helper and MCP binding |
| Cheat Engine | Not used |
| x64dbg | Not used |
| Target memory writes | None |
| Provider writes | None |
| Facing promotion | Not done |
| Full actor/stat-chain promotion | Not done |

## Next gate

Ask for explicit approval before promoting this candidate as the current facing/yaw source. A conservative option is one more repeat of `left/right/forward` before promotion.
