# RiftReader Handoff — Phase 1 target entity snapshot helper — 2026-06-02 04:04 UTC

## Summary

Phase 1 target-entity discovery now has a durable Python-first evidence wrapper
and a live post-flush selected-target packet. The selected target was
deterministically bootstrapped as `Atank` with `/target Atank`, then `/reloadui`
was intentionally sent to flush `ReaderBridgeExport.lua` as a post-save target
snapshot.

| Evidence | Result |
|---|---|
| Current target identity | PID `12664`, HWND `0x205146C`, process `rift_x64`, title `RIFT`. |
| Selected target export | `ReaderBridgeExport.lua` updated `2026-06-02T03:54:15Z`; `targetPresent=true`; target `Atank` / `u035400012FA2D207`. |
| Phase 1 helper output | `scripts\captures\phase1-target-entity-snapshot-20260602-035907-998714\summary.json`. |
| Target-current reader blocker | `target-current-family-resolution-failed:fam-CEC3708F`. |
| Target fields captured | `hp=18208`, `hpMax=18208`, `level=45`, `relation=friendly`, `distance=0`, coord `(7251.0400390625, 821.44000244141, 2987.8698730469)`. |
| Tooling commit | `ceeba06 Add Phase 1 target entity snapshot helper`. |

## New/updated tooling

| Path | Purpose |
|---|---|
| `scripts\phase1_target_entity_snapshot.py` | Captures a post-flush selected-target ReaderBridge snapshot, runs the C# target-current reader, and writes structured JSON/Markdown evidence. |
| `scripts\riftreader-phase1-target-entity-snapshot.cmd` | Thin launcher for the Python helper. |
| `scripts\test_phase1_target_entity_snapshot.py` | Unit/self-test coverage for target extraction and blocker parsing. |
| `tools\riftreader_workflow\tool_catalog.py` | Adds `phase1-target-entity-snapshot` to canonical tools and recommended workflow. |
| `tools\riftreader_workflow\status_packet.py` | Adds the Phase 1 helper to compact bridge commands. |

## Validation

| Validation | Result |
|---|---|
| Python compile | `python -m py_compile scripts\phase1_target_entity_snapshot.py tools\riftreader_workflow\tool_catalog.py tools\riftreader_workflow\status_packet.py scripts\test_phase1_target_entity_snapshot.py scripts\test_tool_catalog.py scripts\test_status_packet.py` passed. |
| Unit tests | `python -m unittest scripts.test_phase1_target_entity_snapshot scripts.test_tool_catalog scripts.test_status_packet` passed; `21` tests. |
| Tool catalog compact | `scripts\riftreader-tool-catalog.cmd --compact-json` passed; `41` tools; Phase 1 helper is canonical and in recommended workflow. |
| Decision packet | `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` passed before commit. |
| Sensitive staged scan | `scripts\riftreader-sensitive-artifact-scan.cmd --staged --json` passed before commit. |

## Safety notes

- Phase 1 live selection used exact PID/HWND window targeting only.
- Live input sent during target acquisition: Tab attempts, one click attempt, `/target Atank`, and `/reloadui`.
- No movement was sent during Phase 1 target acquisition.
- No Cheat Engine/x64dbg/debugger attach, provider writes, target memory writes,
  proof promotion, actor-chain promotion, or branch rewrite were performed.
- The Phase 1 helper itself sends no input and does not reload UI. It records
  `ReaderBridgeExport.lua` only as a deliberate post-flush snapshot, not live
  IPC truth.

## Current next action

Debug the C# `--read-target-current` target family resolver for
`fam-CEC3708F`, then repeat the Phase 1 snapshot with a non-self selected target
once a friendly/hostile unit can be selected reliably.
