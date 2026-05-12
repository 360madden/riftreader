# RiftReader Python Stage-1 Proof Reacquisition Helper

Version: v0.1.0

## Purpose

`script/riftreader_postupdate_proof_reacquire_stage1.py` is the Python-first control plane for post-update proof-anchor reacquisition stage 1.

It replaces fragile one-off PowerShell runners with a repo-owned Python workflow while still reusing existing repo leaf helpers.

## Safety model

- No Cheat Engine.
- No truth-file update.
- No git command from the stage-1 helper.
- No movement unless `--allow-movement-stimulus` is explicitly passed.
- Bounded movement stimulus is only attempted after the visual gate returns `readyForLiveInput=true` and a candidate JSONL exists.
- Navigation/proof-smoke remains blocked until proof promotion and same-target `ProofOnly` pass.

## Example: no-movement candidate scan

```powershell
cmd\riftreader-postupdate-proof-reacquire-stage1.cmd --visual-full
```

## Example: movement-stimulus pose collection after maintenance

```powershell
cmd\riftreader-postupdate-proof-reacquire-stage1.cmd --visual-full --allow-movement-stimulus
```

## Expected output

The helper writes:

```text
scripts\captures\postupdate-proof-reacquire-stage1-python-<UTC>\stage1-python-summary.json
scripts\captures\postupdate-proof-reacquire-stage1-python-<UTC>\stage1-python-summary.md
```

## Promotion boundary

When the batch returns `promotion-candidate-found`, use the existing repo promotion helper:

```text
scripts\promote-current-pid-proof-anchor-from-batch.ps1
```

Then run same-target `ProofOnly`.

Do not update `docs/recovery/current-truth.md` or `docs/recovery/current-proof-anchor-readback.json` before proof promotion and same-target `ProofOnly` pass.

## END_OF_DOCUMENT_MARKER
