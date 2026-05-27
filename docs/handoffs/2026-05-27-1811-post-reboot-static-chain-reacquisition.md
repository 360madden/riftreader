# Post-Reboot Recovery + Static Chain Reacquisition

Generated: 2026-05-27T18:11:00Z

## Verdict

`static-owner-chain-reacquired-after-reboot`

The game process restarted after idle logout. The old target epoch is stale, but the static owner-coordinate chain survived into the new RIFT process.

## New target epoch

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `34176` |
| HWND | `0x3D1544` |
| Start UTC | `2026-05-27T18:06:53.0701460Z` |
| Module base | `0x7FF77AF40000` |
| Window title | `RIFT` |
| Window baseline | [`C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260527-140857-183.png`](C:\RIFT%20MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260527-140857-183.png) |

Old PID/HWND `12148 / 0x640C0C` are now stale.

## Reacquired static owner chain

```text
[rift_x64 + 0x32EBC80] + 0x320/+0x324/+0x328
```

Readback in the new process:

| Field | Value |
|---|---|
| Static root address | `0x7FF77E22BC80` |
| Root value / owner | `0x278C3830010` |
| Coordinate address | `0x278C3830330` |
| X/Y/Z | `7259.5908203125, 821.5345458984375, 2988.985107421875` |
| Owner vtable | `0x7FF77D58CEB8` / RVA `0x264CEB8` |
| Historical shape | matches `owner+0x320/+0x324/+0x328` |

Primary artifact:

[`C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-180907-440028\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-180907-440028\summary.json)

## Secondary chain status

The older proof/playerPosition registry chain did **not** cleanly reacquire after reboot:

```text
[[rift_x64 + 0x32FFB68] + 0x0] + 0x40
```

It failed with a readback error against the new epoch and should be treated as secondary/stale until separately rederived. The owner chain above is now the practical priority.

Failed secondary artifact:

[`C:\RIFT MODDING\RiftReader\scripts\captures\static-playerposition-chain-readback-20260527-180907-700748\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\static-playerposition-chain-readback-20260527-180907-700748\summary.json)

## API-now status

A ChromaLink world-state reference check was attempted and blocked safe:

[`C:\RIFT MODDING\RiftReader\scripts\captures\chromalink-world-state-reference-20260527-180955-988757\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\chromalink-world-state-reference-20260527-180955-988757\summary.json)

Blockers:

- `world-state-not-healthy`
- `world-state-player-position-not-fresh`
- `world-state-player-position-stale`
- `world-state-navigation-player-position-unavailable`

So API-now vs chain-now remains pending.

## Current status gates

Workflow status still reports stale current-proof/current-truth artifacts pointing at historical PID `12148`. That is expected because this recovery pass did not update/promote current truth or proof artifacts.

Movement remains blocked by stale proof/current-truth gates until a fresh API/proof validation is run against PID `34176` / HWND `0x3D1544`.

## Safety

| Field | Result |
|---|---:|
| CE used | false |
| x64dbg attach in this reacquisition pass | false |
| DebugActiveProcessStop | false |
| live input/movement | false |
| provider writes | false |
| proof promotion | false |
| actor/static-chain promotion | false |
| git mutation | false |

## Next best step

Prioritize the static owner chain. Run fresh API-now vs chain-now when a healthy live API source is available:

```powershell
python .\scripts\static_owner_coordinate_chain_readback.py --pid 34176 --hwnd 0x3D1544 --module-base 0x7FF77AF40000 --expected-proof-anchor "" --json
```

Then compare the returned coordinate to a fresh healthy ChromaLink/world-state or other live API coordinate. If that passes, the chain has passed restart/relogin survival and API-now validation and can be prepared for explicit promotion review.
