# Coord freshness workflow handoff - API-now vs memory-now

Created: 2026-05-08 21:11:41 -0400
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
HEAD before this handoff commit: `0a7a614`

## TL;DR

The coordinate-freshness workflow has been corrected and strongly documented.
Do **not** call artifact coordinates current just because PID/HWND still match.
PID/HWND/process-start match is targeting preflight only.

The required stale/non-stale test is now:

```text
fresh API/runtime coordinate now
vs
fresh memory coordinate now
```

Current coordinate truth requires API-now vs memory-now comparison, per-axis
delta within tolerance, and a recorded verdict. If API is stale/missing, memory
readback fails, or deltas exceed tolerance, block movement and treat stored
coordinates as timestamped snapshots/reacquisition seeds only.

## Why this handoff exists

A prior answer over-weighted current PID/HWND match and repeated a timestamped
coordinate artifact as if it might answer current-now position. That was the
wrong framing. PID/HWND can confirm the anchor is targetable, but it does not
prove the coordinate value is fresh. The simplest correct stale check is a fresh
API coordinate compared to an immediate memory read.

## Files changed in this slice

| File | Purpose |
|---|---|
| `C:\RIFT MODDING\RiftReader\agents.md` | Repo-level live movement invariant: API-now vs memory-now is mandatory; PID/HWND is preflight only. |
| `C:\RIFT MODDING\RiftReader\.codex\skills\rift-window-control\SKILL.md` | Skill reminder to avoid cached/current coordinate overclaims. |
| `C:\RIFT MODDING\RiftReader\docs\assistant-operating-policy.md` | Expanded policy table with freshness, failure, and evidence requirements. |
| `C:\RIFT MODDING\RiftReader\docs\recovery\README.md` | Added top-level Coordinate freshness rule. |
| `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md` | Renamed current coordinate wording to latest recorded snapshot and added freshness rule row. |
| `C:\RIFT MODDING\RiftReader\docs\live-testing-python-orchestrator-plan.md` | Added hard invariant and runner workflow for API-now vs memory-now. |
| `C:\RIFT MODDING\RiftReader\docs\candidate-trajectory-promotion-gate.md` | Added promotion/freshness requirements for live API vs memory comparison. |
| `C:\RIFT MODDING\RiftReader\scripts\test_coord_freshness_documentation.py` | Smoke test proving the policy surfaces contain the required rule. |
| This handoff | Resume checkpoint for the correction. |

## New hard rule

| Concept | Required handling |
|---|---|
| PID/HWND/process-start | Targeting preflight only; never coordinate freshness proof. |
| Artifact coordinate | Timestamped snapshot unless freshly re-read/validated. |
| API side | Must be freshness-proven live runtime/API telemetry. |
| Memory side | Must be immediate readback from the current candidate/anchor. |
| Pass condition | API fresh, memory read succeeds, and per-axis deltas are within tolerance. |
| Fail condition | API stale/missing, memory read fails, or delta exceeds tolerance. |
| Failure action | Block movement and keep old artifacts only as reacquisition seeds. |

## Accepted / rejected freshness sources

| Source | Use as API-now side? | Notes |
|---|---:|---|
| ChromaLink `/api/v1/riftreader/world-state` with freshness/contract proof | Yes | Preferred when bridge is available and fresh. |
| Explicitly live ReaderBridge/in-game runtime telemetry | Yes | Must be live runtime state, not SavedVariables. |
| Other current live telemetry stream | Yes | Must include freshness proof. |
| `ReaderBridgeExport.lua` / SavedVariables | No | Post-save snapshots only. |
| `C:\Users\mrkoo\AppData\Roaming\Rift\rift.cfg` | No | Config snapshot, not live coordinate truth. |
| Screenshots | No as numeric API coord | Visual evidence only unless a separate OCR/overlay truth workflow proves freshness. |
| Old `run-summary.json` coordinate | No | Historical snapshot. |

## Required result fields for future `coord-now` / ProofOnly freshness output

```json
{
  "verdict": "current|stale|mismatch|blocked-api-stale|blocked-memory-read-failed",
  "target": { "processName": "rift_x64", "processId": 0, "hwnd": "0x0", "processStartTime": "..." },
  "api": { "source": "...", "fresh": true, "timestampUtc": "...", "x": 0, "y": 0, "z": 0 },
  "memory": { "candidateId": "...", "address": "0x...", "timestampUtc": "...", "x": 0, "y": 0, "z": 0 },
  "delta": { "x": 0, "y": 0, "z": 0, "maxAbs": 0 },
  "tolerance": { "maxAbsDelta": 0.05 }
}
```

## Validation already run

| Command | Result |
|---|---|
| `python -m py_compile scripts/test_coord_freshness_documentation.py` | Passed |
| `python scripts/test_coord_freshness_documentation.py` | Passed, `4/4` |
| `python scripts/test_current_proof_pointer.py` | Passed, `1/1` |
| `python scripts/test_live_test_orchestrator.py` | Passed, `75/75` |
| `git diff --check` | Passed; only LF/CRLF warnings from the dirty worktree |

## Current worktree warning

There were unrelated pre-existing dirty files before this slice. Stage/commit
only the freshness-policy files and this handoff unless the user explicitly asks
for a broader commit.

Current `git status --short` at handoff creation time:

```text
M .codex/skills/rift-window-control/SKILL.md
 M agents.md
 M configs/live-test-profiles.json
 M docs/assistant-operating-policy.md
 M docs/candidate-trajectory-promotion-gate.md
 M docs/live-testing-python-orchestrator-plan.md
 M docs/recovery/README.md
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
?? scripts/test_coord_freshness_documentation.py
```

## Resume prompt

```text
Resume from newest handoff. Continue the coord-freshness correction lane. The hard rule is API-now vs memory-now; PID/HWND/process-start is targeting preflight only. Do not present artifact coordinates as current-now without a fresh API/runtime coordinate compared to immediate memory readback and per-axis deltas within tolerance. Before movement, run or implement a coord-now/ProofOnly freshness check that emits API coord, memory coord, deltas, tolerance, and verdict. Never use SavedVariables, rift.cfg, screenshots, or old run summaries as the API freshness side.
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Commit and push this handoff plus policy docs | Preserves the correction. |
| 2 | Implement a real `coord-now` helper next | Turns policy into one-command verification. |
| 3 | Make `ProofOnly` emit API-vs-memory freshness verdict | Prevents repeat ambiguity. |
| 4 | Include process start time in target identity | Stronger than PID/HWND alone. |
| 5 | Default tolerance to `maxAbsDelta <= 0.05` | Matches existing bootstrap tolerance. |
| 6 | Fail closed when API freshness cannot be proven | Avoids stale false positives. |
| 7 | Keep artifact coords labeled as snapshots in all reports | Prevents overclaiming. |
| 8 | Update future handoffs with the freshness verdict field | Keeps resumes safe. |
| 9 | Avoid broad memory rediscovery unless API-vs-memory fails | Saves time. |
| 10 | Before any movement, run fresh API-now vs memory-now | Correct safety gate. |
