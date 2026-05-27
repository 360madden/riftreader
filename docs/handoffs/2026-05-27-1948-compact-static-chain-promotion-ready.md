# Compact handoff — static player-coordinate chain promotion-ready, not promoted

Updated UTC: `2026-05-27T19:50:31Z`
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main` tracking `origin/main`

## TL;DR

The static player-coordinate chain is discovered, reboot-survived, displacement-validated, and API-now validated:

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`

It is **promotion-review ready** but **not promoted**. Current remaining gate is explicit promotion approval plus flipping the static resolver promotion state. Status/decision helpers have been prepared to honor the promoted resolver after that gate opens.

## Current target / chain

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID / HWND | `34176` / `0x3D1544` |
| Process start UTC | `2026-05-27T18:06:53.0701460Z` |
| Module base | `0x7FF77AF40000` |
| Static root | `rift_x64+0x32EBC80` = `0x7FF77E22BC80` |
| Current owner | `0x278C3830010` |
| Coordinate address | `0x278C3830330` |
| Coordinate offsets | `+0x320/+0x324/+0x328` |
| Owner vtable | `0x7FF77D58CEB8` / RVA `0x264CEB8` |

## Strongest evidence

| Evidence | Artifact |
|---|---|
| Reboot/relogin survival | `docs/recovery/static-owner-coordinate-chain-survived-reboot-2026-05-27.md` |
| Targeted displacement response | `docs/recovery/static-owner-coordinate-chain-displacement-validation-2026-05-27.md` |
| API-now vs chain-now validation | `docs/recovery/static-owner-coordinate-chain-api-now-validation-2026-05-27.md` |
| Final promotion review | `docs/recovery/static-owner-coordinate-chain-promotion-review-2026-05-27.md` |
| Helper-wiring prep | `docs/handoffs/2026-05-27-1942-static-resolver-helper-wiring-prep.md` |

Final fresh sample:

| Source | Coordinate |
|---|---|
| RRAPICOORD API-now | `7259.949700000, 821.440000000, 2990.379900000` |
| Static chain-now | `7259.949707031, 821.437561035, 2990.375732422` |
| Max abs delta | `0.004167578` within tolerance `0.25` |

## Current blockers

- `explicit-promotion-approval-not-given`
- `no-static-resolver-promoted`
- stale PID `12148` proof pointer remains a blocker while `promotionAllowed=false`

## Safety ledger

| Boundary | Status |
|---|---|
| Cheat Engine | Not used |
| x64dbg attach / breakpoints / watchpoints in this slice | Not used |
| DebugActiveProcessStop in this slice | Not called |
| Live input / movement in this slice | Not used |
| Provider repo writes | None |
| Proof/static-chain promotion | Not done |
| Git mutation before this handoff | None |

## Helper readiness

- `tools/riftreader_workflow/decision_packet.py` now recognizes a complete promoted static resolver and suppresses stale proof-pointer target drift only when promoted.
- `scripts/coordinate_recovery_status.py` can use current-truth target identity for live checks only when a complete static resolver is promoted.
- Tests cover both promoted and unpromoted paths, ensuring unpromoted evidence still blocks.

## Validation before commit

| Check | Result |
|---|---|
| JSON parse for current-truth/current-proof/static-chain reports | Passed |
| `python -m py_compile` for changed helpers/tests | Passed |
| `python -m unittest scripts.test_coordinate_recovery_status scripts.test_decision_packet scripts.test_owner_layout_comparison_packet scripts.test_sysinternals_discovery_packet` | Passed, `68` tests |
| `python tools/riftreader_workflow/policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed |
| `git --no-pager diff --check` | Passed; CRLF warnings only |
| `scripts/riftreader-decision-packet.cmd --compact-json --write` | Expected blocked-safe: promotion not approved and static resolver not promoted |

## Next best command after explicit promotion approval

`python .\tools\riftreader_workflow\decision_packet.py --run-safe-checks --compact-json`

Expected now, before promotion: blocked-safe on explicit promotion/no-static-resolver/stale old proof pointer.
