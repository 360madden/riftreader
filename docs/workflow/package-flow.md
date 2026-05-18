# RiftReader Package Flow

Version: riftreader-package-flow-docs-v0.1.3
Total-Character-Count: 3163
Purpose: Document the reusable Python-first package apply/validate helper for RiftReader.

## Purpose

`riftreader-package-flow` is a reusable orchestration helper for repeated package-intake workflows.

It exists because package processing now repeats often:

1. verify package ZIP hash
2. validate package manifest and source files
3. apply through the existing repo-owned package-intake helper
4. run profile-specific validation commands
5. stop immediately on failure
6. emit JSON when requested

The helper does not replace `scripts/riftreader-package-intake.cmd`. It wraps that existing intake helper and chains validation around it.

## Files

```text
tools/riftreader_workflow/package_flow.py
scripts/riftreader-package-flow.cmd
scripts/test_package_flow.py
docs/workflow/package-flow.md
```

## Wrapper

The CMD wrapper is intentionally thin:

```text
cd /d repo root
python tools\riftreader_workflow\package_flow.py %*
exit /b %ERRORLEVEL%
```

No intake logic belongs in PowerShell or CMD.

## Supported profiles

```text
local-artifact-bridge
transport-probe
package-flow
github-review-publish
main-merge
```

## Commands

Inspect a package without applying:

```powershell
.\scripts\riftreader-package-flow.cmd --json inspect-package --package "$env:USERPROFILE\Downloads\RiftReader_TransportProbe_v0.1.1.zip"
```

Apply and validate a package:

```powershell
.\scripts\riftreader-package-flow.cmd --json apply-validate --package "$env:USERPROFILE\Downloads\RiftReader_TransportProbe_v0.1.1.zip" --expected-sha256 "<sha256>" --profile transport-probe
```

Validate already-applied files:

```powershell
.\scripts\riftreader-package-flow.cmd --json validate-current --profile transport-probe
```

Run synthetic self-test:

```powershell
.\scripts\riftreader-package-flow.cmd --json self-test
```

## Safety rules

- No `git add .`
- No commit
- No push
- No live RIFT input
- No ProofOnly
- No CE
- No x64dbg
- No arbitrary command endpoint
- No HTTP write endpoint
- No arbitrary file-read endpoint

## JSON mode

When `--json` is used, stdout is intended to be machine-readable JSON only.

## END_OF_SCRIPT_MARKER


## v0.1.1 correction

`validate-current --profile package-flow` now runs the package-flow self-test through Python directly instead of recursively invoking `scripts/riftreader-package-flow.cmd`. This keeps validation Python-owned and avoids wrapper invocation failures during chained validation. Command failure diagnostics now include return code plus stdout/stderr tails.

# END_OF_PACKAGE_FLOW_DOCS


## v0.1.2 addition

Adds the `github-review-publish` profile so Package Flow can validate the Python-owned GitHub review publish helper and its documentation/tests.

# END_OF_PACKAGE_FLOW_DOCS_V012


## v0.1.3 addition

Adds the `main-merge` profile so Package Flow can validate the Python-owned main merge helper and its documentation/tests.

# END_OF_PACKAGE_FLOW_DOCS_V013

## v0.1.4 addition

Adds the `policy-lint` profile so Package Flow can validate the executable repository policy gate.

# END_OF_PACKAGE_FLOW_DOCS_V014
