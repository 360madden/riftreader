# Actor-Yaw Truth Promotion Handoff

_Last updated: 2026-05-08 15:15:34 local / 2026-05-08 19:15:34Z UTC_

## TL;DR

The current player actor-yaw truth slice is committed on `main` at `facafb4` (`Promote actor yaw truth and readback smoke`). The promoted behavior-backed actor-facing lead is `0x202CA5D23E0 @ +0xD4` for `rift_x64` PID `33912`, HWND `0xE0DB2`. Movement and auto-turn remain blocked; this slice authorizes actor-facing readback truth only.

## Current repo state at handoff creation

| Fact | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` |
| Last actor-yaw truth commit | `facafb4 Promote actor yaw truth and readback smoke` |
| Remote state before this handoff commit | `main` was ahead of `origin/main` by 1 commit |
| RiftScan provider repo | `C:\RIFT MODDING\Riftscan` remained clean: `## main...origin/main` |
| Cheat Engine | Not used |
| Live movement/input in final hardening slices | None |
| RiftScan writes | None |

## Current actor-yaw truth

| Fact | Value |
|---|---|
| Promoted actor-yaw lead | `0x202CA5D23E0 @ +0xD4` |
| Candidate key | `0x202CA5D23E0|0xD4` |
| Previous rejected control | `0X202E570DB20 @ +0xD4` |
| Current truth status command | `python C:\RIFT MODDING\RiftReader\scripts\actor_yaw_current_truth_status.py --json` |
| Status command result at handoff | `status=current`, `validation.status=pass`, `issueCount=0` |
| Safety flags | `noCheatEngine=true`, `movementSent=false`, `movementAllowed=false`, `writesToRiftScan=false`, `savedVariablesUsedAsLiveTruth=false` |

## Latest no-input actor-yaw readback smoke

| Fact | Value |
|---|---|
| Command | `python C:\RIFT MODDING\RiftReader\scripts\actor_yaw_readback_smoke.py --pid 33912 --hwnd 0xE0DB2 --process-name rift_x64 --json` |
| Result | `passed` |
| Latest pointer | `C:\RIFT MODDING\RiftReader\scripts\captures\latest-actor-yaw-readback-smoke.json` |
| Latest summary | `C:\RIFT MODDING\RiftReader\scripts\captures\actor-yaw-readback-smoke-currentpid-33912-20260508-133911\run-summary.json` |
| Readback result | Both `read-player-orientation` and `capture-actor-orientation` resolved `0x202CA5D23E0 @ +0xD4` |
| Safety | `movementSent=false`; no CE; no RiftScan writes; no SavedVariables live truth |

## Committed surfaces in `facafb4`

| Area | Files / purpose |
|---|---|
| Current truth packet | `C:\RIFT MODDING\RiftReader\docs\recovery\current-actor-yaw-disambiguation.json` |
| Behavior-backed lead | `C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json` |
| Validator | `C:\RIFT MODDING\RiftReader\scripts\validate_current_actor_yaw_disambiguation.py` and `C:\RIFT MODDING\RiftReader\scripts\rift_live_test\actor_yaw_disambiguation_validation.py` |
| Status command | `C:\RIFT MODDING\RiftReader\scripts\actor_yaw_current_truth_status.py` |
| No-input smoke | `C:\RIFT MODDING\RiftReader\scripts\actor_yaw_readback_smoke.py` and `C:\RIFT MODDING\RiftReader\scripts\rift_live_test\actor_yaw_readback_smoke.py` |
| Tests | `test_current_actor_yaw_disambiguation.py`, `test_actor_yaw_current_truth_status.py`, `test_actor_yaw_readback_smoke.py`, and proof-suite adapter |
| Docs | `docs\recovery\current-truth.md`, `docs\recovery\README.md`, `docs\player-actor-yaw-candidate-ledger.md` |

## Validation already run before handoff

| Validation | Result |
|---|---|
| `python .\scripts\test_actor_yaw_readback_smoke.py` | `4/4` passed |
| `python .\scripts\test_actor_yaw_current_truth_status.py` | `4/4` passed |
| `python .\scripts\test_current_actor_yaw_disambiguation.py` | `6/6` passed |
| `python .\scripts\test_actor_yaw_candidate_ledger_docs.py` | `2/2` passed |
| `pwsh .\scripts\test-actor-facing-proof-suite.ps1` | Passed |
| `git diff --check` | Passed; only LF-to-CRLF warnings |
| RiftScan provider status | Clean |

## Hard boundaries for next work

- Do **not** use Cheat Engine unless explicitly re-authorized in the current conversation.
- Do **not** write inside `C:\RIFT MODDING\Riftscan` from RiftReader-focused work.
- Do **not** treat actor-yaw truth as movement authorization.
- Do **not** enable auto-turn until a separate turn backend is promoted.
- Run fresh `ProofOnly` before any movement/navigation attempt.
- SavedVariables may appear in reader context output but are not live truth.

## Recommended resume flow

1. Confirm repo state: `git status --short --branch`.
2. Confirm actor-yaw truth: `python .\scripts\actor_yaw_current_truth_status.py --json`.
3. If the RIFT client/PID changed, run or build a restart/rebind actor-yaw probe before trusting `0x202CA5D23E0`.
4. If exact PID/HWND are still current and you need no-input live verification, run: `python .\scripts\actor_yaw_readback_smoke.py --pid 33912 --hwnd 0xE0DB2 --process-name rift_x64 --json`.
5. For movement work, run fresh `ProofOnly` first and keep auto-turn blocked until turn backend evidence exists.

## Ready-to-paste resume prompt

```text
Resume from the newest handoff in C:\RIFT MODDING\RiftReader. Start by checking git status, then run actor_yaw_current_truth_status.py --json. Treat actor-yaw lead 0x202CA5D23E0 @ +0xD4 as current only if the validator passes for the same live PID/HWND. Do not use CE, do not write RiftScan, do not send movement until a fresh ProofOnly gate passes, and keep auto-turn blocked until a turn backend is promoted. Next likely task: build restart/rebind actor-yaw probe or resume turn-backend discovery after proving movement gate freshness.
```
