# C2M truth bind + static chain restart survival

**Status:** durable operator/agent contract (2026-07-18)  
**Live pointer:** always prefer [`current-truth.md`](current-truth.md) / [`current-truth.json`](current-truth.json) for *current* PID/HWND values.

**Related library entries:**

| Doc | Role |
|---|---|
| [`current-truth.md`](current-truth.md) | Live target + promoted root |
| [`progress-2026-07-18-post-patch-root-and-c2m.md`](progress-2026-07-18-post-patch-root-and-c2m.md) | Full session milestone |
| [`../workflows/automated-travel-memory-data-catalog.md`](../workflows/automated-travel-memory-data-catalog.md) | Travel field inventory |
| [`../workflows/owner-layout-reference.md`](../workflows/owner-layout-reference.md) | Owner offsets |
| [`../workflows/optimized-post-update-recovery-workflow.md`](../workflows/optimized-post-update-recovery-workflow.md) | Next patch reseed playbook |
| `scripts/routes/README.md` | C2M route files |

---

## 1. Short answers

| Question | Answer |
|---|---|
| Is `current-truth` what C2M uses? | **Yes** — by default (`--use-current-truth`) |
| Is the static pointer chain restart-survivable? | **Yes** — promote **RVA + offsets**; re-resolve heap owner every session |
| What must be rebound after relaunch? | **PID / HWND / process-start** (and refresh pose); **not** the root RVA on this binary |

---

## 2. What “truth for C2M” means

`scripts/c2m_run_to_goal.py` defaults to **`--use-current-truth`** (use `--no-use-current-truth` only for recovery).

### Fail-closed bind

Before any click, C2M compares **live** RIFT process to `docs/recovery/current-truth.json`:

| Check | Source in truth | On mismatch |
|---|---|---|
| Process ID | `target.processId` | **blocked** (exit 2) |
| HWND | `target.targetWindowHandle` | **blocked** |
| Process start UTC | `target.processStartUtc` | **blocked** if delta > tol (default 2s) |
| Static root RVA | `bestCurrentCandidate.rootRva` | **blocked** if CLI/root disagrees |
| Module base | `target.moduleBase` | **warning** if differs (ASLR); not a hard fail alone |

Recovery-only override: `--allow-target-drift` (does not update truth).

### What C2M reads from truth vs live memory

| Item | From truth? | Live each run? |
|---|---|---|
| Exact target identity (PID/HWND/start) | **Yes** (gate) | Enumerate process to match |
| Root RVA `0x32E07C0` | **Yes** (default) | Read `moduleBase+RVA` |
| Owner heap pointer | No (must not hardcode) | **Yes** — deref root |
| Player X/Y/Z | Snapshot only | **Yes** — `owner+0x320…` when `--pose-source static-chain` |
| Heading for A/D prestep | No | **Yes** — `[[owner+0x330]+0x158]` |
| Route waypoints | Route JSON | — |

### Operator commands

```powershell
# Confirm pose through promoted chain
python scripts\static_owner_pose_now.py --json
python scripts\static_owner_coordinate_chain_readback.py --use-current-truth --samples 2 --json

# C2M uses truth bind + static pose by default
python scripts\c2m_run_to_goal.py --execute --stimulus-approved `
  --use-current-truth --pose-source static-chain --aim-mode w2s --heading-prestep `
  --waypoints-json scripts\routes\safe-handpicked-a-reverse.json --json
```

After every RIFT relaunch: **rebind truth target** (PID/HWND/start) before C2M, or bind will fail closed.

---

## 3. Promoted static chain (restart-survivable)

### Expression (this binary)

```text
moduleBase = base of rift_x64.exe
owner      = read_ptr(moduleBase + 0x32E07C0)     # fail if null
x,y,z      = read_f32(owner + 0x320 / 0x324 / 0x328)
camera     = read_ptr(owner + 0x330)
headingRad = read_f32(camera + 0x158)             # provisional heading
```

### Survives restart vs does not

| Survives process restart | Does **not** survive (session-local) |
|---|---|
| Root RVA **`0x32E07C0`** | Heap **owner** address |
| Coord offsets `+0x320/+0x324/+0x328` | Absolute HWND / PID |
| Camera child offset `+0x330` | Process start timestamp |
| Heading field `camera+0x158` | Absolute world coords in route files if you change zone |
| W2S layout (cam pos `+0x08`, look-at `+0x14`, FOV `+0x38`) | — |

**Invariant:** promote and document **RVA + offsets only**. Always reacquire owner from the root after attach.

### Superseded roots (do not use on this binary)

| Root | Status |
|---|---|
| `0x32EBC80` | Dead pre-patch / wrong epoch |
| `0x32EBDC0` | Null on post-2026-07-14 binary before reseed |

---

## 4. Restart survival evidence (2026-07-18)

| Process epoch | PID | What was proven |
|---|---|---|
| Reseed | `26916` | API family scan → module root `0x32E07C0` |
| Restart #1 | `21436` | Root non-null; owner heap changed; three-pose + API-now; multi-WP C2M |
| Restart #2 | `32636` | Root non-null; new owner `0x179BB4106A0`; truth rebind; **hand-picked absolute route 5/5 arrived** |

Artifacts (selected):

| Proof | Path |
|---|---|
| Restart survival packet | `scripts/captures/owner-root-restart-survival-currentpid-21436-20260718-170030/` |
| Three-pose + API | `scripts/captures/static-root-three-pose-21436-20260718-170754/` |
| Post-restart C2M hand-picked | `scripts/captures/c2m-run-to-goal-20260718-181321/` |
| Known-good route | `scripts/routes/safe-handpicked-a.json` (+ `-reverse`) |

---

## 5. After-restart checklist (C2M)

1. RIFT in-world, single client.  
2. **Rebind truth** (PID/HWND/process-start + live pose).  
3. `static_owner_pose_now.py` or `--use-current-truth` readback → coords sane.  
4. C2M with `--use-current-truth` (default) — should **not** report `pid-mismatch`.  
5. Prefer heading-frame or hand-picked routes; avoid blind world-axis grids into props.

If bind reports `pid-mismatch` / `hwnd-mismatch` / `process-start-mismatch`: **do not** use `--allow-target-drift` for normal play; rebind truth first.

---

## 6. Navigation collision policy (locked)

| Collide for pathing? | Class |
|---|---|
| **No** | Friendly NPCs |
| **No** | Neutral NPCs |
| **No** | Hostile NPCs |
| **Yes (terrain/props)** | Rocks, trees, walls, cliffs, unwalkable ground |

Navmesh / C2M routes model **geometry walkability only**. Stuck detours and blocked
edges are for **terrain/prop** failure, not unit avoidance. Entity lists are out of
scope for navigation collision (combat/targeting is a separate consumer).

## 7. C2M consumer contract (summary)

| Flag / surface | Contract |
|---|---|
| `--use-current-truth` (default **on**) | Fail closed on target/root identity drift |
| `--pose-source static-chain` | Fast pose from promoted root |
| `--pose-source rrapicoord` / `auto` | API string fallback |
| `--aim-mode w2s` | Project goal; clamp safe client band (no toolbar ~0.82 Y) |
| `--heading-prestep` | A/D when heading error large (`cam+0x158`) |
| `--no-refocus` (route clicks) | Keep RIFT focused during multi-click legs |
| Routes under `scripts/routes/` | Absolute or heading-relative JSON |

---

## 8. Next patch note

If a future client build nulls `0x32E07C0`, **do not** assume this doc’s RVA. Follow  
[`../workflows/optimized-post-update-recovery-workflow.md`](../workflows/optimized-post-update-recovery-workflow.md)  
(API-now → family seed → module root scan → restart + three-pose → truth promote).

---

*Library entry for: “Is truth for C2M?” and “Is the static chain restart-survivable?”*  
*Authoritative live numbers always live in `current-truth.json`; this file is the durable contract.*
