# Pointer Chain Reacquisition

**What this covers:** Recovering all promoted pointer chains after a RIFT game
update or client restart.

**When to use:** After any of:
- Game patch (minor or major)
- Client restart where `current-truth.json` module base is stale
- Resolver health check failure
- "module-base-mismatch" error from the freshness gate

**Time estimate:**
- Current artifact dashboard / resume orientation: **1–5 seconds**
- Module base update only (restart, no patch): **30 seconds**
- Minor patch (root RVA unchanged): **1–2 minutes**
- Major patch/expansion (root RVA shifted): **5–15 minutes**

---

## Step 0: Build the navigation pointer discovery dashboard

Before live input, debugger work, or proof promotion, index the latest
repo-owned artifacts so the next action starts from the newest coordinate,
facing-target, turn-rate, and movement-delta evidence.

```powershell
cmd /c scripts\riftreader-navigation-pointer-discovery.cmd --json --write
```

Outputs:

```text
.riftreader-local\navigation-pointer-discovery\latest\summary.json
.riftreader-local\navigation-pointer-discovery\latest\summary.md
```

The same dashboard is embedded in compact workflow status after it exists:

```powershell
cmd /c scripts\riftreader-workflow-status.cmd --compact-json --write
```

When the dashboard shows only `currentTruth` as stale, build an ignored dry-run
tracked-truth proposal before editing truth docs:

```powershell
cmd /c scripts\riftreader-current-truth-refresh-plan.cmd --json --write
```

Outputs:

```text
.riftreader-local\current-truth-refresh-plan\latest\summary.json
.riftreader-local\current-truth-refresh-plan\latest\proposed-current-truth.json
.riftreader-local\current-truth-refresh-plan\latest\proposed-current-truth.diff
```

The refresh-plan helper is **dry-run only**. It does not edit
`docs\recovery\current-truth.json`; applying a tracked truth refresh remains a
separate explicit gate.

This helper is read-only: it indexes existing artifacts only and performs no
live input, movement, target memory read, debugger/CE attach, provider write,
Git mutation, or proof promotion.

Freshness interpretation:

| Dashboard field | Budget | Meaning |
|---|---:|---|
| `coordinateReadback` | 1800 seconds | Current no-input coordinate readback should be refreshed before navigation decisions when stale. |
| `navState` | 1800 seconds | Current no-input facing/turn-rate readback should be refreshed before route or turn planning when stale. |
| `currentTruth` | 1800 seconds | Tracked truth docs may lag newer ignored readback artifacts; refresh only in a deliberate truth-update slice. |
| `facingComparison` | 86400 seconds | Historical discovery evidence remains useful for candidate scoring, but never authorizes promotion by itself. |
| `pointerNeighborhood` | 86400 seconds | Historical pointer-neighborhood evidence remains candidate context only. |
| `familySnapshot` | 86400 seconds | Historical movement-delta evidence confirms prior tracking but does not promote new navigation chains. |

If only `currentTruth` is stale while fresh readback artifacts exist, use the
dashboard for operator orientation and run a deliberate current-truth refresh
slice only when tracked docs must be updated. Do not treat dashboard freshness
as proof promotion or live-input approval.

---

## Decision tree

```
Resolver broken?
├─ Module base mismatch only (restart, no game update)
│   → Step 1: Update current-truth.json
│
├─ Game updated, root RVA might have shifted
│   → Step 2: AOB signature scan
│   → Step 3: Verify chain resolves
│
├─ Owner layout might have changed (expansion)
│   → Step 4: Neighborhood scan
│   → Step 5: Layout validation
│
└─ Complete reacquisition needed
    → Step 6: Full re-discovery
```

---

## Step 1: Update module base only (restart, no patch)

If RIFT just restarted but no game update occurred:

```powershell
tasklist /fi "imagename eq rift_x64.exe" /fo csv
python scripts\static_owner_coordinate_chain_readback.py --process-name rift_x64 --pid <PID> --hwnd <HWND> --module-base 0x<MODULE_BASE> --samples 3 --interval-seconds 0.20 --expect-stationary --json
```

The root RVA `0x32EBC80` and all owner offsets are unchanged — they're struct
positions in the game binary, not runtime addresses.

Only update `current-truth.json` after exact PID/HWND/process-start/module-base
identity has been rechecked and the readback passes.

---

## Step 2: AOB signature scan (minor/major patch)

If the game binary changed, the root RVA might have shifted. Use the captured
AOB signature to find it:

```powershell
dotnet run --project reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-module-pattern "<AOB from signatures\rift_x64\root_0x32EBC80.json>" --json
```

If the signature matches once in the module, the new RVA is reported.
Update `current-truth.json` `rootRva` field and re-verify.

If the signature matches **zero times**: the pattern changed. Re-capture:

```text
Option A: Known-value scan in Cheat Engine
#  1. In CE, scan for current player X coordinate (float)
#  2. Find the coordinate address
#  3. Read backwards to find the owner pointer
#  4. Trace the pointer back to its module-RVA root
```

Cheat Engine/debugger use is a gated boundary. Prefer read-only repo helpers
first when enough exact-target data exists:

```powershell
python scripts\pointer_family_scan.py --target-pid <PID> --target-hwnd <HWND> --expected-module-base 0x<MODULE_BASE> --target-address 0x<COORDINATE_ADDRESS> --depth 3 --json
```

Once the new RVA is found, capture a fresh signature:

```powershell
python scripts\capture_root_signature.py --rva 0x<NEW_RVA> --label root-player-owner --pid <PID> --json
```

---

## Step 3: Verify chain resolves

After updating the root RVA, verify the chain still produces valid coordinates:

```powershell
python scripts\static_owner_coordinate_chain_readback.py --use-current-truth --nav-state --samples 3 --interval-seconds 0.20 --expect-stationary --json
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\capture-rift-api-reference-coordinate.ps1 -ProcessId <PID> -Json
```

Expected: API coordinate matches chain coordinate within 0.25 tolerance.

---

## Step 4: Neighborhood scan (expansion-level update)

If the owner layout might have changed:

```powershell
python scripts\pointer_owner_neighborhood_inspector.py --pid <PID> --hwnd <HWND> --owner-address 0x<OWNER_ADDRESS> --target-address 0x<TARGET_ADDRESS> --target-window-size 65536 --module-base 0x<MODULE_BASE> --module-name rift_x64.exe --include-module-pointers --json
```

Check whether the owner pointer is still rooted at the same RVA and whether
new/different owner pointers appear in the surrounding window.

---

## Step 5: Layout validation (expansion-level update)

Dump the owner window and verify known offsets:

```powershell
python scripts\static_owner_coordinate_chain_readback.py --use-current-truth --nav-state --samples 3 --interval-seconds 0.20 --expect-stationary --json
```

If offsets shifted, treat as a full re-discovery.

Verify:

- `0x300`: accumulated heading (plausible float, not zero)
- `0x304`: yaw-adjacent scalar candidate; keep candidate-only and do not treat
  it as active turn-rate unless a dedicated turn-rate proof supersedes the
  2026-06-01 semantics review.
- `0x30C-0x314`: facing target (non-zero vec3)
- `0x320-0x328`: player coordinates (match `/rap` API)

---

## Step 6: Full re-discovery (worst case)

If both root RVA and owner layout changed:

1. **Cheat Engine:** Known-value scan for player X coordinate
2. **Pointer family scan:** Trace from coordinate address to module pointer
3. **Neighborhood inspector:** Scan for new layout pattern
4. **4-pose triangulation:** Validate yaw from new facing target
5. **API comparison:** Validate coordinates against `/rap`
6. **Promotion gates:** Run all 5 gates via `rift-proof`
7. **Capture new signatures:** For the next update

**Estimated time:** 1–2 hours (guided by tools, not manual RE).

---

## Tool reference

| Tool | Purpose | Speed |
|---|---|---|
| `capture_root_signature.py` | Capture AOB signature | ~5 seconds |
| `static_owner_coordinate_chain_readback.py --nav-state` | Full resolver health check | Milliseconds |
| `pointer_owner_neighborhood_inspector.py` | Scan for owner pointers | ~30 seconds |
| `pointer_family_scan.py` | Trace pointer chains back to module | ~60–90 seconds |
| C# reader `--scan-module-pattern` | AOB pattern scan in module | ~2–5 seconds |
| Cheat Engine | Known-value scan for coordinates | Manual, 1–5 minutes |
| `static_chain_promotion_readiness.py` | All 5 promotion gates | ~1 second |

---

## Emergency contacts

If everything fails and you're stuck:
1. Check `docs/workflows/owner-layout-reference.md` for what fields should exist
2. Check `signatures/` for last-known-good AOB patterns
3. Run `rift-discovery` agent for guided RE assistance
4. `docs/recovery/` has historical handoffs that may contain clues about similar past recoveries
