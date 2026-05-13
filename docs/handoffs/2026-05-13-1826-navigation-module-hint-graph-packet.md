# Navigation coord recovery handoff — module-hint graph packet

## TL;DR

The dominant `0x263E950` module-hint seed is now converted into an explicit
offline candidate graph:

`rift_x64.exe+0x263E950 -> 0x268D75396C0 -> 0x268D7539700 -> 0x268D753AE30 -> 0x268D753AE40 -> 0x268DF21ED20`

This is the clearest current source-chain map, but it is still candidate-only.
The unresolved gap is the static/module root above parent slot `0x268D7539700`.
Movement remains blocked.

## Primary artifact

- `scripts/captures/module-hint-graph-packet-20260513-222832-918691/summary.json`
- Markdown companion: `scripts/captures/module-hint-graph-packet-20260513-222832-918691/summary.md`

## Candidate chain

| Step | Kind | Value | Detail |
|---:|---|---|---|
| 1 | Module hint | `rift_x64.exe+0x263E950` | Selected dominant RVA. |
| 2 | Hint entry | `0x268D75396C0` | `-0x40` from parent slot. |
| 3 | Parent slot | `0x268D7539700` | Exact owner-slot source. |
| 4 | Owner | `0x268D753AE30` | `type-instance-player-candidate`. |
| 5 | Coord pointer storage | `0x268D753AE40` | `[owner+0x10]`. |
| 6 | Coord pointer | `0x268DF21ED20` | Stable candidate coord pointer, not proof. |

## Owner module-pointer fields

| Owner offset | Storage | Value | RVA | Note |
|---:|---|---|---|---|
| `+0x0` | `0x268D753AE30` | `0x7FF71F43AE70` | `0x26AAE70` | Low-noise type marker. |
| `+0x8` | `0x268D753AE38` | `0x7FF71F4BDBC0` | `0x272DBC0` | Secondary module field. |
| `+0xE0` | `0x268D753AF10` | `0x7FF71F3CE950` | `0x263E950` | Selected module hint. |
| `+0x110` | `0x268D753AF40` | `0x7FF71F3E7C80` | `0x2657C80` | Additional module field. |

## What changed

| File | Purpose |
|---|---|
| `scripts/rift_live_test/module_hint_graph_packet.py` | Offline graph builder joining module hint, parent slot, owner, and coord pointer evidence. |
| `scripts/module_hint_graph_packet.py` | Thin CLI wrapper. |
| `scripts/test_module_hint_graph_packet.py` | Unit coverage for module RVA conversion and graph linking. |
| `docs/recovery/current-truth.md` | Added graph-packet result and preserved candidate-only gate. |

## Current gate

| Gate | Status | Note |
|---|---:|---|
| Current target | ✅ present | PID `2928`, HWND `0xC0994` from prior target-control state. |
| Target-control / visual gate | ✅ last passed | Must be refreshed before live input. |
| Same-target `ProofOnly` | ❌ blocked | Latest proof pointer is stale PID `57656`, HWND `0x5417BC`. |
| Coordinate proof promotion | ❌ not promoted | Graph is candidate-only. |
| Movement/navigation | ❌ blocked | No movement permitted from this evidence. |
| RiftScan milestone review | ❌ blocked as expected | `scripts/captures/riftscan-milestone-review-20260513-222839.json`: stale proof pointer + no selected candidate. |

## Validation

These checks passed:

```powershell
python -m py_compile scripts\rift_live_test\module_hint_graph_packet.py scripts\module_hint_graph_packet.py scripts\test_module_hint_graph_packet.py
python scripts\test_module_hint_graph_packet.py -v
python scripts\module_hint_graph_packet.py --occurrence-summary-json scripts\captures\module-hint-occurrence-packet-20260513-222030-779335\summary.json --parent-slot-summary-json scripts\captures\parent-slot-neighborhood-summary-20260513-220334-136540\summary.json --owner-parent-graph-json scripts\captures\owner-type-parent-graph-20260513-215906-263575\summary.json --owner-instance-summary-json scripts\captures\owner-type-instance-inspector-20260513-215227-155967\summary.json --rva 0x263E950 --json
```

## Resume prompt

Paste this into a fresh session:

> Resume `C:\RIFT MODDING\RiftReader` on `main`. Read
> `docs/recovery/current-truth.md` and newest handoff
> `docs/handoffs/2026-05-13-1826-navigation-module-hint-graph-packet.md`.
> Movement is blocked. Continue PC-heavy/offline static-owner discovery from the
> graph path `0x263E950 -> 0x268D75396C0 -> 0x268D7539700 -> 0x268D753AE30 ->
> 0x268D753AE40 -> 0x268DF21ED20`. The unresolved gap is the root above parent
> slot `0x268D7539700`; do not promote anything until API-now vs memory-now and
> same-target `ProofOnly` pass.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Build a structural-signature search for owner objects with module fields `0x26AAE70`, `0x272DBC0`, `0x263E950`, and `0x2657C80`. | This is stronger than searching one offset. |
| 2 | Search for parent-slot containers that point to owners with `[+0x10]` coord-pointer shape. | The unresolved root likely sits above the parent slot. |
| 3 | Export the graph packet to CSV/HTML for local inspection. | Makes PC-heavy review easier and token-light. |
| 4 | Compare sibling owner graphs against the player-candidate graph. | Distinguishes common layout from player-specific path. |
| 5 | Rank owner module-field combinations across existing artifacts. | Finds repeatable class/type signatures. |
| 6 | Keep broad family snapshots as primary live-data method when new poses are needed. | Highest signal per bounded run. |
| 7 | Keep `0x268BEF2C000` de-prioritized unless new movement-vector evidence revives it. | Repeat readbacks showed instability. |
| 8 | Avoid identical x64dbg attach retries. | Previous attempts failed before attach. |
| 9 | Refresh target-control/visual gate before live actions. | Target/focus can drift. |
| 10 | Require same-target `ProofOnly` before navigation. | Prevents stale-pointer movement. |
