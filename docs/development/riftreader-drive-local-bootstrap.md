# RiftReader Drive Local Bootstrap and Manifest Validation

## Purpose

This document describes the first practical local Google Drive integration helpers.

## Helpers

```text
scripts/riftreader-drive-bootstrap-local.ps1
scripts/riftreader-drive-inbox-status.ps1
scripts/riftreader-drive-manifest-validate.ps1
```

## Workflow

1. Create or verify the local Google Drive-synced `RiftReader` folder tree.
2. Optionally create a harmless test package and manifest.
3. Run inbox status to detect packages and manifests.
4. Run manifest validation to verify manifest shape and package SHA-256.
5. Keep patch application as a later explicit step only.

## Safety

These helpers are discovery/setup only. They do not send movement, input, reload UI, screenshot keys, apply patches, or mutate Git state.

## Example

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-drive-bootstrap-local.ps1 -CreateTestArtifact -Json
.\scripts\riftreader-drive-inbox-status.ps1 -Json
.\scripts\riftreader-drive-manifest-validate.ps1 -Json
```

If Google Drive is installed in a nonstandard location, pass `-DriveRoot` or `-InboxRoot` explicitly.
