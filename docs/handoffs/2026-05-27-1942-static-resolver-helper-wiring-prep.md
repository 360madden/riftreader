# Static resolver helper wiring prep — not promoted

Updated UTC: `2026-05-27T19:42:00Z`
Repo: `C:\RIFT MODDING\RiftReader`

## TL;DR

The reboot-surviving static player-coordinate chain remains:

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`

It is still **not promoted**. I prepared the RiftReader status/decision helper
surface so that, after explicit promotion approval, stale PID `12148` proof
pointer drift will not keep blocking the new static resolver lane.

## Current target / candidate

| Field | Value |
|---|---|
| PID | `34176` |
| HWND | `0x3D1544` |
| Module base | `0x7FF77AF40000` |
| Static root | `rift_x64+0x32EBC80` |
| Root address | `0x7FF77E22BC80` |
| Owner | `0x278C3830010` |
| Coordinate address | `0x278C3830330` |
| Latest final chain coordinate | `7259.949707031, 821.437561035, 2990.375732422` |
| Latest RRAPICOORD API coordinate | `7259.949700000, 821.440000000, 2990.379900000` |
| Max abs delta | `0.004167578` within tolerance `0.25` |

## What changed

| File | Change |
|---|---|
| `tools\riftreader_workflow\decision_packet.py` | Added static-resolver-aware target epoch handling. A complete promoted static resolver can supersede stale proof-pointer epoch drift; unpromoted candidates still block. |
| `scripts\coordinate_recovery_status.py` | Added current-truth/static-resolver awareness. A promoted resolver uses current-truth target for live PID checks; unpromoted candidates still use/stale-block on proof pointer. |
| `scripts\test_decision_packet.py` | Added promoted/unpromoted static resolver regression tests. |
| `scripts\test_coordinate_recovery_status.py` | Added promoted/unpromoted coordinate status target-selection tests. |
| `docs\recovery\current-truth.json` / `.md` | Updated helper-readiness state without promoting the chain. |

## Validation

| Check | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\decision_packet.py scripts\test_decision_packet.py scripts\coordinate_recovery_status.py scripts\test_coordinate_recovery_status.py` | Passed |
| `python -m unittest scripts.test_decision_packet` | Passed, `56` tests |
| `python -m unittest scripts.test_coordinate_recovery_status` | Passed, `2` tests |
| `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --compact-json` | Safe checks passed; packet still blocked by promotion/proof-gate state |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed |
| `git --no-pager diff --check` | Passed; only CRLF warnings |

## Current expected blockers

- `explicit-promotion-approval-not-given`
- `no-static-resolver-promoted`
- stale PID `12148` proof pointer remains a blocker while the static chain is unpromoted

## Safety ledger

| Boundary | Status |
|---|---|
| Live input / movement | Not used |
| Cheat Engine | Not used |
| x64dbg attach / breakpoints / watchpoints | Not used |
| DebugActiveProcessStop | Not called |
| Provider repo writes | None |
| Proof promotion | Not done |
| Actor/static-chain promotion | Not done |
| Git mutation | None |

## Next command

If promotion is explicitly approved, update current truth to mark the static
resolver promoted and re-run:

`python .\tools\riftreader_workflow\decision_packet.py --run-safe-checks --compact-json`

Until approval, continue treating the chain as promotion-review-ready evidence
only.
