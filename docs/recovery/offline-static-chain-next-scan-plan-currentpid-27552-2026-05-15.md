# Offline static-chain next-scan plan — current PID coordinate proof

Generated UTC: `2026-05-15T08:12:34Z`
Status: **planned-offline-only-not-executed**
Scope: **offline-only plan generation**. No live memory read, no x64dbg attach/watchpoints, no Cheat Engine, and no movement/input.

## Verdict

A stable static pointer chain is **not** derivable from the current offline artifacts. The best result is a precise, bounded next-scan plan: use the proven 12-byte coord leaf as the future access target and the stable same-family qword as a parent/container seed, but reject both as static truth until module/RVA or static-owner provenance is captured and a repo-owned resolver validates the chain.

## Last-known proof target from artifacts

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID / HWND | `27552` / `0x3411E2` |
| Process start UTC | `2026-05-15T01:11:57.750696Z` |
| Module base | `0x7FF71CD90000` |
| Freshness caveat | Not refreshed live in this offline-only pass; validate target identity before any future live read/debugger work. |

## Current proof anchor evidence

| Item | Value |
|---|---|
| Candidate ID | `api-family-hit-000001` |
| Coord leaf | `0x27B1ED850C0` |
| Read region | `0x27B1ED85080` |
| XYZ offsets from coord leaf | `0x0, 0x4, 0x8` |
| XYZ offset from read region | `0x40` |
| Proof support count | `6` |
| Max reference planar displacement | `26.48665969974286` |
| Max delta error | `0.008501171875195723` |
| Latest ProofOnly | `passed-proof-only` |

## Ranked offline leads

| Rank | Lead | Address / range | Why | Risk |
|---:|---|---|---|---|
| 1 | `coord-12-byte-watch-window` | `0x27B1ED850C0` | Best access target for future approved provenance capture; X/Y/Z layout is proven for current PID artifacts. | Absolute heap address; stale after restart/relog/PID drift. |
| 2 | `parent-container-lead` | `0x27B1EC75C50` | Stable across existing coord-neighborhood samples and inside same rank-1 private heap region. | Heap/current-PID only; no owner/static provenance; not a static chain. |
| 3 | `rank-1-family-region` | `0x27B1EC70000..0x27B1FC80000` | Current-PID recovery family containing both parent lead and coord leaf. | Heap allocation region, not module/static root. |

## False leads to reject early

| Lead | Why to reject |
|---|---|
| `readRegion+0x48 qword 0x27B453EA3EA` | Overlaps Z float bytes at +0x48 with the following 0x27B value; changes with pose and is not a stable pointer lead. |
| `VCRUNTIME140.dll+0x1121C stale PID write event` | Historical PID 23496 copy/write helper evidence; lacks current-PID owner/source and rift_x64.exe module-relative provenance. |
| `heap-only references inside 0x27B1EC70000 family` | Useful for local parent graph only; cannot promote without module/RVA/static-owner root and restart validation. |

## Future approved scan questions

| # | Question |
|---:|---|
| 1 | Which current-PID instruction accesses reads or writes the 12-byte coord leaf 0x27B1ED850C0..0x27B1ED850CB? |
| 2 | Which register or memory operand identifies the owner/component base before adding XYZ field offsets? |
| 3 | Does any access path resolve to rift_x64.exe+RVA or another stable static owner rather than private heap-only pointers? |
| 4 | What references exist to parent lead 0x27B1EC75C50, read region 0x27B1ED85080, and coord leaf 0x27B1ED850C0 outside the narrow readback samples? |
| 5 | Can a repo-owned resolver re-read chain-now and match fresh API-now across at least three displaced poses? |

## Boundary for this offline pass

| Category | Items |
|---|---|
| Allowed now | offline artifact analysis; plan generation; resolver self-tests using synthetic/offline data |
| Not allowed now | x64dbg live attach; hardware/software breakpoints; single-step/tracing; live process memory scans; movement/input; Cheat Engine |
| Must refresh before future live work | PID/HWND/process-start; module base; fresh API/runtime coordinate; candidate address for same target; ProofOnly/read-only gate if needed |

## Future timeout policy if explicitly approved later

| Setting | Value |
|---|---:|
| `maxPreflightAgeSeconds` | `300` |
| `maxApiCoordinateAgeSeconds` | `60` |
| `maxLiveAttachSeconds` | `30` |
| `hardMaxLiveAttachSeconds` | `90` |
| `unresponsiveAbortSeconds` | `15` |
| `maxGoAttempts` | `1` |
| `detachBeforeAnalysis` | `True` |
| `wideScanTimeoutRequiresSeparateApproval` | `True` |

## Static-chain promotion gates

| # | Gate |
|---:|---|
| 1 | same PID/HWND/process-start for every sample used in a proof |
| 2 | fresh API/runtime coordinate close to every chain-now read |
| 3 | same candidate/chain tracks displacement across at least three pose-separated samples |
| 4 | module/RVA or static-owner root exists; heap-only local graph is insufficient |
| 5 | repo-owned no-debugger readback can resolve chain-now |
| 6 | restart/relog/client-epoch validation passes |
| 7 | same-target ProofOnly passes before movement/navigation use |

## Recommended future output paths

| Artifact | Path pattern |
|---|---|
| `accessEventIngest` | `scripts/captures/x64dbg-access-event-ingest-<timestamp>/summary.json` |
| `chainCandidate` | `scripts/captures/x64dbg-access-event-ingest-<timestamp>/x64dbg-coordinate-chain-candidate.json` |
| `resolverOutput` | `scripts/captures/x64dbg-static-chain-resolve-<timestamp>/summary.json` |
| `parentReferenceScan` | `scripts/captures/static-chain-parent-reference-scan-currentpid-<pid>-<timestamp>/summary.json` |
| `handoff` | `docs/handoffs/<timestamp>-static-chain-currentpid-<pid>-handoff.md` |

## Current blockers

| # | Blocker |
|---:|---|
| 1 | `no current-PID instruction/access provenance for coord leaf` |
| 2 | `no module/RVA or static-owner root` |
| 3 | `no full reference map from existing offline samples` |
| 4 | `no repo-owned chain readback candidate to resolve` |
| 5 | `no restart validation for any chain shape` |

## Source artifacts

| # | Path |
|---:|---|
| 1 | `docs/recovery/offline-static-chain-analysis-currentpid-27552-2026-05-15.md` |
| 2 | `docs/recovery/offline-static-chain-parent-lead-analysis-currentpid-27552-2026-05-15.md` |
| 3 | `docs/recovery/current-proof-anchor-readback.json` |
| 4 | `scripts/captures/telemetry-proof-coord-anchor.json` |
| 5 | `scripts/captures/live-test-ProofOnly-20260515-074836/run-summary.json` |
| 6 | `scripts/captures/x64dbg-static-chain-plan-safe-boundary-20260515-0727/coord-chain-plan-summary.json` |

## Generated artifacts

| Artifact | Path |
|---|---|
| Machine plan | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-next-scan-plan-currentpid-27552-20260515-081234\plan.json` |
| Markdown plan | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-next-scan-plan-currentpid-27552-20260515-081234\plan.md` |
| Tracked recovery doc | `C:\RIFT MODDING\RiftReader\docs\recovery\offline-static-chain-next-scan-plan-currentpid-27552-2026-05-15.md` |
