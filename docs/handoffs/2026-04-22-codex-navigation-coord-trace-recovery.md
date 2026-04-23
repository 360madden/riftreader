# Handoff - April 22, 2026 - navigation coord-trace recovered, actor-facing still blocked

> **Historical / superseded note:** this handoff records the April 22 recovery
> state only. For the living recovery workflow and current truth, see
> `docs/recovery/rebuild-runbook.md` and `docs/recovery/current-truth.md`.

## Verdict

The navigation-side trace stack is working again on the current live `rift_x64`
session, but canonical actor-facing truth is still blocked by a stale
behavior-backed lead from the earlier session.

What is re-proven on the current PID:

- coord trace
- coord anchor
- source chain
- source accessor family
- selector-owner trace

What is still **not** re-proven on the current PID:

- behavior-backed actor-facing lead
- canonical live actor-facing capture
- post-repair movement smoke

## Live session state at handoff time

| Item | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `navigation` |
| HEAD | `8af3e65` (`Harden coord-trace refresh recovery`) |
| Rift PID | `63012` |
| Rift start | `2026-04-22 03:13:46 -04:00` |
| Rift state | responding |
| CE PID | `64612` |
| CE process | `cheatengine-x86_64-SSE4-AVX2` |
| CE start | `2026-04-22 04:21:06 -04:00` |
| CE state | responding |
| Working tree | clean |

## What changed in the repo in this pass

| File | Change |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\read-player-current.ps1` | coord-trace refresh now explicitly uses `-WatchMode access -StimulusMode AutoHotkey` |
| `C:\RIFT MODDING\RiftReader\scripts\capture-player-trace-cluster.ps1` | cluster refresh now uses the working access/AHK trace path and briefly retries if current-player is not ready after `/reloadui` |
| `C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1` | timeout error now recommends rerunning with `-WatchMode access -StimulusMode AutoHotkey` when the older write/PostMessage path stalls |
| `C:\RIFT MODDING\RiftReader\docs\recovery\rebuild-runbook.md` | documented the working coord-trace combo and the post-`/reloadui` current-player readiness caveat |

## Root cause of the coord-trace recovery failure

The main false blocker on the current build was **not** the trace instruction
itself. The older default path could still arm breakpoints successfully while
never producing a verified hit.

The working live recovery path on the current client is:

```powershell
C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1 -Json -WatchMode access -StimulusMode AutoHotkey
```

There was also a smaller race right after `/reloadui`, where trace-cluster
refresh could run before grouped player families and player coordinates were
available again from the saved-variable exports.

## Fresh proof recovered on the current session

### 1. Coord trace

Successful live trace result:

- artifact: `C:\RIFT MODDING\RiftReader\scripts\captures\player-coord-write-trace.json`
- verification method: `coord-triplet-access`
- current verified instruction: `0x7FF70A29560E`
- current instruction text: `movss xmm0,[rsi+0000015C]`
- matched displacement: `0x15C`
- inferred coord base relative offset: `0x158`
- source object register value: `0x12CF76F70B0`

### 2. Coord trace cluster

Successful refreshed cluster:

- artifact: `C:\RIFT MODDING\RiftReader\scripts\captures\player-coord-trace-cluster.json`
- current cluster pattern address: `0x7FF70A2955F9`
- current interesting coord instructions include:
  - `movsd [rsi+00000158],xmm0`
  - `mov [rsi+00000160],eax`
  - `movss [rsi+00000158],xmm0`
  - `movss [rsi+0000015C],xmm0`
  - `movss [rsi+00000160],xmm0`

### 3. Source chain

Successful refreshed source chain:

- artifact: `C:\RIFT MODDING\RiftReader\scripts\captures\player-source-chain.json`

| Step | Current value |
|---|---|
| Source container load | `0x7FF70A2955C3` → `mov rcx,[rax+78]` |
| Selected-source load | `0x7FF70A2955C7` → `mov rdi,[rcx+rdx*8]` |
| Source resolve call | `0x7FF70A2955D7` |
| Source resolve target | `0x7FF709FEA040` |
| Current selected source | `0x12CF76F70B0` |

### 4. Source accessor family

Successful refreshed accessor family:

- artifact: `C:\RIFT MODDING\RiftReader\scripts\captures\player-source-accessor-family.json`

| Accessor | Meaning on current live source |
|---|---|
| `lea rax,[rbx+48]` | coord lane |
| `lea rax,[rbx+88]` | duplicate coord lane |
| `lea rax,[rbx+60]` | transform-like / facing row |
| `lea rax,[rbx+94]` | duplicate transform-like / facing row |

Current confirmed accessor starts:

- `0x7FF709FE9FD0` → `+0x60`
- `0x7FF709FE9FF0` → `+0x94`
- `0x7FF709FEA020` → `+0x88`
- `0x7FF709FEA040` → `+0x48`

### 5. Selector-owner trace

Successful refreshed selector-owner trace:

- artifact: `C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.json`

| Item | Current value |
|---|---|
| Trigger instruction | `0x7FF70A2955C7` |
| Owner object | `0x12C9769C810` |
| Owner container | `0x12C944EC320` |
| Selector index | `6` |
| Selected source | `0x12CF76F70B0` |
| Matches coord-trace source | true |

## Artifact freshness from this recovery pass

| Artifact | Last write time |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-coord-write-trace.json` | `2026-04-22 05:32:14 -04:00` |
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-coord-trace-cluster.json` | `2026-04-22 05:33:56 -04:00` |
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-source-accessor-family.json` | `2026-04-22 05:34:54 -04:00` |
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-source-chain.json` | `2026-04-22 05:35:09 -04:00` |
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.json` | `2026-04-22 05:35:37 -04:00` |
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json` | `2026-04-22 05:36:44 -04:00` |

## What is still blocked

### 1. Canonical actor-facing lead is stale for the current PID

Canonical live capture still fails closed:

- command:
  `C:\RIFT MODDING\RiftReader\scripts\capture-actor-orientation.ps1 -Json -ProcessName rift_x64`
- behavior-backed lead file:
  `C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json`
- current stale-lead error:
  - lead timestamp: `2026-04-22T04:42:26.0060098+00:00`
  - current process start: `2026-04-22T07:13:46.8244103Z`

The promoted April 22 truth still points to the earlier validated session:

| Field | Value |
|---|---|
| SourceAddress | `0x24F595F8D10` |
| BasisForwardOffset | `0x60` |
| BasisDuplicateForwardOffset | `0x94` |
| Status | `preferred-solved-lead` |

That lead remains historically important, but it is no longer current-session
safe for PID `63012`.

### 2. Legacy actor-orientation still remains diagnostic only

The bypass path still reads the refreshed owner/source artifacts:

- command:
  `C:\RIFT MODDING\RiftReader\scripts\capture-actor-orientation.ps1 -Json -ProcessName rift_x64 -IgnoreBehaviorBackedLead -RefreshOwnerComponents`

Current diagnostic result from that path:

| Item | Value |
|---|---|
| Selected source | `0x12CF76F70B0` |
| Preferred basis | `Basis60` |
| Basis offsets seen | `0x60` and `0x94` |
| Current diagnostic yaw | `-8.678004047755026` |
| `Coord48` matches player coords | false |
| `Coord88` matches player coords | false |

Most important mismatch from that capture:

| Item | Value |
|---|---|
| Player coords | `7234.2700 / 818.4000 / 3226.6899` |
| Source `Coord48` | `7232.8784 / 818.4040 / 3235.8411` |

So the source/accessor family is live and readable, but it is still **not**
safe to promote as the current canonical actor-facing source without fresh
behavior-backed validation.

### 3. Current-player can still require a fresh export before more live work

At handoff creation time, a plain:

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-current --json
```

was again failing because the saved-variable exports no longer exposed grouped
player families / player coordinates.

Earlier in the same recovery pass, `read-player-current.ps1 -Json -RefreshTraceAnchor`
recovered successfully after forcing a real `/reloadui`, so future live work
should assume that another refresh may be needed before continuing.

## Why movement is still blocked

Movement smoke should remain blocked until:

1. the behavior-backed lead is rebuilt for PID `63012`
2. actor-facing truth is re-proven on the same live session
3. native / PowerShell orientation parity is rerun on the rebuilt lead

Until then, the navigation branch has a recovered trace stack but not a
trustworthy current-session facing source.

## Top 10 recommended next actions

| # | Priority | Action | Why |
|---:|---|---|---|
| 1 | P0 | Rebuild `C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json` for the current `rift_x64` PID `63012` | This is the main remaining blocker |
| 2 | P0 | Run a clean controlled turn validation on `0x12CF76F70B0` using the refreshed `+0x60` and `+0x94` accessor-family lanes | This is the shortest path to re-proving or rejecting the current selected source |
| 3 | P1 | Compare `C:\RIFT MODDING\RiftReader\scripts\trace-player-selector-owner.ps1` output against `C:\RIFT MODDING\RiftReader\scripts\capture-actor-orientation.ps1 -IgnoreBehaviorBackedLead` during the same no-movement window | The current source trace works, but the later actor-orientation bypass capture still drifts |
| 4 | P1 | Rerun `C:\RIFT MODDING\RiftReader\scripts\navigation\assert-orientation-reader-parity.ps1 -Json -ProcessName rift_x64` only after the lead is rebuilt | Parity matters again once canonical truth is restored |
| 5 | P1 | Keep starting live recovery from `C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1 -Json -WatchMode access -StimulusMode AutoHotkey` | That is the currently proven coord-trace recovery combo |
| 6 | P1 | Add the same short current-player-ready retry behavior to any remaining script that refreshes coord trace immediately after `/reloadui` | The reload race was proven real in this pass |
| 7 | P1 | Regenerate `C:\RIFT MODDING\RiftReader\scripts\navigation\smoke-test-waypoints.json` only after actor-facing truth is back | Smoke routes should not be generated from noncanonical facing data |
| 8 | P1 | Run navigation preflight before any movement once the rebuilt lead is in place | Movement proof should stay downstream of canonical facing proof |
| 9 | P2 | Save a second CE `.ct` snapshot immediately after current-session facing truth is re-proven | That will preserve the next high-value live truth state |
| 10 | P2 | Push commit `8af3e65` upstream once this recovery baseline is ready to share | The repo-side coord-trace hardening is complete and clean |
