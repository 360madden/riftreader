# 2026-06-08 00:25 UTC — ChatGPT MCP proof-run packet handoff

## Current result

The RiftReader ChatGPT Web/Desktop MCP lane is ready for the next **actual
ChatGPT-side proof** attempt through the canonical Cloudflare named Tunnel
route:

```text
ChatGPT Web/Desktop
  -> https://mcp.360madden.com/mcp
  -> Cloudflare named Tunnel riftreader-mcp-360madden
  -> http://127.0.0.1:8770/mcp
  -> RiftReader MCP adapter
```

OpenAI Secure MCP Tunnel, `trycloudflare.com` quick tunnels, and
Caddy/router/direct-public-IP routing remain retired for this lane and are not
fallback paths.

## Live route state at handoff creation

| Item | Current value |
|---|---|
| Public Server URL | `https://mcp.360madden.com/mcp` |
| ChatGPT auth mode | `No Authentication` |
| Backend listener | `127.0.0.1:8770` |
| Backend PID observed | `35780` (`python.exe`) |
| Public smoke | HTTP `200`, `serverInfo.name=riftreader_chatgpt_mcp`, version `1.27.1` |
| Caddy/router | Local `caddy.exe` may still listen on TCP 443, but diagnostics report `activeRouteUsesCaddy=false` |

The backend was started from this repo with:

```cmd
scripts\riftreader-chatgpt-mcp.cmd --serve --tool-profile full --host 127.0.0.1 --port 8770 --transport streamable-http --allowed-host mcp.360madden.com --allowed-origin https://chatgpt.com
```

If the backend must be stopped later:

```cmd
taskkill /PID 35780 /T
```

## New local proof helper

Mission Control now has a proof-run packet mode:

```cmd
scripts\riftreader-mcp-mission-control.cmd --proof-run-packet-md
```

It prints a current ChatGPT Web/Desktop packet with:

- Server URL and `No Authentication` mode.
- Live backend PID when visible.
- Latest proof-input path.
- Expected 12-tool list.
- Safe ChatGPT call sequence.
- Local proof `--check-input` and `--record` commands.
- Current final-gate blockers.
- Explicit no-RIFT-input / no-CE / no-git-mutation boundaries.

The existing MCP `get_workflow_control_summary` response now also includes a
compact `proofRunPacket` pointer with the same Server URL, No Authentication
mode, connection mode, and local CLI packet command. This keeps the packet
discoverable from ChatGPT without changing the 12-tool MCP surface.

Operator Lite also exposes the same packet as a safe local command:

```cmd
scripts\riftreader-operator-lite.cmd --mcp-proof-run-packet --json
```

This command is read-only and does not start tunnels, register ChatGPT, apply
packages, mutate Git, or send live RIFT input.

## Local commits since the previous pushed HEAD

| Commit | Summary |
|---|---|
| `6ec817f` | Expose MCP proof packet in Operator Lite |
| `66a8798` | Harden MCP domain port-owner diagnostics |
| `04cdbc0` | Refresh ChatGPT MCP proof handoff state |
| `96f1c87` | Surface MCP proof packet in workflow summary |
| `e440861` | Add ChatGPT MCP proof packet handoff |
| `56f616b` | Filter PID zero from MCP proof packet |
| `c98213b` | Document ChatGPT MCP proof run packet |
| `972bd47` | Add ChatGPT MCP proof run packet |
| `df054d2` | Draft gated ChatGPT MCP live control design |
| `4a8967d` | Rename MCP route action keys for Cloudflare tunnel |
| `a824cbc` | Fix Cloudflare route metadata in MCP control surfaces |

Local branch state after the latest local commit:

```text
main...origin/main [ahead 11]
```

No push was performed because remote mutation is gated by repo policy.

## Validation completed

| Validation | Result |
|---|---|
| `python -m unittest scripts.test_operator_lite` | Passed, 51 tests |
| `scripts\riftreader-operator-lite.cmd --mcp-proof-run-packet --json` | Passed; printed current proof packet through Operator Lite |
| `python -m unittest scripts.test_operator_lite scripts.test_mcp_mission_control scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_mcp_workflow_docs scripts.test_mcp_domain_diagnostics` | Passed, 138 tests |
| targeted `pre-commit run --files tools/riftreader_workflow/operator_lite.py scripts/test_operator_lite.py --show-diff-on-failure` | Passed |
| `python tools\riftreader_workflow\validation_ledger.py --tier full-local --json` | Passed in 444.843s |
| Validation ledger summary | `.riftreader-local\validation-runs\20260608-004411-448466\summary.md` |
| `dotnet restore RiftReader.slnx` | Passed inside full-local ledger |
| `dotnet build RiftReader.slnx --no-restore --configuration Release` | Passed inside full-local ledger, 0 warnings/errors |
| `dotnet test RiftReader.slnx --no-build --configuration Release --logger console;verbosity=minimal` | Passed inside full-local ledger, 109 tests |
| `scripts\riftreader-mcp-final.cmd --status --compact-json` | Blocked as expected on unpushed current-head CI and stale/missing actual-client proof |

## Current final-gate blockers

| Blocker group | Meaning |
|---|---|
| `git:upstream-not-synced:behind=0:ahead=11` | Eleven local commits have not been pushed; GitHub current-head CI cannot run for this local HEAD yet. |
| `ci:missing:.NET build and test` / `ci:missing:RiftReader Policy` | Expected in the final gate until the commits are pushed; local full-local ledger passed separately. |
| `proof:*` stale/missing fields | Existing historical proof is from retired quick-tunnel era and lacks the current Cloudflare named Tunnel proof fields. |
| `phase2:not-ready` | Phase 2 cannot pass until proof replay and current-head CI pass. |

## Required next actual-client proof sequence

1. In ChatGPT Web/Desktop, connect MCP Server URL
   `https://mcp.360madden.com/mcp` with `No Authentication`.
2. Call `health`.
3. Call `get_repo_status`.
4. Call `get_latest_handoff`.
5. Call `get_workflow_control_summary`.
6. Confirm ChatGPT sees exactly the 12 expected tools and output schemas.
7. Call `get_package_proposal_template`.
8. Submit one tiny harmless package proposal with `submit_package_proposal`.
9. Confirm `list_inbox` sees the returned inbox ID.
10. Call `create_package_draft_from_inbox`.
11. Call `review_latest_package_draft` and confirm read-only review.
12. Call `dry_run_latest_package_draft` and record bounded diff-preview facts.
13. Call `apply_latest_package_draft` without approval token and confirm
    `APPLY_APPROVAL_MISSING`, `applied=false`.
14. Fill the latest proof-input JSON and validate it locally:

```cmd
scripts\riftreader-chatgpt-trial-recorder.cmd --check-input --input .riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-232355Z\proof-input.json --json
```

15. Record after check passes:

```cmd
scripts\riftreader-chatgpt-trial-recorder.cmd --record --input .riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-232355Z\proof-input.json --json
```

16. Rerun final gate:

```cmd
scripts\riftreader-mcp-final.cmd --status --compact-json
```

## Safety boundaries still in force

- Do not push without explicit approval.
- Do not register or mutate ChatGPT settings from Codex without explicit
  operator approval.
- Do not send live RIFT input, movement, target selection, `/reloadui`, or
  screenshot-key input.
- Do not attach CE/x64dbg.
- Do not promote coordinates/current-truth/proof anchors.
- Do not expose additional high-power MCP tools until the current 12-tool proof
  passes.
- The new live-control design remains plan-only.
