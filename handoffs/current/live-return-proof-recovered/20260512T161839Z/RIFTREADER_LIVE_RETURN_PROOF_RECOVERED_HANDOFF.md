# RiftReader Current Handoff

- Status: `proofonly-passed-current-proof-recovered`
- Generated UTC: `2026-05-12T16:18:39.998791Z`
- Current lane: `post-maintenance proof-anchor reacquisition completed; current coordinate proof is restored for exact PID/HWND`
- Branch: `main`
- HEAD before commit: `44610842fb17b6447f5bab69d94719cf7ad2b0ec`
- Target: `rift_x64` PID `57656`, HWND `0x5417BC`
- Candidate: `api-family-hit-000001` at `0xCC080EC30C`
- ProofOnly: `passed-proof-only` / ok=`True`

## Current proof

- Promotion status: `validated`
- Assert status: `valid`
- Movement gate after assert: `True`
- ProofOnly movement sent: `False`
- ProofOnly movement attempted: `False`
- Coordinate: `{'x': 7407.42919921875, 'y': 871.8069458007812, 'z': 3030.127685546875, 'recordedAtUtc': '2026-05-12T11:10:56.4345281Z'}`

## Key artifacts

- Stage 1: `C:\RIFT MODDING\RiftReader\scripts\captures\postupdate-proof-reacquire-stage1-python-20260512T103220Z\stage1-python-summary.json`
- Batch: `C:\RIFT MODDING\RiftReader\scripts\captures\postupdate-proof-reacquire-stage1-python-20260512T103220Z\coordinate-anchor-batch\coordinate-anchor-batch-summary.json`
- Promotion: `C:\RIFT MODDING\RiftReader\scripts\captures\promote-stage1-and-proofonly-20260512T111004Z\promote-stage1-and-proofonly-summary.json`
- ProofOnly readback: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-57656-readback-summary-20260512-071051.json`
- Current proof pointer: `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json`
- Current truth: `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`

## Exact next action

Run only separately gated post-proof validations next: visual gate + fresh proof preflight before route smoke, yaw, actor-facing, auto-turn, or navigation. Do not treat those as current until separately revalidated.

## Do not do

- Do not use old PID/HWND proof pointers as current truth.
- Do not claim route, yaw, actor-facing, auto-turn, or navigation truth is restored from this proof alone.
- Do not send route/navigation movement without fresh target-control, visual gate, and proof preflight.
- Do not commit capture directories unless explicitly requested.

# END_OF_DOCUMENT_MARKER
