# RiftReader Current Truth

_Last updated: 2026-05-14T21:42:09.699992Z._

## Verdict

**Coordinate proof remains restored for the active RIFT target.** PID `23496` / HWND `0x2C1024` has a same-PID/HWND no-CE multi-pose proof anchor and the latest same-target `ProofOnly` passed with `movementSent=false`.

Movement/navigation is still subject to each profile's normal exact-target, proof-age, readback, and input-safety gates, but the coordinate proof gate is currently satisfied for this process epoch.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `23496` |
| HWND | `0x2C1024` |
| Window title | `RIFT` |
| Process start | `2026-05-14T20:02:28.245722Z` |
| Module base | `0x7FF71CD90000` |
| ProofOnly | `passed-proof-only` |
| Movement sent by ProofOnly | `false` |
| Current coordinate | `x=7312.89453125, y=875.28466796875, z=3050.156005859375` |
| Coordinate recorded | `2026-05-14T21:42:09.0269307Z` |

## Current proof anchor

| Field | Value |
|---|---|
| Candidate | `api-family-hit-000005` |
| Address | `0x27236F46750` |
| Region base | `0x27236F46710` |
| Region offset | `0x40` |
| Axis order | `xyz` |
| Support count | `4` |
| Proof support count | `4` |
| Latest max abs distance | `0.007873437499256397` |
| Candidate file | `C:\RIFT MODDING\RiftReader\scripts\captures\family-scan-currentpid-23496-20260514-204452-232834\api-family-vec3-candidates.json` |
| Candidate JSONL | `C:\RIFT MODDING\RiftReader\scripts\captures\family-scan-currentpid-23496-20260514-204452-232834\api-family-vec3-candidates.jsonl` |
| Proof anchor cache | `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json` |
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` |

## Displacement proof

| Field | Value |
|---|---|
| Pose count | `2` |
| Max reference planar displacement | `4.285970374371978` |
| Max candidate/reference delta error | `0.006023046874815918` |
| Promotion result | `validated` |
| Pose A readback | `scripts/captures/fast-proof-lane-pid23496-promote-poses-20260514-1650/riftscan-proof-poseA-displaced1-20260514-205119/riftscan-riftreader-currentpid-23496-readback-wrapper-summary-20260514-165156.json` |
| Pose B readback | `scripts/captures/fast-proof-lane-pid23496-promote-poses-20260514-1650/riftscan-proof-poseB-displaced2-20260514-205249/riftscan-riftreader-currentpid-23496-readback-wrapper-summary-20260514-165322.json` |

## Latest validation

| Check | Result |
|---|---|
| Target-control | `passed-target-control` / `exact-hwnd-foreground` |
| Target-control artifact | `C:\RIFT MODDING\RiftReader\scripts\captures\do-1-8-pid23496-proofonly-20260514-174113\live-test-ProofOnly-20260514-214114\target-control\target-control-status.json` |
| Readback assertion | `valid` |
| Movement allowed by current proof pointer | `true` |
| Readback summary | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-23496-readback-summary-20260514-174203.json` |
| ProofOnly | `passed-proof-only` |
| ProofOnly run | `C:\RIFT MODDING\RiftReader\scripts\captures\do-1-8-pid23496-proofonly-20260514-174113\live-test-ProofOnly-20260514-214114\run-summary.json` |
| ProofOnly movement | `movementSent=false`, `movementAttempted=false` |
| Cheat Engine | `not used` |
| SavedVariables as live truth | `not used` |

## Historical / stale evidence

| Item | Status |
|---|---|
| PID `16536` / address `0x21487DF8F64` | Historical/stale after client close; recovery evidence only. |
| PID `2928` candidates | Historical/stale target epoch. |
| x64dbg access proof from PID `16536` | Structural recovery evidence only; not current movement truth. |

## Required before any movement profile

1. Reconfirm exact PID/HWND target-control.
2. Enforce proof-anchor max-age/readback gates.
3. Use `ProofOnly` as the immediate freshness gate before movement work.
4. Keep `api-family-hit-000005 @ 0x27236F46750` scoped to PID `23496` / HWND `0x2C1024` only.
5. Do not reuse PID `16536` address `0x21487DF8F64` as current truth.
6. If `ProofOnly` fails, start with current-PID family scan, not old-address probing.
7. Do not use x64dbg/static-chain unless the fast proof lane fails.
8. Treat this proof pointer as stale after any client restart, PID/HWND change, logout/close, or failed freshness gate.
