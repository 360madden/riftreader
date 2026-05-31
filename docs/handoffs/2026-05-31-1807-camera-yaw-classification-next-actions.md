# RiftReader compact handoff — camera/yaw classification next actions

Generated UTC: `2026-05-31T18:13Z`

# **⚠️ BLOCKED-SAFE — TURN/YAW NOT ROUTE-ACTIONABLE**

The latest pushed slice added a reusable camera/yaw classifier and proved the
current blocker:

**visual camera movement occurred, but the current static-owner yaw candidate did
not change.**

This handoff exists to preserve the current recommended next actions so they can
be resumed later without re-reading the full chat.

## Repo state at handoff

| Field | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` |
| HEAD | `1807db772bac25c7248f6686981cabc2aa782983` |
| HEAD subject | `Add camera yaw classification helper` |
| Remote | `origin/main` was current after push |
| Worktree before this handoff file | Clean |

Newest relevant commits at handoff:

| Commit | What |
|---|---|
| `1807db7` | Add camera yaw classification helper |
| `dfc7a65` | Document blocked turn-yaw recheck |
| `142deab` | Record approved bounded route validation |
| `a19e1a6` | Refresh current truth from no-input readback |
| `caeca92` | Refresh handoff with truth plan status |
| `059832a` | Surface truth refresh plan in workflow status |
| `b5fb8f5` | Refresh handoff with truth refresh plan |
| `f5f8bc2` | Document current truth refresh plan |
| `a539850` | Add current truth refresh plan helper |
| `16f9323` | Document navigation pointer status workflow |

## Current truth boundary

| Item | Status |
|---|---|
| Static coordinate resolver | **Promoted for player coordinates only**: `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Current target metadata | PID `25668`, HWND `0x320CB0`, process start `2026-05-30T02:46:41.581536+00:00`, module base `0x7FF6EE5D0000` |
| Latest tracked coordinate/API truth | Static readback at `2026-05-31T16:37:49.159175+00:00`; RRAPICOORD API-now matched at `2026-05-31T16:37:59.8565695Z` |
| Actor/stat chain | **Not promoted** |
| Facing/turn-rate chain | **Not promoted**; latest current client state requires reacquisition |
| Route movement | Do not run turn-dependent routes until fresh turn/yaw proof passes |

## Latest live finding

Artifact:

`C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-camera-yaw-classification-20260531-174422-894291\summary.json`

| Check | Result |
|---|---|
| Classifier verdict | `visual-changed-static-yaw-unchanged` |
| Visual raw diff | `74.077341%` changed pixels |
| Static yaw before | `22.962550463694146°` |
| Static yaw after | `22.962550463694146°` |
| Signed yaw delta | `0.0°` |
| Coordinate before/after | unchanged at `7267.5234375, 821.6994018554688, 3005.181640625` |
| `owner+0x30C/+0x310/+0x314` | unchanged in this run |
| Changed focus offsets | `owner+0x300` delta `+58.1875`; `owner+0x304` delta `-0.6050287485122681`; `owner+0x408` delta `+0.0034160614013671875` |
| Pointer neighborhood | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-camera-yaw-classification-20260531-174422-894291\pointer-owner-neighborhood-post\summary.json` |

Visual artifacts:

| Type | Path |
|---|---|
| Baseline PNG | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-camera-yaw-classification-20260531-174422-894291\visual-baseline\images\full-window.png` |
| Post PNG | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-camera-yaw-classification-20260531-174422-894291\visual-post\images\full-window.png` |

Safety boundary for the latest run:

| Boundary | Result |
|---|---|
| Mouse-look/input | Sent under explicit approval |
| Route movement | Not sent |
| Cheat Engine / x64dbg | Not used |
| Provider writes | None |
| Target memory writes | None |
| Proof/facing/actor promotion | None |

## Recommended next actions to resume later

| # | Action | Why |
|---:|---|---|
| 1 | Run a left/right/return camera-yaw classification sequence. | Need directionality for `owner+0x300` and `owner+0x304`. |
| 2 | Compare `owner+0x300` against visual heading changes. | It changed strongly while `owner+0x30C/+0x310/+0x314` stayed stale. |
| 3 | Compare `owner+0x304` across left/right pulses. | It may be transient turn/camera rate, not route yaw. |
| 4 | Keep `owner+0x30C/+0x310/+0x314` candidate-only and stale for current camera-turn state. | Latest live evidence did not update those fields. |
| 5 | Add a compact multi-pose report mode to `static_owner_camera_yaw_classification.py`. | Reduces manual comparison across multiple classification runs. |
| 6 | Do not run turn-dependent routes yet. | No current route-actionable yaw/control field is proven. |
| 7 | Refresh no-input static coordinate/nav-state before the next live run. | Decision packet marks latest readbacks stale by age. |
| 8 | Add latest camera-yaw classification indexing to the navigation discovery dashboard. | Keeps resume/status packets aware of this evidence class. |
| 9 | Refresh API-now only if updating tracked current truth. | The latest slice was classification evidence, not current-truth promotion. |
| 10 | After candidate semantics are clear, run one small proof pack before route movement. | Keeps proof separate from route execution and prevents over-promotion. |

## Resume checklist

Use this order next time:

1. Review this handoff and `docs\HANDOFF.md`.
2. Run a clean-state check:
   ```powershell
   git --no-pager status --short --branch
   git --no-pager log -10 --oneline
   ```
3. Refresh the local decision packet:
   ```powershell
   cmd /c scripts\riftreader-decision-packet.cmd --compact-json --write
   ```
4. Refresh no-input exact-target readbacks before any live input:
   ```powershell
   cmd /c scripts\static-owner-coordinate-chain-readback.cmd --use-current-truth --samples 3 --interval-seconds 0.20 --expect-stationary --json
   cmd /c scripts\static-owner-nav-now.cmd --json
   ```
5. If continuing live discovery, bind/focus/capture the exact game window first,
   then run only a bounded candidate-only classification such as:
   ```powershell
   python scripts\static_owner_camera_yaw_classification.py `
     --direction right --pixels 120 --stimulus-approved --json
   ```
6. Do **not** run route movement, ProofOnly, actor-chain/facing promotion,
   x64dbg, Cheat Engine, or provider writes unless explicitly re-approved for
   that exact boundary.

## Last validation/publish state

| Check | Result |
|---|---|
| Full local validation | Passed |
| Ledger | `C:\RIFT MODDING\RiftReader\.riftreader-local\validation-runs\20260531-175151-470597\summary.md` |
| Full local duration | `538.919s` |
| Slow note | `unittest-discover` took `500.293s` vs `420s` budget but passed |
| GitHub `.NET build and test` | Success for `1807db7` |
| GitHub `RiftReader Policy` | Success for `1807db7` |

## Handoff boundary

This handoff is a saved resume artifact only. It does not update tracked current
truth, does not promote facing/turn-rate/actor chains, and does not authorize
future live input by itself.
