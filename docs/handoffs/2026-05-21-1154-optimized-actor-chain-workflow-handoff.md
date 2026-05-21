# **✅ HANDOFF — Optimized player actor coordinate-chain workflow**

Generated: `2026-05-21T15:54Z`  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`  
Purpose: preserve the workflow correction that separates movement-safe proof-anchor recovery from player actor static-chain discovery.

## Verdict

The coordinate-chain workflow has been corrected to be **provenance-first** after the first credible actor-like candidate is found.

Do not keep repeating broad coordinate value scans once:

1. the current proof anchor is valid for the current PID/HWND; and
2. a credible actor-like candidate/owner hypothesis exists.

At that point, continue through owner layout, bounded access provenance, normalized instruction/module/RVA context, resolver generation, API-now vs chain-now validation, restart validation, and promotion.

## Files in this slice

| File | Purpose |
|---|---|
| `agents.md` | Root agent policy now forbids blending proof anchors with actor static-chain truth and bounds x64dbg usage |
| `docs/assistant-operating-policy.md` | Adds proof-anchor vs actor-chain split and bounded access-provenance rules |
| `docs/recovery/current-pid-coordinate-family-recovery-policy.md` | Clarifies current-PID family scanning is for proof-anchor recovery, not already-selected actor-chain provenance |
| `docs/recovery/static-coordinate-chain-10-phase-plan-2026-05-21.md` | Rewrites the 10-phase plan around target, proof gate, actor candidate, owner layout, access provenance, resolver, validation, restart, promotion |
| `docs/recovery/optimized-player-actor-coordinate-chain-workflow.md` | New durable workflow authority and anti-regression checklist |
| `docs/handoffs/2026-05-21-1143-currentpid-67680-actor-coordinate-chain-compact-handoff.md` | Current-PID handoff now points to the optimized workflow |
| `docs/handoffs/2026-05-21-1154-optimized-actor-chain-workflow-handoff.md` | This handoff |

## Corrected workflow

```text
target lock
  -> proof-anchor safety gate
  -> actor-like candidate family
  -> owner-layout hypothesis
  -> bounded x64dbg access provenance
  -> normalized access event
  -> module/RVA or static-owner resolver
  -> API-now vs chain-now validation
  -> restart validation
  -> promotion
```

## Strong anti-regression rules

| Rule | Required behavior |
|---|---|
| Proof anchor is not actor chain | Treat proof/API-family anchors as safety gates only |
| Broad scan has a stopping point | Stop broad value scans once a credible actor-like candidate exists |
| Static chain is provenance-first | Use owner/access/module/RVA evidence, not just value matches |
| x64dbg is bounded | `stop-context` first, then at most one short hardware watchpoint per explicit decision |
| Access events are candidate-only | Normalize and validate before resolver promotion |
| Absolute addresses are session evidence | Never promote raw heap addresses as restart-stable truth |
| API-now vs chain-now is mandatory | Validate immediately around fresh API probes |
| Restart/relog validation is mandatory | Current-PID-only success is not static-chain truth |

## Current live context preserved from prior handoff

| Item | Value |
|---|---|
| Current target at prior handoff | PID `67680`, HWND `0x120CBE` |
| Current proof anchor | `0x242D3DEF010`, proof/API-family safety anchor |
| Actor-like candidate lead | `0x242E9932F70` |
| Hypothesized owner base | `0x242E9932D70` |
| Owner coord offset | `+0x200` |
| Static chain status | Not proven |
| x64dbg attach in this slice | Not run |
| CE | Not used |
| Movement/input | Not sent |

Before resuming live work, rediscover the current target; the PID/HWND above is historical unless freshly re-confirmed.

## Validation for this slice

Run before commit:

```powershell
git --no-pager diff --check
python -m unittest scripts.test_coordinate_candidate_semantic_classifier scripts.test_x64dbg_coord_chain_plan
```

Expected: `diff --check` clean except line-ending warnings; unit tests pass.

## Resume recommendation

1. Reconfirm current RIFT target.
2. Run `python .\scripts\coordinate_recovery_status.py --json`.
3. If still current, do not broad-scan again.
4. Resume with the optimized workflow:
   - owner-layout review for `0x242E9932F70`;
   - x64dbg `stop-context` only;
   - then one bounded hardware-read watchpoint only if stop-context is safe.
