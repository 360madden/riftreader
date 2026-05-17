# Compact handoff — OpenCode live-triage stale-target guidance

Generated UTC: `2026-05-17T08:52:51Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

Live triage now gives OpenCode/desktop ChatGPT the correct next action when
RIFT is online but the proof artifact points at an old PID/HWND. Instead of
generic "load RIFT" guidance, `artifact-pid-stale` now says a live process is
present, the proof artifact is historical, movement remains blocked, and safe
current-target reacquisition/status refresh is required before ProofOnly or
movement.

## Implemented files

| Path | Purpose |
|---|---|
| `tools/riftreader_workflow/live_test_triage.py` | Adds live-verdict-specific next-action text for no-live, missing-artifact-PID, and stale-artifact-PID blockers. |
| `scripts/test_live_test_triage.py` | Verifies `artifact-pid-stale` guidance names the live PID, stale artifact PID/HWND, and stale-proof reuse boundary. |
| `docs/workflow/live-test-fast-lane-triage.md` | Documents expected online/stale-artifact output. |

## Safety

No live input, movement, `/reloadui`, screenshot key, CE/x64dbg attach,
provider write, stage/commit/push logic, or proof promotion is added. This
slice only improves no-input status classification text.

## Resume point

Next safe OpenCode slice: add a compact package-intake/dry-run summary that
desktop ChatGPT and OpenCode can use to inspect applier ZIPs without applying
edits until explicitly approved.
