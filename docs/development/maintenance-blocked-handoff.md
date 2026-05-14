# RiftReader Maintenance-Blocked Handoff Helper

Version: v0.1.2

## Purpose

`scripts/riftreader_maintenance_blocked_handoff.py` creates a compact maintenance-blocked handoff when RIFT is down or unavailable.

It records repo state, RIFT process availability, latest Stage 1 summary if
present, latest coordinate-proof-route pointer if present, current blocker,
exact next action, and do-not-do notes.

## Command

```powershell
cmd\riftreader-maintenance-blocked-handoff.cmd --commit --push
```

## Outputs

```text
handoffs\current\maintenance-blocked\<UTC>\RIFTREADER_MAINTENANCE_BLOCKED_HANDOFF.md
handoffs\current\maintenance-blocked\<UTC>\RIFTREADER_MAINTENANCE_BLOCKED_HANDOFF.json
handoffs\current\RIFTREADER_CURRENT_HANDOFF.md
handoffs\current\RIFTREADER_CURRENT_HANDOFF.json
G:\My Drive\RiftReader\status\RIFTREADER_CURRENT_STATUS.md
G:\My Drive\RiftReader\status\RIFTREADER_CURRENT_STATUS.json
```

## v0.1.2 fix

- Includes `scripts/captures/latest-coordinate-proof-route.json` in generated
  handoffs when present, so visual/capture evidence remains tied to its
  fail-closed coordinate-proof route status.

## v0.1.1 fix

- Normalizes repo-generated handoff paths to Git-style forward slashes before staged-file allowlist comparison.

## Safety

- Sends no input.
- Runs no live recovery.
- Does not promote proof anchors.
- Does not update `docs/recovery/current-truth.md`.
- Does not update `docs/recovery/current-proof-anchor-readback.json`.
- Uses explicit git file allowlist only when `--commit` is supplied.

## END_OF_DOCUMENT_MARKER
