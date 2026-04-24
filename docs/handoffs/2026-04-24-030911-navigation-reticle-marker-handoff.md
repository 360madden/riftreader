# RiftReader Navigation / Marker Handoff — 2026-04-24 03:09:11 -04:00

## TL;DR

Current branch is `navigation`. Today's most useful result is that **AHK ControlSend is the strongest current background/unfocused key-input method**, and the **fishing/ground-target circle can be displayed client-side by pressing hotbar key 5** without clicking/casting. The next highest-impact work is to determine whether that reticle has safe, readable/writable client-side state that can become a display-only waypoint marker.

## Current Repo State

| Item | Status |
|---|---|
| Repo | C:\RIFT MODDING\RiftReader |
| Branch at handoff creation | $branch |
| HEAD at handoff creation | $head |
| Worktree before handoff write | $([string]::IsNullOrWhiteSpace() ? 'Clean' : 'Had existing changes; see git status') |
| Handoff file | $path |
| Live movement invariant | Resolve validated coord-trace anchor before any movement polling / forward-hold proof / coordinate-driven capture |

## Confirmed Input Method Results

| Method | Focused Rift | Unfocused Rift | Verdict |
|---|---:|---:|---|
| PostMessage | Visually worked | Not proven as best path | Useful but weaker than ControlSend |
| AHK ControlSend | Visually worked | **Worked visually while Rift stayed unfocused** | **Best current candidate** |
| NutJS global keyboard | Worked when focused | Failed; keys went to foreground app | Not suitable for background HWND input |
| NutJS by HWND | Could resolve Rift window only | Failed; keyboard was still foreground-global | Not suitable via public API |

### Strongest Unfocused Input Proof

| Check | Result |
|---|---|
| Foreground app | Fresh Notepad |
| Rift state | Unfocused |
| Sent keys | W/A/S/D via AHK ControlSend to Rift HWND |
| Rift response | Large visual frame changes |
| Notepad received WASD? | No; clipboard sentinel check stayed unchanged |
| Limitation | Visual proof only; not coordinate/facing proof |

## Fishing Reticle / Ground Marker Status

User goal: **client-side display-only marker**, not gameplay interaction.

| Item | Result |
|---|---|
| Fishing pole location | Action Bar 1 Slot 5 |
| Input used | ControlSend key 5 to Rift HWND |
| Click/cast performed? | No |
| Result | Red/orange ground-target/fishing circle appeared |
| Persistence | Remained after key release and after a short wait |
| Concern | It may move with player/cursor/camera instead of staying pinned |

### Screenshot Evidence From Runtime Captures

| State | Path |
|---|---|
| Before key 5 | C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260424-025750-685.png |
| After key 5 | C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260424-025838-458.png |
| After wait | C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260424-025920-737.png |

## Working Hypothesis

The fishing circle is likely a **client-side 3D ground-target reticle renderer**. Useful state may include:

| Candidate State | Why It Matters |
|---|---|
| Visible/hidden flag | Required for display-only show/hide |
| Target X/Y/Z or ground-hit position | Required for waypoint placement |
| Cursor/raycast ground result | Explains cursor/camera-follow behavior |
| Ability target mode enum | Explains active target-reticle lifecycle |
| Radius/color/mode fields | Optional later customization |

## Recommended Execution Plan

### 1. Safe show/hide baseline

Use only non-gameplay inputs:

| Action | Expected |
|---|---|
| Send 5 by ControlSend | Reticle appears |
| Wait 2–5 seconds | Reticle remains visible |
| Send Esc by ControlSend | Reticle hides/cancels |
| Repeat twice | Confirms safe reproducibility |

Stop immediately if any cast/fishing/gameplay action starts.

### 2. Classify reticle behavior visually

| Test | Purpose |
|---|---|
| Stand still and wait | Check timeout/persistence |
| Move camera/mouse only | Check cursor/camera coupling |
| Small player movement | Check whether reticle is fixed to world or follows player |
| Hide/show again | Check reset behavior |

If any coordinate-based movement proof is used, first resolve the canonical proof source with:

`powershell
C:\RIFT MODDING\RiftReader\scripts\resolve-proof-coord-anchor.ps1
`

### 3. Read-only memory discovery

Capture snapshots for these states:

| State | Meaning |
|---|---|
| hidden_0 | Reticle hidden baseline |
| isible_0 | Reticle shown |
| isible_camera_moved | Camera/mouse changed |
| isible_player_moved | Player moved slightly |
| hidden_1 | Reticle hidden again |

Search for correlated candidates: visible flag, float triplet, mode enum, pointer chain near ability/reticle state.

### 4. Display-only write proof only after correlation

| Step | Rule |
|---|---|
| Save original values | Required |
| Write tiny coordinate nudge | Visual-only; no click/cast |
| Screenshot before/after | Required |
| Restore immediately | Required |
| Abort on side effect | Required |

Success means the reticle visibly moves/changes without any gameplay action.

### 5. Preserve durable reverse-engineering state

| Artifact | Destination |
|---|---|
| Valuable CE table | C:\RIFT MODDING\RiftReader\artifacts\cheat-engine\tables\ |
| Short proof note | Same artifacts folder or docs\analysis |
| Temporary runtime scripts | Keep ignored unless promoted intentionally |
| Marker docs | Add only after proof, not before |

## Stop Conditions

| Risk | Stop Condition |
|---|---|
| Accidental fishing/casting | Stop immediately |
| Reticle tied only to active cursor raycast | Treat as not directly usable as dropped pin |
| Candidate memory overwritten every frame | Trace writer/controller instead of forcing writes |
| Client crash or unstable state | Restore originals and stop |
| Coordinates stale or heuristic-only | Do not promote without validated proof |

## Best Next Milestone

**Prove whether the fishing reticle has a stable client-side visible flag and position state that can be read, then safely nudged/restored without casting.**

If this succeeds, it can become the fastest path to display-only waypoint markers without requiring full camera yaw/pitch/FOV first.

## Top 5 Recommended Next Actions

| # | Action | Why |
|---:|---|---|
| 1 | Run safe 5 → wait → Esc show/hide loop | Confirms repeatable display-only lifecycle |
| 2 | Test whether reticle follows player/camera/cursor | Determines whether it is a fixed ground marker or active targeting cursor |
| 3 | Capture hidden/visible/moved memory snapshots | Gives clean state transitions for candidate search |
| 4 | Find visible flag plus coordinate/mode candidates | Highest-value lowest-risk memory targets |
| 5 | Attempt tiny visual-only nudge and restore only after correlation | Proves whether this can support waypoint markers |
