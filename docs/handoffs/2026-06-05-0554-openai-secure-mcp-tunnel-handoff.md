# OpenAI Secure MCP Tunnel handoff - 2026-06-05 05:54 UTC

## Verdict

The RiftReader ChatGPT Web/Desktop MCP path has been shifted from
Cloudflare-first to **OpenAI Secure MCP Tunnel first**. Local-only adapter tests
remain the default, and Cloudflare quick tunnel is preserved only as deprecated
fallback/dev-only support.

No live RIFT input, movement, `/reloadui`, screenshot key, x64dbg/CE attach,
provider write, ChatGPT registration, public tunnel startup, Git mutation,
commit, or push was performed.

## Current state

| Surface | State |
|---|---|
| ChatGPT app display name | `rift-mcp` |
| Active local adapter | `tools/riftreader_workflow/riftreader_chatgpt_mcp.py` |
| Adapter service | `riftreader_chatgpt_mcp` |
| Tool surface | 10 allowlisted tools only |
| Recommended Web/Desktop path | OpenAI Secure MCP Tunnel |
| Local default | self-test / SDK validation / loopback transport smoke |
| Deprecated fallback | Cloudflare quick tunnel / `trycloudflare.com` |
| Current blocker | External tunnel setup remains gated: tunnel id, runtime API key, `tunnel-client init/doctor/run`, ChatGPT connector registration, and fresh actual-client proof. |
| Installed tunnel-client | `C:\RIFT MODDING\Tools\OpenAI\tunnel-client\tunnel-client.exe`, version `0.0.9+62b9b42f698ec5319d2115e0c0ff1dcf6557d7ae`. |
| Latest local diagnostics slice | `b9a8341 Verify tunnel-client binary diagnostics` adds SHA256 plus `--version` behavior checks before the Secure Tunnel plan/final dependency gate can pass. |

## Latest continuation - 2026-06-05 07:20 UTC

The Secure Tunnel path now fails closed on a corrupt, missing, or non-executable
`tunnel-client` binary instead of treating file presence as enough evidence.

| Evidence | Result |
|---|---|
| Secure Tunnel plan | Passed and wrote `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T071455Z-secure-tunnel-plan.json`. |
| Binary SHA256 | `6cf9b0ba8f01a661bb040cbf5223c725beef51e3aa6fe6ebe08fb9d364f8334a`. |
| Binary version probe | `tunnel-client --version` exited `0` and printed `0.0.9+62b9b42f698ec5319d2115e0c0ff1dcf6557d7ae`. |
| Wrapper check | `cmd /v:on /c "scripts\riftreader-chatgpt-mcp.cmd --secure-tunnel-plan --json > NUL & echo LAST=!ERRORLEVEL!"` printed `LAST=0`. |
| Final readiness | `dependencyStatus=passed`, `requiredDependencies.tunnel-client=passed`; still blocked on unpushed/current-head CI and stale actual-client proof. |
| Phase 2 status | Still blocked on missing current-head CI for `.NET build and test` and `RiftReader Policy`; proof replay passes but proof freshness is stale. |
| GitHub Actions read-only check | Latest remote CI is for `46bbd33`; local Secure Tunnel commits are not pushed, so remote CI cannot cover current HEAD yet. |
| Validation ledger | `.riftreader-local\validation-runs\20260605-071641-190166\summary.md`, targeted unittest suite passed in `7.779s`. |
| Pre-commit | `pre-commit run --all-files --show-diff-on-failure` passed all configured hooks. |

No tunnel profile was initialized, no `tunnel-client run` was started, no
credential was created or stored, no ChatGPT connector registration was
performed, and no live RIFT/proof/debugger/provider action was attempted.

## Latest continuation - 2026-06-05 07:29 UTC

The compact final-readiness and Mission Control surfaces now expose the Secure
Tunnel binary diagnostic result directly. This keeps CI/operator logs
actionable without requiring the full dependency payload.

| Evidence | Result |
|---|---|
| Compact final status | New `secureTunnelClient` object reports status, path, SHA256, binary diagnostic status, `--version` exit code, and version text. |
| Mission Control summary | `Secure Tunnel client: passed / diagnostics passed` appears under Final readiness. |
| Focused tests | `python -m unittest scripts.test_mcp_final_readiness scripts.test_mcp_mission_control` passed 28 tests in `2.628s`. |
| Targeted MCP suite | `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_mcp_final_readiness scripts.test_mcp_mission_control scripts.test_mcp_workflow_state` passed 76 tests in `7.145s`. |

No public tunnel, ChatGPT registration, credential write, live RIFT/proof
action, provider write, debugger attach, or Git push was performed.

## Latest continuation - 2026-06-05 07:37 UTC

The Secure Tunnel plan now includes a credential-leak guard before writing the
plan artifact.

| Evidence | Result |
|---|---|
| Tunnel id validation | `--secure-tunnel-id` must be a `tunnel_...` value; malformed values are redacted and block the plan. |
| Accidental API-key guard | Secret-looking values passed as `--secure-tunnel-id` are redacted, replaced with the placeholder, and produce `secure-tunnel-id-looks-like-secret`. |
| Secret leak check | Generated plan artifacts include `secretLeakCheck`; the normal local plan reports `secretLeakCheck.status=passed`. |
| Wrapper fail-closed check | Passing a dummy secret-shaped value to `--secure-tunnel-id` returned `LAST=2`. |
| Focused adapter tests | `python -m unittest scripts.test_riftreader_chatgpt_mcp` passed 46 tests in `4.995s`. |

No real credential was passed or stored, and the plan helper still does not run
`tunnel-client init`, `doctor`, or `run`.

## Latest continuation - 2026-06-05 08:03 UTC

The ChatGPT Web/Desktop MCP surface now supports a 9th read-only tool,
`get_workflow_control_plan`, so ChatGPT can inspect the safe repo-control plan
without receiving shell, Git, tunnel, live RIFT, CE, x64dbg, or provider-write
authority.

| Evidence | Result |
|---|---|
| New tool | `get_workflow_control_plan` returns Mission Control state, safe commit-plan guidance, bidirectional data-transfer steps, and gated boundaries. |
| Tool surface | Approved surface is now 9 tools. |
| Local call smoke | `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_workflow_control_plan --json` passed. |
| Trial readiness | `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --trial-readiness --json` passed with 9-tool SDK validation and 9-tool proposal transport smoke. |
| New readiness artifact | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T080228Z-trial-readiness.json`. |
| New proposal smoke artifact | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T080228Z-proposal-transport-smoke.json`. |
| Final gate reconciliation | `toolSurfaceStatus=passed`; old actual-client proof now blocks with `tool-count-not-9:8` until a fresh 9-tool ChatGPT proof is recorded. |

No shell endpoint, Git mutation endpoint, tunnel-control endpoint, ChatGPT
registration, public tunnel, live RIFT action, provider write, or debugger
attach was added.

## Latest continuation - 2026-06-05 08:14 UTC

The ChatGPT Web/Desktop MCP adapter now rejects unexpected tool arguments
fail-closed instead of silently ignoring client mistakes. This makes automated
repo-control planning safer while preserving the same 9-tool authority surface.

| Evidence | Result |
|---|---|
| Argument allowlist | Every exposed tool now has an explicit accepted top-level argument-key set. |
| Manifest debug surface | `health`/tool manifest reports `allowedArgumentKeys` for client troubleshooting. |
| Unknown wrapper args | Calls such as `health({"ignored": true})` or `submit_package_proposal(..., "apply": true)` now block before any inbox write. |
| Non-JSON args | Non-JSON-serializable argument payloads block and are audited without logging proposal content. |
| Focused adapter tests | `python -m unittest scripts.test_riftreader_chatgpt_mcp` passed 50 tests in `3.022s`. |

No tool was added, no apply path was added, and no shell, Git, tunnel, ChatGPT
registration, live RIFT, provider, CE, or x64dbg authority was introduced.

## Latest continuation - 2026-06-05 08:23 UTC

Parallel local MCP validation exposed and fixed a package-draft allocation race:
`--self-test` and `--trial-readiness` could reserve the same self-test draft
suffix and one path failed with `FileExistsError`. Package-draft creation now
reserves the draft directory atomically before writing package files.

| Evidence | Result |
|---|---|
| Root cause | `unique_package_draft_dir()` checked for a free path and created it later; concurrent validation could choose the same suffix. |
| Fix | `reserve_unique_package_draft_dir()` now uses atomic `mkdir(..., exist_ok=False)` reservation and retries suffixes. |
| Regression test | `test_inbox_package_draft_reserves_unique_dirs_for_parallel_creators` creates four package drafts for the same inbox item in parallel. |
| Local tests | `python -m unittest scripts.test_local_artifact_bridge scripts.test_riftreader_chatgpt_mcp` passed 95 tests in `34.007s`. |
| Trial readiness | `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --trial-readiness --json` passed after the fix. |
| New readiness artifact | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T082325Z-trial-readiness.json`. |
| New proposal smoke artifact | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T082325Z-proposal-transport-smoke.json`. |

The failed parallel smoke did not mutate repo targets, Git, tunnel state,
ChatGPT registration, RIFT, provider repos, CE, or x64dbg. It created only
ignored `.riftreader-local` self-test/audit artifacts before the race was fixed.

## Latest continuation - 2026-06-05 08:45 UTC

The ChatGPT Web/Desktop MCP surface now supports a 10th guarded local-write
tool, `create_package_draft_from_inbox`, to complete the safe bidirectional
package path:

`submit_package_proposal` -> `list_inbox` -> `create_package_draft_from_inbox`
-> `review_latest_package_draft` -> `dry_run_latest_package_draft`.

| Evidence | Result |
|---|---|
| New tool | Requires an explicit validated `inboxId` and creates only an inert package draft under `.riftreader-local\artifact-bridge-package-drafts`. |
| Tool surface | Approved surface is now 10 tools. |
| Proof contract | Actual-client proof now expects `toolCount=10` and `createPackageDraftSucceeded=true`. |
| Transport smoke | Proposal transport smoke now covers submit, list inbox, and inert package-draft creation through the real MCP SDK/client path. |
| Focused tests | `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_trial_recorder scripts.test_mcp_phase2_status scripts.test_mcp_proof_replay scripts.test_mcp_workflow_state scripts.test_mcp_phase1_completion scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_final_readiness` passed 113 tests in `15.873s`. |
| Local self-test | `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --self-test --json` passed with `create_package_draft_from_inbox` and dry-run stages. |
| Trial readiness | `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --trial-readiness --json` passed with 10-tool SDK validation and 10-tool proposal transport smoke. |
| New readiness artifact | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T084601Z-trial-readiness.json`. |
| New proposal smoke artifact | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T084601Z-proposal-transport-smoke.json`. |
| Validation ledger | `.riftreader-local\validation-runs\20260605-084838-369184\summary.md`, targeted unittest suite passed in `15.290s`. |
| Safety | No apply, check execution, repo target write, shell endpoint, Git mutation, tunnel control, ChatGPT registration, live RIFT, provider, CE, or x64dbg authority was added. |

The stale historical actual-client proof will now block with a 10-tool mismatch
until a fresh ChatGPT Web/Desktop proof is recorded through the Secure Tunnel
path.

## Latest continuation - 2026-06-05 08:56 UTC

The ChatGPT-facing MCP adapter now recursively redacts the absolute local repo
root from every tool result before audit and return. This closes a nested
helper-leak path where inert package-draft review and dry-run payloads could
surface absolute `sourcePath`, `targetPath`, or command-argument paths from
underlying local helpers.

| Evidence | Result |
|---|---|
| Boundary | Redaction occurs at `RiftReaderChatGptMcpAdapter.call_tool()` after normal/error payload generation and before audit logging. |
| Scope | Applies to nested dict/list/string payloads for all 10 MCP tools, including blocked/error payloads. |
| Safety flag | `base_safety()` now includes `absoluteRepoRootRedacted=true`. |
| Regression tests | `python -m unittest scripts.test_riftreader_chatgpt_mcp` passed 52 tests in `2.758s`. |
| Covered outputs | Package-draft creation, package-draft review, and dry-run MCP responses assert the temp repo root is not serialized. |
| Targeted suite | `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_trial_recorder scripts.test_mcp_phase2_status scripts.test_mcp_proof_replay scripts.test_mcp_workflow_state scripts.test_mcp_phase1_completion scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_final_readiness` passed 113 tests in `15.604s`. |
| Local self-test | `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --self-test --json` passed; nested package-draft/dry-run paths were repo-relative in ChatGPT-facing payloads. |
| Trial readiness | `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --trial-readiness --json` passed with `toolCount=10` and package-draft transport smoke. |
| New readiness artifact | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T085722Z-trial-readiness.json`. |
| New proposal smoke artifact | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T085721Z-proposal-transport-smoke.json`. |
| Validation ledger | `.riftreader-local\validation-runs\20260605-085754-646797\summary.md`, targeted unittest suite passed in `15.790s`. |

No tool was added, no apply path was added, and no shell, Git, tunnel, ChatGPT
registration, live RIFT, provider, CE, or x64dbg authority was introduced.

## Code/docs changes

| File | Change |
|---|---|
| `tools/riftreader_workflow/riftreader_chatgpt_mcp.py` | Added `--secure-tunnel-plan`, env/shared-tools/repo-local `tunnel-client` discovery, stdio MCP command generation, binary SHA256/`--version` diagnostics, `get_workflow_control_plan`, `create_package_draft_from_inbox`, strict MCP wrapper-argument allowlists, ChatGPT-facing absolute repo-root redaction, JSON tunnel plan output/artifact writing, and Cloudflare deprecation framing. |
| `scripts/test_riftreader_chatgpt_mcp.py` | Added Secure MCP Tunnel plan coverage, command-line output coverage, ChatGPT smoke-order coverage, repo-local adminless discovery coverage, binary diagnostic coverage, workflow-control-plan coverage, package-draft creation coverage, response-redaction coverage, strict argument allowlist coverage, and updated trial-readiness dependency assertions to prefer `tunnel-client`. |
| `tools/riftreader_workflow/local_artifact_bridge.py` | Added atomic package-draft directory reservation so concurrent local MCP/self-test validations do not collide on the same draft suffix. |
| `scripts/test_local_artifact_bridge.py` | Added parallel package-draft creation regression coverage. |
| `tools/riftreader_workflow/mcp_workflow_state.py` | Added Secure Tunnel plan artifact indexing and changed MCP recommended workflow routing to prefer `--secure-tunnel-plan` before ChatGPT Web/Desktop proof. |
| `tools/riftreader_workflow/mcp_final_readiness.py` | Added primary-path `tunnel-client` dependency gate, env/shared-tools/repo-local discovery, SHA256/`--version` binary diagnostics, 10-tool approved surface, and aged-out stale ephemeral Cloudflare ready URLs so stale fallback artifacts do not block the Secure Tunnel path. |
| `tools/riftreader_workflow/mcp_mission_control.py` | Surfaced Secure Tunnel plan commands in Mission Control and proof checklist; Cloudflare trial command remains fallback-only. |
| `tools/riftreader_workflow/chatgpt_trial_recorder.py` | Updated actual-client proof template/validation to require 10 tools and package-draft creation confirmation. |
| `tools/riftreader_workflow/mcp_proof_replay.py` | Updated proof replay self-test to use the 10-tool package-draft proof contract. |
| `docs/HANDOFF.md` | Updated the compact handoff index so this Secure MCP Tunnel handoff is the newest resume point. |
| `docs/workflow/riftreader-chatgpt-mcp.md` | Reframed ChatGPT Web/Desktop setup around OpenAI Secure MCP Tunnel; Cloudflare commands now fallback-only; added current OpenAI tunnel requirements/troubleshooting and the 10-tool bidirectional package flow. |
| `docs/workflow/bridge-tunnel-session.md` | Marked old Cloudflare bridge helper deprecated fallback/dev-only and replaced PowerShell blocks with CMD-style commands. |

## New primary operator command

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --secure-tunnel-plan --json
```

The plan prints the exact local stdio MCP command for `tunnel-client`. It does
not start a tunnel, create credentials, register ChatGPT, mutate Git, send RIFT
input, or expose broad local tools.

## Validation performed

| Command | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\riftreader_chatgpt_mcp.py scripts\test_riftreader_chatgpt_mcp.py` | Passed. |
| `python -m unittest scripts.test_riftreader_chatgpt_mcp` | Passed: 41 tests. |
| `python -m unittest scripts.test_mcp_workflow_state scripts.test_mcp_final_readiness scripts.test_mcp_mission_control scripts.test_riftreader_chatgpt_mcp` | Passed: 71 tests. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --trial-readiness --json` | Passed local-only readiness; wrote `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T062943Z-trial-readiness.json`. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --secure-tunnel-plan --json` | Initially blocked before install; after verified shared-tools install, passed and wrote `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T065733Z-secure-tunnel-plan.json`. |
| `cmd /v:on /c "scripts\riftreader-chatgpt-mcp.cmd --secure-tunnel-plan --json > NUL & echo LAST=!ERRORLEVEL!"` | Passed wrapper exit-code check; now prints `LAST=0` after shared-tools `tunnel-client` install. |
| `scripts\riftreader-mcp-final.cmd --status --compact-json` | After install, `dependencyStatus=passed` and `requiredDependencies.tunnel-client=passed`; the dependency gate now includes SHA256 and `--version` binary diagnostics. Remaining blockers are unpushed local commits/current-head CI and stale actual-client proof. |
| `scripts\riftreader-mcp-mission-control.cmd --secure-tunnel-plan --json` | Passed display-only command payload; no tunnel or ChatGPT registration started. |
| `python tools\riftreader_workflow\validation_ledger.py --tier targeted --command "python -m unittest scripts.test_mcp_workflow_state scripts.test_mcp_final_readiness scripts.test_mcp_mission_control scripts.test_mcp_phase1_completion scripts.test_mcp_phase2_status scripts.test_mcp_proof_replay scripts.test_mcp_artifact_browser scripts.test_mcp_ci_status scripts.test_riftreader_chatgpt_mcp"` | Passed in `16.298s`; ledger `.riftreader-local\validation-runs\20260605-064914-219738\summary.md`. |
| `pre-commit run --all-files --show-diff-on-failure` | Passed all configured local hooks. |
| `git --no-pager diff --check` | Passed; only CRLF normalization warnings. |
| Changed MCP docs scan | Passed; no `powershell` references remain in the changed MCP docs. |

## Known blocker

| Blocker | Meaning | Safe next step |
|---|---|---|
| `tunnel-client profile not initialized` | Binary is installed, but no tunnel id/runtime API key has been used to initialize `riftreader-local-stdio`. | Create/select a Platform tunnel, set a runtime API key with Tunnels Read + Use, then run the generated `init`, `doctor`, and `run` command lines. |
| stale actual-client proof | The last actual ChatGPT proof is old and Cloudflare-based. | After Secure Tunnel is running, create/refresh the ChatGPT connector with Tunnel and smoke `health`, `get_repo_status`, `get_latest_handoff`. |

## OpenAI docs context used

| Doc | Use |
|---|---|
| `https://developers.openai.com/api/docs/guides/secure-mcp-tunnels` | Source for Secure MCP Tunnel / `tunnel-client` flow. |
| `https://developers.openai.com/api/docs/guides/secure-mcp-tunnels#connect-from-chatgpt` | Source for ChatGPT connector Tunnel setup expectations. |
| `https://platform.openai.com/settings/organization/tunnels` | Source location for creating/managing OpenAI-hosted MCP tunnel endpoints. |

## Resume instructions

1. Inspect `git --no-pager status --short --branch`.
2. Install/configure OpenAI `tunnel-client`.
3. Re-run `scripts\riftreader-chatgpt-mcp.cmd --secure-tunnel-plan --json`.
4. Use the printed `tunnel-client init`, `doctor`, and `run` commands; the plan now includes both argument arrays and command-line strings.
5. Register/refresh ChatGPT with the OpenAI Tunnel connection path for
   `rift-mcp`, not a `trycloudflare.com` URL.
6. Smoke from ChatGPT with `health`, then `get_repo_status`, then
   `get_latest_handoff`.
7. Keep Cloudflare helpers until the Secure MCP Tunnel path has one successful
   end-to-end proof, then remove or further quarantine them.

## Safety boundary

This handoff is about ChatGPT MCP transport only. It does not authorize live
game input, movement/displacement proof, ProofOnly, current-truth promotion,
x64dbg/CE, provider repo writes, Git push, or destructive cleanup.
