# RiftReader Handoff — Navigation sequence contract report — 2026-06-02 06:55 UTC

## Summary

RiftReader now has a saved-summary contract report for continuous route sequence
dry-runs. External consumers can validate a sequence dry-run artifact without
reading full route-runner internals.

| Evidence | Result |
|---|---|
| Contract helper | `scripts\navigation_sequence_summary_contract.py`; launcher `scripts\static-owner-continuous-route-sequence-contract.cmd`. |
| Accepted source | `kind=static-owner-continuous-route-sequence`, `operator.dryRun=true`, `status=passed`. |
| Safety contract | Requires no movement, no input, no navigation control, no debugger attach, no provider writes, and no target memory writes. |
| Sequence contract | Accepts `sequence-dry-run-plan-built` or already-arrived dry-run sequences; rejects simulated multi-waypoint arrival claims. |
| Tool catalog | `static-owner-route-sequence-contract` is canonical, safe-read-only, and in the recommended workflow. |
| Docs | `docs\workflows\navigation-route.md` includes the saved-summary validation command. |

## Safety notes

- The helper reads a saved JSON summary only.
- It sends no live input or movement and reads no live target memory.
- It performs no `/reloadui`, screenshot key, Cheat Engine, x64dbg, provider
  writes, target memory writes, proof promotion, actor-chain promotion, or route
  control.

## Validation

| Validation | Result |
|---|---|
| Python compile | `python -m py_compile scripts\navigation_sequence_summary_contract.py tools\riftreader_workflow\tool_catalog.py` passed. |
| Unit tests | `python -m unittest scripts.test_navigation_sequence_summary_contract scripts.test_tool_catalog` passed; `9` tests. |
| Saved-summary contract smoke | `scripts\static-owner-continuous-route-sequence-contract.cmd scripts\captures\static-owner-continuous-route-sequence-20260602-064437-323455\summary.json --json` passed. |
| Tool catalog compact | `scripts\riftreader-tool-catalog.cmd --compact-json` passed; `43` tools. |

## Current next action

The repo now exposes a consumer-safe pose feed and a consumer-safe sequence
dry-run artifact gate. The next practical reliability lane is an offline
waypoint-file linter/generator that checks schema, radius, IDs, coordinate
shape, and produces a first-leg dry-run plus contract report in one command.
