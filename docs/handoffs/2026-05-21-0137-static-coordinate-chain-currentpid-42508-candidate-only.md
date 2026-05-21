# Static coordinate chain discovery — current PID 42508 candidate-only

Generated: 2026-05-21 01:37 America/New_York

## TL;DR

The committed 10-phase static-chain plan is in place, and the first current-PID static-chain discovery pass completed without CE/x64dbg/live input. The pass found a useful **current-PID focused heap chain** that reads back the live coordinate accurately, but it did **not** find a module/static root. Do not promote this as a stable static pointer chain yet.

## Current target

| Field | Value |
|---|---|
| PID | `42508` |
| HWND | `0x80E00` |
| Process | `rift_x64` |
| Dynamic coord anchor | `0x1FD21900420` |
| Baseline run dir | `C:\RIFT MODDING\RiftReader\scripts\captures\static-chain-discovery-pid42508-20260521-052220` |

## Best current-PID chain evidence

| Evidence | Value |
|---|---|
| Focused heap chain | `[[0x1FD21A952A8]] + 0x420` |
| `0x1FD21A952A8` readback | `0x1FD4DC04440` |
| `0x1FD4DC04440` readback | `0x1FD21900000` |
| Coord leaf | `0x1FD21900420` |
| API-now vs memory-now max delta | `0.002135851562456992` |
| Verdict | `api-now-matches-focused-chain-now` |
| Promotion eligible | `false` |

## Static/root result

| Check | Result |
|---|---|
| Direct reverse pointer scan from coord leaf/page | Heap refs only; no `rift_x64.exe` module hits |
| Focused chain parent scan | Stops at heap parent `0x1FD21A952A8`; no parent refs found |
| Root-signature sweep | Re-identifies current page-ref owner with full signature and coord pointer slot `0x0` |
| Stable static root | **Not found** |

## Artifacts

| Artifact | Path |
|---|---|
| Run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\static-chain-discovery-pid42508-20260521-052220\run-summary.json` |
| Run manifest | `C:\RIFT MODDING\RiftReader\scripts\captures\static-chain-discovery-pid42508-20260521-052220\static-chain-run-manifest.json` |
| Memory inventory | `C:\RIFT MODDING\RiftReader\scripts\captures\static-chain-discovery-pid42508-20260521-052220\02-memory-inventory` |
| Focused chain pointer family | `C:\RIFT MODDING\RiftReader\scripts\captures\static-chain-discovery-pid42508-20260521-052220\07-focused-chain-pointer-family\summary.json` |
| Fresh API reference | `C:\RIFT MODDING\RiftReader\scripts\captures\static-chain-discovery-pid42508-20260521-052220\08-fresh-api-reference\rift-api-reference-currentpid-42508-20260521-053329.json` |
| Focused chain readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-chain-discovery-pid42508-20260521-052220\08-fresh-api-reference\focused-chain-readback-summary.json` |
| Current root signature packet | `C:\RIFT MODDING\RiftReader\scripts\captures\static-chain-discovery-pid42508-20260521-052220\06-current-root-signature-from-page-ref\root-signature.json` |
| Slot-0 root signature sweep | `C:\RIFT MODDING\RiftReader\scripts\captures\static-chain-discovery-pid42508-20260521-052220\06-sweep-26E4C48-slot0-rerun\summary.json` |

## Code hardening completed

`root_signature_module_hint_sweep.py` now honors `signature.coordPointerSlotOffset` instead of always assuming the coordinate pointer is at owner offset `0x10`. This was needed for the current page-ref owner, where the coordinate page pointer is at offset `0x0`.

## Safety summary

| Safety field | Value |
|---|---|
| Movement sent by this static-chain pass | `false` |
| Key/input sent | `false` |
| Cheat Engine used | `false` |
| x64dbg attached | `false` |
| Target memory written | `false` |
| SavedVariables used as live truth | `false` |
| Provider writes | `false` |

## Resume from here

1. Keep `0x1FD21900420` as the current dynamic proof anchor only while PID/HWND remain current.
2. Treat `[[0x1FD21A952A8]] + 0x420` as a current-PID reacquisition lead, not static truth.
3. Next static-chain pass should search for a parent/static owner of `0x1FD21A952A8` and `0x1FD4DC04440`, or use authorized x64dbg access evidence if the operator explicitly re-authorizes live debugging.
4. Do not promote until module/RVA/static-owner provenance, multi-pose API-now vs chain-now, restart validation, and same-target ProofOnly all pass.
