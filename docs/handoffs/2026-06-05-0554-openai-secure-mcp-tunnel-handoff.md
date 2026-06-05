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
| Tool surface | 8 allowlisted tools only |
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

## Code/docs changes

| File | Change |
|---|---|
| `tools/riftreader_workflow/riftreader_chatgpt_mcp.py` | Added `--secure-tunnel-plan`, env/shared-tools/repo-local `tunnel-client` discovery, stdio MCP command generation, binary SHA256/`--version` diagnostics, JSON tunnel plan output/artifact writing, and Cloudflare deprecation framing. |
| `scripts/test_riftreader_chatgpt_mcp.py` | Added Secure MCP Tunnel plan coverage, command-line output coverage, ChatGPT smoke-order coverage, repo-local adminless discovery coverage, binary diagnostic coverage, and updated trial-readiness dependency assertions to prefer `tunnel-client`. |
| `tools/riftreader_workflow/mcp_workflow_state.py` | Added Secure Tunnel plan artifact indexing and changed MCP recommended workflow routing to prefer `--secure-tunnel-plan` before ChatGPT Web/Desktop proof. |
| `tools/riftreader_workflow/mcp_final_readiness.py` | Added primary-path `tunnel-client` dependency gate, env/shared-tools/repo-local discovery, SHA256/`--version` binary diagnostics, and aged-out stale ephemeral Cloudflare ready URLs so stale fallback artifacts do not block the Secure Tunnel path. |
| `tools/riftreader_workflow/mcp_mission_control.py` | Surfaced Secure Tunnel plan commands in Mission Control and proof checklist; Cloudflare trial command remains fallback-only. |
| `docs/HANDOFF.md` | Updated the compact handoff index so this Secure MCP Tunnel handoff is the newest resume point. |
| `docs/workflow/riftreader-chatgpt-mcp.md` | Reframed ChatGPT Web/Desktop setup around OpenAI Secure MCP Tunnel; Cloudflare commands now fallback-only; added current OpenAI tunnel requirements/troubleshooting. |
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
