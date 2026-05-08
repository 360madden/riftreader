# RiftReader handoff — current PID 33912 visible-HUD proof passed

Created: 2026-05-08 06:33 EDT / 10:33 UTC
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
Scope: current-session coord truth + visible HUD proof checkpoint; no movement/input in this handoff slice.

## TL;DR

| Fact | Current status |
|---|---|
| Live target | `rift_x64` PID `33912`, HWND `0xE0DB2` |
| Client restart needed? | **No**, not while PID `33912` / HWND `0xE0DB2` stays alive and proof passes |
| Player coordinate truth | **Yes for current-session proof-coordinate readback** |
| Latest proof run | `ProofOnly` passed at 2026-05-08 06:31:44 EDT / 10:31:44 UTC |
| Latest coordinate | `X=7436.64013671875`, `Y=885.2191772460938`, `Z=3055.749267578125` at `2026-05-08T10:31:43.1860758Z` |
| Movement sent | `false` |
| Movement attempted | `false` |
| Cheat Engine | **Not used** |
| SavedVariables as live truth | **Not used** |
| HUD GUI | **Launched and alive at handoff time**: `RiftReader HUD - ProofOnly`, GUI PID `26480`, HWND `0xD0590` |
| Auto-turn | **Still blocked**; no promoted turn backend |
| Git state before this handoff commit | `main...origin/main [ahead 15]`; user requested handoff then push |

## Latest visible-HUD proof evidence

| Artifact | Path / value |
|---|---|
| Run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-103043\run-summary.json` |
| Run progress | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-103043\run-progress.json` |
| Proof readback summary | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-33912-readback-summary-20260508-063135.json` |
| Latest run pointer | `C:\RIFT MODDING\RiftReader\scripts\captures\latest-live-test-run.json` points to the `live-test-ProofOnly-20260508-103043` run |
| HUD start file | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-103043\gui-start.json` |
| HUD title | `RiftReader HUD - ProofOnly` |
| HUD mode | read-only progress HUD |
| HUD always-on-top | `false` |

Command that produced the visible HUD proof:

```powershell
python .\scripts\live_test.py --profile ProofOnly --pid 33912 --hwnd 0xE0DB2 --process-name rift_x64
```

Important: the previous invisible proof used `--no-gui`; this visible-HUD proof intentionally omitted `--no-gui`.

## Current truth boundaries

| Area | Status |
|---|---|
| Coord anchor | Current-session proof coordinate readback is valid for PID `33912` / HWND `0xE0DB2` |
| Movement grade | Current session previously passed Forward250, ForwardSeries3x250, fixed-bearing 1m waypoint smoke, and fixed-bearing 2m waypoint smoke |
| 2m waypoint smoke | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-0622-2m\a-to-b-prototype-2m-fixed-bearing.ndjson`; arrived, distance `2.000000000000236m -> 0.6994920167255987m` |
| Movement safety | Proof is age-gated; run fresh ProofOnly/preflight before any later movement |
| Auto-turn | Blocked because compact turn evidence still has zero promoted candidates |
| CE boundary | Do not use CE / CE Lua / debugger unless explicitly reauthorized in the current conversation |
| SavedVariables boundary | Do not treat SavedVariables as live truth |

## What happened immediately before this handoff

1. User asked whether player actor coordinate data is truth now.
2. Local artifacts were checked: latest proof was valid and target process was alive.
3. User asked for actions `1 2 3` from the recommendation list.
4. The exact RIFT window was rebound with `rift-window-control`:
   - PID `33912`
   - HWND `0xE0DB2`
   - title `RIFT`
5. A baseline screenshot was captured:
   - `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-063032-841.png`
6. `ProofOnly` was run without `--no-gui`.
7. The proof passed with no movement and no game input.
8. GUI process was confirmed alive:
   - PID `26480`
   - HWND `0xD0590`
   - title `RiftReader HUD - ProofOnly`
9. Windows focus was switched to the HUD window so the user should see it.

## Current known blocker

| Blocker | Detail |
|---|---|
| Full auto-nav | Auto-turn remains blocked because no input backend has met promotion criteria |
| Why | Latest turn-key profile evidence has zero promoted candidates; `run-a-to-b-prototype.ps1` now fails closed before auto-turn key pulses unless promoted backend evidence exists |
| Do not do | Do not run turn-then-forward navigation until a turn backend produces repeated same-sign yaw deltas with zero proof-coordinate movement and is persisted in promoted evidence |

## Resume instructions for next chat

1. Start in `C:\RIFT MODDING\RiftReader` on `main`.
2. Read this handoff first.
3. Check git status and the newest handoff file.
4. Re-check live target before any live action:
   - expected PID `33912`
   - expected HWND `0xE0DB2`
   - expected process `rift_x64`
5. If PID/HWND changed, do not reuse the current anchor blindly; reacquire proof.
6. Before movement, refresh proof with exact target:

```powershell
python .\scripts\live_test.py --profile ProofOnly --pid 33912 --hwnd 0xE0DB2 --process-name rift_x64
```

7. If the user wants no visible HUD, add `--no-gui`; otherwise omit it.
8. Continue from the auto-turn blocker unless the user asks for docs/status only.

## Ready-to-paste resume prompt

```text
Resume from newest handoff in C:\RIFT MODDING\RiftReader. Start with docs\handoffs\2026-05-08-063335-current-pid-33912-visible-hud-proof-passed-handoff.md. Re-check git status and exact live target PID/HWND before any live action. Current remembered target is rift_x64 PID 33912 HWND 0xE0DB2; latest visible-HUD ProofOnly passed at 2026-05-08 10:31:44 UTC with coordinate 7436.64013671875, 885.2191772460938, 3055.749267578125 and movementSent=false. No CE and no SavedVariables live truth. Auto-turn is still blocked until a turn backend is promoted. If doing movement, refresh ProofOnly/preflight first.
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Keep the current RIFT client open | PID/HWND are validated for this session. |
| 2 | Use the visible HUD for proof status | It is now launched and bound to the latest progress file. |
| 3 | Make HUD always-on-top configurable/defaulted if desired | Current HUD launched with `alwaysOnTop=false`, so it can hide behind other windows. |
| 4 | Refresh `ProofOnly` before movement | Proof is age-gated for safety. |
| 5 | Do not restart unless PID/HWND changes or proof fails | Restart would force reacquisition. |
| 6 | Keep CE disabled | Current live boundary is no-CE. |
| 7 | Keep SavedVariables out of live truth | Avoids stale post-save snapshot mistakes. |
| 8 | Continue turn-backend promotion work | This is the blocker for full auto-nav. |
| 9 | Prefer no-input/read-only proof when answering status questions | Avoids accidental movement/input. |
| 10 | Push this handoff commit | Preserves the current state for restart/new chat recovery. |
