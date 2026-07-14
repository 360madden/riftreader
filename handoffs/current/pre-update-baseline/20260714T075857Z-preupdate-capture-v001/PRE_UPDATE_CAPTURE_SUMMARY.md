# Pre-Update Baseline Capture Summary

**Capture ID:** `20260714T075857Z-preupdate-capture-v001`  
**Captured UTC:** `2026-07-14T07:58:57Z`  
**Mode:** Read-only pre-update baseline (no memory writes, no input injection)

## Live process target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | **24224** |
| HWND | **0x1909B0** |
| Module base | **0x7FF63CA90000** |
| Executable | `C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe` |
| Process start | `2026-07-13T20:02:31Z` (UTC) |
| Window title | RIFT |
| Responding | true |

## Executable identity

| Field | Value |
|---|---|
| SHA256 | `7D2595BE8D9543ACFF7808B12796C967FB690C7825FD7DD6846AC2194E551D40` |
| Length | 60,024,256 bytes |
| LastWriteTimeUtc | `2026-06-30T10:00:16.7422086Z` |
| Glyph manifest SHA1 | `4705144e32c0da22006b32c84a7661688a8658d7` |
| Glyph manifest version | `STABLE-1-1159-a-1256439` |

Manifest length matches on-disk file size. Glyph `manifest64.txt` is present under the Live folder.

## Static coordinate chain baseline

Promoted chain from `docs/recovery/current-truth.md`:

```text
Static global: rift_x64+0x32EBDC0
  → heap owner object pointer
    → +0x320 / +0x324 / +0x328 : X / Y / Z (float)
    → +0x300 : cumulative rotation counter (legacy; not direct heading)
    → +0x304 : speed / turn rate
    → +0x330 : camera-state child pointer
        → +0x158 : direct heading (radians)
        → +0x2C / +0x34 : camera direction vector
```

At capture time for PID 24224:

- Root address: `0x7FF63FD7BDC0` (`moduleBase + 0x32EBDC0`)
- Owner pointer: `0x11E3AED06A0`

Dead chain `rift_x64+0x32EBC80` must not be used.

## ReaderBridge snapshot (SavedVariables)

**Classification:** post-save snapshot — **not** live IPC.

| Field | Value |
|---|---|
| Source file | `...\Deepwood\Atank\SavedVariables\ReaderBridgeExport.lua` |
| LastWriteTimeUtc | `2026-07-11T21:32:23.4581766Z` (~2.4 days stale) |
| Character | Atank (Deepwood, rift315.1@gmail.com) |
| Zone | Silver Landing (`z0000000CB7B53FD7`) |
| Coords | X=6974.5, Y=840.31, Z=3324.52 |
| Export count | 2201 |

AddOn source folder `Interface\AddOns\ReaderBridge` contains Lua sources only; export mirror lives under `Interface\Saved\...\SavedVariables\`.

## Stale vs live warnings

| Artifact | Recorded | Live now | Status |
|---|---|---|---|
| `current-proof-anchor-readback.json` | PID **130540**, HWND **0x9310EA** | PID **24224**, HWND **0x1909B0** | **STALE** — historical epoch only |
| `current-truth.md` validation table | module base `0x7FF728B80000`, PIDs 20080–36332 | module base `0x7FF63CA90000`, PID 24224 | Chain RVAs still valid; target binding must be revalidated |
| ReaderBridge SavedVariables | 2026-07-11 save | live session 2026-07-14 | **STALE** — offline cross-check only |

**Do not** run movement or promotion gates against stale PID/HWND proof-anchor artifacts. Reacquire with same-PID/HWND ProofOnly readback after any client restart or patch.

## Artifacts in this folder

| File | Contents |
|---|---|
| `process-target.json` | Output of `scripts/get-rift-window-targets.ps1 -Json` |
| `executable-identity.json` | SHA256, size, timestamps, Glyph manifest entry |
| `readerbridge-snapshot.json` | Freshest SavedVariables export metadata |
| `STATIC_CHAIN_BASELINE.json` | Chain RVA, owner offsets, live PID/HWND/module base |
| `PRE_UPDATE_CAPTURE_SUMMARY.md` | This summary |

## Post-update recovery checklist

1. Compare new `rift_x64.exe` SHA256/length against this baseline.
2. Re-run `get-rift-window-targets.ps1 -Json` for fresh PID/HWND/module base.
3. Validate `rift_x64+0x32EBDC0` still dereferences to a live owner with coords at `+0x320/+0x324/+0x328`.
4. Cross-check coords against fresh ReaderBridge export or API probe — not this 2026-07-11 snapshot.
5. Update `current-proof-anchor-readback.json` only after same-PID/HWND ProofOnly pass.