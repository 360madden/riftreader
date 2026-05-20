# Character login / relaunch recovery handoff — PID 86740

## Verdict

RIFT was relaunched and is currently at the character-selection screen. The
current target identity is refreshed to PID `86740` / HWND `0x414F8`, selected
character `ATANK`, shard `Deepwood`. World entry and movement remain blocked:
no Play click, key input, focus change, launcher button press, Cheat Engine, or
x64dbg attach was performed.

| Field | Current value |
|---|---|
| Generated UTC | `2026-05-20T18:18:00Z` |
| Branch baseline | `main` at `5dc7ad9` |
| RIFT process | `rift_x64.exe` PID `86740` |
| RIFT HWND | `0x414F8` |
| RIFT process start UTC | `2026-05-20T17:55:14.2126486Z` |
| RIFT module base | `0x7FF7B77A0000` |
| Window geometry | client `640x360`, outer `656x399` |
| Current screen | `character-selection-not-in-world` |
| Selected character | `ATANK` |
| Current shard | `Deepwood` |
| Launcher process | `GlyphClientApp.exe` PID `31812` |
| Process-tree relation | RIFT PID `86740` is a child of Glyph PID `31812` |
| Launcher UI state | hidden/minimized/offscreen; button automation blocked |
| Movement status | blocked; no current in-world coordinate proof |

## Current durable repo truth

| Artifact | Path |
|---|---|
| Current truth JSON | `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.json` |
| Current truth MD | `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md` |
| Current proof/readback blocker | `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` |
| Archived previous target proof | `C:\RIFT MODDING\RiftReader\docs\recovery\historical\current-proof-anchor-readback-2026-05-20-pid80072-hwndD10C20-character-select-historical.json` |

The previous character-select target PID `80072` / HWND `0xD10C20` is now
historical only. Do not use its absolute address, approval state, or movement
gate as current truth.

## Fresh read-only automation data

| Data source | Status | Path |
|---|---:|---|
| Launcher inspection | passed; launcher/game present; launcher buttons blocked while hidden/minimized | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-180746-262609\launcher-inspection-summary.json` |
| Exact game capture | read-only screenshot of current HWND | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-140919-120.png` |
| Screen-state classifier | `classified-character-select`, confidence `1.0` | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-screen-state\run-20260520-180928-731718\character-login-screen-state-summary.json` |
| Character-select env capture | `captured-read-only-character-select`; Play point recorded for future gated executor | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-select-automation-env\run-20260520-180957-798659\character-select-automation-env-summary.json` |
| Character-select plan | planned; no live actions | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-select-automation-plan\run-20260520-181400-411645\character-select-automation-plan-summary.json` |
| Login resilience plan | planned; no live actions | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-resilience-plan\run-20260520-181400-757752\character-login-resilience-plan-summary.json` |
| Executor contract | blocked; explicit same-run approval required | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-executor-contract\run-20260520-181401-139514\character-login-executor-contract-summary.json` |
| Readiness packet | packet-ready; current PID/HWND aligned | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-readiness-packet\run-20260520-181401-513575\character-login-readiness-packet-summary.json` |
| Supervisor | blocked on approval; target not stale | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-supervisor\run-20260520-181401-933577\character-login-supervisor-summary.json` |
| Workflow status | blocked; live target is running and non-stale | `C:\RIFT MODDING\RiftReader\.riftreader-local\turn-20260520-character-refresh\workflow-status.stdout.json` |

## Launcher/relogin findings

| Finding | Automation implication |
|---|---|
| Glyph is running and owns the current RIFT child process. | Relaunch detection should prefer process-tree state before considering launcher UI actions. |
| Glyph main window is visible by flag but minimized/offscreen with `0x0` client area. | Do not press launcher buttons; future launcher automation needs an explicit restore/show + screenshot classifier gate. |
| RIFT command-line arguments are redacted and raw command lines are not stored. | Future automation must keep auth/session values out of tracked docs and status packets. |
| RIFT is already at character selection. | Recovery should resume from character-select gates, not launcher buttons, unless the game process exits. |

## Character-selection automation state

| Gate | Verdict |
|---|---|
| Exact target PID/HWND | passed: PID `86740`, HWND `0x414F8` |
| Screen classifier | passed: character select |
| Selected character | passed: `ATANK` |
| Play button target | captured as client coordinates for future executor only |
| Same-run approval token | not present; intentionally not stored in workflow status |
| Play click | blocked |
| World-load wait | not attempted |
| In-world ProofOnly | blocked until after explicit world entry and fresh in-world target reacquisition |
| Movement | blocked |

## Resume policy for future automation

1. If PID/HWND changes again, immediately mark current proof as target-drifted
   and preserve the previous proof under `docs\recovery\historical\`.
2. Re-run launcher inspection read-only to determine whether RIFT exists, Glyph
   exists, and whether the current RIFT process is a Glyph child.
3. If RIFT is at character selection, run the screen-state classifier and
   character-select env capture before any action plan.
4. Generate a fresh character-select plan, resilience plan, executor contract,
   readiness packet, and supervisor artifact for the current PID/HWND.
5. Require explicit same-run approval before a future executor may click Play.
6. After any Play click, wait for world load, rediscover exact PID/HWND, sample a
   fresh live coordinate source, and run same-target ProofOnly before movement.

## Safety

No live input was sent. No launcher button was pressed. No Play click occurred.
No world-entry attempt occurred. No process was terminated or launched by the
helper flow. No provider writes, Cheat Engine, x64dbg, SavedVariables-as-live
truth, Git mutation by helper, or movement occurred.

## Validation snapshot

- `scripts\riftreader-character-select-plan.cmd --target-character ATANK --plan-enter-world --json` -> planned, no live action.
- `scripts\riftreader-character-login-resilience-plan.cmd --target-character ATANK --json` -> planned, no live action.
- `scripts\riftreader-character-login-executor-contract.cmd --json` -> blocked as designed because explicit approval is missing.
- `scripts\riftreader-character-login-readiness-packet.cmd --target-character ATANK --json` -> packet-ready.
- `scripts\riftreader-character-login-supervisor.cmd --target-character ATANK --samples 3 --interval-seconds 1 --json` -> blocked on approval with non-stale target.
- `scripts\riftreader-workflow-status.cmd --compact-json --write` -> blocked; live target PID/HWND matches current artifacts.

## Continuation update — 2026-05-20 14:37 EDT — approved one-click Play attempt

| Field | Value |
|---|---|
| User-approved scope | `do 1 2 3 only` |
| Same-run supervisor | `.riftreader-local\character-login-supervisor\run-20260520-183445-653101\character-login-supervisor-summary.json` |
| Play executor gate | `.riftreader-local\character-login-play-executor-gate\run-20260520-183451-525996\character-login-play-executor-gate-summary.json` |
| Click count | `1` |
| Click point | client `[517, 343]` |
| Pre-click screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-143510-544.png` |
| Post-click screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-143532-805.png` |
| Frame-change result | `changed=true`, `4.1944%`, `636ms` |
| Post-click classifier | `character-selection-not-in-world`, confidence `1.0` |
| Attempt summary | `.riftreader-local\approved-play-click-attempts\run-20260520-183614\approved-play-click-attempt-summary.json` |

The approved executor sent exactly one Play click and stopped. The client did not
leave character selection according to the post-click classifier, so no retry
click was sent and no post-world ProofOnly or movement work was attempted.
Movement remains blocked.
