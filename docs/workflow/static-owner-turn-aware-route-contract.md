# Static owner turn-aware route contract

## Purpose

This contract covers the first turn-aware navigation layer above the promoted
static owner coordinate resolver. It keeps candidate yaw/facing evidence useful
for planning while preventing it from silently becoming promoted route-control
truth.

## Helpers

| Helper | Output kind | Live input? | Purpose |
|---|---|---:|---|
| `scripts\static-owner-turn-aware-route-plan.cmd` | `static-owner-turn-aware-route-plan` | No | Builds a dry-run first-action plan: `stop`, `forward`, `turn-left`, or `turn-right`. |
| `scripts\static-owner-validate-turn-aware-route-plan.cmd` | `static-owner-turn-aware-route-plan-contract-validation` | No | Validates saved turn-aware plan summaries. |
| `scripts\static-owner-turn-forward-experiment.cmd` | `static-owner-turn-forward-experiment` | Only with all live approval flags | Runs one bounded turn-then-forward experiment; not a route loop. |
| `scripts\static-owner-validate-turn-forward-experiment.cmd` | `static-owner-turn-forward-experiment-contract-validation` | No | Validates saved turn-forward experiment summaries. |

## Turn-aware dry-run plan contract

The planner is always dry-run only. Consumers must reject a plan summary unless
these values remain true:

| Field | Required value | Why |
|---|---:|---|
| `kind` | `static-owner-turn-aware-route-plan` | Confirms the artifact source. |
| `status` | `passed` | Failed plans are not consumable. |
| `verdict` | `turn-aware-route-plan-built` | Confirms planner completion. |
| `plan.candidateOnly` | `true` | Facing/yaw is still candidate evidence. |
| `plan.dryRunOnly` | `true` | Plan artifact did not send input. |
| `plan.movementPermission` | `false` | Plan alone cannot authorize movement. |
| `plan.navigationControl` | `false` | Plan alone cannot control route execution. |
| `plan.facingPromotion` | `false` | Yaw/facing remains unpromoted. |
| `safety.movementSent` | `false` | Planner must not move. |
| `safety.inputSent` | `false` | Planner must not send keys. |
| `safety.noCheatEngine` | `true` | CE is not part of this lane. |
| `safety.x64dbgAttach` | `false` | Debugger attach is not part of this lane. |
| `safety.providerWrites` | `false` | Provider repos stay read-only. |

If the first action is `turn-left` or `turn-right` and
`--allow-candidate-turn-control` was not provided, the plan must include
`candidate-turn-control-not-enabled` in `plan.executionBlockers`.

Checked-in fixtures cover the core planner cases:

| Fixture | First action | Classification |
|---|---|---|
| `scripts\navigation\testdata\static-owner-turn-aware-route-plan-summary-aligned.json` | `forward` | `aligned` |
| `scripts\navigation\testdata\static-owner-turn-aware-route-plan-summary-small-angle.json` | `forward` | `small-angle` |
| `scripts\navigation\testdata\static-owner-turn-aware-route-plan-summary-turn-needed.json` | `turn-right` | `turn-needed` |
| `scripts\navigation\testdata\static-owner-turn-aware-route-plan-summary-opposite-facing.json` | `turn-left` | `opposite-facing` |

## Turn-forward live experiment contract

The live experiment is one sequence only:

1. build a turn-aware dry-run plan from a fresh static-owner state;
2. if the plan requires a turn, require `--allow-candidate-turn-control` and
   `--turn-approved`;
3. run one bounded turn stimulus;
4. delegate the forward pulse to `static-owner-nav-route-step`, which performs
   another fresh static-chain readback before sending `W`.

Live execution must also require `--movement-approved`.

| Guardrail | Default |
|---|---:|
| Max route steps | `1` |
| Max initial turn | `90.0` degrees |
| Max cumulative turn | `90.0` degrees |
| Max observed turn | `90.0` degrees |
| Max total input duration | `600` ms |
| Default turn hold | `175` ms |
| Default forward hold | `250` ms |

The experiment may set `safety.navigationControl=true` only when live input was
actually sent. It still must keep proof, actor-chain, facing promotion,
provider writes, CE, and x64dbg disabled.

## Validation commands

```powershell
cmd /c scripts\static-owner-validate-turn-aware-route-plan.cmd scripts\navigation\testdata\static-owner-turn-aware-route-plan-summary-turn-needed.json --json
cmd /c scripts\static-owner-turn-aware-route-plan.cmd --destination-x 1 --destination-z 2 --dry-run --json
cmd /c scripts\static-owner-turn-forward-experiment.cmd --destination-x 1 --destination-z 2 --dry-run --json
python -m unittest scripts.test_static_owner_turn_aware_route_plan scripts.test_static_owner_turn_forward_experiment
```

Remove `--dry-run` only for a bounded live test after exact target/focus/capture
preflights are satisfied and the operator has explicitly approved live turn and
movement input for the current session.
