# Tooltip / Entity 3D-to-2D Projection Discovery — 2026-04-24

## TL;DR

The mailbox tooltip path is a **stronger current lead than the fishing reticle** for waypoint-marker discovery. A no-click hover over the mailbox reliably showed a tooltip anchored near the 3D mailbox, and hiding/re-hovering reproduced the UI change without selecting a target or triggering mailbox interaction.

Current classification: **tooltip/UI-anchor projection lead, not yet arbitrary XYZ projection**.

## Live safety result

| Check | Result |
|---|---|
| Clicks/casts/mailbox interaction | None performed |
| Movement | None performed |
| Input used | Mouse move/hover only, plus mouse wheel camera zoom probe |
| Target selection during hidden/hover scans | `HasTarget: false` in both reads |
| Gameplay side effects observed | None |

## Visual evidence

Durable artifact folder:

`C:\RIFT MODDING\RiftReader\artifacts\tooltip-projection\20260424-0335-tooltip-projection`

| State | Evidence |
|---|---|
| Initial mailbox hover | `initial_hover.png` |
| Tooltip hidden baseline | `hidden_0.png` |
| Tooltip hover baseline | `hover_0.png` |
| Repeat hidden | `hidden_1.png` |
| Repeat hover | `hover_1.png` |
| Camera/zoom changed, tooltip hidden | `zoom_hidden.png` |
| Camera/zoom changed, tooltip hovered | `zoom_hover.png` |
| Scan-time hidden state | `zoom_hidden_scan_state_2.png` |
| Scan-time hover state | `zoom_hover_scan_state_2.png` |

Observed behavior: the tooltip text `Send and receive mail here.` appears/disappears purely from hover state and remains visually anchored near the mailbox after a camera zoom change.

## Read-only memory evidence

| Probe | Hidden | Hover | Interpretation |
|---|---:|---:|---|
| `--read-target-current` | `HasTarget: false` | `HasTarget: false` | Hover does not require target selection. |
| Scan tooltip text | 2 hits | 4 hits | Hover creates/adds tooltip-text instances beyond static/common localized strings. |
| Scan tooltip X int32 `631` | 24 capped hits | 24 capped hits | Too noisy; not useful yet. |
| Scan tooltip Y int32 `447` | 24 capped hits | 24 capped hits | Too noisy; not useful yet. |
| Scan pointer to hover-only tooltip text `0x12C97BB41B0` | 1 hit | 1 hit | There is pointer-bearing UI/text state, but the record changes by state. |

Important candidate from the hover scan:

| Candidate | Evidence | Current meaning |
|---|---|---|
| `0x12CF46CE240` record, pointer field at `+0x40` / `0x12CF46CE280` | `hover2_scan_pointer_tooltip_hover_only_text.json` | During hover, this field pointed to hover-only tooltip text `0x12C97BB41B0`. |
| Same record after hiding tooltip | `hidden2_read_hover_only_pointer_record.json` | The `+0x40` field no longer pointed to the hover tooltip text; it changed to another pointer-like value. |

This is not enough to promote a stable memory API, but it is enough to justify a focused follow-up on the tooltip UI text/anchor record instead of broad reticle scanning.

## Reuse decision

| Candidate path | Decision |
|---|---|
| Tooltip hover as final marker | Not enough yet; hover-bound and entity-specific. |
| Tooltip UI text/anchor record | **Promising next probe**. It changes with hover state and may include text pointer plus layout/anchor metadata. |
| Existing entity-to-screen projection | **Visually supported**, but not memory-proven yet. Tooltip follows the mailbox on screen and survives camera zoom as an entity-anchored UI affordance. |
| Arbitrary world XYZ projection | Not proven. Need camera matrix / nameplate / UI anchor extraction before claiming this. |
| Fishing reticle | Keep as backup, but deprioritize for now. |

## Next proof target

Trace or sample the tooltip UI record around `0x12CF46CE240` while toggling hover state, looking for:

| Field type | Why |
|---|---|
| Current tooltip text pointer | Already observed at `+0x40` during hover. |
| Tooltip visible/hidden flag | Needed to identify lifecycle. |
| Tooltip screen rectangle / X/Y | Would prove UI-anchor output. |
| Hovered entity pointer/GUID | Would connect the tooltip to the mailbox entity. |
| World/object position or projected anchor | Would bridge entity-to-screen projection. |

## Stop conditions for next pass

- Do not click, open mailbox, cast, or interact.
- Do not promote any address without repeat proof in the current session.
- If the record changes allocation every hover, switch to tracing writer/controller rather than fixed-address reads.
- If tooltip state is hover-only and cannot be decoupled from cursor, compare NPC/player nameplates next.

## Top 5 Recommended Next Actions

| # | Action | Why |
|---:|---|---|
| 1 | Re-hover mailbox and record repeated reads around `0x12CF46CE240` | Confirms whether the candidate record is stable enough for field mapping. |
| 2 | Diff 0x100–0x200 bytes around the candidate across hidden/hover/zoom-hover | Finds text pointer, flags, and possible screen rectangle fields. |
| 3 | Scan pointers to the hover-only text pointer and candidate record after each state change | Separates persistent UI owner objects from transient string allocations. |
| 4 | Search nearby values for tooltip screen rect candidates, not broad global `631/447` scans | Reduces numeric-scan noise. |
| 5 | If tooltip stays too hover-specific, run the same probe on NPC/player nameplates | Nameplates may expose a reusable entity-to-screen anchor path. |
