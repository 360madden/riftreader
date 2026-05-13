# Handoff: owner/type source-chain lead for navigation proof recovery

Generated: 2026-05-13 17:53 EDT / 2026-05-13 21:53 UTC  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`

## TL;DR

Navigation is still **blocked** because same-target `ProofOnly` is target-drifted,
but the read-only source-chain evidence improved. The stable narrow coordinate
family now has a concrete low-noise owner/type relationship:

```text
low-noise type marker rift_x64.exe+0x26AAE70
  -> owner base 0x268D753AE30
  -> [owner + 0x10] = 0x268DF21ED20
  -> stable offset-corrected coord candidate family 0x268DF21E000
```

This is **not** a static pointer chain yet. It is a better source-chain lead for
future proof-anchor recovery.

## Current gate state

| Gate | State |
|---|---|
| Target | `rift_x64.exe` PID `2928`, HWND `0xC0994` |
| Target-control | Passed earlier in this session |
| Visual gate | Passed earlier in this session |
| ProofOnly | `blocked-target-drift`; stale proof pointer PID `57656`, HWND `0x5417BC` |
| Movement/navigation | Blocked |
| CE/x64dbg | Not used in this slice |

## What changed in code

| File | Change |
|---|---|
| `scripts/rift_live_test/owner_type_instance_inspector.py` | New read-only helper that inspects low-noise type-marker scan hits, reads owner windows, follows `[owner + coordPointerOffset]`, and labels candidate-owning instances. |
| `scripts/owner_type_instance_inspector.py` | Thin CLI wrapper. |
| `scripts/test_owner_type_instance_inspector.py` | Unit tests for hit extraction, candidate-pointer labeling, and vec3 filtering. |
| `docs/recovery/current-truth.md` | Updated with the owner/type source-chain lead. |

## New evidence

| Artifact | Result |
|---|---|
| `scripts/captures/pointer-family-scan-20260513-214606-072853/summary.json` | Read-only scan of owner/module-pointer hints; module marker `0x7FF71F43AE70` had only `3` hits. No module/static root hits. |
| `scripts/captures/owner-type-instance-inspector-20260513-215227-155967/summary.json` | Inspected the `3` low-noise marker instances; exactly `1` candidate owner. |
| `scripts/captures/pointer-family-scan-20260513-215245-916937/summary.json` | Pointer scan of owner base found one heap ref at `0x268D7539700`; scanning that ref-storage address found no parent refs. |
| `scripts/captures/pointer-owner-neighborhood-inspector-20260513-215307-379484/summary.json` | Confirmed `0x268D7539700 -> 0x268D753AE30`; same heap region also contains direct `0x268DF21ED20` relation. |

## Important discovered structure

| Field | Value |
|---|---|
| Low-noise marker | `0x7FF71F43AE70` = `rift_x64.exe + 0x26AAE70` |
| Candidate owner base | `0x268D753AE30` |
| Coord pointer storage | `0x268D753AE40` |
| Coord pointer expression | `[0x268D753AE30 + 0x10] = 0x268DF21ED20` |
| Stable candidate family | `0x268DF21E000` |
| Candidate vec3 read | `X=7397.59228515625`, `Y=866.78271484375`, `Z=3023.4453125` |
| Parent heap ref | `0x268D7539700 -> 0x268D753AE30` |
| Static/module root | Not found |

## Interpretation

| Finding | Meaning |
|---|---|
| Type marker has only `3` hits | Much less noisy than the dense `0x268BEF2C000` family. Good source-chain lead. |
| Exactly one type-marker instance points at the stable candidate | Strengthens `0x268D753AE30` as the current player-related owner candidate. |
| Parent ref is heap-local and has no parent refs | Chain still stops in heap; no static/root chain yet. |
| Coord read is offset-corrected, not direct API coordinate | Still candidate-only; do not navigate from it. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile scripts\rift_live_test\owner_type_instance_inspector.py scripts\owner_type_instance_inspector.py scripts\test_owner_type_instance_inspector.py` | Passed |
| `python scripts\test_owner_type_instance_inspector.py -v` | Passed, `3/3` |
| `python scripts\owner_type_instance_inspector.py ... --json` | Passed; wrote owner/type artifact |
| `python scripts\navigation_resume_status.py --json` | Expected `blocked-for-live-input`; proof not promoted and ProofOnly still blocked. |
| `python scripts\riftscan_milestone_review.py --compact-json --write-summary --write-markdown` | Expected strategy-blocked result; wrote `scripts/captures/riftscan-milestone-review-20260513-215522.json`. |

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Navigation remains blocked
until same-target `ProofOnly` passes for PID `2928`, HWND `0xC0994`. Current best
coordinate recovery seed is the narrow stable family `0x268DF21E000`, with owner
relationship `0x268D753AE30 + 0x10 -> 0x268DF21ED20`. Latest owner/type artifact:
`scripts/captures/owner-type-instance-inspector-20260513-215227-155967/summary.json`.
Parent heap ref `0x268D7539700 -> 0x268D753AE30` exists, but no module/static root
has been found. Continue with broad family/source-chain methods and keep movement
blocked.

## Next best actions

| # | Action | Why |
|---:|---|---|
| 1 | Keep movement/navigation blocked. | ProofOnly is still stale-target blocked. |
| 2 | Treat `0x268D753AE30 + 0x10 -> 0x268DF21ED20` as the current best source-chain lead. | It links low-noise type marker to stable candidate family. |
| 3 | Search for a durable/static parent of the heap ref graph, not nearby XYZ offsets. | Chain currently stops at heap-local `0x268D7539700`. |
| 4 | Repeat owner/type inspection after a distinct broad movement-vector snapshot if needed. | Confirms the owner relation moves/tracks correctly. |
| 5 | Avoid promoting `0x268DF21ED20` directly. | It is offset-corrected candidate evidence, not proof truth. |
| 6 | Keep de-prioritizing `0x268BEF2C000`. | It failed repeat-readback stability. |
| 7 | Do not repeat identical x64dbg attach attempts. | Previous attach attempts failed before attach. |
| 8 | Use PC-heavy JSON comparisons for all new readbacks. | Saves tokens and avoids manual row scanning. |
| 9 | Re-run `navigation_resume_status.py` after any proof/recovery milestone. | Keeps gate state visible. |
| 10 | Update current truth before any future live proof attempt. | Prevents stale artifact drift. |
