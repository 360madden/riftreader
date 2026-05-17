# Package Intake Lite

Created: 2026-05-17
Scope: Optional local intake of desktop ChatGPT packages for RiftReader when
Codex is unavailable or not being used.

## Verdict

Package Intake Lite validates and optionally applies a package with an explicit
manifest. It is local-only and fail-closed. It never stages, commits, pushes,
sends live RIFT input, attaches CE/x64dbg, writes provider repos, or treats stale
proof as current truth.

## Package shape

A package can be a directory or `.zip` containing:

```text
riftreader-package-manifest.json
files\...
```

Manifest schema v1:

```json
{
  "schemaVersion": 1,
  "packageName": "example",
  "files": [
    {
      "source": "files/new-doc.md",
      "target": "docs/example/new-doc.md",
      "sha256": "<64-char sha256>"
    }
  ],
  "checks": [
    {
      "name": "diff-check",
      "args": ["git", "--no-pager", "diff", "--check"],
      "expectedExitCodes": [0],
      "timeoutSeconds": 60
    }
  ]
}
```

## Commands

Inspect only; no repo target writes:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-package-intake.cmd --package "C:\path\to\package" --json
```

Compact inspection for OpenCode/desktop ChatGPT pasteback:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-package-intake.cmd --package "C:\path\to\package" --compact
.\scripts\riftreader-package-intake.cmd --package "C:\path\to\package" --compact-json
.\scripts\riftreader-opencode-package-review.cmd "C:\path\to\package-or.zip"
```

Apply after review:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-package-intake.cmd --package "C:\path\to\package" --apply --json
```

## Safety behavior

| Behavior | Rule |
|---|---|
| Target paths | Must be relative to the RiftReader repo and explicitly listed in the manifest. |
| Checksums | Every source file must match its declared SHA-256. |
| Backups | Existing targets are backed up under `.riftreader-local\package-intake\...`. |
| Diffs | Dry-run and apply both write a unified package diff under `.riftreader-local\package-intake\...`. |
| Checks | Manifest checks run after apply unless `--no-checks` is passed. |
| Rollback | Failed checks roll back changed files and return blocked status. |
| Git | No stage, commit, push, reset, clean, or hidden Git mutation. |
| Live game | No movement, no input, no `/reloadui`, no screenshot key, no CE/x64dbg. |

Denied target prefixes include `.git`, `.riftreader-local`, `scripts/captures`,
and `scripts/sessions`.

Denied check command fragments include `git add`, `git commit`, `git push`,
`git reset`, `git clean`, `send-rift-key`, `post-rift-key`, `cheatengine`, and
`x64dbg`.

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | Validation or apply completed successfully. |
| `1` | Script/package error, malformed manifest, checksum failure, or unexpected exception. |
| `2` | Apply was blocked safely, usually because a declared post-apply check failed and rollback ran. |

## Output contract

Each run writes:

```text
.riftreader-local\package-intake\<timestamp>\package-intake-summary.json
.riftreader-local\package-intake\<timestamp>\compact-package-intake-summary.json
.riftreader-local\package-intake\<timestamp>\COMPACT_PACKAGE_INTAKE.md
.riftreader-local\package-intake\<timestamp>\package.diff
```

The summary includes:

- `status`;
- `blockers`;
- `warnings`;
- `errors`;
- `changedFiles`;
- `backups`;
- check command envelopes;
- rollback result;
- safety flags;
- compact `nextRecommendedAction` text preserving the apply/review/commit boundary.
