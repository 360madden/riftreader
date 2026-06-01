# Session Startup Workflow

**What this covers:** Starting a RIFT session and verifying all resolvers are healthy.

**When to use:** Every time you log into RIFT and want to use the memory reader.

**Time estimate:** ~30 seconds (Tier 1) to ~2 minutes (Tier 2 verified).

---

## Step 1: Verify the target process

```bash
python scripts/static_owner_coordinate_chain_readback.py --use-current-truth --nav-state --json
```

This does everything in one call:
- Resolves target PID/HWND from `docs/recovery/current-truth.json`
- **Module base freshness gate (#1):** enumerates live module base, blocks if stale
- **Facing target zero-vector guard (#2):** blocks if 0x30C is (0,0,0)
- Reads player coordinates, yaw, turn rate, and facing target

### What to look for

```json
{
  "status": "passed",
  "verdict": "promoted-static-coordinate-resolver-readback-passed",
  "moduleBaseCheck": {"status": "passed"},
  "navState": {
    "yawDegrees": 87.9,
    "facingTargetCoordinate": {"x": 7262.43, "y": 821.46, "z": 3011.12},
    "navStateError": null
  },
  "coordinate": {"x": 7262.06, "y": 821.58, "z": 3001.12}
}
```

### If it fails

| Error | Cause | Fix |
|---|---|---|
| `module-base-mismatch` | RIFT restarted, `current-truth.json` has old module base | Update `current-truth.json` with new PID/module base |
| `module-base-enumeration-failed` | RIFT not running or wrong PID | Start RIFT, log in, verify PID matches |
| `facing-target-zero-vector` | Fresh zone-in, facing hasn't initialized | Move/turn slightly, retry |
| `process-not-running` | PID in `current-truth.json` is dead | Reacquire: `python scripts/static_owner_coordinate_chain_readback.py --process-name rift_x64 --pid <newpid> --module-base 0x... --json` |

---

## Step 2 (optional): Verify against API ground truth

For full confidence, compare the chain readback against the in-game `/rap` API:

```bash
# A: Get API ground truth
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/capture-rift-api-reference-coordinate.ps1 -ProcessId <pid> -Json

# B: Read chain
python scripts/static_owner_coordinate_chain_readback.py --use-current-truth --json

# Compare: API coordinate should match chain coordinate within 0.25 tolerance
```

---

## Step 3 (optional): Run readiness gate

```bash
python scripts/static_chain_promotion_readiness.py --json
```

This checks all 5 promotion gates offline (~1 second, no live process).

---

## Quick reference: all healthy indicators

| Check | Healthy value |
|---|---|
| `moduleBaseCheck.status` | `"passed"` |
| `navState.navStateError` | `null` |
| `navState.yawDegrees` | Non-None, plausible (-180 to 180) |
| `navState.facingTargetCoordinate` | Non-zero x/y/z |
| `navState.turnRateClassification` | Legacy candidate/support only. Current evidence classifies `0x304` as yaw-adjacent, not active turn-rate; do not use for control unless a future turn-rate gate promotes it |
| `coordinate` | Non-zero, plausible for current zone |

---

## What NOT to do at session startup

| Don't | Why | Do instead |
|---|---|---|
| Run `scan_current_pid_coordinate_family.py` | 60-180 second full memory scan, unnecessary | `--nav-state` (milliseconds) |
| Trust old PID proof anchors | Heap addresses are per-process-epoch | Always resolve from module RVA |
| Use SavedVariables as truth | They update on reloadui/logout, not live | Use RRAPICOORD API or promoted chain |
| Skip the freshness gate | Stale module base → silently wrong coordinates | Always run `--nav-state` first |
