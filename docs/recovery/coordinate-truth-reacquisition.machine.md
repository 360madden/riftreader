# Coordinate Truth Reacquisition — Machine-Readable Contract

Version: v0.1.0
Scope: RiftReader / RiftScan recovery lane
Primary audience: future assistant / tooling / local scripts
Human companion: `docs/recovery/coordinate-truth-reacquisition.md`

This Markdown file is intentionally machine-oriented. The canonical payload is the JSON block below. Tools should parse only the JSON between `BEGIN_COORD_TRUTH_REACQUISITION_JSON` and `END_COORD_TRUTH_REACQUISITION_JSON`.

```json
// BEGIN_COORD_TRUTH_REACQUISITION_JSON
{
  "schemaVersion": 1,
  "documentType": "riftreader.coordinate_truth_reacquisition.machine_readable",
  "version": "v0.1.0",
  "createdUtc": "2026-05-12T00:00:00Z",
  "sourceOfTruth": {
    "repo": "C:\\RIFT MODDING\\RiftReader",
    "github": "360madden/riftreader",
    "currentProofPointer": "docs/recovery/current-proof-anchor-readback.json",
    "currentTruthMarkdown": "docs/recovery/current-truth.md",
    "driveStatusMarkdown": "G:\\My Drive\\RiftReader\\status\\RIFTREADER_CURRENT_STATUS.md",
    "driveStatusJson": "G:\\My Drive\\RiftReader\\status\\RIFTREADER_CURRENT_STATUS.json"
  },
  "currentKnownGoodExample": {
    "processName": "rift_x64",
    "processId": 57656,
    "targetWindowHandle": "0x5417BC",
    "candidateId": "api-family-hit-000001",
    "anchorAddressHex": "0xCC080EC30C",
    "promotionStatus": "validated",
    "assertStatus": "valid",
    "assertMovementAllowed": true,
    "proofOnlyStatus": "passed-proof-only",
    "proofOnlyOk": true,
    "proofOnlyMovementSent": false,
    "proofOnlyMovementAttempted": false,
    "currentCoordinate": {
      "x": 7407.42919921875,
      "y": 871.8069458007812,
      "z": 3030.127685546875,
      "recordedAtUtc": "2026-05-12T11:10:56.4345281Z"
    },
    "finalTruthCommit": "4ee32cf682639e58a1e6c0ae81121f1143de470d"
  },
  "stateMachine": [
    {
      "id": "preflight_repo",
      "description": "Verify local repo state before live work.",
      "requiredInputs": [
        "repoRoot"
      ],
      "commands": [
        "git status --short",
        "git rev-parse HEAD",
        "git ls-remote origin refs/heads/main"
      ],
      "successCriteria": [
        "working tree clean",
        "local HEAD equals remote main or can fast-forward"
      ],
      "failureAction": "stop; inspect git status; do not run live recovery"
    },
    {
      "id": "stage1_reacquire",
      "description": "Resolve target, visual gate, family scan, and movement-stimulus proof poses.",
      "primaryCommand": "\"C:\\Users\\mrkoo\\AppData\\Local\\Programs\\Python\\Python314\\python.exe\" \"scripts\\riftreader_postupdate_proof_reacquire_stage1.py\" --visual-full --allow-movement-stimulus --json",
      "successCriteria": [
        "status == promotion-candidate-found",
        "ok == true",
        "candidateJsonl exists",
        "batchStatus == promotion-candidate-found"
      ],
      "outputs": [
        "stage1-python-summary.json",
        "coordinate-anchor-batch-summary.json",
        "api-family-vec3-candidates.jsonl"
      ]
    },
    {
      "id": "promote_anchor",
      "description": "Promote multi-pose coordinate evidence into telemetry-proof-coord-anchor.json.",
      "primaryTools": [
        "scripts/promote-riftscan-reference-match-to-proof-anchor.ps1",
        "scripts/assert-current-proof-coord-anchor-readback.ps1"
      ],
      "successCriteria": [
        "promotionStatus == validated",
        "assertStatus == valid",
        "assertMovementAllowed == true"
      ],
      "failureAction": "do not run ProofOnly; inspect readback summaries"
    },
    {
      "id": "proofonly",
      "description": "Run same-target ProofOnly to validate and refresh current proof pointer.",
      "primaryCommandTemplate": "\"C:\\Users\\mrkoo\\AppData\\Local\\Programs\\Python\\Python314\\python.exe\" \"scripts\\live_test.py\" --profile ProofOnly --pid <PID> --hwnd <HWND> --process-name rift_x64 --no-gui",
      "successCriteria": [
        "status == passed-proof-only",
        "ok == true",
        "movementSent == false",
        "movementAttempted == false",
        "currentProofPointerUpdate.updated == true"
      ],
      "outputs": [
        "docs/recovery/current-proof-anchor-readback.json",
        "proof-anchor-currentpid-<pid>-readback-summary-*.json"
      ]
    },
    {
      "id": "finalize_truth",
      "description": "Update truth/handoff/Drive status and commit explicit files.",
      "successCriteria": [
        "current-truth updated",
        "current handoff updated",
        "remote SHA verified"
      ],
      "commitFiles": [
        "docs/recovery/current-proof-anchor-readback.json",
        "docs/recovery/current-truth.md",
        "docs/recovery/historical/current-proof-anchor-readback-*.json",
        "handoffs/current/RIFTREADER_CURRENT_HANDOFF.md",
        "handoffs/current/RIFTREADER_CURRENT_HANDOFF.json",
        "handoffs/current/live-return-proof-recovered/*"
      ],
      "forbidden": [
        "git add .",
        "capture directory commit without explicit request"
      ]
    }
  ],
  "toolInventory": {
    "pythonControlPlane": [
      "scripts/riftreader_postupdate_proof_reacquire_stage1.py",
      "scripts/live_test.py",
      "scripts/test_riftreader_postupdate_proof_reacquire_stage1.py"
    ],
    "visualGate": [
      "scripts/check_live_visual_gate.py",
      "scripts/rift_live_test/visual_gate_status.py",
      "tools/rift-game-mcp/helpers/window-tools.ps1"
    ],
    "coordinateFamily": [
      "scripts/scan_current_pid_coordinate_family.py",
      "scripts/capture_current_pid_coordinate_family_snapshot.py",
      "scripts/capture_x64dbg_coord_copy_probe_batch.py",
      "scripts/capture-rift-api-reference-coordinate.ps1",
      "scripts/invoke-riftscan-coordinate-readback.ps1",
      "scripts/capture-riftscan-proof-pose.ps1"
    ],
    "movementStimulus": [
      "scripts/reacquire-current-pid-coordinate-anchor-batch.ps1",
      "scripts/send-rift-key-csharp.ps1"
    ],
    "promotion": [
      "scripts/promote-riftscan-reference-match-to-proof-anchor.ps1",
      "scripts/assert-current-proof-coord-anchor-readback.ps1"
    ],
    "transitionalDownloadsHelpersRecommendedForRepoOwnership": [
      "riftreader-promote-stage1-and-proofonly-v0.1.0.py",
      "riftreader-finalize-proofonly-truth-v0.1.0.py"
    ]
  },
  "artifactPatterns": {
    "stage1RunDir": "scripts/captures/postupdate-proof-reacquire-stage1-python-<UTC>",
    "familyScanDir": "scripts/captures/family-scan-currentpid-<pid>-<timestamp>",
    "batchSummary": "scripts/captures/postupdate-proof-reacquire-stage1-python-<UTC>/coordinate-anchor-batch/coordinate-anchor-batch-summary.json",
    "promotionSummary": "scripts/captures/promote-stage1-and-proofonly-<UTC>/promote-stage1-and-proofonly-summary.json",
    "proofOnlyRunDir": "scripts/captures/live-test-ProofOnly-<timestamp>",
    "proofReadbackSummary": "scripts/captures/proof-anchor-currentpid-<pid>-readback-summary-*.json"
  },
  "safetyPolicy": {
    "cheatEngineAllowedByDefault": false,
    "savedVariablesLiveTruthAllowed": false,
    "oldPidHwndPointerReuseAllowed": false,
    "movementStimulusAllowed": "only when visual gate passes and fresh coordinate truth is captured before/after",
    "navigationMovementAllowed": "only after separate navigation proof gates",
    "truthUpdateAllowed": "only after promotion + assert + same-target ProofOnly pass",
    "githubConnectorWritesAllowed": false,
    "localGitWritesAllowed": true
  },
  "candidateOnlyDiscoveries": [
    {
      "dateUtc": "2026-05-13",
      "targetEpoch": {
        "processName": "rift_x64",
        "processId": 60628,
        "targetWindowHandle": "0xCE0FCE",
        "processStartTimeUtc": "2026-05-13T04:53:58.081190Z",
        "moduleBaseAddressHex": "0x7FF796B50000"
      },
      "status": "candidate-only-not-promoted",
      "discovery": "freshest current coordinate copies in the 0x1FF07570000 family can be unaligned",
      "requiredScanOption": "--scan-stride 1",
      "bestObservedUnalignedCopy": {
        "addressHex": "0x1FF07575346",
        "value": [7406.1318359375, 871.7725830078125, 3028.77099609375],
        "reference": [7406.1299, 871.77, 3028.77],
        "maxAbsDelta": 0.00258300781251819,
        "artifact": "scripts/captures/family-scan-currentpid-60628-20260513-061422/family-scan-summary.json"
      },
      "staleObservedUnalignedCopy": {
        "addressHex": "0x1FF0757215A",
        "duplicateAddressHex": "0x1FF07572183",
        "priorValue": [7411.95458984375, 871.8436279296875, 3031.310546875],
        "priorReference": [7411.9497, 871.84, 3031.3098],
        "priorMaxAbsDelta": 0.004889843749879219,
        "currentSnapshotDeltaApprox": 5.8247
      },
      "x64dbgLead": {
        "caller": "rift_x64.exe+0x47D533",
        "returnAddress": "rift_x64.exe+0x47D538",
        "copyInstruction": "VCRUNTIME140.dll+0x113F8 vmovdqu ymmword ptr ds:[rcx+r9*1-0x40], ymm1",
        "sourceBufferRuleAtHit": "rdx=0x1FF6D600020; coordinate offset rdx+0x28 in coordinate-copy/read contexts",
        "confirmedSourceTriplets": [
          {
            "artifact": "scripts/captures/x64dbg-live-access-capture-20260513-060024-938838/summary.json",
            "sourceAddressHex": "0x1FF6D600020",
            "sourceOffsetHex": "0x28",
            "value": [7406.6005859375, 871.7725830078125, 3028.814208984375]
          },
          {
            "artifact": "scripts/captures/x64dbg-live-access-capture-20260513-060104-964476/summary.json",
            "sourceAddressHex": "0x1FF6D600020",
            "sourceOffsetHex": "0x28",
            "value": [7406.1318359375, 871.7725830078125, 3028.77099609375]
          }
        ]
      },
      "latestBroadSnapshot": {
        "artifact": "scripts/captures/coordinate-family-snapshot-currentpid-60628-20260513-061344/family-snapshot-summary.json",
        "tripletCount": 97,
        "nearReferenceTripletCount": 9,
        "bestCurrentTriplet": "0x1FF07575346"
      },
      "highHeapFamilyReview": {
        "artifact": "scripts/captures/high-heap-coordinate-family-review-currentpid-60628-20260513-0637/summary.json",
        "candidateCount": 53,
        "familyCount": 24,
        "bestExactValue": [7406.1298828125, 871.7699584960938, 3028.77001953125],
        "bestMaxAbsDelta": 0.000041503906231810106,
        "status": "candidate-only-needs-displaced-pose-ranking"
      },
      "displacedPoseBlocker": {
        "artifact": "scripts/captures/movement-stimulus-displacement-check-currentpid-60628-20260513-0642/summary.json",
        "status": "blocked-no-displaced-pose",
        "cleanLowercaseForwardKeySent": true,
        "targetForeground": true,
        "referenceChanged": false,
        "recommendedAction": "manual-displacement-or-visual-state-diagnosis-before-more-movement"
      },
      "copyPathDisassembly": {
        "function": "rift_x64.exe+0x47D408",
        "ownerRegister": "rdi=rcx",
        "destinationRule": "r15=rdi+0x50; r12=[r15]+[rdi+0x94]+[rdi+0x9c]",
        "sourceRule": "r14=[rdi]; rdx=[r14]",
        "interpretation": "heap/ring copy routine, not yet a static player-coordinate chain"
      },
      "latestPointerScan": {
        "artifact": "scripts/captures/pointer-family-scan-20260513-061835-695118/summary.json",
        "depth": 4,
        "scannedTargetCount": 25,
        "staticModuleHits": 0,
        "status": "heap-only-no-static-chain"
      },
      "x64dbgBatchClassifier": {
        "script": "scripts/capture_x64dbg_coord_copy_probe_batch.py",
        "purpose": "reject noisy page-access hits while preserving bounded detach-per-attempt captures",
        "liveArtifacts": [
          "scripts/captures/x64dbg-coord-copy-batch-60628-20260513-060709-057382/summary.json",
          "scripts/captures/x64dbg-coord-copy-batch-60628-20260513-060845-059022/summary.json"
        ]
      },
      "handoff": "docs/handoffs/2026-05-13-0539-currentpid-60628-unaligned-coordinate-copy-truth.md",
      "commitBaseline": "4aafa0b"
    }
  ],
  "timing": {
    "afterCharacterInWorldCoordinateTruthReacquisitionMinutes": "7-12",
    "doesInclude": [
      "target resolution",
      "visual gate",
      "coordinate family scan",
      "movement-stimulus proof poses",
      "promotion",
      "assert readback",
      "same-target ProofOnly"
    ],
    "doesNotInclude": [
      "patch/login/load time",
      "focus/capture repair",
      "yaw recovery",
      "route smoke",
      "navigation validation",
      "auto-turn validation"
    ]
  },
  "nextNavigationFamiliesAfterCoordinateProof": [
    "actor_yaw_body_facing",
    "forward_vector_or_heading_vector",
    "velocity_movement_vector",
    "movement_control_flags",
    "zone_map_context_identity"
  ]
}
// END_COORD_TRUTH_REACQUISITION_JSON
```

## END_OF_DOCUMENT_MARKER
