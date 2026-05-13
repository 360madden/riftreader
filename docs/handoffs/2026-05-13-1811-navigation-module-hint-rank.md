# Navigation coord recovery handoff — module-hint rank

## TL;DR

Parent-slot source-chain evidence is now ranked offline. The strongest next
static-owner clue is the player-candidate parent-slot module pointer:

`rift_x64.exe+0x263E950` at `0x268D7539700 - 0x40`, score `180`.

This improves prioritization for the next PC-heavy/offline static-chain search,
but it is still candidate-only. Movement remains blocked because same-target
`ProofOnly` still points to stale PID `57656` / HWND `0x5417BC` instead of the
current target PID `2928` / HWND `0xC0994`.

## What changed

| File | Purpose |
|---|---|
| `scripts/rift_live_test/parent_slot_module_hint_rank.py` | Offline module-hint ranker for parent-slot summaries. |
| `scripts/parent_slot_module_hint_rank.py` | Thin CLI wrapper. |
| `scripts/test_parent_slot_module_hint_rank.py` | Unit coverage for offset parsing, scoring, and shared-RVA counts. |
| `docs/recovery/current-truth.md` | Added the ranked module-hint clue and preserved candidate-only gate. |

## Evidence

Primary artifact:

- `scripts/captures/parent-slot-module-hint-rank-20260513-221249-080403/summary.json`
- Markdown companion: `scripts/captures/parent-slot-module-hint-rank-20260513-221249-080403/summary.md`

| Rank | Score | RVA | Owner slot | Offset | Why |
|---:|---:|---|---|---:|---|
| 1 | `180` | `0x263E950` | `0x268D7539700` | `-0x40` | Player-candidate slot, exact owner+module hint, near owner slot. |
| 2 | `30` | `0x2647AC0` | `0x268E2A78628` | `-0x150` | Sibling owner slot with module hint. |
| 3 | `30` | `0x2691A88` | `0x268E2A78628` | `-0x3A8` | Sibling owner slot with module hint. |

## Current gate

| Gate | Status | Note |
|---|---:|---|
| Current target | ✅ present | PID `2928`, HWND `0xC0994`. |
| Target-control / visual gate | ✅ last passed | Must be refreshed before live input. |
| Same-target `ProofOnly` | ❌ blocked | Latest proof pointer is stale PID `57656`, HWND `0x5417BC`. |
| Coordinate proof promotion | ❌ not promoted | All current leads are candidate-only. |
| Movement/navigation | ❌ blocked | No movement permitted from this evidence. |

## Validation

These checks passed for this slice:

```powershell
python -m py_compile scripts\rift_live_test\parent_slot_module_hint_rank.py scripts\parent_slot_module_hint_rank.py scripts\test_parent_slot_module_hint_rank.py
python scripts\test_parent_slot_module_hint_rank.py -v
python scripts\parent_slot_module_hint_rank.py --parent-summary-json scripts\captures\parent-slot-neighborhood-summary-20260513-220334-136540\summary.json --json
```

## Resume prompt

Paste this into a fresh session:

> Resume `C:\RIFT MODDING\RiftReader` on `main`. Read
> `docs/recovery/current-truth.md` and newest handoff
> `docs/handoffs/2026-05-13-1811-navigation-module-hint-rank.md`. Movement is
> blocked; all source-chain evidence is candidate-only. Continue PC-heavy
> offline discovery by investigating top module hint `rift_x64.exe+0x263E950`
> near player-candidate parent slot `0x268D7539700`, comparing it against
> sibling hints `0x2647AC0` and `0x2691A88`. Do not promote anything until
> API-now vs memory-now and same-target `ProofOnly` pass.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Build a module-RVA code/data neighborhood packet for `0x263E950`. | It is now the highest-ranked player-candidate static-owner clue. |
| 2 | Compare `0x263E950` against sibling RVAs `0x2647AC0` and `0x2691A88`. | Control comparison prevents overfitting to one heap slot. |
| 3 | Search current artifacts for every occurrence of `0x263E950`. | Reuse existing PC-generated data before live work. |
| 4 | Export a graph view of `type marker -> owner -> parent slot -> module hint`. | Makes the chain easier to inspect and resume. |
| 5 | Scan parent-slot windows for list/container fields around the exact owner refs. | Static root may point to the parent slot container, not the coord copy. |
| 6 | Keep broad family snapshots as the primary live data source when new poses are needed. | Highest signal per bounded run. |
| 7 | Do not retry identical x64dbg attach attempts. | Current attach blocker needs a changed tactic first. |
| 8 | Keep RiftScan read-only until explicitly authorized otherwise. | Preserves provider boundary. |
| 9 | Refresh target-control/visual gate before any future live input. | Focus/target state is short-lived. |
| 10 | Require same-target `ProofOnly` before navigation. | Prevents stale-pointer movement. |
