# Compact handoff: ChatGPT MCP public tunnel smoke validated

Created: 2026-05-19 01:30 EDT
Repo: `C:\RIFT MODDING\RiftReader`
Branch at creation: `main`
Scope: RiftReader live artifact bridge / Desktop ChatGPT MCP adapter lane.

## TL;DR

The narrow ChatGPT MCP adapter is now locally and publicly smoke-validated through a temporary Cloudflare quick tunnel. The public `/mcp` smoke proved `initialize`, `tools/list`, and `tools/call health` over HTTPS, with exact-host and exact-origin validation, then stopped both the tunnel and temporary loopback server. A bounded `--chatgpt-trial-session` mode now starts a verified public MCP URL, writes a ready packet for manual ChatGPT Developer Mode registration, keeps it alive for a requested duration, and stops both processes.

A path-hygiene issue found during the first public smoke was fixed: MCP `health` no longer exposes the absolute local repository path. Public health now reports `repoRoot=.` and `repoName=RiftReader`.

The latest autonomous MCP hardening also fixed the remaining write-tool client gap: `submit_package_proposal` now registers an exact nested Pydantic input schema with FastMCP instead of a broad `object`, and trial readiness now proves a synthetic package proposal through the real SDK streamable-HTTP transport before any ChatGPT registration.

## Current changes in this slice

| Area | Result |
|---|---|
| MCP trial readiness | Added `--trial-readiness` to `tools/riftreader_workflow/riftreader_chatgpt_mcp.py`. |
| SDK local install handling | `--validate-sdk` now auto-detects `.riftreader-local\mcp-sdk-validation`. |
| Operator Lite | Added `mcp-trial-readiness`, aliases, `--mcp-trial-readiness`, and GUI button wiring. |
| Public health hygiene | Redacted absolute repo root from MCP `health`; reports `.` plus repo name. |
| Runtime redaction gate | Transport/public smoke now fails closed if `health` stops redacting `repoRoot` or sets `absoluteRepoRootExposed` to anything other than `false`. |
| ChatGPT trial session | Added `--chatgpt-trial-session --chatgpt-session-seconds <seconds>` for a bounded real registration window. |
| Submit schema hardening | `submit_package_proposal` now exposes an exact nested Pydantic schema for package proposals and forbids broad extra fields. |
| Proposal transport smoke | Added `--proposal-transport-smoke` and made local trial readiness cover synthetic `submit_package_proposal` over MCP transport. |
| Durable smoke summaries | Loopback transport smoke now writes ignored summary JSON under `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke`. |
| Docs | Updated MCP, Operator Lite, and Local Artifact Bridge docs. |
| Tests | Added MCP trial-readiness, proposal transport, schema verifier, and Operator Lite command coverage. |

## Validated proof artifacts

| Proof | Artifact |
|---|---|
| Operator Lite MCP trial readiness | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T050756Z-trial-readiness.json` |
| First public Cloudflare smoke | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T052853Z-cloudflare-tunnel-smoke.json` |
| Public Cloudflare smoke after path redaction | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T053005Z-cloudflare-tunnel-smoke.json` |
| Public Cloudflare smoke after runtime redaction gate | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T053510Z-cloudflare-tunnel-smoke.json` |
| Bounded ChatGPT trial session ready packet | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T054343Z-chatgpt-trial-session-ready.json` |
| Bounded ChatGPT trial session final summary | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T054345Z-chatgpt-trial-session.json` |
| Standalone proposal transport smoke | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T063335Z-proposal-transport-smoke.json` |
| Latest Operator Lite MCP trial readiness | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T063557Z-trial-readiness.json` |
| Proposal transport stage inside latest trial readiness | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T063557Z-proposal-transport-smoke.json` |
| Latest public Cloudflare smoke after proposal hardening | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T063454Z-cloudflare-tunnel-smoke.json` |

## Latest public smoke facts

| Field | Value |
|---|---|
| Status | `passed` |
| Public MCP URL used | `https://car-comm-composed-through.trycloudflare.com/mcp` |
| Public health `repoRoot` | `.` |
| Public health `repoName` | `RiftReader` |
| Public health `absoluteRepoRootExposed` | `false` |
| Tool count | `8` |
| Server stopped | `true` |
| Tunnel stopped | `true` |
| ChatGPT registration performed | `false` |
| Git mutation | `false` |
| RIFT input / CE / x64dbg | `false` |

The latest public URL was ephemeral and is no longer expected to work after the smoke helper stopped the tunnel. Earlier public redaction-gate URL: `https://implied-feeds-colleagues-conscious.trycloudflare.com/mcp`; earlier post-schema-hardening smoke URL: `https://clarke-correlation-apply-shows.trycloudflare.com/mcp`.

## Latest bounded ChatGPT trial-session facts

| Field | Value |
|---|---|
| Status | `passed` |
| Ready | `true` |
| Public MCP URL used | `https://sprint-ken-steam-influences.trycloudflare.com/mcp` |
| Ready packet | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T054343Z-chatgpt-trial-session-ready.json` |
| Final summary | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T054345Z-chatgpt-trial-session.json` |
| Held duration | `2` seconds |
| Server stopped | `true` |
| Tunnel stopped | `true` |
| ChatGPT registration performed | `false` |

The trial URL was ephemeral and is no longer expected to work after the bounded helper stopped the tunnel.

## Commands that passed

```powershell
python -m unittest scripts.test_riftreader_chatgpt_mcp
python -m unittest scripts.test_operator_lite scripts.test_riftreader_chatgpt_mcp
python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_local_artifact_bridge scripts.test_operator_lite scripts.test_package_draft_review
python tools/riftreader_workflow/operator_lite.py --mcp-trial-readiness --json
python tools/riftreader_workflow/riftreader_chatgpt_mcp.py --cloudflare-tunnel-smoke --json
python tools/riftreader_workflow/riftreader_chatgpt_mcp.py --cloudflare-tunnel-smoke --json  # re-run after proposal schema hardening
python tools/riftreader_workflow/riftreader_chatgpt_mcp.py --proposal-transport-smoke --json
python tools/riftreader_workflow/riftreader_chatgpt_mcp.py --trial-readiness --json
.\scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json
.\scripts\riftreader-chatgpt-mcp.cmd --chatgpt-trial-session --chatgpt-session-seconds 2 --json
```

Latest targeted validation: `132` tests passed after proposal-transport hardening
and doc updates. `git --no-pager diff --check` passed with CRLF normalization
warnings only. Latest Operator Lite MCP trial-readiness summary:
`.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T063557Z-trial-readiness.json`.


## MCP Workflow Suite helper-app update

The repo now includes the requested Python-first MCP Workflow Suite helpers with
thin `.cmd` wrappers:

| Helper | Entry point | Result |
|---|---|---|
| MCP Mission Control | `scripts\riftreader-mcp-mission-control.cmd --json` | One dashboard for readiness, artifact proof, dirty Git summary, ranked next actions, and paste-safe commands. |
| Proof Artifact Browser | `scripts\riftreader-mcp-artifacts.cmd --latest --json` | Latest and timeline views for readiness, proposal/public smoke, trial-session, actual-client proof, inbox, draft, and dry-run artifacts. |
| ChatGPT Trial Recorder | `scripts\riftreader-chatgpt-trial-recorder.cmd --template --json` / `--record --input proof.json --json` | Records operator-supplied actual ChatGPT proof packets under ignored `.riftreader-local` and fails closed on proof-quality gaps. |
| Safe Commit Packager | `scripts\riftreader-safe-commit-packager.cmd --plan --json` | Plan-only explicit-path staging checklist and commit-message draft; no staging, commit, or push. |
| Workflow Router | `scripts\riftreader-workflow-router.cmd --mcp --json` | Recommends the next safest MCP lane command from local artifacts and Git state. |

Operator Lite now exposes safe buttons/shortcuts for those helpers, but still has
no button that starts a public tunnel. The bounded real trial remains the direct
`riftreader-chatgpt-mcp.cmd --chatgpt-trial-session ...` command. Follow-up
helper improvements from the Top 30 list were also added: Mission Control
Markdown summary/checklist output, Artifact Browser read-only open-latest,
artifact age/stopped-ephemeral URL warnings, self-test artifact labeling, Safe
Commit Packager Markdown export, and generated Operator Lite command reference.

## Safety boundaries still true

- No broad MCP proxying.
- No arbitrary filesystem read/write tool.
- No shell execution tool.
- No Git mutation endpoint.
- No RIFT input, movement, target control, CE, or x64dbg endpoint.
- No persistent public tunnel remains running after smoke/trial-session completion.
- ChatGPT Developer Mode registration has not been performed yet.
- Package proposals still land only as inert `.riftreader-local` inbox/draft artifacts until separately reviewed and dry-run/applied by explicit operator action.

## Resume sequence

```powershell
cd "C:\RIFT MODDING\RiftReader"
python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_local_artifact_bridge scripts.test_operator_lite scripts.test_package_draft_review
.\scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json
.\scripts\riftreader-chatgpt-mcp.cmd --proposal-transport-smoke --json
.\scripts\riftreader-chatgpt-mcp.cmd --cloudflare-tunnel-smoke --json
.\scripts\riftreader-chatgpt-mcp.cmd --chatgpt-trial-session --chatgpt-session-seconds 900 --json
```

If those pass, the next real proof is manual ChatGPT Developer Mode registration against the fresh `publicMcpUrl` printed by `--chatgpt-trial-session`, then one tiny operator-approved package proposal through the actual ChatGPT client. The local SDK/client proposal path is already proved by `--proposal-transport-smoke` and by the latest `--mcp-trial-readiness` run.

## Paste-ready resume prompt

Resume `C:\RIFT MODDING\RiftReader` live artifact bridge work from `docs/handoffs/2026-05-19-0130-chatgpt-mcp-public-tunnel-validated.md`. First review the current git diff and run the MCP/operator validation commands. The narrow ChatGPT MCP adapter has passed local trial readiness, temporary Cloudflare public smoke, runtime redaction-gate validation, and a short bounded `--chatgpt-trial-session`; health path hygiene was fixed so public health reports `repoRoot=.` and `repoName=RiftReader`. Continue with real ChatGPT Developer Mode registration using a fresh long-running trial session and then a tiny package-proposal loop.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Review the current 8-file diff. | This is now a coherent validated bridge/MCP slice. |
| 2 | Re-run Operator Lite wrapper command `--mcp-trial-readiness`. | Confirms `.cmd` path and synthetic proposal submit through MCP transport. |
| 3 | Run `.\scripts\riftreader-chatgpt-mcp.cmd --proposal-transport-smoke --json` when isolating the write-tool path. | Gives a focused local proof before involving ChatGPT. |
| 4 | Re-run public Cloudflare smoke once if environment changed. | Confirms HTTPS `/mcp` remains viable. |
| 5 | Start `.\scripts\riftreader-chatgpt-mcp.cmd --chatgpt-trial-session --chatgpt-session-seconds 900 --json`. | Provides a verified public MCP URL and keeps it alive for registration. |
| 6 | Register the fresh `publicMcpUrl` in ChatGPT Developer Mode. | Remaining end-to-end proof gap. |
| 7 | In ChatGPT, call `health` and confirm only 8 tools. | Verifies tool surface inside the actual client. |
| 8 | Submit one tiny package proposal through actual ChatGPT. | Proves ChatGPT -> MCP -> inbox beyond the local SDK client. |
| 9 | Export that proposal to an inert draft and dry-run it. | Completes safe proposal package loop without applying. |
| 10 | Commit the validated local+public smoke slice. | Preserves rollbackable milestone before broader trials. |
