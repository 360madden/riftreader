# Player actor-yaw candidate ledger

This note defines the offline evidence contract for the player actor-yaw
candidate ledger used by:

- `C:\RIFT MODDING\RiftReader\scripts\find-player-orientation-candidate.ps1`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Models\OrientationCandidateLedgerLoader.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Models\PlayerOrientationCandidateFinder.cs`

The ledger is a **yaw-discovery input only**. It can downrank candidate actor-yaw
sources before behavior validation, but it must not promote player actor-facing
truth by itself.

## Scope and safety boundary

| Rule | Meaning |
|---|---|
| No CE | Do not use Cheat Engine, CE Lua, CE debugger attach, breakpoints, watchpoints, or `cheatengine-exec.ps1` for this workflow. |
| No live movement from the ledger | Ledger evidence can affect search ranking only; it is not movement permission. |
| No actor-facing promotion from the ledger | Actor-facing still requires behavior-backed proof plus `scripts\test-actor-facing-proof-suite.ps1`. |
| Session-bound addresses | Source addresses remain valid only for the live process/session they were discovered in unless re-proven. |
| SavedVariables are not live IPC | Do not treat stale addon `SavedVariables` contents as same-time yaw or coordinate truth. |

## Ledger file format

The ledger is newline-delimited JSON. Each non-empty line is parsed as one
orientation candidate evidence entry.

Required for candidate matching:

| Field | Meaning |
|---|---|
| `sourceAddress` | Candidate source/base address. Hex strings such as `0xABCDEF00` and integer strings are normalized. |
| `basisForwardOffset` | Forward-basis offset for that candidate. Missing or invalid offsets normalize to `0x0`. |

Important evidence fields:

| Field | Meaning |
|---|---|
| `generatedAtUtc` | Evidence timestamp used to identify the latest evidence for a candidate. |
| `candidateResponsive` | Whether the candidate reacted to the stimulus in that evidence row. |
| `candidateRejectedReason` | Rejection reason such as `stable_but_nonresponsive`, `idle_drift`, or `inter_preflight_idle_drift`. |
| `yawDeltaDegrees` | Observed yaw delta from the evidence run, when available. |
| `coordDriftMagnitude` | Coordinate drift during the evidence run, when available. |

## Candidate key

Candidate identity is:

```text
CandidateKey = normalized sourceAddress|normalized basisForwardOffset
```

Examples:

| Input | CandidateKey |
|---|---|
| `sourceAddress=0xabcdef00`, `basisForwardOffset=212` | `0xABCDEF00|0xD4` |
| `sourceAddress=2748`, missing `basisForwardOffset` | `0xABC|0x0` |

The offset is part of the key on purpose. The same source object may expose
multiple basis offsets, and evidence for `0xABCDEF00|0xD4` must not penalize
`0xABCDEF00|0x94`.

## Penalty semantics

`OrientationCandidateLedgerLoader` builds one evidence summary per
`CandidateKey`.

| Latest evidence | Score effect |
|---|---|
| `stable_but_nonresponsive` and not responsive | Penalize. Base penalty is `180`; each additional stable/nonresponsive row adds `60`; max penalty is `400`. |
| `idle_drift` | Penalize using the same base penalty path. |
| `inter_preflight_idle_drift` | Penalize using the same base penalty path. |
| Later responsive evidence | Clears the stale stable/nonresponsive penalty when the latest row is responsive and has no penalized rejection reason. |
| Missing ledger file | Non-fatal; no candidates are penalized. |
| Malformed NDJSON | Produces `LoadError`; no evidence index is used. |

The candidate finder applies the penalty to pointer-hop candidates only:

```text
Score = max(0, RawScore - LedgerPenalty)
```

The score must never become negative.

## JSON output contract

When `--find-player-orientation-candidate --json` is used, pointer-hop
candidates affected by ledger evidence expose:

| Field | Meaning |
|---|---|
| `RawScore` | Candidate score before ledger penalty. |
| `Score` | Candidate score after ledger penalty. |
| `LedgerPenalty` | Applied penalty. Zero means no penalty. |
| `LedgerRejectionReason` | Latest ledger rejection reason, when matched. |
| `LedgerStableNonresponsiveCount` | Count of stable/nonresponsive evidence rows for the candidate. |
| `LedgerResponsiveCount` | Count of responsive evidence rows for the candidate. |
| `LedgerLatestGeneratedAtUtc` | Timestamp of the latest evidence row used for the candidate summary. |

Search notes should include the ledger path, total ledger entries, unique
candidate count, and `penalizedPointerHopCandidates`.

## Recommended command pattern

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File `
  "C:\RIFT MODDING\RiftReader\scripts\find-player-orientation-candidate.ps1" `
  -ProcessName rift_x64 `
  -OrientationCandidateLedgerFile "C:\RIFT MODDING\RiftReader\scripts\captures\orientation-candidate-ledger.ndjson" `
  -MaxHits 8 `
  -Json
```

For live sessions, prefer exact process selection when known:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File `
  "C:\RIFT MODDING\RiftReader\scripts\find-player-orientation-candidate.ps1" `
  -ProcessId 33912 `
  -OrientationCandidateLedgerFile "C:\RIFT MODDING\RiftReader\scripts\captures\orientation-candidate-ledger.ndjson" `
  -MaxHits 8 `
  -Json
```

## Promotion boundary

The ledger can say “this yaw candidate should rank lower.” It cannot say “this
actor-facing source is current truth.”

Before downstream actor-facing/navigation use:

1. Re-bind the exact live PID/HWND.
2. Re-run the yaw candidate search against current-session data.
3. Verify candidate-search `PlayerCoord` came from the proof-coordinate anchor
   when that anchor is available; JSON notes should identify
   `telemetry-proof-coord-anchor-current-memory` rather than stale
   ReaderBridge/SavedVariables coordinates.
4. Run `scripts\test-actor-yaw-candidates.ps1` and require behavior-responsive
   yaw evidence. If more than one truth-like yaw candidate survives, treat
   readiness as `yaw-ambiguous-needs-disambiguation` and do not promote the
   best row by score alone.
5. Keep `FacingPromotionAttempted=false` in yaw-candidate output unless the
   separate actor-facing promotion path actually ran.
6. Run `scripts\test-actor-facing-proof-suite.ps1`.
7. Record the validated result in `docs\recovery\current-truth.md`.

## Durable readiness checkpoint

After a candidate-search or yaw-validation milestone, write a RiftReader-owned
readiness checkpoint and latest pointer:

```powershell
python "C:\RIFT MODDING\RiftReader\scripts\summarize_actor_yaw_discovery.py" `
  --write-summary `
  --write-markdown `
  --update-latest-pointer `
  --require-fresh
```

Convenience launcher:

```cmd
C:\RIFT MODDING\RiftReader\scripts\summarize-actor-yaw-discovery.cmd --write-summary --write-markdown --update-latest-pointer --require-fresh
```

This writes under `scripts\captures`, refuses output paths inside
`C:\RIFT MODDING\Riftscan`, and exits with code `2` when the input artifacts are
stale. The latest pointer is:

```text
C:\RIFT MODDING\RiftReader\scripts\captures\latest-actor-yaw-discovery-readiness.json
```

## Regression coverage

| Test | Contract protected |
|---|---|
| `OrientationCandidateLedgerLoaderTests` | Key normalization, missing/malformed ledger handling, penalty semantics, responsive-later clearing. |
| `PlayerOrientationCandidateFinderLedgerTests` | Actual pointer-hop candidate score gating and metadata preservation. |
| `PlayerOrientationCandidateSearchJsonOutputTests` | Public JSON output exposes ledger score/evidence fields and notes. |
| `ReaderOptionsParserTests` | `--orientation-candidate-ledger-file` wiring and misuse rejection. |
| `scripts\test-actor-yaw-candidates-reversible-output.ps1` | Yaw-candidate output remains yaw-first and does not claim actor-facing promotion. |
| `scripts\test_summarize_actor_yaw_discovery.py` | Readiness status/freshness gates, durable summary/latest-pointer writes, and RiftScan output-path refusal. |
