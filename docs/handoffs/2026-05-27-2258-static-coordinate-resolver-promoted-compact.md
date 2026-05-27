# Compact handoff — static coordinate resolver promoted

Updated UTC: `2026-05-27T22:55:58Z`
Repo: `C:\RIFT MODDING\RiftReader`
Branch/status at handoff creation:

```text
## main...origin/main [ahead 6]
```

Head before this handoff file: `e00b56c Promote static player coordinate resolver`

## TL;DR

The surviving static player-coordinate chain has been **promoted** as the current coordinate resolver:

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`

Promotion is narrow and documented strongly: **coordinates only**. It is **not** full player actor/stat promotion, not heap-address promotion, and not reuse of the old PID `12148` proof pointer.

## Current truth snapshot

| Field | Value |
|---|---|
| Target | `rift_x64.exe`, PID `34176`, HWND `0x3D1544` |
| Process start UTC | `2026-05-27T18:06:53.0701460Z` |
| Module base | `0x7FF77AF40000` |
| Static root | `rift_x64+0x32EBC80` = `0x7FF77E22BC80` |
| Owner in validated epoch | `0x278C3830010` |
| Coordinate field | `0x278C3830330` |
| Latest chain coordinate | `7260.723144531, 821.425231934, 2995.659667969` |
| Latest API coordinate | `7260.720000000, 821.430000000, 2995.660000000` |
| Current blocker list | Empty |
| Old proof pointer | PID `12148` / `0x23863A26E50` is historical/stale only |

## Promotion evidence

| Sample | Stimulus | Max API/chain delta | Result |
|---|---|---:|---|
| Baseline after RRAPICOORD restore + `/reloadui` | none | `0.001933594` | passed |
| Forward displacement | `w:1200ms` | `0.001955469` | passed |
| Reverse displacement | `s:900ms`, delayed API retry | `0.004768066` | passed |
| Tolerance | n/a | `0.25` | overall passed |

Live artifact bundle:

- `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-chain-live-displacement-validation-20260527-221626\summary.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-chain-live-displacement-validation-20260527-221626\summary.md`

Tracked promotion docs:

- `docs/recovery/static-owner-coordinate-chain-promoted-2026-05-27.md`
- `docs/recovery/static-owner-coordinate-chain-promoted-2026-05-27.json`
- `docs/recovery/current-truth.md`
- `docs/recovery/current-truth.json`
- `docs/recovery/current-proof-anchor-readback.json`

## Last coherent commit

`e00b56c Promote static player coordinate resolver`

That commit:

- set `staticChainStatus.promotionAllowed=true`;
- changed target epoch to the promoted static resolver path;
- demoted PID `12148` proof anchor to historical/stale;
- added tracked Markdown/JSON promotion reports;
- preserved safety language that the resolver is coordinate-only.

Recent local commits:

```text
e00b56c (HEAD -> main) Promote static player coordinate resolver
81fd0ba Add static chain refresh approval request
13b7b35 Surface RRAPICOORD scan evidence in readiness
a97e631 Add RRAPICOORD scan diagnostic step
1d849ac Fix API reference capture defaults
537788e Document reloadui hotbar refresh gate
e91cc60 (origin/main, origin/HEAD) Track static chain current readback gate
3580772 Add static chain recovery command plan
```

## Validation already run after promotion

| Command | Result |
|---|---|
| `python -m json.tool docs\recovery\current-truth.json` | passed |
| `python -m json.tool docs\recovery\current-proof-anchor-readback.json` | passed |
| `python -m json.tool docs\recovery\static-owner-coordinate-chain-promoted-2026-05-27.json` | passed |
| `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` | passed; no blockers; warning only stale proof superseded |
| `python -m unittest scripts.test_decision_packet scripts.test_coordinate_recovery_status scripts.test_actor_chain_no_debug_status scripts.test_static_chain_promotion_readiness` | passed, `78` tests |
| `python scripts\coordinate_recovery_status.py --json` | passed; live PID `34176` running; static resolver promoted |

## Safety boundaries to preserve

| Boundary | Rule |
|---|---|
| Heap owner `0x278C3830010` | Do not hard-code as static; reacquire through module RVA every session. |
| Full actor/stat chain | Not promoted; continue separately. |
| Old PID `12148` proof anchor | Historical only; never current movement/API proof for PID `34176`. |
| Movement/route loops | Allowed only with exact target and fresh static-chain readback preflight. |
| CE/x64dbg | Not used for this promotion; do not silently reintroduce. |
| SavedVariables | Not live truth. |

## Resume checklist

1. Refresh status: `python .\tools\riftreader_workflow\decision_packet.py --json`
2. Confirm live target/static resolver: `python .\scripts\coordinate_recovery_status.py --json`
3. Before any movement loop, run a fresh promoted-chain readback against exact PID/HWND.
4. Start next lane from coordinate consumers or separate actor/stat field discovery; do not re-litigate the already-promoted coordinate resolver unless validation drifts.
5. Push only when explicitly approved; local `main` was ahead of `origin/main` before this handoff.

## Best next local work

Add or route a small consumer/readback command that uses the promoted resolver (`moduleBase + 0x32EBC80`, then `owner+0x320/+0x324/+0x328`) with exact target checks and freshness output.
