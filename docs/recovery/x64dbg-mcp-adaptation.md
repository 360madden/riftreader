# x64dbg Automate MCP: Design Adaptation Note

Status date: 2026-05-12

## Verdict

The x64dbg MCP article is useful as a **design reference**, not as a drop-in
RiftReader workflow. Its recipes assume an AI agent that can directly drive x64dbg.
For this repo, port the reusable ideas into Python-first,
artifact-producing helpers behind the existing RiftReader live-debugger safety
gates.

No local install, live RIFT attach, debugger command, process patch, or movement
validation was performed while writing this note.

## Source index

Use these direct links as the durable reference set. Re-check the live pages
before installing or pinning any version.

| Source | Link | Use in RiftReader |
|---|---|---|
| Article: Cooking with x64dbg and MCP | https://x64.ooo/posts/2026-02-12-cooking-with-x64dbg-and-mcp/ | High-level recipe ideas: state snapshot/diff, trace-guided analysis, YARA scans, documentation-in-context. |
| x64dbg Automate docs home | https://dariushoule.github.io/x64dbg-automate-pyclient/ | Project overview for the plugin, Python client, and MCP support. |
| x64dbg Automate installation | https://dariushoule.github.io/x64dbg-automate-pyclient/installation/ | Install checklist for the plugin, Visual C++ runtime, Python client, and optional MCP extra. |
| x64dbg Automate quickstart | https://dariushoule.github.io/x64dbg-automate-pyclient/quickstart/ | Python client usage model to adapt into repo-owned scripts. |
| x64dbg Automate MCP server docs | https://dariushoule.github.io/x64dbg-automate-pyclient/mcp-server/ | MCP tool categories and configuration examples that must be adapted. |
| x64dbg Automate plugin source | https://github.com/dariushoule/x64dbg-automate | Native plugin/RPC server source and releases entry point. |
| x64dbg Automate Python client source | https://github.com/dariushoule/x64dbg-automate-pyclient | Python reference client, MCP entry point, examples, and docs source. |
| x64dbg Automate releases | https://github.com/dariushoule/x64dbg-automate/releases | Plugin release downloads; verify current release manually before install. |
| x64dbg skills repository | https://github.com/dariushoule/x64dbg-skills | Skill examples to translate into repo docs/scripts, not copy as-is. |
| x64dbg command reference | https://help.x64dbg.com/en/latest/ | Native command reference for any raw x64dbg command used by a helper. |
| Context7 | https://context7.com/ | Optional docs-in-context idea; verify availability in current tooling. |

## What the article contributes

| Article recipe / idea | Reusable concept | Mechanics to avoid copying verbatim |
|---|---|---|
| Decompile skill | Let the assistant summarize a current method or region after the debugger is oriented. | Custom skill packaging and prompts; examples assume the AI can already launch/control the session. |
| State snapshot and state diff | Capture register/memory state before and after a bounded event, then diff changes to infer behavior. | Free-form "run until return" control without a repo-owned safety envelope. |
| Tracealyze | Use trace logs to identify deobfuscation behavior, string references, imports, and candidate code/data relationships. | In-memory patching/assembly examples are not allowed in RiftReader discovery unless separately approved; default should be read-only trace analysis. |
| YARA signatures | Scan in-memory modules/snapshots for known primitives, packers, anti-debug patterns, or signatures. | Broad scan output without a RiftReader-owned JSON summary/blocker contract. |
| Context7/docs context | Pull current API and command docs into the workflow before using raw commands. | Assuming external context tools are always present. Use direct source links or local docs unless the tool is explicitly available. |

## RiftReader porting model

| Layer | Preferred RiftReader form | Notes |
|---|---|---|
| Operator entry point | Short docs plus a repo-owned Python helper under `scripts/` | Follow the repo Python-first helper policy; use `.cmd` only as a thin launcher if needed. |
| x64dbg control | Python `x64dbg_automate` client first | The Python client is the easiest piece to make reproducible and testable. |
| MCP access | Optional, gated, and client-specific | If the runtime exposes a compatible MCP configuration, adapt the command/env shape there; do not paste configuration examples blindly. |
| Skills | Translate into plain docs, Python modules, and agent skills | Keep skill logic explicit and repo-owned instead of relying on external skill names. |
| Outputs | JSON and Markdown summaries under `scripts/captures/` | Record status, blockers, warnings, process identity, commands, and artifact paths. |
| Validation | Existing API-now vs memory-now proof gates | x64dbg output remains candidate evidence until independently validated. |

## Required safety overlay for RiftReader

The article demonstrates powerful debugger automation. For RiftReader, keep the
following stricter boundary:

| Risk area | RiftReader rule |
|---|---|
| Live RIFT attach | Do not attach x64dbg to `rift_x64.exe` unless the user explicitly approves a live-debugger session in the current conversation. |
| Multiple debuggers | Do not use x64dbg and Cheat Engine debugger/watchpoints on the same live target at the same time. |
| Process mutation | Block `write_memory`, `assemble`, `set_register`, `create_thread`, raw patching, and file/process mutation by default. |
| Raw commands | Prefer typed Python client calls; if raw `execute_command` is unavoidable, cite the x64dbg command reference and record the command in the artifact. |
| Promotion | Treat all debugger observations as candidate evidence until fresh API/runtime comparison, multi-pose validation, restart validation, and `ProofOnly` pass. |
| Movement | Do not treat trace/snapshot success as movement permission. Movement remains behind the existing visual gate and proof-anchor gates. |

## Practical adaptation target

The first useful port should be a **read-only snapshot/diff helper** for a
known approved x64dbg session, not an autonomous live attach tool.

Minimum expected behavior:

1. Require explicit target identity: process name, PID, HWND, and process start
   time.
2. Refuse to start/attach to RIFT unless a deliberate `--allow-live-debugger`
   style gate is present.
3. Read debugger state only: registers, selected memory ranges, module list,
   selected disassembly, labels/comments.
4. Produce `snapshot-before.json`, `snapshot-after.json`,
   `snapshot-diff.json`, and a compact `snapshot-diff.md`.
5. Record every x64dbg/Python-client call in a command envelope.
6. Mark output as `candidate` unless the existing API-now vs memory-now
   validation is run separately and passes.

## Reusable helper design sketch

```text
scripts/x64dbg_snapshot_diff.py
  existing debugger session
  --pid <PID>
  --hwnd <HWND>
  --process-name rift_x64
  --output-dir scripts/captures/x64dbg-snapshot-diff-<timestamp>
  --read-only
  --no-patching
```

Expected summary contract:

```yaml
status: "passed | blocked | failed"
mode: "read-only"
tool: "x64dbg_automate"
process:
  name: "rift_x64"
  pid: 0
  hwnd: ""
  startTimeUtc: ""
safety:
  liveDebuggerApproved: false
  writeMemoryAllowed: false
  assembleAllowed: false
  registerWriteAllowed: false
  movementSent: false
blockers: []
warnings: []
artifacts:
  beforeJson: ""
  afterJson: ""
  diffJson: ""
  diffMarkdown: ""
sources:
  - "https://x64.ooo/posts/2026-02-12-cooking-with-x64dbg-and-mcp/"
  - "https://dariushoule.github.io/x64dbg-automate-pyclient/mcp-server/"
```

## Porting priorities

| Priority | Port | Why |
|---|---|---|
| 1 | Source/reference index and this adaptation note | Prevents future sessions from treating external examples as repo-ready commands. |
| 2 | Read-only snapshot/diff helper | Highest value, lowest mutation risk, aligns with article recipe 2. |
| 3 | Trace-log summarizer for an already-approved session | Useful for pointer-chain and owner/source discovery while staying evidence-first. |
| 4 | YARA-on-snapshot helper | Useful for anti-debug/packer/primitive awareness, but should not be on the movement critical path. |
| 5 | Optional MCP configuration experiment | Only after confirming current MCP support and keeping write-class tools blocked. |

## Implementation status: 2026-05-12

The first safe port is tracked here:

- helper: `C:\RIFT MODDING\RiftReader\scripts\x64dbg_snapshot_diff.py`
- implementation: `C:\RIFT MODDING\RiftReader\scripts\rift_live_test\x64dbg_snapshot_diff.py`
- tests: `C:\RIFT MODDING\RiftReader\scripts\test_x64dbg_snapshot_diff.py`
- setup/validation note:
  `C:\RIFT MODDING\RiftReader\docs\recovery\x64dbg-automate-readonly-helper-2026-05-12.md`

The helper is read-only and artifact-producing. It does not configure MCP.
An active x64dbg MCP entry remains deferred until write-class tools can be
blocked by configuration or by a repo-owned shim MCP server.

## Non-goals

- Do not install or update x64dbg Automate from this note alone.
- Do not run a live RIFT debugger attach from documentation work.
- Do not port in-memory patching examples into RiftReader discovery defaults.
- Do not claim x64dbg evidence is current coordinate truth without the existing
  proof gates.
