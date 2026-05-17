# OpenCode Bridge for the Non-Codex Desktop ChatGPT Workflow

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

## Ready-to-paste OpenCode prompts

### Read-only SITREP

```text
Use the RiftReader read-only non-Codex bridge. Do not edit files, stage,
commit, push, send live input, run movement, attach CE/x64dbg, or write provider
repos. Run .\scripts\riftreader-workflow-status.cmd --json --write, then
summarize current branch, HEAD, latest handoff, current proof status, movement
permission, blockers, stale proof reuse policy, validation status, and next safe
action for desktop ChatGPT.
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
.\scripts\riftreader-package-intake.cmd --package <path> --json for
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
.\scripts\riftreader-package-intake.cmd --package "C:\path\to\package" --json
.\scripts\riftreader-package-intake.cmd --package "C:\path\to\package" --apply --json
```

See `docs/workflow/package-intake-lite.md`.

## Acceptance checklist

| Question | Required answer |
|---|---|
| Did OpenCode edit files? | Only if explicitly approved. |
| Did OpenCode send live input/movement? | No, unless explicitly approved for that run. |
| Did OpenCode attach CE/x64dbg? | No, unless explicitly re-approved for that run. |
| Did OpenCode stage/commit/push? | No, unless explicitly requested with explicit paths. |
| Did status output preserve stale-proof boundaries? | Yes; stale PID/HWND/address remains historical only. |
| Are generated status artifacts ignored? | Yes, under `.riftreader-local/`. |
