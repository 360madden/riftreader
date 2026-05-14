---
schemaVersion: 1
mode: riftreader-historical-coordinate-proof-anchor-discovery-timelines
generatedAtUtc: 2026-05-14T18:22:13Z
---

# Machine-readable historical coordinate proof-anchor discovery timelines

```json
{
  "schemaVersion": 1,
  "mode": "riftreader-historical-coordinate-proof-anchor-discovery-timelines",
  "generatedAtUtc": "2026-05-14T18:22:13Z",
  "repoRoot": "C:\\RIFT MODDING\\RiftReader",
  "outputFiles": {
    "humanHtml": "docs\\recovery\\historical-coordinate-proof-anchor-discovery-timelines-2026-05.html",
    "humanMarkdown": "docs\\recovery\\historical-coordinate-proof-anchor-discovery-timelines-2026-05.md",
    "machineMarkdown": "docs\\recovery\\historical-coordinate-proof-anchor-discovery-timelines-2026-05.machine.md"
  },
  "summary": {
    "attemptCount": 10,
    "successfulAttemptCount": 4,
    "blockedAttemptCount": 2,
    "candidateOrPartialCount": 3,
    "latestCurrentAnchor": {
      "candidateId": "snapshot-delta-21487DF8F64-xyz",
      "address": "0x21487DF8F64",
      "target": {
        "processName": "rift_x64",
        "processId": 16536,
        "targetWindowHandle": "0x1E0D66"
      },
      "status": "current-target-proofonly-passed",
      "latestProofOnly": {
        "runSummaryFile": "C:\\RIFT MODDING\\RiftReader\\scripts\\captures\\live-test-ProofOnly-20260514-174521\\run-summary.json",
        "status": "passed-proof-only",
        "generatedAtUtc": "2026-05-14T17:46:22.783527+00:00",
        "movementSent": false,
        "movementAttempted": false,
        "currentCoordinate": {
          "x": 7404.44091796875,
          "y": 871.7135009765625,
          "z": 3028.63232421875,
          "recordedAtUtc": "2026-05-14T17:46:22.1910144Z"
        },
        "coordinateDelta": null,
        "readbackSummaryFile": "C:\\RIFT MODDING\\RiftReader\\scripts\\captures\\proof-anchor-currentpid-16536-readback-summary-20260514-134617.json"
      }
    }
  },
  "attempts": [
    {
      "id": "api-first-scaffold-2026-05-01",
      "date": "2026-05-01",
      "class": "foundation",
      "title": "API-first coordinate reacquisition scaffold",
      "target": "current target at that time; session-specific",
      "candidate": "none promoted",
      "address": null,
      "result": "foundation-success",
      "movementAllowed": false,
      "movementSent": false,
      "proofMethod": "RRAPICOORD1 / Inspect.Unit.Detail player API truth scaffold",
      "summary": "Moved recovery away from stale SavedVariables and old memory addresses. Established live API/runtime coordinate truth as the starting surface.",
      "whyFastOrSlow": "Faster future recovery because a live truth surface exists before memory scans.",
      "artifacts": [
        "memory: MEMORY.md lines 554-562",
        "rollout 019de4cc-afbb-7060-8d43-d02797959dd9"
      ],
      "commits": []
    },
    {
      "id": "no-ce-multipose-bridge-2026-05-06",
      "date": "2026-05-06",
      "class": "successful-proof-anchor-foundation",
      "title": "No-CE multi-pose promotion bridge",
      "target": "stale trace rejected; current PID/HWND revalidated during run",
      "candidate": "reference-scored candidates",
      "address": null,
      "result": "workflow-success",
      "movementAllowed": null,
      "movementSent": false,
      "proofMethod": "no-ce-riftscan-reference-multisample promotion bridge",
      "summary": "Built the strict path that turns reference-scored candidates into movement-gate compatible proof anchors without Cheat Engine.",
      "whyFastOrSlow": "Fast separator: stale trace anchors were rejected before work continued; proof stayed no-CE and current-PID.",
      "artifacts": [
        "memory: MEMORY.md lines 564-582",
        "rollout 019dfcf2-aebd-7153-bed0-a3441cdf3635"
      ],
      "commits": [
        "b42578a Add no-CE RiftScan proof anchor workflow"
      ]
    },
    {
      "id": "direct-no-input-proof-2026-05-06",
      "date": "2026-05-06T14:42:59Z",
      "class": "successful-proof-anchor",
      "title": "Direct no-input current-PID proof artifact",
      "target": "PID 47560 / HWND 0x2122E",
      "candidate": "api-probe-triplet-000007",
      "address": "0x2400EA32120",
      "result": "valid",
      "movementAllowed": true,
      "movementSent": false,
      "proofMethod": "cache",
      "summary": "Recorded stable no-input proof readback against the current PID. This is a historical proof anchor, now stale for current process epochs.",
      "whyFastOrSlow": "Fast because it used direct current-PID readback, stable samples, no movement, and no CE.",
      "artifacts": [
        "scripts/captures/proof-anchor-currentpid-47560-readback-summary-20260506-144259.json"
      ],
      "commits": [
        "17ede2e referenced in memory as no-input proof/handoff commit"
      ],
      "metrics": {
        "decodedSampleCount": 12,
        "stableAcrossReadbackSamples": true,
        "readbackFailures": 0,
        "regionAddress": "0x2400EA320E0",
        "candidateOffsetInRegion": 64
      }
    },
    {
      "id": "riftscan-first-proof-anchor-2026-05-07",
      "date": "2026-05-06T23:31:10-04:00 / 2026-05-07T03:31:10Z",
      "class": "successful-proof-anchor-plus-movement",
      "title": "RiftScan-first proof anchor plus forward smoke",
      "target": "PID 47560 / HWND 0x2122E",
      "candidate": "rift-addon-coordinate-candidate-000001",
      "address": "0x2400EA32120",
      "result": "proof-gated movement passed",
      "movementAllowed": true,
      "movementSent": true,
      "proofMethod": "no-ce-riftscan-reference-multisample",
      "summary": "RiftScan candidate was imported, validated against live reference readback, promoted into telemetry-proof-coord-anchor, then a proof-gated 1000 ms W pulse moved planar distance 1.2391483387792066.",
      "whyFastOrSlow": "Fast because RiftScan was treated as the candidate source and RiftReader stayed the proof/movement gate.",
      "artifacts": [
        "docs/handoffs/2026-05-06-233226-riftscan-first-proof-anchor-resume-handoff.md",
        "C:\\RIFT MODDING\\Riftscan\\reports\\generated\\codex-current-coord-region-passive-20260506-230940-addon-coordinate-matches.json"
      ],
      "commits": [
        "114a5dd Use RiftScan coordinate candidates for proof anchor",
        "7e34ded Add RiftScan proof anchor resume handoff"
      ],
      "metrics": {
        "support": 3,
        "bestMaxAbsDistance": 0,
        "forwardPulseMs": 1000,
        "planarDistance": 1.2391483387792066
      }
    },
    {
      "id": "refreshbaseline-proofonly-needed-2026-05-08",
      "date": "2026-05-08T04:53Z",
      "class": "partial-success-proof-baseline",
      "title": "RefreshBaseline captured displaced proof pose; ProofOnly still required",
      "target": "PID 33912 / HWND 0xE0DB2",
      "candidate": "rift-addon-coordinate-candidate-000001",
      "address": "0x202FEA3E180",
      "result": "baseline captured; movement still blocked",
      "movementAllowed": false,
      "movementSent": false,
      "proofMethod": "RefreshBaseline / proof baseline pool",
      "summary": "Captured a displaced current-session proof pose about 3.023m from the prior blocked ProofOnly coordinate. This was useful evidence but not movement permission until ProofOnly reran.",
      "whyFastOrSlow": "Avoided false movement by separating baseline capture from ProofOnly. Slower because final proof gate was still pending.",
      "artifacts": [
        "docs/handoffs/2026-05-08-005330-post-refreshbaseline-proofonly-needed-handoff.md"
      ],
      "commits": [
        "0402eb1 Harden live proof resume handoff",
        "5051df0 Harden live-test HUD orchestration"
      ],
      "metrics": {
        "planarDisplacementFromPriorBlockedProof": 3.023,
        "referenceMatchCount": 1,
        "stableDecodedCandidateCount": 1
      }
    },
    {
      "id": "pid60628-threepose-candidate-2026-05-13",
      "date": "2026-05-13T07:29Z / 2026-05-13T16:31Z",
      "class": "strong-candidate-only",
      "title": "PID 60628 three-pose candidates and static-chain blocker",
      "target": "PID 60628 / HWND 0xCE0FCE",
      "candidate": "0x1FF08502BC8 exact; 0x1FF94EC0000 family",
      "address": "0x1FF08502BC8",
      "result": "candidate-only; live target later nonresponsive",
      "movementAllowed": false,
      "movementSent": true,
      "proofMethod": "grouped-family scan, displacement-aware ranking, x64dbg evidence",
      "summary": "Three-pose ranking produced strong heap candidates, but no module/static chain was proven and the target became nonresponsive. Do not promote PID 60628 addresses.",
      "whyFastOrSlow": "Useful pattern discovery but slow as a recovery path because static owner/source was not proven and target health failed.",
      "artifacts": [
        "docs/handoffs/2026-05-13-0729-currentpid-60628-threepose-candidate-blocker.md",
        "docs/handoffs/2026-05-13-1231-compact-static-pointer-chain-resume.md"
      ],
      "commits": [
        "cd94266 Rank coordinate families by displacement tracking",
        "87e2a33 Record PID 60628 coordinate family reacquisition",
        "c064985 Rank coordinate families across poses"
      ],
      "metrics": {
        "bestExactTrackMaxError": 0.004333593749834108,
        "bestFamilyTrackMaxError": 6.0937500165891834e-05,
        "sendInputPlanarDeltas": [
          0.4616189445850858,
          0.37082363732641205
        ]
      }
    },
    {
      "id": "pid2928-readiness-blocker-2026-05-13",
      "date": "2026-05-13T20:26 EDT",
      "class": "blocked-readiness",
      "title": "Coordinate proof readiness gate blocked stale/freshness mismatch",
      "target": "PID 2928 / HWND 0xC0994",
      "candidate": "0x268DF21ED20 chain candidate",
      "address": "0x268DF21ED20",
      "result": "blocked-coordinate-proof-readiness",
      "movementAllowed": false,
      "movementSent": false,
      "proofMethod": "reference freshness watchdog + milestone review gate",
      "summary": "A same-target candidate existed, but fresh reference truth was unavailable, so proof/readback and movement were blocked.",
      "whyFastOrSlow": "Slow/blocked because candidate presence was correctly not treated as proof without API-now truth.",
      "artifacts": [
        "docs/handoffs/2026-05-13-2026-coordinate-proof-readiness-gate.md"
      ],
      "commits": [
        "027d31d Add coordinate proof readiness gate",
        "e055974 Surface blocked reference scan in coord preflight"
      ]
    },
    {
      "id": "pid2928-rrapi-repaired-2026-05-14",
      "date": "2026-05-14T02:13Z",
      "class": "candidate-only-live-truth-repaired",
      "title": "ReaderBridge/RRAPICOORD live truth repaired; fresh family candidate found",
      "target": "PID 2928 / HWND 0xC0994",
      "candidate": "family-snapshot-hit-000001",
      "address": "0x268D1FA6120",
      "result": "read-only candidate; movement blocked",
      "movementAllowed": false,
      "movementSent": false,
      "proofMethod": "RRAPICOORD repaired API truth + broad current-PID family snapshot",
      "summary": "Live truth was repaired and a fresh family snapshot candidate matched read-only pose readback, but no movement-grade proof/static chain was present.",
      "whyFastOrSlow": "Faster than stale loops because live truth was repaired; still blocked because it lacked displacement/movement-grade proof.",
      "artifacts": [
        "docs/handoffs/2026-05-14-0213-live-truth-repaired-fresh-family-snapshot.md"
      ],
      "commits": [
        "db17e5a Repair ReaderBridge live coord marker",
        "7d6d1a5 Use RRAPICOORD for family snapshot sequences"
      ]
    },
    {
      "id": "pid2928-no-displacement-blocker-2026-05-14",
      "date": "2026-05-14T12:34Z",
      "class": "blocked-no-displacement",
      "title": "Manual displacement runner found raw matches but valid displacement was zero",
      "target": "PID 2928 / HWND 0xC0994",
      "candidate": "api-family-hit-000001",
      "address": "0x268E2BC09E0",
      "result": "blocked-promotion-readiness",
      "movementAllowed": false,
      "movementSent": false,
      "proofMethod": "two-reference route with displaced-readiness gate",
      "summary": "Raw both-reference matches existed, but valid both-reference matches were zero because the displaced reference did not move enough. Promotion stayed blocked.",
      "whyFastOrSlow": "Important failure: fresh but non-displaced data is not proof. The blocker prevented false promotion.",
      "artifacts": [
        "docs/handoffs/2026-05-14-123423-manual-displacement-runner-compact-truth.md"
      ],
      "commits": [
        "2fb7483 Add manual displacement proof runner",
        "d940893 Gate same-pose coordinate comparisons",
        "c34f262 Document fresh no-displacement gate"
      ],
      "metrics": {
        "rawBothReferenceMatches": 2,
        "validBothReferenceMatches": 0
      }
    },
    {
      "id": "pid16536-current-success-2026-05-14",
      "date": "2026-05-14T17:46:22.792929+00:00",
      "class": "successful-proof-anchor-plus-movement",
      "title": "Current PID 16536 grouped-family displacement proof anchor",
      "target": "PID 16536 / HWND 0x1E0D66",
      "candidate": "snapshot-delta-21487DF8F64-xyz",
      "address": "0x21487DF8F64",
      "result": "current-target-proofonly-passed",
      "movementAllowed": true,
      "movementSent": true,
      "proofMethod": "grouped family snapshot + displacement tracking + route proof + promotion batch + ProofOnly",
      "summary": "The current successful recovery. Primary transform family won by displacement tracking, proof route passed, multi-pose promotion succeeded, ProofOnly passed, and a bounded Forward250 smoke moved.",
      "whyFastOrSlow": "Fast because it used full family groups, displacement tracking, separate baseline/displaced values, and only promoted after same-PID proof.",
      "artifacts": [
        "docs/recovery/current-proof-anchor-readback.json",
        "docs/handoffs/2026-05-14-1711-current-pid-coordinate-proof-restored.md",
        "docs/recovery/current-pid-coordinate-proof-anchor-discovery-2026-05-14.html",
        "scripts/captures/family-snapshot-sequence-currentpid-16536-live-approved-threepose-20260514-122550-422022/delta-analysis/delta-summary.json",
        "scripts/captures/coordinate-proof-route-20260514-163509-016518/coordinate-proof-route.json",
        "scripts/captures/current-pid-coordinate-anchor-batch-16536-live-approved-route-20260514-163620/coordinate-anchor-batch-summary.json",
        "scripts/captures/live-test-ProofOnly-20260514-174521/run-summary.json",
        "scripts/captures/live-test-Forward250-20260514-164220/run-summary.json"
      ],
      "commits": [
        "3c452a0 Restore current-pid coordinate proof promotion"
      ],
      "metrics": {
        "apiPlanarDelta": 6.175614962090404,
        "memoryPlanarDelta": 6.173070231727038,
        "trackingMaxAbs": 0.006591796875,
        "baselineMaxAbsDelta": 0.06460693359372272,
        "displacedMaxAbsDelta": 0.058015136718722715,
        "supportPoseCount": 3,
        "proofSupportCount": 5,
        "forwardPlanarDistance": 0.3315185178299767
      }
    }
  ],
  "commits": {
    "coordinateProofAnchorSearch": "3c452a0 (HEAD -> main, origin/main, origin/HEAD) Restore current-pid coordinate proof promotion\n2fb7483 Add manual displacement proof runner\nd940893 Gate same-pose coordinate comparisons\nb8e1646 Prefer route-selected coordinate candidates\n50a6032 Gate coordinate promotion readiness\n6a4f05f Route coordinate center evidence safely\nba1eb9d Harden coordinate displaced-pose tooling\na346e30 Harden coordinate scan profile workflows\n5697968 Add coordinate scan profile tooling\nd08bf36 Add coordinate proof route gating\n60cd66f Rank duplicate coordinate copies offline\n7d6d1a5 Use RRAPICOORD for family snapshot sequences\n97fd6ab Update truth with repeat proof-pose confirmation\n5c32803 Harden proof-pose reference capture\ndb17e5a Repair ReaderBridge live coord marker\nc841da7 Repair RRAPICOORD addon settings\na79c651 Detect disabled RRAPICOORD addon settings\n342562e Add RRAPICOORD addon state diagnostics\nff3ff54 Add RRAPICOORD scan diagnostics\ne055974 Surface blocked reference scan in coord preflight\n20fa261 Document coordinate root follow-up evidence\n38dd1c2 Select proof-backed family candidate in milestone review\n84c578c Add coordinate proof preflight and family candidate export\n027d31d Add coordinate proof readiness gate\nc3732a9 Guard stale proof anchors and select same-target candidates\nb507d57 Invalidate stale proof pointer on target drift\nb79f745 Rank coord parent slot container\n37869ea Rank coord owner structural signature\n3b38711 Graph coord module hint chain\n3e252ed Find coord module hint occurrences\n7c507b1 Rank coord parent slot module hints\n5445aff Summarize coord parent slot neighborhoods\n6a4be4a Summarize coord owner parent graph\n8e26191 Trace coord candidate owner type lead\n104e610 Rank repeat-stable coord readbacks\n787d57f Compare coord candidate families for navigation proof\n59dcbde Fix navigation target discovery and record proof blocker\n1c988d2 Record pointer-family scan for coord cluster\n325ca13 Package static code leads for coord family\n0ae8e58 Refresh latest coordinate family readback\n34134c4 Harden minimized x64dbg readiness for coord chain\ncd94266 Rank coordinate families by displacement tracking\n7d9619e Document movement displacement blocker\nc00bc05 Document high heap coordinate family leads\na5aeab7 Classify x64dbg coordinate copy probes\n4aafa0b Document unaligned coordinate recovery progress\n132fa64 Recover unaligned coordinate copy evidence\n87e2a33 Record PID 60628 coordinate family reacquisition\nc064985 Rank coordinate families across poses\n32abf4e Prioritize coordinate family scan ranges\n56fff0a Resolve latest API coordinate by target\n1ab2ebc Import API coordinate artifacts into x64dbg planner\n302da88 Add static coord pointer-chain handoff\na2d3d35 Document approved x64dbg coord access capture\n09aaea8 Add x64dbg coord chain planner\n44fee35 Document coordinate truth reacquisition workflow\n4ee32cf Update current proof truth for PID 57656\n53397be Add Python stage1 proof reacquisition helper\nea73ede Document automated movement stimulus policy\n539b31a Fix proof anchor batch promotion helper\nd635293 Add proof anchor batch promotion helper\n963153c Add coordinate anchor batch reacquisition helper\n5f66013 Add measured C# SendInput proof helper\na99422b Document C# SendInput movement proof\n4d8d3a3 Add PID 30992 proof recovery handoff\n92ed4dd Update current truth for PID 30992 proof recovery\n1bce6d1 Refresh current proof pointer for PID 30992\nd66d276 Add current-PID coordinate family scan helper\n18f2d93 Add current-PID coordinate reacquisition helper\n04158d8 Skip partial RRAPICOORD markers during reference capture\nc119eb5 Document restart reacquisition pre-ProofOnly state\n58754e8 Update current truth with latest ProofOnly pointer refresh\n37db9dc Harden actor yaw discovery proof coordinate gate\nb094dc5 Record navigation movement backend metadata\nd167d95 Add native exact-HWND movement backend\n4818a7c Document coordinate freshness gate\n27e470f Harden RiftScan coordination and actor yaw readiness\ne7f210d Add visible HUD proof handoff\n7caff74 Refresh coord anchor proof status\nb17d66e Add proof refresh retries to turn profiler",
    "proofAnchorSearch": "c3732a9 Guard stale proof anchors and select same-target candidates\n539b31a Fix proof anchor batch promotion helper\nd635293 Add proof anchor batch promotion helper\n7e34ded Add RiftScan proof anchor resume handoff\n114a5dd Use RiftScan coordinate candidates for proof anchor\nb42578a Add no-CE RiftScan proof anchor workflow\n8d39d37 Add candidate facing and proof anchor normalization tests\nb883fb2 Short-circuit proof anchor refresh from cached anchor"
  },
  "lessons": [
    "Fresh API/runtime truth must precede memory promotion.",
    "PID/HWND/process epoch matching is targeting preflight only, not coordinate freshness proof.",
    "Grouped current-PID family snapshots beat narrow offset probes.",
    "Displacement tracking is the main separator between real anchors and dense/cached copies.",
    "MovementAllowed and MovementSent must be reported separately.",
    "ProofOnly is required before movement after refresh/baseline/promotion.",
    "Stale proof anchors belong under docs/recovery/historical/ and must not pollute current truth."
  ]
}
```
