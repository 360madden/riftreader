# Actor-Yaw Phase 2 Pre-Restart Baseline

| Fact | Value |
|---|---|
| Status | `phase2-pre-restart-baseline-ready` |
| Target | `rift_x64` PID `33912`, HWND `0xE0DB2` |
| Process start UTC | `2026-05-08T02:38:08.7156673Z` |
| Window | `RIFT` / responding `true` |
| Actor-yaw lead | `0x202CA5D23E0 @ 0xD4` |
| Candidate key | `0x202CA5D23E0|0xD4` |
| Validation method | `isolated-disambiguation-survivor-plus-no-input-readback` |
| Yaw readbacks | read-player `passed`, capture `passed` |
| Coordinate proof | `passed-proof-only` at `2026-05-08T19:43:47.2788961Z` |
| Movement allowed | `false` |
| No Cheat Engine | `true` |

## Artifacts

| Artifact | Path |
|---|---|
| `disambiguationPacket` | `C:\RIFT MODDING\RiftReader\docs\recovery\current-actor-yaw-disambiguation.json` |
| `leadFile` | `C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json` |
| `latestActorYawReadbackPointer` | `C:\RIFT MODDING\RiftReader\scripts\captures\latest-actor-yaw-readback-smoke.json` |
| `latestActorYawReadbackSummary` | `C:\RIFT MODDING\RiftReader\scripts\captures\actor-yaw-readback-smoke-currentpid-33912-20260508-194107\run-summary.json` |
| `latestProofOnlyPointer` | `C:\RIFT MODDING\RiftReader\scripts\captures\latest-live-test-run.json` |
| `latestProofOnlyRunSummary` | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-194205\run-summary.json` |
| `latestProofOnlyReadbackSummary` | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-33912-readback-summary-20260508-154337.json` |

## Phase 2 fallback order

1. Rebind exact new PID/HWND and run actor_yaw_readback_smoke.py first.
2. If direct readback fails, search near the prior behavior-backed source/candidate structure.
3. If narrow rebind fails, rerun orientation candidate search with ledger penalties.
4. Promote only after controlled turn-only yaw validation and zero proof-coordinate movement.
5. Keep movement and auto-turn blocked until separate gates pass.
