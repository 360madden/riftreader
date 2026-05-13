# Navigation coord recovery handoff — owner structural signature

## TL;DR

The player-candidate owner `0x268D753AE30` is now ranked as the clear best
structural owner candidate across the three low-noise type instances.

It is the only owner that combines:

- module fields `0x26AAE70`, `0x272DBC0`, `0x263E950`, `0x2657C80`
- selected `0x263E950` at owner offset `+0xE0`
- coord pointer field `[+0x10] = 0x268DF21ED20`
- stable coord-candidate classification and readable vec3
- parent slot `0x268D7539700` with module hint

This is still candidate-only. The unresolved gap remains the static/root source
above parent slot `0x268D7539700`. Movement stays blocked.

## Primary artifact

- `scripts/captures/owner-structural-signature-packet-20260513-223357-049150/summary.json`
- Markdown companion: `scripts/captures/owner-structural-signature-packet-20260513-223357-049150/summary.md`

## Owner ranking

| Rank | Owner | Score | Matched RVAs | Missing RVAs | Stable coord candidate | Parent slot | Interpretation |
|---:|---|---:|---|---|---:|---|---|
| 1 | `0x268D753AE30` | `270` | `0x26AAE70`, `0x272DBC0`, `0x263E950`, `0x2657C80` | none | `true` | `0x268D7539700` | Best structural owner candidate. |
| 2 | `0x268C6A10EA0` | `85` | `0x26AAE70`, `0x272DBC0` | `0x263E950`, `0x2657C80` | `false` | `0x268B0DD1168` | Sibling/control, not stable coord candidate. |
| 3 | `0x268923AF610` | `75` | `0x26AAE70`, `0x272DBC0` | `0x263E950`, `0x2657C80` | `false` | `0x268E2A78628` | Sibling/control, not stable coord candidate. |

## Best-owner module fields

| Owner offset | Storage | Value | RVA |
|---:|---|---|---|
| `+0x0` | `0x268D753AE30` | `0x7FF71F43AE70` | `0x26AAE70` |
| `+0x8` | `0x268D753AE38` | `0x7FF71F4BDBC0` | `0x272DBC0` |
| `+0xE0` | `0x268D753AF10` | `0x7FF71F3CE950` | `0x263E950` |
| `+0x110` | `0x268D753AF40` | `0x7FF71F3E7C80` | `0x2657C80` |

## What changed

| File | Purpose |
|---|---|
| `scripts/rift_live_test/owner_structural_signature_packet.py` | Offline owner structural-signature ranker. |
| `scripts/owner_structural_signature_packet.py` | Thin CLI wrapper. |
| `scripts/test_owner_structural_signature_packet.py` | Unit coverage for RVA extraction and owner scoring. |
| `docs/recovery/current-truth.md` | Added owner structural-signature result and preserved candidate-only gate. |

## Current gate

| Gate | Status | Note |
|---|---:|---|
| Current target | ✅ present | PID `2928`, HWND `0xC0994` from previous target-control state. |
| Target-control / visual gate | ✅ last passed | Must be refreshed before live input. |
| Same-target `ProofOnly` | ❌ blocked | Latest proof pointer is stale PID `57656`, HWND `0x5417BC`. |
| Coordinate proof promotion | ❌ not promoted | Structural signature is candidate-only. |
| Movement/navigation | ❌ blocked | No movement permitted from this evidence. |
| RiftScan milestone review | ❌ blocked as expected | `scripts/captures/riftscan-milestone-review-20260513-223425.json`: stale proof pointer + no selected candidate. |

## Validation

These checks passed:

```powershell
python -m py_compile scripts\rift_live_test\owner_structural_signature_packet.py scripts\owner_structural_signature_packet.py scripts\test_owner_structural_signature_packet.py
python scripts\test_owner_structural_signature_packet.py -v
python scripts\owner_structural_signature_packet.py --owner-instance-summary-json scripts\captures\owner-type-instance-inspector-20260513-215227-155967\summary.json --owner-parent-graph-json scripts\captures\owner-type-parent-graph-20260513-215906-263575\summary.json --parent-slot-summary-json scripts\captures\parent-slot-neighborhood-summary-20260513-220334-136540\summary.json --module-base 0x7FF71CD90000 --target-rva 0x26AAE70 --target-rva 0x272DBC0 --target-rva 0x263E950 --target-rva 0x2657C80 --json
```

## Resume prompt

Paste this into a fresh session:

> Resume `C:\RIFT MODDING\RiftReader` on `main`. Read
> `docs/recovery/current-truth.md` and newest handoff
> `docs/handoffs/2026-05-13-1832-navigation-owner-structural-signature.md`.
> Movement is blocked. Continue PC-heavy/offline static-owner discovery from
> best structural owner `0x268D753AE30`, parent slot `0x268D7539700`, coord
> pointer storage `0x268D753AE40`, and module-field signature
> `0x26AAE70/0x272DBC0/0x263E950/0x2657C80`. The unresolved gap is the static
> root above parent slot `0x268D7539700`; do not promote anything until
> API-now vs memory-now and same-target `ProofOnly` pass.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Build a parent-slot container search/ranker around `0x268D7539700`. | The root gap is above the parent slot, not inside the owner. |
| 2 | Search existing artifacts for the full owner module-field signature. | Full signature is much higher quality than single RVA hits. |
| 3 | Add a CSV/HTML export for owner signature rows. | Supports local PC-heavy review and quick visual comparison. |
| 4 | Compare parent-slot neighborhoods of all three sibling owners by relative pointer layout. | Identifies container/list fields shared across the family. |
| 5 | Build a reusable structural-signature query format. | Makes future restarts faster and less token-heavy. |
| 6 | Keep broad family snapshots as the primary live-data source when new poses are needed. | Highest signal per bounded run. |
| 7 | Avoid identical x64dbg attach retries. | Previous attempts failed before attach. |
| 8 | Keep RiftScan read-only unless explicitly authorized otherwise. | Preserves provider boundary. |
| 9 | Refresh target-control/visual gate before future live action. | Target/focus can drift. |
| 10 | Require same-target `ProofOnly` before navigation. | Prevents stale-pointer movement. |
