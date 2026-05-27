# Compact handoff — extended static root read-only discovery

Updated UTC: `2026-05-27T20:28:54Z`
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main` tracking `origin/main`, local branch ahead of origin

## TL;DR

Continued player actor/static pointer-chain discovery in the safe no-input lane.
The current static chain remains:

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`

New read-only evidence strengthens the module-root relationship:

- extended owner pointer-family scan still found exactly one `rift_x64.exe`
  module hit to owner `0x278C3830010`;
- that module hit is the known static root `0x7FF77E22BC80`
  (`rift_x64+0x32EBC80`);
- depth-1 refs from the owner scan had no additional upstream hits in the
  bounded run;
- module-root neighborhood inspection found exactly one direct owner pointer at
  the static root address and no direct coordinate-field pointer refs.

The chain is still **candidate-only / promotion-review-ready / not promoted**.

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
| Coordinate offset | `owner+0x320/+0x324/+0x328` |

## New artifacts

| Check | Result | Artifact |
|---|---|---|
| Coordinate status refresh | `blocked`; stale proof pointer PID `12148`, live PID `34176` | console-only safe check |
| Extended owner pointer-family scan | `passed`; scanned `20` targets, `1` remaining queue item, `20` owner hits, `1` `rift_x64.exe` module hit at `0x7FF77E22BC80`; elapsed budget reached after useful result | `scripts/captures/pointer-family-scan-20260527-202627-130980/summary.json` |
| Module static-root neighborhood | `passed`; `380` interesting matches, `379` module pointers, `4` owner-window module pointers, exactly `1` owner pointer at `0x7FF77E22BC80`, `0` direct coordinate-field pointer hits | `scripts/captures/pointer-owner-neighborhood-inspector-20260527-202759-882715/summary.json` |
| ChromaLink blocked detail | position snapshot observed at `2026-05-27T17:41:25.9567639Z`, age about `9,298,239 ms`; not fresh | `scripts/captures/chromalink-world-state-reference-20260527-201624-468822/world-state.json` |

## Interpretation

| Evidence | Meaning |
|---|---|
| `0x7FF77E22BC80 -> 0x278C3830010` | Current module-root-to-owner edge is present at the expected RVA. |
| `0x278C3830010 + 0x320 = 0x278C3830330` | Current owner-to-coordinate field matches the historical actor-like owner shape. |
| Coordinate field has no direct pointer refs | Supports the field being embedded in the owner rather than a separate pointer target. |
| Depth-1 owner refs had no upstream hits | No better static parent/root emerged from the bounded no-debug scan. |
| ChromaLink/RRAPICOORD remain blocked | Fresh API-now validation cannot be refreshed yet. |

## Current blockers

- `explicit-promotion-approval-not-given`
- `no-static-resolver-promoted`
- stale PID `12148` proof pointer still blocks proof/movement reuse
- fresh API/reference source unavailable:
  - RRAPICOORD scan has no usable marker;
  - ChromaLink player position is stale/not healthy for proof-grade position

## Safety ledger

| Boundary | Status |
|---|---|
| Cheat Engine | Not used |
| x64dbg attach / breakpoints / watchpoints | Not used |
| DebugActiveProcessStop | Not called |
| Live input / movement | Not used |
| Provider repo writes | None |
| Proof/static-chain promotion | Not done |

## Next safe action

Restore a fresh live API/reference source before any promotion review. Once
RRAPICOORD or ChromaLink provides a fresh player coordinate again, rerun
API-now vs static-chain-now immediately and keep the stale PID `12148`
proof-family evidence separate from the PID `34176` static resolver.
