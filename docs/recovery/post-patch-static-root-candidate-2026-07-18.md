# Post-patch static root candidate — 2026-07-18

**Status:** **PROMOTED into `current-truth` on 2026-07-18** (restart + three-pose + API-now + center LMB).  
Keep this file as discovery narrative; live authority is `docs/recovery/current-truth.md` / `.json`.

## Chain

```text
[rift_x64+0x32E07C0] → owner
  +0x320 / +0x324 / +0x328  → player XYZ (float)
  +0x300                    → cumulative rotation counter (legacy; not direct heading)
  +0x304                    → matches heading float (same value as cam+0x158 this session)
  +0x330                    → camera-state child
      +0x08/+0x0C/+0x10     → camera position
      +0x14/+0x18/+0x1C     → look-at / player-on-camera
      +0x38                 → FOV degrees (75)
      +0x3C                 → near
      +0x158                → heading radians (revalidated; matches cam look-at yaw)
```

Old July roots `0x32EBC80` / `0x32EBDC0` are **null** on this binary. Do not use them.

## Evidence

| Gate | Result | Artifact |
|---|---|---|
| API-now family seed | passed | `scripts/captures/family-scan-currentpid-26916-20260718-164435-926620/` |
| Module `.data` root reseed | `0x32E07C0` | `scripts/captures/owner-root-reseed-currentpid-26916-20260718-165500/` |
| Same-pose API vs chain | Δ ≈ 0.003 | readback captures |
| **Restart survival** | **passed** (PID 26916 → 21436; owner heap changed) | `scripts/captures/owner-root-restart-survival-currentpid-21436-20260718-170030/` |
| W2S / S2W round-trip | planar error **0.0 m** on look-at/body | `scripts/world-to-screen.py --round-trip` |
| Three-pose displacement | **not run** | needs movement approval |
| `current-truth` update | **not done** | needs explicit approval |

## Live read (post-restart example)

| Field | Value |
|---|---|
| PID / HWND | `21436` / `0x710A94` |
| Module base | `0x7FF696620000` |
| Owner | `0x1D00C8B06B0` (session heap; changes each start) |
| Root RVA | **`0x32E07C0`** (stable) |

```powershell
python scripts\static_owner_coordinate_chain_readback.py --pid <pid> --hwnd <hwnd> --module-base <base> --root-rva 0x32E07C0 --coord-offset 0x320 --samples 2 --json

python scripts\world-to-screen.py --pid <pid> --round-trip --json
python scripts\world-to-screen.py --pid <pid> --screen-x 426 --screen-y 266 --json
```

## W2S notes

- Camera forward = `normalize(lookAt − camPos)` (not the `+0x2C` triple; that field is unit-length but not usable look dir on this patch).
- S2W = camera ray ∩ horizontal plane at ground Y (default look-at Y). Approximate; not engine navmesh hit.
- Prefer SendInput center/projected click via existing harness when testing C2M; legacy `--click` uses PostMessage and is weak for RIFT.

## Safety

No automatic truth promotion. Movement / ProofOnly / x64dbg / CE remain gated.
