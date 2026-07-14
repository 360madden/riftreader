# Pre-Update Server Shutdown Handoff — 2026-07-14

## Status

**PRE-UPDATE BASELINE COMPLETE.** Server disconnect imminent; all safe read-only captures finished on PID **24224**.

## Live epoch (frozen at disconnect)

| Field | Value |
|---|---|
| PID | 24224 |
| HWND | 0x1909B0 |
| Module base | 0x7FF63CA90000 |
| Process start UTC | 2026-07-13T20:02:31Z |
| Exe SHA256 | `7D2595BE8D9543ACFF7808B12796C967FB690C7825FD7DD6846AC2194E551D40` |
| Exe size | 60,024,256 bytes |
| Glyph manifest | `STABLE-1-1159-a-1256439` / SHA1 `4705144e32c0da22006b32c84a7661688a8658d7` |
| Character | Atank @ Sanctum of the Vigil |
| Coords (API + chain) | **7455.58 / 885.58 / 3056.18** |

## Promoted static chain (pre-patch)

```text
[rift_x64.exe+0x32EBDC0] → owner 0x11E3AED06A0
  +0x320/+0x324/+0x328 : X/Y/Z (float) ✅ still readable after disconnect
  +0x300 : cumulative rotation counter
  +0x304 : speed/turn rate
  +0x330 : camera-state child pointer ⚠️ ZEROED after server disconnect
      +0x158 : direct heading — unavailable when +0x330 null
```

**Dead chain:** `rift_x64+0x32EBC80` — null; do not use.

**Owner vtable RVA:** `0x2648FD8` (captured in final owner-window snapshot)

## AOB fast-reacquire signature

| Field | Value |
|---|---|
| Pattern | `1E 01 00 00 ?? ?? ?? ??` |
| Root RVA | `0x32EBDC0` |
| moduleScanCount | 1 |
| File | `signatures/rift_x64/root_coord-root-32ebdc0.json` |
| Alt label file | `signatures/rift_x64/root_preupdate-final-coord-root.json` |

C# module scan confirmed unique hit at `0x7FF63CA9699E` (relative offset `0x699E` in code section — pattern locates root context, not the root itself).

## API vs memory validation (final)

| Axis | API | Chain | Delta |
|---|---|---|---|
| X | 7455.58 | 7455.5825 | 0.0025 |
| Y | 885.58 | 885.5834 | 0.0034 |
| Z | 3056.18 | 3056.1750 | 0.0050 |

**Verdict:** PASS (tolerance 0.25). Marker seq **6555**.

## Disconnect behavior (important)

After server disconnect, same PID still running:

- Coordinate chain at `+0x320/+0x324/+0x328` **unchanged** (frozen last pose).
- `owner+0x330` camera child pointer **zeroed** (was `0x11E6D38FD00` while in-world).
- Do not treat post-disconnect heading/camera fields as in-world truth.

## Stale artifacts — do not use as live truth

| Artifact | Issue |
|---|---|
| `current-proof-anchor-readback.json` | PID 130540 / HWND 0x9310EA |
| ReaderBridge SavedVariables | LastWrite 2026-07-11 (~2.4 days stale) |
| `read-player-current` (C#) | Failed — stale SavedVariables bootstrap |

## Artifact index

### Baseline folder

`handoffs/current/pre-update-baseline/20260714T075857Z-preupdate-capture-v001/`

### Final captures (2026-07-14 ~08:02 UTC)

| Capture | Path |
|---|---|
| 3-sample stationary chain poll | `scripts/captures/static-owner-coordinate-chain-readback-20260714-080203-661753/` |
| Final owner window (418 floats) | `scripts/captures/static-owner-facing-snapshot-preupdate-final-owner-window-20260714-080203-769997/` |
| API reference | `scripts/captures/rift-api-reference-currentpid-24224-20260714-080205.json` |
| Coordinate family snapshot (best) | `scripts/captures/coordinate-family-snapshot-currentpid-24224-20260714-080221/` |
| Coordinate family snapshot (seed) | `scripts/captures/coordinate-family-snapshot-currentpid-24224-20260714-080057/` |
| Candidate readback | `scripts/captures/candidate-readback-currentpid-24224-20260714-080239-200266/` |
| Owner root rediscovery | `scripts/captures/postupdate-owner-root-rediscovery-20260714-080242-579778/` |
| resolve-player-coords (fixed) | `scripts/resolve-player-coords.py` — module base `0x7FF63CA90000` |

### Committed durable artifacts (this handoff commit)

| Path | Role |
|---|---|
| `handoffs/current/pre-update-baseline/20260714T075857Z-preupdate-capture-v001/` | Process/exe/chain baseline JSON |
| `handoffs/current/pre-update-baseline/20260714T080500Z-preupdate-final-v002/ARTIFACT_MANIFEST.json` | Final manifest index |
| `signatures/rift_x64/root_coord-root-32ebdc0.json` | AOB signature for `0x32EBDC0` |
| `signatures/rift_x64/root_preupdate-final-coord-root.json` | Duplicate AOB capture label |

### Code fix applied

`scripts/resolve-player-coords.py` — added `0x7FF63CA90000` to known module bases for this ASLR epoch.

## Post-patch recovery (start here)

1. Allow Glyph patch; note new exe SHA256 vs baseline above.
2. `pwsh -File scripts/get-rift-window-targets.ps1 -Json` — fresh PID/HWND/base.
3. Test `rift_x64+0x32EBDC0` readback; if RVA drifted, AOB-scan pattern above.
4. Fresh API capture; API-now vs chain-now must pass before movement.
5. Revalidate `owner+0x330` / `+0x158` heading only **in-world** after relog.
6. Invalidate `current-proof-anchor-readback.json` on PID change; ProofOnly reacquire.

## Do not do yet

- Do not promote proof-anchor or actor chain from pre-patch artifacts alone.
- Do not trust SavedVariables coords for current session.
- Do not send movement without explicit approval post-patch.

## Resume prompt

```
PRE_UPDATE_SERVER_SHUTDOWN_HANDOFF_2026-07-14.md
Compare post-patch exe SHA256 and revalidate rift_x64+0x32EBDC0.
```

Generated UTC: 2026-07-14T08:05:00Z