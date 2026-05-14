# Historical coordinate proof-anchor discovery timelines — May 2026

Generated: `2026-05-14T18:22:13Z`
Repo: `C:\RIFT MODDING\RiftReader`

## Summary

This document records historical successful, partial, and blocked coordinate proof-anchor discovery attempts so future recovery can compare patterns without mixing old process-epoch truth into current proof.

| Metric | Count |
|---|---:|
| Total attempts documented | 10 |
| Successful proof-anchor attempts | 4 |
| Blocked attempts | 2 |
| Candidate/partial attempts | 3 |

Latest current anchor for comparison:

| Field | Value |
|---|---|
| Candidate | `snapshot-delta-21487DF8F64-xyz` |
| Address | `0x21487DF8F64` |
| Target | PID `16536` / HWND `0x1E0D66` |
| Status | `current-target-proofonly-passed` |
| Latest ProofOnly | `passed-proof-only` |

## Chronological timeline

| Date/time | Attempt | Class | Target | Candidate | Address | Result | MovementAllowed | MovementSent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05-01 | API-first coordinate reacquisition scaffold | foundation | current target at that time; session-specific | none promoted |  | foundation-success | False | False |
| 2026-05-06 | No-CE multi-pose promotion bridge | successful-proof-anchor-foundation | stale trace rejected; current PID/HWND revalidated during run | reference-scored candidates |  | workflow-success | None | False |
| 2026-05-06T14:42:59Z | Direct no-input current-PID proof artifact | successful-proof-anchor | PID 47560 / HWND 0x2122E | api-probe-triplet-000007 | 0x2400EA32120 | valid | True | False |
| 2026-05-06T23:31:10-04:00 / 2026-05-07T03:31:10Z | RiftScan-first proof anchor plus forward smoke | successful-proof-anchor-plus-movement | PID 47560 / HWND 0x2122E | rift-addon-coordinate-candidate-000001 | 0x2400EA32120 | proof-gated movement passed | True | True |
| 2026-05-08T04:53Z | RefreshBaseline captured displaced proof pose; ProofOnly still required | partial-success-proof-baseline | PID 33912 / HWND 0xE0DB2 | rift-addon-coordinate-candidate-000001 | 0x202FEA3E180 | baseline captured; movement still blocked | False | False |
| 2026-05-13T07:29Z / 2026-05-13T16:31Z | PID 60628 three-pose candidates and static-chain blocker | strong-candidate-only | PID 60628 / HWND 0xCE0FCE | 0x1FF08502BC8 exact; 0x1FF94EC0000 family | 0x1FF08502BC8 | candidate-only; live target later nonresponsive | False | True |
| 2026-05-13T20:26 EDT | Coordinate proof readiness gate blocked stale/freshness mismatch | blocked-readiness | PID 2928 / HWND 0xC0994 | 0x268DF21ED20 chain candidate | 0x268DF21ED20 | blocked-coordinate-proof-readiness | False | False |
| 2026-05-14T02:13Z | ReaderBridge/RRAPICOORD live truth repaired; fresh family candidate found | candidate-only-live-truth-repaired | PID 2928 / HWND 0xC0994 | family-snapshot-hit-000001 | 0x268D1FA6120 | read-only candidate; movement blocked | False | False |
| 2026-05-14T12:34Z | Manual displacement runner found raw matches but valid displacement was zero | blocked-no-displacement | PID 2928 / HWND 0xC0994 | api-family-hit-000001 | 0x268E2BC09E0 | blocked-promotion-readiness | False | False |
| 2026-05-14T17:46:22.792929+00:00 | Current PID 16536 grouped-family displacement proof anchor | successful-proof-anchor-plus-movement | PID 16536 / HWND 0x1E0D66 | snapshot-delta-21487DF8F64-xyz | 0x21487DF8F64 | current-target-proofonly-passed | True | True |

## Detailed attempts

### 2026-05-01 — API-first coordinate reacquisition scaffold

| Field | Value |
|---|---|
| Classification | `foundation` |
| Target | `current target at that time; session-specific` |
| Candidate | `none promoted` |
| Address | `` |
| Result | `foundation-success` |
| Proof method | `RRAPICOORD1 / Inspect.Unit.Detail player API truth scaffold` |
| MovementAllowed | `False` |
| MovementSent | `False` |

**What happened:** Moved recovery away from stale SavedVariables and old memory addresses. Established live API/runtime coordinate truth as the starting surface.

**Fast/slow pattern:** Faster future recovery because a live truth surface exists before memory scans.

**Artifacts:**
- `memory: MEMORY.md lines 554-562`
- `rollout 019de4cc-afbb-7060-8d43-d02797959dd9`

**Related commits:**
- None recorded in this summary.

**Metrics:**

```json
{}
```

### 2026-05-06 — No-CE multi-pose promotion bridge

| Field | Value |
|---|---|
| Classification | `successful-proof-anchor-foundation` |
| Target | `stale trace rejected; current PID/HWND revalidated during run` |
| Candidate | `reference-scored candidates` |
| Address | `` |
| Result | `workflow-success` |
| Proof method | `no-ce-riftscan-reference-multisample promotion bridge` |
| MovementAllowed | `None` |
| MovementSent | `False` |

**What happened:** Built the strict path that turns reference-scored candidates into movement-gate compatible proof anchors without Cheat Engine.

**Fast/slow pattern:** Fast separator: stale trace anchors were rejected before work continued; proof stayed no-CE and current-PID.

**Artifacts:**
- `memory: MEMORY.md lines 564-582`
- `rollout 019dfcf2-aebd-7153-bed0-a3441cdf3635`

**Related commits:**
- `b42578a Add no-CE RiftScan proof anchor workflow`

**Metrics:**

```json
{}
```

### 2026-05-06T14:42:59Z — Direct no-input current-PID proof artifact

| Field | Value |
|---|---|
| Classification | `successful-proof-anchor` |
| Target | `PID 47560 / HWND 0x2122E` |
| Candidate | `api-probe-triplet-000007` |
| Address | `0x2400EA32120` |
| Result | `valid` |
| Proof method | `cache` |
| MovementAllowed | `True` |
| MovementSent | `False` |

**What happened:** Recorded stable no-input proof readback against the current PID. This is a historical proof anchor, now stale for current process epochs.

**Fast/slow pattern:** Fast because it used direct current-PID readback, stable samples, no movement, and no CE.

**Artifacts:**
- `scripts/captures/proof-anchor-currentpid-47560-readback-summary-20260506-144259.json`

**Related commits:**
- `17ede2e referenced in memory as no-input proof/handoff commit`

**Metrics:**

```json
{
  "decodedSampleCount": 12,
  "stableAcrossReadbackSamples": true,
  "readbackFailures": 0,
  "regionAddress": "0x2400EA320E0",
  "candidateOffsetInRegion": 64
}
```

### 2026-05-06T23:31:10-04:00 / 2026-05-07T03:31:10Z — RiftScan-first proof anchor plus forward smoke

| Field | Value |
|---|---|
| Classification | `successful-proof-anchor-plus-movement` |
| Target | `PID 47560 / HWND 0x2122E` |
| Candidate | `rift-addon-coordinate-candidate-000001` |
| Address | `0x2400EA32120` |
| Result | `proof-gated movement passed` |
| Proof method | `no-ce-riftscan-reference-multisample` |
| MovementAllowed | `True` |
| MovementSent | `True` |

**What happened:** RiftScan candidate was imported, validated against live reference readback, promoted into telemetry-proof-coord-anchor, then a proof-gated 1000 ms W pulse moved planar distance 1.2391483387792066.

**Fast/slow pattern:** Fast because RiftScan was treated as the candidate source and RiftReader stayed the proof/movement gate.

**Artifacts:**
- `docs/handoffs/2026-05-06-233226-riftscan-first-proof-anchor-resume-handoff.md`
- `C:\RIFT MODDING\Riftscan\reports\generated\codex-current-coord-region-passive-20260506-230940-addon-coordinate-matches.json`

**Related commits:**
- `114a5dd Use RiftScan coordinate candidates for proof anchor`
- `7e34ded Add RiftScan proof anchor resume handoff`

**Metrics:**

```json
{
  "support": 3,
  "bestMaxAbsDistance": 0,
  "forwardPulseMs": 1000,
  "planarDistance": 1.2391483387792066
}
```

### 2026-05-08T04:53Z — RefreshBaseline captured displaced proof pose; ProofOnly still required

| Field | Value |
|---|---|
| Classification | `partial-success-proof-baseline` |
| Target | `PID 33912 / HWND 0xE0DB2` |
| Candidate | `rift-addon-coordinate-candidate-000001` |
| Address | `0x202FEA3E180` |
| Result | `baseline captured; movement still blocked` |
| Proof method | `RefreshBaseline / proof baseline pool` |
| MovementAllowed | `False` |
| MovementSent | `False` |

**What happened:** Captured a displaced current-session proof pose about 3.023m from the prior blocked ProofOnly coordinate. This was useful evidence but not movement permission until ProofOnly reran.

**Fast/slow pattern:** Avoided false movement by separating baseline capture from ProofOnly. Slower because final proof gate was still pending.

**Artifacts:**
- `docs/handoffs/2026-05-08-005330-post-refreshbaseline-proofonly-needed-handoff.md`

**Related commits:**
- `0402eb1 Harden live proof resume handoff`
- `5051df0 Harden live-test HUD orchestration`

**Metrics:**

```json
{
  "planarDisplacementFromPriorBlockedProof": 3.023,
  "referenceMatchCount": 1,
  "stableDecodedCandidateCount": 1
}
```

### 2026-05-13T07:29Z / 2026-05-13T16:31Z — PID 60628 three-pose candidates and static-chain blocker

| Field | Value |
|---|---|
| Classification | `strong-candidate-only` |
| Target | `PID 60628 / HWND 0xCE0FCE` |
| Candidate | `0x1FF08502BC8 exact; 0x1FF94EC0000 family` |
| Address | `0x1FF08502BC8` |
| Result | `candidate-only; live target later nonresponsive` |
| Proof method | `grouped-family scan, displacement-aware ranking, x64dbg evidence` |
| MovementAllowed | `False` |
| MovementSent | `True` |

**What happened:** Three-pose ranking produced strong heap candidates, but no module/static chain was proven and the target became nonresponsive. Do not promote PID 60628 addresses.

**Fast/slow pattern:** Useful pattern discovery but slow as a recovery path because static owner/source was not proven and target health failed.

**Artifacts:**
- `docs/handoffs/2026-05-13-0729-currentpid-60628-threepose-candidate-blocker.md`
- `docs/handoffs/2026-05-13-1231-compact-static-pointer-chain-resume.md`

**Related commits:**
- `cd94266 Rank coordinate families by displacement tracking`
- `87e2a33 Record PID 60628 coordinate family reacquisition`
- `c064985 Rank coordinate families across poses`

**Metrics:**

```json
{
  "bestExactTrackMaxError": 0.004333593749834108,
  "bestFamilyTrackMaxError": 6.0937500165891834e-05,
  "sendInputPlanarDeltas": [
    0.4616189445850858,
    0.37082363732641205
  ]
}
```

### 2026-05-13T20:26 EDT — Coordinate proof readiness gate blocked stale/freshness mismatch

| Field | Value |
|---|---|
| Classification | `blocked-readiness` |
| Target | `PID 2928 / HWND 0xC0994` |
| Candidate | `0x268DF21ED20 chain candidate` |
| Address | `0x268DF21ED20` |
| Result | `blocked-coordinate-proof-readiness` |
| Proof method | `reference freshness watchdog + milestone review gate` |
| MovementAllowed | `False` |
| MovementSent | `False` |

**What happened:** A same-target candidate existed, but fresh reference truth was unavailable, so proof/readback and movement were blocked.

**Fast/slow pattern:** Slow/blocked because candidate presence was correctly not treated as proof without API-now truth.

**Artifacts:**
- `docs/handoffs/2026-05-13-2026-coordinate-proof-readiness-gate.md`

**Related commits:**
- `027d31d Add coordinate proof readiness gate`
- `e055974 Surface blocked reference scan in coord preflight`

**Metrics:**

```json
{}
```

### 2026-05-14T02:13Z — ReaderBridge/RRAPICOORD live truth repaired; fresh family candidate found

| Field | Value |
|---|---|
| Classification | `candidate-only-live-truth-repaired` |
| Target | `PID 2928 / HWND 0xC0994` |
| Candidate | `family-snapshot-hit-000001` |
| Address | `0x268D1FA6120` |
| Result | `read-only candidate; movement blocked` |
| Proof method | `RRAPICOORD repaired API truth + broad current-PID family snapshot` |
| MovementAllowed | `False` |
| MovementSent | `False` |

**What happened:** Live truth was repaired and a fresh family snapshot candidate matched read-only pose readback, but no movement-grade proof/static chain was present.

**Fast/slow pattern:** Faster than stale loops because live truth was repaired; still blocked because it lacked displacement/movement-grade proof.

**Artifacts:**
- `docs/handoffs/2026-05-14-0213-live-truth-repaired-fresh-family-snapshot.md`

**Related commits:**
- `db17e5a Repair ReaderBridge live coord marker`
- `7d6d1a5 Use RRAPICOORD for family snapshot sequences`

**Metrics:**

```json
{}
```

### 2026-05-14T12:34Z — Manual displacement runner found raw matches but valid displacement was zero

| Field | Value |
|---|---|
| Classification | `blocked-no-displacement` |
| Target | `PID 2928 / HWND 0xC0994` |
| Candidate | `api-family-hit-000001` |
| Address | `0x268E2BC09E0` |
| Result | `blocked-promotion-readiness` |
| Proof method | `two-reference route with displaced-readiness gate` |
| MovementAllowed | `False` |
| MovementSent | `False` |

**What happened:** Raw both-reference matches existed, but valid both-reference matches were zero because the displaced reference did not move enough. Promotion stayed blocked.

**Fast/slow pattern:** Important failure: fresh but non-displaced data is not proof. The blocker prevented false promotion.

**Artifacts:**
- `docs/handoffs/2026-05-14-123423-manual-displacement-runner-compact-truth.md`

**Related commits:**
- `2fb7483 Add manual displacement proof runner`
- `d940893 Gate same-pose coordinate comparisons`
- `c34f262 Document fresh no-displacement gate`

**Metrics:**

```json
{
  "rawBothReferenceMatches": 2,
  "validBothReferenceMatches": 0
}
```

### 2026-05-14T17:46:22.792929+00:00 — Current PID 16536 grouped-family displacement proof anchor

| Field | Value |
|---|---|
| Classification | `successful-proof-anchor-plus-movement` |
| Target | `PID 16536 / HWND 0x1E0D66` |
| Candidate | `snapshot-delta-21487DF8F64-xyz` |
| Address | `0x21487DF8F64` |
| Result | `current-target-proofonly-passed` |
| Proof method | `grouped family snapshot + displacement tracking + route proof + promotion batch + ProofOnly` |
| MovementAllowed | `True` |
| MovementSent | `True` |

**What happened:** The current successful recovery. Primary transform family won by displacement tracking, proof route passed, multi-pose promotion succeeded, ProofOnly passed, and a bounded Forward250 smoke moved.

**Fast/slow pattern:** Fast because it used full family groups, displacement tracking, separate baseline/displaced values, and only promoted after same-PID proof.

**Artifacts:**
- `docs/recovery/current-proof-anchor-readback.json`
- `docs/handoffs/2026-05-14-1711-current-pid-coordinate-proof-restored.md`
- `docs/recovery/current-pid-coordinate-proof-anchor-discovery-2026-05-14.html`
- `scripts/captures/family-snapshot-sequence-currentpid-16536-live-approved-threepose-20260514-122550-422022/delta-analysis/delta-summary.json`
- `scripts/captures/coordinate-proof-route-20260514-163509-016518/coordinate-proof-route.json`
- `scripts/captures/current-pid-coordinate-anchor-batch-16536-live-approved-route-20260514-163620/coordinate-anchor-batch-summary.json`
- `scripts/captures/live-test-ProofOnly-20260514-174521/run-summary.json`
- `scripts/captures/live-test-Forward250-20260514-164220/run-summary.json`

**Related commits:**
- `3c452a0 Restore current-pid coordinate proof promotion`

**Metrics:**

```json
{
  "apiPlanarDelta": 6.175614962090404,
  "memoryPlanarDelta": 6.173070231727038,
  "trackingMaxAbs": 0.006591796875,
  "baselineMaxAbsDelta": 0.06460693359372272,
  "displacedMaxAbsDelta": 0.058015136718722715,
  "supportPoseCount": 3,
  "proofSupportCount": 5,
  "forwardPlanarDistance": 0.3315185178299767
}
```

## Reusable recovery rules

1. Fresh API/runtime truth must precede memory promotion.
2. PID/HWND/process epoch matching is targeting preflight only; it is not coordinate freshness proof.
3. Grouped current-PID family snapshots are preferred over individual offset probes.
4. Rank by displacement tracking before raw single-pose delta.
5. Distinguish `MovementAllowed=true` from `MovementSent=true`.
6. Run `ProofOnly` before movement after every refresh, baseline, or promotion.
7. Archive stale proof anchors under `docs/recovery/historical/`.
8. Do not treat SavedVariables or visual evidence as live coordinate proof.

## Related commits from git search

| Commit | Subject |
| --- | --- |
| `3c452a0` | (HEAD -> main, origin/main, origin/HEAD) Restore current-pid coordinate proof promotion |
| `2fb7483` | Add manual displacement proof runner |
| `d940893` | Gate same-pose coordinate comparisons |
| `b8e1646` | Prefer route-selected coordinate candidates |
| `50a6032` | Gate coordinate promotion readiness |
| `6a4f05f` | Route coordinate center evidence safely |
| `ba1eb9d` | Harden coordinate displaced-pose tooling |
| `a346e30` | Harden coordinate scan profile workflows |
| `5697968` | Add coordinate scan profile tooling |
| `d08bf36` | Add coordinate proof route gating |
| `60cd66f` | Rank duplicate coordinate copies offline |
| `7d6d1a5` | Use RRAPICOORD for family snapshot sequences |
| `97fd6ab` | Update truth with repeat proof-pose confirmation |
| `5c32803` | Harden proof-pose reference capture |
| `db17e5a` | Repair ReaderBridge live coord marker |
| `c841da7` | Repair RRAPICOORD addon settings |
| `a79c651` | Detect disabled RRAPICOORD addon settings |
| `342562e` | Add RRAPICOORD addon state diagnostics |
| `ff3ff54` | Add RRAPICOORD scan diagnostics |
| `e055974` | Surface blocked reference scan in coord preflight |
| `20fa261` | Document coordinate root follow-up evidence |
| `38dd1c2` | Select proof-backed family candidate in milestone review |
| `84c578c` | Add coordinate proof preflight and family candidate export |
| `027d31d` | Add coordinate proof readiness gate |
| `c3732a9` | Guard stale proof anchors and select same-target candidates |
| `b507d57` | Invalidate stale proof pointer on target drift |
| `b79f745` | Rank coord parent slot container |
| `37869ea` | Rank coord owner structural signature |
| `3b38711` | Graph coord module hint chain |
| `3e252ed` | Find coord module hint occurrences |
| `7c507b1` | Rank coord parent slot module hints |
| `5445aff` | Summarize coord parent slot neighborhoods |
| `6a4be4a` | Summarize coord owner parent graph |
| `8e26191` | Trace coord candidate owner type lead |
| `104e610` | Rank repeat-stable coord readbacks |
| `787d57f` | Compare coord candidate families for navigation proof |
| `59dcbde` | Fix navigation target discovery and record proof blocker |
| `1c988d2` | Record pointer-family scan for coord cluster |
| `325ca13` | Package static code leads for coord family |
| `0ae8e58` | Refresh latest coordinate family readback |
| `34134c4` | Harden minimized x64dbg readiness for coord chain |
| `cd94266` | Rank coordinate families by displacement tracking |
| `7d9619e` | Document movement displacement blocker |
| `c00bc05` | Document high heap coordinate family leads |
| `a5aeab7` | Classify x64dbg coordinate copy probes |
| `4aafa0b` | Document unaligned coordinate recovery progress |
| `132fa64` | Recover unaligned coordinate copy evidence |
| `87e2a33` | Record PID 60628 coordinate family reacquisition |
| `c064985` | Rank coordinate families across poses |
| `32abf4e` | Prioritize coordinate family scan ranges |
| `56fff0a` | Resolve latest API coordinate by target |
| `1ab2ebc` | Import API coordinate artifacts into x64dbg planner |
| `302da88` | Add static coord pointer-chain handoff |
| `a2d3d35` | Document approved x64dbg coord access capture |
| `09aaea8` | Add x64dbg coord chain planner |
| `44fee35` | Document coordinate truth reacquisition workflow |
| `4ee32cf` | Update current proof truth for PID 57656 |
| `53397be` | Add Python stage1 proof reacquisition helper |
| `ea73ede` | Document automated movement stimulus policy |
| `539b31a` | Fix proof anchor batch promotion helper |
| `d635293` | Add proof anchor batch promotion helper |
| `963153c` | Add coordinate anchor batch reacquisition helper |
| `5f66013` | Add measured C# SendInput proof helper |
| `a99422b` | Document C# SendInput movement proof |
| `4d8d3a3` | Add PID 30992 proof recovery handoff |
| `92ed4dd` | Update current truth for PID 30992 proof recovery |
| `1bce6d1` | Refresh current proof pointer for PID 30992 |
| `d66d276` | Add current-PID coordinate family scan helper |
| `18f2d93` | Add current-PID coordinate reacquisition helper |
| `04158d8` | Skip partial RRAPICOORD markers during reference capture |
| `c119eb5` | Document restart reacquisition pre-ProofOnly state |
| `58754e8` | Update current truth with latest ProofOnly pointer refresh |
| `37db9dc` | Harden actor yaw discovery proof coordinate gate |
| `b094dc5` | Record navigation movement backend metadata |
| `d167d95` | Add native exact-HWND movement backend |
| `4818a7c` | Document coordinate freshness gate |
| `27e470f` | Harden RiftScan coordination and actor yaw readiness |
| `e7f210d` | Add visible HUD proof handoff |
| `7caff74` | Refresh coord anchor proof status |
| `b17d66e` | Add proof refresh retries to turn profiler |
