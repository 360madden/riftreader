# Current-PID 60628 coordinate-family reacquisition

Generated: `2026-05-13T05:09:13Z`

## TL;DR

- Current target was revalidated read-only:
  - PID `60628`
  - HWND `0xCE0FCE`
  - process start UTC `2026-05-13T04:53:58.081190Z`
  - module base `0x7FF796B50000`
  - preflight: `scripts/captures/x64dbg-target-preflight-20260513-050845-232095/summary.json`
- ChromaLink world-state is still stale/not proof-grade:
  - `scripts/captures/chromalink-world-state-reference-20260513-050558-773185/summary.json`
  - blockers include `world-state-player-position-not-fresh`, `world-state-player-position-stale`, and `world-state-navigation-player-position-unavailable`
- Fresh `RRAPICOORD1` API-runtime coordinate truth was reacquired from process memory with no input and no Cheat Engine:
  - `scripts/captures/manual-current-reference-check-20260513-0502/rift-api-reference-currentpid-60628-20260513-050204.json`
  - selected marker seq `914`
  - coordinate `X=7408.8496`, `Y=871.77`, `Z=3031.02`
  - captured UTC `2026-05-13T05:02:29.5603204Z`
- Broad current-PID family scan found the active coordinate family:
  - `scripts/captures/family-scan-currentpid-60628-20260513-050246/family-scan-summary.json`
  - scanned `921030656` bytes across `2215` chunks
  - found `26` candidate XYZ triplets
  - top family/base `0x1FF07560000`
  - best first-pose exact address `0x1FF0756BD9C`
- A fresh targeted family rescan against the same family confirmed the family moved/currented with a newer reference:
  - `scripts/captures/family-scan-currentpid-60628-20260513-050620/family-scan-summary.json`
  - fresh reference marker seq `3116`
  - coordinate `X=7409.71`, `Y=871.77`, `Z=3031.4199`
  - found `2` matching triplets in the same family/base `0x1FF07560000`
  - best second-pose exact address `0x1FF0756EC9C`
- Two-pose ranking supports the family, not a stable exact address:
  - `scripts/captures/coordinate-family-rank-currentpid-60628-20260513-050620-two-pose/coordinate-family-rankings.json`
  - top family `0x1FF07560000`
  - family support pose count `2`
  - exact address support pose count only `1`
  - result remains `candidateOnly=true`

## Current truth level

Fresh current-session API coordinate truth is available through `RRAPICOORD1`.
The active coordinate **family** is reacquired for PID `60628` as
`0x1FF07560000`.

Do **not** promote a static pointer or exact coord address yet:

- exact addresses changed between captures:
  - pose/reference 1: best `0x1FF0756BD9C`
  - pose/reference 2: best `0x1FF0756EC9C`
- same family `0x1FF07560000` matched across both captures
- no restart validation
- no stable exact address
- no runtime proof-anchor promotion
- no movement proof
- no x64dbg writer/source proof

## Pointer-family follow-up

Read-only grouped pointer scan was run against the family and top exact leads:

- artifact: `scripts/captures/pointer-family-scan-20260513-050752-113087/summary.json`
- seeds included:
  - `0x1FF07560000`
  - `0x1FF0756EC9C`
  - `0x1FF0756F4D4`
  - `0x1FF0756BD9C`
  - `0x1FF0756D31C`
- result:
  - family base `0x1FF07560000` had `2` heap refs
  - exact triplet addresses had `0` refs
  - module hits `0`
  - rift module hits `0`

Interpretation: this found current-process heap references only, not a static
root.

## Final freshness check

Another `RRAPICOORD1` reference capture after the scans still succeeded:

- `scripts/captures/manual-current-reference-check-20260513-0508/rift-api-reference-currentpid-60628-20260513-050847.json`
- selected marker seq `4334`
- coordinate `X=7409.71`, `Y=871.77`, `Z=3031.4199`
- captured UTC `2026-05-13T05:09:13.2034882Z`

This confirms the addon/runtime API coordinate source was live after the broad
scan work, even though ChromaLink world-state remained stale.

## Safety

- No x64dbg attach.
- No Cheat Engine.
- No process memory writes.
- No game input.
- No `/reloadui`.
- No screenshot-key input.
- No provider/ChromaLink repo edits.

## Resume-safe next action

Continue with the family-first strategy:

1. Keep `0x1FF07560000` as the top current-PID coordinate-family lead.
2. Do not promote any exact address yet.
3. Capture a deliberate displaced pose if/when approved, then rerun the family
   scan/ranking.
4. Require either:
   - same exact address across displaced poses, or
   - stronger family ownership/source evidence plus proof-anchor readback.
5. Only use x64dbg surgically after the family is ranked and current target
   freshness is proven.

