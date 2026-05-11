# RiftReader Drive Integration v0.1 Sitrep

## Current verified status

Google Drive integration is usable as a v0.1 artifact transport/archive layer.

## Verified facts

- Google Drive connector read/list/search/create/update Docs: working.
- Google Drive local root: `G:\My Drive`.
- RiftReader Drive root: `G:\My Drive\RiftReader`.
- Local folder tree exists and is usable.
- Test ZIP/manifest workflow passed.
- Inbox status detected packages and manifests.
- Manifest validation passed for the generated test artifact.

## Repo helpers

```text
scripts/riftreader-drive-bootstrap-local.ps1
scripts/riftreader-drive-inbox-status.ps1
scripts/riftreader-drive-manifest-validate.ps1
scripts/riftreader-drive-outbox-export.ps1
scripts/riftreader-drive-intake-report.ps1
```

## Repo docs

```text
docs/development/riftreader-drive-artifact-contract.md
docs/development/riftreader-drive-local-bootstrap.md
docs/development/riftreader-drive-outbox-and-intake.md
```

## Operational model

- GitHub remains the source of truth.
- Local repo remains the execution environment.
- Google Drive is the artifact inbox/outbox/archive/status layer.
- Drive package intake remains validation/report-only until a future explicit `-Apply` mode is designed.
