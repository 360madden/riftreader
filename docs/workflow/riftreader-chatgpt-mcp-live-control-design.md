# ChatGPT MCP live RIFT control design

Status: **Stage 41 complete-local design**. Stage 38-40 no-input live-status
MCP tools are exposed, and the current ChatGPT Web/Desktop proof contract is 36
tools. This document still does not expose any live-control execution tool.
The current ChatGPT Web/Desktop proof contract is 36 tools.

This design now starts at Stage 41 because the Stage 38-40 read-only/no-input
surfaces exist. It defines the remaining gates that must exist before ChatGPT
Web/Desktop can request stimulus tests or eventually control player movement.

## Current hard boundary

| Boundary | Rule |
|---|---|
| Current MCP product | Keep the existing 36-tool `https://mcp.360madden.com/mcp` Cloudflare named Tunnel product as the proof target. |
| Actual-client transport | Do not treat local backend status as sufficient; the actual ChatGPT client proof must record `clientTransportStatus=tool-call-succeeded` and `healthCallSucceeded=true`. `Transport closed` blocks this ladder. |
| Tool exposure | Stage 38-40 read-only/no-input tools are exposed. Do not add live RIFT input/movement tools until the current 36-tool actual-client proof is fresh, final readiness passes, and a separate execution-boundary approval is explicit. |
| Live input | Do not send key input, target selection, movement, turn stimulus, `/reloadui`, or screenshot-key input without explicit live approval. |
| Debugger/CE | Do not attach x64dbg, Cheat Engine, breakpoints, or watchpoints from this lane. |
| Promotion | Do not promote current truth, actor chains, coordinates, yaw/facing, or proof anchors from a live-control tool. |
| Provider writes | Do not write ChromaLink, RiftScan, or other provider repos from live-control tools by default. |

## Capability ladder

| Stage | MCP capability | Allowed behavior | Required proof before exposure |
|---:|---|---|---|
| 38 | `get_live_rift_readonly_state` | Read-only exact-target facts/status after fresh proof; no focus/capture/input/ProofOnly. | Exact target identity helper passes and returns fail-closed blockers on stale proof or drift. |
| 39 | `get_live_target_identity_gate` | Read-only reusable target gate: PID, HWND, process start, module base, duplicate detection. | Tests cover PID/HWND mismatch, duplicate RIFT windows, missing module base, and stale artifacts. |
| 40 | `get_live_no_input_proof_status` | Read-only candidate/proof summaries only after the identity gate passes; no movement/input; candidate-only truth preserved. | Current no-input readback reports safety flags and artifact paths without implying route authorization. |
| 41 | Design contract only; no new MCP tool. | Defines action taxonomy, risk classes, required response envelope, approval binding, and stop conditions. | Tests/docs prove the stage is non-executing and keeps `inputSent=false` / `movementSent=false`. |
| 42 | `plan_live_control_action` or equivalent planning tool. | Plan-only stimulus/movement request; returns exact target, proposed actions, risks, blockers, and required approval phrase. | No execution path; output proves `inputSent=false` and `movementSent=false`. |
| 43 | `execute_live_control_action` | Smallest approved exact-target action after explicit approval. | Current target gate passes, approval phrase matches, stop key exists, post-action readback records `inputSent`/`movementSent` truthfully. |

## Stage 41 design contract

Stage 41 is intentionally documentation and test coverage only. It completes the
live-control design boundary without changing the 36-tool MCP surface and without
creating a callable live-control endpoint.

### Action taxonomy

| Action kind | Examples | Risk class | Stage 41 rule |
|---|---|---|---|
| `no-input-read` | Inspect readiness, identity, proof freshness. | read-only | Already covered by Stage 38-40 tools. |
| `ui-action` | Open inventory, press a non-movement hotbar slot. | semantic UI/action risk | Must remain plan-only until a dry-run tool exists. |
| `displacement-stimulus` | Tiny movement pulse for coordinate proof. | live state mutation | Requires explicit current-turn approval and proof gates before any later execution tool. |
| `movement-control` | Hold `W/A/S/D/Q/E`, arrows, Space, route step. | movement risk | Blocked by default; Stage 41 only describes the plan envelope. |
| `proof-only` | Re-run a proof/readback helper that claims no movement. | proof gate risk | Must stay separate from movement/control and never be implied by plan-only output. |

### Required future plan envelope

The later Stage 42 planning tool must return a bounded object with these fields:

| Field | Required behavior |
|---|---|
| `schemaVersion`, `kind`, `status`, `ok` | Standard response identity and pass/block state. |
| `actionKind`, `riskClass`, `movementRisk` | Classify no-input, UI action, displacement stimulus, movement, or proof-only. |
| `targetBinding` | PID, HWND, process start time, module base, module path, proof age, and identity-gate status. |
| `requestedAction` | Semantic action, primitive mapping, max duration, max input count, and verification request. |
| `approvalPacket` | Human-readable current-turn approval prompt bound to target/action/plan hash; never a reusable broad approval token. |
| `recommendedVerification` | Read-only or post-action checks required before any future execution can be trusted. |
| `blockers`, `warnings`, `safety` | Fail-closed reasons and explicit safety truth for every response. |

Stage 41 does **not** allow the plan envelope to execute anything. For every
Stage 41 artifact or response, the safety truth remains:

- `inputSent=false`
- `movementSent=false`
- `reloaduiSent=false`
- `screenshotKeySent=false`
- `targetMemoryBytesWritten=false`
- `x64dbgAttach=false`
- `noCheatEngine=true`
- `providerWrites=false`
- `truthPromotionPerformed=false`
- `savedVariablesUsedAsLiveTruth=false`

## Bidirectional data exchange model

| Direction | Data | Storage / response |
|---|---|---|
| ChatGPT -> RiftReader | Proposed live action plan, approval phrase, target identity expected values, max duration, stop conditions. | MCP request arguments plus a durable audit envelope under `.riftreader-local`. |
| RiftReader -> ChatGPT | Target identity, live-readback status, candidate/proof freshness, blockers, warnings, post-action evidence. | Structured MCP response with bounded previews and artifact paths. |
| RiftReader -> operator | Human-readable action plan and abort/stop instructions. | Markdown summary beside the JSON audit envelope. |
| Operator -> RiftReader | Explicit approval for live stimulus/movement in the current turn. | Approval phrase/token bound to target identity, action kind, duration, and generated plan hash. |

## Required exact-target gate

Every live read/control tool must fail closed unless all required identity facts
match the current process:

| Field | Required behavior |
|---|---|
| PID | Match the selected RIFT process and fail on missing/duplicate process ambiguity. |
| HWND | Match the intended top-level game window and fail if ownership changes. |
| Process start time | Match the captured start time; fail after relog/restart or PID reuse. |
| Module base and image path | Match `rift_x64.exe` for the current install epoch. |
| Manifest epoch | Record manifest version/hash/time so stale proof is not mixed with a new game build. |
| Foreground/input eligibility | Required only for execution tools; read-only tools must not focus or send input. |

## Safety truth required in every response

Every response must include these booleans, even on failure:

| Field | Meaning |
|---|---|
| `inputSent` | Whether any input primitive was called. |
| `movementSent` | Whether movement/turn/stimulus input was sent. |
| `reloaduiSent` | Whether `/reloadui` or equivalent was sent. |
| `screenshotKeySent` | Whether a screenshot key was sent. |
| `targetMemoryBytesRead` | Whether live process memory bytes were read. |
| `targetMemoryBytesWritten` | Must remain `false`; live tools do not write process memory. |
| `x64dbgAttach` | Must remain `false` in this lane. |
| `noCheatEngine` | Must remain `true` in this lane. |
| `providerWrites` | Must remain `false` unless a separate provider-write design is approved. |
| `truthPromotionPerformed` | Must remain `false`; proof promotion is a separate gate. |
| `routeControlAuthorized` | `true` only after current proof gates pass for route control. |
| `canExecuteLiveNavigation` | `true` only after exact-target, current proof, and approval gates pass. |

## Approval binding for any execution tool

An execution-capable live tool must require an approval phrase/token generated
from the same current plan. The token must bind:

1. PID, HWND, process start time, and module base.
2. Action kind: no-input, stimulus, movement, route step, or stop.
3. Maximum duration and max input count.
4. Generated plan hash and artifact path.
5. Expiration timestamp.
6. Current-turn statement that live input/movement is approved.

Missing, stale, mismatched, or reused approval must return a blocker and perform
no action.

## Fail-closed blockers

| Code | Meaning |
|---|---|
| `LIVE_TOOL_NOT_EXPOSED` | Tool is still plan-only or disabled. |
| `LIVE_TARGET_NOT_FOUND` | No exact RIFT PID/HWND target was found. |
| `LIVE_TARGET_AMBIGUOUS` | More than one plausible RIFT target exists. |
| `LIVE_TARGET_DRIFT` | PID/HWND/start/module changed after planning. |
| `LIVE_PROOF_STALE` | Current proof/readback artifacts are too old for action. |
| `LIVE_COORDINATE_ROOT_BLOCKED` | Promoted coordinate/static-owner root is blocked or candidate-only. |
| `LIVE_ROUTE_CONTROL_UNAUTHORIZED` | Route-control proof gates have not passed. |
| `LIVE_APPROVAL_MISSING` | Current-turn live approval token/phrase is absent. |
| `LIVE_APPROVAL_MISMATCH` | Approval does not bind to this target/action/plan. |
| `LIVE_STOP_CONDITION_MISSING` | Execution request lacks a bounded stop condition. |
| `LIVE_INPUT_BACKEND_UNAVAILABLE` | The approved exact-target input backend is unavailable. |
| `LIVE_POST_READBACK_FAILED` | Post-action evidence could not be collected; do not promote truth. |

## Minimal implementation sequence

1. Stage 38 complete-local: `get_live_rift_readonly_state`.
2. Stage 39 complete-local: `get_live_target_identity_gate`.
3. Stage 40 complete-local: `get_live_no_input_proof_status`.
4. Add plan-only live-control action output with no execution path.
5. Add dry-run validation and audit envelopes.
6. Only then add the smallest execution tool, behind explicit current-turn
   approval and bounded stop conditions.

## Current known blockers

| Blocker | Effect |
|---|---|
| Current 36-tool actual-client proof is stale/missing for the Cloudflare named Tunnel route and must include actual-client transport success. | Do not expose high-power live input/movement tools yet. |
| Current static-owner readback root pointer is blocked/null after the game update. | Live navigation/control is not route-actionable. |
| Latest no-input rediscovery is candidate-only and reports PID/HWND mismatch blockers. | Exact-target proof must be rebuilt before movement. |

## Non-goals

- No arbitrary shell command endpoint.
- No arbitrary filesystem read/write endpoint.
- No Git push, branch rewrite, reset, or cleanup.
- No provider repo writes.
- No movement or stimulus by default.
- No debugger/CE attach.
- No proof/current-truth promotion from ChatGPT.
