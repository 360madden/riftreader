# Compact handoff — no-debug static owner-chain discovery extension

Updated UTC: `2026-05-27T20:04:30Z`
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main` tracking `origin/main`

## TL;DR

Continued the player actor/static pointer-chain discovery lane using only
read-only current-PID memory reads. The existing static resolver candidate still
resolves cleanly:

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`

New evidence strengthens the static-owner/root relationship:

- exact PID/HWND check passed for PID `34176` / HWND `0x3D1544`;
- static root `rift_x64+0x32EBC80` still points to owner `0x278C3830010`;
- owner `0x278C3830010` contains a module/vtable-heavy object layout;
- pointer-family scan found one `rift_x64.exe` module hit to the owner at
  `0x7FF77E22BC80`, the expected static root;
- coordinate field `0x278C3830330` has no direct pointer-family refs in a
  focused scan, which fits the field being embedded at owner `+0x320`.

This is still **candidate-only** and **not promoted**.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID / HWND | `34176` / `0x3D1544` |
| Process start UTC | `2026-05-27T18:06:53.0701460Z` |
| Module base | `0x7FF77AF40000` |
| Static root | `rift_x64+0x32EBC80` = `0x7FF77E22BC80` |
| Current owner | `0x278C3830010` |
| Coordinate field | `0x278C3830330` |
| Coordinate offsets | `+0x320/+0x324/+0x328` |

## New no-debug artifacts

| Check | Result | Artifact |
|---|---|---|
| Static owner-chain readback | `passed`; owner `0x278C3830010`; coord `7259.949707031, 821.437561035, 2990.375732422` | `scripts/captures/static-owner-coordinate-chain-readback-20260527-200107-566800/summary.json` |
| Owner neighborhood inspection | `passed`; `255` interesting matches; `177` module pointers; `12` owner-window module pointers; `7` exact owner self refs | `scripts/captures/pointer-owner-neighborhood-inspector-20260527-200201-853835/summary.json` |
| Owner pointer-family scan | `passed`; `26` hits to owner; `1` `rift_x64.exe` module hit at `0x7FF77E22BC80`; warning: elapsed budget reached after discovery | `scripts/captures/pointer-family-scan-20260527-200236-877935/summary.json` |
| Coordinate-field pointer scan | `passed`; `0` direct pointer hits to `0x278C3830330` | `scripts/captures/pointer-family-scan-20260527-200328-634938/summary.json` |
| Owner-layout comparison packet | `blocked` only on promotion/proof gates; recognizes current static owner resolver and separates stale PID `12148` proof-family artifacts | `scripts/captures/owner-layout-comparison-packet-20260527-200911-671622/summary.json` |
| RiftScan milestone review | `blocked`; confirms stale PID `12148` proof pointer and no current selected RiftScan candidate for PID `34176` | `scripts/captures/riftscan-milestone-review-20260527-200952.json` |
| Fresh RRAPICOORD/API refresh | `blocked`; no usable RRAPICOORD marker in attempt 3 scan; `12` hits, `0` usable markers | `scripts/captures/rrapicoord-scan-diagnostics-20260527-201612-575793/summary.json` |
| ChromaLink world-state reference | `blocked`; world-state not healthy/fresh enough for player position | `scripts/captures/chromalink-world-state-reference-20260527-201624-468822/summary.json` |

## Owner layout highlights

| Offset | Value | Meaning |
|---:|---|---|
| `+0x0` | `0x7FF77D58CEB8` / RVA `0x264CEB8` | vtable/module pointer |
| `+0x8` | `0x7FF77D58CEA8` / RVA `0x264CEA8` | module pointer |
| `+0x18` | `0x7FF77B4AC5F0` / RVA `0x56C5F0` | module pointer |
| `+0x20` | `0x7FF77D589218` / RVA `0x2649218` | repeated module pointer |
| `+0x28` | `0x7FF77D589208` / RVA `0x2649208` | repeated module pointer |
| `+0x320` | `7259.949707031` | X coordinate field |
| `+0x324` | `821.437561035` | Y coordinate field |
| `+0x328` | `2990.375732422` | Z coordinate field |

## Current blockers

- `explicit-promotion-approval-not-given`
- `no-static-resolver-promoted`
- stale PID `12148` proof pointer still blocks proof/movement reuse
- no new same-target `ProofOnly` run was performed in this no-input slice
- RiftScan strategy gate remains blocked for this target because the selected
  proof pointer is still PID `12148`, not current PID `34176`
- fresh API-now validation cannot be refreshed until RRAPICOORD emits a usable
  marker again or ChromaLink world-state returns a healthy/fresh player position

## Helper update in this slice

- `scripts/rift_live_test/owner_layout_comparison_packet.py` now consumes
  `current-truth.staticChainStatus.primaryCandidate` and the latest no-debug
  static-owner discovery packet.
- `scripts/test_owner_layout_comparison_packet.py` now covers the static
  resolver path and verifies it remains candidate-only/not promoted.

## Safety ledger

| Boundary | Status |
|---|---|
| Cheat Engine | Not used |
| x64dbg attach / breakpoints / watchpoints | Not used |
| DebugActiveProcessStop | Not called |
| Live input / movement | Not used |
| Provider repo writes | None |
| Proof/static-chain promotion | Not done |
| Git mutation before this handoff | None |

## Next best safe action

If continuing without promotion, restore a fresh live API/reference source
first. Then rerun API-now vs static-chain-now immediately before any promotion
review and keep stale PID `12148` proof-family evidence separate from the
current static resolver. Promotion, live input, debugger attach, CE, provider
writes, and Git push still require explicit approval.
