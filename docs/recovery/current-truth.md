# Current RIFT live truth — post-patch static root **PROMOTED**

Updated UTC: `2026-07-18T18:15:39.846184+00:00`

## **✅ CURRENT — root `0x32E07C0`**

| Field | Value |
|---|---|
| PID / HWND | `32636` / `0x620dd8` |
| Process start UTC | `2026-07-18T18:11:46.6194619Z` |
| Module base | `0x7FF696620000` |
| **Root RVA** | **`0x32E07C0`** |
| Chain | **`[rift_x64+0x32E07C0]+0x320/+0x324/+0x328`** |
| Owner (session heap) | Reacquire every attach — **do not hardcode** (e.g. last: `0x179BB4106A0`) |
| Camera child | `[owner+0x330]` |
| Heading | `[[owner+0x330]+0x158]` (radians) |
| Machine JSON | `docs/recovery/current-truth.json` |
| **C2M uses this truth?** | **Yes** — `c2m_run_to_goal --use-current-truth` (default on, fail closed) |
| **Root restart-survivable?** | **Yes** — RVA `0x32E07C0` survives; rebind PID/HWND/start after relaunch |

### Gates passed (2026-07-18)

| Gate | Result | Artifact |
|---|---|---|
| Static resolver complete | ✅ | reseed + readback |
| Restart / relog survival | ✅ PID `26916` → `21436` | `scripts/captures/owner-root-restart-survival-currentpid-21436-20260718-170030/` |
| Restart #2 + C2M | ✅ PID `21436` → `32636`; hand-picked 5/5 | `scripts/captures/c2m-run-to-goal-20260718-181321/` |
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
# Prefer truth bind (always current PID/HWND after rebind):
python scripts\static_owner_pose_now.py --json
python scripts\static_owner_coordinate_chain_readback.py --use-current-truth --samples 2 --json
```

### W2S / S2W

```powershell
python scripts\world-to-screen.py --pid <live-pid> --round-trip --json
```

Forward = `normalize(lookAt − camPos)` from camera child `+0x14`; FOV at `+0x38`.

### C2M

```powershell
python scripts\c2m_run_to_goal.py --execute --stimulus-approved `
  --use-current-truth --pose-source static-chain --aim-mode w2s --heading-prestep `
  --waypoints-json scripts\routes\safe-handpicked-a-reverse.json --json
```

Full contract: [`c2m-truth-bind-and-static-chain-restart-survival.md`](c2m-truth-bind-and-static-chain-restart-survival.md).

### Historical backup

Previous truth JSON (pre-promote):  
`docs/recovery/historical/current-truth-before-0x32E07C0-promote-20260718-171122.json`

### Operator rules

- Re-bind PID / HWND / process-start after every restart (**truth target rebind**).
- Never hardcode heap owner addresses — only **RVA `0x32E07C0` + offsets**.
- C2M uses this truth by default; mismatch → fail closed.
- Full actor/stat graph is **not** promoted; coordinates (+ heading candidate) only.
- CE / x64dbg remain separately gated.

### Durable progress / handoff

| Doc | Role |
|---|---|
| [`c2m-truth-bind-and-static-chain-restart-survival.md`](c2m-truth-bind-and-static-chain-restart-survival.md) | **C2M truth + restart survival (library)** |
| [`progress-2026-07-18-post-patch-root-and-c2m.md`](progress-2026-07-18-post-patch-root-and-c2m.md) | Full milestone notes (gates, tools, decisions, next) |
| [`post-patch-static-root-candidate-2026-07-18.md`](post-patch-static-root-candidate-2026-07-18.md) | Discovery narrative (promoted; keep for history) |
