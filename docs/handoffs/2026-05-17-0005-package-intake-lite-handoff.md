# Compact handoff — Package Intake Lite for non-Codex workflow

Generated UTC: `2026-05-17T04:05:00Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

Added Package Intake Lite as the next offline-safe non-Codex/OpenCode milestone.
It validates manifest-based desktop ChatGPT packages, verifies SHA-256 hashes,
backs up changed files under `.riftreader-local`, writes a unified diff, runs
declared checks, and rolls back on failed checks. It does not stage, commit,
push, send live RIFT input, move, attach CE/x64dbg, or write provider repos.

## Implemented files

| Path | Purpose |
|---|---|
| `tools/riftreader_workflow/package_manifest.py` | Manifest loading, checksum validation, target allowlist enforcement, and check-command denylist. |
| `tools/riftreader_workflow/apply_package.py` | Dry-run/apply package intake runner with backups, diffs, checks, rollback, and JSON summary. |
| `scripts/riftreader-package-intake.cmd` | Thin launcher for Package Intake Lite. |
| `scripts/test_package_intake.py` | Unit tests for checksum mismatch, denied target, dry-run no-write, apply success, and rollback. |
| `docs/workflow/package-intake-lite.md` | Operator guide and manifest schema. |
| `docs/workflow/non-codex-desktop-chatgpt-workflow.md` | Updated with package-intake commands and boundaries. |
| `docs/workflow/opencode-non-codex-bridge.md` | Updated to prefer Package Intake Lite for manifest-based packages. |
| `.opencode/opencode.example.jsonc` | Updated ask-gated Package Intake Lite permissions. |

## Public commands

Inspect only:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-package-intake.cmd --package "C:\path\to\package" --json
```

Apply after review:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-package-intake.cmd --package "C:\path\to\package" --apply --json
```

## Validation performed

| Check | Result |
|---|---|
| `python -m compileall tools\riftreader_workflow scripts\test_package_intake.py scripts\test_opencode_status_packet.py` | Passed |
| `python -m unittest scripts.test_package_intake scripts.test_opencode_status_packet` | Passed, 10 tests |
| Dry-run CLI smoke with a generated local package under `.riftreader-local` | Passed, status `passed`, `dryRun=True`, `gitMutation=False` |
| `python .\scripts\validate_current_truth.py --json` | Passed, `artifactCount=51` |
| OpenCode config JSONC stripped-comment parse | Passed |
| Secret-pattern search over new package/OpenCode docs/config | No credential values found |
| `git --no-pager diff --check` | Passed; line-ending warnings only |

## Safety status

| Field | Value |
|---|---|
| Live RIFT input | Not used |
| Movement | Not used |
| CE/x64dbg attach | Not used |
| Provider writes | Not used |
| Git stage/commit/push | Not performed by the helper |
| Current proof | Still `blocked-target-drift`; old PID/address remain historical only |

## Next recommended actions

| # | Action | Why |
|---:|---|---|
| 1 | Commit/push this Package Intake Lite milestone after final review. | Preserves the next non-Codex workflow slice. |
| 2 | Add a tiny example package fixture later if desired. | Makes package authoring easier for desktop ChatGPT. |
| 3 | Extend OpenCode prompt docs with a copy/paste package intake flow. | Reduces operator friction. |
| 4 | Keep live observer and package intake separate. | Prevents local package handling from drifting into game input. |
