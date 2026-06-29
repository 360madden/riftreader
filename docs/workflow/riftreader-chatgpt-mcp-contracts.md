# RiftReader ChatGPT MCP contract index

Status: Stage 56 contract map for the current 40-tool ChatGPT Web/Desktop MCP
lane. This file links the authoritative contracts and records the small shared
rules that make the helper suite modular without splitting the repo.

This is not a new tool-surface contract. The approved tool list remains in
`docs\workflow\riftreader-chatgpt-mcp-final-readiness.md`.

## Contract ownership

| Contract area | Canonical source | Implemented by | Test ownership |
|---|---|---|---|
| ChatGPT MCP adapter surface | `docs\workflow\riftreader-chatgpt-mcp-final-readiness.md` | `tools\riftreader_workflow\riftreader_chatgpt_mcp.py` | `scripts\test_riftreader_chatgpt_mcp.py` |
| Final readiness gate | `docs\workflow\riftreader-chatgpt-mcp-final-readiness.md` | `tools\riftreader_workflow\mcp_final_readiness.py` | `scripts\test_mcp_final_readiness.py` |
| Workflow artifact discovery | this file plus final-readiness docs | `tools\riftreader_workflow\mcp_workflow_state.py` | `scripts\test_mcp_workflow_state.py` |
| Artifact classification | this file | `tools\riftreader_workflow\mcp_workflow_state.py` | `scripts\test_mcp_workflow_state.py`, `scripts\test_mcp_contract_audit.py` |
| Contract audit | this file plus final-readiness docs | `tools\riftreader_workflow\mcp_contract_audit.py` | `scripts\test_mcp_contract_audit.py` |
| Recovery plan | `docs\workflow\mcp-readiness-recovery.md` | `tools\riftreader_workflow\mcp_recovery_plan.py` | `scripts\test_mcp_recovery_plan.py` |
| Unified operator status | `docs\workflow\operator-status.md` | `tools\riftreader_workflow\operator_status.py` | `scripts\test_operator_status.py` |
| Release/demo packet | this file plus architecture map | `tools\riftreader_workflow\release_demo_packet.py` | `scripts\test_release_demo_packet.py` |
| Package proposal/draft/dry-run/apply | `docs\workflow\local-artifact-bridge.md`, `docs\workflow\package-flow.md`, `docs\workflow\package-intake-lite.md` | artifact bridge and package review helpers | `scripts\test_local_artifact_bridge.py`, `scripts\test_package_draft_review.py` |
| Commit/push gates | commit/push design docs | commit/push helper modules | commit/push focused tests |

## Shared JSON envelope

Repo workflow helpers should return object-shaped JSON with these fields when
practical:

| Field | Contract |
|---|---|
| `schemaVersion` | Integer schema version for the emitted packet. |
| `kind` | Stable packet/tool name. |
| `generatedAtUtc` | UTC timestamp for generated status packets. |
| `status` | `passed`, `ready`, `blocked`, `failed`, or a documented state. |
| `ok` | Boolean success/readiness summary. `false` for blocked/failed gates. |
| `blockers` | List of actionable blocker strings. Empty when `ok=true`. |
| `warnings` | List of non-blocking warnings for operator attention. |
| `recommendedNextAction` | Optional compact next safe action. |
| `safety` | Explicit safety facts for side-effect-sensitive helpers. |
| `artifacts` | Optional paths to ignored or tracked artifacts written by the helper. |

Missing or malformed envelope fields in MCP tool results must fail closed before
the result is treated as a valid ChatGPT-facing response.

## Exit-code convention

| Exit code | Meaning | Use |
|---:|---|---|
| `0` | Passed/ready. | Validation, status, and self-test success. |
| `1` | Failed unexpectedly. | Exceptions, malformed required artifacts, unsupported states, helper errors. |
| `2` | Blocked-safe. | Known gate is not satisfied and no unsafe action occurred. |

Validation wrappers that intentionally call a blocked-safe status command must
normalize exit `2` only after proving the command is expected to be blocked.

## Artifact classification contract

`mcp_workflow_state` classifies local MCP artifact noise so compact operator
surfaces stay actionable.

| Category | Meaning | Release impact |
|---|---|---|
| `release-blocker` | Local required release artifact is missing/stale/malformed. | Blocks final readiness. |
| `operator-action-needed` | Operator must refresh proof, route, runtime, template, or other evidence. | May block release when `releaseBlocker=true`. |
| `historical-warning` | Old non-required evidence is useful context. | Does not block release. |
| `expected-expired` | Stopped/aged ephemeral public URL evidence. | Does not block release. |
| `ignored-local-evidence` | Self-test or ignored diagnostic evidence that is not operator/live proof. | Does not block release. |
| `obsolete-superseded` | Older missing/malformed summaries superseded by newer readable artifacts. | Does not block release. |

`releaseBlocker` is an explicit record field and must not be inferred only from
the category. Example: stale `actual-client-proof` is
`operator-action-needed` with `releaseBlocker=true`.

## Freshness contract

| Artifact | Budget | Blocking rule |
|---|---:|---|
| `readiness` | 6 hours | Blocks final readiness when stale/missing. |
| `proposal-smoke` | 6 hours | Blocks final readiness when stale/missing. |
| `actual-client-proof` | 24 hours | Blocks final readiness when stale, but as operator proof-refresh work. |
| `proof-input-template` | 24 hours | Operator-action warning; stale template should be regenerated before filling. |
| `manual-public-ip-plan` | 24 hours | Operator-action warning; current active route remains Cloudflare named Tunnel. |
| stopped quick-tunnel/trial artifacts | no release freshness requirement | Classify as `expected-expired` when teardown/age proves they are not active. |

## Side-effect boundaries

| Boundary | Contract |
|---|---|
| Status/readiness/audit helpers | Read-only, except optional ignored `.riftreader-local` summaries. |
| Trial/proof recorder | Writes ignored proof templates or operator-supplied proof artifacts only. |
| Package proposal flow | Writes ignored inbox/draft/package-intake artifacts until explicit apply approval. |
| Apply | Approval-token gated, never stages/commits/pushes and never writes providers. |
| Local commit | Approval-token gated, explicit paths only, no push/rewrite/reset/clean. |
| Push | Approval-token gated normal current-branch push only, no force/rewrite. |
| Live RIFT | No input/movement/focus/click/ProofOnly/proof promotion without explicit approval. |
| Debugger/CE | No attach/breakpoint/watchpoint/memory read/write without explicit approval and supported backend. |
| Provider repos | No writes outside RiftReader unless explicitly authorized in the current turn. |

## Validation contract for docs/code slices

| Slice type | Minimum validation |
|---|---|
| Docs-only | `git --no-pager diff --check`; pre-commit on touched files; markdownlint on touched docs when practical. |
| Python helper/test | `python -m py_compile` for changed helpers/tests; focused unittest modules; `git --no-pager diff --check`; pre-commit. |
| Multi-helper workflow | Targeted `validation_ledger.py --tier targeted --command <cmd>` plus pre-commit. |
| Agent definition edits | `python scripts\agent-validate.py --verbose --json`. |
| Final release claim | Current-head CI, clean worktree, fresh proof, fresh readiness/smoke, final gate, and release/demo packet evidence. |

## Update rules

1. Update the canonical contract first, then link from this index.
2. Do not duplicate the full 40-tool table here.
3. Add a focused regression test with any contract behavior change.
4. Keep blocked-safe proof-recovery and live RIFT blockers separate from MCP
   release-readiness local code blockers.
5. Preserve ignored local artifacts as evidence, not tracked release content.
