# OpenCode Bridge for the Non-Codex Desktop ChatGPT Workflow

<!-- RIFTREADER-OPENCODE-DEMOTION-BEGIN -->
## Current status: OpenCode optional only

OpenCode is no longer the default RiftReader executor. Use it only when explicitly authorized for a scoped task. Normal workflow uses local Python helpers plus local `git`/`gh`.
<!-- RIFTREADER-OPENCODE-DEMOTION-END -->

Created: 2026-05-16
Scope: Optional local OpenCode use for RiftReader when Codex is unavailable,
quota-blocked, or not being used.

## Verdict

OpenCode is useful in this lane as a **local executor/status collector** for
desktop ChatGPT. It does not replace the existing package/apply/review/push
boundary. By default, OpenCode should be read-only or validation-only.

## Role split

| Actor | Role |
|---|---|
| Desktop ChatGPT | Planner, reviewer, patch/package author, strategy layer. |
| OpenCode | Local read-only scout, validator, applier runner, handoff/status summarizer. |
| User | Explicit approval for edits, live input, debugger attach, commit, and push. |

## Safety defaults

| Rule | Default |
|---|---|
| Live movement/input | Forbidden unless explicitly approved for that run. |
| CE/x64dbg attach | Forbidden unless explicitly re-approved for that run. |
| Stale proof pointer reuse | Forbidden; old PID/HWND/address data is historical only. |
| Provider repo writes | Forbidden unless the current task explicitly authorizes them. |
| Git stage/commit/push | Forbidden unless explicitly requested with explicit paths. |
| Secrets/config dumps | Forbidden; summarize config shape, not tokens or credentials. |

Current offline baseline: the latest handoff records current proof as
`blocked-target-drift`; old PID `27552` / HWND `0x3411E2` and address
`0x27B1ED850C0` are historical reacquisition/static-chain hints only. Movement
remains blocked until a fresh in-world PID/HWND passes current-PID recovery and
same-target `ProofOnly`.

When a `rift_x64` process is visible again, the status packet should be treated
as **process-aware but no-input**: it may report a current process PID while
still blocking because the proof artifact points at a historical PID/HWND. A
visible process is not by itself game-online/in-world proof. In that case,
OpenCode must report the PID/HWND mismatch clearly, keep stale proof blocked,
and ask for safe current-target reacquisition/status refresh before any
ProofOnly or movement lane.

## Optional project config

A safe tracked template is provided at:

```text
.opencode/opencode.example.jsonc
```

Do not put provider keys, Context7 keys, GitHub tokens, or local secrets in this
tracked file. If local overrides are needed, use ignored files such as:

```text
.opencode/opencode.local.jsonc
.opencode/secrets*
.opencode/sessions/
```

Template agent defaults:

| Agent | Default lane |
|---|---|
| `riftreader-readonly` | Compact status/SITREP and read-only local truth. |
| `riftreader-validator` | Targeted validation; reports exit `2` status helpers as safe blockers. |
| `riftreader-applier` | Package dry-run review first; `--apply` only after explicit approval. |
| `riftreader-integration` | Autonomous patch-and-test OpenCode integration only; no live/Git mutation. |
| `riftreader-handoff-scribe` | Approved handoff/status docs only. |
| `riftreader-live-observer` | No-input live triage/status summaries; stale proof remains historical. |

## Recommended commands

Deterministic status packet without OpenCode:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-workflow-status.cmd
```

Machine-readable status packet:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-workflow-status.cmd --json
```

Compact paste-ready SITREP for desktop ChatGPT:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-workflow-status.cmd --compact
```

Compact machine-readable SITREP:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-workflow-status.cmd --compact-json
```

The compact SITREP includes a `bridgeCommands` capability list showing whether
the local wrapper scripts exist, including adaptive prompt dry-run, autonomous
OpenCode integration, package self-test, package review, live observer, Operator
Lite, and deterministic status commands.

Write ignored JSON/Markdown artifacts under `.riftreader-local`:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-workflow-status.cmd --write
```

Optional OpenCode one-shot SITREP:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-opencode-sitrep.cmd
```

Dry-run the adaptive prompt without launching OpenCode:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-opencode-prompt.cmd --lane sitrep --json --skip-opencode-check
```

Self-test every adaptive lane prompt without launching OpenCode or using a model:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-opencode-prompt.cmd --self-test
```

Autonomous OpenCode-integration development lane:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-opencode-integration.cmd
```

This lane is patch-and-test only for OpenCode bridge code, wrappers, tests, and
workflow docs. It must not send live input, run movement/proof promotion, attach
CE/x64dbg, stage, commit, push, pull, reset, clean, or write provider repos.

Every generated prompt summary now includes a machine-readable `lanePolicy`
object. This keeps the safety/edit contract explicit for downstream wrappers and
review tools, including the optional configured-agent name to use with `--agent`
when the example OpenCode config has been copied locally:

| Lane | `allowsTrackedEdits` | Meaning |
|---|---:|---|
| `sitrep` | `false` | Read-only local truth summary; ignored prompt/status artifacts only. |
| `live-observer` | `false` | No-input observer; never repairs proof or sends input. |
| `package-review` | `false` | Dry-run package intake/review; no apply without current-turn approval. |
| `integration` | `true` | May patch only OpenCode bridge files, wrappers, tests, docs, and example config. |

For `integration`, `lanePolicy.allowedEditPaths` is the authoritative edit
allowlist. If the next useful change falls outside that list, the OpenCode agent
must stop and report a hard blocker instead of broadening scope.
`lanePolicy.groundingFiles` lists the bridge files, wrappers, tests, workflow
docs, and example config that should be inspected before the first patch in an
integration run.
`lanePolicy.recommendedAgent` is advisory only; the bridge does not require it
unless the operator passes `--agent` or sets `RIFTREADER_OPENCODE_AGENT`.

The bridge `--self-test` validates these lane-policy invariants in addition to
prompt command/safety text so wrapper drift fails before a model run.

The OpenCode wrappers now call
`tools\riftreader_workflow\opencode_bridge.py` first. That helper builds a
fresh status packet, writes the generated prompt under
`.riftreader-local\opencode-prompts\...`, then launches `opencode run` with the
current requested model and reasoning variant. The generated prompt is passed to
OpenCode through stdin rather than as a giant command-line argument, which avoids
Windows command-length failures as the adaptive prompt grows. This keeps the
prompt adaptive to dirty worktrees, stale proof, no-live-process, model
visibility, package-review mode, and live-observer mode instead of relying on
one static command-line prompt.

For `--run`, the bridge uses a streaming `subprocess.Popen` path. OpenCode
stdout and stderr are tee'd live to the terminal while the full streams are
written under `.riftreader-local\opencode-runs\...` as `stdout.txt` and
`stderr.txt`, with a `run-envelope.json` recording exit code, timeout/interrupted
state, previews, byte counts, and artifact paths. If the operator presses
Ctrl+C during the run, the helper attempts to terminate the child process and
returns a clean interrupted envelope instead of a Python traceback.

### Model/provider sanity check

The OpenCode wrappers request an explicit model and reasoning variant instead
of relying on the user/global default:

```text
openai/gpt-5.5
xhigh
```

If you copied `.opencode/opencode.example.jsonc` and want a wrapper run to use a
specific configured agent, pass it through the bridge or set it for the current
shell only:

```powershell
.\scripts\riftreader-opencode-integration.cmd --agent riftreader-integration
$env:RIFTREADER_OPENCODE_AGENT = "riftreader-live-observer"
.\scripts\riftreader-opencode-live-observer.cmd
```

Do not set a project-wide default to the integration agent unless that is the
intended safe default for every local OpenCode run.

Override it only for the current shell when needed:

```powershell
$env:RIFTREADER_OPENCODE_MODEL = "openai/gpt-5.4"
$env:RIFTREADER_OPENCODE_VARIANT = "high"
.\scripts\riftreader-opencode-sitrep.cmd
```

Before blaming provider setup, verify the CLI and the model catalog that the
wrapper actually uses:

```powershell
opencode --version
opencode models openai
opencode run --dir . -m openai/gpt-5.5 --variant xhigh "Say only: provider works"
```

If the desktop app shows `GPT-5.5` but `opencode models openai` does not list
`openai/gpt-5.5`, the PATH/CLI install is stale or different from the desktop
app. Update the CLI package, then rerun the checks:

```powershell
npm view opencode-ai version
npm install -g opencode-ai@latest
```

If `opencode run --dir . -m openai/gpt-5.5 --variant xhigh "Say only: provider works"`
succeeds but bare `opencode run --dir . "Say only: default works"` fails, the
provider is working and the remaining issue is the user/global default model.
Add a top-level `model` to the user-level `opencode.json` or continue using the
RiftReader wrappers, which always pass `-m` and `--variant`:

```json
{
  "model": "openai/gpt-5.5",
  "small_model": "openai/gpt-5.5-fast",
  "provider": {
    "openai": {
      "models": {
        "gpt-5.5": {
          "options": {
            "reasoningEffort": "xhigh",
            "reasoningSummary": "auto"
          }
        }
      }
    }
  }
}
```

Do not paste or publish the full user config if it contains MCP headers,
provider tokens, or other secrets.

The deterministic status packet reports the OpenCode version, requested model,
requested reasoning variant, and whether the model is visible, so desktop
ChatGPT can distinguish a real provider/model outage from a stale
CLI/default-model mismatch.

## Adaptive OpenCode prompt contract

`tools\riftreader_workflow\opencode_bridge.py` is the canonical prompt builder.
It embeds a compact preflight snapshot, but tells OpenCode to rerun the required
status command sequence before final output because repo/process/proof state can
change while the prompt is in flight. Use `--self-test` after changing the
prompt builder, wrapper list, lane rules, or status capability output.

The prompt adapts with these rules:

| Condition | Required OpenCode behavior |
|---|---|
| Dirty worktree | Summarize local paths; do not overwrite, stage, commit, or push. |
| `opencode` model not visible | Report provider/model mismatch before optional lane work. |
| No live `rift_x64` process | Stay offline/status-only; do not run ProofOnly or movement. |
| `artifact-pid-stale` | Treat process presence as process-only context; keep movement blocked. |
| Movement gate closed | Do not send input, `/reloadui`, screenshot hotkeys, movement, or proof promotion. |
| Package review lane | Run dry-run package intake only; `--apply` requires explicit approval. |
| Integration lane | Continue through small validated OpenCode-integration milestones until a hard stop condition. |
| State changes during run | Trust newest command output and say which preflight fact was superseded. |

## Ready-to-paste OpenCode prompts

These are fallback prompts for manual use. Prefer the adaptive wrappers above
for normal runs.

### Read-only SITREP

```text
Use the RiftReader read-only non-Codex bridge. Do not edit files, stage,
commit, push, send live input, run movement, attach CE/x64dbg, or write provider
repos. Run .\scripts\riftreader-workflow-status.cmd --compact-json --write,
then summarize current branch, HEAD, latest handoff, OpenCode version,
requested OpenCode model/model visibility/reasoning variant, liveTarget
verdict/livePids/artifactPid/artifactHwnd, current proof status, movement
permission, blockers, warnings, stale proof reuse policy, validation status,
and next safe action for desktop ChatGPT. If liveTarget is
artifact-pid-stale, say clearly that a `rift_x64` process exists but the proof
artifact is historical, this is not in-world/current-proof validation, and
movement remains blocked.
```

### Validation-only run

```text
Validation only. Do not edit files, stage, commit, push, send live input, run
movement, attach CE/x64dbg, or write provider repos. Run the smallest relevant
validation for the current changed files. Include exact commands, exit codes,
failing output, likely root cause, and the next safest fix. Stop before fixing.
```

### Applier/package inspection

```text
Inspect this desktop ChatGPT package/applier before applying it. Prefer
.\scripts\riftreader-package-intake.cmd --package <path> --compact-json for
manifest-based packages. Confirm every target path is inside
C:\RIFT MODDING\RiftReader and on the explicit allowlist. Do not stage, commit,
push, send live input, run movement, attach CE/x64dbg, or write provider repos.
If approved by the operator, apply it with --apply, preserve backups, run
targeted validation, and summarize changed files plus git diff status.
```

### No-input live observer

```text
Observe only. RIFT may be running, but do not send input, click, move,
/reloadui, attach CE/x64dbg, edit files, stage, commit, push, or promote stale
proof. Run no-input target/process/status checks only. Report PID/HWND/process
epoch, current proof status, movement permission, blockers, and whether
current-PID recovery is still required.
```

### Live-test fast-lane triage

```text
Triage only. Do not edit files, stage, commit, push, send input, run movement,
attach CE/x64dbg, or write provider repos. Run
.\scripts\riftreader-live-triage.cmd --json --write and summarize failedStage,
blockerCategory, evidence artifacts, safety flags, and next safe action for
desktop ChatGPT.
```

## Non-Codex sequence with OpenCode

| Step | Actor | Action |
|---:|---|---|
| 1 | Desktop ChatGPT | Requests local truth or provides a package/applier. |
| 2 | User | Runs deterministic status or OpenCode SITREP locally. |
| 3 | OpenCode | Emits compact local summary and optional ignored artifacts. |
| 4 | User | Pastes the summary into desktop ChatGPT. |
| 5 | Desktop ChatGPT | Reviews and produces next package/applier or instructions. |
| 6 | OpenCode | May inspect/apply/validate only after explicit instruction. |
| 7 | User | Reviews diff and explicitly approves any commit/push. |

## Package Intake Lite

Manifest-based desktop ChatGPT packages can be inspected or applied through:

```powershell
.\scripts\riftreader-package-intake.cmd --package "C:\path\to\package" --compact-json
.\scripts\riftreader-package-intake.cmd --package "C:\path\to\package" --apply --json
```

Optional OpenCode one-shot package review:

```powershell
.\scripts\riftreader-opencode-package-review.cmd "C:\path\to\package-or.zip"
```

Package intake smoke-test without a real package:

```powershell
.\scripts\riftreader-package-intake-selftest.cmd
```

Dry-run inspection writes a package diff and compact Markdown/JSON under
`.riftreader-local\package-intake\...` without touching repo target files.

See `docs/workflow/package-intake-lite.md`.

## Live-Test Fast-Lane Triage

For no-input blocker classification:

```powershell
.\scripts\riftreader-live-triage.cmd --json --write
.\scripts\riftreader-opencode-live-observer.cmd
```

See `docs/workflow/live-test-fast-lane-triage.md`.

## Operator Lite

For a small local button launcher around safe workflow helpers:

```powershell
.\scripts\riftreader-operator-lite.cmd
```

For headless verification:

```powershell
.\scripts\riftreader-operator-lite.cmd --self-test --json
```

See `docs/workflow/operator-lite.md`.

## Acceptance checklist

| Question | Required answer |
|---|---|
| Did OpenCode edit files? | Only if explicitly approved. |
| Did OpenCode send live input/movement? | No, unless explicitly approved for that run. |
| Did OpenCode attach CE/x64dbg? | No, unless explicitly re-approved for that run. |
| Did OpenCode stage/commit/push? | No, unless explicitly requested with explicit paths. |
| Did status output preserve stale-proof boundaries? | Yes; stale PID/HWND/address remains historical only. |
| Does status output distinguish live target from stale artifact? | Yes; a live `rift_x64` process does not make old proof current. |
| Are generated status artifacts ignored? | Yes, under `.riftreader-local/`. |
