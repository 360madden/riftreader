# RiftReader ChatGPT MCP bounded repo command design

Stage: **32 — bounded command design spec**  
Status: **Stage 32 design complete-local; Stage 33 registry complete-local; no command tool exposed by this file**

This document defines the safety contract for a future
`run_bounded_repo_command` MCP tool. It is intentionally design-only: Stage 32
must not add arbitrary shell execution, a broad filesystem endpoint, live RIFT
control, provider repo writes, debugger access, or hidden Git mutation.

## Product intent

`run_bounded_repo_command` should let ChatGPT Web/Desktop run a small set of
repo-owned validation/status helpers after the operator selects a known command
key. It is not a terminal, not a shell, not a PowerShell paste surface, and not a
generic process launcher.

The command lane exists to reduce repeated local copy/paste for deterministic
checks such as MCP status, final-readiness status, selected unit tests, SDK
metadata validation, and current-head CI inspection.

## Stage split

| Stage | Scope | Must not do |
|---:|---|---|
| 32 | Design this contract. | Expose or run commands. |
| 33 | Implement a versioned allowlist registry. | Accept user-provided command strings. |
| 34 | Expose only the bounded command subset through MCP. | Add arbitrary shell/filesystem/live/provider/debugger routes. |
| 35 | Add durable command audit and replay evidence. | Let commands run without envelopes or output caps. |

## Proposed MCP tool shape

Tool name: `run_bounded_repo_command`

Planned arguments:

| Argument | Type | Rule |
|---|---|---|
| `commandKey` | string | Must exactly match a key in the versioned repo registry. |
| `parameters` | object | Optional typed values validated by the registry entry schema; unknown keys block. |
| `expectedRegistryVersion` | string | Optional optimistic binding so ChatGPT cannot unknowingly run a changed registry. |
| `approvalToken` | string | Required for non-read-only, long-running, or resource-heavy command entries. |
| `timeoutSeconds` | number | Optional lower-than-entry timeout override; cannot exceed registry maximum. |

The tool should return a structured command envelope, not free-form console text.

## Registry entry contract

Stage 33 should implement registry entries with this shape or an equivalent
strict Python dataclass/schema:

```json
{
  "key": "mcp_server_status",
  "registryVersion": "bounded-repo-command-registry-v1",
  "title": "MCP server status",
  "description": "Verify local ChatGPT MCP backend process and loaded tool surface.",
  "riskClass": "status-read",
  "readOnly": true,
  "requiresApprovalToken": false,
  "cwd": "repo-root",
  "argvTemplate": ["cmd", "/c", "scripts\\riftreader-mcp-server-status.cmd", "--json"],
  "parameterSchema": {"type": "object", "additionalProperties": false},
  "expectedExitCodes": [0, 2],
  "timeoutSeconds": 20,
  "maxStdoutBytes": 60000,
  "maxStderrBytes": 20000,
  "writesIgnoredArtifacts": false,
  "forbiddenIfDirty": false,
  "safetyFlags": {
    "gitMutation": false,
    "remoteMutation": false,
    "providerWrites": false,
    "inputSent": false,
    "movementSent": false,
    "x64dbgAttach": false
  }
}
```

Rules:

1. Registry keys are hardcoded in repo source, versioned, and tested.
2. `argvTemplate` is an array of fixed tokens; user input cannot inject extra
   shell fragments.
3. If an entry uses `cmd /c` for a `.cmd` wrapper, that exact wrapper path and
   fixed arguments must be registry-owned. No user-supplied `cmd`, PowerShell,
   shell string, `&&`, `|`, redirection, wildcard command, or arbitrary script
   path is allowed.
4. Python helpers are preferred for new workflow brains. `.cmd` wrappers remain
   thin launchers.
5. Every parameter is typed and rendered into argv through a bounded template
   function; unknown, null-where-not-allowed, oversized, or traversal-like
   values fail closed.
6. Registry entries must declare whether they can write ignored artifacts under
   `.riftreader-local`; tracked-source writes are not allowed through this lane.

## Initial allowed command families

Stage 33 now starts with a deliberately small local-only registry in
`tools/riftreader_workflow/bounded_repo_commands.py`.

Registry facts:

| Field | Value |
|---|---|
| Registry version | `bounded-repo-command-registry-v1` |
| CLI inspection | `python tools\riftreader_workflow\bounded_repo_commands.py --list --json` |
| CLI plan mode | `python tools\riftreader_workflow\bounded_repo_commands.py --plan mcp_server_status --json` |
| CLI self-test | `python tools\riftreader_workflow\bounded_repo_commands.py --self-test --json` |
| MCP exposure | Not exposed until Stage 34. |
| Command execution | Not implemented in Stage 33. |

Initial keys:

| Key | Command family | Why safe enough for first subset |
|---|---|---|
| `mcp_server_status` | `scripts\riftreader-mcp-server-status.cmd --json` | Read-only backend dependency truth, now checks live runtime surface. |
| `mcp_final_status` | `scripts\riftreader-mcp-final.cmd --status --compact-json` | Read-only final readiness gate. |
| `current_head_ci_status` | `python tools\riftreader_workflow\mcp_ci_status.py --status --json` | Read-only GitHub Actions inspection through existing helper. |
| `validate_mcp_sdk` | `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --validate-sdk --tool-profile full --json` | Local metadata validation; no persistent server or tunnel. |
| `test_mcp_server_status` | `python -m unittest scripts.test_mcp_server_status` | Focused unit test for runtime dependency guard. |

Do not include broad `unittest discover`, arbitrary `pytest`, generic `git`,
`pre-commit run --all-files`, live proof helpers, route helpers, provider repo
helpers, or any command with hidden mutation in the first subset.

## Forbidden command classes

The bounded command lane must deny these classes even if the operator asks for a
convenient shortcut:

| Class | Examples |
|---|---|
| Arbitrary shell | `cmd /c <user string>`, `powershell -Command <user string>`, `bash -c`, pipes, redirection, `&&`. |
| Arbitrary filesystem | User-chosen paths, recursive scans outside registry commands, broad read/write/delete/move. |
| Git mutation | `git add`, `commit`, `push`, `reset`, `clean`, `stash`, checkout/restore discard, branch rewrite. Use existing dedicated tools instead. |
| Live RIFT input | movement, target selection, `/reloadui`, screenshot key input, ProofOnly, route helpers. |
| Debugger/CE | x64dbg, Cheat Engine, breakpoints, watchpoints, attach flows. |
| Provider writes | ChromaLink/RiftScan or any repo outside RiftReader. |
| Proof promotion | actor-chain/current-truth/proof promotion. |
| Secret exposure | env dumps, credential file reads, token printing. |

## Execution envelope

Every Stage 34+ execution must produce a durable JSON envelope under a path such
as:

```text
.riftreader-local\riftreader-chatgpt-mcp\bounded-commands\<UTC>-<commandKey>\run-summary.json
```

Envelope fields:

| Field | Required content |
|---|---|
| `schemaVersion` | `1` |
| `kind` | `riftreader-bounded-repo-command-run` |
| `registryVersion` | Registry version used. |
| `commandKey` | Exact allowlist key. |
| `argv` | Final redacted argv array. |
| `cwd` | Repo root, redacted in MCP output. |
| `startedAtUtc` / `endedAtUtc` | UTC timestamps. |
| `durationSeconds` | Rounded duration. |
| `exitCode` | Child process exit code or null on timeout. |
| `timedOut` | Boolean. |
| `stdoutPreview` / `stderrPreview` | Capped previews with secrets redacted. |
| `stdoutSha256` / `stderrSha256` | Hashes when output exists. |
| `status` / `ok` / `blockers` / `warnings` | Structured verdict. |
| `safety` | Explicit mutation/input/provider/debugger flags. |

MCP output may be compact, but it must include the summary path, command key,
verdict, exit code, duration, capped previews, and safety flags.

## Approval-token policy

Stage 34 should treat command execution as a high-power MCP action even when the
first subset is read-only. Recommended policy:

- read-only, short status commands may run with current user confirmation in the
  ChatGPT UI and no local approval token;
- long-running tests, commands that write ignored artifacts, or commands with
  external network reads require a local preflight token;
- any tracked-source write, Git mutation, provider write, live RIFT action,
  debugger/CE action, or proof promotion is not eligible for this tool at all.

## Failure behavior

Fail closed when:

- the command key is unknown;
- the registry version does not match `expectedRegistryVersion`;
- any parameter is unknown, invalid, oversized, or not representable as a safe
  argv token;
- final argv contains a forbidden fragment;
- cwd is not the RiftReader repo root;
- timeout/output caps are missing;
- the child process times out;
- stdout/stderr cannot be captured and capped;
- safety flags cannot be computed;
- the worktree state violates an entry's declared dirty-worktree rule.

## Definition of done for later stages

| Stage | Required evidence |
|---:|---|
| 33 | Complete-local: registry code, tests for allowed keys, tests for denied destructive/live/provider/debugger classes. |
| 34 | MCP tool wrapper, argument allowlist, local adapter tests, actual connector denial proof for unknown command, and successful proof for one safe status command. |
| 35 | Durable audit/replay helper, tests for envelope contents, replay of at least one successful and one blocked command. |

## Safety statement

This design plus the Stage 33 registry keep the bounded command lane non-live
and non-mutating so far. It does not expose a command endpoint through MCP, run
allowlisted commands from ChatGPT, mutate Git, send RIFT input, attach
CE/x64dbg, write provider repos, or promote any proof/truth.
