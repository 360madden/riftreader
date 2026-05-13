# x64dbg safe reintegration handoff

Generated: `2026-05-13T04:18:02Z`

## TL;DR

- Current live target revalidated after recovery:
  - PID `79184`
  - HWND `0xA90BFC`
  - start UTC `2026-05-13T00:43:12.080812Z`
  - module base `0x7FF796B50000`
  - preflight artifact: `scripts/captures/x64dbg-target-preflight-20260513-041748-219189/summary.json`
- The game was unfrozen by detecting and force-resuming one pre-existing suspended thread:
  - recovery artifact: `scripts/captures/x64dbg-target-recovery-20260513-041419-087546/summary.json`
  - thread `44128` had previous suspend count `1`
  - post-recovery `respondingAfter: true`
- x64dbg read-access evidence exists, but remains candidate-only:
  - hit artifact: `scripts/captures/x64dbg-live-access-capture-20260513-040436-587946/summary.json`
  - candidate address `0x1738127A5A4`
  - event hit address `0x1738127A5A4`
  - instruction RIP `0x7FF79711BDF3`
  - instruction `movss xmm2, dword ptr ds:[r8+0x2C]`
  - effective address observed in x64dbg arg metadata: `0x1738127A5AC`
  - inferred object pointer for that instruction only: `0x1738127A580`
  - inferred field offsets for the candidate triplet: X `+0x24`, Y `+0x28`, Z `+0x2C`
- Do **not** promote `0x1738127A5A4` or any owner/root. No restart proof, no static root, no runtime chain readback yet.

## What changed in repo tooling

New helper entrypoints:

- `scripts/x64dbg_live_access_capture.py`
- `scripts/x64dbg_target_recovery.py`

New implementation modules:

- `scripts/rift_live_test/x64dbg_live_access_capture.py`
- `scripts/rift_live_test/x64dbg_target_recovery.py`

New unit tests:

- `scripts/test_x64dbg_live_access_capture.py`
- `scripts/test_x64dbg_target_recovery.py`

Important behavior:

- Live capture helper now clears **all** hardware breakpoints with `bphc` before detach when a hardware breakpoint was set.
- Live capture helper attempts one bounded post-hit resume before detach when the target is stopped at the captured event.
- Live capture context now records key registers one-by-one, so the `get_regs()` Unicode decode issue no longer blocks useful register evidence.
- Recovery helper can:
  - verify exact PID/HWND/start/module base,
  - query debugger-remnant state,
  - inspect thread debug registers via suspend/context/restore,
  - optionally clear debug registers,
  - optionally force-resume pre-existing suspended threads when explicitly enabled.

## Latest validation

- `python -m py_compile .\scripts\rift_live_test\x64dbg_live_access_capture.py .\scripts\x64dbg_live_access_capture.py`
- `python -m py_compile .\scripts\rift_live_test\x64dbg_target_recovery.py .\scripts\x64dbg_target_recovery.py`
- `python -m unittest discover -s scripts -p "test_x64dbg*.py"`
  - result: `Ran 89 tests ... OK`
- Post-recovery live preflight:
  - `scripts/captures/x64dbg-target-preflight-20260513-041748-219189/summary.json`
  - result: `passed`
  - `responding: true`
  - debugger process count `0`
- Safety validation after patched live helper:
  - `scripts/captures/x64dbg-live-access-capture-20260513-041650-251036/summary.json`
  - result: timed out without a new hit, detach succeeded
  - follow-up preflight passed
  - follow-up recovery diagnostic found no non-zero debug registers and no pre-existing suspended threads:
    `scripts/captures/x64dbg-target-recovery-20260513-041705-636957/summary.json`

## Current evidence status

Candidate coordinate family remains:

- family/base `0x17381270000`
- selected address `0x1738127A5A4`
- latest ranking artifact:
  `scripts/captures/coordinate-family-rank-20260513-034722-975023/coordinate-family-rankings.json`
- readiness packet:
  `scripts/captures/x64dbg-no-attach-readiness-packet-20260513-035257-799511/summary.json`

Evidence strength:

- Stronger than raw family scan: x64dbg captured code reading the candidate triplet family.
- Still not enough for promotion:
  - no static pointer chain,
  - no module-relative root,
  - no restart validation,
  - no runtime helper readback through a chain,
  - no movement/proof-only validation.

## Follow-up owner-neighborhood scan

Read-only C# `RiftReader.Reader --scan-pointer` probes were run after the
safe x64dbg/recovery cycle:

- summary: `scripts/captures/pointer-owner-scan-20260513-002409-neighborhood/summary.json`
- exact pointer refs to inferred x64dbg object pointer `0x1738127A580`: `0`
- exact pointer refs to coordinate X field `0x1738127A5A4`: `0`
- exact pointer refs to family base `0x17381270000`: `0`
- strongest current-process owner-start lead: `0x1738127A4E0`
  - `6` exact pointer refs
  - local offset to candidate X: `+0xC4`
  - local offset to candidate Y: `+0xC8`
  - local offset to candidate Z: `+0xCC`
- local object window also contained coordinate-like triplets at:
  - `0x1738127A570`
  - `0x1738127A5A4`
  - `0x1738127A5D8`

Important: `0x1738127A4E0` is still **candidate-only**. It is a better
current-process owner lead than `0x1738127A580`, not a stable root.

## Code-path context from the captured hit

The captured instruction lives in a larger float-transform routine, not a
proven coordinate writer:

- code-window artifact:
  `scripts/captures/x64dbg-hit-code-20260513-0429/disasm.txt`
- probable function entry: `0x7FF79711BB70`
- hit RVA from module base `0x7FF796B50000`: `0x5CBDF3`
- nearby reads:
  - `0x7FF79711BDE7: movss xmm0, dword ptr [r8 + 0x28]`
  - `0x7FF79711BDED: movss xmm1, dword ptr [r8 + 0x24]`
  - `0x7FF79711BDF3: movss xmm2, dword ptr [r8 + 0x2C]`

This strengthens the conclusion that `r8` pointed at a transform/position
input for that call (`0x1738127A580` during the hit), but it does **not** prove
that this is the owning static coordinate source. A writer/source trace or
restart-stable chain is still required.

## Resume-safe next action

Do **not** start with another broad x64dbg watchpoint.

Preferred next slice:

1. Convert the hit artifact into an offline candidate-only access-event packet if a fresh API coordinate sample can be paired to it without timestamp skew.
2. Use the inferred object pointer/field offsets only as a local x64dbg lead:
   - object pointer `0x1738127A580`
   - fields X/Y/Z at `+0x24/+0x28/+0x2C`
3. Search for a stable owner/root around the object pointer with read-only scans first.
4. Only attach x64dbg again after a passing preflight, and always run recovery preflight after detach.

## Hard guardrails

- Candidate-only: no promotion.
- No movement/proof work until the x64dbg access evidence is normalized and the target remains responsive after the detach/recovery cycle.
- If the game becomes `responding: false` again:
  1. run `scripts/x64dbg_target_recovery.py` inspect-only,
  2. if exactly debugger-leftover suspend evidence is present, use the explicit force-resume flags,
  3. verify with `scripts/x64dbg_preflight.py`.
