# RiftReader Drive Outbox Export Helper

Version: v0.2.0

## Purpose

Export selected small, text-like RiftReader artifacts into the local Google Drive outbox:

```text
G:\My Drive\RiftReader\outbox\run-summaries
G:\My Drive\RiftReader\outbox\logs
G:\My Drive\RiftReader\outbox\status
```

GitHub remains the source of truth. Google Drive remains an artifact transport/archive layer.

## Default behavior

The helper is Python-first and read-only toward the repo. It copies selected files to Drive and writes:

```text
DRIVE_EXPORT_MANIFEST.json
DRIVE_EXPORT_SUMMARY.md
files-included.json
files-excluded.json
```

## Safety behavior

The helper refuses or excludes:

- files outside the repo root
- `.git`, virtualenv, `bin`, `obj`, `node_modules`, `__pycache__`
- binary-looking files with null bytes
- blocked extensions such as `.bin`, `.dmp`, `.exe`, `.dll`, `.pdb`, `.zip`
- files larger than `--max-file-bytes`
- files containing high-risk token/private-key patterns

## Example dry run

```powershell
cmd\riftreader-drive-outbox-export.cmd --default-sources --dry-run --json
```

## Example export

```powershell
cmd\riftreader-drive-outbox-export.cmd --default-sources --label current-status --json
```

## Export explicit paths

```powershell
cmd\riftreader-drive-outbox-export.cmd --source docs/recovery/current-truth.md --source handoffs/current/post-update-baseline --label baseline-status --json
```

## END_OF_DOCUMENT_MARKER
