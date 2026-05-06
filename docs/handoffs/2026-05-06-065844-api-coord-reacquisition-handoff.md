# 2026-05-06 06:58:44 - RiftReader API coord reacquisition handoff

## TL;DR

A new RIFT client update landed yesterday, so **old memory coord addresses and old actor-coordinate truth must be treated as stale/candidate-only until re-proven**. This session prepared a RiftReader-owned, API-first live coordinate scaffold via `RiftReaderApiProbe` so the next chat can reacquire player actor data without using stale `SavedVariables`.

**Current state:** code is prepared, addon syntax validated, addon files deployed on disk, and deployment hashes match. The running Rift client has **not** been live-reloaded by Codex in this session, and no live game input was sent.

## Hard boundaries for the next chat

| Boundary | Required behavior |
|---|---|
| SavedVariables | Do **not** use `ReaderBridgeExport.lua` / `ReaderBridgeExport_State` as live movement truth. Treat it as a post-save snapshot only. |
| Live input | Ask before sending `/reloadui`, slash commands, key presses, clicks, focus changes, or movement input. |
| Old actor memory data | Treat old actor coord addresses, old process PIDs, old HWNDs, and old `xyz` branch proof addresses as stale after the update. Revalidate before promotion. |
| API coords | Use as initial scaffold/freshness truth, not as final memory actor truth. |
| ChromaLink | Keep provider/consumer boundary: ChromaLink is external provider; RiftReader consumes published surfaces unless explicitly authorized to edit ChromaLink. |

## Repo snapshot

| Field | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` |
| HEAD | `de34e48 Add ChromaLink cross-repo guardrails` |
| Remote state at handoff creation | `main...origin/main` |
| Latest previous handoff before this one | `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-01-122706-chromalink-live-coords-resolved-handoff.md` |
| This handoff | `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-06-065844-api-coord-reacquisition-handoff.md` |

## Working tree at handoff creation

Expected uncommitted changes after this handoff is written:

```text
 M addon/RiftReaderApiProbe/main.lua
?? addon/RiftReaderApiProbe/README.md
?? addon/RiftReaderApiProbe/RiftAddon.toc
?? docs/handoffs/2026-05-06-065844-api-coord-reacquisition-handoff.md
```

No commit was made in this session.

## What changed this session

| File | Change |
|---|---|
| `C:\RIFT MODDING\RiftReader\addon\RiftReaderApiProbe\main.lua` | Added live API coordinate sampling using `Inspect.Unit.Lookup("player")` + `Inspect.Unit.Detail(playerId)`. |
| `C:\RIFT MODDING\RiftReader\addon\RiftReaderApiProbe\main.lua` | Added runtime globals `RiftReaderApiProbe_State` and `RiftReaderApiProbe_Live`. |
| `C:\RIFT MODDING\RiftReader\addon\RiftReaderApiProbe\main.lua` | Publishes marker string beginning `RRAPICOORD1|schema=1|seq=...|sampledAt=...|source=rift-api|view=Inspect.Unit.Detail(player)|status=...|x=...|y=...|z=...|savedVariablesUse=none`. |
| `C:\RIFT MODDING\RiftReader\addon\RiftReaderApiProbe\main.lua` | Refreshes every `0.10s` through `Event.System.Update.Begin` when available. |
| `C:\RIFT MODDING\RiftReader\addon\RiftReaderApiProbe\main.lua` | Added `/rap coord` to print the current coordinate sample and marker. |
| `C:\RIFT MODDING\RiftReader\addon\RiftReaderApiProbe\RiftAddon.toc` | Added deployable addon manifest for `RiftReaderApiProbe`. |
| `C:\RIFT MODDING\RiftReader\addon\RiftReaderApiProbe\README.md` | Documented the non-stale API probe workflow and reload requirement. |

## Validation already completed

| Command / check | Result |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\validate-addon.cmd` | Passed. Lua syntax validated for `ReaderBridge`, `ReaderBridgeExport`, `RiftReaderApiProbe`, and `RiftReaderValidator`. |
| `git diff --check` | Passed. Only warning was Git line ending normalization for `addon/RiftReaderApiProbe/main.lua`. |
| `C:\RIFT MODDING\RiftReader\scripts\deploy-addon.cmd` | Passed. Deployed 4 addons to 2 addon roots, 8 copy operations. |
| Hash check for deployed `RiftReaderApiProbe\main.lua` | Passed. Source and both deployed copies matched SHA256 `ACD8E5FD3819A04D9422687F75A504F8F1479BF4B9118A9B0D7A6A575E0AB9F1`. |

Deployed copies verified:

```text
C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\RiftReaderApiProbe\main.lua
C:\Users\mrkoo\Documents\RIFT\Interface\Addons\RiftReaderApiProbe\main.lua
```

## What was not validated yet

| Pending proof | Why pending |
|---|---|
| Running Rift client loaded the new addon | Requires `/reloadui` or client restart/reload. Codex did not send live input. |
| `/rap coord` runtime behavior | Requires loaded addon in live client. |
| Process memory contains `RRAPICOORD1` | Requires live-loaded addon. |
| `seq` advances between reads | Requires live memory scan after reload. |
| API coords change with movement | Requires live-loaded addon and manual or approved movement. |
| Actor-memory coordinate truth | Not reacquired yet; API probe is only the initial scaffold. |

## Exact resume sequence

Start in PowerShell:

```powershell
cd "C:\RIFT MODDING\RiftReader"
git status --short --branch
.\scripts\validate-addon.cmd
git diff --check
```

Confirm the addon is deployed:

```powershell
.\scripts\deploy-addon.cmd
$src = "C:\RIFT MODDING\RiftReader\addon\RiftReaderApiProbe\main.lua"
$targets = @(
  "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\RiftReaderApiProbe\main.lua",
  "C:\Users\mrkoo\Documents\RIFT\Interface\Addons\RiftReaderApiProbe\main.lua"
)
$srcHash = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
foreach ($t in $targets) {
  $h = (Get-FileHash -LiteralPath $t -Algorithm SHA256).Hash
  "$($h -eq $srcHash) $h $t"
}
```

Then ask the user for live-input approval before either:

1. sending `/reloadui`, or
2. asking the user to manually run `/reloadui` / restart the client.

After reload, first passive scanner probe should be:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-string RRAPICOORD1 --scan-encoding both --scan-context 512 --max-hits 8
```

Acceptance gate for API scaffold:

| Gate | Pass condition |
|---|---|
| Marker exists | At least one readable `RRAPICOORD1` marker found in live process memory. |
| Runtime source | Marker includes `source=rift-api` and `view=Inspect.Unit.Detail(player)`. |
| SavedVariables excluded | Marker includes `savedVariablesUse=none`. |
| Status pass | Marker includes `status=pass`. |
| Numeric coords | Marker includes numeric `x=`, `y=`, `z=` values. |
| Freshness | `seq` and/or `sampledAt` advances across repeated scans. |

Only after this API scaffold passes should the next chat proceed to memory actor-coordinate reacquisition.

## Why current `main` is missing the older actor-coordinate command

Older memory notes indicate `--read-player-actor-coords` and `--read-player-actor-truth` existed in the historical `xyz` actor-coordinate branch/lane. Current `main` help does not expose those commands. If needed, compare old branch code, but do **not** blindly promote its old addresses after the client update.

Suggested inspection command:

```powershell
git grep -n -- "read-player-actor-coords\|read-player-actor-truth" xyz -- .
```

## Recommended implementation after API marker proof

Add a small RiftReader-side command or script that does this repeatably:

1. scan live process for `RRAPICOORD1`,
2. parse key/value fields,
3. require `savedVariablesUse=none`,
4. require `status=pass`,
5. sample twice or three times,
6. require `seq` or `sampledAt` advancement,
7. emit JSON with x/y/z and freshness classification,
8. fail closed if marker is missing, stale, or failed.

Possible names:

| Option | Notes |
|---|---|
| `scripts\read-rift-api-probe-coords.ps1` | Fastest, script-level proof gate. |
| Reader CLI `--read-rift-api-probe-coords` | More durable and easier to integrate into later actor recovery. |
| Reader CLI `--read-player-api-coords` | Clear user-facing name, but avoid implying memory actor truth. |

## Safety classification

| Work item | Spark-safe? | Notes |
|---|---:|---|
| Update docs/handoff/status tables | Yes | Low-risk formatting/docs work. |
| Add parser script for `RRAPICOORD1` | Usually yes | Low-impact if read-only and validated. |
| Add Reader CLI command for marker parsing | Maybe | Small code change okay if scoped; use stronger model if parser touches broad memory scanner behavior. |
| Reacquire actor-memory coordinates after client update | No | Evidence-sensitive reverse engineering; use stronger model. |
| Forward movement/live navigation testing | No | Live movement path risk; require explicit approval and stronger model. |

## Top 10 next recommended actions

| # | Action | Why |
|---:|---|---|
| 1 | Re-open this handoff first in the new chat | Prevents losing the live-input and stale-data boundaries. |
| 2 | Re-run `git status --short --branch` | Confirms no drift since this handoff. |
| 3 | Re-run addon validation | Cheap guard against syntax/edit drift. |
| 4 | Confirm deployed addon hashes still match source | Ensures the client can load the intended probe. |
| 5 | Ask for `/reloadui` approval or have user reload manually | Required before live marker proof. |
| 6 | Scan for `RRAPICOORD1` after reload | Confirms the probe is loaded in live process memory. |
| 7 | Verify `seq`/`sampledAt` advances | Proves live runtime state, not stale text. |
| 8 | Add reusable parser/gate for API marker | Makes future reacquisition repeatable. |
| 9 | Use passed API coords to seed actor-memory reacquisition | Bridges from live API scaffold to memory truth. |
| 10 | Commit only after marker proof or clearly label the commit as scaffold-only | Avoids persisting unproven live proof as completed actor truth. |

## Ready-to-paste new-chat prompt

```text
Resume RiftReader coordinate reacquisition from this handoff:
C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-06-065844-api-coord-reacquisition-handoff.md

Goal: after yesterday's RIFT update, reacquire non-stale player coordinate data. Start with the new RiftReaderApiProbe API scaffold, not SavedVariables. First re-check git status and validation, then ask before live input. If I approve reload/live steps, verify the live `RRAPICOORD1` marker exists in process memory, has `savedVariablesUse=none`, `status=pass`, numeric x/y/z, and advancing seq/sample time. Only then proceed toward actor-memory coordinate reacquisition.
```
