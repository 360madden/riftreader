# Pointer Chain Validation

**What this covers:** Validating new candidate pointer chains through the promotion
gate pipeline. This is the process that elevated `[rift_x64+0x32EBC80]+0x320` from
"candidate" to "promoted resolver."

**When to use:** After discovering a new candidate chain via `rift-discovery` or
when re-validating an existing chain after a game patch.

**Time estimate:** 1–2 hours (full gate pipeline with live movement).

---

## Promotion gates (all 5 must pass)

| Gate | What it checks | How to validate |
|---|---|---|
| `staticResolverComplete` | Chain expression, root RVA, owner, coordinate address all present | Offline — `static_chain_promotion_readiness.py` |
| `restartRelogSurvived` | Resolver reacquired after process restart | Reboot/relog, then re-read chain |
| `staticChainCurrentReadbackPassed` | Latest readback passed (correct PID/HWND/owner, no CE, no movement) | `static_owner_coordinate_chain_readback.py --use-current-truth --nav-state --json` |
| `freshApiNowVsChainNowCurrent` | API-now vs chain-now deltas within tolerance and within age limit | `/rap` vs chain readback, compare within 0.25 |
| `promotionAllowed` | Static chain status explicitly allows promotion | `rift-proof` agent verdict |

## Validation pipeline

### Step 1: Discovery → candidate

Spawn `rift-discovery` agent to:
1. Compare memory snapshots (baseline vs stimulus-displaced)
2. Trace module-RVA pointers back from coordinate/facing addresses
3. Score and rank candidates by displacement consistency

### Step 2: Candidate → proof

Spawn `rift-proof` agent with:
- Chain expression (e.g., `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`)
- Target field (`coordinates`, `yaw`, `facing`, `pitch`)
- Proof type (`three-pose-displacement`, `reboot-survival`, `promotion-readiness`, `full`)
- Movement approved: `true`/`false`

### Step 3: Three-pose displacement

For coordinate chains:
1. Baseline: capture API + chain at starting position
2. Forward: move W 750–2000ms, capture API + chain
3. Reverse: move S 750–1000ms, capture API + chain
4. Verify: chain planar delta matches API planar delta within tolerance

For yaw/facing chains:
1. Baseline: capture facing/yaw at starting orientation
2. Turn right: turn 45–90°, capture
3. Turn left: turn 45–90°, capture
4. Verify: yaw delta matches visual angle delta, atan2 direction consistent

### Step 4: Reboot survival

1. Close RIFT client
2. Restart and log in
3. Re-read chain with new PID/module base
4. Compare against fresh API reference
5. Chain must resolve correctly with only module base change

### Step 5: Promotion

After all gates pass, the human explicitly approves promotion:
- Update `docs/recovery/current-truth.json`
- Update `docs/recovery/current-truth.md`
- Update `knowledge.md`

---

## Existing promoted chains

| Field | Chain | Validated |
|---|---|---|
| Player coordinates | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` | 2026-05-27, max delta 0.00477 |
| Facing target | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` | 2026-05-29, 4-pose triangulation |
| Yaw (derived) | `atan2(Z_0x314 - playerZ, X_0x30C - playerX)` | Derived from facing target |
| Turn rate | `[rift_x64+0x32EBC80]+0x304` | Directional discriminator |

## Data sources for future chains

| Source | Location | Notes |
|---|---|---|
| AOB signatures | `signatures/rift_x64/` | Fast module pattern scanning after updates |
| Pointer family scans | `scripts/captures/pointer-family-scan-*/` | Module-RVA pointer traces |
| Neighborhood inspector | `scripts/captures/pointer-owner-neighborhood-inspector-*/` | Owner window pointer enumeration |
| Owner layout comparison | `scripts/captures/owner-layout-comparison-packet-*/` | Field discovery across sessions |
