# RiftReader handoff — no live target after PID 28248 drift

Created UTC: `2026-05-23T06:48:00Z`

## Direct result

The PID `28248` proof/readiness milestone was committed locally as `9bda0ee`, but it is now historical for live work. After the commit, the live target drifted and then disappeared from process checks.

Current live status:

- `git status`: clean, `main...origin/main [ahead 1]`
- Current proof pointer: `blocked-target-drift`
- Live RIFT target: none detected in the latest process check
- ChromaLink: blocked/provider-stale; player position missing as current truth
- Movement/proof promotion: blocked

## Evidence

| Evidence | Artifact/result |
|---|---|
| Local milestone commit | `9bda0ee Restore current proof readiness and attach diagnostics` |
| Coordinate status after drift | `artifact-target-pid-not-running:artifact=28248;live=28496` at `2026-05-23T06:43:26Z` |
| Brief replacement target | PID `28496`, HWND `0x9121A`, module base `0x7FF7A3830000` |
| Later process check | no `rift_x64`, `rifterrorhandler_x64`, or `x64dbg` process listed |
| ChromaLink freshness | `provider-stale`, `player-position-missing`, `rift-process-missing` |
| ChromaLink artifact | `C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink\artifacts\diagnostics\chromalink-ensure-fresh-20260523T064352Z\summary.json` |
| Pointer-family scan retry | `scripts/captures/pointer-family-scan-20260523-064638-227102/summary.json`, blocked with `target-window-not-found` |

## What changed in this follow-up slice

- Marked `docs/recovery/current-proof-anchor-readback.json` as `blocked-target-drift`.
- Archived PID `28248` proof/truth under `docs/recovery/historical/`.
- Updated `docs/recovery/current-truth.json` and `.md` to reflect no current live target/provider stale.
- Fixed `scripts/rift_live_test/pointer_family_scan.py` so blocked runs with `target=null` still write Markdown instead of crashing.
- Added regression coverage in `scripts/test_pointer_family_scan.py`.

## Safety ledger

| Operation | Status |
|---|---|
| Movement/game input | Not used |
| x64dbg/debugger attach after drift | Not used |
| Breakpoints/watchpoints | Not used |
| Memory writes | Not used |
| Provider writes | Not used |
| Cheat Engine | Not used |
| Git push | Not used |

## Top 10 recommended next actions

1. Do not use PID `28248` addresses as current proof; they are historical hints only.
2. Restore/reopen RIFT to an in-world target before any further proof work.
3. Re-run ChromaLink `Ensure-ChromaLinkFresh.cmd --prepare-window --wait-fresh --json` once a RIFT window exists.
4. Confirm geometry is back to `640x360 / P360C` before consumer proof.
5. Run `coordinate_recovery_status.py --json`; it should remain blocked until a new same-target proof is created.
6. Re-run current-PID proof recovery only after provider freshness and target-control gates pass.
7. Keep x64dbg off the critical path until a stable live target exists; the last attach route was command-rejected.
8. Do not run actor/static-chain scans against stale PID `28248`.
9. Commit this stale-target bookkeeping/fix after validation if clean.
10. Push only after explicit decision that publishing live-truth artifacts is acceptable.
