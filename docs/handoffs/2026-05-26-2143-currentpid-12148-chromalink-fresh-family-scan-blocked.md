# RiftReader handoff — current PID 12148 ChromaLink fresh, flat family scan blocked

Created local: `2026-05-26T21:43:00-04:00`
Created UTC: `2026-05-27T01:43:00Z`

## Direct result

RIFT and ChromaLink are live/fresh for current PID `12148`, but current proof-anchor recovery is still blocked because the tracked proof pointer targets historical PID `28248` and the first read-only flat current-PID family scan found no XYZ triplets within the 300s budget.

This remains **proof-anchor recovery**, not promoted player actor static-chain discovery.

## Current observed target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `12148` |
| HWND | `0x640C0C` |
| Window title | `RIFT` |
| Responding | `true` |
| Process start | `2026-05-26T21:17:01.2653526-04:00` |

## Current API-now truth

| Field | Value |
|---|---|
| Provider | ChromaLink `/api/v1/riftreader/world-state` |
| Provider status | `ready=true`, `healthy=true`, `fresh=true`, `stale=false` |
| Player position available | `true` |
| Position | `X=7259.83`, `Y=821.44`, `Z=2994.06` |
| Observed UTC | `2026-05-27T01:35:03.8538798Z` |
| RiftReader reference artifact | `scripts/captures/chromalink-world-state-reference-20260527-013525-054182/rift-api-reference-currentpid-12148-20260527-013525-151064.json` |

## Proof-anchor state

| Item | Status |
|---|---|
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| Status | `blocked-target-drift` |
| Artifact target | PID `28248`, HWND `0x2302BC` |
| Live target | PID `12148`, HWND `0x640C0C` |
| Required rule | Treat PID `28248` addresses as historical hints only |

## Read-only flat scan result

| Field | Value |
|---|---|
| Command class | `scan_current_pid_coordinate_family.py` |
| Safety | no movement, no input, no CE, no x64dbg, no provider writes |
| Reference | fresh ChromaLink reference above |
| Tolerance | `0.25` |
| Stride | `1` |
| Max seconds | `300` |
| Result | `blocked` |
| Blocker | `no_xyz_triplets_near_reference_found` |
| Warning | `scan time budget reached at 300s` |
| Bytes scanned | `306184192` |
| Hits | `0` |
| Summary | `scripts/captures/family-scan-currentpid-12148-20260527-013552-304834/family-scan-summary.json` |

## Dry-run recovery plan

Dry-run plan passed and wrote:

`C:\RIFT MODDING\RiftReader\scripts\captures\recover-currentpid-coord-anchor-fast-dryrun-12148-20260527-014221-114191\summary.json`

Key dry-run warnings:

- `current-proof-artifact-target-pid-drift:28248!=12148`
- `current-proof-artifact-target-hwnd-drift:0x2302BC!=0x640C0C`
- `movement-not-approved; execution blocks before displaced-pose validation`

## Movement / displacement recommendation

Movement is **not recommended yet**.

Displacement stimulus testing becomes optimal only after a current-PID candidate file exists and at least one candidate initially matches fresh API-now readback. The next proof question is not displacement yet; it is candidate reacquisition via prioritized scan-plan ranges.

## Next optimal action

Ask for explicit approval to run the no-movement fast recovery execution through the target-control/visual-gate and scan-plan batch stages:

```powershell
cd "C:\RIFT MODDING\RiftReader"
python .\scripts\recover_current_pid_coord_anchor_fast.py --pid 12148 --hwnd 0x640C0C --process-name rift_x64 --scan-stride 1 --scan-tolerance 2.0 --scan-plan-top-count 20 --max-seconds-per-scan-range 45 --execute --json
```

Do **not** add `--movement-approved`, `--allow-current-truth-update`, or `--run-proofonly` unless separately approved. Without `--movement-approved`, the helper should block before displaced-pose validation.

## Safety ledger

| Operation | Status |
|---|---|
| ChromaLink HTTP read | Used |
| ChromaLink provider repo writes | Not used in this resume pass |
| Current-PID process memory read | Used by flat scan |
| Movement/game input | Not used |
| Target-control/visual-gate execution | Not executed after dry-run; approval needed |
| x64dbg/debugger attach | Not used |
| Breakpoints/watchpoints | Not used |
| Cheat Engine | Not used |
| Memory writes | Not used |
| Proof promotion/current-truth update | Not used |
| Git stage/commit/push | Not used |

## Top 10 recommended next actions

1. Approve the no-movement fast recovery execution if you want the next optimal proof-recovery step.
2. Keep PID `28248` as historical only; do not reuse its absolute addresses as current truth.
3. Use the fresh ChromaLink API-now reference immediately before each scan/validation step.
4. Prefer scan-plan batch over repeating flat full-process scans; the flat scan already timed out with no hits.
5. Stop before displacement validation unless a current-PID candidate JSONL is produced.
6. Recommend movement/displacement only after initial candidate readback matches API-now.
7. Keep proof-anchor recovery separate from actor static-chain promotion.
8. Do not use x64dbg until a candidate/owner hypothesis is ready and explicitly approved.
9. Do not run `ProofOnly` or update current truth until multi-pose validation succeeds and approval is explicit.
10. If scan-plan batch misses, inspect alternate axis/order/object-family strategy before broad debugger work.
