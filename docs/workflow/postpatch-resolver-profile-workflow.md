# RiftReader post-patch resolver profile workflow

Status: Phase 1/2 scaffold.

This workflow turns the June 2026 post-update recovery lesson into a repeatable
profile generator. It is intentionally safe and candidate-only: it does not send
RIFT input, move the character, attach debuggers, read live target memory, write
tracked current truth, or promote resolver candidates.

## Goal

After a RIFT update, do not start from scratch and do not let stale promoted
truth leak into navigation/consumer tools.

Instead, generate a local post-patch profile packet that records:

1. the local game build fingerprint when the manifest/binary are available;
2. whether tracked current truth is stale, unverified, or contradicted by
   post-update root-null evidence;
3. candidate-only resolver leads gathered from tracked truth and recovery docs;
4. the explicit proof gaps required before promotion;
5. a movement-proof plan template that treats movement as controlled discovery
   stimulus, not consumer automation.

## Command

```powershell
scripts\riftreader-postpatch-profile.cmd --json
```

To write ignored artifacts:

```powershell
scripts\riftreader-postpatch-profile.cmd --json --write
```

Artifacts are written under:

```text
.riftreader-local\postpatch-profile\<timestamp>\
```

The helper writes:

```text
summary.json
summary.md
build-fingerprint.json
stale-truth-report.json
candidate-resolver-profile.json
movement-proof-plan-template.json
```

A `latest-run.txt` pointer is also written under
`.riftreader-local\postpatch-profile\`.

## Phase 1: build fingerprint and stale-truth freeze

Phase 1 answers:

| Question | Output |
|---|---|
| What RIFT manifest/binary is currently installed? | `build-fingerprint.json` |
| Is tracked current truth available? | `stale-truth-report.json` |
| Does recovery evidence show a tracked root became null? | blocker such as `tracked-root-has-postupdate-null-evidence:0x32EBC80` |
| May navigation/follow consumers use this packet? | always no |

If the RIFT manifest or binary is not present on the machine running the helper,
the packet reports `local-build-files-not-found` as a warning. That is useful for
repo-only review and CI-style checks, but it is not sufficient for live proof.

## Phase 2: candidate-only resolver profile

Phase 2 answers:

| Question | Output |
|---|---|
| What promoted resolver is tracked today? | candidate from `docs\recovery\current-truth.json` |
| What post-update candidate chains are documented? | candidates parsed from the recovery plan |
| Which coordinate candidate should be inspected first? | `candidate-resolver-profile.json.bestCandidate` |
| Can this candidate be promoted now? | no |

The helper prefers a documented post-update coordinate-container lead over a
tracked promoted root when the tracked root has root-null evidence.

The current June 2026 recovery lesson is represented by the candidate shape:

```text
[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30
```

That candidate remains candidate-only until API-now, controlled displacement,
restart/relog survival, and ProofOnly gates pass.

## Movement policy

Movement is not banned from discovery. It is required for strong proof.

The packet makes the distinction explicit:

| Movement kind | Policy |
|---|---|
| Controlled discovery stimulus | gated by explicit approval and exact-target preflight |
| Consumer movement / route automation | blocked until promoted truth exists |
| Current-truth write during movement proof | blocked |
| Unbounded movement loops | blocked |

The movement-proof template is written only as a plan. It never sends input.

## Promotion boundary

This workflow cannot promote anything.

Promotion requires a later explicit gate after:

1. exact target identity is current;
2. API-now versus chain-now passes;
3. controlled displacement proof passes with at least two displaced API poses;
4. restart/relog survival passes;
5. same-target ProofOnly passes;
6. the operator explicitly authorizes tracked current-truth refresh.

## Safety invariants

The helper's safety flags must remain:

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

## Recommended loop

1. Run `scripts\riftreader-postpatch-profile.cmd --json --write`.
2. Review `stale-truth-report.json`.
3. Review `candidate-resolver-profile.json`.
4. If a candidate is present, review `movement-proof-plan-template.json`.
5. Only then decide whether to request explicit controlled-discovery movement.
