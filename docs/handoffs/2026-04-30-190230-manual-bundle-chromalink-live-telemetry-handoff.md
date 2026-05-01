# RiftReader Handoff — Manual Bundle + Targeted ChromaLink Live Telemetry Plan

Created: 2026-04-30T19:02:30-04:00  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`  
HEAD: `effe053`  
Status before writing this handoff:

```text
## main...origin/main
```

## TL;DR

- **Do not use `ReaderBridgeExport.lua` SavedVariables as live coordinate truth.** It is a post-save snapshot surface and normally updates only after `/reloadui`, logout, UI shutdown, or another save event.
- `manual-bundle-001` produced useful visual/live overlay truth, but only **7 unique displayed X values** across **29 1Hz samples**; samples **1-7** contain useful X movement and samples **8-29** are stationary tail.
- The previous file-backed ReaderBridge/SavedVariables seed list is **stale-risk candidate data only**, not promotion truth.
- The next strategic path is a **targeted ChromaLink-style live telemetry bridge** for player position and freshness metadata, not a wholesale ChromaLink merge.
- Keep **CE out of this lane** unless the user explicitly re-approves it. Use repo/helper/debug-scanning workflows instead.

## Current truth model

| Surface | Role | Current classification | Notes |
|---|---|---|---|
| In-game overlay screenshots + manual extract | Authoritative truth for `manual-bundle-001` | `overlay-screenshot-manual-extract` | Use `overlay-coords-manual-extract.csv` and summary JSON. |
| ChromaLink-style live relay | Planned live truth/telemetry source | Not integrated yet | Target for player position, sequence IDs, freshness, lifecycle metadata. |
| Native memory reads from candidate addresses | Candidate/negative evidence | Valid only when compared to live truth | Current seed reads are not sufficient for promotion. |
| `ReaderBridgeExport.lua` SavedVariables | Backup/post-flush snapshot only | `stale-post-save-snapshot` | `usableAsLiveTruth=False`. |
| `seed-addresses.json` | Candidate seed list only | stale-risk | Derived from stale-risk SavedVariables-backed scan. |

## Manual bundle artifacts

| Artifact | Path / value |
|---|---|
| Bundle nickname | `manual-bundle-001` |
| Bundle root | `C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012` |
| Stream run | `C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451` |
| Stream summary | `C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451\stream-summary.json` |
| Overlay truth CSV | `C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451\overlay-coords-manual-extract.csv` |
| Overlay summary | `C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451\overlay-coords-manual-extract-summary.json` |
| Truth surface metadata | `C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451\truth-surface.json` |
| SavedVariables freshness metadata | `C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451\savedvariables-freshness.json` |
| Clean samples | `C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451\samples-recording-only.ndjson` |
| Screenshots | `C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451\screenshots` |
| Memory seed reads | `C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451\memory` |
| Crop contact sheets | `C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451\coord-crops-v2` |

## Manual bundle facts

| Fact | Value |
|---|---|
| Capture start | `2026-04-30T18:25:38.5260594-04:00` |
| Capture end | `2026-04-30T18:26:07.5425475-04:00` |
| Duration | `29.016s` |
| Sample count | `29` |
| Sample interval | `1.0s` |
| Stop reason | `stop-file` |
| Error count | `0` |
| Unique displayed X count | `7` |
| Unique displayed X values | `7454.6, 7455.7, 7456.9, 7458.1, 7459.3, 7460.5, 7461.0` |
| Useful motion samples | `1-7` |
| Stationary tail | `8-29` |

## SavedVariables design flaw now documented

`ReaderBridgeExport.lua` is not a live IPC/feed. It is a RIFT SavedVariables file and therefore should be treated as a delayed post-save snapshot. The manual stream showed this directly: overlay coordinates moved around the `7454.6 -> 7461.0` X range while stale file-backed data remained in a different coordinate area. Future recorders must fail closed or label data as stale if SavedVariables are used as live truth.

Primary documentation:

| Document | Purpose |
|---|---|
| `C:\RIFT MODDING\RiftReader\docs\recovery\savedvariables-live-capture-design-flaw.md` | Strong design flaw note and required source rules. |
| `C:\RIFT MODDING\RiftReader\docs\todos\2026-04-30-coord-discovery-workflow-todo.md` | Coord-discovery workflow TODO, now corrected for SavedVariables limitations. |
| `C:\RIFT MODDING\RiftReader\docs\todos\2026-04-30-chromalink-targeted-live-telemetry-integration-plan.md` | Formal targeted ChromaLink live telemetry integration plan. |
| `C:\RIFT MODDING\RiftReader\docs\assistant-operating-policy.md` | Operating-policy surface updated for live truth declarations. |
| `C:\RIFT MODDING\RiftReader\agents.md` | Repo agent policy surface. |

## Targeted ChromaLink integration plan

### Reuse selectively

| Reuse from ChromaLink | Why |
|---|---|
| `Event.System.Update.Begin` refresh loop | Live in-game cadence independent from SavedVariables flush timing. |
| ~0.10s refresh cadence concept | Better than 1Hz/manual-only capture for motion/candidate scoring. |
| Pixel/symbol telemetry strip and decoder ideas | Existing live relay pattern that can be adapted to player data. |
| `playerPosition` frame concept | Directly relevant to coord truth/candidate discovery. |
| Sequence IDs + timestamps + freshness metadata | Detect stale/frozen/lagged telemetry instead of trusting files blindly. |
| Helper workflow pattern: readiness -> dispatch -> telemetry watch -> result summary -> recovery | Avoids treating input dispatch as proof without observed telemetry. |

### Do not port initially

| Excluded initially | Reason |
|---|---|
| Full ChromaLink addon/helper repo | Too broad; use only the live relay patterns needed here. |
| RiftMeter/combat model | Useful later as teacher/reference, not needed for player coord discovery. |
| Ability/aura/full target/combat telemetry | Defer until player-position live feed is proven. |
| Navigation promises | The relay can assist testing, but does not solve route graph/pathfinding by itself. |

### Planned phases

| Phase | Outcome |
|---|---|
| 1. Metadata hardening | Every capture declares truth surface, freshness, source role, and lifecycle. |
| 2. Prototype existing ChromaLink playerPosition feed | Verify live movement telemetry without `/reloadui`. |
| 3. Build ReaderBridgeLive / ChromaLink-lite | Minimal player-position feed inside RiftReader workflow. |
| 4. Robust logging/metadata | Produce `live-coords.ndjson`, process/window identity, input events, quality gates. |
| 5. Candidate scoring integration | Compare memory candidates against full movement trajectory, not isolated points. |
| 6. Expand after player position | Reuse live telemetry for movement, stuck detection, facing, target, combat, replay tests. |

## Required logging/metadata upgrades

| Artifact | Required purpose |
|---|---|
| `artifact-index.json` | Map every file in a bundle to source, role, freshness, and validity. |
| `capture-plan.json` | Record experiment intent, expected movement, selected truth source, and stop conditions. |
| `process-window.json` | Capture PID/HWND/client identity/helper target identity. |
| `truth-surface.json` | Declare authoritative vs candidate vs backup surfaces. |
| `savedvariables-freshness.json` | Explicitly state stale/post-flush status and usability. |
| `recorder-preflight.json` | Verify live relay readiness before `START`. |
| `capture-lifecycle.ndjson` | Log START/STOP, recorder startup latency, and any delayed prompts. |
| `input-events.ndjson` | Record W/key/helper actions with target PID/HWND and foreground/refocus behavior. |
| `live-coords.ndjson` | Future direct live telemetry source with sequence, timestamp, coords, and freshness. |
| `memory-timeseries.csv` | Candidate memory values sampled across the same movement trajectory. |
| `candidate-trajectory-scores.json` | Rank candidates by X/Y/Z trajectory agreement, slope, lag, staleness, and drift. |
| `promotion-gate.json` | Machine-readable proof that a candidate passed all checks before being treated as truth. |

## Analysis plan for `manual-bundle-001`

| Step | Action | Expected use |
|---|---|---|
| 1 | Treat overlay CSV as the only authoritative truth for this bundle | Avoids stale SavedVariables contamination. |
| 2 | Use samples 1-7 as the movement segment | Only segment with changing displayed X. |
| 3 | Treat samples 8-29 as stationary/control tail | Useful to reject drifting or noisy candidates. |
| 4 | Use current memory seed reads as negative/candidate evidence only | They were produced from stale-risk seed generation. |
| 5 | Run fresh repo/debug-scanning against live overlay coordinates before promotion | No CE; rescan with current live source. |
| 6 | Prefer multi-point trajectory matching over single coordinate matching | Better separation of true coords vs nearby stale/cached values. |

## Immediate resume order

| # | Action | Notes |
|---|---|---|
| 1 | Preserve/commit this handoff and existing docs if desired | Worktree was clean before this handoff write. |
| 2 | Patch recorder metadata surfaces | Add truth/freshness/lifecycle artifacts by default. |
| 3 | Add preflight that rejects SavedVariables-as-live | SavedVariables may remain backup/post-flush only. |
| 4 | Prototype ChromaLink `playerPosition` capture to `live-coords.ndjson` | Fastest path to live truth independent of `/reloadui`. |
| 5 | Validate prototype with a short movement sequence | Compare live relay coords to overlay screenshots. |
| 6 | Build candidate trajectory scorer | Score memory candidates against full movement string. |
| 7 | Rescan current process candidates using live overlay/relay truth | Existing seeds are stale-risk. |
| 8 | Promote only after passing `promotion-gate.json` | Avoid another stale-current truth regression. |

## Resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read this handoff first:
C:\RIFT MODDING\RiftReader\docs\handoffs\2026-04-30-190230-manual-bundle-chromalink-live-telemetry-handoff.md

Continue the no-CE player-coordinate discovery lane. Treat SavedVariables as backup/post-flush only, use manual-bundle-001 overlay CSV as current bundle truth, and implement the targeted ChromaLink-style live player-position telemetry plan plus robust metadata logging before promoting any memory candidate.
```
