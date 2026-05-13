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
      "status": "candidate-only-not-promoted-live-work-blocked-by-nonresponsive-target",
      "latestResponsivePreflight": "scripts/captures/x64dbg-target-preflight-20260513-072034-846093/summary.json",
      "currentBlocker": {
        "artifact": "scripts/captures/x64dbg-target-preflight-20260513-072327-946499/summary.json",
        "status": "blocked",
        "blockers": [
          "selected-target-not-responding"
        ],
        "debuggerProcessCount": 0,
        "movementAllowed": false,
        "x64dbgAllowed": false
      },
      "movementInputFinding": {
        "virtualKeyWWorks": true,
        "scanCodeWLowSignal": true,
        "artifacts": [
          {
            "artifact": "scripts/captures/csharp-sendinput-current-virtualkey-w-currentpid-60628-20260513-025312/measured-result.json",
            "planarDisplacement": 0.4616189445850858
          },
          {
            "artifact": "scripts/captures/csharp-sendinput-current-virtualkey-w-thirdpose-currentpid-60628-20260513-031727/measured-result.json",
            "planarDisplacement": 0.37082363732641205
          }
        ]
      },
      "rankingUpdate": {
        "script": "scripts/rift_live_test/coordinate_family_rank.py",
        "behavior": "rank exact addresses and families by displacement tracking error before raw delta tie-breakers",
        "artifact": "scripts/captures/coordinate-family-rank-currentpid-60628-threepose-tracking-20260513-032001-311/coordinate-family-rankings.json",
        "topExactCandidate": {
          "addressHex": "0x1FF08502BC8",
          "supportPoseCount": 3,
          "trackMaxAbsError": 0.004333593749834108,
          "avgBestMaxAbsDistance": 0.003232356770846915,
          "observedValues": [
            [
              7406.1318359375,
              871.7725830078125,
              3028.77099609375
            ],
            [
              7406.58740234375,
              871.7725830078125,
              3028.8134765625
            ],
            [
              7407.099609375,
              871.7734375,
              3028.86181640625
            ]
          ]
        },
        "topFamilyCandidate": {
          "familyBaseHex": "0x1FF94EC0000",
          "supportPoseCount": 3,
          "trackMaxAbsError": 6.0937500165891834e-05,
          "avgBestMaxAbsDistance": 4.225260424088143e-05,
          "movingSlots": [
            "0x1FF94EC8B80",
            "0x1FF94EC8DC0",
            "0x1FF94EC93D0"
          ]
        },
        "destinationFamilyCandidate": {
          "familyBaseHex": "0x1FF07570000",
          "supportPoseCount": 3,
          "requiresScanStride": 1,
          "latestThirdPoseBest": "0x1FF07574839",
          "artifact": "scripts/captures/family-scan-currentpid-60628-20260513-071936-092676/family-scan-summary.json"
        },
        "demotedFamilies": [
          "0x1FF392C0000",
          "0x1FF40660000",
          "0x1FF841D0000"
        ]
      },
      "scanRunDirectoryFix": {
        "script": "scripts/scan_current_pid_coordinate_family.py",
        "fix": "utc_stamp includes microseconds to prevent grouped scan directory collisions",
        "test": "scripts/test_scan_current_pid_coordinate_family.py"
      },
      "latestX64dbgAccessHit": {
        "artifact": "scripts/captures/x64dbg-live-access-capture-20260513-072035-091117/summary.json",
        "candidateAddressHex": "0x1FF08502BC8",
        "ripHex": "0x7FF7970CC2B5",
        "moduleOffset": "rift_x64.exe+0x57C2B5",
        "instruction": "cmp qword ptr ds:[rcx+0x10], 0x00",
        "candidateRelation": "candidate at rcx+0x2F8",
        "interpretation": "candidate-only UI/scene-object-like metadata context, not static player-coordinate proof",
        "detachSucceeded": true
      },
      "latestPointerScan": {
        "artifact": "scripts/captures/pointer-family-scan-20260513-070942-089639/summary.json",
        "seedCount": 14,
        "scannedTargetCount": 67,
        "staticModuleHits": 0,
        "riftModuleHits": 0,
        "status": "heap-only-no-static-chain"
      },
      "nonPromotionList": [
        "0x1FF08502BC8",
        "0x1FF94EC0000",
        "0x1FF94EC93D0",
        "0x1FF07574839",
        "0x1FF07575346",
        "0x1FF6D600020",
        "0x1FF65FADE88",
        "0x1FF392C0000",
        "0x1FF40660000",
        "0x1FF841D0000"
      ],
      "handoff": "docs/handoffs/2026-05-13-0729-currentpid-60628-threepose-candidate-blocker.md",
      "lastPushedBaselineBeforeThisUpdate": "7d9619e"
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
