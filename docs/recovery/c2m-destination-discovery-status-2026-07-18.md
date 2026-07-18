# C2M destination discovery status — 2026-07-18

**Status:** Session candidates found and classified. **Not promoted.**  
**Safety:** Ground clicks used only in the discovery run (`inputSent=true` once). Follow-up was **no-input**. No CE, no x64dbg, no truth/proof promotion.

## Tools

| Script | Role |
|---|---|
| `scripts/c2m_destination_discovery.py` | Automated baseline → click → diff → rank |
| `scripts/c2m_candidate_followup.py` | No-input re-read + classify + limited pointer probe |

## Artifacts

| Run | Path |
|---|---|
| Discovery (2 clicks) | `scripts/captures/c2m-destination-discovery-20260718-073756-913574/summary.json` |
| Follow-up (no input) | `scripts/captures/c2m-candidate-followup-20260718-0742*/summary.json` (see latest under `scripts/captures/c2m-candidate-followup-*`) |

## Target epoch

| Field | Value |
|---|---|
| PID / HWND | `26916` / `0x60A8C` |
| Module base | `0x7FF696620000` |
| API at follow-up | `678.32 / 850.65 / 361.61` |

## Discovery result

| Metric | Value |
|---|---|
| Verdict | `c2m-destination-session-candidates-found` |
| Clicks | 2× client ground PostMessage |
| Player moved after click1 | planar Δ ≈ **3.66 m** (C2M likely engaged) |
| Candidates after 2nd-click boost | 173 |

## Best structural finding (layout)

Top score-10 addresses are **not four independent goals**. They form a **paired min/max (or corner pair)** with fixed half-extent **40** on X/Y/Z:

| Label | Address (examples) | Value at follow-up |
|---|---|---|
| Corner/min A | `0x174041F89F0`, copy `0x174004FEFA0` | `638.322 / 810.650 / 321.611` |
| Corner/max B | `0x174041F8A00` (= A+0x10), copy `0x174004FEFB0` | `718.322 / 890.650 / 401.611` |

```text
B - A = (+80, +80, +80)
center = (A+B)/2 = (678.322, 850.650, 361.611)
apiPlayer ≈ center at follow-up (player arrived at center)
```

Contiguous layout at primary heap object:

```text
base+0x00 : vec3 A (min/corner)
base+0x0C : 0
base+0x10 : vec3 B (max/corner)
```

**Working hypothesis (candidate-only):**

| Hypothesis | Fit |
|---|---|
| Axis-aligned volume / probe / path bounds centered on move goal | Strong — half-extent 40; center ≈ player after walk |
| True single C2M destination float | Weak — destination would usually be one point, not ±40 cube |
| Camera frustum corners | Possible — less likely exact 40 world units on all axes |
| Player body coords | Rejected — planar dist ~56 m at discovery; body cluster separate |

Follow-up: values **frozen** since end of discovery (`deltaVsDiscovery=0`).  
Live re-read confirms **center − API player ≈ 0** after the walk:

| | X | Y | Z |
|---|---:|---:|---:|
| Center `(A+B)/2` | 678.322 | 850.650 | 361.611 |
| API player | 678.32 | 850.65 | 361.61 |
| Δ | ~0.002 | ~0 | ~0.001 |

Interpretation: click set a **fixed world volume** (half-extent 40); player **C2M-walked into its center**. That is stronger evidence for move-related bounds/goal volume than for a free-floating unrelated float cluster.

## Classification (follow-up)

| Class | Addresses | Follow-up score |
|---|---|---|
| `frozen-far` (primary pair + copies) | `0x174041F89F0`, `0x174004FEFA0`, `0x174041F8A00`, `0x174004FEFB0` | 4 |
| Near-player frozen (~7 m) | `0x17403FC8910` family | 0 — likely path/entity noise |

## Pointer / static root

| Probe | Result |
|---|---|
| Exact pointer to A / B in module image | **None** in bounded scan |
| Owner-minus-0x320 style | **None** |
| Conclusion | **Session heap only** so far — no restart-stable root yet |

## What this enables next

| Priority | Action | Gate |
|---|---|---|
| 1 | On next C2M click, re-read A/B and **center**; expect volume to re-center or rebuild | Optional 1 click |
| 2 | If center jumps to new click goal before player moves → strong C2M-volume proof | Stimulus approved |
| 3 | Bounded pointer scan for pointers to **object base** (`A-0` object), not only float addr | No input |
| 4 | Optional one HW watch on write to A on click | x64dbg approval |
| 5 | Promote only after restart + multi-click | Explicit promote |

## What not to do

- Do not treat A or B alone as “the click destination.”
- Do not promote heap addresses.
- Do not claim nav/C2M automation ready.
- Do not confuse this with post-patch static player root (still null).

## Run commands

```powershell
# Full discovery (sends ground clicks — requires --stimulus-approved)
python .\scripts\c2m_destination_discovery.py --execute --stimulus-approved --second-click --pid <pid> --hwnd <hwnd> --json

# No-input follow-up on last discovery summary
python .\scripts\c2m_candidate_followup.py --discovery-summary .\scripts\captures\c2m-destination-discovery-<stamp>\summary.json --json
```

## Follow-up probe (2026-07-18 later) — reclassification

`scripts/c2m_volume_click_probe.py` on `0x174041F89F0`:

| Observation | Value |
|---|---|
| Extent always | **(80,80,80)** half-extent 40 |
| center − player **before** click | ≈ **0** |
| center − player **after** click | ≈ **0** |
| First center change | ~0.55 over 152 ms while player also moved ~2.4 m |
| Verdict | `volume-changed-and-player-also-moved` |

**Revised hypothesis:** A/B is a **player-centered ±40 world volume** (bounds / interest / query box) that **tracks the player**, **not** a frozen C2M click destination.

Prior “player walked into center” was consistent with **center always being the player**.

| Status | Meaning |
|---|---|
| `0x174041F89F0` family | Useful layout find; **not** C2M goal |
| True C2M destination | **Still open** — re-score discovery rejecting player-tracking / ±40 corners |

Discovery scorer updated to penalize:

- `tracks-player-motion`
- `player-centered-pm40-volume-corner`

## Fixed-goal scan (negative)

`scripts/c2m_fixed_goal_scan.py` (2 clicks, rejects player-track and ±40 corners):

| Field | Value |
|---|---|
| Artifact | `scripts/captures/c2m-fixed-goal-scan-20260718-075223/summary.json` |
| Status | `blocked` |
| Verdict | `no-fixed-goal-candidates-after-player-track-rejection` |
| High-score fixed goals | **0** |
| Player moved | planar Δ ≈ 4.6 m (clicks still affect movement) |

**Conclusion so far:** With current float-vec3 heap scanning, we have **not** found a session address that behaves like a **fixed C2M world destination** (set on click, hold while walking, not player-centered).

Likely causes (ranked):

1. Destination not stored as contiguous `float x,y,z` in scanned RW regions  
2. Destination lives in a short-lived buffer / different encoding  
3. PostMessage click path is not the same as a true ground C2M order (partial movement only)  
4. Need access-provenance on click (x64dbg, gated)

## Practical automation implication

| Approach | Blocked by missing dest field? |
|---|---|
| **Issue move via ground click + W2S** | No — still viable; need camera/W2S |
| **Read engine destination for arrival** | Yes — not found yet |
| **Arrival via RRAPICOORD distance to planned goal** | No — use planned goal, not engine field |

## Chosen optimal path (executed)

**Lane:** C2M runner without engine dest / without static root.

| Item | Detail |
|---|---|
| Script | `scripts/c2m_run_to_goal.py` |
| Method | PostMessage ground click + RRAPICOORD distance to planned goal |
| Live proof (v1) | `scripts/captures/c2m-run-to-goal-20260718-081141/summary.json` |
| Result (v1) | `progressed-but-not-arrived` — dist **12.0 → 7.27** m |
| Live proof (v2) | `scripts/captures/c2m-run-to-goal-20260718-090939/summary.json` |
| Result (v2) | **`arrived-within-radius`** — goal +8m Z, final dist **1.62** m (radius 3), 11 steps |

Hardening applied in `c2m_run_to_goal.py`:

- Fast RRAPICOORD in-process scan + cache (fallback to ps1)
- Poll-after-click settle loop
- Distance-aware click depth + bearing bias

### Multi-waypoint + steering (same session)

| Item | Detail |
|---|---|
| Code | `--waypoint-offsets "dx,dz;..."`, `--waypoints-json`, `--click-mode post\|cursor`, invert-on-wrong-way |
| Multi live attempt | `c2m-run-to-goal-20260718-104540` — **failed**: player walked **away** from +Z goal (camera-relative clicks) |
| Later attempts | **No displacement** (moved=0) — clicks not driving C2M (mode off / focus / UI) |
| Pose bug fixed | Do not reuse stale RRAPICOORD capture files during step polls |

### Input backend correction (required)

| Wrong (earlier C2M runner) | Correct (repo policy) |
|---|---|
| `PostMessage` mouse clicks | **Do not use for RIFT mouse** |
| Ad-hoc `mouse_event` without focus gate | Incomplete |
| **Correct** | **C# `RiftReader.SendInput` absolute mouse after foreground focus** |

Implemented:

| Change | Detail |
|---|---|
| `tools/RiftReader.SendInput` | `--client-x` / `--client-y` left-click via SendInput; fails closed if not foreground |
| `scripts/c2m_run_to_goal.py` | Uses only SendInput mouse path; removed post/cursor as valid modes |
| Smoke | `send-rift-key-csharp.ps1 --client-x 400 --client-y 400 ...` → `status=sent`, `TargetProcessForeground=true` |

**Operator check before next live run:** C2M on, not in chat, allow focus steal / RIFT can become foreground.

```powershell
python scripts\c2m_run_to_goal.py --execute --stimulus-approved --offset-z 6 --arrival-radius 3 --max-steps 10 --focus-delay-ms 600 --json
```

## Bottom line

| Solved | Still open |
|---|---|
| Automated click→diff tooling | **True C2M destination field** |
| Player-centered ±40 AABB (session) | Static root |
| Filters that reject false “goals” | Debug-level provenance on click |
| | Camera/W2S for click automation without dest memory |

**Last updated:** 2026-07-18 (fixed-goal scan negative)
