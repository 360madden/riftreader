# Timestamped validation ledger

## Purpose

Use the timestamped validation ledger whenever validation may take long enough
that progress, timing, or CI state could become opaque. The helper wraps
validation commands, records UTC start/end timestamps and durations, emits
heartbeats while long commands run, and writes durable local artifacts under
`.riftreader-local/validation-runs/`.

The ledger is evidence only. It does not send live input, move the player,
attach x64dbg or Cheat Engine, write provider repositories, promote proof, or
stage/commit/push Git changes.

## Artifact contract

Default output directory:

```text
.riftreader-local/validation-runs/<YYYYMMDD-HHMMSS-ffffff>/
```

Each run writes:

```text
summary.json
summary.md
commands/<index>-<slug>.stdout.txt
commands/<index>-<slug>.stderr.txt
```

`summary.json` records the tier, status, Git state, budgets, command args,
timestamps, durations, exit codes, stdout/stderr previews, slow-command
warnings, blockers, errors, and safety flags. `summary.md` gives the operator
view: verdict, timing table, slow commands, failures, artifact paths, Git state,
and next action.

## Tiers

| Tier | Use when | Command |
|---|---|---|
| `smoke` | After small edits or before deciding the next validation tier. | `python tools\riftreader_workflow\validation_ledger.py --tier smoke` |
| `targeted` | Before commit for a focused code slice. | `python tools\riftreader_workflow\validation_ledger.py --tier targeted --command "python -m unittest scripts.test_validation_ledger"` |
| `full-local` | Before push or after broad/risky changes. | `python tools\riftreader_workflow\validation_ledger.py --tier full-local` |
| `ci-parity` | After a pushed commit when GitHub Actions should be verified. | `python tools\riftreader_workflow\validation_ledger.py --tier ci-parity --commit HEAD` |
| `custom` | For an explicit one-off command list. | `python tools\riftreader_workflow\validation_ledger.py --tier custom --command-json "[\"python\",\"-m\",\"unittest\",\"scripts.test_validation_ledger\"]"` |

There is also a thin convenience wrapper:

```powershell
cmd /c scripts\riftreader-validation-ledger.cmd --tier smoke
```

## Budgets and slow warnings

Budgets are warnings by default. A command can be slow and the run can still
pass if every command exits successfully.

| Scope | Warning budget |
|---|---:|
| `smoke` total | 120s |
| `targeted` total | 300s |
| `full-local` total | 900s |
| `ci-parity` total | 900s |
| `py_compile` | 30s |
| focused unittest | 120s |
| full unittest discover | 420s |
| policy lint / decision packet | 120s |
| dotnet restore | 180s |
| dotnet build / test | 300s |

Use `--enforce-budget` only when runtime budgets should fail the run:

```powershell
python tools\riftreader_workflow\validation_ledger.py --tier targeted `
  --command "python -m unittest scripts.test_validation_ledger" `
  --enforce-budget
```

## Progress output

Long commands emit progress lines:

```text
[2026-05-31T13:00:00Z] START full-local #1 unittest-discover
[2026-05-31T13:02:00Z] STILL RUNNING full-local #1 unittest-discover elapsed=120.0s
[2026-05-31T13:05:16Z] DONE full-local #1 unittest-discover exit=0 duration=316.4s status=passed
```

Default heartbeat interval is 30 seconds. Override it with:

```powershell
python tools\riftreader_workflow\validation_ledger.py --tier full-local --heartbeat-seconds 15
```

## Status interpretation

| Status | Meaning | Next action |
|---|---|---|
| `passed` | All executed commands met expected exit codes; slow warnings may still be present. | Continue to the next tier, commit gate, or handoff update. |
| `failed` | A command exited unexpectedly, timed out, or exceeded an enforced budget. | Diagnose the first failed command before broadening scope. |
| `blocked` | The helper could not safely run the requested validation, such as malformed command JSON or missing/auth-blocked `gh`. | Resolve the blocker and rerun. |

Exit codes are `0` passed, `1` failed, and `2` blocked.

## Handoff usage

Every substantial handoff should include the latest ledger artifact path and a
short timing summary, for example:

```markdown
Latest validation ledger:
- `.riftreader-local/validation-runs/20260531-130000-123456/summary.md`
- Tier: `full-local`
- Status: `passed`
- Duration: `510.2s`
- Slow commands: `unittest-discover` at `316.4s`
```

If validation was intentionally not run, say exactly which ledger tier was
skipped and why.
