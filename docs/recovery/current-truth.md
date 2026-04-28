# Current Truth

_Last updated: April 23, 2026 (fresh live coord-anchor validation, agentic actor-facing lead promotion, and same-session provenance refresh on the live `rift_x64` session)_

## Current status

| Area | Status |
|---|---|
| Low-level reader | reliable enough for active work |
| ReaderBridge snapshot load | working |
| Player current read | working |
| Coord-anchor module pattern | working |
| Proof coord anchor cache | refreshed again for the current live PID via direct `--read-player-coord-anchor` validation |
| Proof polling watchset | refreshed again and still includes the canonical `coord-trace-coords` region |
| Active movement (`--navigate-waypoints`) | requires the validated coord-trace anchor only; cached/reacquired anchors are no longer accepted for live movement, even when opt-in auto-turn is enabled |
| Navigation preflight (`--read-navigation-current`) | returns a read-only facing-aware turn hint when actor-facing truth is available; this powers operator guidance and reader-core auto-turn planning |
| Navigation reader-core auto-turn | `--navigate-waypoints` can now opt into pre-movement auto-turn with `--auto-turn-before-move` and related tuning switches; it remains fail-closed if alignment does not improve or worsens repeatedly |
| Navigation v3 route planning | `--plan-navigation-route` builds a read-only ordered start / via / destination route plan with per-segment distance, bearing, arrival radius, and pace; it does not send movement input |
| Navigation v3 active route gate | `--navigate-waypoint-route` is now the explicit active-input route-chain gate; it runs planned segments sequentially, can opt into per-segment auto-turn with `--auto-turn-before-move`, preserves per-segment results, and stops on first failure, but still needs live route proof promotion |
| Navigation prototype wrapper | `C:\RIFT MODDING\RiftReader\scripts\navigation\run-a-to-b-prototype.ps1` remains an optional higher-level helper for the same facing-aware preflight / auto-turn workflow |
| Navigation proof suite | `C:\RIFT MODDING\RiftReader\scripts\navigation\test-navigation-proof-suite.ps1` now rechecks the smoke-route, asserts v3 route-plan segment metadata, verifies facing-aware preflight, current auto-turn-preflight path, and opt-in active v3-prep proofs via `-IncludeActiveMovement` / `-IncludeMisalignedAutoTurn`; failed steps preserve nested command output for foreground/focus abort diagnosis |
| V3 movement readiness | v3-prep blocker cleared and repeated for deliberately misaligned live routes: `navigation-prototype-20260423-195303-923` corrected about `19.9°` to about `2.7°`, and `navigation-prototype-20260423-201344-231` corrected about `20.0°` to about `2.1°`; both sent one corrective `d` pulse and arrived through strict `coord-trace-anchor` forward travel; still needs broader terrain/route-chain decisions before promotion |
| ReaderBridge orientation probe | still empty on the current client |
| `--read-player-orientation` reader mode | live mode works again when called with `--pid` / `--process-name` through the behavior-backed lead; artifact-only mode remains historical |
| `capture-actor-orientation.ps1` | working again for the current session through a live behavior-backed lead |
| Actor yaw / pitch truth | working on the current live session via source `0x12CC0FA0F70` and forward basis row `+0xD4/+0xD8/+0xDC` |
| Source-chain / accessor-family provenance | refreshed again on the current live session; when the refreshed low-level trace cluster drops the older signature, the source-chain step now rebuilds fresh from the last-good suggested source-chain pattern scan |
| Selector-owner / owner-components / owner-graph / stat-hub provenance | refreshed again on the current live session |
| April 22 source-chain/accessor-family actor-facing result | historical evidence only until separately re-proven on the current session |
| Camera yaw / pitch / distance on `main` | stale / unverified after the update |
| Authoritative camera controller | not yet isolated |

## Fresh proof coord anchor truth

Fresh live validation on **April 23, 2026** established:

- canonical live coord region: `0x12C9B02B888`
- canonical live coord-trace object base: `0x12C9B02B888`
- current trace-linked source object: `0x12C9B02B840`
- source-object coord offset: `+0x48`
- current proof cache file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json`
- current proof watchset file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\proof-polling-watchset.json`

Fresh direct validation on the same live PID showed:

- `--read-player-coord-anchor` still matches the current ReaderBridge coords
- the refreshed proof cache still points at the same `coord-trace-object`
- the refreshed watchset still includes the required `coord-trace-coords` region

Operational interpretation:

- the validated coord-trace anchor remains the **only** proof-grade movement
  source
- `--navigate-waypoints` now fails closed unless that coord-trace anchor is
  available and trusted for the current process
- cached player-current anchors and reacquired player-signature anchors remain
  read-only fallback aids only; they are not accepted as live movement proof
- if the full `resolve-proof-coord-anchor.ps1` refresh path cannot reacquire a
  fresh trace because the CE bootstrap/server is unavailable, use direct
  `--read-player-coord-anchor` validation to confirm the current-process trace
  first before trusting any existing proof cache

## Fresh actor yaw / pitch truth

Fresh live agentic discovery on **April 23, 2026** promoted a new
current-session lead, and the later provenance-only pass retained it:

- canonical live source address: `0x12CC0FA0F70`
- canonical forward basis row:
  - `X = +0xD4`
  - `Y = +0xD8`
  - `Z = +0xDC`
- canonical formulas:
  - yaw = `atan2(forwardZ, forwardX)`
  - pitch = `atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))`

Fresh live checks on the promoted lead:

- `refresh-actor-facing-discovery.ps1 -RestartSession -StimulusMode AutoHotkey`
  promoted `0x12CC0FA0F70 @ +0xD4` from the current-session ranked candidate
  pool after reversible D/A validation with zero coord drift
- `refresh-actor-facing-discovery.ps1 -RunProvenance` confirmed the
  source-chain -> selector-owner -> owner-components -> owner-graph ->
  accessor-family -> stat-hub provenance lane on the same PID without
  replacing the promoted live truth
- `capture-actor-orientation.ps1 -Json -ProcessName rift_x64` resolved the live
  source again through the behavior-backed lead and recomputed yaw/pitch from
  `Basis@0xD4.Forward`
- `dotnet ... -- --process-name rift_x64 --read-player-orientation --json`
  resolved the same live source and the same `Basis@0xD4.Forward`
- the current live yaw/pitch remained derivable from that basis without falling
  back to owner-component artifacts

Operational interpretation:

- the repo now carries a behavior-backed lead file at:
  - `C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json`
- the current live actor-facing truth is the validated `0xD4` forward row on
  `0x12CC0FA0F70`, not the earlier April 23 revalidated lead at
  `0x12CAF6F7080` or the older April 22 source-chain `+0x60/+0x94` result
- the current lead is facing-only truth; the same capture still showed
  `Coord48` / `Coord88` on this source do **not** match the current player
  coords, so this lead is not a movement coord source
- `--read-navigation-current` can now reuse the same live behavior-backed lead
  to report read-only preflight movement-space yaw, heading delta, and
  suggested turn direction, and `--navigate-waypoints` can now opt into
  pre-movement auto-turn with `--auto-turn-before-move`
- reader-core auto-turn remains fail-closed and movement-anchor-strict; the
  deliberately misaligned live route proof has now passed end-to-end twice
  (`navigation-prototype-20260423-195303-923` and
  `navigation-prototype-20260423-201344-231`), but broader v3 promotion still
  needs route/terrain scope decisions
- route-chain planning is available as a read-only v3 slice through
  `--plan-navigation-route`; active multi-segment movement is now explicitly
  gated through `--navigate-waypoint-route`, but live route proofing and
  terrain/obstacle scope are still pending
- the same-session provenance lane is live again, and the current
  `capture-player-source-chain.ps1` step now rebuilds fresh with
  `Recovery.Mode = rebuild-from-suggested-source-chain-pattern` when the
  refreshed low-level coord cluster no longer contains the older
  `mov rcx,[rax+78]` signature
- same-session `reuse-previous-source-chain` remains the last-resort fallback
  only if that fresh pattern-scan rebuild path fails
- the earlier April 22 source-chain/accessor-family result at
  `0x24F595F8D10 @ +0x60/+0x94` remains useful historical evidence, but it is
  no longer the living authority for the current live session
- `capture-actor-orientation.ps1` and `--read-player-orientation` now agree on
  the same live lead again for the current PID

See the current live lead / proof artifacts:

- `C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-actor-orientation.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-discovery\session.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-truth-proof.json`
- for a one-shot same-session proof that validates the live lead, capture parity,
  reader parity, and current provenance posture together:
  - `C:\RIFT MODDING\RiftReader\scripts\assert-actor-facing-truth.ps1`
- for the focused actor-facing proof regressions plus current source-chain
  recovery / fresh rebuild self-checks in one command:
  - `C:\RIFT MODDING\RiftReader\scripts\test-actor-facing-proof-suite.ps1`
- for planning / delegation on how to elevate facing to durable truth without
  regressing the current lead:
  - `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-23-actor-facing-truth-planning-prompt.md`
- for navigation smoke-route, facing-aware preflight, and current auto-turn
  proof checks in one command:
  - `C:\RIFT MODDING\RiftReader\scripts\navigation\test-navigation-proof-suite.ps1`

## ReaderBridge / addon orientation status

Fresh inspection on **April 20, 2026** still showed:

- `orientationProbe` block present
- player unit available
- direct heading API unavailable
- direct pitch API unavailable
- no player detail/state/stat orientation candidates surfaced

So the addon/API lane still does **not** expose a usable direct orientation
signal on the current client. Actor yaw / pitch truth is currently coming from
the validated live memory basis above, not from ReaderBridge orientation fields.

## Broken or stale right now

- the April 22 source-chain/accessor-family actor-facing promotion docs are now
  historical-only; do not treat them as the current live authority unless they
  are separately re-proven again
- `capture-player-source-chain.ps1` can still fall back to
  `Recovery.Mode = reuse-previous-source-chain` if the fresh pattern-scan
  rebuild path fails; treat that as a same-session provenance aid, not as
  fresh raw source-chain proof
- fresh coord-trace reacquisition still depends on a working CE/bootstrap path
  when the current trace artifact no longer validates
- `--read-player-orientation` without `--pid` / `--process-name` remains the historical artifact-only path until the owner/source artifact path is rebuilt

## Canonical scripts on `main`

- `C:\RIFT MODDING\RiftReader\scripts\capture-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-actor-facing-discovery.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\profile-actor-orientation-keys.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1`

## Camera script location note

The currently documented live camera helpers are **not present** on the `main`
worktree during this pass.

The active camera workflow currently lives on:

- branch: `feature/camera-orientation-discovery`
- worktree: `C:\RIFT MODDING\RiftReader_camera_feature`

Relevant scripts there:

- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\read-live-camera-yaw-pitch.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\find-live-camera-angle-candidates.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\test-camera-stimulus.ps1`

Do not treat camera outputs as current truth on `main` until the camera path is
revalidated on the updated client.
