# RiftScan -> RiftReader coordinate candidate workflow

## Verdict

Use **RiftScan as the coordinate candidate generator** and **RiftReader as the
current-process sampler / live validator**. RiftScan has stronger offline
candidate ranking, recovery, corroboration, and promotion review. RiftReader
should not re-run broad heuristic candidate discovery when a RiftScan candidate
artifact exists.

## Current safety boundary

- **No Cheat Engine** for live RiftReader work unless the user explicitly
  re-authorizes CE in the current conversation.
- When the active boundary is **do not modify RiftScan**, treat
  `C:\RIFT MODDING\Riftscan` as read-only: inspect existing reports/sessions
  only, and write new coordination summaries under RiftReader.
- RiftScan candidates are **candidate evidence only**.
- A RiftScan candidate watchset is **not** a RiftReader movement proof anchor.
- Active movement remains blocked until RiftReader has a current-process
  canonical movement source that satisfies the movement/polling invariant.

## Ownership split

| Layer | Owner | Purpose |
|---|---|---|
| Candidate generation | RiftScan | Capture, compare, score, recover, corroborate, and rank candidate vec3/scalar lanes. |
| Candidate ledger / evidence | RiftScan | Preserve low-score, rejected, recovered, corroborated, and blocked candidates as replayable evidence. |
| Current-process read sampling | RiftReader | Read selected candidate windows from the current RIFT PID with `--record-session`. |
| Movement/navigation proof | RiftReader | Only after a canonical current-process movement source exists. |
| Addon/SavedVariables data | Either, but freshness-labeled | Corroboration only unless freshness is proven; SavedVariables are post-save snapshots. |

## Export candidates in RiftScan

Preferred coordinate candidate artifacts, strongest first:

1. `riftscan.vec3_truth_promotion.v1` JSON from `riftscan compare vec3-promotion`.
2. `riftscan.vec3_truth_recovery.v1` JSON from `riftscan compare vec3-truth`.
3. `riftscan.vec3_truth_candidate.v1` JSONL from `riftscan compare sessions --vec3-truth-out`.
4. Raw `riftscan.vec3_candidate.v1` JSONL from a single analyzed session.

Example RiftScan lane:

```powershell
cd 'C:\RIFT MODDING\Riftscan'

riftscan compare sessions `
  sessions/<passive_id> `
  sessions/<move_id> `
  --top 100 `
  --out reports/generated/<run>-comparison.json `
  --report-md reports/generated/<run>-comparison.md `
  --truth-readiness reports/generated/<run>-truth-readiness.json `
  --vec3-truth-out reports/generated/<run>-vec3-truth-candidates.jsonl
```

## Import RiftScan candidates into RiftReader

Use the RiftReader importer to convert a RiftScan candidate artifact into a
RiftReader `--record-session` watchset:

```powershell
cd 'C:\RIFT MODDING\RiftReader'

.\scripts\import-riftscan-coordinate-candidates.ps1 `
  -CandidateFile 'C:\RIFT MODDING\Riftscan\reports\generated\<run>-vec3-truth-candidates.jsonl' `
  -ProcessId <current_rift_pid> `
  -TargetWindowHandle <current_rift_hwnd> `
  -TopCount 16 `
  -ContextBytes 64 `
  -OutputFile .\scripts\captures\riftscan-coordinate-candidate-watchset.json
```

The importer emits:

- `Mode = riftscan-coordinate-candidate-watchset`
- `NoCheatEngine = true`
- `MovementAllowed = false`
- `CanonicalCoordSource = none-candidate-watchset-only`

That is intentional. The artifact exists so RiftReader can sample the candidate
windows without pretending they are movement-grade truth.

## Sample current-process candidate windows with RiftReader

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- `
  --pid <current_rift_pid> `
  --record-session `
  --session-watchset-file .\scripts\captures\riftscan-coordinate-candidate-watchset.json `
  --session-output-directory .\scripts\sessions\riftscan-candidate-check-<timestamp> `
  --session-sample-count 20 `
  --session-interval-ms 250 `
  --session-label riftscan_candidate_no_input `
  --json
```

This is read-only sampling. It does **not** send input and does **not** satisfy
movement proof.

## One-command no-CE readback wrapper

For repeatable restarted-PID checks, use the RiftReader wrapper:

```powershell
cd 'C:\RIFT MODDING\RiftReader'

.\scripts\invoke-riftscan-coordinate-readback.ps1 `
  -ProcessId <current_rift_pid> `
  -TargetWindowHandle <current_rift_hwnd>
```

The wrapper performs this safe sequence:

1. Rechecks the RiftReader proof anchor with `resolve-proof-coord-anchor.ps1`
   using `-SkipRefresh`. This is a gate/status check, not movement unlock.
2. Runs a no-input RiftScan passive capture for the current PID.
3. Verifies and analyzes the RiftScan session.
4. Imports fresh RiftScan `vec3_candidates.jsonl` into a RiftReader candidate
   watchset.
5. Runs RiftReader `--record-session` readback against those candidate windows.
6. Decodes the candidate vec3 from the readback bytes and compares it to the
   RiftScan `value_preview` when present.
7. Optionally compares decoded candidates to a supplied external reference
   coordinate.
8. Writes a summary JSON under `scripts\captures`.

The wrapper always reports:

- `NoCheatEngine = true`
- `MovementSent = false`
- `MovementAllowed = false`
- `CanonicalCoordSource = none-candidate-watchset-only`

If you already have a RiftScan candidate artifact, pass it directly:

```powershell
.\scripts\invoke-riftscan-coordinate-readback.ps1 `
  -ProcessId <current_rift_pid> `
  -TargetWindowHandle <current_rift_hwnd> `
  -CandidateFile 'C:\RIFT MODDING\Riftscan\sessions\<session>\vec3_candidates.jsonl'
```

Important: running `invoke-riftscan-coordinate-readback.ps1` **without**
`-CandidateFile` can create a fresh RiftScan passive capture/session under the
RiftScan repo. Do not use that mode while RiftScan is read-only. Prefer an
existing candidate or match file from the current-proof pointer or from
`reports\generated`.

## Read-only coordination checkpoint

Use the Python coordination checkpoint before expanding discovery scope, after a
handoff/commit/push milestone, or whenever the current target PID/HWND may have
drifted:

```powershell
python .\scripts\riftscan_coordination.py `
  --pid <current_rift_pid> `
  --hwnd <current_rift_hwnd> `
  --process-name rift_x64 `
  --write-summary
```

This tool:

1. Reads `docs\recovery\current-proof-anchor-readback.json`.
2. Reads existing RiftScan `reports\generated\*-addon-coordinate-matches.json`
   files for the requested PID.
3. Selects the safest existing candidate source for RiftReader to consume.
4. Emits command arrays that always include `-CandidateFile` when using
   RiftScan-derived candidates.
5. Writes summaries only under RiftReader and refuses to write inside the
   RiftScan repo.

The checkpoint is intentionally read-only for RiftScan: it does not run
`riftscan capture`, does not create sessions/reports in RiftScan, sends no
input, uses no Cheat Engine path, and does not promote candidate evidence into
movement truth.

## RiftReader-owned provider feedback packet

When RiftReader needs to summarize what it learned for later RiftScan/provider
review, write the packet under RiftReader, not inside the RiftScan repo:

```powershell
python .\scripts\riftscan_feedback.py `
  --pid <current_rift_pid> `
  --hwnd <current_rift_hwnd> `
  --process-name rift_x64 `
  --write-summary
```

This packet wraps the same read-only coordination plan and adds RiftReader
artifact pointers such as current truth, the current proof pointer, the newest
handoff, and latest coordination output. It records
`feedbackWritesToRiftScan=false`, `writeAllowed=false`, `movementSent=false`,
and `noCheatEngine=true`, then refuses any output path under
`C:\RIFT MODDING\Riftscan`.

Use the packet for offline review/report generation/provider-feedback review.
Do **not** treat it as permission for movement, live capture, process attach,
memory read, offset validation, `/reloadui`, RiftReader commands, or any
RiftScan write.

## Major milestone strategy checkpoint

After every handoff, commit, push, target change, or broad discovery milestone,
run the combined strategy checkpoint:

```powershell
python .\scripts\riftscan_milestone_review.py `
  --pid <current_rift_pid> `
  --hwnd <current_rift_hwnd> `
  --process-name rift_x64 `
  --write-summary `
  --write-markdown `
  --update-latest-pointer
```

This wraps the coordination plan and feedback packet into a short review with
blocker/warning checks, a strategy decision, a selected candidate source, and
next command arrays. It always writes under RiftReader, refuses output under
RiftScan, sends no input, uses no CE path, and never grants movement permission
by itself. If it returns `blocked`, do not expand discovery until the blocker is
resolved. If it returns `ready-for-read-only-proof`, use explicit
`-CandidateFile` read-only proof first and still run fresh `ProofOnly` before
any movement.

When visual/capture artifacts are involved, attach the coordinate proof route
pointer so the checkpoint can resolve the latest full route before evaluating
sidecar evidence:

```powershell
python .\scripts\riftscan_milestone_review.py `
  --pid <current_rift_pid> `
  --hwnd <current_rift_hwnd> `
  --process-name rift_x64 `
  --proof-route-summary scripts\captures\latest-coordinate-proof-route.json `
  --write-summary `
  --write-markdown
```

The route pointer is intentionally fail-closed:

- visual capture, crops, raw BGRA, and diffs remain sidecar evidence only;
- `candidate-only-stale-against-api-now` and `reacquisition-no-current-hits`
  block proof readiness;
- read-only proof can proceed only when the route reaches an API-memory/current
  candidate match; and
- movement still requires the normal proof gate plus explicit movement approval.

For repeatable no-input scan attempts, use the Python scan-profile runner. It
wraps `scan_current_pid_coordinate_family.py` using argument arrays and records
structured JSON/Markdown summaries:

```powershell
python .\scripts\coordinate_scan_profiles.py `
  --pid <current_rift_pid> `
  --hwnd <current_rift_hwnd> `
  --process-name rift_x64 `
  --reference-file scripts\captures\<fresh-reference>.json `
  --profile wide `
  --profile historical-neighborhood `
  --json
```

If a manual displaced pose has not been captured, use
`--require-displaced-pose` to fail closed with
`manual-displaced-reference-required` rather than pretending a still pose proves
movement-sensitive coordinate truth.

To audit whether older candidate files still match API-now without reading
target memory, use the offline comparison helper:

```powershell
python .\scripts\coordinate_candidate_compare.py `
  --api-reference scripts\captures\<fresh-reference>.json `
  --candidate-file scripts\captures\<candidate-file>.json `
  --discover `
  --json
```

This report may identify a current API match, but it is still offline evidence:
movement remains blocked until same-target readback/proof gates pass.

## Aggregate validation runner

Before committing a coordination/discovery milestone, run the Python aggregate
validation runner instead of hand-copying the long validation batch:

```powershell
python .\scripts\validate_riftscan_coordination.py `
  --pid <current_rift_pid> `
  --hwnd <current_rift_hwnd> `
  --process-name rift_x64 `
  --write-summary `
  --write-markdown `
  --update-latest-pointer
```

The runner uses Python `subprocess.run([...])` argument lists, sends no input,
uses no CE path, writes nothing to RiftScan, runs the RiftScan/RiftReader
coordination regressions, smoke-checks the milestone review status, and verifies
`git -C C:\RIFT MODDING\Riftscan status --short --branch` has no provider
working-tree changes. With `--write-summary --write-markdown --update-latest-pointer`, it writes
durable validation evidence under RiftReader `scripts\captures` and refreshes
`scripts\captures\latest-riftscan-validation.json` for handoff/resume lookup. Use
`--dry-run --compact-json` when you only need to audit the exact commands.

If you have a trusted same-time external reference coordinate, for example from
an overlay/OCR/manual note captured at the same moment, provide it for candidate
scoring:

```powershell
.\scripts\invoke-riftscan-coordinate-readback.ps1 `
  -ProcessId <current_rift_pid> `
  -TargetWindowHandle <current_rift_hwnd> `
  -CandidateFile 'C:\RIFT MODDING\Riftscan\sessions\<session>\vec3_candidates.jsonl' `
  -ReferenceX <x> `
  -ReferenceY <y> `
  -ReferenceZ <z> `
  -ReferenceTolerance 0.25 `
  -ReferenceSource 'overlay-ocr-or-manual-same-time'
```

Preferred repeatable form is a reference JSON file:

```json
{
  "source": "overlay-ocr-or-manual-same-time",
  "captured_at_utc": "2026-05-06T09:30:00.0000000Z",
  "tolerance": 0.25,
  "coordinate": {
    "x": 123.45,
    "y": 67.89,
    "z": 10.11
  }
}
```

Then pass it to the wrapper:

```powershell
.\scripts\invoke-riftscan-coordinate-readback.ps1 `
  -ProcessId <current_rift_pid> `
  -TargetWindowHandle <current_rift_hwnd> `
  -CandidateFile 'C:\RIFT MODDING\Riftscan\sessions\<session>\vec3_candidates.jsonl' `
  -ReferenceFile .\scripts\captures\same-time-reference-coordinate.json `
  -ReferenceMaxAgeSeconds 60 `
  -TopReferenceMatches 5
```

This adds `ReferenceCoordinate`, `ReferenceMatchCount`, and per-candidate
`ReferenceMaxAbsDelta` / `ReferenceMatchesReadback` fields. It also emits
`BestReferenceMatches`, a compact sorted top-N list ordered by smallest
reference delta first. A reference match is still **candidate scoring only**; it
does not satisfy the movement proof-anchor gate by itself.

When `RiftReaderApiProbe` is loaded, generate the same reference-file format
directly from the live `RRAPICOORD1` marker instead of hand-writing x/y/z:

```powershell
.\scripts\capture-rift-api-reference-coordinate.ps1 `
  -ProcessId <current_rift_pid> `
  -TargetWindowHandle <current_rift_hwnd> `
  -OutputFile .\scripts\captures\same-time-reference-coordinate.json
```

The helper scans process memory read-only for `RRAPICOORD1`. The preferred
reference is the newest usable marker with `status=pass`, `source=rift-api`,
and `savedVariablesUse=none`. If the current client/addon layout stores the
probe fields and player `x/y/z` in companion live unit-payload records instead
of one contiguous marker string, the helper may accept a
`rift-api-unit-payload-companion` reference, but only when the same scan also
contains `RRAPICOORD1`, `source=rift-api`, and
`view=Inspect.Unit.Detail(player)` context. This fallback is still a read-only
live process-memory scan, not a SavedVariables file path. The helper writes a
`captured_at_utc` UTC `Z` timestamp, sends no input, uses no Cheat Engine path,
and still produces only reference evidence for scoring or multi-pose
promotion.

If a narrow scan context sees the live `RRAPICOORD1` probe but not the companion
unit-detail payload, rerun the reference helper with the current live-test
default wider read-only context before falling back to manual inspection. A
`4096`-byte context has been observed to miss the full usable marker/payload in
the May 8, 2026 client session; prefer `16384` for proof-gated live-test runs.

```powershell
.\scripts\capture-rift-api-reference-coordinate.ps1 `
  -ProcessId <current_rift_pid> `
  -TargetWindowHandle <current_rift_hwnd> `
  -ScanContextBytes 16384 `
  -MaxHits 512 `
  -OutputFile .\scripts\captures\same-time-reference-coordinate.json
```

`SourcePreviewMatchesReadback` is an exact drift check against the historical
candidate artifact's stored `value_preview`/best memory values. When a candidate
file comes from an older passive pose, this can be `false` even while the same
current-process address is strongly validated by a same-time
`ReferenceMatchesReadback=true` API reference. Prefer the same-time reference
fields for current-pose evidence; do not treat a historical source-preview
mismatch as a movement unlock or blocker by itself.

The wrapper also has an offline decode-only mode for regression testing or
post-processing an existing readback:

```powershell
.\scripts\invoke-riftscan-coordinate-readback.ps1 `
  -DecodeOnlyWatchsetFile .\scripts\captures\riftscan-coordinate-candidate-watchset.json `
  -DecodeOnlySamplesFile .\scripts\sessions\<readback>\samples.ndjson `
  -DecodeOnlyOutputFile .\scripts\captures\riftscan-readback-decode-summary.json `
  -ReferenceX <x> `
  -ReferenceY <y> `
  -ReferenceZ <z> `
  -Json
```

Offline regression:

```powershell
.\scripts\test-invoke-riftscan-coordinate-readback-decode.ps1
```

## Promote multi-pose no-CE reference proof

Reference matches from one still pose are candidate scoring only. To create a
movement-grade proof anchor without Cheat Engine, capture at least two
same-PID/same-candidate readback summaries at distinct manually moved poses,
each with a fresh same-time reference coordinate. Then promote the candidate:

1. Capture the current still pose:

   ```powershell
   .\scripts\capture-riftscan-proof-pose.ps1 `
     -ProcessId <current_rift_pid> `
     -TargetWindowHandle <current_rift_hwnd> `
     -PoseLabel pose-current `
     -ReferenceMaxAgeSeconds 180 `
     -Json
   ```

2. Manually move the character at least `1m` but keep the same RIFT PID/HWND,
   then capture the moved pose:

   ```powershell
   .\scripts\capture-riftscan-proof-pose.ps1 `
     -ProcessId <current_rift_pid> `
     -TargetWindowHandle <current_rift_hwnd> `
     -PoseLabel pose-moved `
     -ReferenceMaxAgeSeconds 180 `
     -Json
   ```

3. Promote the same candidate from the two readback wrapper summaries:

```powershell
.\scripts\promote-riftscan-reference-match-to-proof-anchor.ps1 `
  -ReadbackSummaryFile `
    .\scripts\captures\riftscan-riftreader-currentpid-<pid>-readback-wrapper-summary-pose-a.json, `
    .\scripts\captures\riftscan-riftreader-currentpid-<pid>-readback-wrapper-summary-pose-b.json `
  -CandidateId <candidate_id> `
  -ProcessId <current_rift_pid> `
  -TargetWindowHandle <current_rift_hwnd> `
  -OutputFile .\scripts\captures\telemetry-proof-coord-anchor.json `
  -MinReferenceDisplacement 1.0 `
  -MaxDeltaError 0.25 `
  -MaxEvidenceAgeSeconds 120 `
  -Json
```

4. Re-run the hard movement preflight below before any automated movement.

The promotion script is fail-closed. It requires current PID match,
`NoCheatEngine=true`, `MovementSent=false`, same candidate address across poses,
stable decoded samples, reference matches, enough reference displacement, and
candidate deltas that track reference deltas within tolerance.

Successful promotion emits:

- `CanonicalCoordSourceKind = riftscan-reference-validated-candidate`
- `ProofMethod = no-ce-riftscan-reference-multisample`
- `ProofValidationStatus = validated`
- `ProofProcessMatchesProcess = true`
- normalized coord offsets `0/4/8`

Offline regression:

```powershell
.\scripts\test-promote-riftscan-reference-match-to-proof-anchor.ps1
```

## Movement preflight guard

Before any future movement attempt, run the hard proof-anchor gate:

```powershell
.\scripts\assert-current-proof-coord-anchor.ps1 `
  -ProcessId <current_rift_pid> `
  -TargetWindowHandle <current_rift_hwnd> `
  -Json
```

This preflight is read-only, uses no Cheat Engine path, and sends no movement.
It returns `MovementAllowed=true` only when the current PID/HWND has a fresh,
validated, normalized coord-trace proof anchor or a validated no-CE
multi-pose RiftScan/reference proof anchor. RiftScan candidate watchsets and
single-pose passive readbacks intentionally do **not** satisfy this gate.

`scripts\navigation\run-a-to-b-prototype.ps1` also calls this gate immediately
before any auto-turn key pulse and immediately before the final
`--navigate-waypoints` command. If the current PID/HWND does not satisfy the
proof-anchor gate, the prototype fails closed before sending input.

## Gated exact-target forward-smoke wrapper

For the smallest active forward proof, prefer the dedicated one-pulse wrapper
instead of ad hoc manual key posting:

```powershell
.\scripts\invoke-gated-forward-smoke.ps1 `
  -ProcessId <current_rift_pid> `
  -TargetWindowHandle <current_rift_hwnd> `
  -HoldMilliseconds 250 `
  -PulseCount 1 `
  -Json
```

The wrapper is intentionally narrow:

- sends only `W`;
- requires exact PID and HWND;
- runs `assert-current-proof-coord-anchor-readback.ps1` immediately before
  input and immediately after each pulse;
- enforces a pre-input proof-age budget with
  `-MinimumPostReadbackAgeBudgetSeconds 15` by default, so a proof anchor that
  is about to cross the age gate blocks before input instead of failing only
  after movement;
- defaults to foreground-gated input through `post-rift-key.ps1
  -RequireTargetForeground`;
- refuses holds above `1000 ms` and refuses more than `3` pulses;
- does not refresh proof anchors, use Cheat Engine, or treat SavedVariables as
  live truth;
- writes a structured summary with pre/post coordinates and computed delta.

Use `-DryRun` for a no-input wrapper preflight. Use
`-AllowBackgroundPostMessage` only when foreground `SendInput` is intentionally
not desired; exact PID/HWND validation still applies.

Offline regression:

```powershell
.\scripts\test-assert-current-proof-coord-anchor.ps1
.\scripts\navigation\test-run-a-to-b-proof-anchor-gate.ps1
.\scripts\test-invoke-gated-forward-smoke.ps1
```

## Current restarted-PID evidence from 2026-05-06

Current live process checked during this workflow:

- RIFT PID: `47560`
- HWND: `0x2122E`
- Rule in force: no Cheat Engine and no input/movement.

What was proven:

1. RiftReader proof-anchor refresh failed closed because the newest
   coord-trace anchor belonged to old PID `11220`, not current PID `47560`.
   Latest no-CE recheck artifact:
   `C:\RIFT MODDING\RiftReader\scripts\captures\resolve-proof-coord-anchor-currentpid-47560-no-ce-recheck-20260506-090105.json`.
2. The older RiftScan promotion candidate
   `C:\RIFT MODDING\Riftscan\reports\generated\live-auto-move-forward-repeat-20260429-141511-vec3-truth-promotion.json`
   was not readable in PID `47560`:
   - candidate: `vec3-promoted-000001`
   - old base/offset: `0x975E1D8000 + 0x47EC`
   - absolute address: `0x975E1DC7EC`
   - observed failure: `ReadProcessMemory` Win32 `299`
   - RiftScan verification artifact:
     `C:\RIFT MODDING\Riftscan\reports\generated\riftreader-currentpid-47560-verify-old-promoted-coordinate-20260506-085630.json`
3. A RiftScan process-inventory check found no selected current region at the
   old promotion base `0x975E1D8000`:
   `C:\RIFT MODDING\Riftscan\reports\generated\riftreader-currentpid-47560-old-promotion-base-inventory-20260506-085616.json`.
4. A fresh no-input RiftScan passive capture for PID `47560` completed and
   verified:
   `C:\RIFT MODDING\Riftscan\sessions\riftreader-currentpid-47560-passive-noinput-20260506-085655`.
5. Importing the fresh passive `vec3_candidates.jsonl` into RiftReader and
   sampling with `--record-session` succeeded:
   - watchset:
     `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-currentpid-47560-passive-vec3-watchset-20260506-085915.json`
   - readback:
     `C:\RIFT MODDING\RiftReader\scripts\sessions\riftscan-currentpid-47560-passive-vec3-readback-20260506-085926`
   - result: `IntegrityStatus=ok`, `TotalRegionReadFailures=0`
6. The one-command wrapper was added and live-tested with the same no-CE/no-input
   boundary:
   - summary:
     `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-20260506-090614.json`
   - result: proof anchor `failed`, candidates `10`, readback `ok`,
     failures `0`, movement `blocked`
7. The wrapper was then hardened to decode the readback vec3 bytes and compare
   them to RiftScan source previews:
   - summary:
     `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-20260506-091212.json`
   - result: candidates `10`, decoded `10`, stable decoded `10`,
     source-preview matches `10`, read failures `0`
8. Decode-only regression was added:
   `C:\RIFT MODDING\RiftReader\scripts\test-invoke-riftscan-coordinate-readback-decode.ps1`.
9. The wrapper was smoke-tested again using an existing current-PID RiftScan
   candidate file, without a new capture:
   - summary:
     `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-20260506-091657.json`
   - result: candidates `10`, decoded `10`, stable decoded `10`,
     source-preview matches `10`, read failures `0`, movement `blocked`
10. The hard movement preflight guard was added and live-checked against PID
    `47560`:
    - script: `C:\RIFT MODDING\RiftReader\scripts\assert-current-proof-coord-anchor.ps1`
    - regression: `C:\RIFT MODDING\RiftReader\scripts\test-assert-current-proof-coord-anchor.ps1`
    - live artifact:
      `C:\RIFT MODDING\RiftReader\scripts\captures\proof-coord-anchor-preflight-currentpid-47560-20260506-092319.json`
    - result: `Status=failed`, `MovementAllowed=false`, no CE, no movement,
      because the coord-trace anchor does not match current live process
11. The A-to-B navigation prototype was wired to this gate before auto-turn and
    navigate input:
    - script: `C:\RIFT MODDING\RiftReader\scripts\navigation\run-a-to-b-prototype.ps1`
    - regression:
      `C:\RIFT MODDING\RiftReader\scripts\navigation\test-run-a-to-b-proof-anchor-gate.ps1`
    - live no-input artifact:
      `C:\RIFT MODDING\RiftReader\scripts\captures\proof-coord-anchor-preflight-currentpid-47560-no-ce-post-movement-gate-20260506-093120.json`
    - result: `Status=failed`, `MovementAllowed=false`, `NoCheatEngine=true`,
      `MovementSent=false`; movement remains blocked for PID `47560`

Conclusion:

- Old RiftScan absolute-address promotions are session-bound after a client
  restart. They remain useful historical candidate evidence, but they must not
  be used as current movement truth.
- Fresh RiftScan current-PID candidates can be imported and read by RiftReader,
  proving the candidate exchange path works.
- Passive-only candidates are still **candidate-only**. They are not the
  canonical coord-trace proof anchor and do not unlock movement.

## Feedback loop back to RiftScan

After RiftReader samples the current process:

1. Keep the RiftReader session artifact path beside the original RiftScan
   candidate file in RiftReader-side docs or feedback packets.
2. While RiftScan is read-only, generate
   `scripts\captures\riftscan-feedback-packet-*.json` with
   `scripts\riftscan_feedback.py` instead of writing notes into RiftScan.
3. Only if the user explicitly authorizes a RiftScan edit/write pass, copy the
   reviewed outcome into RiftScan as a corroboration/rejection note; preserve
   alternatives as replayable evidence rather than deleting them.
4. If a candidate fails, record the observed reason as
   `soft_rejected` / `blocked_current_pid_mismatch` / `stale_session` in the
   RiftReader-owned packet first.
5. Prefer another authorized RiftScan capture/compare pass over broad
   RiftReader heuristic scanning.

## Promotion rule

Only promote a candidate into RiftReader movement/navigation if all are true:

1. The candidate came from a current-session or repeat-recovered RiftScan
   artifact.
2. RiftReader read the current PID at the candidate address successfully.
3. A fresh, explicitly live corroboration source agrees within tolerance.
4. The result is written as a new current-truth/proof artifact.
5. Movement preflight can distinguish it from stale SavedVariables or old PID
   proof anchors.

Until then, the candidate remains useful for discovery, but movement stays
blocked.
