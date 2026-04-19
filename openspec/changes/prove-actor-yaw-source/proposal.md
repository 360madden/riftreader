## Why

Actor orientation on `main` is still marked stale after the April 14, 2026 update because the source-chain and selector-owner refresh path is not yet trustworthy enough to promote a live yaw source back to repo truth. This branch already has a repo-native debug scan, but it still lacks a clear proof contract for when a candidate is authoritative and safe to publish as current truth.

## What Changes

- Add a deterministic actor-yaw proof workflow centered on current player/coord truth, candidate discovery, turn-stimulus proof, and optional bounded debug confirmation.
- Require the workflow summary to record the selected candidate, supporting evidence artifacts, freshness/degraded state, and whether the run is eligible for truth promotion.
- Define how repo truth is updated when a run proves an authoritative actor-yaw source, and how stale status is preserved when proof fails or relies on cached fallback artifacts.

## Capabilities

### New Capabilities
- `actor-yaw-proof`: prove a candidate actor-yaw memory source with repo-owned evidence, explicit degraded-state reporting, and a promotion-ready outcome when the proof gate passes.

### Modified Capabilities
None.

## Impact

- `C:\RIFT MODDING\RiftReader\scripts\run-actor-yaw-debug-scan.ps1` and the related orientation candidate search/proof helpers
- actor-yaw debug artifacts under `C:\RIFT MODDING\RiftReader\captures\actor-yaw-debug\` and related debug output directories
- repo truth and recovery docs such as `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`, `C:\RIFT MODDING\RiftReader\README.md`, and branch recovery notes
- any reader-side or script-side fields needed to expose proof quality, candidate selection basis, and fallback status
