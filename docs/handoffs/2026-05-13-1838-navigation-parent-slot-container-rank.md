# Navigation coord recovery handoff — parent-slot container rank

## TL;DR

The root-search gap is now narrowed to parent slot `0x268D7539700`.

New offline ranker confirms `0x268D7539700` is the best parent-slot/container
seed above the best structural owner `0x268D753AE30`:

`0x268D7539700 -> 0x268D753AE30 -> [owner+0x10] 0x268D753AE40 -> 0x268DF21ED20`

This is still candidate-only. The unresolved problem is finding the static/root
container above `0x268D7539700`. Movement remains blocked.

## Primary artifact

- `scripts/captures/parent-slot-container-rank-20260513-224240-201501/summary.json`
- Markdown companion: `scripts/captures/parent-slot-container-rank-20260513-224240-201501/summary.md`
- CSV companion: `scripts/captures/parent-slot-container-rank-20260513-224240-201501/summary.csv`

## Parent-slot ranking

| Rank | Parent slot | Owner | Score | Selected RVA offset | Near-owner internal offsets | Stable coord candidate | Interpretation |
|---:|---|---|---:|---:|---|---:|---|
| 1 | `0x268D7539700` | `0x268D753AE30` | `285` | `-0x40` | `0x0`, `0x10`, `0x18`, `0x40`, `0x48`, `0x50`, `0x58`, `0x60` | `true` | Best root-search seed. |
| 2 | `0x268E2A78628` | `0x268923AF610` | `80` | `-0x3A8`, `-0x150` | `0x0` | `false` | Sibling/control. |
| 3 | `0x268B0DD1168` | `0x268C6A10EA0` | `73` | none | `0x0`, `0x8` | `false` | Sibling/control. |

## What changed

| File | Purpose |
|---|---|
| `scripts/rift_live_test/parent_slot_container_rank.py` | Offline parent-slot/container-root ranker with JSON/Markdown/CSV output. |
| `scripts/parent_slot_container_rank.py` | Thin CLI wrapper. |
| `scripts/test_parent_slot_container_rank.py` | Unit coverage for near-offset filtering and slot scoring. |
| `docs/recovery/current-truth.md` | Added parent-slot container-rank result and preserved candidate-only gate. |

## Current gate

| Gate | Status | Note |
|---|---:|---|
| Current target | ✅ present | PID `2928`, HWND `0xC0994` from previous target-control state. |
| Target-control / visual gate | ✅ last passed | Must be refreshed before live input. |
| Same-target `ProofOnly` | ❌ blocked | Latest proof pointer is stale PID `57656`, HWND `0x5417BC`. |
| Coordinate proof promotion | ❌ not promoted | Parent-slot rank is candidate-only. |
| Movement/navigation | ❌ blocked | No movement permitted from this evidence. |

Latest RiftScan milestone review:
`scripts/captures/riftscan-milestone-review-20260513-225757.json` (`.md`
companion) is **blocked**. The stale-pointer root problem is corrected: target
pointer match now passes against PID `2928` / HWND `0xC0994`, but no selected
same-target RiftScan candidate/match file exists yet.

## Validation

These checks passed:

```powershell
python -m py_compile scripts\rift_live_test\parent_slot_container_rank.py scripts\parent_slot_container_rank.py scripts\test_parent_slot_container_rank.py
python scripts\test_parent_slot_container_rank.py -v
python scripts\parent_slot_container_rank.py --parent-slot-summary-json scripts\captures\parent-slot-neighborhood-summary-20260513-220334-136540\summary.json --owner-structural-signature-json scripts\captures\owner-structural-signature-packet-20260513-223357-049150\summary.json --selected-rva 0x263E950 --json
```

## Resume prompt

Paste this into a fresh session:

> Resume `C:\RIFT MODDING\RiftReader` on `main`. Read
> `docs/recovery/current-truth.md` and newest handoff
> `docs/handoffs/2026-05-13-1838-navigation-parent-slot-container-rank.md`.
> Movement is blocked. Continue PC-heavy/offline static-root discovery above
> parent slot `0x268D7539700`, which points to best owner `0x268D753AE30` and
> stable candidate coord pointer `0x268DF21ED20`. Use the near-owner internal
> pointer cluster `0x0/0x10/0x18/0x40/0x48/0x50/0x58/0x60` and selected module
> hint `0x263E950 @ -0x40` as the container/list signature. Do not promote
> anything until API-now vs memory-now and same-target `ProofOnly` pass.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Build a parent-slot root-search signature packet around `0x268D7539700`. | It is now the highest-ranked unresolved root seed. |
| 2 | Search existing artifacts for slots with the same near-owner internal pointer cluster. | Finds likely sibling/list containers without live probing. |
| 3 | Compare `0x268D7539700` region layout to historical successful coord-root artifacts. | Previous truth often resides in related families. |
| 4 | Generate an HTML report for the chain/owner/container evidence. | Human-readable review helps avoid losing the thread. |
| 5 | Add a reusable structural query JSON format for future restarts. | Makes discovery faster after process drift. |
| 6 | Keep broad family snapshots as primary live-data method when new poses are needed. | Highest signal per bounded run. |
| 7 | Do not retry identical x64dbg attach attempts. | Previous attempts failed before attach. |
| 8 | Keep RiftScan read-only unless explicitly authorized otherwise. | Preserves provider boundary. |
| 9 | Refresh target-control/visual gate before future live action. | Target/focus can drift. |
| 10 | Require same-target `ProofOnly` before navigation. | Prevents stale-pointer movement. |
