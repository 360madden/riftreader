# Ghidra facing/coordinate source-site review — 2026-06-01

## Verdict

The latest evidence supports a stable static owner-root chain for the
candidate-facing target:

`[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314`

Yaw is derived from that facing target and the promoted coordinate resolver:

`atan2(owner+0x314 - owner+0x328, owner+0x30C - owner+0x320)`

This is **supporting evidence only**. It is enough for an explicit
promotion-readiness review, but it does **not** perform or authorize facing,
yaw, actor-chain, or proof promotion by itself.

## Latest source artifacts

| Field | Value |
|---|---|
| Offline pointer evidence | `scripts/captures/ghidra-static-analysis-20260601-071020/pointer-evidence.json` |
| Offline summary | `scripts/captures/ghidra-static-analysis-20260601-071020/summary.json` |
| Program | `rift_x64.exe` |
| Image base | `0x140000000` |
| Root RVA | `0x32EBC80` |
| Root address | `0x1432EBC80` |
| Root refs captured | `200` |
| Instructions scanned | `8057130` |
| Promotion performed | `false` |

## Fresh live yaw/facing evidence

| Evidence | Result |
|---|---|
| Current target | PID `41808`, HWND `0x2B0A26`, module base `0x7FF6EE5D0000` |
| Coordinate readback | `scripts/captures/static-owner-coordinate-chain-readback-20260601-163449-893588/summary.json` |
| Nav/facing readback | `scripts/captures/static-owner-nav-state-20260601-163449-943601/summary.json` |
| API-now reference | `scripts/captures/rift-api-reference-currentpid-41808-20260601-163536.json` |
| Live camera/yaw multipose | `scripts/captures/static-owner-camera-yaw-multipose-report-20260601-163443-380621/summary.json` |
| Fresh facing comparison | `scripts/captures/static-owner-camera-yaw-classification-20260601-163407-394774/static-owner-facing-comparison-20260601-163413-934652/summary.json` |
| Promotion-readiness review | `scripts/captures/facing-target-promotion-readiness-review-20260601-163520-953617/summary.json` |

The live right/left/right camera-yaw pack produced three
`visual-and-static-yaw-changed` classifications:

| Stimulus | Signed yaw delta |
|---|---:|
| right `160px` | `32.46881501641559` |
| left `320px` | `-60.70561869415195` |
| right `160px` | `33.88312498834827` |

The fresh dashboard now indexes the nested facing comparison from the latest
camera-yaw run, so `facingComparison` is fresh and points at
`owner+0x30C` with `33.88312498834827` degrees of observed yaw delta and
`0.0` coordinate planar drift.

## Offset review

| Owner offset | Role in current lane | Hit count | Write-like count | First relevant instruction | Interpretation |
|---|---|---:|---:|---|---|
| `0x300` | Candidate/support yaw scalar | 80 | 18 | `140006b56: LEA RBP,[RSP + 0x300]` | Changes during camera-yaw probes; support-only until a direct static-yaw semantic proof exists. |
| `0x304` | Support-only turn-rate/scalar | 80 | 28 | `14003fa33: MOV dword ptr [RDI + 0x304],R13D` | Same nearby owner writer cluster as facing/coordinate fields; keep support-only until dedicated proof. |
| `0x30C` | Candidate facing-target X | 80 | 26 | `14003fa41: MOV dword ptr [RDI + 0x30c],R13D` | Candidate-facing target appears in the same owner write sequence as promoted coordinate fields. |
| `0x310` | Candidate facing-target Y | 80 | 21 | `140014ea7: MOVAPS xmmword ptr [RSP + 0x310],XMM9` | Part of the candidate facing vector readback; required in the chain, but not promoted independently. |
| `0x314` | Candidate facing-target Z / constant component | 80 | 34 | `14003fa4f: MOV dword ptr [RDI + 0x314],0x3f800000` | Nearby constant write supports structured vector/target component semantics. |
| `0x320` | Promoted coordinate X | 80 | 22 | `14003fa67: MOV dword ptr [RDI + 0x320],R13D` | Matches the promoted coordinate owner offset and appears in the same writer cluster. |
| `0x324` | Promoted coordinate Y | 80 | 21 | `14003fa6e: MOV dword ptr [RDI + 0x324],R13D` | Same owner write sequence as coordinate X/Z. |
| `0x328` | Promoted coordinate Z / constant component | 80 | 19 | `14003fa75: MOV dword ptr [RDI + 0x328],0x3f800000` | Same owner write sequence as promoted coordinates; supports layout continuity. |

## Readiness state

| Gate | Status |
|---|---|
| Static root RVA documented | Passed for `rift_x64+0x32EBC80` |
| Candidate-facing chain shape documented | Passed for `+0x30C/+0x310/+0x314` |
| Coordinate resolver context | Passed for promoted `+0x320/+0x324/+0x328` |
| Fresh current PID readbacks | Passed for PID `41808` / HWND `0x2B0A26` |
| Fresh API-now vs chain-now | Passed; max abs delta `0.004394406249957683` |
| Fresh camera-yaw multipose | Passed; 3/3 visual-and-static-yaw-changed |
| Restart/relog survival packet | Passed in `scripts/captures/facing-target-restart-survival-packet-20260601-054826-920485/summary.json` |
| Formal three-pose gate | Passed in `scripts/captures/facing-target-three-pose-gate-20260601-054258-066521/summary.json` |
| Promotion-readiness review | Passed; awaiting explicit promotion gate |

## Safety and promotion boundary

| Boundary | Status |
|---|---|
| Offline Ghidra review | Passed |
| Live camera-yaw input in latest pack | Sent with explicit operator approval |
| Target memory read | Read-only only |
| Target memory write | No |
| x64dbg / Cheat Engine attach | No |
| Provider writes | No |
| Truth/facing/yaw/actor promotion | No |
| Git push | No |

## Remaining requirements before promotion

1. Operator must explicitly approve the separate facing/yaw promotion gate.
2. Immediately before that gate, refresh exact-target coordinate/nav/API
   readbacks for the current PID/HWND/process-start/module-base.
3. The promotion step must remain separate from this source-site review and
   must record `promotionPerformed` only inside the approved promotion artifact.
