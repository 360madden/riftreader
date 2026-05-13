# Handoff: PID 2928 no-candidate grouped scan blocker

Generated: 2026-05-13 13:04 EDT / 2026-05-13 17:04 UTC
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
Target: `rift_x64` PID `2928`, HWND `0xC0994`, process start `2026-05-13T16:17:56.208370Z`, module base `0x7FF71CD90000`

## TL;DR

RIFT is responsive again after the earlier PID `60628` freeze, but coordinate
truth for current PID `2928` is still **not promoted**.

No x64dbg launch/attach, movement, watchpoints, Cheat Engine, reloadui,
screenshot key, memory writes, or provider writes were used in this slice.

The current blocker is simple: bounded read-only scans did not find any
current-PID XYZ triplet near the fresh ChromaLink API/runtime coordinate.

## Current evidence

| Evidence | Result |
|---|---|
| Target preflight | Passed for PID `2928` / HWND `0xC0994`; target `responding=true`, visible, debugger process count `0`. |
| Fresh API/runtime reference | `scripts/captures/chromalink-world-state-reference-20260513-170034-699164/summary.json` |
| Reference coordinate | `X=7397.52`, `Y=871.78`, `Z=3027.98`, observed `2026-05-13T17:00:34.6914755+00:00`, age `0.01ms`. |
| 45s stride-4 scan | `scripts/captures/family-scan-currentpid-2928-20260513-165436-907290/family-scan-summary.json`; `hitCount=0`. |
| 90s stride-4 scan | `scripts/captures/family-scan-currentpid-2928-20260513-170101-859202/family-scan-summary.json`; tolerance `2.0`, `hitCount=0`, `bytesScanned=390070272`. |
| 60s stride-1 scan | `scripts/captures/family-scan-currentpid-2928-20260513-170252-761030/family-scan-summary.json`; tolerance `2.0`, `hitCount=0`, `bytesScanned=67108864`. |
| Final target check | `scripts/captures/x64dbg-target-preflight-20260513-170413-554633/summary.json`; still `responding=true`, no debugger process. |

## Interpretation

| Finding | Meaning |
|---|---|
| API/runtime coordinate is fresh | ChromaLink is a valid current reference surface for this target epoch. |
| No grouped-scan hits | The current scan strategy did not reach or match the authoritative coordinate storage/copy. |
| No candidates | Do not rank, do not build an x64dbg plan, and do not attach x64dbg yet. |
| Current proof pointer stale | `current-proof-anchor-readback.json` still targets PID `57656` / HWND `0x5417BC`; do not use it for PID `2928`. |

## Safety state

| Boundary | State |
|---|---|
| x64dbg | Not launched or attached. If needed later, keep debugger/dependent windows minimized unless visibility is required for the debugger action. |
| Cheat Engine | Not used and not authorized in this lane. |
| Movement/input | None sent. |
| Promotion | None. `docs/recovery/current-proof-anchor-readback.json` remains unchanged. |
| Evidence tier | `responsive-candidate` target/API evidence only; no `live-proof`; no `frozen-snapshot` captured in this slice. |

## Recommended next step

Do **not** go directly to x64dbg. First improve the non-debugger discovery
surface:

1. build or run a region-inventory / high-address-region scan planner so the
   coordinate family scan can reach likely heap regions instead of burning time
   from low addresses;
2. consider alternate layouts/orderings only after the scan planner confirms the
   relevant regions were actually covered;
3. only build a bounded x64dbg plan if a fresh current-PID candidate exists.

## Optional top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Add or use a memory-region inventory for PID `2928`. | Current scans timed out before proving likely heap coverage. |
| 2 | Prioritize high committed private/readwrite regions instead of low-address order. | Prior successful candidates were heap-family evidence, not low-address data. |
| 3 | Add a scan resume/range planner before another long scan. | Prevents re-reading the same early regions repeatedly. |
| 4 | Keep refreshing ChromaLink API/runtime reference before each scan batch. | Coordinates changed between checks and must stay fresh. |
| 5 | Keep preflight before and after every scan. | Confirms no debugger and target responsiveness. |
| 6 | Do not rank until `hitCount > 0`. | There are no current candidates to rank yet. |
| 7 | Do not build an x64dbg plan until a current candidate exists. | Avoids debugger risk without a watch target. |
| 8 | If adding a scan planner, keep it Python-first with JSON/Markdown artifacts. | Preserves repo workflow policy and resumability. |
| 9 | Keep `frozen-snapshot` separate from `live-proof` if debugger pause work resumes. | Prevents over-promoting snapshot evidence. |
| 10 | Promote nothing until API-now vs memory/chain-now, multi-pose, restart validation, and same-target `ProofOnly` pass. | Maintains movement/navigation safety. |

