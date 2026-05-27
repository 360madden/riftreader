# Static Owner Coordinate Chain — Targeted Displacement Validation Backup

Generated UTC: `2026-05-27T18:44:55Z`

## Verdict

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` **responded to targeted live displacement** on current PID `34176` / HWND `0x3D1544`.

This strengthens the chain as the current player-coordinate static owner candidate, but it is **not promoted** because independent API-now validation is still blocked.

## Chain

| Field | Value |
|---|---|
| Expression | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Module base | `0x7FF77AF40000` |
| Static root address | `0x7FF77E22BC80` |
| Owner address | `0x278C3830010` |
| Target | PID `34176`, HWND `0x3D1544` |

## Pose evidence

| Pose | Input / visual | Coordinate | Artifact |
|---|---|---|---|
| Baseline | Screenshot baseline | `7259.590820312, 821.534545898, 2988.985107422` | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-184129-911623\summary.json` |
| After forward | `W` 450ms, visual change `25.5139%` | `7260.314941406, 821.421386719, 2991.778564453` | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-184151-668697\summary.json` |
| After reverse | `S` 450ms, visual change `21.7778%` | `7259.949707031, 821.437561035, 2990.375732422` | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-184219-347008\summary.json` |

## Deltas

| Segment | dx | dy | dz | X/Z planar |
|---|---:|---:|---:|---:|
| Baseline -> Forward | `0.724121094` | `-0.113159180` | `2.793457031` | `2.885784736` |
| Forward -> Reverse | `-0.365234375` | `0.016174316` | `-1.402832031` | `1.449597826` |
| Baseline -> Reverse | `0.358886719` | `-0.096984863` | `1.390625000` | `1.436188556` |

## Visual artifacts

- Baseline screenshot: `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260527-144111-648.png`
- After forward screenshot: `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260527-144144-370.png`
- After reverse screenshot: `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260527-144212-152.png`

## API-now status

Independent API-now validation remains blocked. Latest ChromaLink attempt:

`C:\RIFT MODDING\RiftReader\scripts\captures\chromalink-world-state-reference-20260527-183942-813019\summary.json`

Blockers:

- `world-state-not-healthy`
- `world-state-player-position-not-fresh`
- `world-state-player-position-stale`
- `world-state-navigation-player-position-unavailable`

## Safety / promotion ledger

| Gate | Status |
|---|---|
| Movement/input | Two bounded approved stimuli were sent: `W` 450ms and `S` 450ms |
| Cheat Engine | Not used |
| x64dbg attach | Not used |
| DebugActiveProcessStop | Not called |
| Provider writes | None |
| Proof promotion | Not done |
| Actor/static-chain promotion | Not done |
| Git mutation | Not done |

## Next promotion gates

1. Restore/fix fresh independent API-now source.
2. Compare API-now vs immediate chain-now for this static chain.
3. Run/record current-pose and displaced-pose validation packet.
4. Ask for explicit promotion approval before marking this actor/static-chain truth.

<!-- API_NOW_VALIDATION_UPDATE_START -->

## Fresh API-now validation update

Updated UTC: `2026-05-27T18:50:27Z`

Fresh RRAPICOORD API-now matched immediate chain-now:

| Source | Coordinate |
|---|---|
| API-now | `7259.949700000, 821.440000000, 2990.379900000` |
| Chain-now | `7259.949707031, 821.437561035, 2990.375732422` |

Max absolute axis delta: `0.004167578` within tolerance `0.25`.

Backup report:

- Markdown: `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-api-now-validation-2026-05-27.md`
- JSON: `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-api-now-validation-2026-05-27.json`

Promotion status remains: **not promoted**; explicit promotion approval is still required.

<!-- API_NOW_VALIDATION_UPDATE_END -->
