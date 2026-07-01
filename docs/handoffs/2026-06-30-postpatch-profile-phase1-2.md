# 2026-06-30 - Post-patch resolver profile Phase 1/2 scaffold

## Verdict

Phase 1/2 scaffold is implemented as a safe, candidate-only post-patch profile
workflow. It does not send live RIFT input, move the character, attach
debuggers, read live target memory, write tracked current truth, promote proof,
or enable navigation/route consumers.

## New files

| Path | Purpose |
|---|---|
| `tools/riftreader_workflow/postpatch_profile.py` | Builds a safe post-patch resolver profile packet. |
| `scripts/riftreader-postpatch-profile.cmd` | Thin Windows wrapper for the helper. |
| `scripts/test_postpatch_profile.py` | Unit coverage for stale-root blocking, candidate selection, and artifact output. |
| `docs/workflow/postpatch-resolver-profile-workflow.md` | Operator workflow documentation. |

## Command

```powershell
scripts\riftreader-postpatch-profile.cmd --json --write
```

## What the helper does

- Fingerprints the local RIFT manifest/binary when available.
- Reads tracked `docs\recovery\current-truth.json`.
- Reads `docs\recovery\post-update-pointer-chain-recovery-plan-2026-06-02.md`.
- Detects documented root-null evidence such as `[rift_x64+0x32EBC80] == 0x0`.
- Surfaces candidate-only resolver leads, preferring the post-update coordinate-container lead when the tracked root has null evidence.
- Emits a movement-proof plan template that treats movement as controlled discovery stimulus, not consumer automation.

## Important candidate

The current recovery-document candidate surfaced by the helper is:

```text
[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30
```

It remains candidate-only until fresh API-now, controlled displacement,
restart/relog survival, and ProofOnly gates pass.

## Safety

The workflow keeps these boundaries:

```json
{
  "movementSent": false,
  "inputSent": false,
  "x64dbgAttach": false,
  "providerWrites": false,
  "gitMutation": false,
  "currentTruthWrite": false,
  "proofPromotion": false,
  "consumerMovementEnabled": false
}
```

## Validation status

The code was syntax-checked before committing. The GitHub status endpoint
reported no combined statuses for the latest commit at handoff time, so remote CI
results were not available in this session.

Recommended local validation:

```powershell
python -m unittest scripts.test_postpatch_profile
scripts\riftreader-postpatch-profile.cmd --json --write
```

## Next safe action

Run the helper locally on the RIFT machine and review:

```text
.riftreader-local\postpatch-profile\<timestamp>\stale-truth-report.json
.riftreader-local\postpatch-profile\<timestamp>\candidate-resolver-profile.json
.riftreader-local\postpatch-profile\<timestamp>\movement-proof-plan-template.json
```

## Next gated action

Only after review, decide whether to approve a controlled-discovery movement
proof for the selected candidate. Consumer movement/navigation must stay blocked
until promotion gates pass.
