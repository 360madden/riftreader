# Navigation coord recovery handoff — parent-slot neighborhoods

## TL;DR

The current live target is still `rift_x64.exe` PID `2928`, HWND `0xC0994`.
Target-control and visual gate are green, but same-target `ProofOnly` is still
blocked on stale proof PID `57656` / HWND `0x5417BC`, so navigation and movement
remain blocked.

This slice improved the offline source-chain map around the low-noise type
marker family. A new read-only summarizer compared the three heap parent slots
for the `rift_x64.exe+0x26AAE70` type instances. Result: all three parent slots
point to their owner exactly once; two slots have nearby module-pointer hints,
including the player-candidate parent slot. This is a stronger static-owner clue
set, but it is still candidate-only and not movement proof.

## Gate status

| Gate | Status | Evidence |
|---|---:|---|
| Current target | ✅ present | PID `2928`, HWND `0xC0994`, process start `2026-05-13T16:17:56.208370Z` |
| Target-control | ✅ passed | `scripts/captures/target-control-currenttarget-20260513-172535/target-control-status.json` |
| Visual gate | ✅ passed | `scripts/captures/visual-gate-currentpid-2928-20260513-171907/visual-gate-status.json` |
| Same-target `ProofOnly` | ❌ blocked | `scripts/captures/live-test-ProofOnly-20260513-211940/run-summary.json` reports stale PID/HWND |
| RiftScan milestone review | ❌ blocked as expected | `scripts/captures/riftscan-milestone-review-20260513-220802.json` reports stale proof pointer + no selected candidate |
| Movement/navigation | ❌ blocked | No promoted current coordinate proof |

## What changed in repo

| File | Purpose |
|---|---|
| `scripts/rift_live_test/parent_slot_neighborhood_summary.py` | Offline summarizer for parent-slot neighborhood artifacts. |
| `scripts/parent_slot_neighborhood_summary.py` | Thin CLI wrapper. |
| `scripts/test_parent_slot_neighborhood_summary.py` | Unit coverage for classification/counting behavior. |
| `docs/recovery/current-truth.md` | Promoted this candidate-only parent-slot evidence into current truth. |

## New evidence

Primary summary:

- `scripts/captures/parent-slot-neighborhood-summary-20260513-220334-136540/summary.json`
- Markdown companion: `scripts/captures/parent-slot-neighborhood-summary-20260513-220334-136540/summary.md`

| Parent slot | Exact target | Classification | Region matches | Owner-window module RVAs | Interpretation |
|---|---|---|---:|---|---|
| `0x268D7539700` | `0x268D753AE30` (`type-instance-player-candidate`) | `owner-slot-with-module-hint` | `159` | `0x263E950` | Best player-candidate source-chain clue; module hint at slot offset `-0x40`. |
| `0x268E2A78628` | `0x268923AF610` (`type-instance-a`) | `owner-slot-with-module-hint` | `25` | `0x2691A88`, `0x2647AC0` | Useful sibling/control comparison for owner layout. |
| `0x268B0DD1168` | `0x268C6A10EA0` (`type-instance-b`) | `owner-slot-heap-only` | `167` | none in owner window | Heap-only sibling; still useful as negative/control structure. |

## Interpretation

- The stable coord-family lead remains the narrow `0x268DF21E000` family.
- The current strongest owner chain is still:
  `rift_x64.exe+0x26AAE70 -> owner 0x268D753AE30 -> [owner+0x10] = 0x268DF21ED20`.
- The new parent-slot map adds source-chain clues around the heap parent slot:
  `0x268D7539700 -> 0x268D753AE30`, with `rift_x64.exe+0x263E950` nearby.
- This helps prioritize the next offline/static-chain search, but it does not
  resolve a module/static root and cannot be used for movement.

## Safety state

| Safety flag | Value |
|---|---:|
| Movement sent | `false` |
| Input sent | `false` |
| Cheat Engine used | `false` |
| x64dbg launched/attached | `false` |
| Target memory read by new summarizer | `false` |
| Candidate-only | `true` |

## Validation

These checks passed for this slice:

```powershell
python -m py_compile scripts\rift_live_test\parent_slot_neighborhood_summary.py scripts\parent_slot_neighborhood_summary.py scripts\test_parent_slot_neighborhood_summary.py
python scripts\test_parent_slot_neighborhood_summary.py -v
python scripts\parent_slot_neighborhood_summary.py --slot-summary-json scripts\captures\pointer-owner-neighborhood-inspector-20260513-220211-476668\summary.json --slot-summary-json scripts\captures\pointer-owner-neighborhood-inspector-20260513-220211-484997\summary.json --slot-summary-json scripts\captures\pointer-owner-neighborhood-inspector-20260513-220211-613580\summary.json --json
python scripts\riftscan_milestone_review.py --pid 2928 --hwnd 0xC0994 --process-name rift_x64 --write-summary --write-markdown --compact-json
```

`riftscan_milestone_review.py` exited non-zero because its expected current
verdict is `blocked`; it wrote
`scripts/captures/riftscan-milestone-review-20260513-220802.json` and confirmed
the same blockers: stale proof pointer plus no selected RiftScan candidate.

## Resume prompt

Paste this into a fresh session:

> Resume `C:\RIFT MODDING\RiftReader` on `main`. Read
> `docs/recovery/current-truth.md` and newest handoff
> `docs/handoffs/2026-05-13-1803-navigation-parent-slot-neighborhoods.md`.
> Current target is PID `2928` / HWND `0xC0994`, target-control and visual gate
> were green, but `ProofOnly` is blocked by stale PID/HWND. Do not move. Keep
> using broad family snapshots and offline/PC-heavy source-chain analysis. Next
> best step: use the parent-slot module hints (`0x263E950`, `0x2691A88`,
> `0x2647AC0`) and owner-slot layouts to search for a static-owner/list root;
> promote nothing until API-now vs memory-now and same-target `ProofOnly` pass.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Build an offline module-hint neighborhood comparer for `0x263E950`, `0x2691A88`, and `0x2647AC0`. | Converts hints into ranked static-owner/list-root candidates. |
| 2 | Compare all three parent-slot owner windows by relative slot layout. | Separates common list mechanics from player-specific structure. |
| 3 | Scan parent-slot regions for container/list signatures around `ownerSlot - 0x400..+0x400`. | The source chain likely lives near the heap parent slot, not the coord copy. |
| 4 | Re-run broad family snapshots only when a new displaced pose is needed. | Keeps signal high and avoids narrow stale-address probing. |
| 5 | Add a compact graph export for owner -> parent slot -> module hint relationships. | Makes future chain scoring PC-heavy and token-light. |
| 6 | Investigate whether `rift_x64.exe+0x263E950` is a type/vtable/descriptor field shared with known owners. | Player-candidate slot's module hint is the best current static clue. |
| 7 | Keep `0x268BEF2C000` de-prioritized unless a new movement-vector snapshot revives it. | Repeat readbacks proved it unstable in this session. |
| 8 | Avoid identical x64dbg attach retries until a new attach tactic exists. | Two minimized attach attempts failed before attach; retrying wastes time. |
| 9 | Run RiftScan milestone review after each committed milestone. | Keeps the cross-tool strategy gate current. |
| 10 | Only attempt movement after API-now vs memory-now and same-target `ProofOnly` pass. | Prevents stale-pointer navigation. |
