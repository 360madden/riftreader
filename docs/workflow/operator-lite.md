# Operator Lite

Created: 2026-05-17
Updated: 2026-05-18
Scope: Offline-safe local launcher for the local ChatGPT/non-Codex RiftReader workflow-control-plane helpers.

## Verdict

Operator Lite v0 is a small Python/Tkinter helper that launches only safe workflow commands:

- Workflow Status;
- Compact ChatGPT SITREP;
- Live-Test Fast-Lane Triage;
- Package Intake dry-run;
- Package Intake self-test;
- Local Artifact Bridge self-test;
- Local Artifact Bridge preflight;
- Local Artifact Bridge Desktop ChatGPT session-start packet;
- Local Artifact Bridge Desktop ChatGPT handoff packet;
- Local Artifact Bridge bootstrap payload;
- Local Artifact Bridge payload index;
- Local Artifact Bridge inbox index;
- Local Artifact Bridge latest inbox read;
- Local Artifact Bridge package draft export;
- Local Artifact Bridge docs/instruction helpers;
- Git Status;
- Open Latest Report.

It intentionally disables target-control, visual gate, ProofOnly, movement, CE, x64dbg, bridge serve/tunnel management, staging, committing, and pushing.

## Commands

Launch GUI:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd
```

Headless command-plan/self-test:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd --self-test --json
```

List safe command keys:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd --list-commands --json
```

Run one safe GUI command from the CLI:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd --run bridge-session-start --json
```

Common aliases are accepted:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd --session-start --json
.\scripts\riftreader-operator-lite.cmd --run session-start --json
.\scripts\riftreader-operator-lite.cmd --bridge-preflight --json
.\scripts\riftreader-operator-lite.cmd --latest-inbox --json
.\scripts\riftreader-operator-lite.cmd --package-draft --json
```

Run the safe bridge startup check group:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd --run-all bridge-startup-checks --json
.\scripts\riftreader-operator-lite.cmd --bridge-startup-checks --json
```

Help:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd /help
```

## Command switches

| Switch | Action | Safety |
|---|---|---|
| `/help` | Prints the same help as `--help`. | No command is run. |
| `--repo-root <path>` | Uses a specific repo root. | Resolves locally; does not mutate Git. |
| `--self-test` | Validates Operator Lite command wiring. | Does not launch the GUI. |
| `--command-plan` | Prints the full safe command plan. | Read-only plan output. |
| `--list-commands` | Lists keys, aliases, and groups allowed by `--run` / `--run-all`. | Does not execute commands. |
| `--run <command-key>` | Runs one known safe command spec, such as `bridge-session-start`. | Still enforces denylist, script existence checks, timeouts, and expected exit codes. |
| `--run-all <group-key>` | Runs one known safe group, currently `bridge-startup-checks`. | Sequential safe commands only; no serving or tunneling. |
| `--session-start` | Shortcut for `--run bridge-session-start`. | Same denylist and timeout checks as `--run`. |
| `--bridge-preflight` | Shortcut for `--run bridge-preflight`. | Does not start a server or tunnel. |
| `--latest-inbox` | Shortcut for `--run bridge-inbox-latest`. | Reads local inbox only; no apply/execute. |
| `--package-draft` | Shortcut for `--run bridge-inbox-package-draft`. | Converts the latest `package-proposal` inbox item into an ignored local package draft only; no apply/execute or repo target writes. |
| `--bridge-startup-checks` | Shortcut for `--run-all bridge-startup-checks`. | Runs self-test, preflight, and session-start without persistent serving. |
| `--json` | Emits machine-readable JSON for command-plan/list/run/run-all modes. | No extra behavior by itself. |

`--run` and `--run-all` are intentionally not arbitrary shell runners. They accept only keys already present in Operator Lite's safe command/group registry. Unknown keys return exit code `2`; denied fragments such as `--serve`, `cloudflared`, Git mutation, ProofOnly, target-control, CE, and x64dbg remain blocked.

Current command aliases:

| Alias | Resolves to |
|---|---|
| `session-start` | `bridge-session-start` |
| `bridge-start` | `bridge-session-start` |
| `preflight` | `bridge-preflight` |
| `latest-inbox` | `bridge-inbox-latest` |
| `inbox-latest` | `bridge-inbox-latest` |
| `package-draft` | `bridge-inbox-package-draft` |
| `inbox-package-draft` | `bridge-inbox-package-draft` |
| `draft-package` | `bridge-inbox-package-draft` |

Current group:

| Group | Commands |
|---|---|
| `bridge-startup-checks` | `bridge-selftest`, `bridge-preflight`, `bridge-session-start` |

## Buttons

| Button | Action | Safety |
|---|---|---|
| Refresh Workflow Status | Runs `scripts\riftreader-workflow-status.cmd --write`. | No input/movement/debugger/Git mutation; exit `2` means a safe blocker. |
| Compact ChatGPT SITREP | Runs `scripts\riftreader-workflow-status.cmd --compact --write`. | Paste-ready for desktop ChatGPT; exit `2` means a safe blocker. |
| Run Live-Test Triage | Runs `scripts\riftreader-live-triage.cmd --write`. | No input/movement/debugger/Git mutation. |
| Package Intake Dry-Run | Lets the operator choose a package and runs intake without `--apply`, printing compact JSON. | No repo target writes; dry-run still writes an ignored package diff. |
| Package Intake Self-Test | Runs `scripts\riftreader-package-intake-selftest.cmd`. | Generates an ignored package and proves dry-run package intake without repo target writes. |
| Bridge Self-Test | Runs `scripts\riftreader-local-artifact-bridge.cmd --self-test --json`. | Exercises bridge reads plus guarded inbox in a temp payload and ephemeral loopback server; no persistent server or tunnel. |
| Bridge Preflight | Runs `scripts\riftreader-local-artifact-bridge.cmd --preflight --payload-root artifacts\chatgpt-payloads --json`. | Checks payload readiness, inbox safety flags, and redacted URL hints without starting a persistent server or tunnel; exit `2` means a safe blocker. |
| Bridge Session Start | Runs `scripts\riftreader-local-artifact-bridge.cmd --session-start --payload-root artifacts\chatgpt-payloads --json`. | Prints one redacted Desktop ChatGPT setup packet with preflight, latest payload, latest inbox, manual commands, and next steps; no serving/tunnel. |
| Bridge ChatGPT Handoff | Runs `scripts\riftreader-local-artifact-bridge.cmd --chatgpt-handoff --payload-root artifacts\chatgpt-payloads --json`. | Prints the redacted Desktop ChatGPT starter packet with read order, inbox schema, and safety rules. |
| Bridge Bootstrap Payload | Runs `scripts\riftreader-local-artifact-bridge.cmd --bootstrap-payload --payload-root artifacts\chatgpt-payloads --json`. | Creates a curated starter payload from fixed repo-owned docs; no source edits or Git mutation. |
| Bridge Payload Index | Runs `scripts\riftreader-local-artifact-bridge.cmd --index --payload-root artifacts\chatgpt-payloads --json`. | Reads the curated payload index only; no HTTP serving or tunnel management. |
| Bridge Inbox Index | Runs `scripts\riftreader-local-artifact-bridge.cmd --inbox-index --json`. | Reads guarded Local Inbox v0 metadata under `.riftreader-local`; no apply/execute. |
| Bridge Latest Inbox | Runs `scripts\riftreader-local-artifact-bridge.cmd --inbox-read-latest --json`. | Reads the newest stored proposal or returns a safe empty-inbox blocker; no apply/execute. |
| Bridge Package Draft | Runs `scripts\riftreader-local-artifact-bridge.cmd --inbox-package-draft --json`. | Converts the latest `package-proposal` inbox item into `.riftreader-local\artifact-bridge-package-drafts`; no apply/execute, Git mutation, or repo target writes. |
| Open Bridge Docs | Opens `docs\workflow\local-artifact-bridge.md`. | Local view only. |
| Copy Bridge Start Command | Copies the manual `--serve --token auto --max-inbox-mb 1` command. | Does not run the command; the operator remains in control of local serving. |
| Copy Inbox JSON Template | Copies a ready-to-fill Local Inbox v0 JSON message template. | Template is inert; it does not post, apply, execute, or mutate the repo. |
| Copy Redacted Bridge Instructions | Copies placeholder `<token>` bridge/tunnel/inbox instructions. | Does not copy a real token; tunnel startup remains manual. |
| Copy ChatGPT Bridge Prompt | Copies a placeholder prompt that tells Desktop ChatGPT to start at `/<token>/`, `/health`, `/payloads/latest/readme.md`, and `/payloads/latest/chunks.json`; it mentions `/inbox/messages` only as operator-approved proposal intake. | Does not copy a real token; only lists safe bridge endpoints. |
| Git Status | Runs `git --no-pager status --short --branch`. | Read-only Git. |
| Open Latest Report | Opens latest ignored `.riftreader-local` report. | Local view only. |
| Target-Control / Visual Gate / ProofOnly / Movement / Bridge Serve-Tunnel | Disabled in v0. | Prevents live action drift and avoids accidental local-server exposure. |

## Safety contract

Operator Lite v0 writes only through the underlying safe helpers:

- `.riftreader-local\workflow-status\...`
- `.riftreader-local\live-test-triage\...`
- `.riftreader-local\package-intake\...`
- `.riftreader-local\package-intake-selftest\...`
- `.riftreader-local\artifact-bridge-inbox\...` when an external client uses the bridge inbox while the operator is manually serving it.
- `.riftreader-local\artifact-bridge-package-drafts\...` when the operator exports an approved package-proposal into an inert local draft.

The bridge self-test uses a temporary payload and ephemeral loopback server; it does not start the persistent `--serve` mode. The bridge preflight/index/session-start/handoff actions read only registered payload metadata from `artifacts\chatgpt-payloads` and generate redacted operator/ChatGPT guidance. The bridge bootstrap action creates a curated payload under `artifacts\chatgpt-payloads` from fixed repo-owned docs only. The bridge inbox index/latest actions read ignored Local Inbox v0 metadata/messages only. The bridge package-draft action writes an ignored package draft only; applying, executing checks, staging, committing, and pushing remain separate explicit actions.

Operator Lite does not stage, commit, push, reset, clean, send game input, run movement, attach CE/x64dbg, start bridge `--serve`, start `cloudflared`, apply inbox content, or write provider repos. Current stale proof remains historical-only until fresh current-PID recovery and same-target `ProofOnly` pass.

## Local Artifact Bridge panel

The GUI includes a small Local Artifact Bridge status panel. It summarizes the current curated payload count, latest payload ID, guarded inbox item count, and package draft count from:

```text
artifacts\chatgpt-payloads
.riftreader-local\artifact-bridge-inbox
.riftreader-local\artifact-bridge-package-drafts
```

This panel is intentionally local and safe. To actually serve a payload or accept inbox proposals, the operator must still start the bridge manually:

```powershell
.\scripts\riftreader-local-artifact-bridge.cmd --serve --payload-root artifacts\chatgpt-payloads --port 8765 --token auto --max-response-mb 25 --max-inbox-mb 1
```

Tunnel management also remains manual:

```powershell
cloudflared tunnel --url http://127.0.0.1:8765
```

Operator Lite copies only redacted placeholder instructions, start commands, inbox templates, and prompts such as `http://127.0.0.1:8765/<token>/`, `http://127.0.0.1:8765/<token>/chatgpt-handoff.json`, and `http://127.0.0.1:8765/<token>/health`; it does not copy or mint a real bridge token. The ChatGPT prompt points at the bridge handoff packet, landing page, health endpoint, latest README alias, latest chunks alias, registered chunk URL pattern, inbox schema endpoint, and the guarded inbox endpoint only for explicit operator-approved JSON proposals.

## Visual layout

Operator Lite groups actions into high-contrast panels so buttons do not blend together:

| Section | Visual treatment | Purpose |
|---|---|---|
| Workflow Status & Triage | Blue primary buttons plus amber triage button. | Separates ordinary status refresh from blocker classification. |
| Packages, Reports & Git | Green package buttons and neutral report/Git buttons. | Makes dry-run package actions distinct from read-only views. |
| Local Artifact Bridge | Purple command/session/handoff/index/package-draft rows, amber bootstrap button, neutral docs/copy/template row, and a blue status strip. | Prevents bridge button overflow while keeping checks, session-start, handoff, payload bootstrap, indexes, inbox review, package drafts, docs, templates, and prompt-copy actions visually separate. |
| Locked Live Controls | Red locked badges instead of normal action buttons. | Shows unsafe live actions are intentionally unavailable. |

The window also includes a persistent safe-mode status bar and a dark output log for better contrast while preserving the same no-input/no-debugger/no-Git-mutation safety model.
