---
state: active
as_of: 2026-04-21
branch: navigation
worktree: C:\RIFT MODDING\RiftReader_facing
---

# Codex Actor Yaw / Pitch No-CE Rebuild Handoff (2026-04-21)

## Scope

This handoff freezes the current no-CE rebuild pass for live actor yaw / facing
verification in:

- `C:\RIFT MODDING\RiftReader_facing`

The goal of this pass was to stop relying on Cheat Engine entirely, port the
new no-CE orientation candidate workflow into this repo, and re-test live
actor-facing recovery against the currently running Rift client.

## Snapshot metadata

| Field | Value |
|---|---|
| State | `active` |
| As of | `2026-04-21` |
| Branch | `navigation` |
| Worktree | `C:\RIFT MODDING\RiftReader_facing` |
| Live process | `rift_x64` PID `48316` |
| Live process start (UTC) | `2026-04-20T21:35:31.0680278Z` |
| Input mode | no-CE only |
| Validation status | partial |

## Current verdict

| Area | Status | Notes |
|---|---|---|
| Actor/player coordinates via memory scan | working | exact current coord triplets still scan live |
| No-CE orientation candidate search | working | now wired into this repo and returns live candidates |
| Stale behavior-backed lead detection | working | helper now fails closed with a stale-lead diagnosis |
| `--read-player-current` | degraded | current family resolution is failing on the live client |
| Live yaw/facing proof | not confirmed | controlled no-CE stimulus runs produced `0.0` yaw delta |
| Cheat Engine dependency | removed from this pass | no CE attach / Lua / bootstrap used |

## What changed in this pass

| File | Change |
|---|---|
| `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Cli\ReaderOptions.cs` | added no-CE orientation candidate options |
| `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Cli\ReaderOptionsParser.cs` | added `--find-player-orientation-candidate` and ledger parsing/validation |
| `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Program.cs` | wired no-CE candidate search into the reader |
| `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Models\OrientationCandidateLedgerLoader.cs` | added candidate-ledger support |
| `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Models\PlayerOrientationCandidateFinder.cs` | added the no-CE candidate finder |
| `C:\RIFT MODDING\RiftReader_facing\scripts\find-player-orientation-candidate.ps1` | added repo-local no-CE search wrapper |
| `C:\RIFT MODDING\RiftReader_facing\scripts\test-actor-yaw-candidates.ps1` | added repo-local no-CE validation harness and ReaderBridge snapshot fallback when `--read-player-current` fails |
| `C:\RIFT MODDING\RiftReader_facing\scripts\send-rift-key.ps1` | added foreground `SendInput` key helper |
| `C:\RIFT MODDING\RiftReader_facing\scripts\send-rift-key-ahk.ps1` | added optional AHK fallback helper |
| `C:\RIFT MODDING\RiftReader_facing\scripts\send-rift-key-ahk.ahk` | added optional AHK key script |
| `C:\RIFT MODDING\RiftReader_facing\scripts\post-rift-command.ps1` | stopped defaulting to a CE background-focus process |
| `C:\RIFT MODDING\RiftReader_facing\scripts\post-rift-key.ps1` | stopped defaulting to a CE background-focus process |
| `C:\RIFT MODDING\RiftReader_facing\scripts\capture-actor-orientation.ps1` | now detects and rejects stale behavior-backed leads using the live process start time |

## Validation run

| Command / check | Result |
|---|---|
| `dotnet build C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\RiftReader.Reader.csproj` | passed |
| `C:\RIFT MODDING\RiftReader_facing\scripts\refresh-readerbridge-export.ps1 -NoReader -NoAhkFallback` | passed |
| `dotnet run --project ... -- --process-name rift_x64 --scan-readerbridge-player-coords --scan-context 32 --max-hits 8 --json` | found 8 exact coord hits for `7207.4296875 / 871.76995849609 / 3025.2099609375` |
| `C:\RIFT MODDING\RiftReader_facing\scripts\find-player-orientation-candidate.ps1 -Json` | returned 8 live pointer-hop candidates |
| `C:\RIFT MODDING\RiftReader_facing\scripts\find-player-orientation-candidate.ps1 -Json -MaxHits 16 ...` | returned 16 candidates including second-hop pointer-hop candidates |
| `C:\RIFT MODDING\RiftReader_facing\scripts\test-actor-yaw-candidates.ps1 ... -StimulusMode SendInput -StimulusKey A` | completed, but all tested candidates stayed at `YawDeltaDegrees = 0.0` |
| Raw live coord hit reads before/after `W` | no change at tested coord addresses |
| `C:\RIFT MODDING\RiftReader_facing\scripts\capture-actor-orientation.ps1 -Json` | now fails with an explicit stale-lead error instead of `ReadProcessMemory` noise |

## Key findings

### 1) Coordinates are still truth-bearing

Current player coordinates continue to scan cleanly in live process memory.
The no-CE rebuild did not break raw coordinate discovery.

### 2) The no-CE orientation scan is now live in this repo

The facing repo can now:

- scan for live orientation candidates without CE
- emit candidate JSON artifacts locally
- validate candidate rows against a controlled no-CE stimulus harness

Important artifacts created in this pass:

- `C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-orientation-candidate-search.json`
- `C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-orientation-candidate-search-16.json`
- `C:\RIFT MODDING\RiftReader_facing\scripts\captures\actor-yaw-candidate-test.json`
- `C:\RIFT MODDING\RiftReader_facing\scripts\captures\actor-yaw-candidate-test-16.json`

### 3) The old cached lead is stale for the current client

The behavior-backed lead file:

- `C:\RIFT MODDING\RiftReader_facing\scripts\actor-facing-behavior-backed-lead.json`

contains a validated timestamp of:

- `2026-04-20T09:09:00Z`

which predates the current live process start:

- `2026-04-20T21:35:31.0680278Z`

The helper now detects that mismatch and fails closed.

### 4) The remaining blocker is live proof, not candidate discovery

The current pass did **not** produce any measured turn or movement from the
automated no-CE key path:

- `A` stimulus produced `0.0` yaw delta across tested candidates
- `W` stimulus produced `0.0` delta on tested live coord addresses

That means the next pass should first prove that the game is really accepting
the live input path before promoting or rejecting more facing candidates.

## Broken or drifted anchors

| Area | Result | Notes |
|---|---|---|
| `--read-player-current` | broken on current live family | failing with `Unable to resolve a full current-player snapshot from family 'fam-CEC3708F'` |
| Cached behavior-backed lead | stale | now diagnosed explicitly |
| Live input proof | unverified | current automated tests show no movement / turn effect |
| Truth-bearing facing source for the current session | unresolved | candidates exist, but none have been proven responsive |

## Recommended first action in the next conversation

- Prove the live no-CE input path first using a visibly focused Rift window and a tiny movement/turn check; do **not** promote any new facing lead until a `W` or `A` input causes measurable change in either raw live coord hits or a candidate yaw sample.

## Rolling queue

- **Active:** prove that the live no-CE input path actually affects the running `rift_x64` window
- **Next:** once live input is proven, rerun `find-player-orientation-candidate.ps1` and `test-actor-yaw-candidates.ps1` to isolate one responsive candidate
- **Validation:** raw live coord addresses change after `W` or one candidate shows `|YawDeltaDegrees| >= 1.0` with coord drift `<= 0.35`
- **Stop if:** focused verified input still produces zero movement and zero yaw change; at that point the blocker is the control path, not the candidate scorer
- **Commit when:** a fresh current-session facing lead can be regenerated and `capture-actor-orientation.ps1` succeeds without `-IgnoreBehaviorBackedLead`

## Notes for the next agent

- Do **not** use Cheat Engine. The user explicitly banned it.
- Treat `C:\RIFT MODDING\RiftReader_facing\docs\recovery\current-truth.md` as stale on the actor-facing section until a fresh current-session lead is validated.
- The current repo changes are uncommitted as of this handoff.
