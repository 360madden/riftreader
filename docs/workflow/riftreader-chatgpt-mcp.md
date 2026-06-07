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
| `scripts\riftreader-chatgpt-mcp.cmd` | Thin launcher for the narrow ChatGPT Developer Mode MCP adapter. | Use this for ChatGPT MCP self-tests, the active manual public-IP plan, and local `--serve`. Do not recreate it under a new name. |
| `scripts\riftreader-bridge-tunnel-session.cmd` | Local Artifact Bridge plus historical Cloudflare tunnel helper. | Related artifact bridge workflow only; do not confuse it with the narrow ChatGPT MCP adapter or use it as a ChatGPT MCP backup. |
| `scripts\riftreader-mcp-server.cmd` | Separate RiftReader stdio MCP server helper. | Support/low-level MCP lane; do not substitute it for the ChatGPT Developer Mode adapter without a deliberate design change. |
| `scripts\riftreader-mcp-client.cmd` | Client config/smoke helper. | Support helper only; not the user-facing ChatGPT app runtime. |

Acceptance proof for "use ChatGPT without Codex" requires the runtime to be
started by the operator outside Codex, from a normal CMD/PowerShell window or an
equivalent user-owned process. The operator should be able to see or identify
the expected local processes (`python.exe` for the MCP adapter and an
operator-owned HTTPS reverse proxy such as Caddy/nginx for public Server URL mode)
without relying on a Codex terminal or Codex quota.

Wrong proof:

```cmd
REM DO NOT count this as final non-Codex proof when launched only inside Codex.
scripts\riftreader-chatgpt-mcp.cmd --chatgpt-trial-session --json
```

Correct non-Codex manual external-IP proof shape:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host <current-external-ip> --json
scripts\riftreader-chatgpt-mcp.cmd --serve --host 127.0.0.1 --port 8770 --transport streamable-http --allowed-host <current-external-ip> --allowed-origin https://chatgpt.com
```

Keep that operator-owned console open while ChatGPT connects. A saved ChatGPT app
entry is only configuration; it does not start the local repo MCP server, does
not start the HTTPS reverse proxy, and does not update the Server URL when the
residential IP changes.

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
| Live RIFT control | Planned; not exposed | Explicit live approval plus exact current target identity and bounded action plan. |
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

Manual external-IP command plan:

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host <current-external-ip> --json
```

This prints the repo-specific manual external-IP Server URL plan for the local
RiftReader MCP adapter. It does not start the MCP server, start a reverse proxy,
configure a router, create certificates, register ChatGPT, mutate Git, send RIFT
input, or expose broad local tools. The JSON includes both argument arrays and
copyable command-line strings, plus the exact first ChatGPT smoke order:
`health`, `get_repo_status`, then `get_latest_handoff`.

Retired transport paths:

| Retired path | Rule |
|---|---|
| OpenAI Secure MCP Tunnel / `tunnel-client` | Do not use as primary or backup for this lane. |
| Cloudflare quick/named tunnel / `cloudflared` / `trycloudflare.com` | Do not use as primary or backup for this lane. |


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
| MCP Mission Control | `scripts\riftreader-mcp-mission-control.cmd --json` | Shows readiness, latest artifacts, Git dirty summary, ranked next actions, paste-safe commands, `--summary-md`, and `--checklist-md`. |
| Manual Public-IP Plan | `scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host <current-external-ip> --json` | Writes an ignored local plan artifact and prints the active Server URL, loopback MCP serve command, router/reverse-proxy checklist, retired-path warnings, and first ChatGPT smoke order. |
| Final Readiness Gate | `scripts\riftreader-mcp-final.cmd --status --compact-json` | Authoritative final-product gate covering Phase 2 proof/CI/freshness, clean tree, upstream sync, retired tunnel dependency state, environment preflight, tool-surface safety, and public-session state. |
| Proof Artifact Browser | `scripts\riftreader-mcp-artifacts.cmd --latest --json` | Lists latest readiness/smoke/trial/proof-input-template/inbox/draft/dry-run/proof artifacts; `--timeline`, `--kind <kind>`, and read-only `--open-latest` are supported. |
| Workflow Router | `scripts\riftreader-workflow-router.cmd --mcp --json` | Emits one recommended next action plus ranked alternatives from local artifacts and dirty state. |
| ChatGPT Trial Recorder | `scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --json` / `--check-latest-template --json` / `--check-input --input proof.json --json` / `--template --json` / `--record --input proof.json --json` / `--self-test --json` | Writes an ignored fillable proof input template, validates the latest or explicitly selected filled proof input read-only before recording, records operator-supplied actual ChatGPT facts under `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof`, and still supports stdout-only template printing; current proof should use `connectionMode=manual-public-ip` and fails closed on unknown connection mode, retired tunnel-host misuse, unfilled URL placeholders, tool count and exact tool-name set, per-tool output-schema confirmation/count/name set, repo-root redaction, inbox, package-draft creation, read-only draft review, dry-run success, bounded `dryRun.diffPreview` proof gaps, and apply-without-approval denial proof. |
| Safe Commit Packager | `scripts\riftreader-safe-commit-packager.cmd --plan --json` | Generates explicit `git add -- <path>` checklist and commit-message draft only; `--markdown` prints a review packet; it never stages, commits, or pushes. |
| Phase 1 Completion Gate | `scripts\riftreader-mcp-phase1.cmd --status --json` | Evaluates repo-side readiness plus the latest actual ChatGPT client proof revalidated against current proof rules, and reports whether Phase 1 is complete or externally blocked. |

The shared state layer marks self-test inbox/draft artifacts, adds artifact age
fields, indexes manual public-IP plan artifacts, warns on stale proof budgets,
and labels stopped or aged-out historical ephemeral public URLs as
expected-expired. The final gate also checks loopback port allocation, default
serve-port availability, retired tunnel dependency state, and whether
`.riftreader-local` remains Git-ignored for local MCP artifacts. Mission Control
`--manual-public-ip-plan` prints the active Server URL plan command without
starting the MCP server, reverse proxy, or router configuration. Secure MCP
Tunnel and Cloudflare command surfaces return retired/blocked status and are not
backups. Only `--run-readiness` and `--run-proposal-smoke` execute local-only
validation. No helper starts public exposure by default. The Phase 1 gate
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

## ChatGPT Web/Desktop route: manual external-IP Server URL

ChatGPT Developer Mode needs an HTTPS-reachable MCP endpoint. The current
RiftReader path is now **manual external IP**, not OpenAI Secure MCP Tunnel and
not Cloudflare. The operator starts the local MCP server and local HTTPS reverse
proxy outside Codex, forwards router TCP 443 to that reverse proxy, then pastes
the current external-IP URL into the ChatGPT custom MCP app.

Primary local plan command:

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host <current-external-ip> --json
```

If you only need to decide which existing non-Codex command to run, use the
plan-only launcher inventory first:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --operator-launch-plan --json
```

The plan prints the local loopback MCP server command. The adapter remains bound
to `127.0.0.1`; expose it through an operator-owned HTTPS reverse proxy instead
of binding the adapter directly to the LAN/WAN. The reverse proxy must forward
`/mcp` to `http://127.0.0.1:8770/mcp` and present a trusted HTTPS endpoint to
ChatGPT.

Manual network checklist:

1. Confirm the router WAN IPv4 is a real public address and not CGNAT.
2. Forward TCP 443 from the router/gateway to this PC's HTTPS reverse proxy.
3. Allow the reverse proxy through Windows Firewall.
4. Start the local MCP server outside Codex.
5. Start the HTTPS reverse proxy outside Codex.
6. In ChatGPT, configure the custom MCP app Server URL as
   `https://<current-external-ip>/mcp` and Authentication as **No Auth**.
7. If the residential IP changes, manually edit the ChatGPT app Server URL.

Current active proof packets must record the selected connection path explicitly:

| Field | Primary value | Rule |
|---|---|---|
| `connectionMode` | `manual-public-ip` | Required for the active ChatGPT Web/Desktop proof lane. |
| `publicMcpUrl` | `https://<current-external-ip>/mcp` or an operator-owned equivalent hostname | Must be HTTPS and currently reachable from ChatGPT/OpenAI. |
| `toolNames` | Canonical 12 allowlisted tool names | Must match the expected tool-name set exactly; duplicate, missing, or unexpected names block proof replay. |
| `toolOutputSchemasPresent` | `true` | Confirms the ChatGPT-observed tool descriptors include per-tool output-schema contracts for returned `structuredContent`. |
| `toolOutputSchemaCount` | `12` | Must match the allowlisted tool count so a partial schema registration cannot pass as final proof. |
| `toolOutputSchemaToolNames` | Canonical 12 allowlisted tool names | Must match the same expected tool-name set exactly, proving every allowlisted tool has an observed output-schema contract. |

Retired paths are not backups:

| Retired path | Rule |
|---|---|
| OpenAI Secure MCP Tunnel / `tunnel-client` | Do not use for this lane unless a future explicit policy reverses retirement. |
| Cloudflare quick/named tunnels / `cloudflared` / `trycloudflare.com` | Do not use for this lane unless a future explicit policy reverses retirement. |
| New tunnel wrapper scripts | Do not create duplicate wrappers; do not fork the workflow into another near-duplicate script. Extend the existing adapter only if policy changes. |

For public Server URL mode, the public Host header must still be allowlisted on
the MCP server. Do not pass a full URL to `--allowed-host`; pass only the exact
Host header value, such as `98.51.100.10` or `example.duckdns.org`. Pass only an
exact origin to `--allowed-origin`, such as `https://chatgpt.com`; do not include
a path, query, fragment, credentials, or wildcard.

## Registering in ChatGPT Developer Mode

In ChatGPT web:

1. Enable Developer Mode under Settings -> Apps -> Advanced settings.
2. Open Apps/Connectors settings.
3. Create an app/connector using **Server URL** and
   `https://<current-external-ip>/mcp`.
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
  Authentication. The current RiftReader manual public-IP lane uses No
  Authentication by operator choice.
- ChatGPT Developer Mode supports MCP tools, including read and write tools, but
  write actions require careful review; read-only detection respects
  `readOnlyHint`.
- ChatGPT local development needs an HTTPS-reachable MCP endpoint. The active
  RiftReader route is manual external IP through ChatGPT **Server URL**.
- OpenAI Secure MCP Tunnel and Cloudflare tunnels are retired for this lane and
  are not backup paths.
- ChatGPT connector setup should choose **Server URL** under Connection and use
  the current external-IP HTTPS URL.
- Current Python MCP SDK examples use `from mcp.server.fastmcp import FastMCP`
  and `mcp.run(transport="streamable-http")`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `'python' is not recognized` from a `.cmd` helper | The launcher shell cannot find Python on `PATH`, or a direct embedded-Python run spawned a child `.cmd` without the normal user PATH. | Run the repo `.cmd` helpers from a normal CMD/terminal where `where python` resolves, or invoke the underlying `tools\riftreader_workflow\*.py` module with an explicit Python executable for diagnostics. |
| `MCP_PYTHON_SDK_MISSING` | Python `mcp` package is not installed. | Install `mcp[cli]` before `--serve`. |
| `RETIRED_TRANSPORT_PATH` | A retired Secure MCP Tunnel or Cloudflare command was called. | Use `--manual-public-ip-plan --public-mcp-host <current-external-ip> --json`. |
| ChatGPT cannot reach external IP | Router forwarding, Windows Firewall, HTTPS reverse proxy, TLS, CGNAT, or ISP port blocking is preventing inbound access. | Verify WAN IP/public IP match, forward TCP 443 to the reverse proxy, allow firewall, and confirm the HTTPS endpoint externally. |
| HTTP `421 Misdirected Request` through public Server URL | The public Host header is not allowlisted. | Restart `--serve` with `--allowed-host <bare-public-host>` and, for ChatGPT, `--allowed-origin https://chatgpt.com`. |
| HTTP `403 Forbidden` through a tunnel | The request has an `Origin` header not in `allowed_origins`. | Restart `--serve` with `--allowed-origin https://chatgpt.com` or the exact origin being tested. |
| ChatGPT cannot connect | Server URL is missing `/mcp`, not HTTPS, unreachable, or the local server/reverse proxy is stopped. | Restart the local MCP server and reverse proxy, then refresh/reconnect the ChatGPT app. |
| Write tool prompts for confirmation | Expected for action tools. | Review JSON payload before approving. |
| `PACKAGE_DRAFT_OPERATOR_EMPTY` | Only self-test drafts exist or no operator draft exists. | Submit/review a real operator-approved proposal first. |
| `INBOX_EMPTY` | No proposal is stored yet. | Submit a valid package proposal first. |
