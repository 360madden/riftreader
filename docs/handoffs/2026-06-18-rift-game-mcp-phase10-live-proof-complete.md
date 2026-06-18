# 2026-06-18 - RIFT game MCP Phase 10 live wrapper proof complete

## Current truth

| Item | Evidence |
|---|---|
| Scope | Completed the repo-owned `tools\rift-game-mcp` Stage/Phase 9-10 movement-control slice for one exact-target live movement step. |
| Exact live target | PID `130540`, HWND `0x9310EA`, process `rift_x64`, title `RIFT`, visible/non-minimized/foreground during preflight and live execution. |
| Current-proof source | `docs\recovery\current-proof-anchor-readback.json` was refreshed by same-target recovery/ProofOnly at `2026-06-18T06:24:30.980596+00:00` for PID `130540` / HWND `0x9310EA`. |
| Stale current-truth handling | `docs\recovery\current-truth.json` still points at PID `12664` / HWND `0x205146C`; patched MCP preflight now reports that stale/mismatched current-truth as a warning when fresh same-target current-proof is usable. |
| Patched MCP dry-run | Local patched MCP server dry-run passed using current-proof source; artifact `tools\rift-game-mcp\.runtime\manual-phase10\manual-phase10-dry-run-20260618T063651Z.json`. |
| Live wrapper execution | Local patched MCP server executed exactly one `move_forward` / `W` hold for `750 ms`; artifact `tools\rift-game-mcp\.runtime\manual-phase10\manual-phase10-live-20260618T063800Z.json`. |
| Visual verification | `wait_for_frame_change` reported `changed=true`, `changePercent=26.6389`; baseline `tools\rift-game-mcp\.runtime\screenshots\capture-20260618-023753-919.png`, changed `capture-20260618-023758-438.png`, final `capture-20260618-023759-699.png`. |
| Coordinate verification | Pre-live RRAPICOORD `7262.2197, 821.75, 3004.52`; post-live RRAPICOORD `7262.0698, 822.18, 3009.21`; `maxAbs=4.69`, `planarXZ=4.6924`, `spatialXYZ=4.7121`, threshold `0.25`. |
| Coordinate delta artifact | `.riftreader-local\rift-game-mcp\manual-phase10\phase10-coordinate-delta-20260618T063926Z.json`. |
| Codex-injected MCP caveat | The in-thread injected `mcp__rift_game` transport was stale and still reported current-truth-only blockers. The proof used a local MCP client that spawned the patched repo server directly. Restart/reload the Codex MCP transport before relying on injected `mcp__rift_game` for this new behavior. |
| Safety | The live wrapper sent one approved bounded movement input and released movement keys. No CE, x64dbg, provider writes, public route live control, broad reusable approval token, or SavedVariables-as-live-truth path was used. |

## Code and artifact changes

| Path | Change |
|---|---|
| `tools\rift-game-mcp\index.mjs` | Added current-proof artifact reading, target/freshness summaries, proof-gate evaluation, proof-backed Phase 9 preflight selection, and approval phrases tied to `proofSource` / `proofUpdatedAt`. |
| `tools\rift-game-mcp\test-control-tools.mjs` | Added no-input assertions that readiness/preflight surface current-proof schema and approval phrases include proof source/timestamp fields. |
| `tools\rift-game-mcp\README.md` | Documented current-proof-backed preflight and exact approval phrase semantics. |
| `scripts\postupdate_owner_root_rediscovery.py` / `scripts\postupdate_static_access_chain.py` | Fixed process-start comparison to normalize UTC/local offset timestamps instead of fragile string-prefix checks. |
| `scripts\scan_current_pid_coordinate_family.py` | Added UTF-8 BOM-safe JSON loading for reference files. |
| `scripts\current_pid_candidate_readback.py` | Added `--reference-file` reuse path with UTF-8 BOM-safe JSON loading to avoid unnecessary fresh capture reruns. |
| `docs\recovery\coordinate-recovery-profile.json` / `docs\recovery\current-proof-anchor-readback.json` | Refreshed current target proof profile for PID `130540` / HWND `0x9310EA`. |

## Validation and error checks

| Command / evidence | Result |
|---|---|
| `node --check tools\rift-game-mcp\index.mjs` | Passed. |
| `node --check tools\rift-game-mcp\test-control-tools.mjs` | Passed. |
| `npm run validate` in `tools\rift-game-mcp` | Passed; 26 expected tools, control output/safety schema checks, smoke self-test. |
| `npm run test:control` in `tools\rift-game-mcp` | Passed; classifier/preflight/executor dry-run/release/plan/latest-artifact tests. |
| `npm run test:smoke` in `tools\rift-game-mcp` | Passed. |
| `python -m py_compile` for touched Python helpers/tests | Passed. |
| `python -m unittest scripts.test_postupdate_owner_root_rediscovery scripts.test_postupdate_static_access_chain scripts.test_scan_current_pid_coordinate_family scripts.test_current_pid_candidate_readback` | Passed; 26 tests. |
| `git diff --check` | Passed. |
| Live Phase 10 wrapper proof | Passed after external coordinate delta verification; wrapper itself correctly returned `executed-awaiting-live-coordinate-verification` until that verifier ran. |

## Remaining caveats

- `docs\recovery\current-truth.json` remains historical/stale for PID `12664`; do not use it as current live movement truth for PID `130540`.
- The injected Codex `mcp__rift_game` server/transport must be restarted or reloaded before it exposes the proof-backed preflight behavior.
- Current-proof freshness still ages normally; rerun same-target proof/readback before later movement if the proof age exceeds the selected preflight threshold.
