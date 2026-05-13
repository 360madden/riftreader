# x64dbg live-attach incident and hard safety update

Incident window: 2026-05-12 evening EDT / 2026-05-13 UTC  
Repo: `C:\RIFT MODDING\RiftReader`

## Verdict

The x64dbg live attach to RIFT PID `63412` froze the client long enough that the
player was forced out/logged out. Treat all PID `63412` absolute addresses from
that debug epoch as historical candidate evidence only.

No coordinate candidate was promoted. No stable static pointer chain was found.

## What is stale now

The following evidence is no longer current-session truth after logout/relogin:

| Evidence | Status |
|---|---|
| PID `63412`, HWND `0xB70082`, process start `2026-05-12T15:53:24.4410214Z` | Historical debug epoch only |
| Coordinate candidate `0x20005B30800` | Historical access-proven candidate only |
| Observed owner/base `0x20005B304E0` | Historical owner relationship only |
| Owner fields `+0x320/+0x324/+0x328` | Historical field-shape clue only |
| Pointer scan `pointer-scan-owner-0x20005B304E0.json` | Historical/truncated scan; not current root evidence |

These values can guide future shape hypotheses, but they must not be used as
live/current addresses after the relog.

## New live process observed after relog

Observed without debugger attach, input, or memory writes:

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `79184` |
| HWND | `0xA90BFC` |
| Process start UTC | `2026-05-13T00:43:12.0808119Z` |
| Main module base | `0x7FF796B50000` |
| Responding | `True` at inspection |

No new coordinate proof, memory candidate, or static chain has been captured for
this PID.

## Incident artifacts preserved

Local ignored artifacts:

| Artifact | Meaning |
|---|---|
| `scripts/captures/x64dbg-stop-context-20260513-003938/summary.json` | Stop-context capture summary and detach result |
| `scripts/captures/x64dbg-stop-context-20260513-003938/summary.md` | Human-readable incident summary |
| `scripts/captures/x64dbg-stop-context-20260513-003938/stop-context.json` | Read-only debugger state, registers, code bytes, disassembly |

Tracked handoff checkpoint:

| Commit/path | Meaning |
|---|---|
| `302da88` | `Add static coord pointer-chain handoff` |
| `docs/handoffs/2026-05-12-193321-stable-static-coord-pointer-chain-handoff.md` | Pre-incident static-chain resume handoff; now historical for PID `63412` addresses |

## Root cause / failure mode

The debugger attach paused RIFT. `go/run` returned success through Automate, but
x64dbg immediately stopped again. The target stayed `Responding=False` long
enough for the online session to be forced out/logged out.

Captured stop context before detach:

| Field | Value |
|---|---|
| x64dbg PID | `81780` |
| Debuggee PID | `63412` |
| `is_debugging` | `true` |
| `is_running` | `false` |
| Stopped module from title | `kernelbase.dll` |
| Thread from title | `75096` |
| CIP/RIP | `0x7FFC707F79DA` |
| Latest Automate debug event | `None` from the new client queue |

## Hard future rule

For any future RIFT x64dbg live attach:

1. Prepare every command, capture path, and expected read before attaching.
2. Start an explicit attach timer before launching/attaching x64dbg.
3. If RIFT is `Responding=False` for more than 15 seconds after attach or after
   a `go/run` attempt, capture minimal stop context if already available and
   detach immediately.
4. Permit at most one `go/run` attempt unless the user explicitly approves a
   longer debugger session after seeing the stop reason.
5. Never use exception-swallowing as a retry loop.
6. Do not set hardware watchpoints until the process can run predictably.
7. Detach within 30-90 seconds unless the user explicitly approves extending the
   attach window.
8. After logout/relog/restart, mark all absolute heap/object addresses stale.

## Repo reintegration status

The x64dbg planning/snapshot lane has been reintegrated as guarded tooling, not
as an open-ended live-debugger lane:

- `scripts/rift_live_test/x64dbg_safety.py` defines the shared live-attach
  guard: 30-second default window, 90-second hard maximum, 15-second
  `Responding=False` abort threshold, and one default `go/run` attempt.
- `scripts/rift_live_test/x64dbg_coord_chain_plan.py` emits that guard in every
  plan/checklist and blocks unsafe guard values.
- `scripts/rift_live_test/x64dbg_snapshot_diff.py` carries the same guard in
  read-only snapshot artifacts and blocks overlong RIFT live-debugger windows
  before connecting to x64dbg. It also blocks if the collected debugger/debuggee
  identity no longer matches the approved PID/HWND/process metadata.
- `scripts/rift_live_test/x64dbg_launcher.py` owns x64dbg launch behavior.
  `scripts/open-x64dbg.cmd` and `.ps1` are compatibility wrappers only, keeping
  new workflow logic out of PowerShell.

This does not make old PID `63412` addresses current again. It only makes future
x64dbg use explicit, timed, candidate-only, and detach-first.

## Current recommended lane

Stay offline until a fresh current-PID coordinate candidate is reacquired for
PID `79184` or a newer exact target. Use the old PID `63412` artifacts only as
historical shape evidence.
