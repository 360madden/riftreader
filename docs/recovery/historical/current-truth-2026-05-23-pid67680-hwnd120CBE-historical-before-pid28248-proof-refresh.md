# Current RIFT live truth — PID 67680 proof anchor current, actor chain candidate-only

Updated UTC: `2026-05-21T16:30:46Z`
Repo: `C:\RIFT MODDING\RiftReader`

## Verdict

The current RIFT target is **in-world and proof-anchor current** for PID `67680` / HWND `0x120CBE`. Same-target `ProofOnly` passed for proof anchor `0x242D3DEF010`.

The player actor static coordinate chain is **not promoted**. The best actor-like lead is `0x242E9932F70` under owner `0x242E9932D70 + 0x200`, and it remains **candidate-only** until access/static provenance, resolver validation, restart/relog validation, and final ProofOnly gates pass.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `67680` |
| HWND | `0x120CBE` |
| Process start UTC | `2026-05-21T14:38:42.127583Z` |
| Module base | `0x7FF6A24B0000` |
| Proof anchor | `0x242D3DEF010` |
| Proof status | `current-target-proofonly-passed` |
| Latest proof coordinate | `X=7371.48876953125`, `Y=868.26171875`, `Z=2997.662109375` |
| Proof artifact | `docs/recovery/current-proof-anchor-readback.json` |

## Actor-chain candidate status

| Field | Value |
|---|---|
| Candidate | `0x242E9932F70` |
| Candidate ID | `api-family-hit-000001` |
| Classification | `offset-corrected-current-coordinate-candidate` |
| Owner hypothesis | `0x242E9932D70` |
| Coord offset from owner | `+0x200` |
| Fresh API reference | `X=7365.830078`, `Y=870.959961`, `Z=3001.300049` |
| Candidate memory value | `X=7365.82958984375`, `Y=872.4995727539062`, `Z=3001.297607421875` |
| Direct max abs delta | `1.5396117539062288` |
| Offset-corrected max abs delta | `0.004650953124837542` |
| Promotion | `candidate-only`, `promotionEligible=false` |
| Readback artifact | `scripts/captures/candidate-readback-currentpid-67680-20260521-160728-953877/candidate-readback-summary.json` |

## Static-chain blockers

- `blocked-no-debugger-access-provenance`: current authorization allows read-only process reads, but no debugger/watchpoint evidence.
- `no-module-rva-static-owner-resolver-promoted`: no restart-stable resolver exists yet.
- `not-restart-validated`: current-PID evidence has not survived restart/relog.
- `riftscan-milestone-review-blocked-no-supported-candidate`: RiftScan provider lane has no supported selected candidate artifact for this target.
- Actor yaw/facing remains blocked until current-target behavior-backed proof is separately revalidated.


## No-debug priority parent-lane result

| Field | Value |
|---|---|
| Pointer-family scan | `scripts/captures/pointer-family-scan-20260521-161945-968614/summary.json` |
| Scanned targets | `2` |
| Targets with hits | `1` |
| Module hits | `0` |
| rift_x64 hits | `0` |
| Exhaustion report | `scripts/captures/priority-scan-exhaustion-report-20260521-162011-122035/summary.json` |
| Verdict | `priority-lane-exhausted-no-static-root` |

Interpretation: the current no-debug priority parent lead does not produce module/static-root evidence. This narrows the safe no-debug lane but does not promote or invalidate the actor-like candidate.


## Broadened no-debug root-lane result

| Scan | Targets | Targets with hits | Module hits | rift_x64 hits | Verdict |
|---|---:|---:|---:|---:|---|
| Priority parent leads | `2` | `1` | `0` | `0` | `priority-lane-exhausted-no-static-root` |
| Non-priority parent leads | `6` | `3` | `0` | `0` | `priority-lane-exhausted-no-static-root` |
| Owner + coord-storage addresses | `12` | `0` | `0` | `0` | `no owner/static reference hits` |

Artifacts:

| Artifact | Path |
|---|---|
| Non-priority parent scan | `scripts/captures/pointer-family-scan-20260521-162245-598545/summary.json` |
| Non-priority exhaustion report | `scripts/captures/priority-scan-exhaustion-report-20260521-162331-293407/summary.json` |
| Owner/coord-storage scan | `scripts/captures/pointer-family-scan-20260521-162400-107887/summary.json` |

Interpretation: the current no-debug parent/owner root lanes are exhausted for this evidence set. The actor-like coordinate candidate remains useful candidate evidence, but these scans do not yield a module/RVA/static-owner resolver.

## Safety ledger for latest update

| Operation | Used? |
|---|---:|
| Read-only target discovery | Yes |
| Read-only API/reference scan | Yes |
| Read-only process memory read | Yes |
| x64dbg/debugger attach | No |
| Breakpoints/watchpoints | No |
| Cheat Engine | No |
| Movement/input | No |
| Memory writes | No |
| Provider writes | No |
| Git mutation | No |

## Current artifacts

| Artifact | Path |
|---|---|
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| Latest handoff | `docs/handoffs/2026-05-21-1211-readonly-actor-chain-currentpid-67680-handoff.md` |
| Actor candidate readback | `scripts/captures/candidate-readback-currentpid-67680-20260521-160728-953877/candidate-readback-summary.json` |
| Owner neighborhood | `scripts/captures/pointer-owner-neighborhood-inspector-20260521-160610-600819/summary.json` |
| Root-signature sweep | `scripts/captures/root-signature-module-hint-sweep-20260521-160610-674508/summary.json` |
| Root-family classifier | `scripts/captures/root-signature-family-classifier-20260521-160834-290054/summary.json` |
| RiftScan milestone review | `scripts/captures/riftscan-milestone-review-20260521-163007.json` |
| Actor-chain no-debug status | `scripts/captures/actor-chain-no-debug-status-20260521-162848-574766/summary.json` |

## Required next step

Use `python .\scripts\actor_chain_no_debug_status.py --json` as the first no-debug status gate in the next session. Promotion remains blocked until access/static provenance, resolver validation, restart/relog validation, and final ProofOnly gates pass. Do not promote the actor static chain until resolver, multi-pose API-now vs chain-now, restart/relog, and final ProofOnly gates pass.
