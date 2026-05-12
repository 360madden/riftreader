# RiftReader Current Handoff

- Status: `maintenance-blocked`
- Generated UTC: `2026-05-12T09:47:41.093464Z`
- Current lane: `post-update proof-anchor reacquisition paused because RIFT is down for maintenance`
- Branch: `main`
- HEAD: `0dcf639bb2987f984d6afff7e7e3b82c3daec005`
- Dirty files before handoff: `0`
- RIFT process snapshot status: `failed`
- RIFT process count: `0`
- Latest Stage 1 summary: `C:\RIFT MODDING\RiftReader\scripts\captures\postupdate-proof-reacquire-stage1-20260512T080211Z\stage1-wrapper-summary.json`

## Current blocker

RIFT is unavailable/down for maintenance. Live target resolution, visual gate, coordinate-family scan, proof promotion, ProofOnly, yaw, route smoke, and movement workflows are blocked until the game is back and Atank is confirmed in-world.

## Exact next action

After maintenance ends: pull latest main if needed, log into Atank in-world, then run cmd\riftreader-postupdate-proof-reacquire-stage1.cmd --visual-full. Only run --allow-movement-stimulus after visual gate and coordinate truth are healthy.

## Do not do

- Do not run live recovery while RIFT is down for maintenance.
- Do not run Stage 1, ProofOnly, promotion, yaw, route smoke, auto-turn, or navigation until Atank is in-world.
- Do not update docs/recovery/current-truth.md or docs/recovery/current-proof-anchor-readback.json before same-target ProofOnly passes.
- Do not use old PID/HWND proof pointers as current truth.
- Do not commit unrelated local changes.

## Verified helper state

- `cmd/riftreader-postupdate-proof-reacquire-stage1.cmd`
- `scripts/riftreader_postupdate_proof_reacquire_stage1.py`
- `scripts/test_riftreader_postupdate_proof_reacquire_stage1.py`
- `docs/development/postupdate-proof-reacquire-stage1.md`

## Drive artifacts

- `G:\My Drive\RiftReader\status\RIFTREADER_CURRENT_STATUS.md`
- `G:\My Drive\RiftReader\status\RIFTREADER_CURRENT_STATUS.json`

# END_OF_DOCUMENT_MARKER
