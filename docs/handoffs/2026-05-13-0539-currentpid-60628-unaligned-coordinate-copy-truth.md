# Handoff: current PID 60628 unaligned coordinate-copy truth

Generated: 2026-05-13 05:39 UTC  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`  
Target: `rift_x64` PID `60628`, HWND `0xCE0FCE`, start UTC `2026-05-13T04:53:58.081190Z`, module base `0x7FF796B50000`

## TL;DR

Coordinate truth was reacquired as **candidate-only live-process evidence**. The major new finding is that the current coordinate payload in the `0x1FF07570000` family is often **unaligned**. The old 4-byte-aligned scanner was missing the freshest copy and ranking stale aligned copies instead.

The current best observed coordinate copy after the latest unaligned scan is:

- `0x1FF0757215A` and duplicate `0x1FF07572183`
- Value: `[7411.95458984375, 871.8436279296875, 3031.310546875]`
- Reference: `[7411.9497, 871.84, 3031.3098]`
- Max abs delta: `0.004889843749879219`

Do **not** promote this as stable. Exact addresses continue to move. Treat the page/family and writer path as the useful lead, not the absolute address.

## What changed in code

- `scripts/scan_current_pid_coordinate_family.py`
  - Added `--scan-stride {1,4}`.
  - `--scan-stride 1` finds unaligned float32 XYZ payloads that the old 4-byte aligned scan missed.
- `scripts/capture_current_pid_coordinate_family_snapshot.py`
  - New read-only broad family snapshot helper.
  - Captures plausible XYZ triplets across a target address range, compares them to multiple observation/reference files, clusters the family, and remains candidate-only.
- `scripts/rift_live_test/x64dbg_live_access_capture.py`
  - Added `memory-access` capture mode using x64dbg memory breakpoints.
  - Added stack/code/register-memory previews at hits.
  - Preserves detach/cleanup gates.
- `scripts/test_x64dbg_live_access_capture.py`
  - Added coverage for memory-breakpoint cleanup.

## Key live evidence

### Target safety

Latest post-debugger preflight passed:

- `scripts/captures/x64dbg-target-preflight-20260513-053604-049421/summary.json`
- Responding: true
- Debugger processes: 0
- Exact PID/HWND/start/module base matched

### 4-byte aligned scanner was insufficient

Aligned scans kept finding moved/stale copies such as:

- `0x1FF075700AC`
- `0x1FF075704E8`
- `0x1FF07571240`
- `0x1FF075719E4`

But x64dbg showed the copy routine writing an unaligned payload in the same page. After adding `--scan-stride 1`, the scanner found better current hits:

- Artifact: `scripts/captures/family-scan-currentpid-60628-20260513-053508/family-scan-summary.json`
- Best: `0x1FF0757215A`
- Duplicate: `0x1FF07572183`
- Stable readback artifact: `scripts/captures/readback-currentpid-60628-unaligned-20260513-0535/riftscan-riftreader-currentpid-60628-readback-wrapper-summary-20260513-013527.json`

### Broad family snapshot

Artifact:

- `scripts/captures/coordinate-family-snapshot-currentpid-60628-20260513-053557/family-snapshot-summary.json`

Findings:

- Scanned `0x1FF07570000..0x1FF075A0000` with `scanStride=1`.
- Triplets: `29`
- Near-reference triplets: `19`
- Best current triplet: `0x1FF0757215A`
- All results remain candidate-only.

### x64dbg integration is now safe enough for bounded captures

Stop-context attach/detach succeeded:

- `scripts/captures/x64dbg-live-access-capture-20260513-052645-069337/summary.json`

Exact-address hardware read/write watchpoints timed out on older slots, which is expected because those addresses are copy slots, not stable sources:

- `scripts/captures/x64dbg-live-access-capture-20260513-052704-639486/summary.json`
- `scripts/captures/x64dbg-live-access-capture-20260513-052745-998320/summary.json`

Page memory breakpoint succeeded and caught the writer/copy path:

- `scripts/captures/x64dbg-live-access-capture-20260513-053129-095426/summary.json`
- `scripts/captures/x64dbg-live-access-capture-20260513-053245-131513/summary.json`
- `scripts/captures/x64dbg-live-access-capture-20260513-053703-121830/summary.json`

Writer/copy context:

- Hit instruction: `VCRUNTIME140.dll+0x113F8` / `0x7FFC593F13F8`
- Instruction: `vmovdqu ymmword ptr ds:[rcx+r9*1-0x40], ymm1`
- Return address: `rift_x64.exe+0x47D538`
- Caller instruction before copy: `rift_x64.exe+0x47D533` calls `0x7FF798FF06D9`
- At caller breakpoint (`scripts/captures/x64dbg-live-access-capture-20260513-053859-682586/summary.json`):
  - `rcx/r12 = destination buffer`
  - `rdx = [r14] = 0x1FF6D600020` source buffer
  - `r8 = 0x37` copy length
  - `r14 = 0x1FF65FADE88` source cursor/struct candidate
  - Source buffer at `rdx + 0x28` held current XYZ: `[7412.0126953125, 871.8435668945312, 3031.3076171875]`
  - `r15Deref0 = 0x1FF07568020` contains ChromaLink/addon metadata (`ChromaLink`, `0.1.0-dev`, etc.)

Interpretation: the `0x1FF07570000` family is a dynamic destination/copy family. The useful x64dbg lead is the caller path and the source cursor (`r14 -> source buffer`), not any single destination address.

### Pointer scan

Artifact:

- `scripts/captures/pointer-family-scan-20260513-053727-089429/summary.json`

Findings:

- Source buffer `0x1FF6D600020` had heap references only; no `rift_x64.exe` module/static hits.
- Source cursor `0x1FF65FADE88` had one heap hit at `0x1FF6D658590`.
- ChromaLink metadata `0x1FF07568020` had one heap hit at `0x1FF6D6585E0`.
- No static pointer chain promoted.

## Current truth boundary

Confirmed current-session candidate truth:

1. `RRAPICOORD1` remains the reference source for current coordinate scoring.
2. The freshest copied coordinate payload can be unaligned. Use `--scan-stride 1` for this family.
3. The destination family/page `0x1FF07570000` receives current coordinate payloads through a RIFT caller into VCRUNTIME copy code.
4. The x64dbg caller lead is `rift_x64.exe+0x47D533` / return `+0x47D538`.
5. Source cursor candidate at hit time: `r14=0x1FF65FADE88`, `[r14]=0x1FF6D600020`, coord offset `+0x28` inside that source buffer at the breakpoint moment.

Not confirmed:

- No stable exact destination address.
- No restart-stable static pointer chain.
- No movement proof-anchor gate satisfied.

## Validation run

- `python -m py_compile .\scripts\scan_current_pid_coordinate_family.py .\scripts\capture_current_pid_coordinate_family_snapshot.py`
- `python -m py_compile .\scripts\rift_live_test\x64dbg_live_access_capture.py .\scripts\x64dbg_live_access_capture.py`
- `$env:PYTHONPATH=(Resolve-Path .\scripts).Path; python -m unittest .\scripts\test_x64dbg_live_access_capture.py`
- `$env:PYTHONPATH=(Resolve-Path .\scripts).Path; python -m unittest .\scripts\test_x64dbg_live_access_capture.py .\scripts\test_x64dbg_coordinate_family_rank.py .\scripts\test_pointer_family_scan.py`
- `git diff --check` passed with line-ending warnings only.

## Optional top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Use `--scan-stride 1` for all future coordinate-family scans in this live PID. | The freshest payload is often unaligned. |
| 2 | Keep `0x1FF0757215A` candidate-only. | It is a copied destination slot and exact addresses move. |
| 3 | Repeat x64dbg execute breakpoint at `rift_x64.exe+0x47D533` for 2-3 more movements. | Confirms the source cursor pattern across poses. |
| 4 | Capture `r14`, `[r14]`, and `[r14]+0x28` at each execute-break hit. | This is the current best route toward source-chain truth. |
| 5 | Pointer-scan the source cursor parent (`0x1FF6D658590`) with bounded depth 2. | Current pointer hits are heap-only; parent chain may reveal a better owner. |
| 6 | Add a compact analyzer for x64dbg hit summaries. | Avoid manual extraction of source cursor/caller evidence. |
| 7 | Do not rely on aligned-only historical rankings. | They over-rank stale slots after this finding. |
| 8 | Keep memory breakpoints page-scoped and bounded. | They work, but must detach quickly to avoid freezing/disconnects. |
| 9 | Do not promote until restart/relogin validation repeats the caller/source pattern. | Current evidence is PID-local. |
| 10 | Preserve this handoff before deeper pointer work. | This is the cleanest recovery checkpoint so far. |
