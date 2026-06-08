# Operator Lite

Created: 2026-05-17
Updated: 2026-05-21
Scope: Offline-safe local launcher for the local ChatGPT/non-Codex RiftReader workflow-control-plane helpers.

## Verdict

Operator Lite v0 is a small Python/Tkinter helper that launches only safe workflow commands:

- Workflow Status;
- Compact ChatGPT SITREP;
- Refresh Decision Packet;
- Decision Packet Schema Contract;
- Decision Packet Agent Plan;
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
- newest Local Artifact Bridge package draft summary;
- explicit newest package draft intake dry-run;
- Local Artifact Bridge package-proposal loop self-test;
- Local Artifact Bridge Desktop ChatGPT trial-readiness gate;
- ChatGPT MCP trial-readiness gate;
- MCP Mission Control;
- Browser/Computer Use readiness;
- Latest MCP Artifacts;
- ChatGPT Trial Proof Template;
- Safe Commit Plan;
- Workflow Router;
- Local Artifact Bridge docs/instruction helpers;
- Git Status;
- Open Latest Report.

It intentionally disables target-control, visual gate, ProofOnly, movement, CE, x64dbg, bridge serve/tunnel management, staging, committing, and pushing.

## Decision Packet integration

The local decision-control-plane layer is tracked in
`docs/workflow/local-decision-control-plane-plan.md`.

Operator Lite includes a safe `Refresh Decision Packet` command/button that runs:

```powershell
.\scripts\riftreader-operator-lite.cmd --decision-packet --json
```

It writes only ignored `.riftreader-local\decision-packet\latest\*` artifacts and
returns packet status, lane, risk, blockers, and the safest next command. Operator
Lite also exposes a read-only schema contract shortcut:

```powershell
.\scripts\riftreader-operator-lite.cmd --decision-packet-schema --json
```

That shortcut runs `riftreader-decision-packet.cmd --schema-json`, parses the
contract into `stdoutJson`, and writes no artifacts. Operator Lite also exposes
`--decision-packet-agent-plan --json`, which runs `--agent-plan`, preserves
safe-blocked exit `2`, and parses `agentPlan` plus `llmReminder` into
`stdoutJson`. None of these commands adds movement, debugger, ProofOnly,
target-control, staging, commit, push, serve, or tunnel controls.

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
.\scripts\riftreader-operator-lite.cmd --package-draft-index --json
.\scripts\riftreader-operator-lite.cmd --latest-package-draft --json
.\scripts\riftreader-operator-lite.cmd --latest-operator-draft --json
.\scripts\riftreader-operator-lite.cmd --package-draft-dry-run --json
.\scripts\riftreader-operator-lite.cmd --operator-draft-dry-run --json
.\scripts\riftreader-operator-lite.cmd --package-draft-selftest --json
.\scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json
.\scripts\riftreader-operator-lite.cmd --mcp-mission-control --json
.\scripts\riftreader-operator-lite.cmd --desktop-control-readiness --json
.\scripts\riftreader-desktop-control-readiness.cmd --repair-guide --json
.\scripts\riftreader-desktop-control-readiness.cmd --record-observation --browser-dashboard-smoke-ok --computer-use-stage setup --computer-use-error "Computer Use native pipe path is unavailable" --json
.\scripts\riftreader-operator-lite.cmd --mcp-artifacts --json
.\scripts\riftreader-operator-lite.cmd --chatgpt-trial-proof-template --json
.\scripts\riftreader-operator-lite.cmd --safe-commit-plan --json
.\scripts\riftreader-operator-lite.cmd --workflow-router --json
.\scripts\riftreader-operator-lite.cmd --decision-packet --json
.\scripts\riftreader-operator-lite.cmd --decision-packet-schema --json
.\scripts\riftreader-operator-lite.cmd --decision-packet-agent-plan --json
.\scripts\riftreader-operator-lite.cmd --proposal-loop-checks --json
.\scripts\riftreader-operator-lite.cmd --trial-readiness --json
```

Run the safe bridge startup check group:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd --run-all bridge-startup-checks --json
.\scripts\riftreader-operator-lite.cmd --bridge-startup-checks --json
.\scripts\riftreader-operator-lite.cmd --run-all bridge-proposal-loop-checks --json
.\scripts\riftreader-operator-lite.cmd --proposal-loop-checks --json
.\scripts\riftreader-operator-lite.cmd --run-all bridge-trial-readiness --json
.\scripts\riftreader-operator-lite.cmd --trial-readiness --json
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
| `--command-reference-md` | Prints generated Markdown command reference from the safe command registry. | Docs-only output; no command execution. |
| `--run <command-key>` | Runs one known safe command spec, such as `bridge-session-start`. | Still enforces denylist, script existence checks, timeouts, and expected exit codes. |
| `--run-all <group-key>` | Runs one known safe group, such as `bridge-startup-checks` or `bridge-proposal-loop-checks`. | Sequential safe commands only; no serving or tunneling. |
| `--session-start` | Shortcut for `--run bridge-session-start`. | Same denylist and timeout checks as `--run`. |
| `--bridge-preflight` | Shortcut for `--run bridge-preflight`. | Does not start a server or tunnel. |
| `--latest-inbox` | Shortcut for `--run bridge-inbox-latest`. | Reads local inbox only; no apply/execute. |
| `--package-draft` | Shortcut for `--run bridge-inbox-package-draft`. | Converts the latest `package-proposal` inbox item into an ignored local package draft only; no apply/execute or repo target writes. |
| `--package-draft-index` | Shortcut for `--run package-draft-index`. | Lists ignored package drafts only; no intake, apply, or repo target writes. |
| `--latest-package-draft` | Shortcut for `--run package-draft-latest`. | Prints the newest ignored package draft summary; no intake, apply, or repo target writes. |
| `--latest-operator-draft` | Shortcut for `--run package-draft-latest-operator`. | Prints the newest non-self-test operator draft summary; blocks if only self-test drafts exist. |
| `--package-draft-dry-run` | Shortcut for `--run package-draft-dry-run-latest`. | Explicitly runs package intake dry-run for the newest package draft; never passes `--apply`. |
| `--operator-draft-dry-run` | Shortcut for `--run package-draft-dry-run-latest-operator`. | Explicitly runs package intake dry-run for the newest operator draft; never passes `--apply` and ignores self-test drafts. |
| `--package-draft-selftest` | Shortcut for `--run package-draft-loop-selftest`. | Runs synthetic `package-proposal` to inbox to inert draft to dry-run loop with ignored local artifacts only. |
| `--mcp-trial-readiness` | Shortcut for `--run mcp-trial-readiness`. | Runs compact local ChatGPT MCP trial-readiness checks, including a synthetic package proposal through the MCP transport; may start a temporary loopback-only server, but no public tunnel, ChatGPT registration, persistent serving, apply, Git mutation, live RIFT input, CE, or x64dbg. |
| `--mcp-mission-control` | Shortcut for `--run mcp-mission-control`. | Read-only dashboard; does not start a tunnel or mutate Git. |
| `--desktop-control-readiness` | Shortcut for `--run desktop-control-readiness`. | Reports no-write Browser Use and Computer Use readiness; does not drive browser UI, desktop UI, RIFT input, tunnels, package apply, or Git mutation. |
| `--mcp-artifacts` | Shortcut for `--run mcp-artifacts-latest`. | Read-only latest artifact lookup. |
| `--chatgpt-trial-proof-template` | Shortcut for `--run chatgpt-trial-proof-template`. | Prints a proof JSON template only; does not call ChatGPT. |
| `--safe-commit-plan` | Shortcut for `--run safe-commit-plan`. | Plan-only explicit-path staging checklist; no stage/commit/push. |
| `--workflow-router` | Shortcut for `--run workflow-router-mcp`. | Read-only next-action selector for the MCP lane. |
| `--decision-packet` | Shortcut for `--run decision-packet`. | Writes ignored decision-packet artifacts only; exit `2` means a safe blocker. |
| `--decision-packet-schema` | Shortcut for `--run decision-packet-schema`. | Prints the static schema contract and parses it into `stdoutJson`; no artifact writes. |
| `--decision-packet-agent-plan` | Shortcut for `--run decision-packet-agent-plan`. | Prints parallel-agent-safe work slices and parses `agentPlan`/`llmReminder` into `stdoutJson`; exit `2` means a safe blocker. |
| `--bridge-startup-checks` | Shortcut for `--run-all bridge-startup-checks`. | Runs self-test, preflight, and session-start without persistent serving. |
| `--proposal-loop-checks` | Shortcut for `--run-all bridge-proposal-loop-checks`. | Runs HTTP proposal-to-draft self-test plus local draft-to-intake dry-run self-test; no persistent serving, tunnel, apply, or Git mutation. |
| `--trial-readiness` | Shortcut for `--run-all bridge-trial-readiness`. | Runs self-test, preflight, session-start, inbox index, draft index, and operator-draft availability gate; no serving, tunnel, draft export, dry-run, apply, or Git mutation. |
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
| `package-draft-index` | `package-draft-index` |
| `draft-index` | `package-draft-index` |
| `package-drafts` | `package-draft-index` |
| `latest-package-draft` | `package-draft-latest` |
| `package-draft-latest` | `package-draft-latest` |
| `review-package-draft` | `package-draft-latest` |
| `latest-operator-draft` | `package-draft-latest-operator` |
| `latest-operator-package-draft` | `package-draft-latest-operator` |
| `operator-package-draft` | `package-draft-latest-operator` |
| `package-draft-dry-run` | `package-draft-dry-run-latest` |
| `dry-run-package-draft` | `package-draft-dry-run-latest` |
| `dry-run-latest-draft` | `package-draft-dry-run-latest` |
| `operator-draft-dry-run` | `package-draft-dry-run-latest-operator` |
| `dry-run-operator-draft` | `package-draft-dry-run-latest-operator` |
| `dry-run-latest-operator-draft` | `package-draft-dry-run-latest-operator` |
| `package-draft-selftest` | `package-draft-loop-selftest` |
| `package-draft-self-test` | `package-draft-loop-selftest` |
| `draft-loop-selftest` | `package-draft-loop-selftest` |
| `proposal-loop-selftest` | `package-draft-loop-selftest` |
| `mcp-trial` | `mcp-trial-readiness` |
| `chatgpt-mcp-trial` | `mcp-trial-readiness` |
| `chatgpt-mcp-trial-readiness` | `mcp-trial-readiness` |
| `mcp-mission` | `mcp-mission-control` |
| `desktop-control-readiness` | `desktop-control-readiness` |
| `browser-computer-readiness` | `desktop-control-readiness` |
| `computer-use-readiness` | `desktop-control-readiness` |
| `mcp-mission-control` | `mcp-mission-control` |
| `mcp-artifacts` | `mcp-artifacts-latest` |
| `latest-mcp-artifacts` | `mcp-artifacts-latest` |
| `chatgpt-trial-proof` | `chatgpt-trial-proof-template` |
| `chatgpt-trial-proof-template` | `chatgpt-trial-proof-template` |
| `safe-commit-plan` | `safe-commit-plan` |
| `workflow-router` | `workflow-router-mcp` |
| `mcp-router` | `workflow-router-mcp` |
| `decision-packet` | `decision-packet` |
| `refresh-decision-packet` | `decision-packet` |
| `local-decision-packet` | `decision-packet` |
| `decision-packet-schema` | `decision-packet-schema` |
| `local-decision-packet-schema` | `decision-packet-schema` |
| `decision-packet-agent-plan` | `decision-packet-agent-plan` |
| `agent-plan` | `decision-packet-agent-plan` |
| `local-agent-plan` | `decision-packet-agent-plan` |

Current group aliases:

| Alias | Resolves to |
|---|---|
| `startup` | `bridge-startup-checks` |
| `bridge-checks` | `bridge-startup-checks` |
| `chatgpt-startup` | `bridge-startup-checks` |
| `proposal-loop` | `bridge-proposal-loop-checks` |
| `bridge-proposal-loop` | `bridge-proposal-loop-checks` |
| `package-proposal-loop` | `bridge-proposal-loop-checks` |
| `chatgpt-proposal-loop` | `bridge-proposal-loop-checks` |
| `trial-readiness` | `bridge-trial-readiness` |
| `bridge-trial` | `bridge-trial-readiness` |
| `desktop-chatgpt-trial` | `bridge-trial-readiness` |
| `chatgpt-trial-readiness` | `bridge-trial-readiness` |

Current groups:

| Group | Commands |
|---|---|
| `bridge-startup-checks` | `bridge-selftest`, `bridge-preflight`, `bridge-session-start` |
| `bridge-proposal-loop-checks` | `bridge-selftest`, `package-draft-loop-selftest` |
| `bridge-trial-readiness` | `bridge-selftest`, `bridge-preflight`, `bridge-session-start`, `bridge-inbox-index`, `package-draft-index`, `package-draft-latest-operator` |

## Buttons

| Button | Action | Safety |
|---|---|---|
| Refresh Workflow Status | Runs `scripts\riftreader-workflow-status.cmd --write`. | No input/movement/debugger/Git mutation; exit `2` means a safe blocker. |
| Refresh Decision Packet | Runs `scripts\riftreader-decision-packet.cmd --write --compact-json`. | Writes ignored `.riftreader-local` packet artifacts only; exit `2` means a safe blocker. |
| Decision Packet Schema | Runs `scripts\riftreader-decision-packet.cmd --schema-json`. | Read-only schema contract; no artifact writes, live input, debugger, or Git mutation. |
| Decision Packet Agent Plan | Runs `scripts\riftreader-decision-packet.cmd --agent-plan`. | Read-only parallel-agent work slices plus LLM reminder; exit `2` means a safe blocker. |
| Compact ChatGPT SITREP | Runs `scripts\riftreader-workflow-status.cmd --compact --write`. | Paste-ready for desktop ChatGPT; exit `2` means a safe blocker. |
| Run Live-Test Triage | Runs `scripts\riftreader-live-triage.cmd --write`. | No input/movement/debugger/Git mutation. |
| Package Intake Dry-Run | Lets the operator choose a package and runs intake without `--apply`, printing compact JSON. | No repo target writes; dry-run still writes an ignored package diff. |
| Package Intake Self-Test | Runs `scripts\riftreader-package-intake-selftest.cmd`. | Generates an ignored package and proves dry-run package intake without repo target writes. |
| Bridge Self-Test | Runs `scripts\riftreader-local-artifact-bridge.cmd --self-test --json`. | Exercises bridge reads, guarded inbox HTTP POST, duplicate/malformed handling, and HTTP `package-proposal` to inert draft export in a temp payload and ephemeral loopback server; no persistent server or tunnel. |
| Bridge Preflight | Runs `scripts\riftreader-local-artifact-bridge.cmd --preflight --payload-root artifacts\chatgpt-payloads --json`. | Checks payload readiness, inbox safety flags, and redacted URL hints without starting a persistent server or tunnel; exit `2` means a safe blocker. |
| Bridge Session Start | Runs `scripts\riftreader-local-artifact-bridge.cmd --session-start --payload-root artifacts\chatgpt-payloads --json`. | Prints one redacted Desktop ChatGPT setup packet with preflight, latest payload, latest inbox, manual commands, and next steps; no serving/tunnel. |
| Bridge ChatGPT Handoff | Runs `scripts\riftreader-local-artifact-bridge.cmd --chatgpt-handoff --payload-root artifacts\chatgpt-payloads --json`. | Prints the redacted Desktop ChatGPT starter packet with read order, inbox schema, and safety rules. |
| Bridge Bootstrap Payload | Runs `scripts\riftreader-local-artifact-bridge.cmd --bootstrap-payload --payload-root artifacts\chatgpt-payloads --json`. | Creates a curated starter payload from fixed repo-owned docs; no source edits or Git mutation. |
| Bridge Payload Index | Runs `scripts\riftreader-local-artifact-bridge.cmd --index --payload-root artifacts\chatgpt-payloads --json`. | Reads the curated payload index only; no HTTP serving or tunnel management. |
| Bridge Inbox Index | Runs `scripts\riftreader-local-artifact-bridge.cmd --inbox-index --json`. | Reads guarded Local Inbox v0 metadata under `.riftreader-local`; no apply/execute. |
| Bridge Latest Inbox | Runs `scripts\riftreader-local-artifact-bridge.cmd --inbox-read-latest --json`. | Reads the newest stored proposal or returns a safe empty-inbox blocker; no apply/execute. |
| Bridge Package Draft | Runs `scripts\riftreader-local-artifact-bridge.cmd --inbox-package-draft --json`. | Converts the latest `package-proposal` inbox item into `.riftreader-local\artifact-bridge-package-drafts`; no apply/execute, Git mutation, or repo target writes. |
| Draft Index | Runs `scripts\riftreader-package-draft-review.cmd --index --json`. | Lists ignored package drafts and separates operator proposals from self-test drafts; no package intake, apply, or repo target writes. |
| Latest Draft Summary | Runs `scripts\riftreader-package-draft-review.cmd --latest --json`. | Prints the newest package draft summary pointer; no intake/apply/execute. |
| Latest Operator Draft | Runs `scripts\riftreader-package-draft-review.cmd --latest-operator --json`. | Prints the newest non-self-test operator draft summary; blocks with `PACKAGE_DRAFT_OPERATOR_EMPTY` if only self-test drafts exist. |
| Dry-Run Latest Draft | Runs `scripts\riftreader-package-draft-review.cmd --dry-run-latest --json`. | Explicitly invokes package intake dry-run for the newest draft without `--apply`; safe blockers return exit `2`. |
| Dry-Run Operator Draft | Runs `scripts\riftreader-package-draft-review.cmd --dry-run-latest-operator --json`. | Explicitly invokes package intake dry-run for the newest operator draft without `--apply`; safe blockers return exit `2`. |
| Draft Loop Self-Test | Runs `scripts\riftreader-package-draft-review.cmd --self-test --json`. | Stores a synthetic inbox proposal, exports an inert package draft, and dry-runs intake; writes ignored `.riftreader-local` artifacts only. |
| Proposal Loop Checks | Runs `scripts\riftreader-operator-lite.cmd --run-all bridge-proposal-loop-checks --json` internally. | Proves HTTP proposal-to-draft plus local draft-to-dry-run paths; no persistent serving, tunnel, apply, or Git mutation. |
| Trial Readiness Gate | Runs `scripts\riftreader-operator-lite.cmd --run-all bridge-trial-readiness --json` internally. | Proves bridge startup readiness and checks for a real operator draft without exporting drafts, dry-running intake, serving, tunneling, applying, or mutating Git; exit `2` means a safe missing-operator-draft/preflight blocker. |
| MCP Trial Readiness | Runs `scripts\riftreader-chatgpt-mcp.cmd --trial-readiness --json`. | Proves the narrow ChatGPT MCP adapter locally: self-test, SDK metadata validation, loopback transport smoke with synthetic `submit_package_proposal`, and optional tunnel-tool availability checks; no public tunnel, ChatGPT registration, persistent serve, apply, Git mutation, live input, CE, or x64dbg. |
| MCP Mission Control | Runs `scripts\riftreader-mcp-mission-control.cmd --json`. | Consolidated MCP status, latest proof artifacts, dirty state, ranked next actions, paste-safe commands, and optional Markdown summary/checklist modes; no tunnel or Git mutation. |
| Browser/Computer Readiness | Runs `scripts\riftreader-desktop-control-readiness.cmd --json`. | Read-only readiness report for no-write Browser Use dashboard smoke and Computer Use native-pipe/list-apps smoke; returns exit `2` until external smokes are confirmed. The companion `--repair-guide` mode is guide-only and prints the supported native-pipe recovery checklist plus safe observation-record commands. |
| Latest MCP Artifacts | Runs `scripts\riftreader-mcp-artifacts.cmd --latest --json`. | Read-only latest readiness/smoke/trial/proof-input-template/inbox/draft/dry-run/proof lookup with timeline/kind/open-latest CLI support. |
| ChatGPT Trial Proof Template | Runs `scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --json`. | Writes an ignored, operator-fillable actual-client proof input template and prints the record command. |
| Check Latest ChatGPT Proof Input | Runs `scripts\riftreader-chatgpt-trial-recorder.cmd --check-latest-template --json`. | Validates the latest filled proof input template read-only before recording proof artifacts. |
| Safe Commit Plan | Runs `scripts\riftreader-safe-commit-packager.cmd --plan --json`. | Builds an explicit-path staging/commit checklist only; Markdown export is available; never stages, commits, or pushes. |
| Workflow Router | Runs `scripts\riftreader-workflow-router.cmd --mcp --json`. | Recommends the next safest MCP lane action from local state only. |
| Open Bridge Docs | Opens `docs\workflow\local-artifact-bridge.md`. | Local view only. |
| Copy Bridge Start Command | Copies the manual `--serve --token auto --max-inbox-mb 1` command. | Does not run the command; the operator remains in control of local serving. |
| Copy Inbox JSON Template | Copies a ready-to-fill Local Inbox v0 JSON message template. | Template is inert; it does not post, apply, execute, or mutate the repo. |
| Copy Package Proposal Template | Copies a ready-to-fill `package-proposal` JSON template with one UTF-8 text file and one safe check example. | Template is inert; package draft export still requires a separate inbox POST and explicit local review. |
| Copy Redacted Bridge Instructions | Copies placeholder `<token>` bridge/tunnel/inbox instructions. | Does not copy a real token; tunnel startup remains manual. |
| Copy ChatGPT Bridge Prompt | Copies a placeholder prompt that tells Desktop ChatGPT to start at `/<token>/`, `/health`, `/payloads/latest/readme.md`, and `/payloads/latest/chunks.json`; it mentions `/inbox/messages` only as operator-approved proposal intake. | Does not copy a real token; only lists safe bridge endpoints. |
| Git Status | Runs `git --no-pager status --short --branch`. | Read-only Git. |
| Open Latest Report | Opens latest ignored `.riftreader-local` report. | Local view only. |
| Target-Control / Visual Gate / ProofOnly / Movement / Bridge Serve-Tunnel | Disabled in v0. | Prevents live action drift and avoids accidental local-server exposure. |

## Safety contract

Operator Lite v0 writes only through the underlying safe helpers; the Decision Packet Schema and Decision Packet Agent Plan commands are read-only and write no artifacts:

- `.riftreader-local\workflow-status\...`
- `.riftreader-local\live-test-triage\...`
- `.riftreader-local\package-intake\...`
- `.riftreader-local\package-intake-selftest\...`
- `.riftreader-local\artifact-bridge-inbox\...` when an external client uses the bridge inbox while the operator is manually serving it.
- `.riftreader-local\artifact-bridge-package-drafts\...` when the operator exports an approved package-proposal into an inert local draft.
- `.riftreader-local\package-intake\...` when the operator explicitly dry-runs the newest package draft.

The bridge self-test uses a temporary payload and ephemeral loopback server; it does not start the persistent `--serve` mode. It now also POSTs a synthetic HTTP `package-proposal` and exports that proposal into an inert draft without invoking package intake. The proposal-loop checks group runs that bridge self-test plus the local draft-loop self-test. The trial-readiness gate runs self-test, preflight, session-start, inbox index, package-draft index, and an operator-draft availability check; it does not export drafts or dry-run intake, and it safely blocks when no real operator-proposal draft exists. The MCP trial-readiness command checks the narrow ChatGPT MCP adapter with self-test, SDK metadata validation, and temporary loopback transport smoke including one synthetic `submit_package_proposal`; it writes ignored `.riftreader-local` summaries/inbox entries and does not start a public tunnel or register ChatGPT. The MCP helper-suite buttons are local dashboards, Browser/Computer Use readiness, artifact lookup, proof-template, commit-plan, and next-action selectors; only the trial recorder's record mode writes ignored actual-client proof packets, and Operator Lite exposes template mode only. The desktop-control readiness helper can also write an ignored observation artifact with `--record-observation`; that writer records only declared Browser/Computer smoke results, enforces a 24-hour freshness budget, and never automates Browser Use, Computer Use, desktop UI, RIFT input, tunnels, package apply, or Git mutation. The `--repair-guide` mode is also guide-only: it prints the supported Computer Use native-pipe recovery checklist, forbidden fallbacks, and record-observation commands without touching browser/desktop UI or repo state. The decision-packet schema command is a read-only contract print and writes no artifacts. The bounded real ChatGPT MCP registration window is intentionally a direct `riftreader-chatgpt-mcp.cmd --chatgpt-trial-session` action rather than an Operator Lite button, because it starts `cloudflared` and a public tunnel. The bridge preflight/index/session-start/handoff actions read only registered payload metadata from `artifacts\chatgpt-payloads` and generate redacted operator/ChatGPT guidance. The bridge bootstrap action creates a curated payload under `artifacts\chatgpt-payloads` from fixed repo-owned docs only. The bridge inbox index/latest actions read ignored Local Inbox v0 metadata/messages only. The inbox/package-proposal template copy actions write only to the clipboard. The bridge package-draft action writes an ignored package draft only. The draft-index and latest-draft summary actions read those ignored drafts only, separate operator proposals from self-test drafts, and block if package or manifest pointers escape `.riftreader-local\artifact-bridge-package-drafts`. The operator-only summary/dry-run actions ignore self-test drafts and block if no operator-proposal draft exists. The latest-draft dry-run action invokes package intake without `--apply`. The draft-loop self-test writes a synthetic ignored inbox proposal/draft and package-intake dry-run summary; applying, executing apply checks, staging, committing, and pushing remain separate explicit actions.

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
| MCP & Proof | Blue MCP proof buttons, amber Browser/Computer readiness, and purple artifact lookup. | Keeps ChatGPT proof, dashboard/browser smoke, and desktop automation readiness visible without adding control endpoints. |
| Packages, Reports & Git | Green package buttons and neutral report/Git buttons. | Makes dry-run package actions distinct from read-only views. |
| Local Artifact Bridge | Purple command/session/handoff/index/package-draft rows, amber bootstrap button, neutral docs/template/copy rows, and a blue status strip. | Prevents bridge button overflow while keeping checks, session-start, handoff, payload bootstrap, indexes, inbox review, package draft export, draft index, newest-draft summary, operator-only summary/dry-run, explicit draft dry-run, draft-loop self-test, proposal-loop checks, trial-readiness gate, docs, templates, and prompt-copy actions visually separate. |
| Locked Live Controls | Red locked badges instead of normal action buttons. | Shows unsafe live actions are intentionally unavailable. |

The window also includes a persistent safe-mode status bar and a dark output log for better contrast while preserving the same no-input/no-debugger/no-Git-mutation safety model.
