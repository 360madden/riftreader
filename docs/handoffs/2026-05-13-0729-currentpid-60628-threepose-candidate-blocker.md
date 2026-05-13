# Handoff: PID 60628 three-pose coordinate candidates, live target blocked

Generated: 2026-05-13 07:29 UTC  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`  
Target: `rift_x64` PID `60628`, HWND `0xCE0FCE`, process start `2026-05-13T04:53:58.081190Z`, module base `0x7FF796B50000`

## TL;DR

Coordinate truth is still **candidate-only** for PID `60628`.

Best current evidence after grouped-family scanning and displacement-aware ranking:

- best exact heap candidate: `0x1FF08502BC8`, pose support `3`, track max error `0.004333593749834108`;
- best family-level candidate: `0x1FF94EC0000`, pose support `3`, moving slots `0x1FF94EC8B80` -> `0x1FF94EC8DC0` -> `0x1FF94EC93D0`, track max error `6.0937500165891834e-05`;
- destination-page family `0x1FF07570000` still works only as moving/unaligned copy evidence; use `--scan-stride 1`;
- latest pointer-family scan found **zero** module/static hits;
- latest x64dbg capture detached successfully but the RIFT window later became `responding=false` with no debugger process attached.

Do **not** promote any PID `60628` address. Do **not** run movement, x64dbg, hardware watchpoints, or repeated attach/go loops while exact-target preflight reports `responding=false`.

## What changed in code

- `scripts/rift_live_test/coordinate_family_rank.py`
  - Adds displacement tracking summaries for exact-address and family rankings.
  - Sorts same-support candidates by tracking error before raw reference delta.
  - Emits `displacementTracking` in JSON and `Track max error` in Markdown.
- `scripts/scan_current_pid_coordinate_family.py`
  - Uses microsecond UTC stamps for run directories to prevent same-second artifact collisions during rapid grouped scans.
- Tests added/updated:
  - `scripts/test_x64dbg_coordinate_family_rank.py`
  - `scripts/test_scan_current_pid_coordinate_family.py`

## Best evidence

### Movement/input truth

C# exact-HWND SendInput `VirtualKey` `w` moved the character:

- `scripts/captures/csharp-sendinput-current-virtualkey-w-currentpid-60628-20260513-025312/measured-result.json` - planar displacement `0.4616189445850858`.
- `scripts/captures/csharp-sendinput-current-virtualkey-w-thirdpose-currentpid-60628-20260513-031727/measured-result.json` - planar displacement `0.37082363732641205`.

Earlier C# `ScanCode` `w` was ineffective/low-signal for this target. Use `VirtualKey` for future bounded movement stimulus only after visual/target gates pass.

### Three-pose ranking

Artifact: `scripts/captures/coordinate-family-rank-currentpid-60628-threepose-tracking-20260513-032001-311/coordinate-family-rankings.json`

Top exact address:

- address `0x1FF08502BC8`;
- support `3`;
- track max error `0.004333593749834108`;
- avg delta `0.003232356770846915`;
- values tracked:
  - `[7406.1318359375, 871.7725830078125, 3028.77099609375]`;
  - `[7406.58740234375, 871.7725830078125, 3028.8134765625]`;
  - `[7407.099609375, 871.7734375, 3028.86181640625]`.

Top family:

- family `0x1FF94EC0000`;
- support `3`;
- track max error `6.0937500165891834e-05`;
- moving slots `0x1FF94EC8B80` -> `0x1FF94EC8DC0` -> `0x1FF94EC93D0`.

Demoted after third pose:

- `0x1FF392C0000`;
- `0x1FF40660000`;
- `0x1FF841D0000`.

These had two-pose promise but no third-pose hit in targeted rescans.

### x64dbg evidence

Current best exact candidate x64dbg capture:

- `scripts/captures/x64dbg-live-access-capture-20260513-072035-091117/summary.json`
- watched candidate `0x1FF08502BC8`;
- hit RIP `0x7FF7970CC2B5` (`rift_x64.exe+0x57C2B5`);
- instruction `cmp qword ptr ds:[rcx+0x10], 0x00`;
- candidate relation `rcx+0x2F8`;
- context looked like UI/scene-object metadata, not a static player-coordinate owner;
- detach succeeded.

Older source-copy lead remains useful but not promotable:

- `rdx=0x1FF6D600020`;
- coordinate offset `rdx+0x28`;
- copy/ring routine around `rift_x64.exe+0x47D408`;
- heap-local, no static owner chain.

### Pointer scan

Artifact: `scripts/captures/pointer-family-scan-20260513-070942-089639/summary.json`

- seed count `14`;
- scanned target count `67`;
- total module hits `0`;
- total `rift_x64.exe` hits `0`;
- heap refs only.

## Current blocker

After the x64dbg memory-access capture on `0x1FF08502BC8`, exact-target preflight reports:

- artifact: `scripts/captures/x64dbg-target-preflight-20260513-072327-946499/summary.json`;
- blocker: `selected-target-not-responding`;
- debugger process count `0`;
- target window visible and exact PID/HWND/start/module still matched.

WGC capture also timed out:

- `scripts/captures/post-x64dbg-nonresponsive-visual-20260513-032345-187/wgc-result.json`.

Interpretation: x64dbg is detached, but RIFT is not responsive. This blocks further live/debugger work until the game is manually recovered/relaunched and exact-target preflight passes again.

## Non-promotion list

Keep these candidate-only:

- `0x1FF08502BC8`;
- `0x1FF94EC0000` / `0x1FF94EC93D0`;
- `0x1FF07574839`, `0x1FF07575346`, `0x1FF0757215A`;
- `0x1FF6D600020`, `0x1FF65FADE88`, `0x1FF6D658590`;
- transient `0x1FF392*`, `0x1FF406*`, `0x1FF841*` leads.

## Paste-ready resume prompt

Resume in `C:\RIFT MODDING\RiftReader` on `main`. Start by checking git status and the latest pushed commit, then read `docs/recovery/current-truth.md` and this handoff. Do not do live movement or x64dbg until exact-target preflight passes with `responding=true` and no debugger processes. Current target PID `60628` / HWND `0xCE0FCE` became nonresponsive after `scripts/captures/x64dbg-live-access-capture-20260513-072035-091117/summary.json`; latest blocker is `scripts/captures/x64dbg-target-preflight-20260513-072327-946499/summary.json`. Candidate truth remains unpromoted. Best exact candidate is `0x1FF08502BC8`; best family candidate is `0x1FF94EC0000` with moving slots. Use grouped family scans, displacement-tracking ranking, and C# `VirtualKey` movement only after target/visual gates pass. Do not update `current-proof-anchor-readback.json` until same-target `ProofOnly` passes.

## Optional top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Recover/relaunch RIFT manually, then revalidate exact PID/HWND/start/module/responding/no-debugger. | Live work is blocked while `responding=false`. |
| 2 | Do not run x64dbg or movement until preflight is green. | Prevents another freeze/disconnect loop. |
| 3 | Preserve `0x1FF08502BC8` as top exact candidate only. | Strong 3-pose evidence, but no static chain. |
| 4 | Prioritize `0x1FF94EC0000` as top family candidate. | Best displacement tracking across moving slots. |
| 5 | Continue grouped scans with microsecond-stamped outputs. | Avoids artifact overwrite/collision and captures whole families. |
| 6 | Use C# `VirtualKey` `w` for future bounded movement stimulus, not ScanCode. | VirtualKey produced measured displacement. |
| 7 | Re-run three-pose ranking after any relog/restart with fresh PID. | Current absolute heap addresses are PID-local. |
| 8 | Run pointer scans only on families that track displacement after relog/restart. | Avoids wasting time on stale scene/render copies. |
| 9 | Use x64dbg surgically only after ranking and only with detach-first scripts. | Limits freeze risk. |
| 10 | Keep `current-proof-anchor-readback.json` unchanged until ProofOnly passes. | Prevents false truth promotion. |
