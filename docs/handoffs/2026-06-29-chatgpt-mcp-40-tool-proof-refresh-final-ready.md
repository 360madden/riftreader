# ChatGPT MCP 40-tool proof refresh final-ready

Date: 2026-06-29

## Verdict

The ChatGPT Web/Desktop MCP proof lane was refreshed for the current 40-tool
RiftReader MCP surface, local trial/proposal readiness was refreshed, and the
final-readiness gate passed with no release blockers.

## Current truth

| Item | Current truth |
|---|---|
| Proof mode | `final-40-tool` actual-client proof replay is fresh and passed. |
| Tool surface | Full non-Codex ChatGPT MCP profile is 40 tools with 40 output schemas. |
| Runtime | Local HTTP runtime is `running-current` on `http://127.0.0.1:8770/mcp`, full profile, source-fresh, PID `92060`. |
| Public route | Active route remains `https://mcp.360madden.com/mcp` via Cloudflare named Tunnel to local `127.0.0.1:8770`. |
| Auth lane | Personal `No Authentication` lane is preserved; saved ChatGPT connector config still does not start the local server or tunnel. |
| Package-loop proof | Template fetch, package proposal submit, inbox listing, draft creation, read-only review, and package dry-run all succeeded. |
| Apply gate | `apply_latest_package_draft` without approval correctly blocked with `APPLY_APPROVAL_MISSING`; `applied=false`. |
| Trial/proposal readiness | `scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json` passed and refreshed both trial readiness and proposal transport smoke artifacts. |
| Final readiness | `scripts\riftreader-mcp-final.cmd --status --compact-json` passed at `2026-06-29T18:36:13Z`, `ok=true`, blockers `[]`. |
| Release/demo packet | `scripts\riftreader-release-demo-packet.cmd --json --write --summary-md --refresh-safe-local` passed at `2026-06-29T18:39:28Z`; release blockers `[]`. |
| Git/GitHub before handoff commit | `main`, `origin/main`, and remote `refs/heads/main` matched `2f7bad2161e548e4ee41ae02ff2905aa3d38c0c2`. |
| Safety | No RIFT input, movement, focus/capture/click/key input, CE/x64dbg attach, provider write, proof promotion, branch rewrite, reset, cleanup, repo-source apply, or Git mutation occurred during proof refresh. |

## Key artifacts

| Artifact | Path |
|---|---|
| Actual-client proof JSON | `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\20260629-182953Z\proof.json` |
| Actual-client proof Markdown | `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\20260629-182953Z\proof.md` |
| Package proposal inbox item | `.riftreader-local\artifact-bridge-inbox\20260629T182549Z-07571a559545` |
| Package draft summary | `.riftreader-local\artifact-bridge-package-drafts\20260629T182549Z-07571a559545\summary.json` |
| Package dry-run summary | `.riftreader-local\package-intake\20260629-182709Z\package-intake-summary.json` |
| Package dry-run compact summary | `.riftreader-local\package-intake\20260629-182709Z\compact-package-intake-summary.json` |
| Package dry-run diff | `.riftreader-local\package-intake\20260629-182709Z\package.diff` |
| Trial readiness summary | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260629T183145Z-trial-readiness.json` |
| Proposal transport smoke summary | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260629T183145Z-proposal-transport-smoke.json` |
| Release/demo packet summary JSON | `.riftreader-local\riftreader-chatgpt-mcp\release-demo-packet\20260629-183928Z\summary.json` |
| Release/demo packet summary Markdown | `.riftreader-local\riftreader-chatgpt-mcp\release-demo-packet\20260629-183928Z\summary.md` |

## Validation

| Check | Result |
|---|---|
| `get_mcp_runtime_status` | Passed: runtime `running-current`, full profile, source-fresh. |
| `health` | Passed: 40 tools exposed with output-schema metadata. |
| Package proof loop | Passed through template, submit, inbox, draft, review, and dry-run. |
| Apply without approval | Blocked as expected with `APPLY_APPROVAL_MISSING`; no apply occurred. |
| `submit_actual_client_observation` | Passed and wrote the fresh ignored proof artifact. |
| Trial/proposal readiness | Passed via `scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json`. |
| Final readiness command | Passed: `ok=true`, `status=passed`, blockers `[]`, proof freshness `fresh`, proof replay `passed`, tool surface `passed`, upstream `passed`, CI `passed`. |
| Release/demo packet refresh | Passed with release blockers `[]`; proof-recovery target work remains deferred and is not an MCP release blocker. |
| Git sync check | Clean and synchronized before this handoff commit. |

## Notes

- The proof-refresh artifacts are intentionally ignored local evidence under
  `.riftreader-local`; this tracked handoff records the paths for recovery.
- One stale Codex/local stdio counterpart warning was present during runtime
  inspection. It is not Cloudflare HTTP runtime proof and did not block final
  readiness.
- The old manual-public-IP plan age remains an operator-action warning, not a
  release blocker for the named-tunnel lane.
- Current-PID/RIFT proof-recovery work is deferred because no RIFT window target
  is visible. That lane is separate from MCP release readiness and did not
  block the final gate.
- The authoritative release/demo gate remains:
  `scripts\riftreader-mcp-final.cmd --status --compact-json`.

## Recommended next action

Commit and push this handoff, then wait for current-head GitHub Actions. After
CI is green for the new handoff commit, rerun the final-readiness gate before
any release/demo.
