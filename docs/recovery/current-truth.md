# RiftReader current truth

## Verdict

RIFT is currently at **character selection**, not in-world. Movement and route automation are blocked.

| Field | Value |
|---|---|
| Updated UTC | `2026-05-20T17:29:39.217389Z` |
| Current target | PID `80072`, HWND `0xD10C20` |
| Process start UTC | `2026-05-20T16:54:54.7174411Z` |
| Screen state | `character-select-not-in-world` |
| Screen classifier | `character-selection-not-in-world` confidence `0.9178` |
| Play executor gate | `blocked-approval-required` |
| Visual evidence | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-132806-184.png` |
| Latest supervisor | `.riftreader-local\character-login-supervisor\run-20260520-172826-508165\character-login-supervisor-summary.json` |
| Play executor gate artifact | `.riftreader-local\character-login-play-executor-gate\run-20260520-172832-522225\character-login-play-executor-gate-summary.json` |
| Future MCP action manifest | `.riftreader-local\character-login-supervisor\run-20260520-172826-508165\future-mcp-action-manifest.json` |
| Expected approval token | `ENTER-WORLD:ATANK:80072:0xD10C20` |

## Current blockers

- RIFT is at character selection, not in the in-game world; no current player coordinate proof exists for PID `80072` / HWND `0xD10C20`.
- Play executor gate is blocked until explicit approval token and `--allow-world-entry` are provided in the same fresh run.
- Prior character-select target PID `77728` / HWND `0x8E13A6` is stale after target drift and is historical only.
- Prior in-world proof PID `1948` / HWND `0x3C0D58` remains historical-only; do not use its absolute address or candidate as current movement truth.
- Actor yaw/facing artifacts remain stale until current in-world PID/HWND artifacts exist and pass readback.

## Fresh character-login artifacts

| Artifact | Path |
|---|---|
| Screen state classifier | `.riftreader-local\character-login-supervisor\run-20260520-172826-508165\screen-state\character-login-screen-state-summary.json` |
| Environment summary | `.riftreader-local\character-select-automation-env\run-20260520-172824-675348\character-select-automation-env-summary.json` |
| Selection plan | `.riftreader-local\character-select-automation-plan\run-20260520-172825-242705\character-select-automation-plan-summary.json` |
| Resilience plan | `.riftreader-local\character-login-resilience-plan\run-20260520-172825-551314\character-login-resilience-plan-summary.json` |
| Executor contract | `.riftreader-local\character-login-supervisor\run-20260520-172826-508165\executor-contract\character-login-executor-contract-summary.json` |
| Readiness packet | `.riftreader-local\character-login-supervisor\run-20260520-172826-508165\readiness-packet\character-login-readiness-packet-summary.json` |
| Supervisor summary | `.riftreader-local\character-login-supervisor\run-20260520-172826-508165\character-login-supervisor-summary.json` |
| Play executor gate | `.riftreader-local\character-login-play-executor-gate\run-20260520-172832-522225\character-login-play-executor-gate-summary.json` |
| Future MCP action manifest | `.riftreader-local\character-login-supervisor\run-20260520-172826-508165\future-mcp-action-manifest.json` |

## Required recovery

1. Rerun screen-state, supervisor, and Play executor gate immediately before any future approved world-entry action.
2. Only after explicit current-run approval, use the manifest's exact-target MCP sequence and click Play at most once.
3. Wait for frame transition and capture post-transition evidence; do not retry blind clicks if the screen does not change.
4. After world load, rediscover exact PID/HWND/process start.
5. Sample fresh API/runtime coordinate truth; do not use SavedVariables as live truth.
6. Run same-target ProofOnly before any movement or diagnostic input.

## Safety

No click, key input, movement, Cheat Engine, x64dbg attach, provider write, or live memory read was used to create this blocker.
