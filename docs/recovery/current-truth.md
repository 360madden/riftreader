# Current RIFT live truth — post-patch static root **PROMOTED**

Updated UTC: `2026-07-18T17:11:22Z`

## **✅ CURRENT — root `0x32E07C0`**

| Field | Value |
|---|---|
| PID / HWND | `21436` / `0x710A94` |
| Process start UTC | `2026-07-18T16:58:36.9977119Z` |
| Module base | `0x7FF696620000` |
| **Root RVA** | **`0x32E07C0`** |
| Chain | **`[rift_x64+0x32E07C0]+0x320/+0x324/+0x328`** |
| Owner (session heap) | `0x1D00C8B06B0` — reacquire each session |
| Camera child | `[owner+0x330]` |
| Heading | `[[owner+0x330]+0x158]` (radians) |
| Machine JSON | `docs/recovery/current-truth.json` |

### Gates passed (2026-07-18)

| Gate | Result | Artifact |
|---|---|---|
| Static resolver complete | ✅ | reseed + readback |
| Restart / relog survival | ✅ PID `26916` → `21436` | `scripts/captures/owner-root-restart-survival-currentpid-21436-20260718-170030/` |
| Three-pose displacement | ✅ A→B ≈ 4.87 m, B→C ≈ 2.35 m | `scripts/captures/static-root-three-pose-21436-20260718-170754/` |
| API-now vs chain-now (3 poses) | ✅ maxAbs Δ ≪ 0.5 | same three-pose capture |
| Center SendInput LMB C2M | ✅ planar Δ ≈ **2.14 m** | `scripts/captures/sendinput-lmb-test-20260718-170938/` |

### Superseded roots (do not use)

| Root | Status |
|---|---|
| `0x32EBC80` | dead pre-patch |
| `0x32EBDC0` | null post-patch before reseed |

### Instant readback

```powershell
python scripts\static_owner_coordinate_chain_readback.py --pid 21436 --hwnd 0x710A94 --module-base 0x7FF696620000 --root-rva 0x32E07C0 --coord-offset 0x320 --samples 2 --json

# or after binding from truth:
python scripts\static_owner_coordinate_chain_readback.py --use-current-truth --samples 2 --json
```

### W2S / S2W

```powershell
python scripts\world-to-screen.py --pid 21436 --round-trip --json
python scripts\world-to-screen.py --pid 21436 --screen-x 426 --screen-y 266 --json
```

Forward = `normalize(lookAt − camPos)` from camera child `+0x14`; FOV at `+0x38`.

### Historical backup

Previous truth JSON (pre-promote):  
`docs/recovery/historical/current-truth-before-0x32E07C0-promote-20260718-171122.json`

### Operator rules

- Re-bind PID / HWND / process-start / module base after every restart.
- Never hardcode heap owner addresses.
- Movement consumers: fresh chain readback + exact target before input.
- Full actor/stat graph is **not** promoted; coordinates (+ heading candidate) only.
- CE / x64dbg remain separately gated.

### Durable progress / handoff

| Doc | Role |
|---|---|
| [`progress-2026-07-18-post-patch-root-and-c2m.md`](progress-2026-07-18-post-patch-root-and-c2m.md) | Full milestone notes (gates, tools, decisions, next) |
| [`post-patch-static-root-candidate-2026-07-18.md`](post-patch-static-root-candidate-2026-07-18.md) | Discovery narrative (promoted; keep for history) |
