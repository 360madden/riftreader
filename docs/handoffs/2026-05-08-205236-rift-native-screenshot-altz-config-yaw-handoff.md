# RIFT native screenshot + Alt+Z config/yaw handoff

Created: 2026-05-08 20:52:36 -0400
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
HEAD: `113b261`

## TL;DR

- Native in-game screenshot blocker was overcome by using RIFT's current `Take Screenshot` bind: **`NUM PAD *` / `VK_MULTIPLY`**.
- **Never use `Ctrl+P`, `Control+P`, `PrtSc`, or Snipping Tool for screenshot automation** on this machine.
- Screenshot backend/docs/tests were committed and pushed in commit `113b261` (`Document native Rift screenshot backend`). Current HEAD at handoff time: `113b261`.
- Current `Alt+Z` camera-zoom config file is `C:\Users\mrkoo\AppData\Roaming\Rift\rift.cfg`.
- Current config has a visible alt-zoom setup: normal `20` and alt `60`, with `useAltDistScale = False` so `Alt+Z` should toggle `20 <-> 60`.
- The config file is **not read-only**, so RIFT can rewrite it again. That is the likely reason it previously went back to all `20`.
- `rift.cfg` contains `[Camera] yaw/pitch` and `[Window] yaw/pitch`. Treat those as persisted snapshots only unless a `/reloadui` flush test proves a fresh write.

## Hard rules carried into next session

| Rule | Required behavior |
|---|---|
| Screenshot key | Use only `NUM PAD *` / `numpad_multiply` / `VK_MULTIPLY` for RIFT native screenshots. |
| Forbidden screenshot keys | Do **not** send `Ctrl+P`, `Control+P`, `PrtSc`, Windows Snipping Tool shortcuts, or PrintScreen. |
| Live window targeting | Re-discover and focus exact RIFT PID/HWND before any input; do not trust stale PID/HWND. |
| Config yaw | `rift.cfg` yaw/pitch is not continuous live truth; at best it can become a recent post-flush snapshot. |
| Alt zoom preservation | If RIFT keeps resetting custom alt zoom, restore known-good block and set `rift.cfg` read-only after RIFT is closed. |

## Current `rift.cfg` evidence

Path: `C:\Users\mrkoo\AppData\Roaming\Rift\rift.cfg`
LastWriteTime: `2026-05-08 20:45:20 -0400`
Read-only by filesystem mode: `False`

Relevant block observed at handoff time:

```ini
[Camera]
distanceScale = 20.000000
distanceScaleAlt = 60.000000
maxDistanceScale = 20.000000
maxDistanceScaleAlt = 60.000000
pitch = -0.212749
useAltDistScale = False
yaw = 0.010000
[Window]
pitch = -0.732818
useAltDistScale = False
yaw = -0.015000
```

### Alt+Z interpretation

| Field | Current value | Meaning |
|---|---:|---|
| `distanceScale` | `20.000000` | Normal camera distance. |
| `distanceScaleAlt` | `60.000000` | Alternate camera distance. |
| `maxDistanceScale` | `20.000000` | Normal max camera cap. |
| `maxDistanceScaleAlt` | `60.000000` | Alternate max camera cap. |
| `useAltDistScale` | `False` | Keeps `Alt+Z` as the toggle rather than forcing alt zoom always on. |

If it breaks again and all four distance fields become `20`, restore:

```ini
[Camera]
distanceScale = 20.000000
distanceScaleAlt = 60.000000
maxDistanceScale = 20.000000
maxDistanceScaleAlt = 60.000000
useAltDistScale = False
```

Recommended preservation flow:

```powershell
# RIFT must be fully closed before edit/lock.
Copy-Item "C:\Users\mrkoo\AppData\Roaming\Rift\rift.cfg" "C:\Users\mrkoo\AppData\Roaming\Rift\rift.cfg.backup-altzoom-$(Get-Date -Format yyyyMMdd-HHmmss)"
attrib +R "C:\Users\mrkoo\AppData\Roaming\Rift\rift.cfg"
```

Unlock later if normal settings need to be saved:

```powershell
attrib -R "C:\Users\mrkoo\AppData\Roaming\Rift\rift.cfg"
```

## Config yaw/pitch discovery note

The file currently includes:

| Section | Field | Observed value |
|---|---|---:|
| `[Camera]` | `pitch` | `-0.212749` |
| `[Camera]` | `yaw` | `0.010000` |
| `[Window]` | `pitch` | `-0.732818` |
| `[Window]` | `yaw` | `-0.015000` |

Working classification:

```json
{
  "source": "rift.cfg",
  "freshness_without_flush": "stale_or_unknown_persisted_snapshot",
  "freshness_after_proven_reloadui_flush": "recent_post_reloadui_snapshot",
  "live": false,
  "usable_as": ["camera_yaw_seed", "controlled_validation_sample"],
  "not_usable_as": ["movement_polling_truth", "continuous_navigation_yaw"]
}
```

Important conflict:

| Goal | `rift.cfg` read-only? | Why |
|---|---:|---|
| Preserve custom Alt+Z zoom | Yes | Prevents RIFT from resetting `60` to `20`. |
| Sample yaw/pitch via `/reloadui` | No during sample | RIFT needs write permission to flush the config. |
| Both goals | Temporarily unlock, flush/read, restore alt-zoom block, re-lock | Best combined workflow. |

Proposed safe `/reloadui` validation plan for next session:

1. Re-discover exact RIFT PID/HWND.
2. Snapshot `rift.cfg` `LastWriteTime`, `[Camera] yaw/pitch`, and `[Window] yaw/pitch`.
3. Temporarily remove read-only if set.
4. Focus exact RIFT window.
5. Perform a controlled non-movement camera stimulus.
6. Send `/reloadui` safely through chat/slash input.
7. Wait for UI reload/responding state.
8. Re-read `LastWriteTime` and yaw/pitch.
9. Confirm timestamp is after stimulus/reload and values changed plausibly.
10. Restore known-good Alt+Z block and re-lock file if needed.

This would prove a **fresh snapshot** source, not live continuous yaw.

## Native screenshot workflow state

Recent validated behavior from this session:

| Item | Value |
|---|---|
| Required RIFT bind | `Take Screenshot = NUM PAD *` |
| Windows virtual key | `VK_MULTIPLY` / `0x6A` |
| Repo helper | `C:\RIFT MODDING\RiftReader\scripts\rift_native_screenshot.py` |
| Good input method | Exact-window message path for already-bound screenshot key. |
| Forbidden fallback | `Ctrl+P` is now blocked/forbidden for screenshot use. |

Validated native screenshot artifacts from the session:

| Run | Evidence |
|---|---|
| Live pass | `C:\RIFT MODDING\RiftReader\scripts\captures\native-screenshot-numpad-star-live-20260508-200805\rift-native-numpad-multiply-screenshot-20260509-000805.jpg` |
| Failed-test rerun pass | `C:\RIFT MODDING\RiftReader\scripts\captures\native-screenshot-numpad-star-rerun-20260508-201818\rift-native-numpad-multiply-screenshot-20260509-001819.jpg` |
| Prior failed artifact | `C:\RIFT MODDING\RiftReader\scripts\captures\native-screenshot-numpad-star-20260508-194446\native-screenshot-result.json` had `screenshot-timeout` and was overcome by rerun. |

Committed/pushed screenshot slice included:

- `.codex/skills/rift-window-control/SKILL.md`
- `docs/assistant-operating-policy.md`
- `docs/live-testing-python-orchestrator-plan.md` screenshot-specific hunks
- `docs/recovery/README.md`
- `docs/recovery/native-rift-screenshot-backend.md`
- `scripts/profile_turn_keys.py`
- `scripts/rift_live_test/turn_keys.py`
- `scripts/rift_native_screenshot.py`
- `scripts/test_rift_native_screenshot.py`

Known validation from that slice:

```text
python -m py_compile scripts/rift_native_screenshot.py scripts/profile_turn_keys.py scripts/rift_live_test/turn_keys.py scripts/test_rift_native_screenshot.py
python scripts/test_rift_native_screenshot.py      # 2/2
python scripts/test_turn_key_profile.py            # 9/9
python scripts/rift_native_screenshot.py --hwnd 0x5121A --key-chord ctrl+p --json  # correctly refused before input
```

## Repo state at handoff time

Latest commits:

```text
113b261 Document native Rift screenshot backend
54d0fea Prepare actor yaw phase 2 baseline
02b476b Add actor yaw truth handoff
facafb4 Promote actor yaw truth and readback smoke
27e470f Harden RiftScan coordination and actor yaw readiness
```

Working tree has unrelated pre-existing modifications. Do **not** accidentally stage these when only preserving this handoff:

```text
M configs/live-test-profiles.json
 M docs/live-testing-python-orchestrator-plan.md
 M docs/recovery/current-proof-anchor-readback.json
 M docs/recovery/current-truth.md
 M reader/RiftReader.Reader.Tests/Cli/ReaderOptionsParserTests.cs
 M reader/RiftReader.Reader/Cli/ReaderOptionsParser.cs
 M reader/RiftReader.Reader/Program.cs
 M scripts/capture-riftscan-proof-pose.ps1
 M scripts/invoke-gated-forward-smoke.ps1
 M scripts/post-rift-key.ps1
 M scripts/rift_live_test/baselines.py
 M scripts/rift_live_test/gui.py
 M scripts/rift_live_test/reports.py
 M scripts/rift_live_test/riftscan_coordination.py
 M scripts/rift_live_test/riftscan_milestone_review.py
 M scripts/rift_live_test/riftscan_validation.py
 M scripts/rift_live_test/runner.py
 M scripts/rift_live_test/status.py
 M scripts/test-capture-riftscan-proof-pose-pointer.ps1
 M scripts/test-invoke-gated-forward-smoke.ps1
 M scripts/test_current_proof_pointer.py
 M scripts/test_live_test_orchestrator.py
 M scripts/test_riftscan_milestone_review.py
 M scripts/test_riftscan_validation.py
?? docs/recovery/historical/current-proof-anchor-readback-2026-05-08-pid33912-hwndE0DB2-historical.json
```

## Resume prompts

### If resuming Alt+Z repair

```text
Resume from newest handoff. First inspect C:\Users\mrkoo\AppData\Roaming\Rift\rift.cfg. If alt zoom reset, restore [Camera] distanceScaleAlt/maxDistanceScaleAlt to 60, keep useAltDistScale=False, and only set read-only after RIFT is fully closed. Do not touch screenshot keys except NUM PAD *.
```

### If resuming cfg yaw snapshot proof

```text
Resume from newest handoff. Plan and run a non-movement /reloadui freshness test for rift.cfg yaw/pitch. Treat rift.cfg yaw as stale until LastWriteTime proves a post-stimulus flush. Temporarily unlock rift.cfg only during the flush test, then restore Alt+Z config and re-lock if needed. Do not use CE.
```

### If resuming native screenshot workflow

```text
Resume from newest handoff. Use scripts/rift_native_screenshot.py with RIFT Take Screenshot bound to NUM PAD * / VK_MULTIPLY only. Never send Ctrl+P or PrintScreen. Re-discover exact RIFT PID/HWND before input.
```

## Open questions / blockers

| Question | Current answer |
|---|---|
| Does `/reloadui` flush `rift.cfg` yaw/pitch? | Not proven yet. Needs controlled test. |
| Is `rift.cfg` yaw live enough for navigation? | No. It is at best a snapshot after a proven flush. |
| Should `rift.cfg` be read-only now? | Good for preserving Alt+Z, bad for yaw sampling; choose based on current task. |
| Is current RIFT PID/HWND still valid? | Unknown/stale. Must re-discover before live input. |
| Are unrelated repo changes safe to commit? | Unknown. They predate this handoff lane and need separate review. |

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Decide immediate lane: Alt+Z repair vs cfg-yaw freshness proof | The read-only choice differs by lane. |
| 2 | If repairing Alt+Z, close RIFT before changing `rift.cfg` | Prevents overwrite-on-exit. |
| 3 | Preserve `20 <-> 60` config and set read-only only after repair | Stops RIFT resetting alt zoom. |
| 4 | Save a known-good `rift.cfg` backup after Alt+Z works | Fast manual rollback. |
| 5 | If proving yaw snapshot, temporarily unlock `rift.cfg` | RIFT must be allowed to write during `/reloadui`. |
| 6 | Make `/reloadui` proof non-movement only | Avoids navigation risk while testing config freshness. |
| 7 | Require timestamp proof before trusting yaw/pitch | Prevents stale snapshot contamination. |
| 8 | Keep config yaw separate from live memory yaw candidates | It can seed discovery but not prove runtime truth. |
| 9 | Continue using only `NUM PAD *` for screenshots | Keeps the screenshot blocker solved and avoids forbidden keys. |
| 10 | Before any commit, isolate this handoff from unrelated dirty files | Current worktree has many pre-existing modified files. |
