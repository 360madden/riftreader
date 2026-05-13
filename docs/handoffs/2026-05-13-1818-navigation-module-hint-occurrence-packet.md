# Navigation coord recovery handoff — module-hint occurrence packet

## TL;DR

The offline occurrence scan confirms `rift_x64.exe+0x263E950` is the dominant
module-hint seed to investigate next. It appears far more often and closer to
the player-candidate parent-slot structure than the sibling-control RVAs.

Movement remains blocked. This is candidate-only static-owner/source-chain
evidence, not coordinate proof.

## Result

Primary artifact:

- `scripts/captures/module-hint-occurrence-packet-20260513-222030-779335/summary.json`
- Markdown companion: `scripts/captures/module-hint-occurrence-packet-20260513-222030-779335/summary.md`

| Rank | RVA | Score | Occurrences | Artifacts | Owners | Owner-window hits | Near-owner hits | Interpretation |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | `0x263E950` | `962` | `57` | `6` | `4` | `4` | `2` | Dominant player-candidate static-owner seed. |
| 2 | `0x2647AC0` | `68` | `1` | `1` | `1` | `1` | `0` | Sibling/control hint only. |
| 3 | `0x2691A88` | `68` | `1` | `1` | `1` | `1` | `0` | Sibling/control hint only. |

Best sample:

| Field | Value |
|---|---|
| Artifact | `scripts/captures/pointer-owner-neighborhood-inspector-20260513-220211-613580/summary.json` |
| Owner/slot | `0x268D7539700` |
| Entry | `0x268D75396C0` |
| Offset from owner slot | `-0x40` |
| Module value | `0x7FF71F3CE950` |
| RVA | `0x263E950` |
| Sources | `ownerWindowModulePointers`, `regionMatches`, `ownerWindow` |

## What changed

| File | Purpose |
|---|---|
| `scripts/rift_live_test/module_hint_occurrence_packet.py` | Offline artifact scanner and ranked occurrence packet builder for module-pointer RVAs. |
| `scripts/module_hint_occurrence_packet.py` | Thin CLI wrapper. |
| `scripts/test_module_hint_occurrence_packet.py` | Unit coverage for normalization, de-duping, and ranking. |
| `docs/recovery/current-truth.md` | Added the occurrence-packet result and preserved candidate-only gate. |

## Current gate

| Gate | Status | Note |
|---|---:|---|
| Current target | ✅ present | PID `2928`, HWND `0xC0994` from previous target-control state. |
| Target-control / visual gate | ✅ last passed | Must be refreshed before live input. |
| Same-target `ProofOnly` | ❌ blocked | Latest proof pointer is stale PID `57656`, HWND `0x5417BC`. |
| Coordinate proof promotion | ❌ not promoted | All current leads are candidate-only. |
| Movement/navigation | ❌ blocked | No movement permitted from this evidence. |
| RiftScan milestone review | ❌ blocked as expected | `scripts/captures/riftscan-milestone-review-20260513-222102.json`: stale proof pointer + no selected candidate. |

## Validation

These checks passed:

```powershell
python -m py_compile scripts\rift_live_test\module_hint_occurrence_packet.py scripts\module_hint_occurrence_packet.py scripts\test_module_hint_occurrence_packet.py
python scripts\test_module_hint_occurrence_packet.py -v
python scripts\module_hint_occurrence_packet.py --rva 0x263E950 --rva 0x2647AC0 --rva 0x2691A88 --module-address 0x7FF71F3CE950 --json
```

## Resume prompt

Paste this into a fresh session:

> Resume `C:\RIFT MODDING\RiftReader` on `main`. Read
> `docs/recovery/current-truth.md` and newest handoff
> `docs/handoffs/2026-05-13-1818-navigation-module-hint-occurrence-packet.md`.
> Movement is blocked. Continue PC-heavy/offline static-owner discovery using
> `rift_x64.exe+0x263E950` as the top seed. The occurrence packet found `57`
> selected occurrences across `6` artifacts and `4` owners; sibling RVAs
> `0x2647AC0` and `0x2691A88` each had one occurrence. Do not promote anything
> until API-now vs memory-now and same-target `ProofOnly` pass.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Build a graph packet rooted at `0x263E950 -> owner slot -> owner -> coord pointer`. | Converts occurrence evidence into an explicit chain candidate map. |
| 2 | Compare the repeated `0x263E950` owner offsets across all 6 artifacts. | Repeated stride/offset patterns may reveal a list/container layout. |
| 3 | Inspect whether `0x263E950` is a vtable/type descriptor-like pointer by comparing nearby module hints. | Determines if it can identify the owner class reliably. |
| 4 | Add a compact CSV export for `0x263E950` occurrences. | Makes local spreadsheet/PC review easier and token-light. |
| 5 | Search for heap owners that combine `0x26AAE70`, `0x263E950`, and `[+0x10]` coord pointer shape. | This is a stronger structural signature than any single offset. |
| 6 | Keep `0x2647AC0` and `0x2691A88` as sibling controls. | Controls reduce false positives. |
| 7 | Avoid live x64dbg attach retries until a changed tactic exists. | Previous attempts failed before attach. |
| 8 | Refresh target-control/visual gate before any future live action. | Current target/focus can drift quickly. |
| 9 | Keep movement blocked until same-target `ProofOnly` passes. | Prevents stale-pointer movement. |
| 10 | Run RiftScan milestone review after the next commit/push. | Keeps the cross-provider strategy gate current. |
