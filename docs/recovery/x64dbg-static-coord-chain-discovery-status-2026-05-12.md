# x64dbg static coordinate pointer-chain discovery status

Status date: 2026-05-12

## Verdict

The workflow foundation for stable static coordinate pointer-chain discovery is
now in place, but the actual stable chain is **not yet discovered or promoted**.

Current evidence is still candidate-only:

- current live target observed during this slice: PID `63412`, HWND `0xB70082`,
  process start UTC `2026-05-12T15:53:24.4410214Z`;
- fresh ChromaLink world-state API was healthy/fresh during the slice and
  reported `X=7376.41`, `Y=863.71`, `Z=2989.88`;
- newest current-PID family-scan seed for static-chain planning:
  `api-family-hit-000001 @ 0x78BF4FE420`;
- the older promoted proof anchor for PID `57656` is stale for this process
  epoch and must not be used as current movement truth.

Live x64dbg approval was granted later in the same conversation. The first live
capture downranked `0x78BF4FE420` as stack/scratch-like evidence and produced a
stronger access-proven coordinate candidate at `0x20005B30800`. The observed
coordinate owner/base object was `0x20005B304E0`, with coordinate fields at
`+0x320/+0x324/+0x328`. See
`docs/recovery/x64dbg-live-coordinate-access-capture-2026-05-12.md`.

## Time spent

| Measurement | Value |
|---|---|
| Measured start for this continuation slice | 2026-05-12 18:37:07 EDT |
| Measured completion checkpoint | 2026-05-12 18:44:08 EDT |
| Duration | 7 minutes 1 second |
| Measurement basis | From the first current live target/API grounding output in this continuation to the post-test validation timestamp. |

Earlier x64dbg Automate setup action-package timing remains documented in
`docs/recovery/x64dbg-automate-readonly-helper-2026-05-12.md`.

## Completed action map

| # | Action | Result |
|---:|---|---|
| 1 | Generate a real plan from a freshly grounded current coord candidate | Done: current target/API were rechecked and a plan was generated for `api-family-hit-000001 @ 0x78BF4FE420`. Artifact: `scripts\captures\x64dbg-coord-chain-plan-20260512-224303-882775\coord-chain-plan-summary.json`. |
| 2 | Add an access-event ingester | Done: `scripts\x64dbg_access_event_ingest.py` plus implementation and tests. |
| 3 | Keep live x64dbg attach gated | Done: planner/ingester remain artifact-only/offline; docs and AGENTS policy require current-turn approval before live attach. |
| 4 | Add chain-readback schema fields | Done at candidate-packet level: `derivedChain`, `rootRva`, `offsets`, `fieldOffsets`, instruction module/RVA provenance, validation gates, and blockers are documented/emitted. |
| 5 | Build no-x64dbg chain resolver after first good candidate | Partially done as an offline resolver harness: `scripts\x64dbg_static_chain_resolve.py` can validate a real `derivedChain` packet against a module map and offline memory image. Real live/current resolver use remains blocked until x64dbg captures module/RVA/static-owner evidence. |
| 6 | Require API-now vs chain-now comparison | Done as a documented promotion gate and candidate blocker. The ingester records API-now vs memory-now deltas; final chain-now validation remains a separate resolver step. |
| 7 | Keep evidence candidate-only until multi-pose/restart proof | Done: emitted packets keep `movementProofEligible=false` and block restart/runtime-readback/proof-only promotion. |
| 8 | Add restart-validation artifacts/gates | Done in docs and candidate schema; still blocked until a real chain survives restart/relog. |
| 9 | Avoid active MCP until shim/allowlist exists | Done: no x64dbg MCP config was added; helper/docs keep MCP inactive. |
| 10 | Commit each coherent validated workflow slice | This slice is ready for explicit staging, commit, and push after final diff check; the final commit hash is expected to be recorded in chat. |

## New files and touched surfaces

| Path | Purpose |
|---|---|
| `scripts/rift_live_test/x64dbg_access_event_ingest.py` | Offline/manual x64dbg access-event ingester. |
| `scripts/x64dbg_access_event_ingest.py` | Thin operator wrapper. |
| `scripts/test_x64dbg_access_event_ingest.py` | Regression tests for safety and validation gates. |
| `scripts/rift_live_test/x64dbg_static_chain_resolve.py` | Offline static-chain resolver harness for real `derivedChain` packets. |
| `scripts/x64dbg_static_chain_resolve.py` | Thin operator wrapper for the resolver harness. |
| `scripts/test_x64dbg_static_chain_resolve.py` | Resolver contract tests using synthetic offline memory images. |
| `docs/recovery/x64dbg-pointer-chain-workflow.md` | Added access-event ingester workflow and static-chain integration order. |
| `docs/recovery/x64dbg-automate-readonly-helper-2026-05-12.md` | Added follow-on ingester status. |
| `docs/recovery/README.md` | Added x64dbg helper index entries. |
| `AGENTS.md` | Added durable x64dbg static coord-chain invariant. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile ...x64dbg...` | Passed |
| `python scripts\test_x64dbg_snapshot_diff.py -v` | Passed: 5 tests |
| `python scripts\test_x64dbg_coord_chain_plan.py -v` | Passed: 4 tests |
| `python scripts\test_x64dbg_access_event_ingest.py -v` | Passed: 8 tests |
| `python scripts\x64dbg_access_event_ingest.py --self-test --json` | Passed and wrote a synthetic candidate-only packet |
| `python scripts\test_x64dbg_static_chain_resolve.py -v` | Passed: 7 tests |
| `python scripts\x64dbg_static_chain_resolve.py --self-test --json` | Passed and wrote a synthetic offline resolved-chain packet |
| `python scripts\x64dbg_static_chain_resolve.py --dry-run --json` | Blocked as expected with `dry-run-no-chain-resolved` |

## Resolver readiness

| Item | State | Notes |
|---|---|---|
| Candidate schema | Ready | Planner and ingester emit/accept `derivedChain`, `rootRva`, offsets, field offsets, instruction module/RVA provenance, validation gates, and promotion blockers. |
| Offline resolver harness | Ready | `scripts\x64dbg_static_chain_resolve.py` can resolve a real packet against a module map and offline memory image. |
| Real module/RVA/static-owner evidence | Missing | No approved x64dbg access-event capture has produced a real chain yet. |
| Live/current process chain readback | Not implemented | Intentionally not added until real chain evidence exists; current helper stays offline-only. |
| Promotion status | Blocked | Requires API-now vs chain-now, multi-pose, restart validation, and same-target ProofOnly. |
| Allowed next slice | Capture/ingest real events | Do not guess offsets or promote from heap-only watch addresses. |

## Current discovery progress

| Area | Progress | Notes |
|---|---:|---|
| Safe x64dbg local setup | 90% | x64dbg, x64dbg Automate client/plugin, read-only helper, and docs are in place. MCP is intentionally not active. |
| Coordinate candidate seed | 55% | Current-PID candidate `api-family-hit-000001 @ 0x78BF4FE420` exists, but it is single-scan candidate evidence. |
| Static-chain evidence capture | 20% | Planner and ingester are ready, but no approved live x64dbg access events have been captured yet. |
| Static-chain evidence capture | 40% | Approved live x64dbg captured coordinate access for `0x20005B30800` and object field relationship `0x20005B304E0 + 0x320/+0x324/+0x328`; still single-pose. |
| No-x64dbg chain resolver | 25% | Offline resolver harness and tests exist, but real live/current readback remains blocked until a stable root chain to `0x20005B304E0` is captured. |
| Movement/proof truth | 0% for static chain | No static chain has passed API-now vs chain-now, multi-pose, restart validation, and ProofOnly. |

Bottom line: the first disciplined x64dbg access-event capture has now narrowed
the problem from "find a coordinate address" to "find a stable root path to
object `0x20005B304E0`." The stable static coordinate pointer chain is still not
proven.

## Next gate

Do not promote or move from this evidence. The next meaningful step is:

1. refresh API-now and current PID/HWND;
2. use `api-family-hit-000001 @ 0x78BF4FE420` as the first watch seed;
3. only if explicitly approved, attach x64dbg to the exact target and capture
   12-byte XYZ access events across at least three poses;
4. ingest the manual events with `scripts\x64dbg_access_event_ingest.py`;
5. fill the `derivedChain` fields from real module/RVA/static-owner evidence;
6. run `scripts\x64dbg_static_chain_resolve.py` against that packet and a
   readback source;
7. only after that, add a live/current readback extension if the offline
   resolver proves the chain shape.
