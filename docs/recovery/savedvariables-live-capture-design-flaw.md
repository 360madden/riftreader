# SavedVariables Live-Capture Design Flaw

_Created: 2026-04-30_

## Verdict

`ReaderBridgeExport.lua` and other RIFT addon `SavedVariables` files are
**not live data feeds**. They are post-save snapshots. Treating them as live IPC
during coordinate discovery is a major workflow/design flaw.

## Correct model

| Surface | Updates during normal play? | External reader sees updates live? | Correct use |
|---|---:|---:|---|
| In-game addon runtime state | Yes | No, unless exposed through a real live bridge | In-game UI, labels, runtime trace state |
| On-screen addon overlay | Yes | Yes, via screenshot/OCR or visual inspection | Live ground truth for manual captures |
| Native memory reads | Yes | Yes | Candidate discovery and validation |
| Validated coord-trace anchor | Yes | Yes | Proof-grade movement/polling source |
| `ReaderBridgeExport.lua` SavedVariables file | No, not continuously | No | Post-`/reloadui` / logout / UI-save snapshot only |

## What went wrong in `manual-bundle-001`

During `manual-bundle-001`, the on-screen `PlayerCoords` overlay showed live
positions around:

```text
7454.6, 893.1, 3020.4 -> 7461.0, 894.2, 3019.3
```

But `ReaderBridgeExport.lua` still contained an older saved coordinate around:

```text
7293.4897, 818.4000, 3094.7000
```

The file timestamp did not advance during the capture. Seeds produced from that
file were therefore stale relative to the live overlay trajectory.

## Hard rules

| Rule | Requirement |
|---|---|
| Do not use SavedVariables as live IPC | `ReaderBridgeExport.lua` must not be treated as a live stream during START/STOP movement capture |
| Timestamp every file-derived seed | Record SavedVariables `LastWriteTimeUtc` and capture start/end times |
| Classify freshness explicitly | If the file timestamp predates capture start, mark derived data `stale-post-save-snapshot` |
| Separate truth surfaces | Do not mix overlay truth and SavedVariables-derived seeds without labeling their time domains |
| Fail closed | If a live bundle accidentally depends on stale SavedVariables for ground truth, stop and reframe the run |
| Use real live truth | Prefer overlay screenshots/OCR, native memory, or validated coord-trace anchors for live movement data |
| Use `/reloadui` only for snapshots | `/reloadui` can create a post-flush snapshot, but it is not a substitute for a live feed |

## Required manifest fields for future coord bundles

Every future live coordinate bundle should declare:

```json
{
  "truthSurface": "overlay|validated-memory-anchor|post-flush-savedvariables|other",
  "savedVariablesUse": "none|post-flush-snapshot|seed-only|invalid-for-live",
  "savedVariablesLastWriteUtc": "optional ISO timestamp",
  "captureStartUtc": "ISO timestamp",
  "freshnessClassification": "live|post-flush-current|stale-post-save-snapshot",
  "failClosedIfStaleSavedVariables": true
}
```

## Adapted workflow

| Step | New behavior |
|---:|---|
| 1 | Before capture, declare the authoritative truth surface |
| 2 | If using `ReaderBridgeExport.lua`, verify it is intentionally a post-flush snapshot |
| 3 | For START/STOP live movement, stream screenshots/OCR and native memory once per second or faster as needed |
| 4 | Use visible overlay coordinates as live truth unless a validated memory anchor exists; this can be ReaderBridge's own API-backed coord display or observed/on-screen PlayerCoords values, not SavedVariables or addon files |
| 5 | Derive memory candidates from live truth samples, not from stale SavedVariables |
| 6 | Preserve stationary tail samples for cache/static rejection |
| 7 | Write `freshnessClassification` into every seed/candidate packet |

## Impact on current bundle

| Artifact | Classification |
|---|---|
| `stream-1hz-20260430-182451\screenshots\sample-*.png` | Live visual truth |
| `overlay-coords-manual-extract.csv` | Live overlay-derived truth at displayed 1-decimal precision |
| `seed-addresses.json` | Stale-risk seed list; derived from old point-1 SavedVariables-backed scan |
| `point-01` / `point-02` / `point-03` ReaderBridge snapshot coords | Stale post-save snapshot relative to stream overlay |
| Native seed reads during stream | Valid reads of stale-risk seeds; useful mainly as negative/cache evidence |

## Next implementation target

Build or patch the coord bundle workflow so it:

1. refuses to call SavedVariables file data "live";
2. captures overlay screenshots/OCR as the live truth source when no validated
   memory anchor is available;
3. writes freshness metadata into seeds, samples, candidate scores, and
   promotion gates;
4. performs fresh scans against extracted live overlay coordinates instead of
   stale file-backed coordinates.
