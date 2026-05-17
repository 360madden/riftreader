# Compact handoff — outage-safe OpenCode wording update

Created: 2026-05-17 08:45 EDT
Branch: `main`
Scope: Adapt OpenCode/non-Codex status language after user-reported power outage/game offline state.

## TL;DR

User reported a power outage and game offline state. Local process inspection still saw `rift_x64` PID `22304`, so helpers must not equate process presence with game-online/in-world truth. Updated status/helper/doc wording from `Live RIFT is running` / `RIFT is online` assumptions to process-aware language: a `rift_x64` process may be visible while proof remains stale and movement blocked.

Follow-up: user then reported the game is online again. This does not reverse
the wording change: process visibility and operator-reported online state are
useful context, but current proof remains blocked until same-target proof is
refreshed.

## Current status

| Field | Value |
|---|---|
| Local `rift_x64` process | PID `22304` still visible during check |
| User-reported game state | Offline after power outage; treat as not in-world/current-proof validated |
| Proof artifact | Historical PID `27552` / HWND `0x3411E2` |
| Proof status | `blocked-target-drift` |
| Movement | Blocked; no input/movement/reload/debugger sent |
| OpenCode | CLI `1.15.3`, model `openai/gpt-5.5`, model visible |

## Change made

| File | Change |
|---|---|
| `tools/riftreader_workflow/status_packet.py` | Next action now says a `rift_x64 process is visible`, not `Live RIFT is running`. |
| `tools/riftreader_workflow/live_test_triage.py` | Same process-aware wording for stale artifact PID. |
| `scripts/test_opencode_status_packet.py` | Updated expectation for process-aware wording. |
| `scripts/test_live_test_triage.py` | Updated expectation for process-aware wording. |
| `docs/workflow/opencode-non-codex-bridge.md` | Clarifies process visibility is not game-online/in-world proof. |
| `docs/workflow/non-codex-desktop-chatgpt-workflow.md` | Same clarification for desktop ChatGPT bridge. |
| `docs/workflow/live-test-fast-lane-triage.md` | Rewords expected stale-PID case around process visibility. |
| `docs/handoffs/2026-05-17-0622-live-aware-status-overlay.md` | Clarifies prior handoff wording. |

## Resume prompt

```text
Resume RiftReader OpenCode/non-Codex lane after the outage-safe wording update. Treat a visible `rift_x64` PID as process presence only, not game-online/in-world proof. Keep stale PID `27552` / HWND `0x3411E2` historical only and movement blocked. Run `scripts\riftreader-workflow-status.cmd --compact-json` and continue offline-safe OpenCode/status/package workflow unless live proof recovery is explicitly authorized.
```
