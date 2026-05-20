# Current RIFT live truth — target reacquired at character selection

RIFT is currently at **character selection**, not in-world. Movement and route automation remain **blocked**.

| Field | Value |
|---|---|
| Updated UTC | `2026-05-20T19:06:25Z` |
| Current target | PID `51016`, HWND `0x4613F0` |
| Process start UTC | `2026-05-20T18:55:37.6710595Z` |
| Screen state | `character-select-not-in-world-after-restart` |
| Clean screen classifier | `character-selection-not-in-world` confidence `1.0` |
| Clean visual evidence | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-145745-653.png` |
| Clean screen-state summary | `.riftreader-local\character-login-screen-state\run-20260520-185843-765426\character-login-screen-state-summary.json` |
| Environment summary | `.riftreader-local\character-select-automation-env\run-20260520-185900-605658\character-select-automation-env-summary.json` |
| Launcher inspection | `.riftreader-local\launcher-inspection\run-20260520-185719-537492\launcher-inspection-summary.json` |
| Latest visual gate | `blocked-non-game-overlay`; screenshot `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-150319-668.png` |
| Latest visual-gate summary | `.riftreader-local\character-login-screen-state\run-20260520-190625-436699\character-login-screen-state-summary.json` |
| Latest supervisor | `.riftreader-local\character-login-supervisor\run-20260520-190523-757189\character-login-supervisor-summary.json` |
| Previous target | PID `86740`, HWND `0x414F8` archived at `docs\recovery\historical\current-proof-anchor-readback-2026-05-20-pid86740-hwnd414F8-character-select-approved-click-historical.json` |

## Current blockers

- The latest live capture has a non-game Command Prompt overlay covering the Play/shard/center landmarks; high-confidence Play click automation is blocked until a fresh clean screenshot passes.
- RIFT is at character selection after restart, not in the in-game world; no current player coordinate proof exists for PID `51016` / HWND `0x4613F0`.
- Prior character-select target PID `86740` / HWND `0x414F8` is stale after restart and is historical only.
- Prior in-world proof PID `1948` / HWND `0x3C0D58` remains historical-only; do not use its absolute address or candidate as current movement truth.
- Actor yaw/facing artifacts remain stale until current in-world PID/HWND artifacts exist and pass readback.

## Fresh post-restart automation artifacts

| Artifact | Path |
|---|---|
| Clean screen state classifier | `.riftreader-local\character-login-screen-state\run-20260520-185843-765426\character-login-screen-state-summary.json` |
| Latest blocked visual gate classifier | `.riftreader-local\character-login-screen-state\run-20260520-190625-436699\character-login-screen-state-summary.json` |
| Environment summary | `.riftreader-local\character-select-automation-env\run-20260520-185900-605658\character-select-automation-env-summary.json` |
| Character-select plan | `.riftreader-local\character-select-automation-plan\run-20260520-190522-012595\character-select-automation-plan-summary.json` |
| Login resilience plan | `.riftreader-local\character-login-resilience-plan\run-20260520-190522-428657\character-login-resilience-plan-summary.json` |
| Executor contract | `.riftreader-local\character-login-executor-contract\run-20260520-190522-904425\character-login-executor-contract-summary.json` |
| Readiness packet | `.riftreader-local\character-login-readiness-packet\run-20260520-190523-313119\character-login-readiness-packet-summary.json` |
| Login supervisor | `.riftreader-local\character-login-supervisor\run-20260520-190523-757189\character-login-supervisor-summary.json` |
| Redacted helper sequence summary | `.riftreader-local\turn-20260520-restart-pid51016-gates\redacted-helper-sequence-summary.json` |
| Workflow status compact SITREP | `.riftreader-local\workflow-status\20260520-191003Z\compact-sitrep.json` |
| Launcher inspection | `.riftreader-local\launcher-inspection\run-20260520-185719-537492\launcher-inspection-summary.json` |
| Clean screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-145745-653.png` |
| Latest obstructed screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-150319-668.png` |
| Post-world proof checklist | `docs/workflow/post-world-entry-proof-reacquisition-checklist.md` |

## Required recovery

1. Clear or avoid the non-game overlay and capture a fresh exact-target screenshot.
2. Rerun screen-state, environment capture if needed, supervisor, and Play executor gate against PID `51016` / HWND `0x4613F0` immediately before any future approved world-entry action.
3. Only after explicit current-run approval and high-confidence visual/executor evidence, use the manifest's exact-target MCP sequence and click Play at most once.
4. Wait for frame transition and capture post-transition evidence; do not retry blind clicks if the screen does not change.
5. After world load, rediscover exact PID/HWND/process start.
6. Sample fresh API/runtime coordinate truth; do not use SavedVariables as live truth.
7. Run same-target ProofOnly before any movement, route automation, or diagnostic movement input.

## Safety

No click, key input, movement, Cheat Engine, x64dbg attach, provider write, raw command-line secret storage, or live memory read was used to refresh this post-restart target blocker. Approval-token contract values remain redacted from committed docs.
