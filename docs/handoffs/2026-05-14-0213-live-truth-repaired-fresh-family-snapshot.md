# Live truth repaired + fresh family snapshot handoff

_Last updated: 2026-05-14 02:13 UTC._

## Verdict

`ReaderBridge` now provides the live RRAPICOORD-compatible truth marker, and current preflight is back to `ready-for-read-only-proof`. Movement is still blocked. The newest selected candidate is `family-snapshot-hit-000001` at `0x268D1FA6120` from a fresh broad current-PID family snapshot; it matched the fresh reference in read-only pose readback with `ReferenceMatchCount=8`, but there is still no movement-grade proof anchor, restart validation, or static pointer chain.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `2928` |
| HWND | `0xC0994` |
| Process start | `2026-05-13T16:17:56.208370Z` |
| Module base | `0x7FF71CD90000` |
| Movement | `blocked` |
| CE/x64dbg | Not used |

## New truth-source evidence

| Artifact | Result |
|---|---|
| `addon/ReaderBridge/ReaderBridge.lua` | Emits `ReaderBridge_RRAPICOORD1` from live `Inspect.Unit.Detail(player)` data, with `source=rift-api`, `view=Inspect.Unit.Detail(player)`, and `savedVariablesUse=none`. |
| `cmd /c scripts\validate-addon.cmd` | Passed Lua syntax validation for 4 addons. |
| `cmd /c scripts\deploy-addon.cmd` | Deployed addon source to both discovered AddOns roots. |
| Exact-target `/reloadui` | Sent only to PID `2928` / HWND `0xC0994`; no movement. |
| `scripts/captures/coordinate-proof-preflight-20260514-020050-354005/summary.json` | Passed: `ready-for-read-only-proof`; movement false. |
| `scripts/captures/rift-api-reference-currentpid-2928-20260514-020051.json` | Fresh RRAPICOORD reference: `7402.0, 871.78, 3029.4199`. |
| `scripts/captures/rrapicoord-scan-diagnostics-20260514-020126-043153/summary.json` | Passed: `1` usable marker. |
| `scripts/captures/rrapicoord-addon-state-diagnostics-20260514-020130-043012/summary.json` | Passed: addon installed and live marker observed. |

## New family snapshot / readback evidence

| Artifact | Result |
|---|---|
| `scripts/captures/riftscan-proof-pose-20260514-020200/` | Old `0x268E113FED0` candidate failed against the new fresh reference (`ReferenceMatchCount=0`); historical seed only now. |
| `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-020258/family-snapshot-summary.json` | Broad snapshot over `0x268D0000000`-`0x268E8000000`; `327,319,552` bytes scanned; `42,209` plausible triplets; `23` near-reference triplets. |
| `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-020258/family-import-candidates.json` | New import candidate packet with `50` candidates. |
| `scripts/captures/riftscan-proof-pose-20260514-020339/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-220346.json` | Passed read-only pose readback: `ReferenceMatchCount=8`, best `family-snapshot-hit-000001` at `0x268D1FA6120`, stable across `4` samples. |
| `scripts/captures/pointer-family-scan-20260514-021115-344001/summary.json` | Bounded pointer scan: `24` targets, top family base has heap hits only; `0` module/RIFT-module hits. |
| `scripts/captures/pointer-owner-batch-currentpid-2928-20260514-021250-664397/summary.json` | `16` owner windows inspected; `0` module-RVA hints. |
| `scripts/captures/riftscan-milestone-review-20260514-021300.json` | Strategy gate selects the new family candidate file and keeps `movementAllowedByReview=false`. |

## Proven truth vs candidate-only

| Item | Status |
|---|---|
| Live reference surface | Repaired via `ReaderBridge_RRAPICOORD1`; current enough for read-only proof. |
| ChromaLink world-state | Still stale/unhealthy. |
| `family-snapshot-hit-000001` / `0x268D1FA6120` | Strong current same-pose candidate; not movement proof. |
| Old `0x268E113FED0` lead | Historical seed only after failing new-reference readback. |
| Static pointer chain | Not proven. |
| Movement/navigation use | Blocked until current proof anchor/static chain and same-target `ProofOnly` pass. |

## Resume prompt

Resume in `C:\RIFT MODDING\RiftReader` on `main`. Read `docs/recovery/current-truth.md` and this handoff first. Use `ReaderBridge_RRAPICOORD1` / RRAPICOORD as the repaired live reference surface; do not use SavedVariables as live truth. Current target is PID `2928`, HWND `0xC0994`. The newest candidate file is `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-020258/family-import-candidates.json`; selected candidate is `family-snapshot-hit-000001` at `0x268D1FA6120`, backed by `scripts/captures/riftscan-proof-pose-20260514-020339/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-220346.json` (`ReferenceMatchCount=8`). Movement remains blocked. Next best work is bounded read-only owner/static-chain investigation or multi-pose proof planning; do not navigate, poll movement, use stale PID `57656`, use old absolute addresses as current truth, or promote without same-target ProofOnly/static-chain proof.
