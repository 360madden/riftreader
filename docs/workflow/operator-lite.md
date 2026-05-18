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
- Local Artifact Bridge Desktop ChatGPT handoff packet;
- Local Artifact Bridge payload index;
- Local Artifact Bridge inbox index;
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
| Bridge ChatGPT Handoff | Runs `scripts\riftreader-local-artifact-bridge.cmd --chatgpt-handoff --payload-root artifacts\chatgpt-payloads --json`. | Prints the redacted Desktop ChatGPT starter packet with read order, inbox schema, and safety rules. |
| Bridge Payload Index | Runs `scripts\riftreader-local-artifact-bridge.cmd --index --payload-root artifacts\chatgpt-payloads --json`. | Reads the curated payload index only; no HTTP serving or tunnel management. |
| Bridge Inbox Index | Runs `scripts\riftreader-local-artifact-bridge.cmd --inbox-index --json`. | Reads guarded Local Inbox v0 metadata under `.riftreader-local`; no apply/execute. |
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

The bridge self-test uses a temporary payload and ephemeral loopback server; it does not start the persistent `--serve` mode. The bridge preflight/index/handoff actions read only registered payload metadata from `artifacts\chatgpt-payloads` and generate redacted operator/ChatGPT guidance. The bridge inbox index reads ignored Local Inbox v0 metadata only.

Operator Lite does not stage, commit, push, reset, clean, send game input, run movement, attach CE/x64dbg, start bridge `--serve`, start `cloudflared`, apply inbox content, or write provider repos. Current stale proof remains historical-only until fresh current-PID recovery and same-target `ProofOnly` pass.

## Local Artifact Bridge panel

The GUI includes a small Local Artifact Bridge status panel. It summarizes the current curated payload count, latest payload ID, and guarded inbox item count from:

```text
artifacts\chatgpt-payloads
.riftreader-local\artifact-bridge-inbox
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
| Local Artifact Bridge | Purple command/handoff/index rows, neutral docs/copy/template row, and a blue status strip. | Prevents bridge button overflow while keeping checks, handoff, indexes, docs, templates, and prompt-copy actions visually separate. |
| Locked Live Controls | Red locked badges instead of normal action buttons. | Shows unsafe live actions are intentionally unavailable. |

The window also includes a persistent safe-mode status bar and a dark output log for better contrast while preserving the same no-input/no-debugger/no-Git-mutation safety model.
