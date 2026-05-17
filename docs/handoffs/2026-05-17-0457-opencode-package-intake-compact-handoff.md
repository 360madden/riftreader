# Compact handoff — OpenCode package-intake compact dry-run

Generated UTC: `2026-05-17T08:57:03Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

Package Intake Lite now has a compact OpenCode/desktop ChatGPT pasteback mode
and dry-run package diff generation. OpenCode can inspect a manifest-based
desktop ChatGPT package, return changed files, blockers, warnings, safety flags,
and the diff path, while still avoiding repo target writes until `--apply` is
explicitly approved.

## Implemented files

| Path | Purpose |
|---|---|
| `tools/riftreader_workflow/apply_package.py` | Adds dry-run preview diff, `--compact`, `--compact-json`, compact artifacts, and next-action text preserving the apply boundary. |
| `tools/riftreader_workflow/operator_lite.py` | Uses compact package-intake JSON for the GUI dry-run lane. |
| `scripts/test_package_intake.py` | Verifies dry-run diff generation, compact summary safety, and compact artifact writes. |
| `scripts/test_operator_lite.py` | Verifies Operator Lite package dry-run uses `--compact-json`. |
| `docs/workflow/package-intake-lite.md` | Documents compact package intake and dry-run diff behavior. |
| `docs/workflow/opencode-non-codex-bridge.md` | Updates the OpenCode package-inspection prompt/command. |
| `docs/workflow/non-codex-desktop-chatgpt-workflow.md` | Updates the non-Codex package-inspection path. |
| `docs/workflow/operator-lite.md` | Notes compact JSON package dry-run output. |

## Safety

Dry-run still performs no repo target writes. This slice does not add staging,
commit, push, live input, movement, `/reloadui`, screenshot key, CE/x64dbg
attach, provider writes, or proof promotion.

## Resume point

Next safe OpenCode slice: add or refine launcher/prompt text that tells local
OpenCode to run package dry-run with `--compact-json` first, paste the compact
result to desktop ChatGPT, and only apply after explicit approval.
