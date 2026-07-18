# Optimized post-update recovery workflow (trimmed)

**Purpose:** Durable, lane-split recovery playbook for the next RIFT client
update. Prefer signal and restart-stable resolvers; cut ceremony that does not
add capability.

**When to use:** After a patch, root-null, PID/HWND drift, or when reacquiring
coordinates before navigation.

**Status:** Canonical trimmed workflow for post-update recovery. Supersedes
ad-hoc “run the full fast helper through movement every time” habits for
**seed** work. Formal promotion gates for shipping navigation remain intact.

**Related:**

| Doc | Role |
|---|---|
| `docs/recovery/current-truth.md` | Current epoch authority / blockers |
| `docs/recovery/hybrid-fast-reacquire-strategy.md` | Hybrid architecture context |
| `docs/recovery/optimized-player-actor-coordinate-chain-workflow.md` | Provenance-first discovery detail |
| `docs/workflows/pointer-chain-validation.md` | Full formal promotion gates |
| `docs/workflows/automated-travel-memory-data-catalog.md` | Pose/camera/overlay field inventory |
| `docs/recovery/c2m-destination-discovery-status-2026-07-18.md` | C2M click→diff session findings (candidate-only) |

---

## Two lanes (do not mix)

| Lane | Goal | Output |
|---|---|---|
| **A — Session seed** | Current PID coords without claiming static/nav truth | Candidate address + API match |
| **B — Static resolver** | Restart-stable chain | Module RVA + offsets (promoted only at end) |

Movement, CE, x64dbg attach, current-truth apply, ProofOnly, and promotion remain
**separately approval-gated**. Lane A does not require them.

---

## Lane A — Session seed (no movement by default)

### 1. Preflight (once per process epoch)

| Do | Skip |
|---|---|
| Exactly one `rift_x64` + HWND | Visual gate every run |
| Bind PID / HWND / process-start / module base | ChromaLink if down |
| Confirm window responding | Full decision-packet ritual as a blocker |

**Stop if:** multi-client, no window, process dead.

### 2. API-now

| Do | Skip |
|---|---|
| RRAPICOORD memory scan (`status=pass` + x/y/z) | SavedVariables / `ReaderBridgeExport.lua` as live |
| Record seq + coords + time | Waiting on ChromaLink |

**Stop if:** no usable marker (fix/enable `RiftReaderApiProbe` / `ReaderBridge`).

### 3. Root probe (~seconds)

| Do | Skip |
|---|---|
| Read known roots (last-promoted RVAs + any new candidates) | Blind module-RVA sweeps when already null for this binary |
| If **non-null** → jump to **Lane B §4** (validate layout) | Treating null root as “try harder the same way” |

### 4. Family hit (only if root null or unproven)

| Do | Skip |
|---|---|
| Memory inventory **or** last-good range / restart profile first | Full large-range inventory every time if a profile exists |
| Stop-on-hit scan for API float triplet | Broad scan after first credible hit |
| Keep top 1–3 candidates | Promoting heap absolute addresses |

### 5. Same-pose verify

| Do | Skip |
|---|---|
| Immediate re-read candidate vs fresh API | Multi-pose, ProofOnly, truth apply |
| Δ within tolerance → **session seed ready** | Navigation / movement |

**Lane A done.** Artifact: candidate JSONL + API sample + target identity.

---

## Optional A→B bridge (one approval)

Only if you need to kill copy addresses before debugger/static work:

| Do | Skip |
|---|---|
| **One** short W pulse (e.g. 500–750 ms) | Adaptive W/W/Q/E battery |
| Re-read same address; must track API Δ | Full 3-pose yet |

---

## Lane B — Static resolver (restart survival)

### 1. Freeze one seed

- Best address from Lane A (post-pulse if you ran it)
- Owner hypothesis if obvious (e.g. coords look like `+0x320` pattern)

### 2. Provenance (pick one path)

| Preferred if authorized | Offline if root-null / no debug approval |
|---|---|
| **One** bounded HW watch on coord field → stack → `rift_x64` caller | Ghidra xref/writer on installed `rift_x64.exe` |
| Normalize event → module/RVA candidate | No live attach |

**Skip:** watch loops, CE, broad debugger scan.

### 3. Build resolver candidate

```text
moduleBase + ROOT_RVA  →  owner  →  +offX/+offY/+offZ
```

- Promote **RVA + offsets only**, never heap absolute.

### 4. Validate (current session)

| Gate | Required |
|---|---|
| Root non-null, owner plausible | Yes |
| API-now vs chain-now (same cycle) | Yes |
| 2–3 poses if claiming movement-grade | Yes for promote; no for “interesting candidate” only |

### 5. Restart survival

| Do | Skip |
|---|---|
| Relog/restart → new PID → re-resolve `moduleBase+RVA` | Reusing old owner heap |
| API match again | Calling it static without this |

### 6. Promote (explicit only)

| Write | Do not |
|---|---|
| Resolver expression + binary identity (hash / size / version) | Auto-apply truth every session |
| Mark previous root historical if superseded | Claim nav until this exists |

---

## End-to-end order

```text
1. Bind target (PID/HWND/start/base)
2. RRAPICOORD API-now
3. Probe static roots
   ├─ hit → validate offsets + API ──► restart ──► promote
   └─ null → family stop-on-hit
4. API match on candidate  (= session seed; STOP here often)
5. [optional] 1× movement pulse, re-check
6. 1× watch OR Ghidra → new ROOT_RVA
7. API match + restart
8. Explicit promote → only then nav/automation
```

---

## Intentionally removed (do not reintroduce by habit)

| Removed | Why |
|---|---|
| ChromaLink required | RRAPICOORD is enough for API-now |
| Visual gate every time | Once per epoch is enough |
| Full multi-pose before any candidate | Seed does not need it |
| ProofOnly for discovery | Only for movement-safe / nav control |
| current-truth thrash | Update on real epoch change only |
| MSC / HUD / Export as live path | Not critical path |
| Repeat root-signature sweeps after null | Zero signal; go offline static |
| Full formal promotion packet for every micro-step | Use for promote, not for seed |

---

## Keep strict (do not trim)

| Gate | Why |
|---|---|
| Exact PID/HWND/process-start | Wrong client = wrong truth |
| API-now vs memory-now before “current” | Only real freshness proof |
| No SavedVariables as live | Historical failure mode |
| No movement / CE / x64dbg / promotion without explicit yes | Blast radius |
| Promote RVA+offsets, never heap absolute | Restart survival definition |
| Restart survival before calling something **static** | Without this it is a session pointer |
| Separate proof-anchor vs static actor-chain | Mixing them causes false “done” |

---

## Done criteria

| Level | You have | You may |
|---|---|---|
| **Session seed** | API + matching heap candidate | Readback, ranking, handoff |
| **Session-validated** | + 1 pulse tracks | Stronger discovery; still not static |
| **Static candidate** | + module RVA resolves owner | Restart test |
| **Promoted** | + restart + API + explicit promote | Nav / automation |

**Default stop for “see if recovery helps”:** session seed.  
**Default stop for “travel after patch”:** promoted (or hybrid seed + same-target ProofOnly if you accept non-static session truth).

---

## Minimal commands

```powershell
# API-now (Lane A §2)
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\capture-rift-api-reference-coordinate.ps1 `
  -ProcessId <pid> -TargetWindowHandle <hwnd> -Json

# Session seed (Lane A §3–5) — no movement / no truth / no ProofOnly
python .\scripts\recover_current_pid_coord_anchor_fast.py --execute --pid <pid> --hwnd <hwnd> --json
# Stop at candidate JSONL; movement-approval blocker is expected and OK for Lane A

# Root probe
python .\scripts\static_owner_coordinate_chain_readback.py --pid <pid> --hwnd <hwnd> --json

# Offline static when root null (Lane B §2 offline path)
.\scripts\riftreader-ghidra-static-evidence.cmd --plan --json
.\scripts\riftreader-ghidra-static-evidence.cmd --run --binary-path "C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe" --json
```

Optional (explicit approval only):

```powershell
# One-pulse bridge or multi-pose promotion path
python .\scripts\recover_current_pid_coord_anchor_fast.py --execute --pid <pid> --hwnd <hwnd> --movement-approved --json
```

---

## Historical method note (why this order)

The last long-lived promoted chain (May–June 2026) was not found by repeating
broad scans. It was:

```text
API-matched live coord
  → bounded access provenance (one watch / stack)
  → singleton / module .data root (e.g. 0x32EBC80)
  → owner-relative +0x320/+0x324/+0x328
  → restart re-resolve (heap changes; RVA+offsets hold)
  → API-now + displacement
  → promote RVA+offsets only
```

Post-patch roots going null is expected. **Do not** re-promote pre-patch RVAs
from artifacts. Rebuild from Lane A seed + Lane B provenance on the **current**
binary identity (hash/size).

---

## Maintenance

| Event | Action |
|---|---|
| New client SHA | Start Lane A; treat prior roots as historical until re-proven |
| Session seed found | Prefer owner-layout / provenance over more family scans |
| Root-null after one thorough probe | Offline Ghidra / caller review; stop live root-signature loops |
| Promotion | Update `current-truth.md` (+ JSON if used) with new expression and binary id |

**Last updated:** 2026-07-18  
**Document kind:** durable workflow (not a live truth pointer)
