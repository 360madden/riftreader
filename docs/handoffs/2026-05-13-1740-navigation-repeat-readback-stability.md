# Handoff: repeat readback stability narrows navigation proof seeds

Generated: 2026-05-13 17:40 EDT / 2026-05-13 21:40 UTC  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`

## TL;DR

Navigation remains **blocked**. Target-control and visual gate pass on the current
RIFT target, but same-target `ProofOnly` still blocks on stale proof pointer
PID/HWND. The newest work stayed read-only after the earlier broad snapshot: it
re-read the Top 100 candidates and added an offline stability comparer so local
PC artifacts can rank families without AI manually scanning thousands of rows.

| Gate | Current state |
|---|---|
| Target | `rift_x64.exe` PID `2928`, HWND `0xC0994`, title `RIFT` |
| Target-control | Passed |
| Visual gate | Passed |
| ProofOnly | `blocked-target-drift`; stale proof pointer PID `57656`, HWND `0x5417BC` |
| Navigation/movement | Blocked |
| CE/x64dbg | Not used in this slice |

## What changed in code

| File | Change |
|---|---|
| `scripts/rift_live_test/candidate_readback_stability.py` | New offline JSON comparer for repeated candidate readbacks. It ranks stable versus intermittent families without reading target memory or sending input. |
| `scripts/compare_candidate_readback_stability.py` | Thin CLI wrapper. |
| `scripts/test_candidate_readback_stability.py` | Unit tests for stable/intermittent classification and no-live-action output contract. |
| `docs/recovery/current-truth.md` | Updated current truth with repeat-readback stability result. |

## New evidence

| Evidence | Result |
|---|---|
| Repeat Top 100 readback | `scripts/captures/candidate-readback-currentpid-2928-20260513-213805-490589/candidate-readback-summary.json`; `passed`, `100` read, `8` matching; no input. |
| Stability comparison | `scripts/captures/candidate-readback-stability-20260513-214028-928580/summary.json`; `passed`, compared `3` readback summaries, `95` unique addresses. |
| Narrow family | `0x268DF21E000`; `3` addresses, `3` stable repeat matches. |
| Dense family | `0x268BEF2C000`; `92` addresses, `0` stable repeat matches, `84` intermittent/dropped, `8` mismatch. |
| RiftScan milestone review | `scripts/captures/riftscan-milestone-review-20260513-214256.json`; `blocked` on stale proof pointer and missing selected RiftScan candidate. |

## Interpretation

| Family | Current interpretation | Priority |
|---|---|---|
| `0x268DF21E000` | Narrow offset-corrected coordinate-copy family; repeated readbacks stayed stable while player/reference stayed fixed. | Keep as candidate seed evidence. |
| `0x268BEF2C000` | Dense family looked promising in the first readback but decayed/mismatched by the repeat Top 100 readback. | De-prioritize unless a new movement-vector snapshot revalidates it. |

Important: this is still **candidate-only**. It does not resolve a static pointer
chain, does not pass restart validation, and does not authorize navigation.

## Validation

| Command | Result |
|---|---|
| `python -m py_compile scripts\rift_live_test\candidate_readback_stability.py scripts\compare_candidate_readback_stability.py scripts\test_candidate_readback_stability.py` | Passed |
| `python scripts\test_candidate_readback_stability.py -v` | Passed, `2/2` |
| `python scripts\compare_candidate_readback_stability.py <top20> <top100> <repeat-top100> --json` | Passed; wrote stability artifacts |
| `python scripts\riftscan_milestone_review.py --compact-json --write-summary --write-markdown` | Expected strategy-blocked result; wrote `scripts/captures/riftscan-milestone-review-20260513-214256.json`. |

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Current target is
`rift_x64.exe` PID `2928`, HWND `0xC0994`. Target-control and visual gate pass,
but `ProofOnly` remains blocked by stale proof pointer PID `57656` / HWND
`0x5417BC`; movement/navigation must stay blocked. Latest broad family snapshot
is `scripts/captures/family-snapshot-sequence-currentpid-2928-20260513-212104-107039/summary.json`.
Latest repeat-readback stability artifact is
`scripts/captures/candidate-readback-stability-20260513-214028-928580/summary.json`:
only narrow family `0x268DF21E000` is repeat-stable; dense family
`0x268BEF2C000` is de-prioritized. Use broad family-group snapshots/offline
deltas for further recovery, not narrow stale-address probing. Do not run
navigation movement until same-target `ProofOnly` passes.

## Next best actions

| # | Action | Why |
|---:|---|---|
| 1 | Keep movement/navigation blocked. | ProofOnly has not passed for PID `2928` / HWND `0xC0994`. |
| 2 | Use `0x268DF21E000` as the primary candidate seed family. | It is the only repeat-stable family across three readbacks. |
| 3 | De-prioritize `0x268BEF2C000` unless revalidated by a new movement vector. | Latest repeat readback shows it is unstable/dropped. |
| 4 | Search owner/source relationships around `0x268D753AE40` read-only. | It remains the only pointer/ref-storage clue for `0x268DF21ED20`. |
| 5 | Avoid another identical x64dbg attach retry. | Prior attach attempts failed before attach; use a new tactic only. |
| 6 | If more discovery input is needed, use a bounded broad-family snapshot with a distinct vector. | Family snapshots give better signal than narrow probes. |
| 7 | Keep repeat-readback stability comparison in the loop after each broad snapshot. | It lets the PC down-rank noisy candidate families automatically. |
| 8 | Re-run navigation resume status after any proof-recovery change. | Keeps the user-facing gate state current. |
| 9 | Do not promote offset-corrected copies directly. | Navigation needs API-now vs memory-now plus same-target proof. |
| 10 | Update current truth and handoff after the next proof gate result. | Prevents stale candidate evidence from becoming assumed truth. |
