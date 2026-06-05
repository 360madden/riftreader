# Validation ledger blocked-safe status handoff — 2026-06-05 11:14 UTC

## Result

The timestamped validation ledger now preserves the RiftReader autonomous
continuation rule that known status helpers returning exit code `2` are
blocked-safe evidence, not a failed local CI run.

## Root cause

`python tools\riftreader_workflow\validation_ledger.py --tier full-local`
failed fast at the decision-packet step when the decision packet correctly
returned exit code `2` for the existing proof-recovery blocker
`latest-static-owner-readback-root-pointer-null`. That contradicted the repo
policy that known helper/status blocker exit `2` should be treated as
`blocked-safe` and should not stop safe local validation.

## Changed files

| Path | Change |
|---|---|
| `tools/riftreader_workflow/validation_ledger.py` | `full-local` now accepts `0` or `2` for known status helpers `decision-packet` and `workflow-status`; expected nonzero exits produce explicit warnings. |
| `scripts/test_validation_ledger.py` | Added regression coverage that an expected exit `2` passes while recording a warning. |
| `docs/workflow/timestamped-validation-ledger.md` | Documents the blocked-safe exit `2` handling for known full-local status helpers. |
| `docs/HANDOFF.md` | Adds this handoff to the top re-entry index. |

## Validation

| Command | Result |
|---|---|
| `python -m unittest scripts.test_validation_ledger` | Passed 10 tests in 9.811s. |
| `python tools\riftreader_workflow\validation_ledger.py --tier full-local` | Passed in 470.565s at `.riftreader-local/validation-runs/20260605-110550-722733/summary.md`. |

## Notes

- The successful `full-local` ledger recorded warnings for expected exit `2`
  from `decision-packet` and `workflow-status` and one slow warning for
  `unittest-discover` at 425.016s versus a 420s warning budget.
- No public tunnel, ChatGPT registration, RIFT input, CE/x64dbg attach, provider
  writes, proof promotion, push, or remote mutation was performed.
- The MCP final gate remains blocked on stale actual-client proof, missing
  current-head remote CI, and local branch ahead of origin; the next MCP action
  remains explicit operator proof recording via the Secure Tunnel path.
