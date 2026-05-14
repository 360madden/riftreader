# Handoff — Route-Selected Coordinate Candidate Gate

Created: `2026-05-14T12:04:16Z`

## Verdict

Latest coordinate proof route has **API-now / memory-now agreement** for PID `2928` / HWND `0xC0994`, and milestone review now selects that route candidate instead of an older family-import candidate. This is **read-only proof planning only**: movement remains blocked and proof-anchor promotion remains blocked.

## Current selected read-only candidate

| Field | Value |
|---|---|
| Selection source | `latest-coordinate-proof-route-memory-readback` |
| Candidate ID | `api-family-hit-000001` |
| Address | `0x268E2BC09E0` |
| Candidate file | `scripts/captures/family-scan-currentpid-2928-20260514-114535-319032/api-family-vec3-candidates.jsonl` |
| Memory readback | `scripts/captures/riftscan-proof-readonly-current-after-drift-best-1-20260514-114545/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260514-074606.json` |
| Route | `scripts/captures/coordinate-proof-route-current-reacquire-20260514-074641-promotion-readiness-routing/coordinate-proof-route.json` |
| Reference max abs delta | `4.1503906231810106e-05` |
| Reference match count | `2` |
| Stable decoded candidates | `2` |
| Movement allowed | `false` |

## Promotion / movement blockers

- fresh displaced/two-reference match missing; bothReferenceMatchCount=0
- displaced-reference readiness is blocked
- proof-anchor promotion allowed=False
- same-target movement-grade ProofOnly anchor is still not promoted
- movement/player-control input remains blocked without explicit approval and proof-gate pass

## Fresh artifacts

| Artifact | Path | Status |
|---|---|---|
| Milestone review | `scripts/captures/riftscan-milestone-review-20260514-120033.json` | `ready-for-read-only-proof` |
| Readiness gate | `scripts/captures/coordinate-proof-readiness-gate-20260514-080033-route-selection/summary.json` | `passed` / `ready-for-read-only-proof` |
| Candidate comparison | `scripts/captures/coordinate-candidate-comparison-currentpid-2928-20260514-074627-current-after-drift-vs-displaced/summary.json` | `candidate-only-no-two-reference-match` |
| Displaced readiness | `scripts/captures/coordinate-displaced-reference-readiness-currentpid-2928-20260514-070715/summary.json` | `blocked` |
| HTML summary | `docs/recovery/coordinate-proof-route-actions-1-10-summary-2026-05-14-120416.html` | created this handoff pass |

## Safe resume commands

These are command arrays from the milestone review. They are read-only planning/proof commands and do not grant movement permission.

```json
{
  "writesToRiftScan": false,
  "notes": [
    "Commands are shown as argument arrays to avoid shell-string ambiguity.",
    "Do not run invoke-riftscan-coordinate-readback.ps1 without -CandidateFile while RiftScan is read-only; that path creates a RiftScan capture/session."
  ],
  "freshProofOnly": [
    "python",
    "C:\\RIFT MODDING\\RiftReader\\scripts\\live_test.py",
    "--profile",
    "ProofOnly",
    "--pid",
    "2928",
    "--hwnd",
    "0xC0994",
    "--process-name",
    "rift_x64"
  ],
  "readOnlyProofPose": [
    "pwsh",
    "-NoLogo",
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "C:\\RIFT MODDING\\RiftReader\\scripts\\capture-riftscan-proof-pose.ps1",
    "-CandidateFile",
    "C:\\RIFT MODDING\\RiftReader\\scripts\\captures\\family-scan-currentpid-2928-20260514-114535-319032\\api-family-vec3-candidates.jsonl",
    "-ProcessId",
    "2928",
    "-TargetWindowHandle",
    "0xC0994",
    "-ProcessName",
    "rift_x64",
    "-Json"
  ],
  "readOnlyCandidateReadback": [
    "pwsh",
    "-NoLogo",
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "C:\\RIFT MODDING\\RiftReader\\scripts\\invoke-riftscan-coordinate-readback.ps1",
    "-CandidateFile",
    "C:\\RIFT MODDING\\RiftReader\\scripts\\captures\\family-scan-currentpid-2928-20260514-114535-319032\\api-family-vec3-candidates.jsonl",
    "-ProcessId",
    "2928",
    "-TargetWindowHandle",
    "0xC0994",
    "-ProcessName",
    "rift_x64",
    "-Json"
  ]
}
```

## Next best action

Capture or otherwise provide a fresh displaced-pose reference for the same PID/HWND, then rerun candidate comparison and the route generator. Do not promote the proof anchor or send movement until promotion readiness and same-target ProofOnly pass.
