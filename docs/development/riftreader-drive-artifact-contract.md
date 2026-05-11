# RiftReader Drive Artifact Contract

## Purpose

Google Drive is used as a controlled artifact transport and archive layer for RiftReader work.

GitHub remains the source of truth. The local repository remains the execution environment. Google Drive is used to reduce copy/paste payloads, preserve handoffs, archive run outputs, and support phone-visible status review.

## Drive role

| Area | Role |
|---|---|
| Inbox | Patch packages, manifests, handoffs, external artifacts |
| Outbox | Run summaries, logs, screenshots, machine-readable results |
| Archive | Historical patch packages and run artifacts |
| Status | Current workflow summaries readable from phone or another device |

## Recommended Drive structure

```text
RiftReader/
  inbox/
    patches/
    manifests/
    handoffs/
  outbox/
    run-summaries/
    logs/
    screenshots/
  archive/
    patches/
    runs/
  status/
```

## Connector limitation

The current Google Drive connector can list, search, fetch, create native Google Workspace files, and update Docs content. No direct folder-create action is exposed in the current tool listing.

Until folder creation is automated elsewhere, create the folder tree manually in Drive or use a local sync/API helper outside the connector.

## Naming convention

| Artifact | Pattern |
|---|---|
| Patch package | `RiftReader_<Purpose>Patch_v<semver>_<UTC>.zip` |
| Manifest | `RiftReader_<Purpose>Patch_v<semver>_<UTC>.manifest.json` |
| Run summary | `RiftReader_RunSummary_<Workflow>_<UTC>.json` |
| Handoff | `RIFTREADER_HANDOFF_<YYYY-MM-DD>_<topic>.md` |

## Patch package requirements

Every patch package should include:

- `manifest.json`
- `README.md`
- `tools/apply_*.py` when repo mutation is needed
- `payload/` files when adding or replacing repo content
- SHA-256 values for important payload files when practical
- explicit safety metadata:
  - `movementSent`
  - `inputSent`
  - `reloaduiSent`
  - `screenshotKeySent`
  - `noCheatEngine`
  - `githubConnectorWrites`

## Manifest minimum fields

```json
{
  "schemaVersion": 1,
  "packageKind": "riftreader-example",
  "packageVersion": "v0.1.0",
  "createdUtc": "2026-05-11T00:00:00Z",
  "targetRepo": "360madden/riftreader",
  "targetFiles": [],
  "commitMessage": "Describe change",
  "movementSentByApplier": false,
  "inputSentByApplier": false,
  "reloaduiSentByApplier": false,
  "screenshotKeySentByApplier": false,
  "noCheatEngine": true,
  "payloadSha256": {}
}
```

## Repo integration rules

1. Do not make Google Drive the canonical source of repo truth.
2. Do not apply files from Drive directly into the repo without validation.
3. Preferred flow: Drive package -> local intake helper -> validation -> explicit git commit -> push/verify.
4. Reusable/high-value workflows should be promoted into repo helpers.
5. Helper behavior should be configurable through command-line switches.
6. JSON output must remain clean in machine-readable mode.
7. Human output may be readable/progress-oriented, but must not corrupt JSON.

## Initial repo helper scope

The first repo helper is intentionally conservative:

```text
scripts/riftreader-drive-inbox-status.ps1
```

It inspects a local Drive-synced folder path, lists package/manifest candidates, computes SHA-256 for discovered files, and writes JSON status. It does not apply patches.

## Safety

Drive intake helpers must default to discovery/status only.

They must not:

- send movement/input
- run `/reloadui`
- press screenshot keys
- mutate Git state
- apply patches
- trust package contents without validation
- treat Drive as source of truth over Git
