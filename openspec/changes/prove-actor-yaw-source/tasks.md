## 1. Define the actor-yaw proof contract

- [x] 1.1 Add selection, promotion-readiness, and degraded-state fields to the actor-yaw workflow summary artifact
- [x] 1.2 Normalize cached/live/debug-blocked reporting across the candidate search, proof, and debug-trace steps

## 2. Harden the proof workflow

- [x] 2.1 Ensure the workflow uses current player/coord truth and deterministic candidate-selection ordering
- [x] 2.2 Ensure turn-stimulus proof records the thresholds, coord-drift measurements, and truth-like evidence for each tested candidate
- [x] 2.3 Block promotion-ready outcomes when cached fallback, stale artifacts, skipped stimulus, or skipped debug confirmation invalidate the proof gate

## 3. Publish repo truth from promotion-ready runs

- [x] 3.1 Update the current-truth and recovery docs to describe the authoritative actor-yaw source only when a promotion-ready run exists
- [x] 3.2 Update README and workflow guidance so the repo-native actor-yaw path is the documented source of truth for future rebuilds

## 4. Validate end to end

- [x] 4.1 Run the actor-yaw workflow against a live Rift client and save representative proof artifacts
- [x] 4.2 Verify that failure or degraded runs preserve stale/provisional truth instead of promoting a source
