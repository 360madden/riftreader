# Static Owner Coordinate Chain — Survived Reboot/Re-login

Generated UTC: `2026-05-27T18:18:00Z`
Repo: `C:\RIFT MODDING\RiftReader`

# **✅ STRONG CURRENT CANDIDATE — NOT PROMOTED YET**

The newly discovered player-coordinate pointer chain survived a full game logout/reboot/re-login process epoch change.

Best chain:

```text
[rift_x64 + 0x32EBC80] + 0x320/+0x324/+0x328
```

This is the current best static owner-coordinate chain candidate. It is **not yet promoted** because the independent live API-now vs chain-now validation is blocked by stale/unhealthy ChromaLink/world-state output.

---

## Why this report exists

This file intentionally duplicates the key handoff evidence as a standalone backup so the chain is not lost across context switches, stale current-truth docs, dirty worktrees, or future game restarts.

Use this file as the high-priority recovery note if other handoff context is missing.

---

## Chain summary

| Field | Value |
|---|---|
| Chain | `[rift_x64 + 0x32EBC80] + 0x320/+0x324/+0x328` |
| Root module | `rift_x64.exe` |
| Root RVA | `0x32EBC80` |
| Root address with current module base | `0x7FF77E22BC80` |
| Coordinate field offset | `+0x320/+0x324/+0x328` |
| Historical shape match | `owner+0x320/+0x324/+0x328` |
| Current classification | `static-owner-layout-coordinate-chain-candidate-current-session` |
| Promotion state | `not-promoted` |
| Promotion blocker | `api-now-vs-chain-now-not-complete` |

---

## Reboot/re-login survival evidence

The game logged out due to idle and was rebooted/re-entered into world. The process epoch changed, but the root RVA and coordinate offset still resolved correctly.

| Field | Pre-reboot epoch | Post-reboot epoch |
|---|---:|---:|
| PID | `12148` | `34176` |
| HWND | `0x640C0C` | `0x3D1544` |
| Process start UTC | `2026-05-27T01:17:01.265352Z` | `2026-05-27T18:06:53.0701460Z` |
| Module base | `0x7FF77AF40000` | `0x7FF77AF40000` |
| Root address | `0x7FF77E22BC80` | `0x7FF77E22BC80` |
| Owner pointer read from root | `0x238679C06A0` | `0x278C3830010` |
| Coordinate address | `0x238679C09C0` | `0x278C3830330` |
| X | `7259.5908203125` | `7259.5908203125` |
| Y | `821.5345458984375` | `821.5345458984375` |
| Z | `2988.985107421875` | `2988.985107421875` |
| Readback verdict | `passed` | `passed` |

Key interpretation: owner heap address changed as expected across process epochs, but the static root RVA and coordinate field offset survived. This is exactly the expected behavior for a useful static pointer chain.

---

## Current live target epoch to use

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `34176` |
| HWND | `0x3D1544` |
| Window title | `RIFT` |
| Process start UTC | `2026-05-27T18:06:53.0701460Z` |
| Module base | `0x7FF77AF40000` |
| Window baseline screenshot | [`C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260527-140857-183.png`](C:\RIFT%20MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260527-140857-183.png) |

Do not use old PID/HWND `12148 / 0x640C0C` as current truth. Those addresses are historical now.

---

## Primary readback artifacts

| Artifact | Purpose | Verdict |
|---|---|---|
| [`C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-180907-440028\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-180907-440028\summary.json) | Post-reboot chain readback, PID `34176` | `passed` |
| [`C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-candidate-20260527-175818-641508\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-candidate-20260527-175818-641508\summary.json) | First PID `12148` owner-chain candidate packet | `passed` |
| [`C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-175915-451509\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-175915-451509\summary.json) | Reusable helper readback in PID `12148` | `passed` |
| [`C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-27-1811-post-reboot-static-chain-reacquisition.md`](C:\RIFT%20MODDING\RiftReader\docs\handoffs\2026-05-27-1811-post-reboot-static-chain-reacquisition.md) | Reacquisition handoff | `static-owner-chain-reacquired-after-reboot` |
| [`C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-27-1800-static-owner-chain-candidate.md`](C:\RIFT%20MODDING\RiftReader\docs\handoffs\2026-05-27-1800-static-owner-chain-candidate.md) | Original static owner chain handoff | `current-session-static-module-root-owner-plus-0x320-coordinate-chain` |

---

## Discovery path evidence

The chain was found from a bounded x64dbg access-provenance hit against the old proof anchor in PID `12148`.

Hardware watch hit:

| Field | Value |
|---|---|
| Watched address | `0x23863A26E50` |
| Hit RIP | `0x7FF83181121C` |
| Immediate module | `VCRUNTIME140.dll` |
| Immediate instruction | `mov dword ptr ds:[rax+0x08], ecx` |
| Candidate triplet at hit | `7259.5908203125, 821.5345458984375, 2988.985107421875` |

Important RIFT caller RVAs exposed by stack/disassembly:

| RVA | Role |
|---:|---|
| `0x0847513` / return `0x0847518` | Copies upstream source coordinate into proof/playerPosition registry |
| `0x1138378` / return `0x113837D` | Registry copy shim calls buffer helper |
| `0x116299F` / return `0x11629A4` | Buffer copy helper calls CRT/memcpy-like routine |

Static disassembly then showed `rift_x64+0x488EA0` returns the singleton rooted at `rift_x64+0x32EBC80`, and that singleton carries the live coordinate field at `+0x320`.

---

## Secondary chain to treat cautiously

A secondary proof/playerPosition registry chain was also observed before reboot:

```text
[[rift_x64 + 0x32FFB68] + 0x0] + 0x40
```

Before reboot it resolved to descriptor `playerPosition` and proof anchor `0x23863A26E50`. After reboot it did **not** reacquire cleanly:

[`C:\RIFT MODDING\RiftReader\scripts\captures\static-playerposition-chain-readback-20260527-180907-700748\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\static-playerposition-chain-readback-20260527-180907-700748\summary.json)

Policy: keep this as secondary/historical until separately re-derived. Do not let it distract from the owner chain that survived reboot.

---

## Current blocker before promotion

API-now vs chain-now is blocked because the ChromaLink/world-state reference was stale/unhealthy:

[`C:\RIFT MODDING\RiftReader\scripts\captures\chromalink-world-state-reference-20260527-180955-988757\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\chromalink-world-state-reference-20260527-180955-988757\summary.json)

Blockers recorded:

- `world-state-not-healthy`
- `world-state-player-position-not-fresh`
- `world-state-player-position-stale`
- `world-state-navigation-player-position-unavailable`

Until a fresh independent live API/runtime coordinate matches `[rift_x64+0x32EBC80]+0x320`, this chain remains candidate evidence, not promoted truth.

---

## Reusable validation command

For the current PID/HWND epoch:

```powershell
python .\scripts\static_owner_coordinate_chain_readback.py --pid 34176 --hwnd 0x3D1544 --module-base 0x7FF77AF40000 --expected-proof-anchor "" --json
```

Expected current result shape:

```json
{
  "status": "passed",
  "verdict": "static-module-root-owner-plus-0x320-coordinate-chain-resolved",
  "ownerAddress": "0x278C3830010",
  "coordinate": {
    "x": 7259.5908203125,
    "y": 821.5345458984375,
    "z": 2988.985107421875
  }
}
```

---

## Safety / non-promotion ledger

| Field | Result |
|---|---:|
| Cheat Engine used | false |
| DebugActiveProcessStop used for this chain | false |
| x64dbg needed after chain discovery | false for reboot reacquisition |
| Live input/movement during reboot reacquisition | false |
| Provider writes | false |
| Proof promotion | false |
| Actor/static-chain promotion | false |
| Git mutation | false |

---

## Required future promotion gates

| Gate | Current status |
|---|---|
| Static owner-chain discovered | passed |
| Restart/re-login survival | passed |
| Fresh API-now vs chain-now | blocked/pending |
| Movement/displacement coordinate delta | not required for documentation; useful after API source is healthy |
| Current-truth proof/current target refresh | pending |
| Explicit promotion approval | not granted |

---

## Bottom line

Preserve this chain:

```text
[rift_x64 + 0x32EBC80] + 0x320/+0x324/+0x328
```

It is the best known static player-coordinate chain candidate and has survived reboot/re-login. The next work should focus on restoring a fresh independent live coordinate source and validating API-now vs chain-now, not on broad pointer scans or the stale secondary proof-buffer chain.

<!-- DYNAMIC_VALIDATION_UPDATE_START -->

## Subsequent targeted displacement validation

Updated UTC: `2026-05-27T18:44:55Z`

The same chain also responded to bounded approved live displacement on PID `34176` / HWND `0x3D1544`:

| Segment | Evidence |
|---|---|
| Baseline -> `W` 450ms | Visual change `25.5139%`; chain X/Z planar delta `2.885784736` |
| Forward -> `S` 450ms | Visual change `21.7778%`; chain X/Z planar delta `1.449597826` |

Backup report:

- Markdown: `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-displacement-validation-2026-05-27.md`
- JSON: `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-displacement-validation-2026-05-27.json`

Promotion status remains unchanged: **candidate, not promoted** because API-now vs chain-now is still blocked by stale/unhealthy ChromaLink world-state.

<!-- DYNAMIC_VALIDATION_UPDATE_END -->

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
