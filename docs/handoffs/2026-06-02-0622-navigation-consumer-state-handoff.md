# RiftReader Handoff — Navigation consumer state contract — 2026-06-02 06:22 UTC

## Summary

RiftReader now has a read-only consumer-facing navigation state contract for
external projects that need current player position and yaw without inheriting
route-control or candidate-field ambiguity.

| Evidence | Result |
|---|---|
| Helper | `scripts\navigation_consumer_state.py`; launcher `scripts\riftreader-navigation-consumer-state.cmd`. |
| Contract doc | `docs\workflows\navigation-consumer-contract.md`. |
| Tool catalog | `navigation-consumer-state` is a canonical safe-read-only navigation-readback tool. |
| Live read-only verification | `scripts\riftreader-navigation-consumer-state.cmd --json --write` passed. |
| Latest output | `.riftreader-local\navigation-consumer-state\latest\summary.json`; verdict `consumer-navigation-state-ready`. |
| Promoted position | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`. |
| Promoted yaw | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314`. |
| Candidate boundary | `owner+0x304` and support fields are emitted only under `navigation.diagnostics`; route control is `authorized=false`. |

## Safety notes

- The helper sends no live input or movement.
- No `/reloadui`, screenshot key, Cheat Engine, x64dbg, provider writes, target
  memory writes, current-truth apply, proof promotion, actor-chain promotion, or
  route control is performed.
- The helper may read target memory through the already-promoted resolver to
  produce a fresh pose.
- Consumers must reject stale payloads and must not treat candidate diagnostics
  as control authority.

## Validation

| Validation | Result |
|---|---|
| Python compile | `python -m py_compile scripts\navigation_consumer_state.py tools\riftreader_workflow\tool_catalog.py` passed. |
| Unit tests | `python -m unittest scripts.test_navigation_consumer_state scripts.test_tool_catalog` passed; `9` tests. |
| Tool catalog compact | `scripts\riftreader-tool-catalog.cmd --compact-json` passed; `42` tools. |
| Live read-only helper | `scripts\riftreader-navigation-consumer-state.cmd --json --write` passed. |
| Diff check | `git --no-pager diff --check` passed. |
| Policy lint | `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` passed. |

## Current next action

Use `scripts\riftreader-navigation-consumer-state.cmd --json --write` as the
stable pose feed for external consumers. The next practical navigation
reliability lane is a dry-run waypoint-sequence contract, followed by explicit
live approval for a bounded multi-waypoint run when movement is allowed.
