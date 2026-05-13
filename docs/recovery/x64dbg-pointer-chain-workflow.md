# x64dbg pointer-chain discovery workflow

Status date: 2026-05-12

## Verdict

x64dbg is installed as a **local reverse-engineering workbench** for
stable pointer-chain discovery. It is not a runtime dependency and it is not a
movement-proof source by itself.

## Current local tool state

| Tool | Local path | Version / snapshot |
|---|---|---|
| x64dbg x64 | `C:\RIFT MODDING\Tools\x64dbg\release\x64\x64dbg.exe` | `2026.04.20` / `snapshot_2026-04-20_19-04.zip` |
| x64dbg launcher | `C:\RIFT MODDING\Tools\x64dbg\release\x96dbg.exe` | `2026.04.20` |
| x64dbg x32 | `C:\RIFT MODDING\Tools\x64dbg\release\x32\x32dbg.exe` | `2026.04.20` |

The repo launcher is Python-owned: `scripts\x64dbg_launcher.py` prefers this
external install path and falls back to the repo-local ignored staging path if
needed. `scripts\open-x64dbg.cmd` and `scripts\open-x64dbg.ps1` are compatibility
wrappers only. The launcher prints the live-attach guard before opening x64dbg;
run `python scripts\x64dbg_launcher.py --print-safety-only` to review the guard
without launching anything.

Repo-local reverse-engineering tool folders are intentionally git-ignored:

- `tools/reverse-engineering/downloads/`
- `tools/reverse-engineering/x64dbg/`
- `tools/reverse-engineering/ReClass.NET/`

## Refresh / verify

Preferred manual install/refresh target:

```text
C:\RIFT MODDING\Tools\x64dbg
```

Verify the external install:

```powershell
Test-Path 'C:\RIFT MODDING\Tools\x64dbg\release\x64\x64dbg.exe'
Test-Path 'C:\RIFT MODDING\Tools\x64dbg\release\x96dbg.exe'
Test-Path 'C:\RIFT MODDING\Tools\x64dbg\release\x32\x32dbg.exe'
Get-FileHash 'C:\RIFT MODDING\Tools\x64dbg\release\x64\x64dbg.exe' -Algorithm SHA256
```

Optional repo-local staging can also be refreshed with:

```powershell
& 'C:\RIFT MODDING\RiftReader\tools\reverse-engineering\install-tools.ps1'
```

Verify optional repo-local staging:

```powershell
Test-Path 'C:\RIFT MODDING\RiftReader\tools\reverse-engineering\x64dbg\release\x64\x64dbg.exe'
Test-Path 'C:\RIFT MODDING\RiftReader\tools\reverse-engineering\x64dbg\release\x96dbg.exe'
Test-Path 'C:\RIFT MODDING\RiftReader\tools\reverse-engineering\x64dbg\release\x32\x32dbg.exe'
Get-FileHash 'C:\RIFT MODDING\RiftReader\tools\reverse-engineering\downloads\snapshot_2026-04-20_19-04.zip' -Algorithm SHA256
```

Known current snapshot hash from the 2026-05-12 refresh:

```text
x64dbg.exe: 3E4EAB55DC9D73A36727D04E2B7BC0ED46E7D6CAEA3DFD82F3D0719C0DD86E6B
snapshot_2026-04-20_19-04.zip: 985561EA9FBD5E3CC557C9B5868EC608FCF450BFC88F0AC4A7279DED2A9CE7EC
```

## Safety boundary

Treat x64dbg as a debugger-class live tool.

| Rule | Required behavior |
|---|---|
| Live attach | Do not attach to `rift_x64.exe` unless the user explicitly approves a live-debugger session in the current conversation. |
| One debugger | Do not use Cheat Engine debugger/watchpoints and x64dbg against the same live target at the same time. |
| Normal runtime | Do not require x64dbg for normal RiftReader reads, navigation, or movement. |
| Promotion | Do not promote a pointer chain from x64dbg alone. It remains candidate evidence until validated against fresh API/runtime truth. |
| Movement | Keep movement/navigation blocked until chain-now vs API-now passes the existing proof gates. |
| Patching | Do not patch the game process or files as part of pointer-chain discovery. |
| Shell integration | Do not register shell extensions or system-wide integrations by default. |

## Live attach timeout / forced-logout guard

The May 12/13 x64dbg attach to RIFT PID `63412` froze the client long enough for
the player to be forced out/logged out. Future live debugger sessions must be
short, preplanned, and fail-closed:

| Guard | Required behavior |
|---|---|
| Preplanned commands | Prepare capture paths, exact addresses, and the detach path before attach. Do not plan while the game is paused. |
| Attach timer | Start a wall-clock timer before attach. Detach within 30-90 seconds unless the user explicitly approves extending the live-debugger window. |
| Unresponsive target | If RIFT is `Responding=False` for more than 15 seconds after attach or a `go/run` attempt, capture minimal stop context if already available and detach immediately. |
| `go/run` retries | Allow at most one `go/run` attempt by default. Do not loop `go/run`; do not use exception swallowing unless the stop reason is understood and the user explicitly approves. |
| Watchpoints | Do not set hardware watchpoints until the process can run predictably. |
| Relog/restart | After logout, relog, restart, or process-start change, mark all absolute heap/object addresses stale and reacquire current-PID evidence. |

## Discovery target

Start with one target only:

| Target | Reason |
|---|---|
| Player coordinate triplet `X/Y/Z` | Existing RiftReader gates already know how to compare memory-now against API-now. Stable coordinate chains unblock the highest-value workflow first. |

Do not mix coordinate, facing, camera, target, nameplate, and actor-list work in
the same first debugger session.

## Pre-attach checklist

Before opening a live-debugger session:

1. Identify the exact RIFT PID/HWND/process start time, responsiveness, and
   module base with the no-attach Python preflight:

   ```powershell
   python C:\RIFT MODDING\RiftReader\scripts\x64dbg_preflight.py --json
   ```

   For live-debugger readiness, fail closed unless the exact target is supplied
   and no known debugger-class process is open:

   ```powershell
   python C:\RIFT MODDING\RiftReader\scripts\x64dbg_preflight.py `
     --require-exact-target `
     --require-no-debugger-process `
     --target-pid <PID> `
     --target-hwnd <HWND> `
     --expected-start-time-utc <process-start-utc-from-last-packet> `
     --expected-module-base <module-base-from-last-packet> `
     --json
   ```

   The packet includes visible RIFT targets plus known debugger-class processes
   such as x64dbg and Cheat Engine. This preflight uses OS/window/process
   metadata only. It does not attach x64dbg, send input, set
   breakpoints/watchpoints, or read/write target memory bytes.
2. Capture a fresh API/runtime coordinate sample.
3. Capture the candidate memory address and current X/Y/Z values.
4. Confirm no other debugger-class tool is attached.
5. Confirm the session is discovery-only: no movement proof, no route execution,
   no process patching.
6. Prepare an output packet path under `scripts/captures/`.
7. Prebuild the exact read/watch commands and detach command before attach.
8. Define the hard detach timeout and the `Responding=False` abort threshold.

## x64dbg session checklist

1. Launch:

   ```powershell
   python 'C:\RIFT MODDING\RiftReader\scripts\x64dbg_launcher.py'
   ```

2. Attach only to the exact approved 64-bit `rift_x64.exe` target.
3. Set data breakpoints/watchpoints around the 12-byte coordinate triplet.
4. Exercise bounded, operator-controlled pose changes only if approved.
5. For each hit, record:
   - process PID/HWND/start time;
   - module name and module base;
   - instruction address and module-relative RVA;
   - instruction bytes and disassembly;
   - read/write/access type;
   - register values used to address the coordinate field;
   - derived object pointer and field offset;
   - current API coordinate and memory coordinate.
6. Prefer instructions and module-relative roots over heap-only addresses.
7. Stop after enough hits to explain the owner/source path; do not loop on weak
   hits without new evidence.

## Repo-owned coord-chain planner

Before any live x64dbg attach/watchpoint session, generate a bounded plan packet
from the current coordinate candidate and fresh API/runtime coordinate:

```powershell
python C:\RIFT MODDING\RiftReader\scripts\x64dbg_coord_chain_plan.py `
  --preflight-summary <x64dbg-target-preflight-summary.json-or-latest> `
  --api-coordinate-file <fresh-rift-api-reference-coordinate.json> `
  --candidate-file <coordinate-candidate.json> `
  --max-live-attach-seconds 30 `
  --unresponsive-abort-seconds 15 `
  --max-go-attempts 1 `
  --json
```

This planner is artifact-only: it does not attach x64dbg, set watchpoints, read
live memory, configure MCP, send movement/input, or promote a chain. It writes a
summary, a session checklist, and a candidate-packet template under
`scripts\captures\x64dbg-coord-chain-plan-*`. It also writes
`x64dbg-coordinate-chain-rerun-command.txt`, a copy-paste command that preserves
the resolved preflight/API artifact paths for handoff.

The summary includes a conservative `readiness` verdict. A planner `status` of
`planned` does not by itself mean live-debugger work should begin; the readiness
status must show `ready-for-current-turn-approval` before asking for approval, or
`approved-for-bounded-capture` only when explicit current-turn debugger approval
was already supplied to the planner.

If the target is `rift_x64` and no current-turn live-debugger authorization is
present, the planner still writes the packet but records a warning that live
attach is not authorized. Passing `--allow-live-debugger` only records that a
future session was approved for planning purposes; the planner still performs no
debugger actions.

Prefer `--preflight-summary` over manually copying PID/HWND/process-start
metadata. The planner imports the selected target from
`scripts\x64dbg_preflight.py` output and blocks if any explicitly supplied
target PID/HWND/start/module-base field disagrees with that preflight packet.

Use `--preflight-summary latest` only as a convenience inside the current repo
workspace. It resolves to the newest passed
`scripts\captures\x64dbg-target-preflight-*\summary.json` artifact, ignoring
blocked packets. For handoffs or audits, prefer the exact resolved path recorded
in the plan summary.

When manually planning without a preflight packet, pass `--module-base` if it is
known so the session checklist preserves the full process epoch. A preflight
packet remains preferred because it imports PID, HWND, process start time, and
module base together.

Prefer `--api-coordinate-file` over hand-copying `--api-x`, `--api-y`,
`--api-z`, and `--api-sampled-at-utc` when a fresh
`capture-rift-api-reference-coordinate.ps1` reference JSON is available. The
planner imports the coordinate and blocks if that artifact reports movement,
Cheat Engine usage, SavedVariables-as-live-truth, or a PID/HWND mismatch with
the selected preflight target.

Use `--api-coordinate-file latest` only when the planner already has an exact
target PID/HWND from `--preflight-summary` or explicit target arguments. The
alias resolves to the newest usable same-target
`scripts\captures\**\rift-api-reference-currentpid-*.json` artifact and blocks
instead of guessing if no matching PID/HWND artifact exists.

Prefer `--candidate-file` over hand-copying `--candidate-address` when a
candidate artifact is available. Single-candidate JSON files import directly.
Multi-candidate files must be paired with `--candidate-id`; otherwise the
planner blocks instead of guessing which address to watch.

The planner now emits the live-attach guard as machine-readable safety metadata:

- default live attach window: `30` seconds;
- hard maximum live attach window: `90` seconds;
- `Responding=False` abort threshold: `15` seconds;
- default `go/run` attempts: `1`;
- exception-swallow retry loops: blocked;
- collected debugger/debuggee identity must still match the approved target;
- detach first, analyze artifacts second.

Supplying values outside that guard blocks the plan packet instead of normalizing
an unsafe live-debugger workflow.

## Offline access-event ingester

After an explicitly approved x64dbg session produces manual watchpoint/access
events, normalize them with the repo-owned offline ingester:

```powershell
python C:\RIFT MODDING\RiftReader\scripts\x64dbg_access_event_ingest.py `
  --events-json <manual-x64dbg-access-events.json> `
  --candidate-id <candidate-id> `
  --max-delta 1.0 `
  --json
```

The ingester is artifact-only and offline-only. It parses a manual event JSON
file, validates target identity, a 12-byte `X/Y/Z` watch window, API-now versus
memory-now deltas, pose count, instruction provenance, and write-class hazards.
It writes:

- `summary.json`
- `summary.md`
- `normalized-access-events.json`
- `x64dbg-coordinate-chain-candidate.json`

under `scripts\captures\x64dbg-access-event-ingest-*`.

It does **not** attach x64dbg, read live process memory, configure MCP, send
input, or promote movement truth. A `passed` ingest only means a candidate packet
was generated from structurally valid events. The emitted candidate remains
blocked for movement until a separate repo-owned chain readback and proof gate
promote it.

Minimal manual event input shape:

```json
{
  "schemaVersion": 1,
  "kind": "x64dbg-manual-access-events",
  "capturedAtUtc": "2026-05-12T21:00:00Z",
  "process": {
    "name": "rift_x64",
    "pid": 63412,
    "hwnd": "0xB70082",
    "startTimeUtc": "2026-05-12T15:53:24Z"
  },
  "watchWindow": {
    "baseAddress": "0x78BF4FE420",
    "sizeBytes": 12,
    "axisOrder": "xyz",
    "axisOffsets": {
      "x": "0x0",
      "y": "0x4",
      "z": "0x8"
    }
  },
  "events": [
    {
      "eventId": "pose-001-hit-001",
      "poseId": "pose-001",
      "hitAtUtc": "2026-05-12T21:00:05Z",
      "targetStillMatched": true,
      "access": "read",
      "truthSurface": {
        "kind": "api-now",
        "source": "fresh-api-runtime-coordinate",
        "sampledAtUtc": "2026-05-12T21:00:05Z",
        "x": 7376.87,
        "y": 863.82,
        "z": 2990.35
      },
      "memoryNow": {
        "address": "0x78BF4FE420",
        "sampledAtUtc": "2026-05-12T21:00:05Z",
        "x": 7376.86,
        "y": 863.83,
        "z": 2990.35
      },
      "instruction": {
        "module": "rift_x64.exe",
        "moduleBase": "0x140000000",
        "address": "0x141234567",
        "rva": "0x1234567",
        "bytes": "F30F1001",
        "disassembly": "movss xmm0, dword ptr [rcx]",
        "access": "read",
        "registers": {
          "rcx": "0x78BF4FE420"
        },
        "derivedObjectPointer": "0x78BF4FE420",
        "fieldOffset": "0x0"
      }
    }
  ]
}
```

Static-chain integration order:

1. produce a coord-chain plan from a current candidate and fresh API/runtime
   coordinate;
2. collect x64dbg access events only after explicit current-turn debugger
   approval;
3. ingest those events offline into a candidate packet;
4. derive a module/RVA/static-owner chain hypothesis;
5. resolve that chain with a repo-owned non-x64dbg readback helper;
6. compare chain-now to fresh API-now across multiple poses;
7. restart/relog and validate the same chain shape again;
8. pass the existing same-target proof gate before any movement/navigation use.

Do **not** implement or promote a resolver from the candidate template,
heap-only watch address, or guessed offsets. Resolver input must contain real
x64dbg-derived module/RVA or static-owner provenance tied back to captured event
IDs.

## Offline static-chain resolver harness

After real x64dbg access events have been ingested and a `derivedChain` has been
filled with module/RVA/static-owner provenance, the repo-owned resolver harness
can validate the chain shape without x64dbg:

```powershell
python C:\RIFT MODDING\RiftReader\scripts\x64dbg_static_chain_resolve.py `
  --candidate-json <x64dbg-coordinate-chain-candidate.json> `
  --module-map-json <current-module-map.json> `
  --memory-image-json <offline-memory-image.json> `
  --json
```

The current implementation is intentionally limited:

- no x64dbg attach;
- no MCP server;
- no process memory reads;
- no input or movement;
- offline memory-image readback only;
- `movementProofEligible=false` in all outputs.

It fails closed when the packet lacks `derivedChain.module`,
`derivedChain.rootRva`, offsets, field offsets, current module base, readback
source, or API-now versus chain-now agreement. A successful self-test only proves
the resolver contract and pointer-walk convention; it does not prove any live
RIFT coordinate chain.

## Candidate packet contract

Write debugger-derived candidates as explicit candidate evidence, for example:

```json
{
  "status": "candidate",
  "tool": "x64dbg",
  "capturedAtUtc": "",
  "process": {
    "name": "rift_x64",
    "pid": 0,
    "hwnd": "",
    "startTimeUtc": ""
  },
  "truthSurface": {
    "kind": "api-now",
    "sampledAtUtc": "",
    "x": 0.0,
    "y": 0.0,
    "z": 0.0
  },
  "memoryNow": {
    "address": "",
    "x": 0.0,
    "y": 0.0,
    "z": 0.0
  },
  "instruction": {
    "module": "rift_x64.exe",
    "moduleBase": "",
    "address": "",
    "rva": "",
    "bytes": "",
    "disassembly": "",
    "access": "read | write | access"
  },
  "derivedChain": {
    "root": "module+rva | pending",
    "offsets": [],
    "fieldOffset": ""
  },
  "validation": {
    "samePoseDelta": null,
    "multiPose": false,
    "restartValidated": false,
    "movementProofEligible": false
  },
  "blockers": [
    "not-restart-validated",
    "not-promoted-through-api-now-vs-chain-now"
  ]
}
```

## Promotion gates

A chain can move from `candidate` to `proof-candidate` only when all are true:

| Gate | Required evidence |
|---|---|
| Same target | PID/HWND/process-start identity recorded for each sample. |
| API comparison | Fresh API/runtime coordinate and chain-read coordinate sampled close together. |
| Multi-pose | Same chain tracks X/Y/Z across multiple displaced poses. |
| Module-relative root | Chain root is expressible from module base/RVA or a stable static owner path, not only a heap address. |
| Restart validation | Same chain shape works after relog/restart/client epoch change. |
| Runtime helper | Repo-owned Python/C# readback can resolve the chain without x64dbg. |
| Movement gate | Existing proof-only/readback gate accepts the chain before any movement/navigation use. |

The current repo-owned integration intentionally separates evidence levels:

| Level | Meaning | Movement allowed |
|---|---|---|
| `candidate` | Manual x64dbg events were normalized and are structurally usable for follow-up chain work. | No |
| `proof-candidate` | A repo-owned resolver can read chain-now and compare against API-now across poses. | No |
| promoted proof anchor | Restart validation and same-target ProofOnly pass. | Only through the existing movement gate |

## Stop conditions

Stop and write a blocker instead of continuing if:

- the target PID/HWND changes;
- API/runtime truth is stale or unavailable;
- the candidate only works for one pose;
- the chain root is heap-only with no stable owner;
- x64dbg or the target process becomes unstable;
- RIFT is `Responding=False` for more than 15 seconds after attach or `go/run`;
- the live attach window reaches 30-90 seconds without an explicit extension;
- another debugger-class tool is already attached;
- the workflow would require process patching, memory writes, or movement.
