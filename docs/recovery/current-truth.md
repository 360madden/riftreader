# RiftReader current truth

## Verdict

RIFT is currently at **character selection**, not in-world. Movement and route automation are blocked.

| Field | Value |
|---|---|
| Updated UTC | `2026-05-20T18:18:48Z` |
| Current target | PID `86740`, HWND `0x414F8` |
| Process start UTC | `2026-05-20T17:55:14.2126486Z` |
| Screen state | `character-select-not-in-world` |
| Screen classifier | `character-selection-not-in-world` confidence `1.0` |
| Visual evidence | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-140919-120.png` |
| Screen-state summary | `.riftreader-local\character-login-screen-state\run-20260520-180928-731718\character-login-screen-state-summary.json` |
| Environment summary | `.riftreader-local\character-select-automation-env\run-20260520-180957-798659\character-select-automation-env-summary.json` |
| Launcher inspection | `.riftreader-local\launcher-inspection\run-20260520-180746-262609\launcher-inspection-summary.json` |
| Login supervisor | `.riftreader-local\character-login-supervisor\run-20260520-181401-933577\character-login-supervisor-summary.json` |
| Previous target | PID `80072`, HWND `0xD10C20` archived at `docs\recovery\historical\current-proof-anchor-readback-2026-05-20-pid80072-hwndD10C20-character-select-historical.json` |

## Current blockers

- RIFT is at character selection, not in the in-game world; no current player coordinate proof exists for PID `86740` / HWND `0x414F8`.
- Prior character-select target PID `80072` / HWND `0xD10C20` is stale after target drift and is historical only.
- Prior in-world proof PID `1948` / HWND `0x3C0D58` remains historical-only; do not use its absolute address or candidate as current movement truth.
- Actor yaw/facing artifacts remain stale until current in-world PID/HWND artifacts exist and pass readback.

## Fresh character-login artifacts

| Artifact | Path |
|---|---|
| Screen state classifier | `.riftreader-local\character-login-screen-state\run-20260520-180928-731718\character-login-screen-state-summary.json` |
| Environment summary | `.riftreader-local\character-select-automation-env\run-20260520-180957-798659\character-select-automation-env-summary.json` |
| Character-select plan | `.riftreader-local\character-select-automation-plan\run-20260520-181400-411645\character-select-automation-plan-summary.json` |
| Login resilience plan | `.riftreader-local\character-login-resilience-plan\run-20260520-181400-757752\character-login-resilience-plan-summary.json` |
| Executor contract | `.riftreader-local\character-login-executor-contract\run-20260520-181401-139514\character-login-executor-contract-summary.json` |
| Readiness packet | `.riftreader-local\character-login-readiness-packet\run-20260520-181401-513575\character-login-readiness-packet-summary.json` |
| Login supervisor | `.riftreader-local\character-login-supervisor\run-20260520-181401-933577\character-login-supervisor-summary.json` |
| Launcher inspection | `.riftreader-local\launcher-inspection\run-20260520-180746-262609\launcher-inspection-summary.json` |
| Screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-140919-120.png` |
| Post-world proof checklist | `docs/workflow/post-world-entry-proof-reacquisition-checklist.md` |

## Required recovery

1. Rerun supervisor and Play executor gate against the current PID/HWND immediately before any future approved world-entry action.
2. Only after explicit current-run approval, use the manifest's exact-target MCP sequence and click Play at most once.
3. Wait for frame transition and capture post-transition evidence; do not retry blind clicks if the screen does not change.
4. After world load, rediscover exact PID/HWND/process start.
5. Sample fresh API/runtime coordinate truth; do not use SavedVariables as live truth.
6. Run same-target ProofOnly before any movement or diagnostic input.

## Safety

No click, key input, movement, Cheat Engine, x64dbg attach, provider write, raw command-line secret storage, or live memory read was used to create this blocker.
