# Current Truth

_Last updated: April 15, 2026 (post-update triage + Desktop-2 focus-enforced actor-yaw recovery)_

## Current status

| Area | Status |
|---|---|
| Low-level reader | reliable enough for active work |
| ReaderBridge snapshot load | working |
| Player current read | working |
| Coord-anchor module pattern | working |
| Source-chain refresh | broken after the update |
| Selector-owner trace | broken after the update |
| CE scan / inspection lane | usable for bounded reintegration |
| CE debugger-trace lane | suspected Windows debugger attach instability; keep opt-in and log repeated failures before patching guards |
| Player orientation read | recovered on `codex/actor-yaw-pitch` via focused-PostMessage live actor-yaw recovery; old owner/source-chain artifacts on `main` remain stale |
| Camera yaw / pitch / distance on `main` | stale / unverified after the update |
| Authoritative camera controller | not yet isolated |
| Direct gameplay key stimulus on `main` | focused `PostMessage` via `post-rift-key.ps1 -RequireTargetFocus` is the trusted Desktop-2 default; foreground `SendInput` remains untrusted |

## Post-update note

Use this report before trusting older actor/camera captures:

- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-post-update-anchor-drift-report.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-camera-workflow-branch-audit.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-live-camera-script-behavior-and-offset-drift.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-actor-orientation-stop-point-and-resume-plan.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-cheat-engine-reintegration-and-attach-failure-plan.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-15-live-key-delivery-recheck.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-15-actor-yaw-focused-postmessage-recovery.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-15-aggressive-wrapper-unattended-validation.md`
- `C:\RIFT MODDING\RiftReader\docs\input-safety.md`

## Surviving baselines

### Player current

Still working from the cache/blob family:

- family id: `fam-6F81F26E`
- signature: `level@-144|health[1]@-136|health[2]@-128|health[3]@-120|coords@0`

### Coord anchor

Still working as a module-local pattern:

- pattern: `F3 0F 10 86 5C 01 00 00`
- updated module offset observed during triage: `0x93560E`
- inferred coord offsets: `0x158 / 0x15C / 0x160`

## Broken or stale right now

- `capture-player-source-chain.ps1` no longer locates the expected source-container load
- `trace-player-selector-owner.ps1` can remain `armed` without a hit
- `player-selector-owner-trace.json` is stale until regenerated
- `player-owner-components.json` is stale until regenerated
- `player-actor-orientation.json` is stale until regenerated

## Actor yaw / pitch recovery direction

The current recommended recovery path is:

1. addon-first orientation probing
2. export any API-visible heading / pitch / facing candidates
3. inspect the latest exported probe with `C:\RIFT MODDING\RiftReader\scripts\inspect-readerbridge-orientation.ps1`
4. use CE scan / inspection only as a secondary discovery lane when it helps
5. only then fall back to raw-memory rediscovery or CE debugger-trace if the addon layer yields nothing useful

For live actor-yaw screening on `codex/actor-yaw-pitch`:

- do **not** assume `Codex` staying foreground is enough
- Rift may still reject most live input unless the game window itself takes focus
- use focused `PostMessage` as the trusted live-input lane:
  - `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1 -RequireTargetFocus`
  - `C:\RIFT MODDING\RiftReader\scripts\screen-actor-orientation-candidates.ps1 -RequireTargetFocus`
  - `C:\RIFT MODDING\RiftReader\scripts\run-aggressive-actor-yaw-discovery.ps1`
- if focus cannot be verified, stop and require operator intervention instead of falling through to `SendInput`
- when Rift is isolated on Desktop 2, screenshot-based UI clear checks are not authoritative unless that desktop is visible; the aggressive wrapper skips that gate by default
- the reusable workflow backups for future live feature recovery/discovery now live here:
  - `C:\RIFT MODDING\RiftReader\docs\recovery\focused-postmessage-discovery-workflow.md`
  - `C:\RIFT MODDING\RiftReader\docs\recovery\focused-postmessage-discovery-prompt.json`

Validated actor-yaw winners on `codex/actor-yaw-pitch`:

1. first manual pinned validation:
   - source address: `0x245D78DCB50`
   - basis forward offset: `0xD4`
   - artifact:
     - `C:\RIFT MODDING\RiftReader\scripts\captures\screening\aggressive\recovery-245d78dcb50-basis-d4.manual.nowarning.json`
2. later unattended wrapper validation:
   - source address: `0x245B92311D0`
   - basis forward offset: `0xD4`
   - artifact:
     - `C:\RIFT MODDING\RiftReader\scripts\captures\screening\aggressive\recovery-245b92311d0-basis-d4.json`

Shared recovery properties:

- focused `PostMessage`
- opposite-direction A/D gate passed
- `YawRecovered = true`
- `PitchRecovered = true`
- zero coord drift on the winning pass(es)
- basis family remains validated at `0xD4`

Operational truth:

- the unattended aggressive wrapper is now live-validated
- if forced ReaderBridge refresh fails, the wrapper can retry without refresh and still recover yaw
- the wrapper can stop immediately after the first validated yaw winner

Important nuance:

- the first pinned recovery against this same source failed as `idle_drift`
- that was workflow-induced by repeated live-warning countdown delays, not by the candidate itself
- the successful path suppressed those warning delays during AI-driven recovery
- the later unattended wrapper validation also confirmed that refresh-lane failure is no longer a hard blocker if the no-refresh path remains viable

Do **not** treat the old debugger-driven owner/source chain as the default first
step for actor yaw / pitch recovery on the updated client. Use:

- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-actor-orientation-stop-point-and-resume-plan.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-cheat-engine-reintegration-and-attach-failure-plan.md`

If CE shows:

- `Error attaching the windows debugger: 87`

log the run and stop the debugger-trace attempt for that pass. Do **not** patch
the Lua attach guards until that failure is repeated and documented across
multiple fresh runs.

## Canonical scripts on `main`

- `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1`

## Camera script location note

The currently documented live camera helpers are **not present** on the `main`
worktree during this post-update triage pass.

The active camera workflow currently lives on:

- branch: `feature/camera-orientation-discovery`
- worktree: `C:\RIFT MODDING\RiftReader_camera_feature`

Relevant scripts there:

- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\read-live-camera-yaw-pitch.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\find-live-camera-angle-candidates.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\test-camera-stimulus.ps1`

Do not treat camera outputs as current truth on `main` until the actor/source
chain is rebuilt and the camera path is revalidated on the updated client.

## Camera offset drift snapshot

As of `2026-04-14`, these old camera references are **historical only**:

- yaw basis on selected-source:
  - `+0x60/+0x68/+0x78`
  - duplicate `+0x94/+0x9C/+0xAC`
- pitch / distance via `entry15` orbit coordinates:
  - `+0xA8/+0xAC/+0xB0`
  - duplicate `+0xB4/+0xB8/+0xBC`

The last-known pre-update object addresses used for that model are now stale:

- selected-source base: `0x1FDA0D13170`
- `entry15` base: `0x1FD9FA6F190`

Direct raw reads against those addresses failed during the live drift check, so
they should not be reused as current offsets without a fresh object recovery.

Preferred live camera probe for post-update work:

- `C:\RIFT MODDING\RiftReader\scripts\probe-live-camera-offset-diff.ps1`

Do **not** use the legacy angle-candidate script as the default live camera
probe path.

## Tier-1 artifacts

These remain Tier 1, but they are currently **pre-update stale** until rebuilt:

- `C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-graph.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-stat-hub-graph.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-actor-orientation.json`

## Do not trust these as current truth

- pre-update owner/source/actor-orientation artifacts unless regenerated after the update
- selected-source `+0xB8..+0x150` camera window
- selected-source `+0x7D0` camera basis idea
- `entry4 +0x1D0` as a confirmed direct pitch scalar
