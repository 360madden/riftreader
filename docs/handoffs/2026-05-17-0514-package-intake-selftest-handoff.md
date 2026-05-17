# Compact handoff — Package intake self-test for OpenCode bridge

Generated UTC: `2026-05-17T09:14:15Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

Package Intake Lite now has a deterministic self-test path that creates a
temporary manifest package under `.riftreader-local`, dry-runs intake, emits the
same compact OpenCode/desktop ChatGPT summary, and proves the repo target file
was not written. This gives OpenCode a safe package-review smoke test without
requiring a real desktop ChatGPT package or OpenCode model execution.

## New command

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-package-intake-selftest.cmd
```

Equivalent Python:

```powershell
python .\tools\riftreader_workflow\apply_package.py --self-test --compact-json
```

## Implemented files

| Path | Purpose |
|---|---|
| `tools/riftreader_workflow/apply_package.py` | Adds `--self-test`, compact self-test metadata, and shared summary writers. |
| `scripts/riftreader-package-intake-selftest.cmd` | Thin self-test launcher. |
| `scripts/test_package_intake.py` | Verifies self-test no-target-write behavior and compact artifact output. |
| `.opencode/opencode.example.jsonc` | Allows the self-test launcher in safe OpenCode lanes. |
| `docs/workflow/package-intake-lite.md` | Documents the self-test command and ignored output path. |
| `docs/workflow/opencode-non-codex-bridge.md` | Adds the self-test to the OpenCode bridge package lane. |
| `docs/workflow/non-codex-desktop-chatgpt-workflow.md` | Adds the self-test to the non-Codex package-review path. |

## Safety

The self-test uses dry-run only. It writes generated package/intake artifacts
under `.riftreader-local\package-intake-selftest\...`, does not apply files,
does not stage/commit/push, and does not interact with live RIFT, CE, x64dbg, or
provider repos.

## Resume point

Next safe OpenCode slice: wire this self-test into Operator Lite or the OpenCode
SITREP docs if the operator wants one-click package-review smoke validation.
