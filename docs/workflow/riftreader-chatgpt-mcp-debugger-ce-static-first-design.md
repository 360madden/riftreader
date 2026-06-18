# RiftReader ChatGPT MCP Debugger/CE static-first design

Status: **Stage 45 plan-only surface implemented**. This document defines the
debugger/Cheat Engine boundary for Stage 45-46 work. Stage 45 exposes
`plan_debugger_ce_action` only; it does not expose a ChatGPT MCP attach tool,
does not start x64dbg or Cheat Engine, does not read or write target process
memory, and raises the full MCP surface to 39 tools.

## Purpose

Debugger and Cheat Engine workflows have the highest local blast radius after
live movement/control. Stage 44 makes the default route explicit:

1. prefer offline/static evidence first;
2. keep candidate evidence candidate-only;
3. make plan-only guidance the next MCP surface, not attach execution;
4. require explicit current-turn approval and crash-risk disclosure before any
   future attach/watchpoint/breakpoint assistance.

## Current hard boundary

| Boundary | Rule |
|---|---|
| Current MCP surface | Stage 45 raises this to a 39-tool Cloudflare named Tunnel proof contract by adding `plan_debugger_ce_action`. No attach/CE execution tool is exposed. |
| x64dbg | Must not be launched, attached, scripted, or used for breakpoints/watchpoints by this stage. |
| Cheat Engine | Must not be launched, attached, connected through Lua/pipe, or used for scans by this stage. |
| Target memory | No target process memory read/write is authorized by this design doc. Existing read-only memory helpers remain separate repo workflows and are not exposed as debugger/CE MCP tools. |
| Live RIFT input | No movement, input, target selection, `/reloadui`, screenshot key, or stimulus is authorized by this stage. |
| Provider writes | No ChromaLink/RiftScan/provider writes are authorized. |
| Truth promotion | No current-truth, actor-chain, coordinate, yaw/facing, proof-anchor, or provider proof promotion is authorized. |

## Static-first evidence order

| Priority | Evidence source | Allowed in Stage 44 | Notes |
|---:|---|---|---|
| 1 | Tracked source and docs | Yes | Read only; use tracked context tools or local repo inspection. |
| 2 | Existing ignored artifacts | Yes, bounded | Read only from known repo-owned artifact roots when a later plan-only tool is added. |
| 3 | Existing offline disassembly/static exports | Yes, bounded | Prefer Ghidra/static exports and prior summaries over attaching a debugger. |
| 4 | Existing no-input readback/proof summaries | Yes, bounded | Candidate-only unless separate proof-promotion gates pass. |
| 5 | New plan-only debugger/CE guidance | Stage 45 only | May write ignored plan artifacts but must not attach. |
| 6 | Live debugger/CE attach/watchpoint/breakpoint | Stage 46+ only | Requires explicit approval, exact target binding, crash-risk disclosure, logging, and candidate-only default. |

## Required Stage 45 plan-only envelope

The `plan_debugger_ce_action` plan-only surface returns:

| Field | Required behavior |
|---|---|
| `schemaVersion`, `kind`, `status`, `ok` | Standard MCP response identity and pass/block state. |
| `riskClass` | One of `static-review`, `artifact-review`, `candidate-triage`, `debugger-attach-plan`, `ce-attach-plan`, or `blocked`. |
| `targetBinding` | Exact PID/HWND/process-start/module facts if the plan references a live target; no live attach is implied. |
| `staticFirstChecklist` | Offline/static alternatives that must be attempted or explicitly waived before attach. |
| `requestedAction` | Human-readable attach/watchpoint/breakpoint/scan intent, maximum duration, and stop condition. |
| `approvalPacket` | Human/operator prompt bound to target, action, crash risk, and plan hash; never a reusable broad token. |
| `recommendedVerification` | Read-only post-plan checks and expected artifacts. |
| `blockers`, `warnings`, `safety` | Fail-closed reasons and explicit safety truth. |

The plan-only surface may write ignored artifacts under a dedicated
`.riftreader-local\riftreader-chatgpt-mcp\debugger-ce-plans\*` root. It must not
execute input, launch debuggers, connect CE, set breakpoints/watchpoints, read
arbitrary files, or promote truth.

## Stage 45 implementation contract

| Item | Stage 45 behavior |
|---|---|
| Tool | `plan_debugger_ce_action` in the full MCP profile only. |
| Artifact root | `.riftreader-local\riftreader-chatgpt-mcp\debugger-ce-plans\*`. |
| Allowed risks | `static-review`, `artifact-review`, `candidate-triage`, `debugger-attach-plan`, `ce-attach-plan`, and blocked classifications. |
| Attach execution | Not exposed; `executionReadiness.canExecuteFromThisTool=false`. |
| Approval | Produces a human prompt/fingerprint only, never a reusable broad token. |
| Safety truth | `inputSent=false`, `movementSent=false`, `noCheatEngine=true`, `x64dbgAttach=false`, `debuggerAttached=false`, `breakpointsSet=false`, `watchpointsSet=false`, and `targetMemoryBytesWritten=false`. |

## Required Stage 46 gated-assist preconditions

Any future execution-capable debugger/CE assist must fail closed unless all
preconditions pass:

| Gate | Required fact |
|---|---|
| Explicit current-turn approval | The operator approves this exact target, action, crash risk, duration, and plan hash. |
| Exact target identity | PID, HWND, process start, module base, and image path match the plan. |
| Crash-risk disclosure | Response states that attach/watchpoints/breakpoints can crash, pause, or destabilize the client. |
| Static-first review | Plan records why static/offline evidence is insufficient for this narrowed question. |
| Bounded action | Maximum attach duration, watchpoint/breakpoint count, and stop condition are explicit. |
| Candidate-only default | New addresses/chains remain candidate-only; no promotion occurs in the attach lane. |
| Audit artifacts | Every action writes ignored local JSON/Markdown run envelopes before returning success. |

## Fail-closed blocker codes

| Code | Meaning |
|---|---|
| `DEBUGGER_TOOL_NOT_EXPOSED` | Stage 44 does not expose a debugger/CE MCP tool. |
| `DEBUGGER_STATIC_FIRST_REQUIRED` | Offline/static evidence has not been reviewed or waived. |
| `DEBUGGER_TARGET_NOT_BOUND` | Plan references live attach but lacks exact target identity. |
| `DEBUGGER_TARGET_DRIFT` | PID/HWND/start/module facts changed after planning. |
| `DEBUGGER_APPROVAL_MISSING` | Current-turn approval is absent. |
| `DEBUGGER_APPROVAL_MISMATCH` | Approval does not bind to this exact target/action/plan. |
| `DEBUGGER_CRASH_RISK_NOT_ACKNOWLEDGED` | Operator has not acknowledged crash/pause risk. |
| `DEBUGGER_STOP_CONDITION_MISSING` | Plan lacks duration or stop condition. |
| `DEBUGGER_BACKEND_UNAVAILABLE` | The approved local backend is not available. |
| `DEBUGGER_PROMOTION_FORBIDDEN` | Request tries to promote truth from debugger/CE evidence. |

## Safety truth required in every future response

Every future debugger/CE response, including blocked responses, must include:

```yaml
movementSent: false
inputSent: false
reloaduiSent: false
screenshotKeySent: false
noCheatEngine: true # false only inside a separately approved CE attach run
x64dbgAttach: false # true only inside a separately approved x64dbg attach run
debuggerAttached: false
breakpointsSet: false
watchpointsSet: false
targetMemoryBytesWritten: false
providerWrites: false
savedVariablesUsedAsLiveTruth: false
truthPromotionPerformed: false
```

Stage 44 itself must always preserve `noCheatEngine=true`,
`x64dbgAttach=false`, `debuggerAttached=false`, `breakpointsSet=false`,
`watchpointsSet=false`, and `targetMemoryBytesWritten=false`.

## Non-goals

- No public ChatGPT MCP live debugger tool.
- No arbitrary shell or arbitrary filesystem helper.
- No CE Lua pipe/control endpoint.
- No x64dbg command endpoint.
- No watchpoint/breakpoint execution.
- No live movement/input or target-control coupling.
- No proof/current-truth/provider promotion.
