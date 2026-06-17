# 2026-06-17 - Pre-Stage-38 proof refresh gate started

# **⚠️ BLOCKED-SAFE — STAGE 38 IS NOT ACTIVE**

This handoff records the safe pre-Stage-38 work completed before live RIFT
read-only tooling is considered. The local MCP/runtime side is current; the
remaining hard blocker is a fresh actual ChatGPT Web/Desktop observation for
the current 33-tool surface.

## Current truth

Snapshot refreshed after the local MCP runtime restart and artifact-freshness
fixes. Avoid using this handoff as a substitute for the commands below: rerun
`git --no-pager status --short --branch`,
`python tools\riftreader_workflow\mcp_server_status.py --json`, and
`python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_final_readiness_status --json`
before any Stage 38 approval packet.

| Area | Evidence |
|---|---|
| Git | Latest code-changing MCP readiness slice is pushed as `745683c1d7facb60410b6b40b38ba2318914427a` (`Clarify MCP artifact freshness blockers`). Handoff-only follow-up commits may move HEAD; always re-run `git --no-pager log -1 --oneline` before final decisions. |
| CI | `.NET build and test` and `RiftReader Policy` passed for `745683c1d7facb60410b6b40b38ba2318914427a`; re-check current-head CI after any later handoff/docs-only commit. |
| Runtime | `mcp_server_status.py --json` reports `status=running-current` for PID `134652`, full profile, source freshness passed, and 33/33 tools observed. |
| Tunnel | `get_tunnel_status` reported Cloudflared service running and public MCP initialize passed at `https://mcp.360madden.com/mcp`. |
| Tool surface | Source/runtime expected 33 tools; latest actual-client proof still records 20 tools. |
| Stale stdio counterpart detection | Added after this handoff started: local status now reports Codex/local stdio MCP adapter counterparts separately from the Cloudflare HTTP runtime. In this pass, stale stdio PIDs `97436` and `116596` explained why an actual callable `mcp__riftreader.health` surface still showed 20 tools while HTTP PID `53740` showed 33. Those exact stale stdio PIDs were then stopped after command-line verification. |
| Post-recovery runtime | HTTP runtime restarted through guarded exact-PID preflight. Current HTTP PID is `134652`; `mcp_server_status.py --json` observed 33/33 tools, `healthVersion=0.1.4`, source freshness passed, and `stdioCounterparts.status=not-running`. |
| Remaining client refresh | The stale callable `mcp__riftreader` stdio transport is now closed after stopping the old process. Refresh/restart the ChatGPT/Codex MCP app/client before using that stdio surface again. |
| Local trial readiness | Fresh artifact: `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260617T155223Z-trial-readiness.json`. |
| Public route plan | Refreshed artifact: `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260617T155406Z-manual-public-ip-plan.json`. |
| Proof template | Fresh final-33-tool template: `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-155237Z\proof-input.json`. |
| Final readiness | Still blocked: `phase2:not-ready` plus proof replay failures because the latest proof is 20-tool evidence, not 33-tool evidence. Artifact freshness is now classified correctly: readiness/proposal smoke artifacts are final-readiness requirements; expired public-session smoke artifacts are warning-only while `publicSessionStatus=passed`. |
| Stage 38 consideration gate | Local-only helper added after this handoff was first written: `scripts\riftreader-stage38-consideration.cmd --status --compact-json`. It does not add an MCP tool or start Stage 38; it summarizes runtime, route, final readiness, and explicit live-boundary approval before an approval packet can be drafted. |

## Root cause / blocker

| Blocker | Plain meaning | Owner |
|---|---|---|
| Actual-client proof mismatch | ChatGPT's latest saved proof saw only 20 tools. The MCP server now exposes 33 tools, so final readiness correctly refuses to trust the old proof. | Actual ChatGPT Web/Desktop operator proof refresh |

This is not an MCP-server-running problem right now: the local server and
Cloudflare route are running and current. The blocker is that the actual
ChatGPT client has not yet produced a fresh 33-tool observation.

There is also a second local-client hazard: Codex/local stdio MCP adapter
processes can remain alive after source/tool-surface changes. Those processes
are not the Cloudflare HTTP runtime, but they can make an actual callable tool
surface report an older tool count. Treat `stdioCounterparts.status=stale-running`
as a client-refresh/restart signal, not as proof that the HTTP route is wrong.
After stopping stale stdio PIDs, a `Transport closed` result from that same
client-side tool is expected until the client/app refreshes and starts a fresh
stdio server.

## Dependency sequence that must be established every time

This sequence is the guardrail against repeating the old mistake of assuming
"connector exists" or "some MCP process exists" means the real ChatGPT route is
ready.

| Step | Criterion | How to prove it | If it fails |
|---:|---|---|---|
| 1 | Saved connector config is not treated as runtime. | `get_mcp_runtime_status` reports `saved-connector-is-not-runtime`. | Start or restart the actual local backend; do not edit ChatGPT connector settings as a substitute. |
| 2 | Loopback listener exists. | `mcp_server_status.py --json` finds `127.0.0.1:8770` listening. | Start the MCP backend; final readiness cannot proceed. |
| 3 | Listener identity is correct. | Listener command line is `riftreader_chatgpt_mcp.py --serve`, not a legacy/foreign process. | Stop the wrong listener or choose a free port; do not record proof. |
| 4 | Tool profile is final/full. | Runtime classification says `toolProfile=full` and `fullProfileReady=true`. | Restart with `--tool-profile full`. |
| 5 | Loaded runtime surface matches source. | Runtime `list_tools`/health observes exactly 33 expected tools. | Treat as stale runtime or wrong server; restart before proof. |
| 6 | Runtime source is fresh. | `runtimeSourceFreshness.status=passed`; process started after adapter source mtimes. | Restart exact PID through preflight. |
| 7 | Stdio counterparts are not stale. | `stdioCounterparts.status=not-running` or non-stale. | Refresh/restart the client-side MCP app/server; stale stdio can keep a 20-tool callable surface alive. |
| 8 | Public route forwards to the current backend. | `get_tunnel_status` passes for `https://mcp.360madden.com/mcp`. | Fix/start Cloudflare tunnel; do not use local SDK proof as a substitute. |
| 9 | Actual ChatGPT client observes the same surface. | ChatGPT Web/Desktop reports 33 tools and schemas. | Refresh/reconnect ChatGPT MCP app; do not record final proof. |
| 10 | Recorded proof replays. | Filled template passes `--check-input`, then `--record`, then Phase 2/final readiness pass. | Keep Stage 38 inactive and resolve the proof mismatch. |
| 11 | Stage 38 consideration gate passes. | `scripts\riftreader-stage38-consideration.cmd --status --compact-json` reports `passed` only after runtime, route, final readiness, and explicit live-boundary approval are satisfied. | Treat `blocked` or `approval-required` as not ready; do not start Stage 38. |

## Commands run in this pre-Stage-38 pass

```cmd
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_mcp_runtime_status --json
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_tunnel_status --json
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_tool_surface_diff --json
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_actual_client_proof_status --json
scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json
scripts\riftreader-mcp-phase2.cmd --status --json
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_final_readiness_status --json
scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --json
scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host mcp.360madden.com --json
python tools\riftreader_workflow\mcp_server_status.py --skip-runtime-surface-check --json
python tools\riftreader_workflow\mcp_server_status.py --json
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_current_head_ci_status --json
scripts\riftreader-chatgpt-trial-recorder.cmd --check-input --input .riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-155237Z\proof-input.json --json
```

## Actual-client proof refresh packet

| Item | Value |
|---|---|
| ChatGPT Server URL | `https://mcp.360madden.com/mcp` |
| Auth | `No Authentication` |
| Expected profile | Full final proof surface |
| Expected tool count | `33` |
| First ChatGPT-side calls | `health`, `get_mcp_runtime_status`, `get_tool_surface_diff`, `get_tunnel_status`, `get_actual_client_proof_status` |
| Fillable proof input | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-155237Z\proof-input.json` |
| Read-only check command | `scripts\riftreader-chatgpt-trial-recorder.cmd --check-input --input .riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-155237Z\proof-input.json --json` |
| Record command after the file is filled with real ChatGPT observations | `scripts\riftreader-chatgpt-trial-recorder.cmd --record --input .riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-155237Z\proof-input.json --json` |

## Do not do these before Stage 38

| Do not | Why |
|---|---|
| Do not treat the saved ChatGPT app/connector entry as the running backend. | The saved entry is only configuration; it does not start the local MCP server or Cloudflared. |
| Do not treat a local/Codex stdio MCP counterpart as the Cloudflare HTTP runtime. | Stdio counterparts can be stale and can explain an old actual callable tool surface. |
| Do not substitute local `list_tools`, SDK validation, or tunnel initialize for actual-client proof. | Final readiness requires evidence from ChatGPT Web/Desktop. |
| Do not move into Stage 38 live RIFT read-only tooling yet. | Final readiness and explicit live-boundary approval are both still required. |
| Do not send RIFT input, attach CE/x64dbg, write provider repos, or promote proof/current truth. | These are separate hard gates. |

## Criteria before Stage 38 can even be considered

| # | Required evidence | Current state |
|---:|---|---|
| 1 | Git clean and synced with origin. | Passed at this handoff. |
| 2 | Current-head CI green. | Passed at this handoff. |
| 3 | Local MCP runtime is `running-current` and source-fresh. | Passed at this handoff. |
| 4 | Public Cloudflare named Tunnel route initializes at `https://mcp.360madden.com/mcp`. | Passed at this handoff. |
| 5 | Trial readiness/proposal smoke artifacts are fresh. | Passed at this handoff. |
| 6 | Actual ChatGPT Web/Desktop observes exactly 33 tools and output schemas. | **Blocked — latest proof is 20-tool evidence.** |
| 7 | Filled proof input passes `--check-input`. | **Blocked until actual ChatGPT facts are filled.** |
| 8 | Fresh proof is recorded and replay passes. | **Blocked until actual ChatGPT proof is recorded.** |
| 9 | `scripts\riftreader-mcp-phase2.cmd --status --json` passes. | **Blocked by proof replay.** |
| 10 | `get_final_readiness_status` passes. | **Blocked by Phase 2/proof replay.** |
| 11 | `scripts\riftreader-stage38-consideration.cmd --status --compact-json` passes. | **Blocked until runtime/route/final readiness pass and explicit live-boundary approval is supplied.** |

Only after all eleven items pass should the workflow draft a Stage 38 approval
packet. Stage 38 implementation still requires explicit live-boundary approval.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Refresh/reconnect the ChatGPT Web/Desktop MCP app for `https://mcp.360madden.com/mcp`. | Forces ChatGPT to rescan the current 33-tool surface. |
| 2 | From ChatGPT, call `get_mcp_runtime_status`. | Confirms the actual client sees the current local backend. |
| 3 | If ChatGPT/Codex callable tools still show 20 tools, refresh/restart that client-side MCP app/server before proof. | Clears stale stdio/app-surface cache before recording proof. |
| 4 | From ChatGPT, call `get_tool_surface_diff`. | Confirms source/runtime/client proof drift is visible from the client side. |
| 5 | From ChatGPT, confirm exactly 33 tools and output schemas. | This is the missing final-readiness fact. |
| 6 | From ChatGPT, run the harmless proposal/draft/review/dry-run proof flow. | Preserves the repo-write safety proof for the current tool surface. |
| 7 | Fill the fresh proof template with only the observed ChatGPT facts. | Avoids inventing proof and keeps replay trustworthy. |
| 8 | Run the proof `--check-input` command. | Catches missing booleans/IDs before recording. |
| 9 | Record the checked proof with `--record`. | Creates the replayable actual-client proof artifact. |
| 10 | Rerun Phase 2 and final readiness before drafting a Stage 38 approval packet. | Keeps live RIFT work separated from local MCP readiness. |
