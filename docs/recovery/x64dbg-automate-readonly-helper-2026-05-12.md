# x64dbg Automate read-only helper setup and validation

Status date: 2026-05-12

## Verdict

The first safe x64dbg Automate port is now in place as a **read-only,
candidate-evidence helper**, not as an always-on Codex MCP debugger tool.

The helper can:

- run a no-live synthetic self-test;
- diff existing before/after snapshot JSON files;
- run a helper-owned harmless `winver.exe` smoke through x64dbg Automate;
- connect to an existing x64dbg session only when strict target identity is
  supplied;
- block RIFT live-debugger use unless explicitly authorized in the current
  conversation;
- emit JSON and Markdown summaries with blockers, warnings, artifacts, safety
  flags, and source links.

No Codex MCP x64dbg server was configured. That is intentional: the upstream MCP
server exposes raw debugger powers that include write, assembly, breakpoint,
thread, and execution-control operations.

## Timing

| Field | Value |
|---|---|
| Work package | Actions 1-10 from the x64dbg Automate MCP setup recommendation list |
| Measured start | 2026-05-12 16:44:58 EDT / 2026-05-12 20:44:58 UTC |
| Measured completion | 2026-05-12 16:55:57 EDT / 2026-05-12 20:55:57 UTC |
| Total measured duration | 10 minutes 59 seconds |
| Measurement basis | From first local setup operation for this package to final validation before commit/push |

## Completed action map

| # | Action | Result |
|---:|---|---|
| 1 | Build read-only `x64dbg_snapshot_diff.py` helper | Done: `scripts/rift_live_test/x64dbg_snapshot_diff.py` plus wrapper `scripts/x64dbg_snapshot_diff.py`. |
| 2 | Keep MCP unconfigured for now | Done: `codex mcp list` showed no x64dbg MCP entry after setup. |
| 3 | Add self-test / harmless target validation path | Done: `--self-test` is no-live synthetic; `--harmless-exe C:\Windows\System32\winver.exe --allow-harmless-exe` passed using x64dbg Automate. |
| 4 | Install `x64dbg_automate` in a dedicated venv | Done locally under `.riftreader-local\venvs\x64dbg-automate` with `x64dbg_automate==0.7.6`. This venv is intentionally git-ignored. |
| 5 | Install x64dbg Automate plugin when ready to test | Done for local x64 x64dbg: `x64dbg-automate.dp64` and `libzmq-mt-4_3_5.dll` copied to `C:\RIFT MODDING\Tools\x64dbg\release\x64\plugins`. |
| 6 | Add explicit blocked operations list | Done in helper summary safety: write, assembly, register write, breakpoint, execution, thread, raw command, attach, and anti-debug hiding methods are blocked. |
| 7 | Require PID/HWND/process-start identity | Done for `--connect-session`; RIFT additionally requires `--allow-live-debugger`. |
| 8 | Emit `status/blockers/warnings/artifacts/safety` JSON | Done: every run writes `summary.json`, `summary.md`, and when applicable snapshots/diff artifacts. |
| 9 | Only then add Codex MCP config | Intentionally deferred/not active. The safe wrapper exists, but Codex MCP remains unconfigured because upstream MCP still exposes write-class tools without repo-level allowlisting. |
| 10 | Never use MCP for live RIFT unless explicitly approved | Done as a helper gate and documented policy: RIFT live-debugger connect blocks without current-turn authorization. |

## Local setup facts

| Item | Value |
|---|---|
| x64dbg path | `C:\RIFT MODDING\Tools\x64dbg\release\x64\x64dbg.exe` |
| x64dbg launcher | `C:\RIFT MODDING\Tools\x64dbg\release\x96dbg.exe` |
| Python venv | `.riftreader-local\venvs\x64dbg-automate` |
| Python package | `x64dbg_automate==0.7.6` |
| Plugin release | `v0.6.1-green_pepe` |
| Plugin zip | `.riftreader-local\downloads\x64dbg-automate\release64-0.6.1-green_pepe.zip` |
| Plugin zip SHA256 | `AC90FB26FE20EE091536C1C3DE21BACBFCFBD47ED5A17392EA23AFDA1641A0CD` |
| Plugin files copied | `x64dbg-automate.dp64`, `libzmq-mt-4_3_5.dll` |
| Codex MCP x64dbg config | Not configured / not active |

## Validation artifacts

| Validation | Result | Artifact |
|---|---|---|
| Unit tests | Passed | `python scripts/test_x64dbg_snapshot_diff.py -v` |
| Synthetic self-test | Passed | `scripts\captures\x64dbg-snapshot-diff-20260512-205548-425508\summary.json` |
| Dry-run safety summary | Blocked as expected | `scripts\captures\x64dbg-snapshot-diff-20260512-205548-628632\summary.json` |
| RIFT live-debugger connect without approval | Blocked as expected | `scripts\captures\x64dbg-snapshot-diff-20260512-205548-829486\summary.json` |
| Helper-owned `winver.exe` x64dbg Automate smoke | Passed | `scripts\captures\x64dbg-snapshot-diff-20260512-205549-029439\summary.json` |
| Codex MCP list | Verified no x64dbg MCP entry | `rift_game`, `windows-mcp`, and `openaiDeveloperDocs` only |

Note: capture directories under `scripts\captures\` are generated artifacts and
are intentionally git-ignored.

## Helper usage

No-live self-test:

```powershell
python scripts\x64dbg_snapshot_diff.py --self-test --json
```

Offline file diff:

```powershell
python scripts\x64dbg_snapshot_diff.py --before <before.json> --after <after.json> --json
```

Harmless local x64dbg Automate smoke from the dedicated venv:

```powershell
.\.riftreader-local\venvs\x64dbg-automate\Scripts\python.exe scripts\x64dbg_snapshot_diff.py `
  --harmless-exe C:\Windows\System32\winver.exe `
  --allow-harmless-exe `
  --json
```

Existing x64dbg session connection requires exact target identity:

```powershell
.\.riftreader-local\venvs\x64dbg-automate\Scripts\python.exe scripts\x64dbg_snapshot_diff.py `
  --connect-session <X64DBG_DEBUGGER_PID> `
  --process-name <process-name> `
  --target-pid <target-pid> `
  --target-hwnd <target-hwnd> `
  --process-start-time-utc <process-start-utc> `
  --json
```

For `rift_x64`, the same command also requires `--allow-live-debugger` and
current-turn user authorization. Without it, the helper blocks before attempting
to connect.

## Safety model

| Category | Helper behavior |
|---|---|
| Movement/input | Never sent. |
| Cheat Engine | Not used. |
| Codex MCP | Not configured and not started. |
| Provider writes | Not performed. |
| GitHub connector writes | Not performed by helper. |
| x64dbg write-class operations | Blocked by design and listed in every summary. |
| Live RIFT debugger | Blocked unless explicitly authorized in the current conversation. |
| Evidence level | Candidate-only; not movement proof and not coordinate truth. |

Blocked operation classes include:

- memory writes and memset;
- memory allocation/protection/free;
- assembly/code patching;
- register writes;
- breakpoints;
- execution control;
- thread control;
- raw `cmd_sync`;
- direct process attach;
- debugger hiding;
- terminating non-owned sessions.

## Source references

| Source | Link |
|---|---|
| Cooking with x64dbg and MCP | https://x64.ooo/posts/2026-02-12-cooking-with-x64dbg-and-mcp/ |
| x64dbg Automate docs | https://dariushoule.github.io/x64dbg-automate-pyclient/ |
| x64dbg Automate installation | https://dariushoule.github.io/x64dbg-automate-pyclient/installation/ |
| x64dbg Automate quickstart | https://dariushoule.github.io/x64dbg-automate-pyclient/quickstart/ |
| x64dbg Automate MCP server | https://dariushoule.github.io/x64dbg-automate-pyclient/mcp-server/ |
| Debug control API | https://dariushoule.github.io/x64dbg-automate-pyclient/api/debug-control/ |
| Memory control API | https://dariushoule.github.io/x64dbg-automate-pyclient/api/memory-control/ |
| Registers and expressions API | https://dariushoule.github.io/x64dbg-automate-pyclient/api/registers-expressions/ |
| Assembler/disassembler API | https://dariushoule.github.io/x64dbg-automate-pyclient/api/assembler-disassembler/ |
| x64dbg Automate plugin releases | https://github.com/dariushoule/x64dbg-automate/releases |
| x64dbg Automate Python client on PyPI | https://pypi.org/project/x64dbg-automate/ |

## Next gate before active MCP

Do not add an active Codex MCP entry until one of these is true:

1. Codex supports a reliable per-tool allowlist/denylist for this MCP server; or
2. a repo-owned shim MCP server is built that exposes only the helper's
   read-only, fail-closed operations.

Until then, use the Python helper directly.

## Follow-on static coord-chain planner

The next integration layer is:

- helper: `C:\RIFT MODDING\RiftReader\scripts\x64dbg_coord_chain_plan.py`
- implementation:
  `C:\RIFT MODDING\RiftReader\scripts\rift_live_test\x64dbg_coord_chain_plan.py`
- tests: `C:\RIFT MODDING\RiftReader\scripts\test_x64dbg_coord_chain_plan.py`

This planner prepares the coordinate-chain packet and x64dbg session checklist
for a known current coordinate candidate. It does not attach x64dbg or perform
debugger actions; it exists to keep the static pointer-chain workflow
evidence-shaped before any approved live-debugger session.

## Follow-on offline access-event ingester

The next repo-owned bridge after a planned x64dbg session is:

- helper: `C:\RIFT MODDING\RiftReader\scripts\x64dbg_access_event_ingest.py`
- implementation:
  `C:\RIFT MODDING\RiftReader\scripts\rift_live_test\x64dbg_access_event_ingest.py`
- tests:
  `C:\RIFT MODDING\RiftReader\scripts\test_x64dbg_access_event_ingest.py`

This helper ingests manually captured x64dbg watchpoint/access-event JSON and
emits a candidate-only packet. It remains offline-only: no attach, no live
memory reads, no MCP server, no input, no movement, and no promotion to
coordinate truth. It blocks malformed input, missing target identity, non-12-byte
watch windows, API-vs-memory deltas outside tolerance, unsafe write-access
events, and instruction/module/RVA mismatches.

Use it only after a live-debugger session has been separately approved and the
operator has exported/recorded the manual event JSON:

```powershell
python C:\RIFT MODDING\RiftReader\scripts\x64dbg_access_event_ingest.py `
  --events-json <manual-x64dbg-access-events.json> `
  --candidate-id <candidate-id> `
  --json
```

The output still requires a later repo-owned chain resolver, API-now versus
chain-now comparison, multi-pose validation, restart validation, and same-target
ProofOnly before movement can use it.

## Follow-on offline static-chain resolver harness

The resolver harness is:

- helper: `C:\RIFT MODDING\RiftReader\scripts\x64dbg_static_chain_resolve.py`
- implementation:
  `C:\RIFT MODDING\RiftReader\scripts\rift_live_test\x64dbg_static_chain_resolve.py`
- tests:
  `C:\RIFT MODDING\RiftReader\scripts\test_x64dbg_static_chain_resolve.py`

It is schema/test ready but intentionally evidence-gated. It should only be used
with a real x64dbg-derived candidate packet that contains module/RVA or
static-owner provenance. It blocks placeholder templates, heap-only watch
addresses, missing current module bases, missing readback sources, and API-now
versus chain-now mismatches.

The current resolver harness performs offline memory-image readback only. It
does not attach x64dbg, read the live process, configure MCP, send input, or
promote movement truth.
