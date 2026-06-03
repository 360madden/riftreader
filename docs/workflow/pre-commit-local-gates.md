# Pre-commit local gates

## Purpose

`pre-commit` is the fast local commit gate for RiftReader. It catches basic
file, Python, and agent-definition problems before a local commit is created.

It does **not** replace the timestamped validation ledger, live RIFT proof
gates, current-truth refresh rules, promotion gates, or Git push approval.
Treat it as the first low-risk validation layer.

## Local tool install

The shared local tool lives outside the repo:

```text
C:\RIFT MODDING\tools\pre-commit\
  .venv\
  cache\
  pre-commit.cmd
```

The launcher sets:

```text
PRE_COMMIT_HOME=C:\RIFT MODDING\tools\pre-commit\cache
```

The optional manual Gitleaks secret scanner is also installed outside the repo:

```text
C:\RIFT MODDING\tools\gitleaks\
  gitleaks.exe
  gitleaks.cmd
```

The optional manual Pyright type checker is installed outside the repo:

```text
C:\RIFT MODDING\tools\pyright\
  node_modules\
  package.json
  pyright.cmd
```

Additional optional workflow tools are installed in their own folders under the
same shared tools root:

```text
C:\RIFT MODDING\tools\actionlint\
  actionlint.exe
  actionlint.cmd
C:\RIFT MODDING\tools\markdownlint-cli2\
  node_modules\
  package.json
  markdownlint-cli2.cmd
C:\RIFT MODDING\tools\osv-scanner\
  osv-scanner.exe
  osv-scanner.cmd
C:\RIFT MODDING\tools\renovate\
  node_modules\
  package.json
  renovate.cmd
  renovate-config-validator.cmd
C:\RIFT MODDING\tools\semgrep\
  .venv\
  semgrep.cmd
```

PSScriptAnalyzer is intentionally not installed or configured.

Use the bare command in a new terminal after User PATH refresh:

```powershell
pre-commit --version
```

If the current process has stale PATH, call the launcher directly:

```powershell
& "C:\RIFT MODDING\tools\pre-commit\pre-commit.cmd" --version
```

## Repo setup

`pre-commit` commands in this document assume the current directory is the
RiftReader repo root:

```powershell
Set-Location "C:\RIFT MODDING\RiftReader"
```

Running `pre-commit` from `C:\RIFT MODDING\tools\pre-commit` or another
non-repo directory will not use RiftReader's `.pre-commit-config.yaml` and Git
state. Navigate to the repo first, then run the commands.

Install the local Git hook from the repo root:

```powershell
python scripts\install_precommit_hook.py
```

This installs `.git\hooks\pre-commit` and patches it to export:

```text
PRE_COMMIT_HOME=C:\RIFT MODDING\tools\pre-commit\cache
```

Use the installer again if `pre-commit install` is run manually or the hook is
regenerated. This writes only local Git hook metadata under
`.git\hooks\pre-commit`.

## Standard commands

Run these from `C:\RIFT MODDING\RiftReader`.

| Use | Command |
|---|---|
| Check staged files before commit | `pre-commit run` |
| Check every tracked file after config changes | `pre-commit run --all-files --show-diff-on-failure` |
| Run policy lint on changed files directly | `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` |
| Run the manual policy lint pre-commit hook on explicit files | `pre-commit run riftreader-policy-lint-paths --hook-stage manual --files docs/workflow/pre-commit-local-gates.md .pre-commit-config.yaml` |
| Run the manual validation ledger smoke hook | `pre-commit run riftreader-validation-ledger-smoke --hook-stage manual` |
| Run the manual Gitleaks history secret scan | `pre-commit run riftreader-gitleaks-history-scan --hook-stage manual` |
| Run Gitleaks directly | `python scripts\gitleaks_history_scan.py` |
| Run the manual Pyright type check | `pre-commit run riftreader-pyright-manual --hook-stage manual` |
| Run Pyright directly | `python scripts\pyright_manual_gate.py` |
| Run actionlint directly | `python scripts\actionlint_check.py` |
| Verify EditorConfig directly | `python scripts\editorconfig_verify.py` |
| Run the manual Semgrep safety scan | `pre-commit run riftreader-semgrep-manual --hook-stage manual` |
| Run Semgrep directly | `python scripts\semgrep_manual_scan.py` |
| Run the manual OSV source scan | `pre-commit run riftreader-osv-scanner-manual --hook-stage manual` |
| Run OSV-Scanner directly | `python scripts\osv_scanner_manual_scan.py` |
| Validate Renovate config manually | `pre-commit run riftreader-renovate-config-validate --hook-stage manual --all-files` |
| Validate Renovate config directly | `python scripts\renovate_config_validate.py` |
| Run markdownlint on explicit docs | `python scripts\markdownlint_manual.py docs\workflow\pre-commit-local-gates.md` |
| Refresh hook environments | `pre-commit install-hooks` |
| Remove unused hook caches | `pre-commit gc` |

## Hook policy

The default commit hook should stay fast and non-live:

| Gate | Scope | Notes |
|---|---|---|
| `pre-commit-hooks` syntax/file checks | tracked staged files | JSON/YAML/TOML/Python syntax, merge-conflict, case-conflict, private-key checks. |
| `ruff critical Python lint` | `scripts/` and `tools/riftreader_workflow/` Python files | Critical parse/pyflakes checks only, including undefined-name checks; no auto-fix by default. |
| `RiftReader Python compile` | Python files | `python -m py_compile` for staged Python paths. |
| `RiftReader agent definitions validate` | `.agents/*.ts` and validator changes | Runs `scripts/agent-validate.py --verbose --json`. |
| `RiftReader actionlint GitHub workflows` | `.github/workflows/*.yml` / `.yaml` | Static-checks GitHub Actions workflows with local actionlint. |
| `RiftReader EditorConfig verify` | `.editorconfig` | Confirms the repo root EditorConfig baseline exists and keeps final-newline behavior enabled. |

Manual hooks are intentionally not automatic:

| Manual hook | Why manual |
|---|---|
| `riftreader-policy-lint-paths` | Existing full-repo policy debt should not block every commit; use explicit paths or the direct changed-scope command when needed. |
| `riftreader-validation-ledger-smoke` | Writes `.riftreader-local` validation artifacts and can take longer than a normal commit gate. |
| `riftreader-gitleaks-history-scan` | Scans Git history for secrets; useful before publish/PR, but slower than the default commit gate and depends on the local Gitleaks install. |
| `riftreader-pyright-manual` | Type checks the current Pyright bootstrap scope in `pyrightconfig.json`; keep it manual until the broad repo baseline is small enough for default gating. |
| `riftreader-semgrep-manual` | Runs repo safety rules over workflow Python; keep manual while the rule set is small and intentional. |
| `riftreader-osv-scanner-manual` | Performs dependency vulnerability discovery; useful before publish/PR, but it can touch network and can surface advisory triage work. |
| `riftreader-renovate-config-validate` | Validates Renovate config when dependency automation config changes. |
| `riftreader-markdownlint-manual` | Checks explicit Markdown paths; keep manual until existing docs have a known clean baseline. |

The current repo has four known historical/default-rule Gitleaks findings
recorded in `.gitleaksignore` by fingerprint. Keep that file narrow: add only
reviewed false positives or already-remediated historical findings, and require
a clean redacted scan before adding new ignore fingerprints.

The current Pyright config intentionally starts narrow:

```text
scripts/gitleaks_history_scan.py
scripts/install_precommit_hook.py
scripts/actionlint_check.py
scripts/editorconfig_verify.py
scripts/markdownlint_manual.py
scripts/osv_scanner_manual_scan.py
scripts/pyright_manual_gate.py
scripts/renovate_config_validate.py
scripts/semgrep_manual_scan.py
```

A broad first pass across `scripts/` and `tools/riftreader_workflow/` produced
1951 existing type errors, so broad type-checking is a cleanup campaign, not a
default commit gate yet.

## CI propagation

The GitHub `RiftReader Policy` workflow runs the pre-commit config with:

```powershell
python -m pre_commit run --all-files --show-diff-on-failure
```

The workflow installs pinned actionlint `1.7.12` before running pre-commit so the
default GitHub Actions hook has the same checker available in CI and locally.
Keep CI and local hooks aligned. If a hook is too slow or too broad for CI, move
it to the `manual` stage instead of weakening safety-critical local rules.

## Safety boundaries

- Do not put live RIFT input, movement, target-control mutation, ProofOnly,
  x64dbg, Cheat Engine, provider writes, proof promotion, Git push, or remote
  mutation inside automatic pre-commit hooks.
- Do not add auto-fixing hooks until the repo has been checked for blast radius.
- Prefer fast, deterministic checks for default commit hooks.
- Use the validation ledger for substantial or longer-running validation.

## Upgrade path

Ranked next improvements once the initial gate is stable:

| # | Improvement | Why |
|---:|---|---|
| 1 | Reduce Pyright baseline by package/import-boundary first. | Makes manual type checking actionable before default gating. |
| 2 | Add Semgrep policy rules for RiftReader safety patterns. | Converts more AGENTS policy into executable checks. |
| 3 | Consider unused-import checks after a dry run. | Useful cleanup, but can create broad churn. |
| 4 | Consider formatter hooks only after an all-files dry run. | Avoids large formatting churn in a dirty long-lived repo. |
