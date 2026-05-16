# Offline static pointer-chain analysis — current PID coordinate proof

Generated UTC: `2026-05-15T08:03:22+00:00`
Scope: **offline/read-only artifact analysis only**. No live process memory read, no movement/input, no Cheat Engine, no x64dbg attach/watchpoints.

## Verdict

**Stable static pointer chain is still not discovered.** The current proof anchor is strong current-PID coordinate truth, but the artifacts still lack the missing static-chain requirements: a module/RVA or static-owner root, current-PID access instruction provenance, repo-owned chain readback, and restart/client-epoch validation.

| Item | Current evidence |
|---|---|
| Target | `rift_x64` PID `27552` / HWND `0x3411E2` |
| Candidate | `api-family-hit-000001` |
| Coord leaf | `0x27B1ED850C0` |
| Read region | `0x27B1ED85080` |
| XYZ field offsets | `+0x0/+0x4/+0x8` from coord leaf; `+0x40` from read region |
| Proof support | `6` poses |
| Max reference planar displacement | `26.48665969974286` |
| Max proof delta error | `0.008501171875195723` |
| Latest ProofOnly | `passed-proof-only` at `2026-05-15T07:49:25.137137+00:00` |
| Latest current coordinate | `X=7315.03076171875`, `Y=875.1163330078125`, `Z=3050.24462890625` |

## What was analyzed offline

| Artifact | Path | Finding |
|---|---|---|
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` | Current PID proof pointer is valid for PID `27552` only. |
| Proof anchor cache | `scripts/captures/telemetry-proof-coord-anchor.json` | Multi-pose proof has `6` support entries and displacement tracking. |
| Latest static-chain plan | `scripts/captures/x64dbg-static-chain-plan-safe-boundary-20260515-0727/coord-chain-plan-summary.json` | Planned, ready for current-turn approval only; no live debugger authorization. |
| Current region samples | `scripts/sessions/**/samples.ndjson` | Parsed `123` samples for region `0x27B1ED85080`. |
| Historical x64dbg ingest | `scripts/captures/x64dbg-access-event-ingest-20260514-221947-655978/summary.json` | Stale PID `23496` candidate only; instruction is `VCRUNTIME140.dll` `mov dword ptr ds:[rax+0x08], ecx`. |
| Offline resolver self-test | `scripts/x64dbg_static_chain_resolve.py --self-test --json` | Passed; proves helper contract only, not a RIFT chain. |

## Current proof/displacement evidence

| Pose | Candidate address | Ref X | Ref Y | Ref Z | Memory X | Memory Y | Memory Z |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | `0x27B1ED850C0` | `7340.9199` | `872.11` | `3055.8298` | `7340.9169921875` | `872.1109619140625` | `3055.825927734375` |
| 2 | `0x27B1ED850C0` | `7336.2598` | `872.74` | `3054.96` | `7336.25927734375` | `872.7384033203125` | `3054.958984375` |
| 3 | `0x27B1ED850C0` | `7331.5698` | `873.34` | `3054.45` | `7331.572265625` | `873.3389892578125` | `3054.44970703125` |
| 4 | `0x27B1ED850C0` | `7327.0098` | `873.86` | `3053.95` | `7327.01318359375` | `873.85595703125` | `3053.95458984375` |
| 5 | `0x27B1ED850C0` | `7327.0098` | `873.86` | `3053.95` | `7327.01318359375` | `873.85595703125` | `3053.95458984375` |
| 6 | `0x27B1ED850C0` | `7315.0298` | `875.12` | `3050.24` | `7315.03076171875` | `875.1163330078125` | `3050.24462890625` |

| Pose index | Reference planar delta | Candidate planar delta | Max abs delta error |
|---:|---:|---:|---:|
| 1 | `4.740578450991021` | `4.737710243783752` | `0.0028566406249410647` |
| 2 | `9.451360645430583` | `9.445522640468495` | `0.005373437499656575` |
| 3 | `14.03654266726683` | `14.02917670116551` | `0.008462109375159343` |
| 4 | `14.03654266726683` | `14.02917670116551` | `0.008462109375159343` |
| 5 | `26.48665969974286` | `26.481084277084847` | `0.008501171875195723` |

## Offline struct/neighborhood observations

The existing 140-byte readback region is useful for layout clues but **not sufficient to walk to a static root**.

| Observation | Value |
|---|---|
| Parsed samples | `123` |
| Unique 140-byte images | `13` |
| First sample UTC | `2026-05-15T02:24:05.0942261+00:00` |
| Last sample UTC | `2026-05-15T07:49:24.4282099+00:00` |
| Changing byte ranges | `0x40-0x42, 0x44-0x46, 0x48-0x49` |

### Changing float offsets

| Offset from region | Min | Max | Range | Latest |
|---|---:|---:|---:|---:|
| `0x40` | `7314.909180` | `7340.916992` | `26.007812` | `7315.030762` |
| `0x44` | `872.110962` | `876.268555` | `4.157593` | `875.116333` |
| `0x48` | `3050.244629` | `3055.825928` | `5.581299` | `3050.244629` |

Interpretation: the only meaningful changing float lane is `+0x40/+0x44/+0x48`, which is the proven XYZ triplet. That supports field layout, not static ownership.

### Stable pointer-like qwords inside the 140-byte neighborhood

| Offset from region | Latest qword | Delta from region | Delta from coord leaf | Delta from family base `0x27B1EC70000` | Stable |
|---|---|---:|---:|---:|---:|
| `0x68` | `0x27B1EC75C50` | `-0x10F430` | `-0x10F470` | `+0x5C50` | `True` |

Best offline lead: `region+0x68 -> 0x27B1EC75C50`. It is stable across parsed samples and lands inside the same current-PID heap/family range. Treat it as an **owner/container lead for future scans**, not as static truth.

## Historical x64dbg event assessment

| Field | Historical event |
|---|---|
| PID/HWND | `23496` / `0x2C1024` |
| Watch address | `0x27236F46750` |
| Candidate | `api-family-hit-000005` |
| Instruction module | `VCRUNTIME140.dll` |
| Instruction RVA | `0x1121C` |
| Instruction | `mov dword ptr ds:[rax+0x08], ecx` |
| Register base | `rax=0x27236F46750` |
| Field offset | `0x8` |
| Derived root kind | `pending-rift-module-root-not-proven` |

Conclusion: this is useful as a workflow proof, but weak as a static-chain lead. It is stale PID evidence, write-class/copy evidence, and the instruction is in `VCRUNTIME140.dll`, not `rift_x64.exe`. It does not answer the current chain questions for `0x27B1ED850C0`.

## Answer to the chain-discovery questions from current offline evidence

| Question | Offline answer |
|---|---|
| Which instruction accesses/writes the proven coord leaf? | **Unknown for current PID.** No current-PID x64dbg access event exists for `0x27B1ED850C0`. |
| Which register holds owner/component base? | **Unknown.** Existing stale event used `rax` as the copied write destination; that is not owner provenance. |
| What field offset reaches XYZ? | Proven leaf layout is `X +0x0`, `Y +0x4`, `Z +0x8`; relative to read region `0x27B1ED85080`, XYZ starts at `+0x40`. |
| Is the instruction module-relative inside `rift_x64.exe`? | **Not proven.** The only ingested historical event was `VCRUNTIME140.dll+0x1121C`; current plan still needs a `rift_x64.exe` module/RVA or static-owner event. |

## Blockers to stable static-chain promotion

- `no current-PID x64dbg access events for 0x27B1ED850C0`
- `no module/RVA root or static-owner root in current artifacts`
- `existing historical x64dbg event is stale PID 23496 and VCRUNTIME140.dll write helper, not a rift_x64.exe owner/source instruction`
- `offline snapshots cover only the 140-byte coord neighborhood, not a full pointer-reference memory image`
- `restart/client-epoch validation missing for any chain shape`

## Offline leads ranked

| Rank | Lead | Use | Risk |
|---:|---|---|---|
| 1 | Stable same-family qword `region+0x68 -> 0x27B1EC75C50` | Seed future parent/owner scans around `0x27B1EC75C50` and references to it. | Heap/current-PID only; not static. |
| 2 | Proven 12-byte XYZ leaf `0x27B1ED850C0` | Best future watch target if live debugger is explicitly reapproved. | Current PID only; no static root. |
| 3 | Prior PID x64dbg workflow artifacts | Reuse event schema and guardrails. | Stale PID and VCRUNTIME copy instruction. |
| 4 | Static-chain resolver self-test | Confirms resolver contract. | Synthetic only; no live chain evidence. |

## Recommended offline-only next work

1. Add/prepare an offline parent-slot/reference analysis packet for `0x27B1EC75C50` using existing samples only where possible.
2. Do **not** call that pointer an owner until a current-PID memory/reference scan proves it.
3. Keep current watch target as `0x27B1ED850C0` with size `12` for any future approved x64dbg session.
4. In the next approved live debugger session, reject copy-helper hits unless caller/owner path is captured.
5. Prefer hits inside `rift_x64.exe` or a chain that yields `rift_x64.exe + RVA -> offsets -> XYZ`.
6. Require at least three displaced poses for chain-now vs API-now tracking.
7. Require restart/relog validation before static promotion.
8. Keep ProofOnly as the final same-target movement gate.

## Generated artifacts

| Artifact | Path |
|---|---|
| Machine summary | `scripts/captures/offline-static-chain-analysis-currentpid-27552-20260515-080322/summary.json` |
| Human report | `docs/recovery/offline-static-chain-analysis-currentpid-27552-2026-05-15.md` |
