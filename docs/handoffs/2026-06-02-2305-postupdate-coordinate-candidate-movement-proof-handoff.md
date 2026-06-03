# Post-update coordinate candidate movement-proof handoff — 2026-06-02 23:05 UTC

## TL;DR

The old promoted player-coordinate resolver is still blocked after the 2026-06-02 RIFT update:

```text
[rift_x64+0x32EBC80] == 0x0
```

The strongest replacement evidence is now the **candidate-only** global-container coordinate chain:

```text
[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30
```

It has passed stationary readback, pointer-family backtrace to the module global, and one controlled movement/API-now proof. It has **not** passed restart/relog survival and has **not** been promoted or written to current truth.

## Current state

| Surface | State |
|---|---|
| Current branch before this handoff | `main` aligned with `origin/main` at `1b66418 Add post-update recovery handoff` |
| Old promoted coordinate root | Blocked: `[rift_x64+0x32EBC80]` reads null on post-update PID `77152` |
| Candidate coordinate chain | `[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30` |
| Latest candidate coordinate | `(7261.1806640625, 821.4239501953125, 2990.301025390625)` |
| Latest API-now vs chain-now | Passed; max abs delta `0.003950195312540927` |
| Movement proof | One bounded `W` pulse for `800 ms`; foreground and exact PID/HWND verified by `RiftReader.SendInput` |
| Restart/relog survival | Not run |
| Current-truth update | Not performed |
| Proof/actor-chain promotion | Not performed |
| Client/game restart | Not performed |

## Promoted truth vs candidate-only truth

| Category | Chain | Status | Consumer rule |
|---|---|---|---|
| Old promoted coordinate resolver | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` | Blocked by newer root-null readback | Do not use for navigation or movement |
| Post-update coordinate candidate | `[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30` | Candidate-only, movement/API-proven, no restart survival | Surface as evidence only; not route/actionable truth |
| Static orientation/layout root | `[rift_x64+0x335F508]` | Orientation/matrix-like, not position | Keep as non-position clue only |

## Evidence captured this session

| Evidence | Result | Artifact |
|---|---|---|
| Stationary candidate polling | 5/5 samples matched; drift `0.0` | `scripts\captures\postupdate-global-container-coordinate-readback-20260602-223909-905242\summary.json` |
| Exact-target static access-chain read | `[rift_x64+0x335F508]` classified orientation/matrix, not position | `scripts\captures\postupdate-static-access-chain-20260602-224326-874505\summary.json` |
| Pointer-family scan of coordinate field | No direct pointer hits for `0x1D4D7D4FDD8` | `scripts\captures\pointer-family-scan-20260602-224649-353798\summary.json` |
| Pointer-family scan of child object | Heap references, broad fanout, no module root inside bounded run | `scripts\captures\pointer-family-scan-20260602-224738-749064\summary.json` |
| Pointer-family scan of container | Module hit at `0x7FF72449D7E8 == rift_x64+0x32DD7E8` | `scripts\captures\pointer-family-scan-20260602-224738-271284\summary.json` |
| Movement pulse | `W`, `800 ms`, exact PID `77152`, HWND `0x17A0DB2`; foreground verified | SendInput console JSON in session transcript |
| Post-move API reference | API coordinate `(7261.1797, 821.42, 2990.3)` | `scripts\captures\rift-api-reference-currentpid-77152-20260602-225531.json` |
| Post-move candidate readback with API reference | Best chain `+0x28/+0x2C/+0x30`; max abs delta `0.003950195312540927` | `scripts\captures\postupdate-global-container-coordinate-readback-20260602-225839-858745\summary.json` |
| Movement proof packet | Movement planar delta `4.800616746509729`; API-vs-chain max abs delta `0.003950195312540927` | `scripts\captures\postupdate-global-container-movement-proof-20260602-230020-479116\summary.json` |

## Code/status surfaces changed

| File | Purpose |
|---|---|
| `tools/riftreader_workflow/decision_packet.py` | Surfaces `postUpdateRecovery` candidate, keeps old promoted root blocked, prefers root-null blocker over later stale-target mismatch artifacts |
| `scripts/navigation_consumer_state.py` | Adds candidate-only `postUpdateRecovery` visibility for downstream consumers while keeping route control blocked |
| `docs/schemas/navigation/navigation-consumer-state.schema.json` | Adds schema coverage for candidate-only post-update recovery fields |
| `scripts/postupdate_owner_root_rediscovery.py` | Extracts current candidate target/address/reference fields from the new nested global-container readback schema |
| `scripts/postupdate_static_access_chain.py` | Prefers current candidate PID/HWND/module-base over stale static-readback target fields |
| `scripts/postupdate_global_container_coordinate_readback.py` | Adds `--reference-json` so post-movement readback can classify against API-now instead of stale pre-move reference |
| Tests under `scripts/test_*` | Cover the new stale-target handling, candidate-only consumer state, decision packet candidate surfacing, and fresh API reference parsing |

## Validation run

| Command | Result |
|---|---|
| `python -m py_compile ...` for changed helpers/tests | Passed |
| `python -m unittest scripts.test_navigation_consumer_state scripts.test_decision_packet scripts.test_postupdate_owner_root_rediscovery scripts.test_postupdate_static_access_chain scripts.test_postupdate_global_container_coordinate_readback` | Passed: `Ran 109 tests in 37.381s`, OK |
| `git --no-pager diff --check` | Passed; CRLF warnings only |
| `python scripts\navigation_schema_validate.py --schema-key navigation-consumer-state --input .riftreader-local\navigation-consumer-state\latest\summary.json --json` | Passed; validation error count `0` |
| `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` | Safe checks passed; packet remains blocked-safe on old root-null blocker |

## Current blockers

| Blocker | Meaning |
|---|---|
| `latest-static-owner-readback-root-pointer-null` | The old promoted static root is dead on the current post-update epoch |
| `restart-survival-not-run` | The candidate has not survived client/game restart or relog |
| `promotion-not-performed` | Candidate remains evidence-only, not current truth |
| Launcher/relogin readiness stale | Read-only launcher inspection showed launcher present but minimized/offscreen; login readiness artifacts are stale and not suitable for automated restart/relogin execution |

## Safety record

| Action class | State |
|---|---|
| Movement/input | One approved `W` movement pulse sent for proof; no route control |
| Client/game restart | Not performed |
| x64dbg / Cheat Engine | Not used |
| Target memory writes | None |
| Provider repo writes | None |
| Current truth / proof promotion | None |
| Git push | Pending after this handoff is committed |

## Resume cue

Start from this handoff, then refresh the decision packet:

```powershell
cmd /c scripts\riftreader-decision-packet.cmd --compact-json --write
```

Treat `[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30` as the current strongest **candidate-only** coordinate chain. Do not promote or use for navigation until restart/relog survival and a promotion-readiness review pass.

## Recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Build a dedicated restart-survival packet for `0x32DD7E8 -> +0x80 -> +0x28` | Final missing proof gate before promotion |
| 2 | Refresh current launcher/relogin readiness artifacts for PID `77152` or the next epoch | Existing login artifacts are stale and target a May 20 process |
| 3 | Make Glyph launcher visible and classify button state before any automated relaunch | Current launcher is minimized/offscreen |
| 4 | Add tracked movement-proof packet helper | Replace the one-off summary writer with repeatable proof tooling |
| 5 | Add decision-packet visibility for latest movement-proof packet | Keeps future agents from missing the movement/API proof |
| 6 | Run a second controlled movement vector after restart plan is ready | Strengthens displacement proof beyond one forward pulse |
| 7 | Add restart-survival schema for coordinate candidates | Makes promotion review machine-checkable |
| 8 | Keep old `[rift_x64+0x32EBC80]` resolver blocked everywhere | Prevents stale promoted truth from leaking into route/navigation |
| 9 | Run promotion-readiness review only after restart survival | Avoids over-promoting a single-epoch candidate |
| 10 | Update current truth only through the existing gated apply path | Preserves auditability and rollback safety |
