# Static-chain offline targeted owner analysis — 2026-05-26

## Verdict

Static player-actor coordinate chain solved: **false**.

This is an offline/candidate-only analysis using tracked repository evidence. It does not use live process reads, x64dbg attach, watchpoints, movement, Cheat Engine, provider writes, or memory writes.

The best next offline target is the historical access-proven owner shape from PID `63412`: object/base `0x20005B304E0` with coordinate fields at `+0x320/+0x324/+0x328`, because it is the only known evidence that narrows the problem from value-hit recovery to an owner/field relationship. It is historical single-epoch evidence only and must not be promoted.

The best current resume constraint is from `docs/recovery/current-truth.md`: the latest proof anchor is historical, ChromaLink is stale, and no current-PID actor/static-chain candidate is active. Therefore all absolute addresses below are either historical shape clues or current-epoch proof anchors only.

## Evidence sources reviewed

- `docs/recovery/current-truth.md`
- `docs/handoffs/2026-05-13-1231-compact-static-pointer-chain-resume.md`
- `docs/handoffs/2026-05-15-0310-static-chain-offline-readonly-handoff.md`
- `docs/recovery/static-coordinate-chain-10-phase-plan-2026-05-21.md`
- `docs/recovery/x64dbg-pointer-chain-workflow.md`
- `docs/recovery/x64dbg-static-coord-chain-discovery-status-2026-05-12.md`
- Commit evidence: `0d7fea4` current-PID proof anchor recovery for PID `42508`
- Commit evidence: `9bda0ee` PID `28248` proof readiness restored while actor/static-chain blockers remained

## Candidate inventory

| Candidate | Epoch / source | Classification | Support / tracking | Static-chain value | Known failure / limitation |
|---|---|---|---|---:|---|
| `0x20005B304E0 + 0x320/+0x324/+0x328` -> coord field `0x20005B30800` | PID `63412`, 2026-05-12 x64dbg access capture status doc | actor-like owner candidate | access-proven coordinate owner/base relationship; single historical epoch | 78/100 | Historical after logout/relog; no current-PID reacquisition; no module/static root; no restart validation |
| `0x1FF94EC0000` family, moving slots `0x1FF94EC8B80 -> 0x1FF94EC8DC0 -> 0x1FF94EC93D0` | PID `60628`, May 13 three-pose ranking | moving-slot family | support `3`; track max error `6.0937500165891834e-05` | 70/100 | Excellent displacement tracking but slots move; pointer-family scan found heap refs only and no module hits |
| `0x1FF08502BC8` | PID `60628`, May 13 three-pose ranking | actor-like/scene-object candidate, not proven owner | support `3`; track max error `0.004333593749834108`; avg delta `0.003232356770846915` | 58/100 | x64dbg access-proven, but likely UI/scene-object metadata path; no static owner/root |
| `0x1FD21900420` from `api-family-hit-000001` | PID `42508`, commit `0d7fea4` | proof/API buffer | support `3`; best max abs distance `0.0077781250001862645`; ProofOnly passed for that epoch | 42/100 | Movement-grade current proof anchor only; not actor-chain truth; stale after process epoch change |
| `0x2D409F3BBE0` | PID `28248`, `current-truth.md` / commit `9bda0ee` | proof/API buffer, historical/latest proof epoch depending artifact time | historical ProofOnly passed; later target drift documented | 25/100 | Current-truth marks it historical only; no current actor/static-chain candidate |
| `0x27B1ED850C0` from `api-family-hit-000001` | PID `27552`, May 15 handoff | proof/API buffer | support `6`; ProofOnly/current anchor valid for that epoch | 36/100 | Current target proof anchor only; no static root; no x64dbg live attach approved in that handoff |
| `0x1FF07570000` family / `0x1FF07574839`, `0x1FF07575346`, `0x1FF0757215A` | PID `60628`, May 13 handoff | destination/copy-page family | unaligned copy/destination evidence | 45/100 | Needs grouped snapshots and `--scan-stride 1`; no module root |
| `0x1FF6D600020 + 0x28` | PID `60628`, May 13 handoff | source-copy buffer | around `rift_x64.exe+0x47D408`; shape clue | 40/100 | Heap-local/source-copy clue only; not promoted |
| transient `0x1FF392*`, `0x1FF406*`, `0x1FF841*` leads | PID `60628` | rejected/noise | demoted after third pose | 10/100 | Stationary/false-positive behavior; do not use as primary target |

## Candidate classification details

### 1. Historical owner-shape candidate: `0x20005B304E0 + 0x320/+0x324/+0x328`

This is the best offline static-chain lead because it contains an observed object/base plus coordinate field offsets. It is not a static chain, but it is the most specific owner-layout shape currently documented.

Recommended offline interpretation:

- likely owner base: `0x20005B304E0` for the historical PID `63412` epoch only;
- likely coordinate offset: `+0x320` X, `+0x324` Y, `+0x328` Z;
- likely role: actor-like coordinate owner or close coordinate-bearing object;
- best use: shape template for reacquisition and future access-provenance capture;
- missing evidence: current-PID reacquisition, module/RVA/static-owner root, multi-pose current validation, restart validation.

### 2. Moving-slot family: `0x1FF94EC0000`

This is the best displacement-tracking family from PID `60628`. The moving slots are valuable because they may show copy/storage topology better than a single exact heap address.

Recommended offline interpretation:

- likely owner base: unknown;
- likely coordinate offset: unknown;
- likely role: moving copy/destination family or dynamic slot family;
- best use: current-PID reacquisition pattern and neighborhood scan seed;
- missing evidence: stable owner base, field offset, access provenance, static root.

### 3. Exact three-pose candidate: `0x1FF08502BC8`

This remains useful but secondary. It tracked across three poses, but previous notes suspect UI/scene-object metadata rather than a true player-actor coordinate owner.

Recommended offline interpretation:

- likely owner base: unknown;
- coordinate offset: unknown;
- likely role: actor-like/scene-object metadata candidate;
- best use: compare against `0x1FF94EC0000` and `0x20005B304E0 + 0x320` shape;
- missing evidence: proof that it belongs to player actor and not a mirror/UI/scene layer.

## Negative evidence reuse

The previous broad pointer-family scan should not be repeated as-is because it already scanned `14` seeds and `67` targets with `0` module hits, `0` `rift_x64.exe` hits, and heap refs only. Repeating that same scan shape would likely burn time on stale heap-only topology.

Use the negative result as a filter:

1. Do not promote heap-only references.
2. Do not treat proof/API buffers as actor ownership.
3. Prefer owner-layout or access-provenance evidence over more raw coordinate value scans.
4. Search around candidate owner bases and field offsets, not arbitrary coordinate hits.
5. For future current-PID work, first reacquire an actor-like candidate, then inspect owner-neighborhood pointer slots and module-like fields before pointer-family expansion.

## Narrower recommended offline search shape

When current-PID evidence exists again, use this shape:

1. Reacquire current proof/API anchor only as a freshness gate.
2. Find candidate coordinate-bearing structures that resemble the historical `owner + 0x320/+0x324/+0x328` pattern.
3. Around candidate owner bases, inspect nearby pointer-sized fields, vtable-like values, repeated stride/object patterns, and actor-adjacent floats.
4. Generate resolver candidates only from module/RVA/static-owner provenance, not raw heap refs.
5. Validate candidates against API-now vs chain-now across displaced poses.

## Future access-provenance target

Recommended future target, not executed:

| Field | Value |
|---|---|
| Target type | current-PID coordinate-bearing field matching historical `owner + 0x320/+0x324/+0x328` shape |
| Historical template | owner `0x20005B304E0`, coordinate field `0x20005B30800` |
| Preferred watch window | 12-byte XYZ window at current candidate coordinate field |
| Scalar fallback | X field only, if 12-byte watch is unsafe/unavailable |
| Why this target | It is more actor-owner-like than API/proof buffers because it has an observed owner/base plus field offset relation |
| Required event capture | instruction pointer, module/RVA, disassembly, register context, memory operand, derived owner/base pointer, field offset, access type, API-now coordinate, memory-now coordinate |

Do not watch `0x1FD21900420`, `0x27B1ED850C0`, or `0x2D409F3BBE0` as primary targets unless no actor-like candidate exists, because those are proof/API anchor style addresses and risk proving only a mirror buffer.

## Promotion status

| Gate | Status |
|---|---|
| Static chain solved | false |
| Candidate-only | true |
| Module/static root found | false |
| Restart-stable | false |
| Movement/navigation eligible from static chain | false |
| Current in-world target available | false per current-truth |
| ChromaLink/API-now freshness | blocked/stale per current-truth |
| Best single future access-provenance target | current-PID coordinate-bearing field matching `owner + 0x320/+0x324/+0x328` historical shape |

## Next required live/current-epoch evidence

Before any promotion or movement use:

1. Restore a live in-world RIFT target and ChromaLink freshness.
2. Reacquire exact PID/HWND/process start/module base.
3. Run same-target current coordinate recovery and ProofOnly.
4. Find a current-PID actor-like candidate, not just an API/proof buffer.
5. If explicitly approved later, run one bounded access-provenance capture against the current candidate 12-byte XYZ field.
6. Ingest the event into repo-owned tooling.
7. Build a module/RVA/static-owner resolver candidate.
8. Validate chain-now vs API-now across displaced poses.
9. Restart/relog and prove the resolver survives.
10. Run final ProofOnly before any movement/navigation eligibility.

## Validation status

Offline repository evidence review only. No local commands were run by ChatGPT in `C:\RIFT MODDING\RiftReader`.

Required local validation before treating this as a clean working-tree patch:

```powershell
python -m py_compile scripts/*.py
python scripts/rift_workflow.py generated-output-guard
git diff --check
```
