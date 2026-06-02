# Post-update global-container coordinate readback handoff — 2026-06-02 20:06 UTC

## Verdict

The old promoted root remains invalid for the current post-update epoch, but
the recovery lane now has a stronger candidate-only static/container coordinate
path:

`[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30`

This candidate passed exact-target no-input current readback against PID
`77152` / HWND `0x17A0DB2`, including a five-sample stationary polling baseline.
It is **not promoted** and is **not movement/restart proof**.

## Evidence

| Check | Result |
|---|---|
| RIFT manifest epoch | `STABLE-1-1152-a-1256395`; `rift_x64.exe` manifest SHA1 `a8ba8748ea752e4e5581cea34188dc702469c923`. |
| Old promoted root | `[rift_x64+0x32EBC80] == 0x0`; do not use old current-truth resolver for this epoch. |
| Static access-chain packet | `scripts/captures/postupdate-static-access-chain-20260602-195804-076419/summary.json`. |
| Orientation-only root | `[rift_x64+0x335F508] -> 0x1D4BA2A6230`; `+0x320` is unit/matrix-like, not world position. |
| Breadcrumb global lead | Function `0xC38390` reads `rift_x64+0x32DD7E8`; container child offsets `0x80`, `0x88`, `0x90` each exposed coordinate-like triples. |
| New readback helper | `scripts/postupdate_global_container_coordinate_readback.py`; wrapper `scripts/riftreader-postupdate-global-container-coordinate-readback.cmd`. |
| Best current readback | `[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30` -> coordinate `7256.38916015625, 821.4478149414062, 2990.00537109375`; max abs delta vs reference `0.004628906250218279`. |
| Polling baseline | `scripts/captures/postupdate-global-container-coordinate-readback-20260602-200619-457973/summary.json`; 5/5 samples matched reference; stationary planar drift `0.0`. |
| Rediscovery status refresh | `scripts/captures/postupdate-owner-root-rediscovery-20260602-201119-651369/summary.json` surfaces the global-container readback while keeping overall status blocked on proof/root gates. |
| Tool catalog | `postupdate-global-container-coordinate-readback` is canonical and safe-read-only. |

## Safety boundary

No live input, movement, `/reloadui`, screenshot key, debugger/CE attach, target
memory write, provider write, `current-truth` apply, ProofOnly, proof promotion,
or actor-chain promotion was performed.

## Resume from here

1. Use `scripts\riftreader-postupdate-global-container-coordinate-readback.cmd --samples 5 --interval-seconds 0.2 --json` for no-input candidate readback refresh.
2. Keep `[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30` candidate-only until explicit movement/restart proof is approved and passes.
3. Do not repeat the exhausted `0x26E5E80`, `0x26E5278`, or `0x26E3200` root-signature sweeps unless a fresh owner/container lead changes the seed set.
4. Next safe local work is a no-input consumer-readiness bridge that reports this candidate separately from promoted current truth, so downstream navigation stays blocked instead of silently using stale 2026-06-01 truth.
