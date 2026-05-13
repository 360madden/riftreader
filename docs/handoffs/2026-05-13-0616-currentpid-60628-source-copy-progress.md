# Handoff: PID 60628 source-copy progress, still candidate-only

Generated: 2026-05-13 06:16 UTC  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`  
Target: `rift_x64` PID `60628`, HWND `0xCE0FCE`, start UTC `2026-05-13T04:53:58.081190Z`, module base `0x7FF796B50000`

## TL;DR

Coordinate truth is still **candidate-only**, but the best current evidence moved from a single copied destination slot toward a repeatable source-copy pattern:

- latest fresh current destination copy: `0x1FF07575346`;
- fresh `RRAPICOORD1` reference: `[7406.1299, 871.77, 3028.77]`;
- copied memory value: `[7406.1318359375, 871.7725830078125, 3028.77099609375]`;
- max abs delta: `0.00258300781251819`;
- best source lead: `rdx=0x1FF6D600020`, coordinate offset `rdx+0x28`, observed across two displaced copied poses.

Do **not** promote `0x1FF07575346`, `0x1FF0757215A`, `0x1FF6D600020`, `0x1FF65FADE88`, or `0x1FF6D658590`. No static/restart-stable pointer chain or same-target `ProofOnly` promotion exists.

## New code in this slice

- `scripts/capture_x64dbg_coord_copy_probe_batch.py`
  - Python wrapper around the existing bounded x64dbg capture helper.
  - Runs repeated page-access captures and classifies hits.
  - Rejects noisy page accesses unless the expected source offset/copy-size evidence is present.
  - Writes `summary.json` and `summary.md` under `scripts/captures/x64dbg-coord-copy-batch-*`.
- `scripts/test_capture_x64dbg_coord_copy_probe_batch.py`
  - Unit tests for good-hit, copy-size mismatch, and implausible source-triplet classification.

Validation run:

- `python -m py_compile .\scripts\capture_x64dbg_coord_copy_probe_batch.py .\scripts\test_capture_x64dbg_coord_copy_probe_batch.py`
- `python .\scripts\capture_x64dbg_coord_copy_probe_batch.py --self-test --json`
- `$env:PYTHONPATH=(Resolve-Path .\scripts).Path; python -m unittest .\scripts\test_capture_x64dbg_coord_copy_probe_batch.py`

## Key artifacts from this slice

### Fresh target/preflight

- `scripts/captures/x64dbg-target-preflight-20260513-060835-880910/summary.json`
  - exact PID/HWND/start/module matched;
  - `responding=true`;
  - debugger process count `0`.

### Fresh reference and current family scan

- `scripts/captures/family-scan-currentpid-60628-20260513-061017/family-scan-summary.json`
- `scripts/captures/family-scan-currentpid-60628-20260513-061422/family-scan-summary.json`

Both used fresh `RRAPICOORD1` capture. Latest selected reference:

- `X=7406.1299`
- `Y=871.77`
- `Z=3028.77`
- marker seq `40521`

Best current unaligned family hit:

- `0x1FF07575346`
- value `[7406.1318359375, 871.7725830078125, 3028.77099609375]`
- max abs delta `0.00258300781251819`

### Broad family snapshot

- `scripts/captures/coordinate-family-snapshot-currentpid-60628-20260513-061344/family-snapshot-summary.json`

Findings:

- scan range `0x1FF07570000..0x1FF075A0000`;
- `scanStride=1`;
- `tripletCount=97`;
- `nearReferenceTripletCount=9`;
- best current triplet `0x1FF07575346`;
- prior `0x1FF0757215A` is now stale by about `5.8247`.

### Broader high-heap aligned scans

- `scripts/captures/family-scan-currentpid-60628-20260513-062614/family-scan-summary.json` — broad low/stack range, timed at `120s`, found stack-like candidates.
- `scripts/captures/family-scan-currentpid-60628-20260513-062840/family-scan-summary.json` — high heap `0x1FF00000000..0x20000000000`, timed at `180s`, found exact high-heap candidates.
- `scripts/captures/family-scan-currentpid-60628-20260513-063352/family-scan-summary.json` — high heap `0x1FF40000000..0x1FF80000000`, timed at `120s`, found more exact candidates.
- `scripts/captures/family-scan-currentpid-60628-20260513-063559/family-scan-summary.json` — high heap `0x1FF80000000..0x1FFC0000000`, completed, found more exact candidates.
- `scripts/captures/family-scan-currentpid-60628-20260513-063709/family-scan-summary.json` — high heap `0x1FFC0000000..0x20000000000`, no readable regions/hits.
- Consolidated review: `scripts/captures/high-heap-coordinate-family-review-currentpid-60628-20260513-0637/summary.json`

Review findings:

- `candidateCount=53`;
- `familyCount=24`;
- exact aligned high-heap candidates exist outside the unaligned `0x1FF07570000` destination page;
- best exact value: `[7406.1298828125, 871.7699584960938, 3028.77001953125]`;
- best max abs delta: `4.1503906231810106e-05`;
- candidate-only: nearby context includes scene/player-info/render strings such as `avril Plaza`, `elf_high_female`, and `plume_14.dds`, so displaced-pose ranking is required before x64dbg/static-chain work on these families.

### Displaced-pose blocker

- Artifact: `scripts/captures/movement-stimulus-displacement-check-currentpid-60628-20260513-0642/summary.json`

Findings:

- Exact-HWND C# SendInput focused foreground RIFT successfully.
- Uppercase `W` was a bad clean-forward stimulus because it produced `shiftState=1`.
- Lowercase `w` was sent cleanly with `shiftState=0`, `sentInputEvents=2`, exact HWND foreground, target process foreground.
- Fresh `RRAPICOORD1` references before/after remained `[7406.1299, 871.77, 3028.77]`.
- Result: `blocked-no-displaced-pose`.

Interpretation: do not spam more movement. Either the character is blocked/stuck, movement input is not effective in the current in-game state, or visual/state diagnosis is needed. High-heap family ranking now needs manual displacement or a verified movement setup.

### x64dbg source-copy evidence

Useful coordinate-source captures:

- `scripts/captures/x64dbg-live-access-capture-20260513-060024-938838/summary.json`
  - `rdx=0x1FF6D600020`;
  - source triplet at `rdx+0x28`: `[7406.6005859375, 871.7725830078125, 3028.814208984375]`;
  - destination/copy family later ranked `0x1FF07575121`.
- `scripts/captures/x64dbg-live-access-capture-20260513-060104-964476/summary.json`
  - `rdx=0x1FF6D600020`;
  - source triplet at `rdx+0x28`: `[7406.1318359375, 871.7725830078125, 3028.77099609375]`;
  - destination/copy family later ranked `0x1FF07575346`.

Interpretation:

- `rdx+0x28` is a stronger current source lead than any `0x1FF0757xxxx` destination slot.
- Destination slots move/stale; source buffer address was stable across these two useful captures.
- Disassembly of `rift_x64.exe+0x47D408` shows a heap/ring copy routine: `rdi=rcx`, `r15=rdi+0x50`, `r14=[rdi]`, destination `r12=[r15]+[rdi+0x94]+[rdi+0x9c]`, source `rdx=[r14]`.
- This remains heap-local and PID-local until a stable owner/static chain or restart/relogin proof exists.

### Noisy page-access evidence

The new batch helper correctly rejected non-coordinate page hits:

- `scripts/captures/x64dbg-coord-copy-batch-60628-20260513-060709-057382/summary.json`
- `scripts/captures/x64dbg-coord-copy-batch-60628-20260513-060845-059022/summary.json`

Observed rejected copy/page sizes included `0x8` and `0x4A`. This means page breakpoints are useful only when classified/filtering is applied; first-hit page captures are not automatically coordinate evidence.

### Pointer family scans

- `scripts/captures/pointer-family-scan-20260513-061154-710379/summary.json`
- `scripts/captures/pointer-family-scan-20260513-061835-695118/summary.json`

Findings:

- no `rift_x64.exe` module/static hits;
- latest bounded depth-4 scan covered `25` target/owner leads and still had total module hits `0`;
- `0x1FF6D600020` source buffer has heap-local refs only;
- `0x1FF65FADE88` source cursor is referenced by `0x1FF6D658590`;
- `0x1FF07568020` ChromaLink/addon metadata is referenced by `0x1FF6D6585E0`;
- no static pointer chain promoted.

## Current truth boundary

Confirmed:

1. `--scan-stride 1` is required for this destination family.
2. Fresh `RRAPICOORD1` still scores the family correctly.
3. Best current destination copy at 06:14 UTC was `0x1FF07575346`.
4. Earlier best `0x1FF0757215A` is now stale, proving exact destination slots move/stale.
5. `rdx=0x1FF6D600020`, offset `+0x28`, is the best source-copy lead observed across two useful x64dbg captures.
6. Broader high-heap scans found better exact candidate families that now need displaced-pose ranking.
7. Automated key stimulus did not create a displaced pose, despite exact foreground targeting.

Not confirmed:

- no static pointer chain;
- no restart/relogin stability;
- no promoted proof anchor;
- no same-target `ProofOnly`;
- no navigation/route/movement-grade truth.

## Paste-ready resume prompt

Resume in `C:\RIFT MODDING\RiftReader` on `main`. Continue coordinate truth recovery for RIFT PID `60628` / HWND `0xCE0FCE` only after revalidating exact PID/HWND/start/module and no debugger process. Current status is candidate-only. Latest fresh best destination copy is `0x1FF07575346`, but do not promote it. Strongest source lead is x64dbg `rdx=0x1FF6D600020`, coordinate at `rdx+0x28`, observed in `x64dbg-live-access-capture-20260513-060024-938838` and `x64dbg-live-access-capture-20260513-060104-964476`. Use `--scan-stride 1`, grouped family snapshots, and the new `scripts/capture_x64dbg_coord_copy_probe_batch.py` classifier. Next goal is to turn the heap-local source lead into a restart-stable/static owner chain or prove it cannot be promoted. Keep all evidence candidate-only until same-target ProofOnly passes.

## Optional top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Revalidate PID/HWND/start/module/no-debugger before more live work. | Prevents stale target mistakes. |
| 2 | Keep scanning `0x1FF07570000..0x1FF075A0000` with `--scan-stride 1`. | Fresh copies are unaligned. |
| 3 | Treat destination slots as disposable. | `0x1FF0757215A` already went stale. |
| 4 | Focus on source `rdx=0x1FF6D600020` + offset `0x28`. | It tracked two useful copied poses. |
| 5 | Produce a real displaced pose manually or by first diagnosing why `w` did not move. | Ranking cannot advance without coordinate displacement. |
| 6 | Rank the high-heap exact families across that real displaced pose. | This is now a better lead than only chasing the ChromaLink destination page. |
| 7 | Deepen pointer-family scanning only on high-heap families that track displacement. | Avoids wasting time on static/stale scene copies. |
| 8 | Avoid exact hardware watchpoints on unaligned destination floats. | Size-4 unaligned hardware BP failed; size-1 timed out. |
| 9 | Do not update `current-proof-anchor-readback.json` yet. | ProofOnly has not passed for PID `60628`. |
| 10 | Commit this recovery slice after validation. | Preserves the classifier and accurate truth docs. |
