# RiftReader Drive Outbox Export and Intake Report

## Purpose

This document describes the second-stage Drive workflow helpers added after the v0.1 Drive baseline was verified.

## Helpers

```text
scripts/riftreader-drive-outbox-export.ps1
scripts/riftreader-drive-intake-report.ps1
```

## Verified baseline before this step

- Local Drive root: `G:\My Drive`
- RiftReader Drive root: `G:\My Drive\RiftReader`
- Folder tree existed and was usable.
- Harmless test ZIP/manifest creation passed.
- Inbox status detected packages/manifests.
- Manifest validation passed for the generated test manifest.

## Outbox export helper

`riftreader-drive-outbox-export.ps1` copies selected local JSON/log/status artifacts into the local Drive outbox and verifies SHA-256 after copy.

Default behavior auto-discovers recent Drive-related JSON summaries under:

```text
scripts/captures
```

and copies them to:

```text
G:\My Drive\RiftReader\outbox\run-summaries\<UTC-stamp>\
```

## Intake report helper

`riftreader-drive-intake-report.ps1` scans the local Drive inbox, groups package ZIPs and manifest files, validates manifest shape and package hashes, and reports readiness.

It does not apply packages.

## Safety

Both helpers are non-mutating with respect to the repository. They do not send input, move the player, reload UI, press screenshot keys, apply patches, or mutate Git.
