# ChromaLink Change Request

Date: 2026-05-15  
Requested by: RiftReader recovery workflow  
RiftReader branch/session: `main`, fast coordinate-anchor restart recovery

## Need

- RiftReader use case:
  - Use ChromaLink `/api/v1/riftreader/world-state` as the fastest API-now
    coordinate reference for post-restart player-coordinate proof-anchor
    recovery.
- Existing ChromaLink endpoint/client checked:
  - `http://127.0.0.1:7337/api/v1/riftreader/world-state`
  - Checked by `scripts/chromalink_world_state_reference.py` during
    `scripts/recover_current_pid_coord_anchor_fast.py --execute`.
- Missing field/behavior:
  - The endpoint was reachable, but player position was stale and the aggregate
    was unhealthy.
  - No fresh `referenceJson` could be produced for RiftReader recovery.
- Why current ChromaLink data is insufficient:
  - The 2026-05-15 fast recovery run blocked ChromaLink with:
    - `world-state-not-healthy`
    - `world-state-player-position-not-fresh`
    - `world-state-player-position-stale`
    - `world-state-navigation-player-position-unavailable`
  - Source snapshot diagnostics showed:
    - snapshot generated: `2026-05-15T05:52:47.7651831Z`
    - aggregate last updated: `2026-05-14T13:52:33.8308+00:00`
    - newest frame age: about `58,193,934 ms`
    - fresh frame count: `0`
    - stale frame count: `4`

## Proposed provider contract

- Endpoint or client API:
  - `/api/v1/riftreader/world-state`
- Proposed JSON/client field names:
  - Preserve existing `player.position.{x,y,z,observedAtUtc,fresh,stale,ageMs}`.
  - Preserve aggregate readiness fields:
    `ready`, `healthy`, `fresh`, `stale`, and
    `navigation.playerPositionAvailable`.
  - If unavailable, include a machine-readable stale reason such as:
    `player.position.staleReason`.
- Expected freshness/latency:
  - Player position must be fresh enough for coordinate proof recovery.
  - Current RiftReader freshness gate expects the provider to mark stale data as
    stale and refuse promotion to API-now truth.
  - Target goal: position `ageMs <= 5000` during active live recovery.
- Read-only vs control:
  - Read-only telemetry only.
  - No movement, input, focus, debugger, or process-memory behavior is requested
    from ChromaLink.
- Backward compatibility concerns:
  - Existing fields should remain stable.
  - New stale-reason fields should be additive.

## Consumer plan

- RiftReader adapter area:
  - `scripts/chromalink_world_state_reference.py`
  - `scripts/recover_current_pid_coord_anchor_fast.py`
- Validation command/proof needed in RiftReader:
  - `python scripts/chromalink_world_state_reference.py --target-pid <PID> --target-hwnd <HWND> --process-name rift_x64 --json`
  - `python scripts/recover_current_pid_coord_anchor_fast.py --pid <PID> --hwnd <HWND> --execute --json`
- Blocked until ChromaLink handoff/commit:
  - ChromaLink cannot be used as the fast reference provider until
    `world-state` returns a fresh player position and writes a non-null
    `referenceJson`.
  - RiftReader currently falls back to RRAPICOORD reference capture, which is
    correct but slow.

## Boundaries

- Does this request involve heading/facing/yaw/control?
  - No.
- Is raw diagnostic snapshot data being promoted to a stable contract?
  - No. Snapshot diagnostics are used only to explain why the provider is stale.
  - Any new provider fields should be implemented with ChromaLink schema/docs/tests
    before RiftReader treats them as contract.

## Evidence from latest RiftReader run

| Field | Value |
|---|---|
| Run summary | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-27552-20260515-055223-314971/summary.json` |
| ChromaLink summary | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-27552-20260515-055223-314971/02-reference-chromalink/summary.json` |
| Result | ChromaLink blocked; RRAPICOORD fallback used |
| Final recovery status | Passed after fallback, movement-approved pose validation, promotion, and ProofOnly |
