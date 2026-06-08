# 2026-06-08 — MCP Browser/Computer readiness surface

Fresh compact handoff:
`docs/handoffs/2026-06-08-mcp-desktop-control-readiness-handoff.md`.

| Item | Current truth |
|---|---|
| New helper | `scripts\riftreader-desktop-control-readiness.cmd --json` reports no-write Browser Use and Computer Use readiness. |
| Operator Lite | Adds `desktop-control-readiness` / `--desktop-control-readiness` plus a Browser/Computer readiness GUI button. |
| MCP dashboard | Adds a `Browser & Computer Use` status card and `desktopControl` JSON payload. |
| Current blocker | Browser Use dashboard smoke passed; remaining external blocker is `computer-use-native-pipe-not-confirmed`. |
| Latest observation | `.riftreader-local\riftreader-chatgpt-mcp\desktop-control-readiness\20260608-095805Z\observation.json` |
| Safety | Browser smoke was read-only. No clicks, typing, desktop UI automation, RIFT input, movement, tunnel management, package apply, or service changes were performed. |
| Next operator action | Repair/confirm Computer Use native pipe, rerun lightweight bootstrap/list-apps, then update the ignored observation artifact. |

---

# 2026-06-08 — ChatGPT MCP final readiness passed

Fresh compact handoff:
`docs/handoffs/2026-06-08-chatgpt-mcp-final-readiness-ci-passed-compact-handoff.md`.

| Item | Current truth |
|---|---|
| Final readiness | Passed at `2026-06-08T09:23:15Z`: `ok=true`, `status=passed`, `phase2Ready=true`, `ciStatus=passed`, `upstreamStatus=passed`. |
| Public route | `https://mcp.360madden.com/mcp` via Cloudflare named Tunnel `riftreader-mcp-360madden` to `127.0.0.1:8770`; Caddy/router/direct-public-IP remains deprecated legacy. |
| Actual ChatGPT proof | Complete and recorded under `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\20260608-091238Z\`. |
| Proof/CI baseline HEAD | `b332124f8bb28a09839ff584a293de6e8d2851a6`, synchronized with `origin/main` after the proof push. |
| Current-head CI | `.NET build and test` run `27127927030` passed; `RiftReader Policy` run `27127927100` passed. |
| Latest domain diagnostics | `.riftreader-local\riftreader-chatgpt-mcp\domain-diagnostics\20260608-092312Z\summary.json` passed; public smoke returned HTTP `200`, server `riftreader_chatgpt_mcp` version `1.27.1`. |
| Caddy note | Diagnostics may show `caddy.exe` listening on TCP 443, but `activeRouteUsesCaddy=false`; it is not the active ChatGPT MCP route. |
| Next operator action | Keep proof fresh and begin maintenance/UX hardening; any live RIFT stimulus or movement testing still requires explicit approval. |

---

# 2026-06-08 — ChatGPT MCP actual-client proof complete

Fresh proof-complete handoff:
`docs/handoffs/2026-06-08-chatgpt-mcp-actual-client-proof-complete-handoff.md`.

| Item | Current truth |
|---|---|
| Actual ChatGPT proof | Complete and recorded. All package-loop tools were observed through ChatGPT, including blocked `apply_latest_package_draft` without `approvalToken`. |
| Recorded proof | `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\20260608-091238Z\proof.json` |
| Proof replay | Passed and fresh in final readiness. |
| Public route | `https://mcp.360madden.com/mcp` via Cloudflare named Tunnel to `127.0.0.1:8770`; Caddy is deprecated and not active. |
| Remaining blockers | `git:upstream-not-synced:behind=0:ahead=3`, `phase2:not-ready`, and current-head CI missing for `.NET build and test` plus `RiftReader Policy`. |
| Next operator action | If approved, push `main` and wait for current-head CI. |

---

# 2026-06-08 — ChatGPT MCP dry-run proof compact handoff

Fresh compact handoff:
`docs/handoffs/2026-06-08-chatgpt-mcp-dry-run-proof-compact-handoff.md`.

| Item | Current truth |
|---|---|
| Proof progress | ChatGPT has successfully called all package-loop tools through `dry_run_latest_package_draft`. |
| Latest draft ID | `20260608T034503Z-2828ca695563` |
| Current blocker | Final actual-client negative proof: ChatGPT must call `apply_latest_package_draft` without `approvalToken` and it must block. |
| Public route | `https://mcp.360madden.com/mcp` via Cloudflare named Tunnel to `127.0.0.1:8770`; Caddy is deprecated and not active. |
| Next operator action | In ChatGPT, call `apply_latest_package_draft` without `approvalToken`, then paste the blocked output into Codex. |

---

# 2026-06-08 — ChatGPT MCP review-ready proof compact handoff

Fresh compact handoff:
`docs/handoffs/2026-06-08-chatgpt-mcp-review-ready-proof-compact-handoff.md`.

| Item | Current truth |
|---|---|
| Proof progress | ChatGPT has successfully called `get_package_proposal_template`, `submit_package_proposal`, `list_inbox`, `create_package_draft_from_inbox`, and `review_latest_package_draft`. |
| Latest draft ID | `20260608T034503Z-2828ca695563` |
| Current blocker | ChatGPT still needs to call `dry_run_latest_package_draft` and return diff-preview proof. |
| Public route | `https://mcp.360madden.com/mcp` via Cloudflare named Tunnel to `127.0.0.1:8770`; Caddy is deprecated and not active. |
| Next operator action | In ChatGPT, call `dry_run_latest_package_draft`, then paste the output into Codex. |

---

# 2026-06-08 — ChatGPT MCP draft-created proof compact handoff

Fresh compact handoff:
`docs/handoffs/2026-06-08-chatgpt-mcp-draft-created-proof-compact-handoff.md`.

| Item | Current truth |
|---|---|
| Proof progress | ChatGPT has successfully called `get_package_proposal_template`, `submit_package_proposal`, `list_inbox`, and `create_package_draft_from_inbox`. |
| Latest inbox ID | `20260608T034503Z-2828ca695563` |
| Latest draft ID | `20260608T034503Z-2828ca695563` |
| Current blocker | ChatGPT still needs to call `review_latest_package_draft` and prove read-only review for the latest draft. |
| Public route | `https://mcp.360madden.com/mcp` via Cloudflare named Tunnel to `127.0.0.1:8770`; Caddy is deprecated and not active. |
| Next operator action | In ChatGPT, call `review_latest_package_draft`, then paste the output into Codex. |

---

# 2026-06-08 — ChatGPT MCP list-inbox proof compact handoff

Fresh compact handoff:
`docs/handoffs/2026-06-08-chatgpt-mcp-list-inbox-proof-compact-handoff.md`.

| Item | Current truth |
|---|---|
| Proof progress | ChatGPT has successfully called `get_package_proposal_template`, `submit_package_proposal`, and `list_inbox`. |
| Latest inbox ID | `20260608T034503Z-2828ca695563` |
| Current blocker | ChatGPT still needs to call `create_package_draft_from_inbox` with `20260608T034503Z-2828ca695563`. |
| Public route | `https://mcp.360madden.com/mcp` via Cloudflare named Tunnel to `127.0.0.1:8770`; Caddy is deprecated and not active. |
| Push intent | User requested compact handoff then push; after validation, push `main` to `origin`. |

---

# 2026-06-08 — ChatGPT MCP submit-proof current handoff

Fresh handoff:
`docs/handoffs/2026-06-08-chatgpt-mcp-submit-proof-current-handoff.md`.

| Item | Current truth |
|---|---|
| Proof progress | ChatGPT has successfully called `get_package_proposal_template`, `submit_package_proposal`, and `list_inbox`. |
| Latest inbox ID | `20260608T034503Z-2828ca695563` |
| Current blocker | ChatGPT still needs to call `create_package_draft_from_inbox` with `20260608T034503Z-2828ca695563`. |
| Public route | `https://mcp.360madden.com/mcp` via Cloudflare named Tunnel to `127.0.0.1:8770`; Caddy is deprecated and not the active route. |
| Latest validation | Proof input check is blocked-safe with `create-package-draft-not-confirmed`; domain diagnostics passed at `2026-06-08T03:48:37Z`. |
| Next operator action | In ChatGPT, call `create_package_draft_from_inbox` with the latest inbox ID, then paste the output into Codex. |

---

# 2026-06-08 — ChatGPT MCP package-template callable update

Current actual ChatGPT Web/Desktop proof advanced: the operator pasted a
successful `get_package_proposal_template` result from the `rift-mcp` Developer
Mode app at `2026-06-08T03:35:46Z`.

| Item | Current truth |
|---|---|
| Latest handoff | `docs/handoffs/2026-06-08-chatgpt-mcp-package-template-callable-handoff.md` |
| Cleared blockers | `get_package_proposal_template` and `submit_package_proposal` are now callable in ChatGPT; `template-fetch-not-confirmed` and `submit-package-proposal-not-confirmed` are no longer current. |
| Current proof input | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-232355Z\proof-input.json` |
| Latest ChatGPT inbox ID | `20260608T034503Z-2828ca695563` |
| Current proof state | Still blocked until ChatGPT `list_inbox` sees `20260608T034503Z-2828ca695563`, then `create_package_draft_from_inbox`, `review_latest_package_draft`, `dry_run_latest_package_draft`, and `apply_latest_package_draft` without `approvalToken` are observed from ChatGPT. |
| Public route | `https://mcp.360madden.com/mcp` via Cloudflare named Tunnel to local backend `127.0.0.1:8770`; Caddy remains deprecated and is not the active route. |
| Latest domain diagnostics | `.riftreader-local\riftreader-chatgpt-mcp\domain-diagnostics\20260608-033956Z\summary.json` passed. |
| Next operator action | In ChatGPT, call `list_inbox`, then paste the output back into Codex. |

---

# 2026-06-07 — Cloudflare named Tunnel canonical route update

Current public MCP route is **Cloudflare named Tunnel**, not Caddy/router:

```text
ChatGPT Web/Desktop
-> https://mcp.360madden.com/mcp
-> Cloudflare proxied DNS
-> Cloudflare Tunnel riftreader-mcp-360madden
-> cloudflared Windows service
-> http://127.0.0.1:8770/mcp
-> RiftReader ChatGPT MCP adapter
```

| Item | Current truth |
|---|---|
| Public smoke | `scripts\riftreader-mcp-domain-diagnostics.cmd --public-mcp-host mcp.360madden.com --json` passed on `2026-06-07T22:37:12Z`. |
| Latest proof artifact | `.riftreader-local\riftreader-chatgpt-mcp\domain-diagnostics\20260607-223711Z\summary.json`. |
| Server identity | `serverInfo.name=riftreader_chatgpt_mcp`, version `1.27.1`, HTTP 200. |
| Cloudflare route | Named tunnel `riftreader-mcp-360madden`, published application target `http://127.0.0.1:8770`. |
| Cloudflare security rule | `Disable BIC for RiftReader MCP endpoint` disables Browser Integrity Check for `/mcp*`. |
| Deprecated route | Caddy/router/direct-public-IP route is legacy and must not be recreated as a fallback. |
| Still retired | OpenAI Secure MCP Tunnel and `trycloudflare.com` quick tunnels. |

---

# RiftReader Handoff — 2026-05-30

**Compact re-entry doc.** Read this first when returning to the project.

## Latest compact handoff — ChatGPT MCP domain prerequisite context — 2026-06-07 16:55 EDT

A new compact handoff exists at
docs/handoffs/2026-06-07-1655-chatgpt-mcp-domain-prereq-context-handoff.md.

The ChatGPT Web/Desktop MCP lane has been realigned around the full prerequisite
chain instead of treating repo code or a saved ChatGPT app as sufficient. The
current target remains `https://mcp.360madden.com/mcp` with `No Authentication`,
routed through an operator-owned local HTTPS reverse proxy to the operator-owned
local MCP server on `127.0.0.1:8770`. Final proof still requires actual
ChatGPT Web/Desktop observations from operator-owned processes outside Codex.

| Evidence | Result |
|---|---|
| Operator plan | `scripts\riftreader-chatgpt-mcp.cmd --operator-launch-plan --json` now defaults to `mcp.360madden.com` and emits the prerequisite chain. |
| Public-host plan | `scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host mcp.360madden.com --json` classifies the host as `domain-or-ddns-host` and lists Cloudflare/Caddy/router prerequisites. |
| Docs/policy | `AGENTS.md` and `docs\workflow\riftreader-chatgpt-mcp.md` now describe the public-host/domain Server URL lane and distinguish retired quick tunnels from the domain/DNS route. |
| Current blocker | Public domain smoke remains blocked by Cloudflare `403 Error 1010`; Caddy ACME logs show Cloudflare-intercepted challenge failures. |
| Boundary | No Cloudflare/router/firewall settings, ChatGPT app registration, RIFT input, CE/x64dbg, provider writes, or proof recording were performed. |
## Latest compact handoff — ChatGPT MCP domain read-only dashboard — 2026-06-07 15:25 EDT

A new compact handoff exists at
docs/handoffs/2026-06-07-1525-chatgpt-mcp-domain-readonly-dashboard-handoff.md.

The ChatGPT Web/Desktop MCP lane now has a safe Phase 0 public-domain proof path
and a localhost-only dashboard, built on the existing canonical adapter. The
default full 12-tool path remains unchanged; --tool-profile public-read-only
exposes only health, get_repo_status, get_latest_handoff,
get_workflow_control_summary, and get_workflow_control_plan for the first
public proof on https://mcp.360madden.com/mcp with No Authentication.

| Evidence | Result |
|---|---|
| Read-only profile | scripts\riftreader-chatgpt-mcp.cmd --validate-sdk --tool-profile public-read-only --json passed with exactly 5 registered read-only tools. |
| Full profile preserved | scripts\riftreader-chatgpt-mcp.cmd --validate-sdk --json passed with the canonical 12-tool surface. |
| Dashboard | scripts\riftreader-mcp-dashboard.cmd serves a status-only local dashboard on http://127.0.0.1:8788/; no control endpoints are exposed. |
| Domain diagnostics | .riftreader-local\riftreader-chatgpt-mcp\domain-diagnostics\20260607-191604Z\summary.json correctly blocked on missing local backend and Cloudflare 403 Error 1010. |
| Phase 0 proof template | .riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-192205Z\proof-input.json. |
| Boundary | No public route fix, ChatGPT registration, RIFT input, CE/x64dbg, provider write, push, or remote mutation was performed. |

## Latest compact handoff — ChatGPT MCP 12-tool current proof gate — 2026-06-06 20:58 EDT

A new compact handoff exists at
`docs/handoffs/2026-06-06-2058-chatgpt-mcp-12tool-current-proof-gate-handoff.md`.

The ChatGPT Web/Desktop MCP lane is now aligned to the current 12-tool
manual-public-IP proof contract. Fresh proof-input templates must match
`connectionMode=manual-public-ip`, `toolCount=12`, output-schema count `12`,
and include `get_workflow_control_summary` plus gated
`apply_latest_package_draft` before final/Phase 1 gates recommend checking that
file. Old 11-tool or Secure Tunnel-mode templates route back to writing a fresh
template.

| Evidence | Result |
|---|---|
| Current template | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-005424Z\proof-input.json` is 12-tool/manual-public-IP. |
| Manual public-IP plan | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260607T005441Z-manual-public-ip-plan.json` used `https://173.54.133.37/mcp` and did not start a server/tunnel. |
| Local readiness | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260607T005601Z-trial-readiness.json` passed locally with 12-tool loopback transport smoke and unapproved apply denial. |
| Recommended proof action | Fill the fresh template with actual ChatGPT observations, then run its emitted `--check-input` and `--record` commands. |
| Boundary | No public tunnel, ChatGPT registration, approved package apply, RIFT input, CE/x64dbg, provider writes, or push was performed while creating this handoff. |


## Latest compact handoff — ChatGPT MCP current gate — 2026-06-05 17:30 UTC

A new compact handoff exists at
`docs/handoffs/2026-06-05-1730-chatgpt-mcp-current-gate-handoff.md`.

Current local MCP state: clean worktree, `main...origin/main [ahead 19]`, HEAD
`8891fe889a34f7f5ce0ee0248a410235fea602c9`. Final readiness remains blocked
because local trial-readiness/proposal-smoke artifacts are stale, actual
ChatGPT proof is stale and missing current proof-contract fields, current-head
CI is missing, and the branch has not been pushed.

| Evidence | Result |
|---|---|
| Latest hardening | `8891fe8 Require ChatGPT MCP proof tool identities`. |
| Final gate | `scripts\riftreader-mcp-final.cmd --status --compact-json` ran read-only and returned expected blocked status. |
| Recommended safe next action | `scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json` to refresh local-only readiness before gated proof/CI work. |
| Gated next actions | Push for current-head CI and fresh actual ChatGPT Secure Tunnel proof both require explicit approval/operator action. |
| Boundary | No public tunnel, ChatGPT registration, RIFT input, CE/x64dbg attach, provider writes, proof promotion, push, or remote mutation. |

## Latest compact handoff — ChatGPT MCP proof tool-identity contract — 2026-06-05 12:05 UTC

A new compact handoff exists at
`docs/handoffs/2026-06-05-1205-chatgpt-mcp-proof-tool-identity-contract-handoff.md`.

The actual ChatGPT Web/Desktop MCP proof contract now validates exact tool
identity, not only counts. Fresh proof packets must include both observed
`toolNames` and observed `toolOutputSchemaToolNames`, and both lists must match
the canonical 10-tool allowlist.

| Evidence | Result |
|---|---|
| Proof fields | `toolNames` and `toolOutputSchemaToolNames` are required by `validate_proof`. |
| Fail-closed validation | Duplicate, missing, unexpected, non-list, or non-string tool-name entries block proof replay. |
| Replay/state visibility | Proof replay and latest-artifact summaries surface both tool-name proof lists. |
| Mission Control | Final-product progress no longer treats actual-client proof as completed without exact tool-name matches. |
| Focused validation | `python -m unittest scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase1_completion scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control` passed 46 tests in 12.203s. |
| Broad MCP validation | `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_final_readiness scripts.test_local_artifact_bridge scripts.test_package_draft_review scripts.test_mcp_phase1_completion` passed 189 tests in 46.533s. |
| Targeted ledger | `.riftreader-local\validation-runs\20260605-121300-915646\summary.md` passed in 45.276s. |
| Boundary | No public tunnel, ChatGPT registration, RIFT input, CE/x64dbg attach, provider writes, proof promotion, push, or remote mutation. |

## Latest compact handoff — ChatGPT MCP proof output-schema contract — 2026-06-05 11:54 UTC

A new compact handoff exists at
`docs/handoffs/2026-06-05-1154-chatgpt-mcp-proof-output-schema-contract-handoff.md`.

The actual ChatGPT Web/Desktop MCP proof contract now requires the operator
proof packet to confirm that ChatGPT saw per-tool `outputSchema` contracts for
all 10 allowlisted tools. This keeps the final Secure Tunnel proof aligned with
the local manifest/SDK/runtime schema guardrails.

| Evidence | Result |
|---|---|
| Proof fields | `toolOutputSchemasPresent=true` and `toolOutputSchemaCount=10` are required by `validate_proof`. |
| Replay visibility | Proof replay and latest-artifact summaries surface output-schema proof facts. |
| Mission Control | Final-product progress no longer treats actual-client proof as completed without output-schema proof facts. |
| Focused validation | `python -m unittest scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase1_completion scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control` passed 43 tests in 12.325s. |
| Broad MCP validation | `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_final_readiness scripts.test_local_artifact_bridge scripts.test_package_draft_review scripts.test_mcp_phase1_completion` passed 186 tests in 46.540s. |
| Targeted ledger | `.riftreader-local\validation-runs\20260605-115535-540313\summary.md` passed in 46.027s. |
| Boundary | No public tunnel, ChatGPT registration, RIFT input, CE/x64dbg attach, provider writes, proof promotion, push, or remote mutation. |

## Latest compact handoff — ChatGPT MCP runtime result contract — 2026-06-05 11:38 UTC

A new compact handoff exists at
`docs/handoffs/2026-06-05-1138-chatgpt-mcp-runtime-result-contract-handoff.md`.

The ChatGPT Web/Desktop MCP adapter now validates each tool handler result
against the minimum structuredContent contract before returning it to the client
or writing sanitized audit metadata. Malformed handler payloads fail closed as
`TOOL_RESULT_CONTRACT_INVALID` instead of leaking ambiguous structured content.

| Evidence | Result |
|---|---|
| Code path | `tools/riftreader_workflow/riftreader_chatgpt_mcp.py::validate_tool_result_payload`. |
| Runtime guard | `RiftReaderChatGptMcpAdapter.call_tool()` validates every handler result before return/audit. |
| Focused validation | `python -m unittest scripts.test_riftreader_chatgpt_mcp` passed 58 tests in 3.080s. |
| Broad MCP validation | `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_final_readiness scripts.test_local_artifact_bridge scripts.test_package_draft_review` passed 179 tests in 43.731s. |
| Targeted ledger | `.riftreader-local/validation-runs/20260605-114220-809119/summary.md` passed in 43.023s. |
| Local MCP self-test | `scripts\riftreader-chatgpt-mcp.cmd --self-test --json` passed with `ok=true`. |
| SDK validation | `scripts\riftreader-chatgpt-mcp.cmd --validate-sdk --json` passed with 10 registered tools. |
| Boundary | No public tunnel, ChatGPT registration, RIFT input, CE/x64dbg attach, provider writes, proof promotion, push, or remote mutation. |

## Latest compact handoff — ChatGPT MCP output-schema guardrails — 2026-06-05 11:28 UTC

A new compact handoff exists at
`docs/handoffs/2026-06-05-1128-chatgpt-mcp-output-schema-guardrails-handoff.md`.

The ChatGPT Web/Desktop MCP manifest and SDK/transport verification now surface
and require per-tool `outputSchema` contracts for returned `structuredContent`.
This catches missing/non-object output-schema regressions locally before an
actual ChatGPT Secure Tunnel proof run.

| Evidence | Result |
|---|---|
| Code path | `tools/riftreader_workflow/riftreader_chatgpt_mcp.py`. |
| Manifest | `tool_manifest()` now includes `outputSchema` for all 10 allowlisted tools. |
| Verifier | SDK/transport validation captures and blocks missing/non-object output schemas. |
| Focused validation | `python -m unittest scripts.test_riftreader_chatgpt_mcp` passed 56 tests in 3.048s. |
| Broad MCP validation | `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_final_readiness scripts.test_local_artifact_bridge scripts.test_package_draft_review` passed 177 tests in 44.610s. |
| Targeted ledger | `.riftreader-local/validation-runs/20260605-113233-975976/summary.md` passed in 42.770s. |
| Boundary | No public tunnel, ChatGPT registration, RIFT input, CE/x64dbg attach, provider writes, proof promotion, push, or remote mutation. |

## Latest compact handoff — Validation ledger blocked-safe status handling — 2026-06-05 11:14 UTC

A new compact handoff exists at
`docs/handoffs/2026-06-05-1114-validation-ledger-blocked-safe-status-handoff.md`.

The timestamped validation ledger `full-local` tier now treats known helper
exit code `2` from the decision packet and workflow-status helpers as expected
blocked-safe evidence instead of failed CI. This lets full local validation keep
running through the repo's current proof-recovery blocker while still recording
explicit warnings for expected nonzero status exits.

| Evidence | Result |
|---|---|
| Root cause | `full-local` previously failed fast when `decision-packet` returned expected blocked-safe exit `2`. |
| Code path | `tools/riftreader_workflow/validation_ledger.py`. |
| Regression test | `python -m unittest scripts.test_validation_ledger` passed 10 tests in 9.811s. |
| Full local validation | `.riftreader-local/validation-runs/20260605-110550-722733/summary.md` passed in 470.565s with expected status-exit warnings. |
| Boundary | No public tunnel, ChatGPT registration, RIFT input, CE/x64dbg attach, provider writes, proof promotion, push, or remote mutation. |

## Latest compact handoff — ChatGPT MCP Mission Control final-gate truth — 2026-06-05 10:56 UTC

A new compact handoff exists at
`docs/handoffs/2026-06-05-1056-chatgpt-mcp-mission-control-final-truth-handoff.md`.

Mission Control now uses compact final-readiness truth for dashboard status,
blockers, recommended action, and ranked actions. A stale actual-client proof
artifact with historical `status=passed` can no longer make the dashboard look
ready when final proof replay blocks on the current Secure Tunnel/diff-preview
proof rules.

| Evidence | Result |
|---|---|
| Active Mission Control | `tools/riftreader_workflow/mcp_mission_control.py`. |
| Final-gate truth source | `tools/riftreader_workflow/mcp_final_readiness.py::compact_final_readiness`. |
| Dashboard routing | `recommendedNextAction` and `rankedActions[0]` now prefer final readiness blocker-specific action before raw artifact state. |
| Real dirty dashboard check | `scripts/riftreader-mcp-mission-control.cmd --json` reported `status=blocked`, `ok=false`, and top ranked `safe-commit-plan` while this slice was dirty. |
| Focused validation | `python -m unittest scripts.test_mcp_mission_control scripts.test_mcp_final_readiness scripts.test_workflow_router scripts.test_mcp_phase1_completion scripts.test_mcp_phase2_status` passed 52 tests in 11.110s. |
| Broad MCP validation | `python -m unittest scripts.test_mcp_mission_control scripts.test_mcp_final_readiness scripts.test_workflow_router scripts.test_mcp_phase1_completion scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_riftreader_chatgpt_mcp scripts.test_local_artifact_bridge scripts.test_package_draft_review` passed 182 tests in 48.063s. |
| Final ledger | `.riftreader-local/validation-runs/20260605-105433-751150/summary.md` passed in 45.527s. |

## Latest compact handoff — ChatGPT MCP final next-action priority — 2026-06-05 10:46 UTC

A new compact handoff exists at
`docs/handoffs/2026-06-05-1046-chatgpt-mcp-final-next-action-priority-handoff.md`.

The RiftReader ChatGPT Web/Desktop MCP final readiness gate now chooses specific
actionable blockers before generic wrapper blockers. Proof replay failures route
directly to actual-client proof recording instead of generic `phase2:not-ready`,
and upstream-sync-only failures use a non-mutating approval/status action rather
than implying an automated push.

| Evidence | Result |
|---|---|
| Active final gate | `tools/riftreader_workflow/mcp_final_readiness.py`. |
| Proof priority | `proof:*` blockers recommend `record-actual-client-proof` with `scripts/riftreader-chatgpt-trial-recorder.cmd --write-template --json` so the operator gets the current fillable 11-tool proof packet before recording actual ChatGPT observations. |
| Upstream priority | `git:upstream-not-synced:*` recommends `request-push-approval` with `git --no-pager status --short --branch`; no push command is emitted. |
| Dirty-tree priority | Dirty worktree still recommends `safe-commit-plan` before external proof/CI work. |
| Focused validation | `python -m unittest scripts.test_mcp_final_readiness scripts.test_mcp_phase2_status scripts.test_mcp_phase1_completion scripts.test_mcp_mission_control scripts.test_workflow_router` passed 51 tests in 11.650s. |
| Broad MCP validation | `python -m unittest scripts.test_mcp_final_readiness scripts.test_mcp_phase1_completion scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_riftreader_chatgpt_mcp scripts.test_local_artifact_bridge scripts.test_package_draft_review` passed 181 tests in 46.618s. |
| Final ledger | `.riftreader-local/validation-runs/20260605-104515-615980/summary.md` passed in 46.777s. |

## Latest compact handoff — ChatGPT MCP Phase 1 current-proof revalidation — 2026-06-05 10:38 UTC

A new compact handoff exists at
`docs/handoffs/2026-06-05-1038-chatgpt-mcp-phase1-current-proof-revalidation-handoff.md`.

The RiftReader ChatGPT Web/Desktop MCP Phase 1 completion gate now revalidates
the latest actual-client proof against the current proof recorder rules. Stale
proof artifacts that merely have historical `status=passed` no longer make Phase
1 complete after the Secure Tunnel and diff-preview proof contract changed.

| Evidence | Result |
|---|---|
| Active Phase 1 gate | `tools/riftreader_workflow/mcp_phase1_completion.py`. |
| Current proof rule source | `tools/riftreader_workflow/chatgpt_trial_recorder.py::validate_proof`. |
| Legacy proof behavior | Old `status=passed` proof now blocks with `actual-client-proof-invalid:<rule>` if it lacks current fields. |
| Local Phase 1 status | `scripts/riftreader-mcp-phase1.cmd --status --json` blocks as expected on stale proof missing `connectionMode` and current proof fields. |
| Focused validation | `python -m unittest scripts.test_mcp_phase1_completion scripts.test_mcp_phase2_status scripts.test_mcp_final_readiness scripts.test_mcp_workflow_state` passed 41 tests in 8.659s. |
| Broad MCP validation | `python -m unittest scripts.test_mcp_phase1_completion scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_final_readiness scripts.test_riftreader_chatgpt_mcp scripts.test_local_artifact_bridge scripts.test_package_draft_review` passed 179 tests in 48.076s. |
| Final ledger | `.riftreader-local/validation-runs/20260605-103641-064539/summary.md` passed in 46.529s. |

## Latest compact handoff — ChatGPT MCP Secure Tunnel proof template — 2026-06-05 10:22 UTC

A new compact handoff exists at
`docs/handoffs/2026-06-05-1022-chatgpt-mcp-secure-tunnel-proof-template-handoff.md`.

The RiftReader ChatGPT Web/Desktop MCP actual-client proof path is now
explicitly **OpenAI Secure MCP Tunnel-first**. The trial proof template requires
`connectionMode`, defaults to `openai-secure-mcp-tunnel`, and fails closed if a
Secure Tunnel-mode proof uses public fallback hosts such as Cloudflare or ngrok.

| Evidence | Result |
|---|---|
| Active proof recorder | `tools/riftreader_workflow/chatgpt_trial_recorder.py`. |
| Required connection proof | `connectionMode` must be `openai-secure-mcp-tunnel` or explicit `public-https-fallback`. |
| Primary-path fallback-host guard | `trycloudflare.com`, `ngrok.app`, and `ngrok-free.app` block proof replay when `connectionMode=openai-secure-mcp-tunnel`. |
| Placeholder guard | Unfilled `publicMcpUrl` placeholders with `<...>` block proof recording. |
| Replay visibility | Proof replay and artifact summaries now surface `connectionMode`. |
| Focused validation | `python -m unittest scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state` passed 27 tests in 6.132s. |
| Broad MCP validation | `python -m unittest scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_phase1_completion scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_final_readiness scripts.test_riftreader_chatgpt_mcp scripts.test_local_artifact_bridge scripts.test_package_draft_review` passed 178 tests in 47.060s. |
| Final ledger | `.riftreader-local/validation-runs/20260605-102706-854015/summary.md` passed in 47.278s. |

## Latest compact handoff — ChatGPT MCP actual-client diff-preview proof contract — 2026-06-05 10:00 UTC

A new compact handoff exists at
`docs/handoffs/2026-06-05-1000-chatgpt-mcp-actual-proof-diff-preview-contract-handoff.md`.

The RiftReader ChatGPT Web/Desktop MCP actual-client proof recorder now matches
the stronger local transport smoke contract. A fresh external ChatGPT
Web/Desktop proof must confirm draft review and bounded dry-run diff-preview
facts before Phase 2/final readiness can pass.

| Evidence | Result |
|---|---|
| Active proof recorder | `tools/riftreader_workflow/chatgpt_trial_recorder.py`. |
| Active proof replay | `tools/riftreader_workflow/mcp_proof_replay.py`. |
| New required review proof | `reviewLatestPackageDraftSucceeded=true` and `reviewLatestPackageDraftReadOnly=true`. |
| New required diff-preview proof | `dryRunDiffPreviewOk=true`, `dryRunDiffPreviewArtifactUnderPackageIntake=true`, `dryRunDiffPreviewBoundedBytes=true`, positive `dryRunDiffPreviewTextLength`, and boolean `dryRunDiffPreviewTruncated`. |
| Defensive artifact replay | If a local dry-run diff artifact path is present, replay blocks paths outside `.riftreader-local/package-intake`. |
| Focused validation | `python -m unittest scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_final_readiness` passed 42 tests in 3.958s. |
| Broader MCP validation | `python -m unittest scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_phase1_completion scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_final_readiness scripts.test_riftreader_chatgpt_mcp scripts.test_local_artifact_bridge scripts.test_package_draft_review` passed 173 tests in 49.331s. |
| Final ledger | `.riftreader-local/validation-runs/20260605-100236-265736/summary.md` passed in 48.033s. |

## Latest compact handoff — ChatGPT MCP transport dry-run preview coverage — 2026-06-05 09:40 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-05-0940-chatgpt-mcp-transport-dry-run-preview-handoff.md`.

The RiftReader ChatGPT Web/Desktop MCP local proposal transport smoke now proves
the full package-review loop over the real SDK/loopback MCP transport:
`submit_package_proposal` → `list_inbox` → `create_package_draft_from_inbox` →
`review_latest_package_draft` → `dry_run_latest_package_draft` →
`dryRun.diffPreview`.

| Evidence | Result |
|---|---|
| Active adapter | `tools\riftreader_workflow\riftreader_chatgpt_mcp.py`. |
| Tool surface | Still 10 allowlisted tools. |
| New transport coverage | Proposal transport smoke calls review and dry-run after inert package draft creation. |
| New verifier gate | Transport verifier requires `dryRunSucceeded=true` and `dryRun.diffPreview.ok=true`. |
| Safety | Local loopback only; no public tunnel, ChatGPT registration, `--apply`, Git mutation, live RIFT input, debugger, or provider write. |
| Focused validation | `python -m unittest scripts.test_riftreader_chatgpt_mcp` passed 55 tests in 2.790s. |
| Proposal transport smoke | `scripts\riftreader-chatgpt-mcp.cmd --proposal-transport-smoke --json` passed; artifact `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T094411Z-proposal-transport-smoke.json`. |
| Trial readiness | `scripts\riftreader-chatgpt-mcp.cmd --trial-readiness --json` passed; artifact `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T094435Z-trial-readiness.json`. |
| Broader MCP validation | `python -m unittest scripts.test_local_artifact_bridge scripts.test_package_draft_review scripts.test_riftreader_chatgpt_mcp scripts.test_mcp_final_readiness scripts.test_mcp_proof_replay` passed 135 tests in 34.694s. |
| Final ledger | `.riftreader-local\validation-runs\20260605-094551-835464\summary.md` passed in 34.510s. |


## Latest compact handoff — ChatGPT MCP dry-run diff preview — 2026-06-05 09:11 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-05-0911-chatgpt-mcp-dry-run-diff-preview-handoff.md`.

The RiftReader ChatGPT Web/Desktop MCP path now exposes a bounded
`dryRun.diffPreview` from the existing `dry_run_latest_package_draft` tool. This
preserves the current 10-tool contract while letting ChatGPT review the latest
package-intake `package.diff` without arbitrary filesystem reads. The preview
is capped at 16 KiB, reads only
`.riftreader-local\package-intake\*\package.diff`, marks truncation explicitly,
and blocks unsafe artifact paths without echoing arbitrary absolute paths.

| Evidence | Result |
|---|---|
| Active adapter | `tools\riftreader_workflow\riftreader_chatgpt_mcp.py`. |
| Tool surface | 10 allowlisted tools; no new tool-count/proof-contract churn. |
| New review field | `dryRun.diffPreview`. |
| Safety | Read-only, bounded, repo-local package-intake artifact preview; no `--apply`, Git, live RIFT, debugger, provider write, tunnel run, or ChatGPT connector registration. |
| Focused validation | `python -m unittest scripts.test_riftreader_chatgpt_mcp` passed 54 tests in 3.368s. |
| Broader MCP validation | `python -m unittest scripts.test_local_artifact_bridge scripts.test_package_draft_review scripts.test_riftreader_chatgpt_mcp scripts.test_mcp_final_readiness scripts.test_mcp_proof_replay` passed 134 tests in 36.049s. |
| Final ledger | `.riftreader-local\validation-runs\20260605-092746-535699\summary.md` passed in 34.756s. |

## Latest compact handoff — OpenAI Secure MCP Tunnel MCP path — 2026-06-05 05:54 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-05-0554-openai-secure-mcp-tunnel-handoff.md`.

The RiftReader ChatGPT Web/Desktop MCP path is now **OpenAI Secure MCP Tunnel
first**. Local-only adapter tests remain the default, and Cloudflare quick tunnel
support is preserved only as deprecated fallback/dev-only support.

| Evidence | Result |
|---|---|
| ChatGPT app display name | `rift-mcp`. |
| Active local adapter | `tools\riftreader_workflow\riftreader_chatgpt_mcp.py`. |
| Tool surface | 8 allowlisted tools only. |
| Recommended Web/Desktop path | OpenAI Secure MCP Tunnel using `tunnel-client` and local stdio MCP. |
| Local default | Self-test / SDK validation / loopback transport smoke. |
| Deprecated fallback | Cloudflare quick tunnel / `trycloudflare.com`. |
| Current blocker | External tunnel setup remains gated: tunnel id, runtime API key, `tunnel-client init/doctor/run`, ChatGPT connector registration, and fresh actual-client proof. |
| Primary command | `scripts\riftreader-chatgpt-mcp.cmd --secure-tunnel-plan --json`. |
| Mission Control | `scripts\riftreader-mcp-mission-control.cmd --secure-tunnel-plan --json` displays the plan command without starting `tunnel-client`; final readiness now verifies `tunnel-client` presence, SHA256, and `--version` behavior for the primary path. |

Safety: no live RIFT input, movement, `/reloadui`, screenshot key, x64dbg/CE
attach, provider write, ChatGPT registration, public tunnel startup, Git
mutation, commit, or push was performed. This handoff is transport-only and does
not authorize live game/proof/promotion work.

## Latest compact handoff — post-update no-input yaw/facing inventory — 2026-06-03 08:05 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-03-0805-postupdate-no-input-yaw-facing-inventory-handoff.md`.

The first no-input post-update recovery pass is complete. The old promoted
static owner root remains blocked (`[rift_x64+0x32EBC80] == 0x0`), the current
coordinate candidate refresh blocked safely with `global-container-coordinate-leads-missing`,
and the recovery/status surfaces now expose post-update yaw/facing seeds as
candidate-only inventory.

| Evidence | Result |
|---|---|
| Current live target | PID `77152`, HWND `0x17A0DB2`, process start `2026-06-02T15:45:29.2617327Z`, module base `0x7FF7211C0000`. |
| Current game epoch | Manifest `STABLE-1-1152-a-1256395`, `rift_x64.exe` SHA1 `a8ba8748ea752e4e5581cea34188dc702469c923`. |
| Coordinate refresh | `scripts\captures\postupdate-global-container-coordinate-readback-20260603-074657-625756\summary.json` blocked with `global-container-coordinate-leads-missing`; no samples were read. |
| Static/access refresh | `scripts\captures\postupdate-static-access-chain-20260603-074712-201893\summary.json` blocked with `process-start-mismatch`. |
| Rollup | `scripts\captures\postupdate-owner-root-rediscovery-20260603-074732-196871\summary.json` blocked with `no-owner-root-hypothesis-yet` and `process-start-mismatch`. |
| Yaw/facing inventory | `postUpdateRecovery.yawFacingCandidates.status=candidate`, root `rift_x64+0x335F508`, `fieldCandidateCount=8`, `routeControlAuthorized=false`, `actionableForNavigation=false`. |
| Consumer/navigation status | `.riftreader-local\navigation-consumer-state\latest\summary.json` and `.riftreader-local\navigation-pointer-discovery\latest\summary.json` keep `canExecuteLiveNavigation=false`. |
| Validation ledger | `.riftreader-local\validation-runs\20260603-080950-908985\summary.md` passed in `31.002s`. |

Safety: no input, movement, route execution, `/reloadui`, screenshot key,
x64dbg/CE attach, target memory write, provider write, current-truth update,
ProofOnly, proof promotion, actor-chain promotion, Git commit, or Git push was
performed. The next safe slice is target-epoch mismatch repair for the
post-update helpers. Movement proof and restart/relog survival remain gated.

## Latest compact handoff — post-update coordinate candidate movement proof — 2026-06-02 23:05 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-2305-postupdate-coordinate-candidate-movement-proof-handoff.md`.

The old promoted coordinate resolver remains blocked after the 2026-06-02 game update:
`[rift_x64+0x32EBC80] == 0x0` on the current post-update epoch. The strongest
replacement evidence is now the **candidate-only** global-container chain:

`[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30`

| Evidence | Result |
|---|---|
| Stationary polling | 5/5 candidate samples matched with drift `0.0`. |
| Pointer-family backtrace | Container pointer backtraced to module global `rift_x64+0x32DD7E8`. |
| Movement proof | One bounded `W` pulse for `800 ms`; post-move memory matched fresh API coordinate with max abs delta `0.003950195312540927`. |
| Movement proof packet | `scripts\captures\postupdate-global-container-movement-proof-20260602-230020-479116\summary.json`. |
| Candidate readback | `scripts\captures\postupdate-global-container-coordinate-readback-20260602-225839-858745\summary.json`. |
| Consumer state | `postUpdateRecovery` is visible but `candidateOnly=true`, `promotionEligible=false`, `routeControlAuthorized=false`, `actionableForNavigation=false`. |

Safety: one approved movement pulse was sent for displacement proof. No client/game
restart, x64dbg/CE attach, target memory write, provider write, current-truth
update, ProofOnly, proof promotion, actor-chain promotion, or route/navigation
execution was performed. Restart/relog survival remains the next required proof
gate before any promotion.

## Latest compact handoff — post-update recovery/reacquisition — 2026-06-02 20:22 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-2022-postupdate-recovery-reacquisition-handoff.md`.

The repo is clean and aligned with `origin/main` at commit
`918595b Add post-update global container coordinate readback`. The current
blocked-safe state is unchanged: the 2026-06-02 RIFT update invalidated the old
promoted static owner root, and the latest decision packet still reports the
post-update gate `latest-static-owner-readback-root-pointer-null`.

The strongest recovery evidence remains the **candidate-only** global-container
coordinate chain:

`[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30`

| Evidence | Result |
|---|---|
| Old promoted root | `[rift_x64+0x32EBC80] == 0x0`; stale 2026-06-01 promoted truth must not be used for navigation. |
| Candidate readback | `scripts\captures\postupdate-global-container-coordinate-readback-20260602-200619-457973\summary.json` passed no-input current readback; best max abs delta vs reference `0.004628906250218279`; 5/5 stationary polling samples matched. |
| Rollup | `scripts\captures\postupdate-owner-root-rediscovery-20260602-201119-651369\summary.json` surfaces the candidate while preserving the blocked recovery verdict. |
| Decision packet refresh | `cmd /c scripts\riftreader-decision-packet.cmd --compact-json --write` returned expected `LAST=2`, `status=blocked`, `lane=proof-recovery`. |
| Next code slice | Wire the candidate-vs-promoted bridge into `navigation_consumer_state.py`, `decision_packet.py`, schemas, and tests so downstream consumers can see candidate evidence while route control stays blocked. |

Safety: no input, movement, route control, debugger/CE attach, target memory
write, provider write, current-truth apply, ProofOnly, proof promotion,
actor-chain promotion, or navigation execution was performed. The `0x32DD7E8`
chain is not promoted and is not consumer-ready navigation truth.

## Latest compact handoff — post-update global-container coordinate readback — 2026-06-02 20:06 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-2006-postupdate-global-container-coordinate-readback-handoff.md`.

The 2026-06-02 RIFT update invalidated the old promoted static owner root for
the current epoch: `[rift_x64+0x32EBC80]` is readable but currently null. The
safe post-update recovery lane now has a stronger **candidate-only** static /
container coordinate readback:

`[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30`

| Evidence | Result |
|---|---|
| Static access-chain packet | `scripts\captures\postupdate-static-access-chain-20260602-195804-076419\summary.json` found function `0xC38390` reading `rift_x64+0x32DD7E8`. |
| Orientation-only root | `[rift_x64+0x335F508]` remains a non-position orientation/static-layout anchor; do not use it as world position. |
| New readback helper | `scripts\postupdate_global_container_coordinate_readback.py`; wrapper `scripts\riftreader-postupdate-global-container-coordinate-readback.cmd`. |
| Best readback | `[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30` matched the current reference coordinate with max abs delta `0.004628906250218279`. |
| Polling baseline | `scripts\captures\postupdate-global-container-coordinate-readback-20260602-200619-457973\summary.json` passed 5/5 no-input samples with stationary planar drift `0.0`. |
| Rediscovery status | `scripts\captures\postupdate-owner-root-rediscovery-20260602-201119-651369\summary.json` now surfaces this candidate while keeping overall recovery blocked on proof/root gates. |

Safety: no input, movement, debugger/CE attach, target memory write, provider
write, `current-truth` apply, ProofOnly, proof promotion, actor-chain promotion,
or navigation control was performed. The new chain is not promoted and still
requires explicit movement/restart proof before any consumer can treat it as
working navigation truth.

Current next safe action: wire a candidate-vs-promoted bridge for downstream
navigation consumers so the repo can expose this post-update readback as
candidate evidence while continuing to block stale promoted-current navigation.

## Latest compact handoff — navigation live-run command plan — 2026-06-02 09:19 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-0919-navigation-live-run-command-plan-handoff.md`.

RiftReader now has a saved-JSON-only live-run command-plan artifact. During the
current RIFT maintenance/world-entry outage, this advances practical automated
navigation infrastructure without requiring game access: the helper consumes a
passed live-run review and emits dry-run plus execution command templates while
still refusing to authorize or invoke route execution.

| Evidence | Result |
|---|---|
| Helper | `scripts\navigation_live_run_command_plan.py`; launcher `scripts\riftreader-navigation-live-run-command-plan.cmd`. |
| Output schema | `docs\schemas\navigation\navigation-live-run-command-plan.schema.json`; registered in `scripts\navigation_schema_validate.py`. |
| Tool catalog | `navigation-live-run-command-plan` is canonical, safe-read-only, and in the recommended workflow; tool count is now `52`. |
| Command-plan smoke | `scripts\riftreader-navigation-live-run-command-plan.cmd --live-run-review-json scripts\captures\navigation-live-run-review-20260602-090328-266990\summary.json --game-maintenance --json` passed with `requestedMode=continuous-route-run`, `commandPlanOnly=true`, `executionAuthorized=false`, `executionAttempted=false`, `routeRunnerInvoked=false`, `movementSent=false`, `inputSent=false`, and `targetMemoryBytesRead=false`. |
| Schema smoke | `scripts\captures\navigation-live-run-command-plan-20260602-091850-026491\summary.json` passed `navigation-live-run-command-plan` schema validation with `validationErrorCount=0`. |

Safety: the command-plan helper reads saved JSON only. It sends no input or
movement, performs no live target memory read/write, no `/reloadui`, no
screenshot key, no debugger/CE attach, no provider write, no proof/actor/facing
/turn-rate promotion, and no route control. It intentionally keeps
`executionAuthorized=false`, `executionAttempted=false`, and
`routeRunnerInvoked=false`.

Current next action while game entry is down: add a downstream consumer replay
fixture that validates the full saved chain: package → request → review →
command-plan. When RIFT is available again, refresh target proof/current pose
before considering any bounded live dry-run or movement approval.

## Latest compact handoff — navigation live-run review — 2026-06-02 09:03 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-0903-navigation-live-run-review-handoff.md`.

RiftReader now has a saved-JSON-only live-run request review gate. A downstream
consumer can create a live-run request, then run a separate review artifact that
validates the request schema, validates the source downstream package schema,
checks request/package freshness budgets, and reports whether the request is
ready for a later explicit live-approval decision.

| Evidence | Result |
|---|---|
| Helper | `scripts\navigation_live_run_review.py`; launcher `scripts\riftreader-navigation-live-run-review.cmd`. |
| Output schema | `docs\schemas\navigation\navigation-live-run-review.schema.json`; registered in `scripts\navigation_schema_validate.py`. |
| Tool catalog | `navigation-live-run-review` is canonical, safe-read-only, and in the recommended workflow; tool count is now `51`. |
| Review smoke | `scripts\riftreader-navigation-live-run-review.cmd --live-run-request-json scripts\captures\navigation-live-run-request-20260602-084748-577328\summary.json --json` passed with `readyForSeparateLiveApproval=true`, `executionReviewApproved=false`, `executionAuthorized=false`, `executionAttempted=false`, `routeRunnerInvoked=false`, `movementSent=false`, `inputSent=false`, and `targetMemoryBytesRead=false`. |
| Schema smoke | `scripts\captures\navigation-live-run-review-20260602-090328-266990\summary.json` passed `navigation-live-run-review` schema validation with `validationErrorCount=0`. |

Safety: the review helper reads saved JSON only. It sends no input or movement,
performs no live target memory read/write, no `/reloadui`, no screenshot key, no
debugger/CE attach, no provider write, no proof/actor/facing/turn-rate
promotion, and no route control. It intentionally keeps
`executionReviewApproved=false`, `executionAuthorized=false`, and
`routeRunnerInvoked=false`.

Current next action: add a non-executing live-run command-plan artifact that
consumes the passed review summary and produces the exact route-runner command,
target preflight requirements, and refusal reasons while still leaving execution
authorization, route-runner invocation, input, and movement false.

## Latest compact handoff — navigation live-run request — 2026-06-02 08:48 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-0848-navigation-live-run-request-handoff.md`.

RiftReader now has a saved-JSON-only gated live-run request artifact. A
downstream consumer can take a passed downstream package and record an intended
route execution request for later review without invoking movement, route
control, or live target access.

| Evidence | Result |
|---|---|
| Helper | `scripts\navigation_live_run_request.py`; launcher `scripts\riftreader-navigation-live-run-request.cmd`. |
| Output schema | `docs\schemas\navigation\navigation-live-run-request.schema.json`; registered in `scripts\navigation_schema_validate.py`. |
| Tool catalog | `navigation-live-run-request` is canonical, safe-read-only, and in the recommended workflow; tool count is now `50`. |
| Request smoke | `scripts\riftreader-navigation-live-run-request.cmd --downstream-package-json scripts\captures\navigation-downstream-package-20260602-083424-354068\summary.json --json` passed with `requestAcceptedForReview=true`, `executionAuthorized=false`, `executionAttempted=false`, `routeRunnerInvoked=false`, `movementSent=false`, `inputSent=false`, and `targetMemoryBytesRead=false`. |
| Schema smoke | `scripts\captures\navigation-live-run-request-20260602-084748-577328\summary.json` passed `navigation-live-run-request` schema validation with `validationErrorCount=0`. |

Safety: the request helper reads saved JSON only. It sends no input or
movement, performs no live target memory read/write, no `/reloadui`, no
screenshot key, no debugger/CE attach, no provider write, no proof/actor/facing
/turn-rate promotion, and no route control. Live execution remains explicitly
gated.

Current next action: add a saved live-run request review gate that validates the
request and source package freshness and emits an explicit non-executable review
summary. It should still avoid route-runner invocation and live input unless a
separate explicit movement approval gate is present.

## Latest compact handoff — navigation downstream package — 2026-06-02 08:35 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-0835-navigation-downstream-package-handoff.md`.

RiftReader now has a one-command downstream navigation package workflow. It
refreshes consumer pose, reruns the downstream consumer demo, builds the route
preview, and validates all package artifacts so another local project can fetch
one durable machine-readable bundle.

| Evidence | Result |
|---|---|
| Helper | `scripts\navigation_downstream_package.py`; launcher `scripts\riftreader-navigation-downstream-package.cmd`. |
| Output schema | `docs\schemas\navigation\navigation-downstream-package.schema.json`; registered in `scripts\navigation_schema_validate.py`. |
| Tool catalog | `navigation-downstream-package` is canonical, safe-read-only, and in the recommended workflow; tool count is now `49`. |
| Package smoke | `scripts\riftreader-navigation-downstream-package.cmd --waypoint-readiness-json scripts\captures\navigation-waypoint-readiness-20260602-071111-256714\summary.json --json` passed with `canRenderRoute=true`, `canUseDryRunContract=true`, `canRenderRoutePreview=true`, `canQueueGatedLiveRunRequest=true`, and `canExecuteLiveNavigation=false`. |
| Schema smoke | `scripts\captures\navigation-downstream-package-20260602-083424-354068\summary.json` passed `navigation-downstream-package` schema validation with `validationErrorCount=0`. |

Safety: the package may read live target memory through the consumer refresh
step, but it sends no input or movement, performs no target memory write, no
`/reloadui`, no screenshot key, no debugger/CE attach, no provider write, no
proof/actor/facing/turn-rate promotion, and no route control. Live execution
remains explicitly gated.

Current next action: add a gated live-run request schema and saved request
artifact so downstream consumers can express an intended route execution request
without invoking live movement. The actual route runner should continue to
require explicit live approval before execution.

## Latest compact handoff — navigation route preview — 2026-06-02 08:22 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-0822-navigation-route-preview-handoff.md`.

RiftReader now has a saved-artifact route preview workflow for downstream
map/UI consumers. It derives the active leg, remaining route legs, per-leg
distance/bearing, active-leg yaw delta, suggested initial turn, and arrival
radius from the latest consumer pose plus normalized waypoints.

| Evidence | Result |
|---|---|
| Helper | `scripts\navigation_route_preview.py`; launcher `scripts\riftreader-navigation-route-preview.cmd`. |
| Output schema | `docs\schemas\navigation\navigation-route-preview.schema.json`; registered in `scripts\navigation_schema_validate.py`. |
| Tool catalog | `navigation-route-preview` is canonical, safe-read-only, and in the recommended workflow; tool count is now `48`. |
| Route-preview smoke | `scripts\riftreader-navigation-route-preview.cmd --waypoint-readiness-json scripts\captures\navigation-waypoint-readiness-20260602-071111-256714\summary.json --max-consumer-state-age-seconds 60 --json` passed with `activeLegPlanarDistance=273.80771899466805`, `activeLegBearingDegrees=52.256314250788364`, `activeLegInitialYawDeltaDegrees=50.49110968572896`, `canQueueGatedLiveRunRequest=true`, and `canExecuteLiveNavigation=false`. |
| Schema smoke | `scripts\captures\navigation-route-preview-20260602-082123-882214\summary.json` passed `navigation-route-preview` schema validation with `validationErrorCount=0`. |

Safety: the route preview reads saved JSON only. It sends no input or movement,
performs no live target read/write, no `/reloadui`, no screenshot key, no
debugger/CE attach, no provider write, no proof/actor/facing/turn-rate
promotion, and no route control. Live execution remains explicitly gated.

Current next action: add a one-command downstream package helper that runs
consumer refresh, route preview, schema validation, and consumer demo as one
safe workflow so external projects can fetch a complete bundle without racing
the 5-second pose freshness window.

## Latest compact handoff — navigation consumer refresh — 2026-06-02 08:01 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-0801-navigation-consumer-refresh-handoff.md`.

RiftReader now has a no-input consumer refresh workflow that regenerates the
consumer pose and reruns the downstream consumer demo in one command.

| Evidence | Result |
|---|---|
| Helper | `scripts\navigation_consumer_refresh.py`; launcher `scripts\riftreader-navigation-consumer-refresh.cmd`. |
| Output schema | `docs\schemas\navigation\navigation-consumer-refresh.schema.json`; registered in `scripts\navigation_schema_validate.py`. |
| Tool catalog | `navigation-consumer-refresh` is canonical, safe-read-only, and in the recommended workflow; tool count is now `47`. |
| Read-only refresh smoke | `scripts\riftreader-navigation-consumer-refresh.cmd --waypoint-readiness-json scripts\captures\navigation-waypoint-readiness-20260602-071111-256714\summary.json --json` passed with `canRenderRoute=true`, `canUseDryRunContract=true`, `canQueueGatedLiveRunRequest=true`, and `canExecuteLiveNavigation=false`. |
| Schema smoke | `scripts\captures\navigation-consumer-refresh-20260602-080549-511814\summary.json` passed `navigation-consumer-refresh` schema validation with `validationErrorCount=0`. |

Safety: the refresh workflow may read live target memory through
`navigation_consumer_state.py`, but it sends no input or movement, performs no
`/reloadui`, no screenshot key, no debugger/CE attach, no provider write, no
target memory write, no proof/actor/facing/turn-rate promotion, and no route
control. Live execution remains explicitly gated.

Current next action: add a route preview artifact that derives per-leg distance,
bearing, initial yaw delta, and arrival radius from the refreshed consumer state
plus normalized waypoints for downstream map/UI consumers.

## Latest compact handoff — navigation consumer demo — 2026-06-02 07:48 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-0748-navigation-consumer-demo-handoff.md`.

RiftReader now has a saved-artifact-only downstream consumer demo report that
combines consumer pose, normalized waypoints, route sequence dry-run, contract
report, and schema checks into one practical external-consumer decision.

| Evidence | Result |
|---|---|
| Helper | `scripts\navigation_consumer_demo.py`; launcher `scripts\riftreader-navigation-consumer-demo.cmd`. |
| Output schema | `docs\schemas\navigation\navigation-consumer-demo.schema.json`; registered in `scripts\navigation_schema_validate.py`. |
| Consumer-state schema repair | Real `target.moduleBaseCheck` / `processStartCheck` / `hwndCheck` object payloads now validate. |
| Tool catalog | `navigation-consumer-demo` is canonical, safe-read-only, and in the recommended workflow; tool count is now `46`. |
| Saved-artifact smoke | `scripts\riftreader-navigation-consumer-demo.cmd --waypoint-readiness-json scripts\captures\navigation-waypoint-readiness-20260602-071111-256714\summary.json --json` passed with `canRenderRoute=true`, `canUseDryRunContract=true`, `canQueueGatedLiveRunRequest=false`, and `canExecuteLiveNavigation=false`. |
| Schema smoke | The generated consumer-demo summary and latest consumer-state summary both passed `scripts\riftreader-navigation-schema-validate.cmd --input <summary.json> --json`. |

Safety: the consumer demo reads saved JSON only. It sends no input or movement,
performs no live target read/write, no `/reloadui`, no screenshot key, no
debugger/CE attach, no provider write, no proof/actor/facing/turn-rate
promotion, and no route control.

Current next action: add an artifact freshness/refresh command that regenerates
consumer-state pose and reruns the consumer demo in one safe no-input workflow.
Keep live movement execution separately gated.

## Latest compact handoff — navigation consumer schema package — 2026-06-02 07:30 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-0730-navigation-schema-package-handoff.md`.

RiftReader now has a tracked JSON-schema package and a saved-JSON validator for
the practical automated-navigation consumer artifacts built in the previous
slices.

| Evidence | Result |
|---|---|
| Schema package | `docs\schemas\navigation\` contains schemas for consumer state, normalized waypoints, continuous sequence dry-runs, sequence contract reports, and waypoint readiness summaries. |
| Validator helper | `scripts\navigation_schema_validate.py`; launcher `scripts\riftreader-navigation-schema-validate.cmd`. |
| Schema inference | Infers from `kind` or `provenance.kind`; `--schema-key` can override. |
| Tool catalog | `navigation-schema-validate` is canonical, safe-read-only, and in the recommended workflow; tool count is now `45`. |
| Saved-artifact smoke | `scripts\riftreader-navigation-schema-validate.cmd --input scripts\captures\navigation-waypoint-readiness-20260602-071111-256714\summary.json --json` passed with `schemaKey=navigation-waypoint-readiness`, `validationErrorCount=0`. |
| Targeted tests | `python -m unittest scripts.test_navigation_schema_validate scripts.test_tool_catalog` passed: `Ran 11 tests in 0.772s OK`. |

Safety: the schema validator reads saved JSON only. It sends no input or
movement, performs no live target read/write, no `/reloadui`, no screenshot key,
no debugger/CE attach, no provider write, no proof/actor/facing/turn-rate
promotion, and no route control.

Current next action: build a tiny downstream-consumer fixture/report that reads
the consumer-state, normalized waypoint, dry-run contract, and schema-validation
artifacts together and states whether an external project can render/queue a
route or must block on stale target/proof.

## Latest compact handoff — navigation waypoint readiness infrastructure — 2026-06-02 07:08 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-0708-navigation-waypoint-readiness-handoff.md`.

RiftReader now has a one-command waypoint readiness workflow for practical
automated-navigation consumers. It validates waypoint files, writes a normalized
canonical waypoint artifact, runs a no-input sequence dry-run by default, and
then validates the saved sequence contract report.

| Evidence | Result |
|---|---|
| Readiness helper | `scripts\navigation_waypoint_readiness.py`; launcher `scripts\riftreader-navigation-waypoint-readiness.cmd`. |
| Waypoint lint | Validates `waypoints[]`, finite `x/y/z`, nonnegative `arrivalRadius`, duplicate IDs, and requested ID filters. |
| Normalization | Writes canonical `normalized-waypoints.json`; legacy `radius` becomes `arrivalRadius`; missing IDs become `waypoint-###`. |
| Dry-run bundle | Default mode runs `static_owner_continuous_route_runner.py --dry-run --json` against the normalized file. |
| Consumer gate | Runs `navigation_sequence_summary_contract.py` against the saved dry-run summary and reports `contractConsumable`. |
| Offline mode | `--skip-dry-run` performs lint/normalization only and reads no live target memory. |
| Tool catalog | `navigation-waypoint-readiness` is canonical, safe-read-only, and in the recommended workflow; tool count is now `44`. |
| Full no-input smoke | `scripts\riftreader-navigation-waypoint-readiness.cmd --waypoint-sequence-json scripts\navigation\smoke-test-waypoints.json --json` passed with `waypoint-readiness-consumable`, `contractConsumable=true`, `movementSent=false`, and `inputSent=false`. |

Safety: no input, movement, `/reloadui`, screenshot key, debugger/CE attach,
provider write, target memory write, proof/actor promotion, or route-control
promotion is performed. Default mode may perform read-only current-target memory
reads through the dry-run route planner; use `--skip-dry-run` for offline-only
lint.

Current next action: add a consumer JSON-schema package for pose, dry-run
sequence, contract report, and waypoint readiness summaries.

## Latest compact handoff — navigation sequence contract report — 2026-06-02 06:55 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-0655-navigation-sequence-contract-handoff.md`.

RiftReader now has a saved-summary contract report for continuous route
sequence dry-runs, so external consumers can validate a dry-run artifact without
reading route-runner internals.

| Evidence | Result |
|---|---|
| Contract helper | `scripts\navigation_sequence_summary_contract.py`; launcher `scripts\static-owner-continuous-route-sequence-contract.cmd`. |
| Accepted source | `kind=static-owner-continuous-route-sequence`, `operator.dryRun=true`, `status=passed`. |
| Safety contract | Requires no movement, no input, no navigation control, no debugger attach, no provider writes, and no target memory writes. |
| Sequence contract | Accepts `sequence-dry-run-plan-built` or already-arrived dry-run sequences; rejects simulated multi-waypoint arrival claims. |
| Tool catalog | `static-owner-route-sequence-contract` is canonical, safe-read-only, and in the recommended workflow; tool count is now `43`. |
| Saved-summary smoke | `scripts\static-owner-continuous-route-sequence-contract.cmd scripts\captures\static-owner-continuous-route-sequence-20260602-064437-323455\summary.json --json` passed with `consumable=true`. |

Safety: the contract helper reads a saved JSON summary only. It sends no input
or movement, reads no live target memory, performs no `/reloadui`, screenshot
key, debugger/CE attach, provider write, target memory write, proof/actor
promotion, or route-control promotion.

Current next action: add an offline waypoint-file linter/generator that checks
schema, radius, IDs, coordinate shape, and produces a first-leg dry-run plus
contract report in one command.

## Latest compact handoff — navigation sequence dry-run reliability — 2026-06-02 06:40 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-0640-navigation-sequence-dry-run-handoff.md`.

The continuous route runner now has a safer consumer-facing dry-run sequence
contract: dry-run does not require live approval flags, and a multi-waypoint
dry-run no longer claims all waypoints were reached without movement.

| Evidence | Result |
|---|---|
| Helper updated | `scripts\static_owner_continuous_route_runner.py`. |
| Dry-run approval behavior | `--dry-run` bypasses `--turn-approved`, `--movement-approved`, and `--allow-candidate-turn-control` because no input can be sent. |
| Sequence dry-run behavior | Stops after the first unreached leg plan with verdict `sequence-dry-run-plan-built`; `legsPlanned=1`, `legsArrived=0`. |
| Waypoint compatibility | `arrivalRadius` remains canonical; legacy `radius` is accepted when `arrivalRadius` is absent. |
| Live no-input verification | `python scripts\static_owner_continuous_route_runner.py --waypoint-sequence-json scripts\navigation\smoke-test-waypoints.json --dry-run --json` passed with `movementSent=false` and `inputSent=false`. |

Safety: no input, movement, `/reloadui`, screenshot key, debugger/CE attach,
provider write, target memory write, proof/actor promotion, or route-control
promotion was performed. Live multi-waypoint execution remains gated by the
existing approval flags and proof-anchor movement freshness checks.

Current next action: add a saved-summary validator/report for sequence dry-runs
so external projects can consume waypoint feasibility output without knowing
runner internals.

## Latest compact handoff — navigation consumer state contract — 2026-06-02 06:22 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-0622-navigation-consumer-state-handoff.md`.

RiftReader now has a read-only consumer-facing navigation state contract for
external projects that need current player position and yaw without inheriting
route-control or candidate-field ambiguity.

| Evidence | Result |
|---|---|
| Helper | `scripts\navigation_consumer_state.py`; launcher `scripts\riftreader-navigation-consumer-state.cmd`. |
| Contract doc | `docs\workflows\navigation-consumer-contract.md`. |
| Tool catalog | `navigation-consumer-state` is canonical and safe-read-only. |
| Live read-only verification | `scripts\riftreader-navigation-consumer-state.cmd --json --write` passed. |
| Latest output | `.riftreader-local\navigation-consumer-state\latest\summary.json`; verdict `consumer-navigation-state-ready`. |
| Position/yaw | Uses promoted position `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` and promoted yaw `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314`. |

Safety: the helper sends no input or movement, performs no `/reloadui`, no
debugger/CE attach, no target memory writes, no provider writes, no current-truth
apply, no proof/actor/facing/turn-rate promotion, and no route control.
`owner+0x304` and support fields remain diagnostics only.

Current next action: use the consumer-state helper as the stable pose feed for
other projects, then advance waypoint-sequence dry-run reliability before any
explicitly approved live multi-waypoint run.

## Latest compact handoff — target-current resolver repair — 2026-06-02 04:39 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-0439-target-current-resolver-repair-handoff.md`.

The Phase 1 C# `--read-target-current` blocker is repaired for the current
selected-target packet. The previous blocker was
`target-current-family-resolution-failed:fam-CEC3708F`.

| Evidence | Result |
|---|---|
| Root cause | Target acceptance required optional name/distance fields that the memory sample did not read, and target-family ranking let high-volume coord-only `fam-CEC3708F` outrank the full coord+level+health object family. |
| Code repair | `TargetCurrentReader` now treats name/distance as optional readback fields; `TargetSignatureProbeCaptureBuilder` prioritizes full coord+level+health matches over coord-only hit count. |
| Live readback | `--read-target-current --json` passed against PID `12664` / process `rift_x64`. |
| Phase 1 helper | `scripts\riftreader-phase1-target-entity-snapshot.cmd --json` passed. |
| New helper output | `scripts\captures\phase1-target-entity-snapshot-20260602-043904-933361\summary.json`; verdict `phase1-target-current-reader-passed`. |
| Resolved target family | `fam-6F81F26E` at `0x1E036430920`, level `45`, health `18208`, coords `(7251.04, 821.44, 2987.8699)`. |

Safety: the repair validation used read-only process memory access only. No live
input, movement, `/reloadui`, screenshot key, Cheat Engine/x64dbg, provider
writes, target memory writes, proof promotion, actor-chain promotion, branch
rewrite, or remote mutation was performed. `ReaderBridgeExport.lua` remains a
post-flush SavedVariables snapshot, not live IPC truth.

Current next action: repeat Phase 1 with a non-self selected target once target
selection is reliable, then use the passing target reader output as the seed for
selected-target memory/entity discovery.

## Latest compact handoff — Phase 1 target entity snapshot helper — 2026-06-02 04:04 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-02-0404-phase1-target-entity-snapshot-handoff.md`.

Phase 1 target-entity discovery now has a durable Python-first evidence wrapper
and a live post-flush selected-target packet. The selected target was
deterministically bootstrapped as `Atank` with `/target Atank`, then `/reloadui`
was intentionally sent to flush `ReaderBridgeExport.lua` as a post-save target
snapshot.

| Evidence | Result |
|---|---|
| Phase 1 helper | `scripts\phase1_target_entity_snapshot.py`; launcher `scripts\riftreader-phase1-target-entity-snapshot.cmd`. |
| Helper output | `scripts\captures\phase1-target-entity-snapshot-20260602-035907-998714\summary.json`. |
| Selected target export | `targetPresent=true`; target `Atank` / `u035400012FA2D207`; file updated `2026-06-02T03:54:15Z`. |
| Target-current reader blocker | `target-current-family-resolution-failed:fam-CEC3708F`. |
| Tooling commit | `ceeba06 Add Phase 1 target entity snapshot helper`. |

Safety: exact PID/HWND live target acquisition sent Tab attempts, one click,
`/target Atank`, and `/reloadui`; no movement was sent. No Cheat Engine/x64dbg,
provider writes, target memory writes, proof promotion, actor-chain promotion,
or branch rewrite were performed. The helper itself sends no input and treats
SavedVariables only as a deliberate post-flush snapshot, not live IPC truth.

Current next action: debug the C# `--read-target-current` target family resolver
for `fam-CEC3708F`, then repeat Phase 1 with a non-self selected target once one
can be selected reliably.

## Latest compact handoff — current proof anchor restored — 2026-06-01 21:50 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-01-2150-current-proof-anchor-restored-handoff.md`.

The current proof anchor has been restored for active target PID `12664` /
HWND `0x205146C`. A targeted current-PID family scan found
`api-family-hit-000001 @ 0x1E067A80330`, the displaced-pose batch captured
3 poses with 2 bounded exact-HWND `W` pulses, promotion validated, and final
same-target `ProofOnly` passed.

| Evidence | Result |
|---|---|
| Current proof pointer | `docs\recovery\current-proof-anchor-readback.json` status `current-target-proofonly-passed`. |
| Final ProofOnly | `scripts\captures\live-test-ProofOnly-20260601-214524\run-summary.json`; `passed-proof-only`. |
| Current truth | `docs\recovery\current-truth.json` updated `2026-06-01T21:52:01Z`. |
| API vs chain | Final max abs delta `0.003935546875027285 <= 0.25`. |
| Actor no-debug | `scripts\captures\actor-chain-no-debug-status-20260601-214643-169924\summary.json`; blockers `[]`. |
| Historical stale pointer | `docs\recovery\historical\current-proof-anchor-readback-2026-06-01-pid12148-hwnd640C0C-historical.json`. |

Safety: movement was limited to the proof-pose batch's two exact-HWND `W`
pulses; final ProofOnly sent no movement. No Cheat Engine/x64dbg, target memory
writes, provider writes, push, or branch rewrite were performed.

Current safe next action: continue actor/stat-chain provenance work from the
now-current proof anchor, or push only if explicitly approved.

## Latest compact handoff — stage-0 navigation pointer refresh — 2026-06-01 21:24 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-01-2124-stage0-navigation-pointer-refresh-handoff.md`.

Stage-0 navigation pointer discovery is refreshed, indexed, and backed by
fresh current-target truth. The dashboard is fresh with no stale sources, and
current truth has same-target static-chain/API-now agreement with max abs delta
`0.004418749999786087 <= 0.25`.

Current target identity is PID `12664`, HWND `0x205146C`, process start
`2026-06-01T17:19:45.159353Z`, module base `0x7FF6EE5D0000`.

| Resolver / field | Result |
|---|---|
| Coordinate | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`; latest readback `(7308.57421875, 823.53662109375, 3045.098388671875)`. |
| Facing/yaw | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314`; current yaw `44.11798623707763°`. |
| Velocity/speed | Forward/back/stop live-correlation passed; still not a dedicated static speed pointer. |
| `owner+0x304` | Candidate-only yaw-adjacent scalar, not active turn-rate. |
| `owner+0x438/+0x43C/+0x440` | Candidate-only raw support fields; unchanged during forward progress. |
| Actor/stat chain | Not promoted; no-debug status still blocks on `current-proof-anchor-not-passed`. |

Fresh evidence now indexed:

| Evidence | Path |
|---|---|
| Navigation dashboard | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` |
| Current truth | `docs\recovery\current-truth.json` updated `2026-06-01T21:21:33Z` |
| Static readback | `scripts\captures\static-owner-coordinate-chain-readback-20260601-211913-897755\summary.json` |
| API marker | `scripts\captures\rift-api-reference-currentpid-12664-20260601-212046.json` |
| Forward route refresh | `scripts\captures\static-owner-nav-route-step-20260601-211844-099888\summary.json` |
| Backward route contrast | `scripts\captures\static-owner-nav-route-step-20260601-210105-864282\summary.json` |
| Offline Ghidra evidence | `scripts\captures\ghidra-static-analysis-20260601-210631\summary.json` |
| Actor no-debug status | `scripts\captures\actor-chain-no-debug-status-20260601-210455-466513\summary.json` |

Safety: live movement was exact-target and bounded; no Cheat Engine/x64dbg,
target memory writes, provider writes, proof promotion, actor promotion, or
turn-rate promotion were performed. Git push was not performed. Current local
branch was ahead of origin and remains awaiting explicit push approval.

Current safe next action: continue actor/stat-chain provenance discovery from
read-only/no-debug evidence where practical, or approve a push if the local
stage-0 commits should be published.

## Latest compact handoff — static facing/yaw restart survival propagated — 2026-06-01 17:34 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-01-1734-static-facing-yaw-restart-survival-propagated-handoff.md`.

Static owner facing/yaw is now promoted, restart-survived, and propagated into tracked current truth. Current target identity is PID `12664`, HWND `0x205146C`, process start `2026-06-01T17:19:45.159353Z`, module base `0x7FF6EE5D0000`.

| Resolver | Chain / result |
|---|---|
| Coordinate | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`; current readback passed at `2026-06-01T17:23:08.352942+00:00`. |
| Facing/yaw | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314`; restart survival packet passed; current yaw `41.29403500816383°`. |
| API-now | Current PID `12664` chain/API max abs delta `0.00248046875003638` <= `0.25`. |
| Current truth | `docs\recovery\current-truth.json` updated at `2026-06-01T17:33:38Z`. |
| Strong docs | `docs\recovery\static-owner-facing-yaw-restart-survival-2026-06-01.md`; `docs\workflow\static-owner-facing-yaw-discovery-workflow.md`. |

Safety: this propagation sent no live input/movement, did not attach x64dbg/Cheat Engine, did not write provider repos, did not write target memory, and did not perform a new proof/facing/actor promotion. It applied tracked current truth only after the already-promoted facing/yaw chain survived restart.

Current safe next action: use the promoted static owner coordinate and facing/yaw resolvers after exact PID/HWND/process-start/module-base preflight. Keep turn-rate/support fields, actor/stat chains, proof anchors, and autonomous route-control automation separate.

## Latest compact handoff — window-tool audit classification + fresh pre-promotion readbacks — 2026-06-01 08:00 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-01-0800-window-tool-audit-readback-refresh-handoff.md`.

Safe continuation after the 07:48 handoff is pushed through HEAD `e2d8a09`
(`Classify repo window tool in input audit`). The live-input surface audit now
classifies `tools\RiftReader.WindowTools\Program.cs` as a repo-owned
window/control primitive with explicit target gates instead of leaving it under
a generic legacy-review bucket. Exact-target no-input readbacks and the
report-only candidate-facing readiness review were also refreshed.

Current target identity remains PID `41808`, HWND `0x2B0A26`, process start
`2026-06-01T01:50:50.903773Z`, module base `0x7FF6EE5D0000`. The promoted
coordinate chain remains `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`; the
candidate-facing chain remains `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` and
is still candidate-only.

Fresh evidence now indexed:

| Evidence | Status | Path |
|---|---|---|
| Static owner coordinate readback | `passed`; stationary; `x=7259.82568359375`, `y=821.4274291992188`, `z=2994.700439453125` | `scripts\captures\static-owner-coordinate-chain-readback-20260601-075735-998580\summary.json` |
| Static owner nav/facing readback | `passed`; candidate yaw `75.17711284220054` degrees; pitch `4.941137747009679` degrees | `scripts\captures\static-owner-nav-state-20260601-075736-800286\summary.json` |
| RRAPICOORD/API-now reference | `captured`; max abs chain-vs-API delta `0.004394406249957683` <= `0.25` | `scripts\captures\rift-api-reference-currentpid-41808-20260601-075737.json` |
| Candidate-facing readiness review | `passed`; review-ready; `promotionAllowed=false`; `promotionPerformed=false`; explicit promotion gate still required | `scripts\captures\facing-target-promotion-readiness-review-20260601-075836-835459\summary.json` |
| Navigation pointer dashboard | `passed`; freshness `fresh`; no stale sources; generated `2026-06-01T07:58:38Z` | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` |
| Compact workflow status | `passed`; clean Git at `e2d8a09`; generated `2026-06-01T07:58:39Z` | `.riftreader-local\workflow-status\20260601-075839Z\compact-sitrep.json` |

Safety: this continuation sent no live input/movement, did not attach
x64dbg/Cheat Engine, did not write provider repos, and did not perform
proof/facing/actor promotion. It read target memory only through approved
read-only static owner/API capture helpers. Git push was performed for the
coherent audit-hardening slice.

Current safe next action: the next meaningful progress is an explicit
candidate-facing promotion/proof gate. Before that gate, refresh exact-target
static coordinate, nav/facing, and RRAPICOORD/API-now readbacks again and verify
PID/HWND/process-start/module-base. `keep working` alone is not approval to
cross that promotion/proof boundary.

## Latest compact handoff — Ghidra evidence surfaced + no-input truth refresh — 2026-06-01 07:48 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-01-0748-ghidra-evidence-current-truth-refresh-handoff.md`.

Safe local continuation after the 06:53 handoff is pushed through HEAD
`caaedaa` (`Refresh current truth from no-input readbacks`). Ghidra static
evidence is now visible in the navigation dashboard, compact workflow status,
and compact decision packet, and tracked `docs\recovery\current-truth.json` has
been refreshed from fresh no-input current-PID readbacks/API-now evidence.

Current target identity remains PID `41808`, HWND `0x2B0A26`, process start
`2026-06-01T01:50:50.903773Z`, module base `0x7FF6EE5D0000`. The promoted
coordinate chain remains `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`.

Fresh evidence now indexed:

| Evidence | Status | Path |
|---|---|---|
| Static owner coordinate readback | `passed`; stationary; `x=7259.82568359375`, `y=821.4274291992188`, `z=2994.700439453125` | `scripts\captures\static-owner-coordinate-chain-readback-20260601-074133-448811\summary.json` |
| Static owner nav/facing readback | `passed`; candidate yaw `75.17711284220054` degrees; pitch `4.941137747009679` degrees | `scripts\captures\static-owner-nav-state-20260601-074144-187124\summary.json` |
| RRAPICOORD/API-now reference | `passed`; max abs chain-vs-API delta `0.004394406249957683` <= `0.25` | `scripts\captures\rift-api-reference-currentpid-41808-20260601-074156.json` |
| Offline Ghidra static evidence | `passed`; `200` root refs; `8057130` instructions scanned; warning `ghidra-analysis-timeout-project-saved` | `scripts\captures\ghidra-static-analysis-20260601-071020\summary.json` |
| Navigation pointer dashboard | `passed`; freshness `fresh`; no stale sources | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` |
| Compact workflow status | `passed`; clean Git at `caaedaa` | `.riftreader-local\workflow-status\20260601-074448Z\compact-sitrep.json` |

Safety: this continuation sent no live input/movement, did not attach
x64dbg/Cheat Engine, did not write provider repos, and did not perform
proof/facing/actor promotion. It did read target memory through approved
read-only static owner/API capture helpers and applied tracked current truth
only through the explicit refresh helper.

Current safe next action: if pursuing facing promotion, refresh exact-target
static/nav/API readbacks again immediately before the gate, then run a separate
explicit promotion gate. `keep working` alone is not approval to cross that
promotion/proof boundary.

## Latest compact handoff — fresh current-truth refresh + facing review — 2026-06-01 06:53 UTC

A new compact handoff exists at
`docs\handoffs\2026-06-01-0653-current-truth-refresh-facing-review-handoff.md`.

Tracked `docs\recovery\current-truth.json` has been refreshed again from the
06:50 dry-run plan and fresh no-input current-PID evidence. The apply summary is
`.riftreader-local\current-truth-refresh-apply\latest\summary.json`, and the
navigation dashboard was regenerated at `2026-06-01T06:53:05Z` with all indexed
sources fresh.

Current target identity remains PID `41808`, HWND `0x2B0A26`, process start
`2026-06-01T01:50:50.903773Z`, module base `0x7FF6EE5D0000`. The promoted
coordinate chain remains `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`.

Fresh evidence now indexed:

| Evidence | Status | Path |
|---|---|---|
| Static owner coordinate readback | `passed`; stationary; `x=7259.82568359375`, `y=821.4274291992188`, `z=2994.700439453125` | `scripts\captures\static-owner-coordinate-chain-readback-20260601-064834-659174\summary.json` |
| Static owner nav/facing readback | `passed`; candidate yaw `75.17711284220054` degrees; pitch `4.941137747009679` degrees | `scripts\captures\static-owner-nav-state-20260601-064844-619041\summary.json` |
| RRAPICOORD/API-now reference | `passed`; max abs chain-vs-API delta `0.004416406250129512` <= `0.25` | `scripts\captures\rift-api-reference-currentpid-41808-20260601-064857.json` |
| Candidate-facing review packet | `passed`; review-ready but promotion still blocked behind explicit gate | `scripts\captures\facing-target-promotion-readiness-review-20260601-064955-374586\summary.json` |
| Navigation pointer dashboard | `passed`; freshness `fresh`; no stale sources | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` |

Safety: this slice applied tracked current truth only. It sent no new live
input/movement, did not attach x64dbg/Cheat Engine, did not write provider repos,
and did not perform proof/facing/actor promotion.

Current safe next action: if pursuing facing promotion, refresh exact-target
static/nav/API readbacks again immediately before the gate, then run a separate
explicit promotion gate. The review packet alone is still report-only and must
not be treated as promotion.

## Latest compact handoff — candidate-facing promotion-readiness review — 2026-06-01 06:44 UTC

A new compact handoff exists at
`docs/handoffs/2026-06-01-0644-facing-promotion-readiness-review-handoff.md`.

The report-only review packet now exists at
`scripts\captures\facing-target-promotion-readiness-review-20260601-063743-001453\summary.json`.
It passed with verdict
`candidate-facing-review-ready-for-explicit-promotion-gate`, but still records
`promotionAllowed=false`, `promotionPerformed=false`,
`explicitPromotionGateRequired=true`, and
`freshPrePromotionReadbackRequired=true`.

New workflow surfaces:

| Surface | Status |
|---|---|
| `scripts\riftreader-facing-target-promotion-readiness-review.cmd` | report-only review of existing gate/static evidence; no promotion |
| Compact workflow status | now surfaces `facingPromotionReadinessReview` and shifts next action to fresh exact-target readbacks |
| Tool catalog / bridge commands | now lists the review helper as safe-read-only |

Current safe next action: refresh exact-target static/nav/API readbacks before
any promotion gate. Do **not** promote facing/turn-rate/actor truth from the
review packet alone.
## Latest compact handoff — current-truth apply and gate-aware status wiring — 2026-06-01 06:17 UTC

A new compact handoff exists at
`docs/handoffs/2026-06-01-0617-current-truth-apply-status-wiring-handoff.md`.

Tracked `docs/recovery/current-truth.json` has now been applied from the
validated dry-run proposal under
`.riftreader-local\current-truth-refresh-plan\latest\`. The apply summary is
`.riftreader-local\current-truth-refresh-apply\latest\summary.json`, with a
backup at
`.riftreader-local\current-truth-refresh-apply\latest\current-truth-before-apply.json`.

Current target identity remains PID `41808`, HWND `0x2B0A26`, process start
`2026-06-01T01:50:50.903773Z`, module base `0x7FF6EE5D0000`. The promoted
coordinate chain remains `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`, and the
latest applied API-now vs chain-now max abs delta is
`0.004416406250129512` <= tolerance `0.25`.

New workflow surfaces:

| Surface | Status |
|---|---|
| `scripts\riftreader-current-truth-refresh-apply.cmd` | explicit dry-run/apply gate; no proof/facing/actor promotion |
| Navigation pointer discovery | now indexes three-pose gate, restart survival, and turn-forward proof |
| Compact workflow status | now surfaces `currentTruthRefreshApply` and gate-aware next action |
| Tool catalog / bridge commands | now lists apply and report-only facing gate helpers |

Gate readiness is packaged but still candidate-only:

| Gate | Status | Evidence |
|---|---|---|
| Three-pose route-progress gate | `passed` | `scripts\captures\facing-target-three-pose-gate-20260601-054258-066521\summary.json` |
| Restart/relog survival packet | `passed` | `scripts\captures\facing-target-restart-survival-packet-20260601-054826-920485\summary.json` |
| Turn-forward progress proof | `passed` | `scripts\captures\static-owner-turn-forward-experiment-20260601-054700-011212\summary.json` |

Current safe next action: build a separate candidate-facing promotion-readiness
review packet from these gates and static-root/source-site evidence; do not
promote facing/turn-rate chains automatically.

## Latest compact handoff — facing-target gates and live proof refresh — 2026-06-01 05:51 UTC

A new compact handoff exists at
`docs/handoffs/2026-06-01-0551-facing-target-gates-live-proof-handoff.md`.

Current target identity and tracked truth remain PID `41808`, HWND `0x2B0A26`,
process start
`2026-06-01T01:50:50.903773Z`, module base `0x7FF6EE5D0000`. The promoted
coordinate chain remains `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`.

Latest post-proof API-now vs chain-now passed from
`scripts\captures\rift-api-reference-currentpid-41808-20260601-054745.json`
against
`scripts\captures\static-owner-coordinate-chain-readback-20260601-054735-005823\summary.json`
with max abs delta `0.004416406250129512` <= tolerance `0.25`.

Newest gate packets:

| Packet | Status | Path |
|---|---|---|
| Camera/yaw multipose aggregate | `passed`, route-actionable pose count `2` | `scripts\captures\static-owner-camera-yaw-multipose-report-20260601-052037-685312\summary.json` |
| Three-pose route-progress gate | `passed` | `scripts\captures\facing-target-three-pose-gate-20260601-054258-066521\summary.json` |
| Current PID turn-forward proof | `passed`, route progress `1.5254744940722471` | `scripts\captures\static-owner-turn-forward-experiment-20260601-054700-011212\summary.json` |
| Restart/relog survival packet | `passed`, distinct process epochs and stable offsets | `scripts\captures\facing-target-restart-survival-packet-20260601-054826-920485\summary.json` |

Current state: `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` is still the closest
facing-target candidate and remains **candidate-only** for truth/promotion. The
new Ghidra review note is
`docs/recovery/ghidra-facing-coordinate-source-site-review-2026-06-01.md`.

Main blocker at the 05:51 handoff was a separate proof/promotion review artifact to consume
the three-pose gate, live turn-forward proof, restart/relog packet, and Ghidra
source-site review. Tracked current truth was not updated in that 05:51 slice; this is superseded by the 06:17 apply section above.

## Ghidra offline-static lane reintroduced as a default discovery step — 2026-06-01

Treat Ghidra as a first-class reverse-engineering platform — decompiler, xrefs,
control-flow/data-flow, writer-site discovery, and type/structure recovery —
not as a simple reader. Use it before another live/debugger/proof escalation
when reviewing pointer-chain candidates, owner-layout semantics, or
restart-survival failures. The safe planner command is:

```powershell
cmd /c scripts\riftreader-ghidra-static-evidence.cmd --plan --json
```

To run the actual offline import/xref/writer evidence extractor, pass the local
RIFT binary explicitly:

```powershell
cmd /c scripts\riftreader-ghidra-static-evidence.cmd --run --binary-path "C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe" --json
```

This lane is powerful but offline-only: it plans/runs against offline files and
does **not** attach to the live process, read/write target memory, send input,
write provider repos, update current truth, or promote candidates. Prioritize
decompiler/xref/writer analysis and layout semantics around
`rift_x64+0x32EBC80`, `owner+0x300/+0x304/+0x30C`,
`owner+0x320/+0x324/+0x328`, and `owner+0x438/+0x43C/+0x440`.

The helper intentionally writes Ghidra projects under ignored
`scripts\captures\ghidra-static-projects\project-*` instead of
`.riftreader-local`, because Ghidra rejects project path components beginning
with `.`. It also uses Windows short paths internally to avoid batch-file
breakage on paths containing spaces or parentheses.

Latest offline Ghidra evidence:
`docs/recovery/ghidra-static-pointer-evidence-2026-06-01.md`.
The first pass imported `rift_x64.exe`, scanned `5,162,625` instructions, and
captured 200 capped refs to `rift_x64+0x32EBC80` (`101` READ / `99` WRITE in the
cap). It also found the key same-owner write cluster at `0x14003FA33..0x14003FA75`
for `owner+0x304`, `owner+0x30C/+0x310/+0x314`, and
`owner+0x320/+0x324/+0x328`. This supports `0x30C` as owner-layout evidence, but
the restart zero-vector result still keeps it candidate-only/state-dependent.

## Current state

RIFT automated navigation is in **Phase 0 (correctness)**. Four of four
correctness blockers now have offline/code-level coverage; live route validation
and any strafe recovery execution remain explicitly gated.

| # | Blocker | Status |
|---|---|---|
| #1 | Static resolver freshness gate | ✅ Done — pre-movement readback gate in runner |
| #2 | Turn-aware route planning (atan2 + 0x304 cross-check) | ✅ Done — `turn_aware_route_plan.py` |
| #3 | Verified turn convergence (pulse-loop detector) | ⚠️ Historical coverage exists, but the latest 17:21 UTC same-target recheck did **not** produce static-owner yaw delta after chat focus was cleared; reacquire turn/yaw evidence before using turn control. |
| #4 | Strafe/drift detection | ✅ Done offline — route summaries classify stationary block/drift-back and emit advisory recovery plan |

**Pipeline architecture (only after fresh turn/yaw reacquisition passes):**
```
state readback → plan (bearing + 0x304) → turn (mouse-look pulse-loop verified) → forward (route step) → repeat
```

## Key files (start here)

| File | Purpose |
|---|---|
| `scripts/static_owner_continuous_route_runner.py` | Main loop: plan → turn → forward → repeat |
| `scripts/turn_completion_detector.py` | Pulse-loop turn convergence (Phase 0 #3) |
| `scripts/static_owner_mouse_turn_probe.py` | Exact-target right-mouse-look yaw probe/calibration |
| `scripts/static_owner_turn_input_probe.py` | Keyboard/backend input probe; use to rule out chat/UI focus swallowing keys |
| `scripts/static_owner_camera_yaw_classification.py` | Candidate-only visual camera vs static-owner yaw classifier with screenshots/raw diff and owner-window deltas |
| `scripts/static_owner_turn_aware_route_plan.py` | Bearing + 0x304 cross-check plan (Phase 0 #2) |
| `scripts/static_owner_nav_route_step.py` | Single forward step with pre/post state analysis |
| `scripts/nav_state_readback.py` | Read yaw, turn rate, facing from promoted static chain |
| `scripts/capture_root_signature.py` | Capture AOB signatures for game-update resilience |
| `scripts/riftreader-tool-catalog.cmd` | Safe tool catalog and Ghidra static-lane planner |
| `scripts/riftreader-ghidra-static-evidence.cmd` | Runs/plans offline Ghidra import plus pointer evidence extraction with Windows path fixups |
| `tools/riftreader_workflow/tool_catalog.py` | Ghidra/offline-static priority, target offsets, and safety metadata |
| `tools/riftreader_workflow/ghidra_static_evidence.py` | Python orchestrator for Ghidra headless runs and summary artifacts |
| `tools/riftreader_workflow/ghidra_scripts/RiftReaderPointerEvidence.java` | Ghidra script extracting root refs, owner-offset hits, and decompiler snippets |
| `tools/riftreader_workflow/decision_packet.py` | Safe next-action routing; candidate-only actor/navigation evidence now surfaces Ghidra first |
| `docs/workflows/README.md` | Master decision tree (8 scenarios) |
| `docs/workflows/session-startup.md` | "I just logged in, what now?" |

## Promoted static resolver (current truth)

All reads use the promoted static pointer chain at `rift_x64.exe+0x32EBC80`:

| Field | Offset | Notes |
|---|---|---|
| Player X/Y/Z | +0x320/+0x324/+0x328 | 2 ReadProcessMemory calls |
| Facing target | +0x30C/+0x310/+0x314 | Same owner, 20 bytes before coords |
| Turn rate | +0x304 | float, positive=left, negative=right |
| Yaw formula | `atan2(Z@0x314 - PZ, X@0x30C - PX)` | Read both chains in same cycle |

**AOB signature** for game-update resilience: `B5 01 00 00 ?? ?? ?? ??` (stored in `signatures/rift_x64/root_root-player-owner.json`)

## Recent commits (newest 10 before this slice)

| Commit | What |
|---|---|
| `dfc7a65` | Document blocked turn-yaw recheck |
| `142deab` | Record approved bounded route validation |
| `a19e1a6` | Refresh current truth from no-input readback |
| `caeca92` | Refresh handoff with truth plan status |
| `059832a` | Surface truth refresh plan in workflow status |
| `b5fb8f5` | Refresh handoff with truth refresh plan |
| `f5f8bc2` | Document current truth refresh plan |
| `a539850` | Add current truth refresh plan helper |
| `16f9323` | Document navigation pointer status workflow |
| `c6fad32` | Refresh handoff with navigation discovery status |

## Latest live finding — 2026-05-31

| Finding | Evidence |
|---|---|
| Forward movement still works through exact PID/HWND SendInput | `static-owner-nav-route-step-20260531-110018-508811` reduced distance from `5.00m` to `3.50m`. |
| Turn detector now exact-targets SendInput instead of title-only matching | `turn-completion-detector-20260531-110947-987388` child pulses all used PID `25668` / HWND `0x320CB0`. |
| Chat input focus can swallow movement/turn keys and mimic terrain blockage | Screenshot `tools/rift-game-mcp/.runtime/screenshots/capture-20260531-075721-244.png` showed chat active with typed probe characters after route/key tests. Treat no-progress results as input-focus suspect until ruled out. |
| Exact-target Escape cleared chat focus | After focus/capture, `escape` produced screenshot `tools/rift-game-mcp/.runtime/screenshots/capture-20260531-075808-939.png` with chat closed. Escape is not idempotent; only send it when chat/menu focus is visually confirmed. |
| Keyboard input works once chat focus is cleared | `static-owner-turn-input-probe-20260531-115821-551526` showed `w` planar movement `2.90m`, `s` `1.45m`, `a` yaw delta `79.06°`, and `d` yaw delta `81.88°`. |
| Mouse-look turns are live-valid | `static-owner-mouse-turn-probe-20260531-113550-179711` validated 6/6 exact-target mouse-look attempts: 40px ≈ `5.65°` left / `7.06°` right, 80px ≈ `16.94°`, 160px ≈ `50–52°`, with zero coordinate drift. |
| Turn completion detector now supports `--turn-backend mouse-look` | `turn-completion-detector-20260531-114052-609533` converged a +15° right turn in 2 mouse pulses: yaw `62.47° → 76.59°`, final error `0.88°`. |
| Continuous route loop can execute mouse turns; earlier forward no-progress was not confirmed terrain | `static-owner-continuous-route-20260531-114251-242356` and `static-owner-continuous-route-20260531-114509-094476` both completed mouse-look turns while chat was likely active, then classified forward `W` as `blocked-stationary-no-movement`. Treat as chat/UI-focus suspect until ruled out. |
| Mouse arc recovery succeeds after chat focus is cleared | `static-owner-mouse-arc-recovery-20260531-115937-707432` passed on offset `0.0°`: planar movement `2.90m`, destination distance `2.55m → 0.40m`, progress `2.15m`. |
| Continuous route loop passes with chat focus ruled out | `static-owner-continuous-route-20260531-121254-529672` routed to an ahead-4m destination with no chat input active: initial distance `4.00m`, progress `3.73m`, arrived in 1 forward step, no blockers. |
| Defensive chat-focus preclear is now opt-in | `static_owner_nav_route_step.py`, `static_owner_continuous_route_runner.py`, and `static_owner_mouse_arc_recovery_probe.py` support `--clear-ui-focus-before-input`; it sends one exact-target Escape where applicable and records a warning because Escape is not idempotent. |
| No-progress reporting now keeps the focus hazard explicit | Route-step/route-loop no-progress paths warn that chat/UI focus is not ruled out before treating `blocked-stationary-no-movement` as terrain; recovery gates now include visual focus hygiene. |
| Mouse arc recovery is wired into route-loop recovery advice | `static_owner_continuous_route_runner.py` now emits `recoveryHelper` metadata pointing to `static_owner_mouse_arc_recovery_probe.py` with candidate-only notes and required live gates. |


## Fresh live verification — 2026-05-31 12:41–12:42 UTC

| Check | Evidence |
|---|---|
| Exact current PID static readback passed | `scripts\captures\static-owner-coordinate-chain-readback-20260531-124243-250543\summary.json`: PID `25668`, HWND `0x320CB0`, module base matched, coordinate `7262.338, 821.694, 3002.999`. |
| Exact current PID nav-state readback passed | `scripts\captures\static-owner-nav-state-20260531-124244-004288\summary.json`: yaw `85.06°`, no blockers. |
| Keyboard turn backend produced yaw delta | `scripts\captures\static-owner-turn-input-probe-20260531-124139-909597\summary.json`: key `a`, signed yaw delta `-12.71°`, zero coordinate drift. |
| Mouse-look turn backend produced yaw delta | `scripts\captures\static-owner-mouse-turn-probe-20260531-124158-803473\summary.json`: right 40px, signed yaw delta `+5.65°`, zero coordinate drift. |
| Turn completion detector converged with mouse-look | `scripts\captures\turn-completion-detector-20260531-124210-709153\summary.json`: +10° signed target, 1 pulse, final error `2.94°`. |
| Bounded movement probe passed | `scripts\captures\static-owner-mouse-arc-recovery-20260531-124230-635784\summary.json`: offset `0°`, 300ms `W`, planar movement `1.82m`, no blockers. |

## Pointer-chain discovery refresh — 2026-05-31 14:19–14:23 UTC

| Check | Evidence |
|---|---|
| Exact target reacquired | PID `25668`, HWND `0x320CB0`, module base `0x7FF6EE5D0000`, owner `0x1B53D7806A0`. |
| Baseline static-owner snapshot | `scripts\captures\static-owner-facing-snapshot-baseline-20260531-20260531-141907-660274\summary.json` |
| Mouse-look right yaw stimulus | `scripts\captures\static-owner-mouse-turn-probe-20260531-141920-662365\summary.json`: right `160px`, yaw delta `+49.410772°`, planar drift `0.0`. |
| Mouse-look left yaw stimulus | `scripts\captures\static-owner-mouse-turn-probe-20260531-141934-149919\summary.json`: left `320px`, yaw delta `-111.529978°`, planar drift `0.0`. |
| Facing comparison | `scripts\captures\static-owner-facing-comparison-20260531-141949-380215\summary.json`: top relative target `owner+0x30C/+0x310/+0x314`, yaw deltas `+49.410772°` and `-62.119206°` from baseline, coordinate drift `0.0`. |
| Pointer neighborhood | `scripts\captures\pointer-owner-neighborhood-inspector-20260531-142006-017134\summary.json`: read-only owner neighborhood passed; heap-near-target references only, no promotion. |
| Memory-region scan plan | `scripts\captures\memory-region-inventory-currentpid-25668-20260531-142058-445123\scan-plan.json` |
| Bounded movement-family snapshot | `scripts\captures\family-snapshot-sequence-currentpid-25668-20260531-142159-332736\summary.json`: exact-target `W` 350ms, movement/input sent, no CE/x64dbg/provider writes. |
| Current coordinate candidate reacquired | Delta summary `scripts\captures\family-snapshot-sequence-currentpid-25668-20260531-142159-332736\delta-analysis\delta-summary.json`: best candidate `0x1B53D7809C0` / owner+`0x320`, tracking max abs `0.006398926`, API planar `2.267577m`, memory planar `2.269441m`. |
| Post-run static readback | `scripts\captures\static-owner-coordinate-chain-readback-20260531-142312-924000\summary.json`: coordinate `7264.431641, 821.697205, 3003.875732`, stationary, no blockers. |
| Post-run nav-state readback | `scripts\captures\static-owner-nav-state-20260531-142312-943158\summary.json`: yaw `22.940854°`, pitch `-4.941195°`, turn rate `1.171186`, no blockers. |

Outcome: current coordinate/facing pointer-chain evidence is reacquired for PID `25668`; `docs\recovery\current-truth.*` now records the fresh current API-now validation. No new actor/stat chain or proof promotion was performed.

## Safe-local dashboard/status refresh — 2026-05-31 15:19 UTC

| Check | Evidence |
|---|---|
| Compact workflow status now embeds navigation pointer discovery | Commit `6f9dcc7`; `cmd /c scripts\riftreader-workflow-status.cmd --compact-json` includes `navigationPointerDiscovery` with promoted coordinate, candidate facing target, candidate turn rate, coordinate-delta evidence, freshness, next action, and safety flags. |
| Exact target no-input coordinate readback refreshed | `scripts\captures\static-owner-coordinate-chain-readback-20260531-151942-201598\summary.json`: PID `25668`, HWND `0x320CB0`, owner `0x1B53D7806A0`, coordinate readback fresh. |
| Exact target no-input nav-state readback refreshed | `scripts\captures\static-owner-nav-state-20260531-151943-009442\summary.json`: yaw `22.940854°`, pitch `-4.941195°`, turn rate `1.171186`, no input/movement/debugger/provider writes. |
| Dashboard regenerated | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` generated `2026-05-31T15:19:44Z`; status `passed`, freshness `stale` only because tracked `currentTruth` is older than the local readbacks. |
| Validation ledger recorded reacquisition timing | `.riftreader-local\validation-runs\20260531-151941-457745\summary.md`: coordinate readback `0.777s`, nav readback `0.779s`, dashboard regen `0.773s`, overall passed. |

Current safe next action: keep using the dashboard/status packet for resume context. Do **not** promote facing/turn-rate chains or rewrite current truth unless a deliberate proof/truth-refresh gate is opened.

## Current-truth refresh dry-run plan — 2026-05-31 15:38 UTC

| Check | Evidence |
|---|---|
| Dry-run planner added | `scripts\riftreader-current-truth-refresh-plan.cmd --json --write` calls Python helper `tools\riftreader_workflow\current_truth_refresh_plan.py`. |
| Compact workflow status now embeds the plan | Commit `059832a`; `cmd /c scripts\riftreader-workflow-status.cmd --compact-json` includes `currentTruthRefreshPlan` with status, update count, proposed artifacts, safety flags, and the explicit apply gate. |
| Ignored proposal generated | `.riftreader-local\current-truth-refresh-plan\latest\summary.json`, `proposed-current-truth.json`, and `proposed-current-truth.diff`. |
| Planner result | Status `passed`, `updateCount=9`; it proposes refreshing static-chain readback timestamps/coordinate fields only and keeps API-now/proof/promotion boundaries explicit. |
| Safety boundary | `trackedTruthWritten=false`, `movementSent=false`, `inputSent=false`, `targetMemoryBytesRead=false`, `proofPromotion=false`, `facingPromotion=false`, `gitMutation=false`. |
| Notable warning | Current tracked truth already contains historical `staticOwnerFacing` promotion metadata while the latest dashboard keeps facing as candidate-only context; the plan does not change that field. |
| Validation ledger | `.riftreader-local\validation-runs\20260531-153915-784379\summary.md` and `.riftreader-local\validation-runs\20260531-153917-915814\summary.md` passed. |

Current safe next action: review the ignored proposal artifacts. Applying any
tracked `docs\recovery\current-truth.json` update remains a separate explicit
truth-refresh gate; the dry-run plan is not proof promotion.


## Current-truth refresh apply — 2026-05-31 16:08 UTC

| Check | Evidence |
|---|---|
| No-input coordinate readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260531-160614-677227\summary.json` passed for PID `25668` / HWND `0x320CB0` at `2026-05-31T16:06:14.677913+00:00`. |
| No-input nav-state readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-state-20260531-160615-484864\summary.json` passed; yaw `22.940854°`, turn-rate sample `1.171186`. |
| Dashboard regenerated | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` generated `2026-05-31T16:06:16Z`; current truth was the only stale dashboard source afterward. |
| Planner hardened | `tools\riftreader_workflow\current_truth_refresh_plan.py` now carries latest coordinate/nav-state artifact paths into the proposed tracked truth, not just timestamps. |
| Tracked truth applied | `docs\recovery\current-truth.json` and `docs\recovery\current-truth.md` updated from the reviewed dry-run proposal (`updateCount=13`). |
| Boundary | API-now remains the prior 2026-05-31 bounded family validation ending `2026-05-31T14:22:57Z`; no movement/input, proof promotion, actor-chain promotion, or facing/turn-rate promotion was performed by this refresh. |

Current safe next action: run targeted/full validation for this tracked-truth slice, then push only after the explicit repo-publish gate is satisfied. Live route reruns still require explicit `--turn-approved`, `--movement-approved`, and `--allow-candidate-turn-control` approval with a destination.


## Approved bounded route-loop validation and truth refresh — 2026-05-31 16:37 UTC

| Check | Evidence |
|---|---|
| Live route loop passed | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-continuous-route-20260531-163708-174984\summary.json`: one approved ahead-3m destination, `route-loop-arrived`, initial distance `2.999636m`, progress `2.642985m`, final distance `0.356651m`, one forward step. |
| Gates used | User approved `--turn-approved --movement-approved --allow-candidate-turn-control`; route used mouse-look backend but `turnsExecuted=0` because bearing was already aligned. |
| Visual verification | Baseline `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260531-123659-264.png`, frame-change `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260531-123721-931.png`, final `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260531-123728-957.png`. |
| Post-route readback | Static `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260531-163749-157934\summary.json` and nav-state `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-state-20260531-163749-964534\summary.json` passed for PID `25668` / HWND `0x320CB0`. |
| Post-route API-now | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-25668-20260531-163751.json` matched static readback within max abs delta `0.003437500`. |
| Dashboard/planner fix | `tools/riftreader_workflow/navigation_pointer_discovery.py` now prefers latest readback coordinates over tracked stale truth; `current_truth_refresh_plan.py` carries stale best-candidate, movement-gate, latest-static-readback, and facing current-reacquisition fields. |
| Tracked truth/docs | `docs/recovery/current-truth.json` and `.md` updated from reviewed dry-run evidence plus post-route API-now; `docs/HANDOFF.md` records this resume point. |
| Boundary | Movement/input were sent only by the approved route loop. No Cheat Engine, x64dbg attach, provider writes, target memory writes, proof promotion, actor-chain promotion, or facing/turn-rate promotion. |

Current safe next action: use this as a bounded route-loop success baseline. For a larger route, refresh exact-target static/API-now evidence first, keep one destination/recovery mode at a time, and do not promote facing/turn-rate chains without their proof gates.

## Approved facing/turn-rate recheck — 2026-05-31 17:11–17:22 UTC

This slice used the user's explicit approval for bounded live input to advance
facing/turn-rate discovery. It is **candidate-only** and intentionally does not
promote facing, turn-rate, actor chains, or proof artifacts.

| Check | Evidence |
|---|---|
| Exact target rebound and captured | PID `25668`, HWND `0x320CB0`; visual preflight `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260531-132147-219.png`. |
| Fresh no-input coordinate readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260531-171111-287296\summary.json`: coordinate `7267.5234375, 821.6994018554688, 3005.181640625`, stationary. |
| Fresh no-input nav-state readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-state-20260531-171111-334276\summary.json`: yaw `22.962550464°`, pitch `-7.446817291°`; candidate-only. |
| Mouse-look proof pack blocked | `C:\RIFT MODDING\RiftReader\scripts\captures\facing-turnrate-proof-pack-20260531-171311-130557\summary.json`; `static-owner-mouse-turn-probe-20260531-171311-633040\summary.json` sent approved mouse input and frame changed, but static-owner yaw delta stayed `0.0°`. |
| Keyboard proof initially contaminated by chat focus | `C:\RIFT MODDING\RiftReader\scripts\captures\turn-input-discovery-proof-20260531\static-owner-turn-input-probe-20260531-171640-888917\summary.json`; screenshot `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260531-131832-868.png` showed typed probe keys in chat input. |
| Chat focus cleared | Exact-target `escape` produced `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260531-131930-205.png`; chat input was visually closed. |
| Keyboard proof rerun still blocked after focus clear | `C:\RIFT MODDING\RiftReader\scripts\captures\facing-turnrate-key-proof-pack-20260531-172158-665488\summary.json`; `d` ScanCode input was delivered to the exact foreground target, but pre/post static yaw stayed `22.962550464°` and coordinate drift stayed `0.0m`. |
| Post-input visual state changed | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260531-132212-776.png`; visual camera/scene changed, but the current static-owner yaw candidate did not change in memory readback. |
| Boundary | Mouse/keyboard/Escape input was sent under approval. No route movement was run after the turn-yaw blocker; no Cheat Engine, x64dbg attach, provider writes, target memory writes, proof promotion, actor-chain promotion, or facing/turn-rate promotion. |

Current safe next action: treat turn/yaw as **not currently reacquired** despite
historical success. Do not run a turn-dependent route until a fresh proof pack
shows same-target yaw delta. Next practical discovery is a no-promotion
camera-vs-avatar-yaw classification run: collect simultaneous visual captures,
static nav-state reads, and a small set of read-only owner-neighborhood fields
around `0x304/0x30C/0x310/0x314` after one approved turn/camera stimulus, then
compare for the field that actually changes in this client state.

## Approved camera/yaw classification — 2026-05-31 17:44 UTC

This slice used the user's explicit approval for one bounded exact-target
mouse-look stimulus. It adds `scripts\static_owner_camera_yaw_classification.py`
and a thin `scripts\static-owner-camera-yaw-classification.cmd` launcher so the
visual-vs-memory classification can be rerun without ad hoc orchestration. It is
candidate-only and performs no promotion.

| Check | Evidence |
|---|---|
| Helper added | `scripts\static_owner_camera_yaw_classification.py --self-test --json` passes offline; tool catalog/status surfaces list the guarded live helper. |
| Live classification | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-camera-yaw-classification-20260531-174422-894291\summary.json`: verdict `visual-changed-static-yaw-unchanged`. |
| Visual evidence | Baseline `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-camera-yaw-classification-20260531-174422-894291\visual-baseline\images\full-window.png`; post `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-camera-yaw-classification-20260531-174422-894291\visual-post\images\full-window.png`; raw diff changed `74.077341%` of pixels. |
| Static nav-state | Baseline and post static-owner yaw both `22.962550464°`; signed yaw delta `0.0°`; coordinate stayed `7267.5234375, 821.6994018554688, 3005.181640625`. |
| Owner-window deltas | Focus deltas changed at `owner+0x300` (`+58.1875`), `owner+0x304` (`-0.605028749`), and `owner+0x408` (`+0.003416061`); `owner+0x30C/+0x310/+0x314` and coordinates stayed unchanged in this run. |
| Pointer neighborhood | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-camera-yaw-classification-20260531-174422-894291\pointer-owner-neighborhood-post\summary.json` captured the post-stimulus owner-neighborhood read-only context. |
| Boundary | Input/mouse-look stimulus was sent under approval. No route movement, Cheat Engine, x64dbg attach, provider writes, target memory writes, proof promotion, actor-chain promotion, or facing/turn-rate promotion. |

Current safe next action: treat `owner+0x30C/+0x310/+0x314` as stale for the
current camera-turn state. Next discovery should investigate `owner+0x300` and
`owner+0x304` across a left/right/return stimulus set with visual captures
before any turn-dependent route work. `owner+0x304` changed with the visual
stimulus but is still candidate-only and not route-actionable.

## Safe local 1–10 continuation — 2026-05-31 23:47 UTC

This pass executed the safe parts of the recommended action list and stopped at
the live-input/push/promotion gates.

| Check | Evidence |
|---|---|
| Push decision | Branch was clean and `ahead 2`; no push was performed because remote mutation still requires explicit approval. |
| Local code commit | `5145e46` — report-only multi-pose aggregation mode. |
| No-input coordinate readback refreshed | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260531-234341-274277\summary.json`: coordinate `7261.361328125, 821.6102905273438, 3001.443115234375`, stationary, no blockers. |
| No-input nav-state refreshed | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-state-20260531-234342-003613\summary.json`: yaw `79.412343321°`, candidate-only, no blockers. |
| Decision packet refreshed after readbacks | Passed; navigation pointer discovery stale sources reduced to `currentTruth` only. |
| Report-only multi-pose mode added | `scripts\static_owner_camera_yaw_classification.py --aggregate-summary-json <summary.json> [...] --json` aggregates existing classification summaries without live input. |
| First report-only aggregate | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-camera-yaw-multipose-report-20260531-234724-167850\summary.json`: verdict `visual-changed-static-yaw-unchanged-across-poses`, source count `1`, route-actionable pose count `0`. |
| Tool catalog | Camera/yaw tool notes now document the report-only aggregate mode separately from the gated live stimulus mode. |
| Targeted validation ledger | `C:\RIFT MODDING\RiftReader\.riftreader-local\validation-runs\20260531-235122-118928\summary.md`: duration `33.850s`, 88 focused tests passed. |
| Boundary | No live input, route movement, x64dbg/Cheat Engine, provider writes, proof promotion, actor-chain promotion, or facing/turn-rate promotion. |

Current safe next action: collect the missing left/right/return camera-yaw
classification summaries only after explicit live stimulus approval, then rerun
the report-only aggregate mode to compare `owner+0x300/+0x304` directionality.

## Validation timing ledger — 2026-05-31 13:49 UTC

Future repair/testing lanes should use the timestamped validation ledger so long
test runs show UTC timestamps, durations, heartbeats, and durable logs.

| Check | Evidence |
|---|---|
| Full local validation passed | `.riftreader-local\validation-runs\20260531-134923-272027\summary.md` |
| Total duration | `367.943s` |
| Longest command | `unittest-discover` at `341.273s` |
| Slow-budget warnings | None; `unittest-discover` stayed under its `420s` warning budget. |
| Immediate smoke command | `python tools\riftreader_workflow\validation_ledger.py --tier smoke` |

## Decision tree

- **"I just logged in"** → `docs/workflows/session-startup.md`
- **"Game updated, resolver broken"** → `docs/workflows/pointer-chain-reacquisition.md`
- **"Turn isn't working"** → `scripts/turn_completion_detector.py --help`
- **"Navigation stuck"** → Check forward no-progress sub-classification in runner output
- **"Need to capture new signature"** → `python scripts/capture_root_signature.py --rva <hex> --label <name> --pid <pid> --json`

## Safety gates (all must be explicitly approved)

| Flag | Purpose |
|---|---|
| `--turn-approved` | Turn key input |
| `--movement-approved` | Forward movement input |
| `--allow-candidate-turn-control` | Candidate yaw-based turning |

## Quick commands

```powershell
# Read current player state (no input)
python scripts/nav_state_readback.py --use-current-truth --json

# Run full route loop to coordinates using the live-valid mouse-look turn backend
python scripts/static_owner_continuous_route_runner.py `
  --destination-x 7295 --destination-z 2945 `
  --turn-backend mouse-look --mouse-pixels-per-pulse 40 `
  --turn-approved --movement-approved --allow-candidate-turn-control --json

# Same route loop with one opt-in Escape preclear if chat/menu focus is visually confirmed
python scripts/static_owner_continuous_route_runner.py `
  --destination-x 7295 --destination-z 2945 `
  --turn-backend mouse-look --mouse-pixels-per-pulse 40 `
  --clear-ui-focus-before-input `
  --turn-approved --movement-approved --allow-candidate-turn-control --json

# Validate turn completion (standalone mouse-look)
python scripts/turn_completion_detector.py `
  --direction left --target-bearing-degrees 90 `
  --turn-backend mouse-look --mouse-pixels-per-pulse 40 --turn-approved --json

# Classify visual camera change vs static-owner yaw/facing fields (candidate-only; sends one approved mouse-look stimulus)
python scripts/static_owner_camera_yaw_classification.py `
  --direction right --pixels 120 --stimulus-approved --json

# Run all tests
python -m unittest discover -s scripts -p "test_*.py"

# Preferred timed validation smoke check
python tools\riftreader_workflow\validation_ledger.py --tier smoke

# Preferred timed full local validation before push
python tools\riftreader_workflow\validation_ledger.py --tier full-local
```

## Next steps (priority order)

1. **Run a left/right/return camera-yaw classification set** — latest run shows visual change plus `owner+0x300/+0x304` deltas but unchanged `owner+0x30C/+0x310/+0x314`.
2. **Investigate `owner+0x300` and `owner+0x304` semantics** — determine whether either is camera heading, transient turn rate, or another state value; keep candidate-only.
3. **Reacquire turn/yaw proof before turn-dependent routing** — current same-target proof attempts show visual scene change but no static-owner yaw delta.
4. **Route-loop rerun only after turn proof passes** — use visual preflight or the opt-in `--clear-ui-focus-before-input` flag only when focus is confirmed.
5. **Refresh route fixtures with blocked-turn and camera-yaw artifacts** — preserve historical success, chat-focus hazard, post-Escape blocked proof, camera/yaw classification, and route-loop pass separately.
6. **Phase 1: Combat bot** — target selection, combat state detection, ability rotation (see `docs/workflows/combat-bot-roadmap.md`) after movement/facing control is stable.
