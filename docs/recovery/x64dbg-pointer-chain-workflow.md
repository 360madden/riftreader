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

The repo launcher `scripts\open-x64dbg.cmd` prefers this external install path
and falls back to the repo-local ignored staging path if needed.

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

## Discovery target

Start with one target only:

| Target | Reason |
|---|---|
| Player coordinate triplet `X/Y/Z` | Existing RiftReader gates already know how to compare memory-now against API-now. Stable coordinate chains unblock the highest-value workflow first. |

Do not mix coordinate, facing, camera, target, nameplate, and actor-list work in
the same first debugger session.

## Pre-attach checklist

Before opening a live-debugger session:

1. Identify the exact RIFT PID/HWND/process start time.
2. Capture a fresh API/runtime coordinate sample.
3. Capture the candidate memory address and current X/Y/Z values.
4. Confirm no other debugger-class tool is attached.
5. Confirm the session is discovery-only: no movement proof, no route execution,
   no process patching.
6. Prepare an output packet path under `scripts/captures/`.

## x64dbg session checklist

1. Launch:

   ```powershell
   & 'C:\RIFT MODDING\RiftReader\scripts\open-x64dbg.cmd'
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

## Stop conditions

Stop and write a blocker instead of continuing if:

- the target PID/HWND changes;
- API/runtime truth is stale or unavailable;
- the candidate only works for one pose;
- the chain root is heap-only with no stable owner;
- x64dbg or the target process becomes unstable;
- another debugger-class tool is already attached;
- the workflow would require process patching.
