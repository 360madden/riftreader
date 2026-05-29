# Coordinate Recovery & Reacquisition Workflow

The promoted static resolver `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` is the
primary coordinate source. It was validated 2026-05-27 through three-pose live
displacement (baseline → forward-W → reverse-S) with max delta **0.00477**
against RRAPICOORD API. It is reboot-surviving, Cheat Engine–free, and read-only.

## Tool classification

| Tool | Purpose | Speed | Use for recovery? |
|---|---|---|---|
| `static_owner_coordinate_chain_readback.py` | Direct resolver read | **Milliseconds** | ✅ Primary |
| `capture-rift-api-reference-coordinate.ps1` | API ground truth (`/rap`) | **5–15 seconds** | ✅ Verification |
| `static_chain_promotion_readiness.py` | Gate check (offline) | **~1 second** | ✅ Health check |
| `rrapicoord_scan_diagnostics.py` | Marker diagnostic | **5–15 seconds** | ✅ If `/rap` fails |
| `rrapicoord_addon_state_diagnostics.py` | Addon runtime check | **5–15 seconds** | ✅ If `/rap` fails |
| `repair_rrapicoord_addon_settings.py` | AddonSettings repair | **5–15 seconds** | ✅ If `/rap` fails |
| `scan_current_pid_coordinate_family.py` | **Discovery** — full memory scan | **60–180 seconds** | ❌ Not for recovery |
| `current_pid_candidate_readback.py` | **Discovery** — candidate scoring | **30–60 seconds** | ❌ Not for recovery |
| `coordinate_candidate_compare.py` | **Discovery** — two-pose scoring | **60–120 seconds** | ❌ Not for recovery |
| `coordinate_proof_route.py` | **Discovery audit** — evidence aggregation | **~1 second (offline)** | ❌ Not for recovery |

**Rule:** the discovery pipeline (family scans, candidate readbacks, candidate
comparisons, proof routes) exists to *find and validate new resolver chains*.
Once a chain is promoted, the direct readback tools replace the entire discovery
pipeline for routine use.

---

## Tier 1 — Instant (milliseconds, read-only)

```bash
python scripts/static_owner_coordinate_chain_readback.py --use-current-truth --json
```

Two `ReadProcessMemory` calls: deref `rift_x64+0x32EBC80` → add `0x320` → read
12 bytes of `(x, y, z)`. Returns coordinates, owner address, vtable, and optional
proof-anchor delta. No scanning. No candidates. No API dependency.

**Use this** when you just need the player's position *right now* — navigation
loops, polling, waypoint checks, live coordinate consumers.

### What you get

```json
{
  "status": "passed",
  "verdict": "promoted-static-coordinate-resolver-readback-passed",
  "classification": "static-coordinate-resolver-current-position-source",
  "ownerAddress": "0x278C3830010",
  "coordinate": {"x": 7258.8896, "y": 821.43, "z": 2991.5598},
  "sampleCount": 1,
  "maxPlanarDelta": 0.0,
  "ownerChangedCount": 0
}
```

### Options

| Flag | Purpose |
|---|---|
| `--use-current-truth` | Populate PID/HWND/module-base from `docs/recovery/current-truth.json` |
| `--samples 3` | Poll N samples (e.g., for stationary check) |
| `--interval-seconds 0.2` | Gap between poll samples |
| `--expect-stationary` | Block if planar drift exceeds `--max-stationary-planar-drift` |
| `--expected-proof-anchor 0x...` | Compare against a known proof anchor address |
| `--json` | Compact JSON output |

---

## Tier 2 — Verified (5–15 seconds, read-only)

Two commands in parallel, then compare:

```bash
# A: Fresh RRAPICOORD API ground truth
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/capture-rift-api-reference-coordinate.ps1 -ProcessId 34176 -Json

# B: Static chain readback (3 samples, stationary check)
python scripts/static_owner_coordinate_chain_readback.py --use-current-truth --samples 3 --expect-stationary --json
```

If the API coordinate matches the chain coordinate within the 0.25 default
tolerance, the resolver is confirmed healthy for the current session. This is the
same validation that passed promotion on 2026-05-27.

Expected delta: **sub-millimeter** (typically < 0.002 when stationary).

---

## Tier 3 — Readiness Gate (~1 second, offline artifact analysis)

```bash
python scripts/static_chain_promotion_readiness.py --json
```

This checks every gate that matters using offline artifact analysis (no live
process interaction):

| Gate | Meaning |
|---|---|
| `staticResolverComplete` | Chain expression, root RVA, root address, owner address, coordinate address all present |
| `restartRelogSurvived` | Resolver reacquired after process restart |
| `staticChainCurrentReadbackPassed` | Latest chain readback passed (correct PID/HWND/owner, coordinate valid, no Cheat Engine, no movement sent, within age limit) |
| `freshApiNowVsChainNowCurrent` | API-now vs chain-now comparison within tolerance and within age limit |
| `promotionAllowed` | Static chain status explicitly allows promotion |

If it returns `verdict: static-chain-promotion-gates-passed`, everything is green.
The only common blocker is artifact age — a fresh API + chain capture pair (Tier 2)
resolves it.

---

## Tier 4 — If RRAPICOORD Is Down (diagnostic, then repair)

When `/rap` returns no usable marker (`status=pass, source=rift-api,
savedVariablesUse=none`):

### Step 1: Diagnose

```bash
# Classify the raw scan artifacts
python scripts/rrapicoord_scan_diagnostics.py --json

# Check addon runtime state
python scripts/rrapicoord_addon_state_diagnostics.py --json
```

### Step 2: Preview the fix

```bash
# Dry-run — no mutation, preview only
python scripts/repair_rrapicoord_addon_settings.py --scope latest --json
```

### Step 3: Apply (requires explicit approval)

```bash
# Writes external RIFT AddonSettings outside the repo
python scripts/repair_rrapicoord_addon_settings.py --scope latest --apply --json
```

### Step 4: Reload addon runtime

In the RIFT game window, press actionbar slot `-` (reloadUI) or `/reloadui`.
This activates the repaired AddonSettings. Then retry Tier 2.

The repair pipeline was battle-tested 2026-05-27: `AddonSettings` repair restored
the marker, `/reloadui` reactivated it, and the three-pose validation passed.

---

## Tier 5 — Full Displacement Validation (if re-proof is needed)

For when the resolver needs re-validation after a patch, module drift, or new
process epoch:

### Step 1: Baseline capture

```bash
# Capture API reference at starting position
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/capture-rift-api-reference-coordinate.ps1 -ProcessId <pid> -Json

# Read static chain at starting position
python scripts/static_owner_coordinate_chain_readback.py --use-current-truth --json
```

### Step 2: Move character

```bash
# Hold W for 2 seconds to move forward
dotnet run --no-build --project tools/RiftReader.SendInput/RiftReader.SendInput.csproj -- --key w --hold-ms 2000 --pid <pid> --hwnd <hwnd> --input-mode ScanCode --json
```

### Step 3: Capture at displaced position

```bash
# Capture API reference at new position
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/capture-rift-api-reference-coordinate.ps1 -ProcessId <pid> -Json

# Read static chain at new position
python scripts/static_owner_coordinate_chain_readback.py --use-current-truth --json
```

### Step 4: Reverse movement (optional, for three-pose validation)

```bash
# Hold S for 1 second to move back
dotnet run --no-build --project tools/RiftReader.SendInput/RiftReader.SendInput.csproj -- --key s --hold-ms 1000 --pid <pid> --hwnd <hwnd> --input-mode ScanCode --json

# Capture API + chain at this position
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/capture-rift-api-reference-coordinate.ps1 -ProcessId <pid> -Json
python scripts/static_owner_coordinate_chain_readback.py --use-current-truth --json
```

### Step 5: Verify

For each movement segment, the chain planar delta should match the API planar
delta within tolerance. The 2026-05-27 validation showed:

| Segment | API planar X/Z | Chain planar X/Z |
|---|---|---|
| Baseline → Forward (W:1200ms) | 7.472 | 7.475 |
| Forward → Reverse (S:900ms) | 2.744 | 2.746 |

### Step 6: Re-run readiness gate

```bash
python scripts/static_chain_promotion_readiness.py --json
```

---

## Decision tree

```
Need coordinates?
├─ Instant (no API needed)
│   → static_owner_coordinate_chain_readback.py --use-current-truth
│
├─ Verified (with ground truth)
│   → /rap + chain readback, compare deltas
│
├─ Is my resolver still healthy?
│   → static_chain_promotion_readiness.py
│
├─ RRAPICOORD marker missing?
│   → rrapicoord_scan_diagnostics.py
│   → rrapicoord_addon_state_diagnostics.py
│   → repair_rrapicoord_addon_settings.py --scope latest
│   → (approve) → --apply
│   → /reloadui in game
│   → Retry Tier 2
│
└─ Need full re-proof after patch/restart?
    → Tier 5 displacement validation
```

## Anti-patterns: what NOT to do

| Don't | Why | Use instead |
|---|---|---|
| Run `scan_current_pid_coordinate_family.py` for routine coordinates | Scans GBs of process memory, takes 60–180s, produces candidate lists not coordinates | `static_owner_coordinate_chain_readback.py` (milliseconds) |
| Run `current_pid_candidate_readback.py` after a family scan | Still needs a fresh API capture, produces per-address scores not a single coordinate | `static_owner_coordinate_chain_readback.py` (milliseconds) |
| Run `coordinate_candidate_compare.py` for two-pose validation | Requires two family scans, cross-referencing by address; data model from family scans doesn't naturally support `bothReferenceMatchCount > 0` | Tier 5 displacement validation (chain vs API through movement) |
| Run `coordinate_proof_route.py` for routine health checks | Aggregates visual/API/memory/static/candidate/displaced evidence designed for pre-promotion discovery audit | `static_chain_promotion_readiness.py` (offline, ~1s) |
| Use old PID proof anchors (e.g., `0x23863A26E50` for PID 12148) | Heap addresses are per-process-epoch; the promoted resolver is module-RVA based and survives restarts | `--use-current-truth` to load the current target |
| Treat the current owner address (`0x278C3830010`) as static | It changes per process epoch | Always resolve from `moduleBase + 0x32EBC80` each session |

## Safety invariants

All Tier 1–3 operations are **read-only**:
- No movement sent
- No input sent
- No Cheat Engine
- No x64dbg attach
- No target memory writes
- No provider/github writes
- No proof promotion

Tier 4 step 3 (repair apply) and Tier 5 (movement) require explicit approval
because they mutate external state (AddonSettings file or game position).

---

## Reference: the promoted resolver

| Field | Value |
|---|---|
| Chain | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Root module | `rift_x64.exe` |
| Root RVA | `0x32EBC80` |
| Coordinate offsets | `+0x320` (x), `+0x324` (y), `+0x328` (z) |
| Promoted | 2026-05-27 |
| Validation | Three-pose live displacement, max delta 0.00477 |
| Survives restart | ✅ |
| Survives relog | ✅ |
| Full actor/stat chain | ❌ Not promoted (coordinate resolver only) |
