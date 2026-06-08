# RiftReader ChatGPT MCP adapter

Status: MVP plus gated apply tool, narrow tool-only adapter.

Final-product readiness contract: `docs\workflow\riftreader-chatgpt-mcp-final-readiness.md`.

## Purpose

`riftreader_chatgpt_mcp` is a narrow MCP server for Desktop ChatGPT Developer
Mode. It exposes only allowlisted RiftReader workflow surfaces and deliberately
does **not** proxy broad local MCPs such as `rift_game` or `windows-mcp`.

The adapter is designed for this safe loop:

1. ChatGPT reads repo status and latest handoff context.
2. ChatGPT fetches the package-proposal template.
3. ChatGPT submits an operator-approved `package-proposal`.
4. The proposal is stored only under `.riftreader-local`.
5. ChatGPT can create an inert package draft from a specific inbox proposal
   under `.riftreader-local` only.
6. Operator/Codex reviews inbox and inert package drafts before any dry-run.
7. ChatGPT can dry-run the latest operator package draft and receive bounded
   package diff evidence.
8. ChatGPT can apply only after the local operator supplies the Stage 18/19
   approval token bound to the reviewed dry-run.
9. ChatGPT can request a read-only workflow control plan with safe next actions,
   explicit staging/check commands, bidirectional data-transfer steps, and
   gated boundaries.

## Tool surface

| Tool | Access | Behavior |
|---|---|---|
| `health` | Read-only | Returns server status, redacted repo identity, version, tool manifest, and safety flags. |
| `get_repo_status` | Read-only | Returns compact repo/workflow truth using existing status helper logic. |
| `get_latest_handoff` | Read-only | Reads only the newest Markdown file under `docs/handoffs`. |
| `get_workflow_control_summary` | Read-only | Returns the smallest safe workflow-control summary for MCP clients that time out on the full plan. |
| `get_package_proposal_template` | Read-only | Returns the existing Local Artifact Bridge package proposal template/schema. |
| `submit_package_proposal` | Guarded write | Stores a valid `package-proposal` only under `.riftreader-local\artifact-bridge-inbox`. |
| `list_inbox` | Read-only | Lists Local Artifact Bridge inbox metadata only. |
| `create_package_draft_from_inbox` | Guarded local write | Converts an explicit validated `inboxId` into an inert package draft under `.riftreader-local\artifact-bridge-package-drafts`; never applies files or executes checks. |
| `review_latest_package_draft` | Read-only | Returns latest inert package draft review status; defaults to non-self-test operator drafts. |
| `dry_run_latest_package_draft` | Explicit action | Runs package-draft intake dry-run only; never passes `--apply`; returns a bounded `dryRun.diffPreview` from `.riftreader-local\package-intake\*\package.diff` when available. |
| `apply_latest_package_draft` | Approval-token gated action | Applies the latest operator package draft only through package intake after matching dry-run summary, diff SHA-256, and local approval token; never stages, commits, pushes, runs shell, sends RIFT input, writes providers, or touches CE/x64dbg. |
| `get_workflow_control_plan` | Read-only | Returns Mission Control status, safe commit-plan guidance, bidirectional data-flow steps, and gated action boundaries without executing them. |

Each tool has an explicit allowlist of accepted argument keys. Unknown wrapper
arguments are blocked fail-closed instead of being silently ignored, and the
`health` manifest reports each tool's `allowedArgumentKeys` for ChatGPT
Web/Desktop client debugging.

Each tool also carries an `outputSchema` contract for returned
`structuredContent`. The local manifest surfaces the minimum common result
shape, and SDK/transport verification blocks missing or non-object output
schemas before actual ChatGPT proof runs.

At runtime, the adapter validates every handler result before returning it. A
malformed result that omits the common structuredContent fields (`schemaVersion`,
`kind`, `status`, or boolean `ok`) is converted into a fail-closed
`TOOL_RESULT_CONTRACT_INVALID` response and recorded in sanitized audit metadata.

## Phase 0 domain read-only proof profile

The canonical adapter remains `scripts\riftreader-chatgpt-mcp.cmd`. For the
first public domain proof, run the same adapter with the read-only profile
instead of creating a second MCP server:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\riftreader-chatgpt-mcp.cmd --serve --tool-profile public-read-only --host 127.0.0.1 --port 8770 --transport streamable-http --allowed-host mcp.360madden.com --allowed-origin https://chatgpt.com
```

Phase 0 exposes only:

- `health`
- `get_repo_status`
- `get_latest_handoff`
- `get_workflow_control_summary`
- `get_workflow_control_plan`

The default `--tool-profile full` path still exposes the existing 12-tool final
proof surface and is not deleted or downgraded.

For the domain route, use ChatGPT Web/Desktop Developer Mode, not ChatGPT Codex:

| Field | Value |
|---|---|
| Server URL | `https://mcp.360madden.com/mcp` |
| Authentication | `No Authentication` |
| Expected app name | `rift-mcp` |
| Local backend | `http://127.0.0.1:8770/mcp` |

Write a Phase 0 proof template with:

```cmd
scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --proof-mode domain-read-only --json
```

Record it only after actual ChatGPT Web/Desktop observations confirm the app,
Server URL, No Authentication, read-only tool list, successful `health`, successful
`get_repo_status`, and either `get_latest_handoff` or
`get_workflow_control_summary`.

## Domain diagnostics and local dashboard

Use the repo-native diagnostic helper instead of downloaded one-file runners:

```cmd
scripts\riftreader-mcp-domain-diagnostics.cmd --public-mcp-host mcp.360madden.com --json
```

The helper writes JSON/Markdown summaries under
`.riftreader-local\riftreader-chatgpt-mcp\domain-diagnostics`, checks the local
backend, DNS, public TCP 443 reachability, and performs a real MCP `initialize`
smoke with protocol/header `2025-06-18`. HTTP `502`, `403`, `404`, `421`, and
non-MCP JSON are failures even if the HTTP client exits normally. It does **not**
write legacy Caddyfile text by default; `--write-legacy-caddyfile` is an
opt-in compatibility artifact only. The canonical public route is the
persistent Cloudflare named Tunnel `riftreader-mcp-360madden`.

Start the status-only localhost dashboard with:

```cmd
scripts\riftreader-mcp-dashboard.cmd
```

Open `http://127.0.0.1:8788/`. The dashboard is localhost-only, auto-refreshes,
and has no start/stop, shell, Git, RIFT input, CE, x64dbg, arbitrary filesystem,
or public control endpoint. It also displays the plan-only Desktop Queue
Contract from `scripts\riftreader-desktop-control-queue-contract.cmd --json`:
the contract shows Browser/Computer readiness, required future executor gates,
forbidden action families, and `execution.status=disabled`. This is visibility
only; it does not add a queue writer, executor, ChatGPT MCP tool, Browser Use
automation, Computer Use automation, desktop input, or game-control endpoint.

## Hard boundaries

- No arbitrary filesystem read tool.
- No arbitrary filesystem write tool.
- No shell execution endpoint.
- No Git stage/commit/push/reset/clean endpoint.
- No RIFT input, movement, target control, CE, or x64dbg endpoint.
- No automatic persistent bridge/tunnel startup.
- No proxying `rift_game`, `windows-mcp`, or other broad MCPs.
- All ChatGPT-originated writes stay under `.riftreader-local`.
- Server audit events are sanitized and written under
  `.riftreader-local\riftreader-chatgpt-mcp\audit`.
- ChatGPT-facing tool output redacts the absolute local repository path. Public
  health reports the repo as `.` plus a repo name, and nested draft/dry-run
  helper fields are normalized before audit/return.

## Non-Codex runtime invariant and existing launcher inventory

This MCP exists so ChatGPT Web/Desktop can work with the local RiftReader repo
when Codex is unavailable, quota-blocked, closed, or intentionally not part of
the workflow. Do **not** treat a Codex-launched process as final acceptance proof
for this lane.

Before adding any new launcher, inspect and reuse the existing repo-owned
scripts:

| Existing script | Current role | Use / avoid rule |
|---|---|---|
| `scripts\riftreader-chatgpt-mcp.cmd` | Thin launcher for the narrow ChatGPT Developer Mode MCP adapter. | Use this for ChatGPT MCP self-tests, the active Cloudflare named Tunnel plan, and local `--serve`. Do not recreate it under a new name. |
| `scripts\riftreader-bridge-tunnel-session.cmd` | Local Artifact Bridge plus historical Cloudflare tunnel helper. | Related artifact bridge workflow only; do not confuse it with the narrow ChatGPT MCP adapter or use it as a ChatGPT MCP backup. |
| `scripts\riftreader-mcp-server.cmd` | Separate RiftReader stdio MCP server helper. | Support/low-level MCP lane; do not substitute it for the ChatGPT Developer Mode adapter without a deliberate design change. |
| `scripts\riftreader-mcp-client.cmd` | Client config/smoke helper. | Support helper only; not the user-facing ChatGPT app runtime. |

Acceptance proof for "use ChatGPT without Codex" requires the runtime to be
started by the operator outside Codex, from a normal CMD/PowerShell window or an
equivalent user-owned process. The operator should be able to see or identify
the expected local processes (`python.exe` for the MCP adapter and
`cloudflared.exe`/the Cloudflared Windows service for the persistent named
Tunnel) without relying on a Codex terminal or Codex quota.

Wrong proof:

```cmd
REM DO NOT count this as final non-Codex proof when launched only inside Codex.
scripts\riftreader-chatgpt-mcp.cmd --chatgpt-trial-session --json
```

Correct non-Codex public-host/domain proof shape:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host mcp.360madden.com --json
scripts\riftreader-chatgpt-mcp.cmd --serve --tool-profile public-read-only --host 127.0.0.1 --port 8770 --transport streamable-http --allowed-host mcp.360madden.com --allowed-origin https://chatgpt.com
```

Keep that operator-owned console open while ChatGPT connects. A saved ChatGPT app
entry is only configuration; it does not start the local repo MCP server, does
not start Cloudflared, does not configure Cloudflare, and does not update the
Server URL if the public host changes.

Plan-only helper for this invariant:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\riftreader-chatgpt-mcp.cmd --operator-launch-plan --json
```

`--operator-launch-plan` does not start a server, start a tunnel, register
ChatGPT, mutate Git, send RIFT input, or attach CE/x64dbg. It prints the existing
operator-owned commands, the expected visible processes, and the "do not use"
list so future sessions do not recreate the launcher or confuse the artifact
bridge tunnel with the narrow ChatGPT MCP adapter.

## Future capability roadmap

`get_workflow_control_summary` is the transport-safe first workflow-control
call; `get_workflow_control_plan` advertises the intended higher-power
capability ladder while keeping endpoints gated until their proof and approval
gates exist. This lets ChatGPT Web/Desktop reason about next steps without
silently gaining Git, shell, live RIFT, CE, or x64dbg powers.

The full current-to-finished-product plan is maintained in
`docs\workflow\riftreader-chatgpt-mcp-50-stage-plan.md` and is summarized in
the `fullProductStagePlan` field returned by `get_workflow_control_plan`.
The first future repo-source-mutation contract is documented in
`docs\workflow\riftreader-chatgpt-mcp-apply-tool-design.md` and is surfaced as
`futureToolContracts.apply_latest_package_draft` with `status=exposed-gated`.
Its
Stage 18 local-only preflight helper is
`tools\riftreader_workflow\package_draft_review.py --apply-preflight-latest-operator`,
which validates draft identity, dry-run freshness, and diff hash binding without
passing `--apply`.
Stage 19 adds `--apply-latest-operator` as a local-only bridge that requires the
preflight approval token before it can pass `--apply` to package intake. Stage
20 wraps that bridge as `apply_latest_package_draft`; the MCP tool still
requires the local approval token and performs no Git, provider, RIFT, CE, or
x64dbg action.

| Future capability | Current status | Minimum gate before exposure |
|---|---|---|
| Apply latest package draft to repo | Stage 20 exposed-gated | Explicit operator approval token plus fresh reviewed dry-run, dry-run diff hash binding, and clean preflight. |
| Commit reviewed local slice | Planned; not exposed | Explicit operator approval plus safe commit plan and passing validation. |
| Push current branch | Planned; not exposed | Explicit current-turn approval, clean worktree, visible branch/upstream state, no force push. |
| Run bounded repo command | Planned; not exposed | Explicit approval plus repo-owned command allowlist, argument-array invocation, timeout/output caps. |
| Live RIFT control | Planned; not exposed | Explicit live approval plus exact current target identity and bounded action plan; plan-only gates are drafted in `docs\workflow\riftreader-chatgpt-mcp-live-control-design.md`. |
| Debugger/CE assist | Planned; not exposed | Explicit debugger approval with crash-risk statement and candidate-only proof boundaries. |

Default development order: apply-package dry-run-to-apply bridge first, local
commit second, push third, bounded shell fourth, live RIFT control fifth, and
debugger/CE assist last.

## Local checks

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --tool-manifest --json
.\scripts\riftreader-chatgpt-mcp.cmd --self-test --json
```

The self-test runs local handlers without ChatGPT and without a public tunnel.
It may create ignored `.riftreader-local` inbox, draft, package-intake, and audit
artifacts. It must not apply files, mutate Git, start a server, start a tunnel,
send RIFT input, or attach CE/x64dbg.

If the Python MCP SDK is installed, validate actual FastMCP import, tool
registration, descriptions, and annotations without starting a server:

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --validate-sdk --json
```

After SDK validation passes, run a bounded loopback transport smoke test. This
starts a temporary `127.0.0.1` server on an ephemeral port, calls `list_tools`
and `health` through the MCP streamable HTTP client, writes a local summary
under `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke`, then stops
the server. It does **not** start a tunnel or register anything in ChatGPT.

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --transport-smoke --json
```

To prove the guarded write-shaped MCP tools over the same real SDK/client
transport before using ChatGPT, run the proposal transport smoke. It submits a
synthetic `package-proposal` through `submit_package_proposal`, confirms
`list_inbox` can see the result, creates an inert package draft with
`create_package_draft_from_inbox`, reviews it with
`review_latest_package_draft`, dry-runs it with `dry_run_latest_package_draft`,
verifies the bounded `dryRun.diffPreview`, calls `apply_latest_package_draft`
without an approval token and requires the fail-closed `APPLY_APPROVAL_MISSING`
denial with `applied=false`, writes only ignored
`.riftreader-local` inbox/draft/package-intake/audit/smoke artifacts, and stops
the temporary loopback server.

`dry_run_latest_package_draft` also compacts the package-intake result for
ChatGPT review. Its optional `dryRun.diffPreview` is intentionally not an
arbitrary file read: it resolves only the `artifacts.diff` path from the compact
package-intake summary, requires the resolved file to be
`.riftreader-local\package-intake\*\package.diff`, caps returned text at 16 KiB,
sets `truncated=true` when clipped, and fails closed without echoing arbitrary
absolute paths when the artifact path is unsafe.

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --proposal-transport-smoke --json
```

For a single compact local go/no-go gate before any public-IP ChatGPT
registration, run trial readiness. This runs the handler self-test, SDK
metadata validation, loopback transport smoke including a synthetic
`submit_package_proposal`, `list_inbox`, inert package-draft creation, draft
review, dry-run, bounded `dryRun.diffPreview`, fail-closed
`apply_latest_package_draft` without approval, and optional `curl`
readiness checks. It
writes a compact summary under
`.riftreader-local\riftreader-chatgpt-mcp\transport-smoke`.

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --trial-readiness --json
```

The same gate is exposed through Operator Lite:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json
```

This may create ignored `.riftreader-local` self-test/audit/smoke/inbox
artifacts and may start a temporary loopback-only server for transport
validation, including one synthetic package proposal. It does not start a
public tunnel, reverse proxy, register ChatGPT, serve persistently, apply package content,
mutate Git, send RIFT input, or attach CE/x64dbg.

Manual public-host/domain command plan:

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host mcp.360madden.com --json
```

This prints the repo-specific public-host/domain Server URL plan for the local
RiftReader MCP adapter. The flag name is retained for compatibility, but the
current plan is the persistent Cloudflare named Tunnel route
`riftreader-mcp-360madden -> http://127.0.0.1:8770`. It does not start the MCP
server, start Cloudflared, edit Cloudflare, register ChatGPT, mutate Git, send
RIFT input, or expose broad local tools. The JSON includes both argument arrays
and copyable command-line strings, plus the exact first ChatGPT smoke order:
`health`, `get_repo_status`, then `get_latest_handoff`.

Retired transport paths:

| Retired path | Rule |
|---|---|
| OpenAI Secure MCP Tunnel / `tunnel-client` | Do not use as primary or backup for this lane. |
| Cloudflare quick tunnel / `trycloudflare.com` | Do not use as primary or backup for this lane. |
| Caddy/router/direct public-IP route | Deprecated legacy path; do not recreate it for this lane. |


## MCP Workflow Suite helpers

The local helper suite gives one place to find the latest MCP proof artifacts,
choose the next safe action, record actual ChatGPT-side proof facts, and prepare
an explicit-path commit checklist. Defaults are local-first and read-only except
for ignored `.riftreader-local` proof records created by the trial recorder.

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-mcp-mission-control.cmd --json
.\scripts\riftreader-mcp-artifacts.cmd --latest --json
.\scripts\riftreader-workflow-router.cmd --mcp --json
.\scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --json
.\scripts\riftreader-safe-commit-packager.cmd --plan --json
```

| Helper | Command | Default behavior |
|---|---|---|
| MCP Mission Control | `scripts\riftreader-mcp-mission-control.cmd --json` | Shows readiness, latest artifacts, Git dirty summary, ranked next actions, paste-safe commands, `--summary-md`, `--checklist-md`, and `--proof-run-packet-md`. |
| Manual Public-Host Plan | `scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host mcp.360madden.com --json` | Writes an ignored local plan artifact and prints the active Cloudflare named Tunnel Server URL, loopback MCP serve command, tunnel/Cloudflare checklist, retired-path warnings, and first ChatGPT smoke order. |
| Final Readiness Gate | `scripts\riftreader-mcp-final.cmd --status --compact-json` | Authoritative final-product gate covering Phase 2 proof/CI/freshness, clean tree, upstream sync, retired tunnel dependency state, environment preflight, tool-surface safety, and public-session state. |
| Proof Artifact Browser | `scripts\riftreader-mcp-artifacts.cmd --latest --json` | Lists latest readiness/smoke/trial/proof-input-template/inbox/draft/dry-run/proof artifacts; `--timeline`, `--kind <kind>`, and read-only `--open-latest` are supported. |
| Workflow Router | `scripts\riftreader-workflow-router.cmd --mcp --json` | Emits one recommended next action plus ranked alternatives from local artifacts and dirty state. |
| ChatGPT Trial Recorder | `scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --json` / `--check-latest-template --json` / `--check-input --input proof.json --json` / `--template --json` / `--record --input proof.json --json` / `--self-test --json` | Writes an ignored fillable proof input template, validates the latest or explicitly selected filled proof input read-only before recording, records operator-supplied actual ChatGPT facts under `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof`, and still supports stdout-only template printing; current proof should use `connectionMode=cloudflare-named-tunnel` and fails closed on unknown connection mode, retired tunnel-host misuse, unfilled URL placeholders, tool count and exact tool-name set, per-tool output-schema confirmation/count/name set, repo-root redaction, inbox, package-draft creation, read-only draft review, dry-run success, bounded `dryRun.diffPreview` proof gaps, and apply-without-approval denial proof. |
| Safe Commit Packager | `scripts\riftreader-safe-commit-packager.cmd --plan --json` | Generates explicit `git add -- <path>` checklist and commit-message draft only; `--markdown` prints a review packet; it never stages, commits, or pushes. |
| Phase 1 Completion Gate | `scripts\riftreader-mcp-phase1.cmd --status --json` | Evaluates repo-side readiness plus the latest actual ChatGPT client proof revalidated against current proof rules, and reports whether Phase 1 is complete or externally blocked. |

The shared state layer marks self-test inbox/draft artifacts, adds artifact age
fields, indexes legacy `manual-public-ip-plan` artifacts whose current active path is Cloudflare named Tunnel, warns on stale proof budgets,
and labels stopped or aged-out historical ephemeral public URLs as
expected-expired. The final gate also checks loopback port allocation, default
serve-port availability, retired tunnel dependency state, and whether
`.riftreader-local` remains Git-ignored for local MCP artifacts. Mission Control
`--manual-public-ip-plan` prints the active Server URL plan command without
starting the MCP server, starting Cloudflared, or editing Cloudflare. Secure MCP
Tunnel, trycloudflare quick tunnel, and Caddy/router command surfaces return
retired/deprecated status and are not backups. Only `--run-readiness` and
`--run-proposal-smoke` execute local-only validation. No helper starts public
exposure by default. The Phase 1 gate
intentionally reports `blocked` until an
actual ChatGPT Developer Mode proof packet is recorded and revalidates against
the current `actual-client-proof` schema/rules; stale artifacts that merely have
historical `status=passed` no longer complete the gate.

## Final-product Mission Control flow

Phase 5 makes Mission Control the default operator entrypoint for the MCP final
product lane. Use it before public exposure:

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-mcp-mission-control.cmd --summary-md
.\scripts\riftreader-mcp-mission-control.cmd --checklist-md
.\scripts\riftreader-mcp-mission-control.cmd --proof-run-packet-md
.\scripts\riftreader-mcp-final.cmd --status --compact-json
```

Mission Control now emits:

| Field / mode | Purpose |
|---|---|
| `finalStatus` | Compact final gate result with CI, proof, dependency, environment, tool-surface, and public-session status. |
| `finalProductProgress` | Phase 1-8 progress table with completed phases, next phase, and explicit public-trial boundary state. |
| `operatorNextAction` | One dashboard-selected next operator action from final-gate truth. |
| `recommendedNextAction` / `rankedActions` | Final-gate-aligned operator routing; raw artifact presence cannot mark the dashboard ready when proof replay fails current rules. |
| `--summary-md` | Human-readable progress and latest-artifact summary suitable for handoff context. |
| `--checklist-md` | Paste-safe proof checklist covering final gate, optional local refreshes, explicit public trial, package review, proof recording, and final gate rerun. |
| `--proof-run-packet-md` | Current ChatGPT Web/Desktop proof packet with the live Cloudflare Server URL, No Authentication mode, backend PID when visible, latest proof-template path, expected 12-tool list, safe ChatGPT call sequence, and check/record commands. |
| `--trial-command --json` | Prints the bounded public-trial command without running it. |

Mission Control remains safe by default: it does not start a public tunnel,
register ChatGPT, mutate Git, apply packages, send RIFT input, attach CE/x64dbg,
or write provider repos. Only `--run-readiness` and `--run-proposal-smoke`
execute local-only validation helpers; the public trial command is display-only
unless the operator explicitly runs the printed command.

Mission Control status, blockers, recommended action, and ranked actions should
prefer final-readiness proof replay over raw artifact presence. If the latest
actual-client proof artifact has historical `status=passed` but fails the
current Secure Tunnel/diff-preview proof rules, Mission Control must report
`blocked` and route to `record-actual-client-proof`.

## Running the MCP server locally

The server path uses the official Python MCP SDK when `--serve` is requested.
Install the SDK before serving if it is not already available:

RUN THIS:

```cmd
python -m pip install "mcp[cli]"
```

For an isolated repo-local validation install that does not modify the global
Python environment, use an ignored target directory. The MCP validation helpers
auto-detect `.riftreader-local\mcp-sdk-validation` when present:

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
python -m pip install --target .riftreader-local\mcp-sdk-validation "mcp[cli]"
.\scripts\riftreader-chatgpt-mcp.cmd --validate-sdk --json
.\scripts\riftreader-chatgpt-mcp.cmd --transport-smoke --json
```

Then start the local server manually:

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --serve --host 127.0.0.1 --port 8770 --transport streamable-http
```

Local MCP endpoint:

```text
http://127.0.0.1:8770/mcp
```

## ChatGPT Web/Desktop route: public-host/domain Server URL

ChatGPT Developer Mode needs an HTTPS-reachable MCP endpoint. The current
RiftReader path is now **public-host/domain Server URL through the persistent
Cloudflare named Tunnel**:
`https://mcp.360madden.com/mcp`, not OpenAI Secure MCP Tunnel, not a
`trycloudflare.com` quick tunnel, and not the deprecated Caddy/router route. The
operator starts the local MCP server outside Codex, keeps the Cloudflared
Windows service healthy, ensures the Cloudflare published application route maps
`mcp.360madden.com` to `http://127.0.0.1:8770`, then uses the domain Server URL
in the ChatGPT custom MCP app.

Primary local plan command:

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host mcp.360madden.com --json
```

If you only need to decide which existing non-Codex command to run, use the
plan-only launcher inventory first:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --operator-launch-plan --json
```

The plan prints the local loopback MCP server command. The adapter remains bound
to `127.0.0.1`; expose it through the persistent Cloudflare named Tunnel instead
of binding the adapter directly to the LAN/WAN. The Cloudflare published
application must forward `mcp.360madden.com` to `http://127.0.0.1:8770` so
`/mcp` reaches `http://127.0.0.1:8770/mcp`.

Manual network checklist:

1. Start the local MCP server outside Codex.
2. Confirm the Cloudflared Windows service for named tunnel `riftreader-mcp-360madden` is running.
3. Confirm the Cloudflare Tunnel public hostname `mcp.360madden.com` routes to `http://127.0.0.1:8770`.
4. Confirm Cloudflare DNS for `mcp.360madden.com` points to the tunnel hostname and remains proxied.
5. Confirm the scoped Cloudflare Configuration Rule `Disable BIC for RiftReader MCP endpoint` disables Browser Integrity Check for `/mcp*`.
6. Run `scripts\riftreader-mcp-domain-diagnostics.cmd --public-mcp-host mcp.360madden.com --json` and require HTTP 200 MCP initialize.
7. In ChatGPT, configure the custom MCP app Server URL as `https://mcp.360madden.com/mcp` and Authentication as **No Authentication**.
8. If the public hostname/route changes, manually edit the ChatGPT app Server URL.

Current active proof packets must record the selected connection path explicitly:

| Field | Primary value | Rule |
|---|---|---|
| `connectionMode` | `cloudflare-named-tunnel` (legacy recorder packets may still say `manual-public-ip`) | Required for the active ChatGPT Web/Desktop proof lane. |
| `publicMcpUrl` | `https://mcp.360madden.com/mcp` | Must be HTTPS and currently reachable from ChatGPT/OpenAI. |
| `toolNames` | Canonical 12 allowlisted tool names | Must match the expected tool-name set exactly; duplicate, missing, or unexpected names block proof replay. |
| `toolOutputSchemasPresent` | `true` | Confirms the ChatGPT-observed tool descriptors include per-tool output-schema contracts for returned `structuredContent`. |
| `toolOutputSchemaCount` | `12` | Must match the allowlisted tool count so a partial schema registration cannot pass as final proof. |
| `toolOutputSchemaToolNames` | Canonical 12 allowlisted tool names | Must match the same expected tool-name set exactly, proving every allowlisted tool has an observed output-schema contract. |

Retired paths are not backups:

| Retired path | Rule |
|---|---|
| OpenAI Secure MCP Tunnel / `tunnel-client` | Do not use for this lane unless a future explicit policy reverses retirement. |
| Cloudflare quick tunnels / `trycloudflare.com` | Do not use for this lane unless a future explicit policy reverses retirement. |
| Caddy/router/direct public-IP route | Deprecated legacy path; do not recreate it for this lane. |
| New tunnel wrapper scripts | Do not create duplicate wrappers; do not fork the workflow into another near-duplicate script. Extend the existing adapter only if policy changes. |

For public Server URL mode, the public Host header must still be allowlisted on
the MCP server. Do not pass a full URL to `--allowed-host`; pass only the exact
Host header value, such as `mcp.360madden.com`. Pass only an
exact origin to `--allowed-origin`, such as `https://chatgpt.com`; do not include
a path, query, fragment, credentials, or wildcard.

## Registering in ChatGPT Developer Mode

In ChatGPT web:

1. Enable Developer Mode under Settings -> Apps -> Advanced settings.
2. Open Apps/Connectors settings.
3. Create an app/connector using **Server URL** and
   `https://mcp.360madden.com/mcp`.
4. Confirm the tool list contains only the 12 allowlisted RiftReader tools.
5. In the conversation, explicitly select Developer Mode and this app.

Suggested first prompt:

```text
Use only the RiftReader ChatGPT MCP app. First call health, then get_repo_status,
then get_latest_handoff. Do not call write/action tools unless I explicitly ask
in this turn.
```

## Notes from current OpenAI/MCP docs

- ChatGPT Developer Mode creates apps from remote MCP servers and supports SSE
  and streaming HTTP.
- ChatGPT Developer Mode supports OAuth, No Authentication, and Mixed
  Authentication. The current RiftReader Cloudflare named Tunnel lane uses No
  Authentication by operator choice.
- ChatGPT Developer Mode supports MCP tools, including read and write tools, but
  write actions require careful review; read-only detection respects
  `readOnlyHint`.
- ChatGPT local development needs an HTTPS-reachable MCP endpoint. The active
  RiftReader route is the public-host/domain Server URL
  `https://mcp.360madden.com/mcp`.
- OpenAI Secure MCP Tunnel and Cloudflare quick tunnels are retired for this
  lane and are not backup paths.
- ChatGPT connector setup should choose **Server URL** under Connection and use
  `https://mcp.360madden.com/mcp`.
- Current Python MCP SDK examples use `from mcp.server.fastmcp import FastMCP`
  and `mcp.run(transport="streamable-http")`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `'python' is not recognized` from a `.cmd` helper | The launcher shell cannot find Python on `PATH`, or a direct embedded-Python run spawned a child `.cmd` without the normal user PATH. | Run the repo `.cmd` helpers from a normal CMD/terminal where `where python` resolves, or invoke the underlying `tools\riftreader_workflow\*.py` module with an explicit Python executable for diagnostics. |
| `MCP_PYTHON_SDK_MISSING` | Python `mcp` package is not installed. | Install `mcp[cli]` before `--serve`. |
| `RETIRED_TRANSPORT_PATH` | A retired Secure MCP Tunnel or Cloudflare quick-tunnel command was called. | Use `--manual-public-ip-plan --public-mcp-host mcp.360madden.com --json`. |
| ChatGPT cannot reach `mcp.360madden.com` | Local MCP server is stopped, Cloudflared service/tunnel is unhealthy, Cloudflare published application targets the wrong local port, DNS is not routed to the tunnel, or Cloudflare security settings block `/mcp`. | Verify `http://127.0.0.1:8770/mcp`, Cloudflared service health, published application target `http://127.0.0.1:8770`, proxied DNS, the scoped BIC-off rule for `/mcp*`, and external MCP initialize. |
| HTTP `421 Misdirected Request` through public Server URL | The public Host header is not allowlisted. | Restart `--serve` with `--allowed-host <bare-public-host>` and, for ChatGPT, `--allowed-origin https://chatgpt.com`. |
| HTTP `403 Forbidden` through a tunnel | The request has an `Origin` header not in `allowed_origins`. | Restart `--serve` with `--allowed-origin https://chatgpt.com` or the exact origin being tested. |
| ChatGPT cannot connect | Server URL is missing `/mcp`, not HTTPS, unreachable, or the local server/Cloudflared tunnel is stopped. | Restart the local MCP server, verify Cloudflared service health, then refresh/reconnect the ChatGPT app. |
| Write tool prompts for confirmation | Expected for action tools. | Review JSON payload before approving. |
| `PACKAGE_DRAFT_OPERATOR_EMPTY` | Only self-test drafts exist or no operator draft exists. | Submit/review a real operator-approved proposal first. |
| `INBOX_EMPTY` | No proposal is stored yet. | Submit a valid package proposal first. |
